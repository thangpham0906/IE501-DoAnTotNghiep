"""Supervisor quản lý vòng đời, trạng thái nạp và giải phóng của Translation và ASR engines."""

import asyncio
import anyio
import logging
import threading
from collections.abc import Callable
from typing import Any, Literal

from src.web_app.core.config import WebSettings
from src.web_app.core.exceptions import ModelNotReadyError
from src.web_app.core.language import SUPPORTED_DIRECTIONS
from src.web_app.services.asr.base import ASREngine, ASRMetadata
from src.web_app.services.translation.base import (
    BundleModelInfo,
    InferenceEngine,
    TranslationMetadata,
)

logger = logging.getLogger("web_app.supervisor")

EngineState = Literal["loading", "ready", "failed", "disabled", "stopping"]
OverallHealthStatus = Literal["ready", "loading", "degraded"]


class EngineSupervisor:
    """Quản lý trạng thái và tác vụ nền của TranslationEngine và ASREngine."""

    def __init__(
        self,
        settings: WebSettings,
        translation_engine: InferenceEngine,
        asr_engine: ASREngine | None,
    ) -> None:
        self.settings = settings
        self.translation_engine = translation_engine
        self.asr_engine = asr_engine

        # Trạng thái ban đầu
        self.translation_state: EngineState = "loading"
        self.asr_state: EngineState = "disabled" if asr_engine is None else "loading"

        self.translation_error: str | None = None
        self.asr_error: str | None = None

        # Snapshot an toàn phản ánh cấu hình ban đầu (§4.5)
        self._translation_engine_type = settings.TRANSLATION_ENGINE_TYPE
        self._translation_is_mock = settings.TRANSLATION_ENGINE_TYPE == "mock"
        self._validated_translation_meta: TranslationMetadata | None = None
        self._validated_translation_directions: list[str] = []
        self._validated_bundle_info: BundleModelInfo | None = None

        self._asr_engine_type = settings.ASR_ENGINE_TYPE
        self._asr_is_mock = settings.ASR_ENGINE_TYPE == "mock"
        self._validated_asr_meta: ASRMetadata | None = None

        # Đồng bộ luồng nạp thực tế (C06): theo dõi cả work đã nhận/chờ dispatch và active thread IDs
        self._loader_lock = threading.Lock()
        self._pending_load_count: int = 0
        self._active_loader_tids: set[int] = set()
        self._loader_finished_event = threading.Event()
        self._loader_finished_event.set()  # Ban đầu không có luồng nào chạy

        self._loaded_event = anyio.Event()
        self._is_stopping: bool = False
        self._unloaded: bool = False
        self._late_load_exceptions: list[BaseException] = []

    def is_loader_running(self) -> bool:
        """Kiểm tra xem có bất kỳ load job nào đang chờ dispatch hoặc đang chạy trong OS thread."""
        with self._loader_lock:
            return self._pending_load_count > 0 or len(self._active_loader_tids) > 0

    async def wait_loaded(self) -> None:
        """Chờ quá trình nạp engine bất đồng bộ hoàn tất."""
        await self._loaded_event.wait()

    def is_translation_ready(self) -> bool:
        """Kiểm tra engine dịch đã sẵn sàng phục vụ."""
        with self._loader_lock:
            return self.translation_state == "ready" and self.translation_engine.is_ready()

    def is_asr_ready(self) -> bool:
        """Kiểm tra engine ASR đã sẵn sàng phục vụ."""
        with self._loader_lock:
            if self.asr_engine is None:
                return False
            return self.asr_state == "ready" and self.asr_engine.is_ready()

    def is_engine_failed(self, task_type: str) -> bool:
        """Kiểm tra engine tương ứng có đang ở trạng thái failed hay không."""
        with self._loader_lock:
            if task_type == "translation":
                return self.translation_state == "failed"
            if task_type == "asr":
                return self.asr_state == "failed"
            return False

    def handle_fatal_error(self, task_type: str, exc: BaseException) -> None:
        """Đánh dấu engine thất bại vĩnh viễn khi gặp lỗi tài nguyên nghiêm trọng."""
        if task_type == "translation":
            self.mark_translation_failed(f"Fatal resource error: {exc}")
        elif task_type == "asr":
            self.mark_asr_failed(f"Fatal resource error: {exc}")

    def get_overall_status(self) -> OverallHealthStatus:
        """Tính toán trạng thái tổng thể cho GET /api/health (§4.5)."""
        with self._loader_lock:
            if self.translation_state in ("failed", "stopping") or self.asr_state in ("failed", "stopping"):
                return "degraded"

            if self.translation_state == "loading" or (self.asr_engine is not None and self.asr_state == "loading"):
                return "loading"

            if (
                self.translation_state == "ready"
                and self.translation_engine.is_ready()
                and (self.asr_engine is None or (self.asr_state == "ready" and self.asr_engine.is_ready()))
            ):
                return "ready"

            return "degraded"

    async def _dispatch_load(
        self,
        component_name: str,
        load_fn: Callable[[Any], None],
        arg: Any,
    ) -> bool:
        """Đăng ký và thực thi tác vụ load trong threadpool, theo dõi cả trạng thái chờ và chạy."""
        with self._loader_lock:
            if self._is_stopping:
                return False
            self._pending_load_count += 1
            self._loader_finished_event.clear()

        thread_started = False

        def sync_worker() -> None:
            nonlocal thread_started
            tid = threading.get_ident()
            with self._loader_lock:
                thread_started = True
                self._active_loader_tids.add(tid)
                should_run = not self._is_stopping

            try:
                if should_run:
                    load_fn(arg)
            finally:
                with self._loader_lock:
                    self._active_loader_tids.discard(tid)
                    self._pending_load_count -= 1
                    if self._pending_load_count == 0 and not self._active_loader_tids:
                        self._loader_finished_event.set()

        try:
            await anyio.to_thread.run_sync(sync_worker)
            with self._loader_lock:
                return not self._is_stopping
        except BaseException:
            with self._loader_lock:
                if not thread_started:
                    self._pending_load_count -= 1
                    if self._pending_load_count == 0 and not self._active_loader_tids:
                        self._loader_finished_event.set()
            raise

    def _validate_translation_contract(self) -> None:
        """Kiểm tra toàn bộ hợp đồng metadata bắt buộc cho translation engine (C12)."""
        metadata = self.translation_engine.get_metadata()
        if not metadata:
            raise ModelNotReadyError("Translation metadata là None.")
        if not metadata.model_id or not metadata.model_id.strip():
            raise ModelNotReadyError("Thiếu model_id bắt buộc trong translation metadata.")
        if not metadata.artifact_id or not metadata.artifact_id.strip():
            raise ModelNotReadyError("Thiếu artifact_id bắt buộc trong translation metadata.")
        if not metadata.checkpoint_version or not metadata.checkpoint_version.strip():
            raise ModelNotReadyError("Thiếu checkpoint_version bắt buộc trong translation metadata.")
        if not metadata.tokenizer_version or not metadata.tokenizer_version.strip():
            raise ModelNotReadyError("Thiếu tokenizer_version bắt buộc trong translation metadata.")
        if metadata.engine_type not in ("mock", "pipeline"):
            raise ModelNotReadyError(f"engine_type không hợp lệ: {metadata.engine_type}")

        if metadata.engine_type == "mock" and metadata.is_mock is not True:
            raise ModelNotReadyError("Engine type 'mock' phải có is_mock=True.")
        if metadata.engine_type == "pipeline" and metadata.is_mock is not False:
            raise ModelNotReadyError("Engine type 'pipeline' phải có is_mock=False.")

        directions = self.translation_engine.get_supported_directions()
        if not directions:
            raise ModelNotReadyError("Translation engine không công bố chiều dịch nào.")
        for d in directions:
            if d not in SUPPORTED_DIRECTIONS:
                raise ModelNotReadyError(f"Chiều dịch không hợp lệ trong supported_directions: {d}")

        bundle_info = self.translation_engine.get_bundle_info()
        if bundle_info is not None:
            if not bundle_info.id or not bundle_info.id.strip():
                raise ModelNotReadyError("Bundle id rỗng.")
            if bundle_info.id != metadata.model_id:
                raise ModelNotReadyError(
                    f"Bundle id ({bundle_info.id}) không khớp model_id ({metadata.model_id})."
                )
            if not bundle_info.name or not bundle_info.name.strip():
                raise ModelNotReadyError("Bundle name rỗng.")
            if not bundle_info.bundle_version or not bundle_info.bundle_version.strip():
                raise ModelNotReadyError("Bundle bundle_version rỗng.")
            if bundle_info.engine_type != metadata.engine_type:
                raise ModelNotReadyError("Bundle engine_type không khớp metadata engine_type.")
            if bundle_info.is_mock != metadata.is_mock:
                raise ModelNotReadyError("Bundle is_mock không khớp metadata is_mock.")
            if not bundle_info.supported_directions:
                raise ModelNotReadyError("Bundle supported_directions rỗng.")
            for bd in bundle_info.supported_directions:
                if bd not in directions:
                    raise ModelNotReadyError(f"Bundle chiều dịch {bd} không có trong supported_directions.")

        self._validated_translation_meta = metadata
        self._validated_translation_directions = list(directions)
        self._validated_bundle_info = bundle_info
        self._translation_engine_type = metadata.engine_type
        self._translation_is_mock = metadata.is_mock
        logger.info(
            "Translation engine đã nạp thành công: model_id=%s engine_type=%s is_mock=%s",
            metadata.model_id,
            metadata.engine_type,
            metadata.is_mock,
        )

    def _validate_asr_contract(self) -> None:
        """Kiểm tra toàn bộ hợp đồng metadata bắt buộc cho ASR engine (C12)."""
        if self.asr_engine is None:
            return
        asr_meta = self.asr_engine.get_metadata()
        if not asr_meta:
            raise ModelNotReadyError("ASR metadata là None.")
        if not asr_meta.model_id or not asr_meta.model_id.strip():
            raise ModelNotReadyError("Thiếu model_id bắt buộc trong ASR metadata.")
        if not asr_meta.model_version or not asr_meta.model_version.strip():
            raise ModelNotReadyError("Thiếu model_version bắt buộc trong ASR metadata.")
        if asr_meta.engine_type not in ("mock", "whisper"):
            raise ModelNotReadyError(f"ASR engine_type không hợp lệ: {asr_meta.engine_type}")

        if asr_meta.engine_type == "mock" and asr_meta.is_mock is not True:
            raise ModelNotReadyError("ASR engine type 'mock' phải có is_mock=True.")
        if asr_meta.engine_type == "whisper" and asr_meta.is_mock is not False:
            raise ModelNotReadyError("ASR engine type 'whisper' phải có is_mock=False.")

        self._validated_asr_meta = asr_meta
        self._asr_engine_type = asr_meta.engine_type
        self._asr_is_mock = asr_meta.is_mock
        logger.info(
            "ASR engine đã nạp thành công: model_id=%s engine_type=%s is_mock=%s",
            asr_meta.model_id,
            asr_meta.engine_type,
            asr_meta.is_mock,
        )

    async def load_engines(self) -> None:
        """Nạp các engine bất đồng bộ ngoài event loop với xác thực hợp đồng nghiêm ngặt (C06, C12)."""
        try:
            # 1. Nạp Translation Engine
            with self._loader_lock:
                if self._is_stopping:
                    self.translation_state = "stopping"
                    if self.asr_state != "disabled":
                        self.asr_state = "stopping"
                    return
                self.translation_state = "loading"

            bundle_path = self.settings.resolve_path(self.settings.MODEL_BUNDLE_PATH)
            translation_loaded = False
            try:
                dispatched = await self._dispatch_load(
                    "translation",
                    self.translation_engine.load,
                    bundle_path,
                )
                if dispatched:
                    translation_loaded = True
            except BaseException as e:
                with self._loader_lock:
                    if self._is_stopping or isinstance(e, asyncio.CancelledError):
                        self.translation_state = "stopping"
                        if self.asr_state != "disabled":
                            self.asr_state = "stopping"
                        self._late_load_exceptions.append(e)
                        return
                    self.translation_state = "failed"
                    self.translation_error = str(e)
                logger.error("Nạp translation engine thất bại: %s", e)

            with self._loader_lock:
                if self._is_stopping:
                    self.translation_state = "stopping"
                    if self.asr_state != "disabled":
                        self.asr_state = "stopping"
                    return

                if translation_loaded:
                    if not self.translation_engine.is_ready():
                        self.translation_state = "failed"
                        self.translation_error = "Translation engine báo chưa sẵn sàng sau load()."
                        logger.error(self.translation_error)
                    else:
                        try:
                            self._validate_translation_contract()
                            self.translation_state = "ready"
                        except Exception as val_err:
                            self.translation_state = "failed"
                            self.translation_error = str(val_err)
                            logger.error("Xác thực metadata translation thất bại: %s", val_err)

            # 2. Nạp ASR Engine (nếu được cấu hình)
            with self._loader_lock:
                if self._is_stopping:
                    self.translation_state = "stopping"
                    if self.asr_state != "disabled":
                        self.asr_state = "stopping"
                    return

                if self.asr_engine is None:
                    self.asr_state = "disabled"
                    logger.info("ASR engine ở trạng thái disabled theo cấu hình.")
                    return

                self.asr_state = "loading"

            model_path = self.settings.resolve_path(self.settings.WHISPER_MODEL_PATH)
            asr_loaded = False
            try:
                asr_dispatched = await self._dispatch_load(
                    "asr",
                    self.asr_engine.load,
                    model_path,
                )
                if asr_dispatched:
                    asr_loaded = True
            except BaseException as e:
                with self._loader_lock:
                    if self._is_stopping or isinstance(e, asyncio.CancelledError):
                        self.asr_state = "stopping"
                        self._late_load_exceptions.append(e)
                        return
                    self.asr_state = "failed"
                    self.asr_error = str(e)
                logger.error("Nạp ASR engine thất bại: %s", e)

            with self._loader_lock:
                if self._is_stopping:
                    self.asr_state = "stopping"
                    return

                if asr_loaded:
                    if not self.asr_engine.is_ready():
                        self.asr_state = "failed"
                        self.asr_error = "ASR engine báo chưa sẵn sàng sau load()."
                        logger.error(self.asr_error)
                    else:
                        try:
                            self._validate_asr_contract()
                            self.asr_state = "ready"
                        except Exception as val_err:
                            self.asr_state = "failed"
                            self.asr_error = str(val_err)
                            logger.error("Xác thực metadata ASR thất bại: %s", val_err)
        finally:
            self._loaded_event.set()

    def mark_translation_failed(self, reason: str) -> None:
        """Đánh dấu engine dịch thất bại do lỗi tài nguyên nghiêm trọng."""
        with self._loader_lock:
            if not self._is_stopping:
                self.translation_state = "failed"
            self.translation_error = reason
        logger.error("Đánh dấu translation engine FAILED: %s", reason)

    def mark_asr_failed(self, reason: str) -> None:
        """Đánh dấu engine ASR thất bại do lỗi tài nguyên nghiêm trọng."""
        with self._loader_lock:
            if not self._is_stopping:
                self.asr_state = "failed"
            self.asr_error = reason
        logger.error("Đánh dấu ASR engine FAILED: %s", reason)

    async def shutdown(self, runner_clean: bool, grace_sec: float | None = None) -> None:
        """Chuyển trạng thái stopping và giải phóng tài nguyên nếu an toàn (C06)."""
        with self._loader_lock:
            self._is_stopping = True
            self.translation_state = "stopping"
            if self.asr_state != "disabled":
                self.asr_state = "stopping"

        # Nếu loader thread còn đang chạy trong background OS thread hoặc đang chờ dispatch, đợi trong thời gian grace
        if self.is_loader_running() and grace_sec is not None and grace_sec > 0:
            try:
                await anyio.to_thread.run_sync(self._loader_finished_event.wait, grace_sec)
            except Exception:
                pass

        # C06: Chỉ unload khi KHÔNG còn worker inference và KHÔNG còn loader thread nào đang chạy
        with self._loader_lock:
            loader_still_running = self._pending_load_count > 0 or len(self._active_loader_tids) > 0
            if runner_clean and not loader_still_running:
                if not self._unloaded:
                    self._unloaded = True
                    try:
                        self.translation_engine.unload()
                        logger.info("Đã unload translation engine thành công.")
                    except Exception as e:
                        logger.warning("Ngoại lệ khi unload translation engine: %s", e)

                    if self.asr_engine is not None:
                        try:
                            self.asr_engine.unload()
                            logger.info("Đã unload ASR engine thành công.")
                        except Exception as e:
                            logger.warning("Ngoại lệ khi unload ASR engine: %s", e)
            else:
                logger.warning(
                    "Không gọi unload() lên các engine vì runner_clean=%s, loader_running=%s.",
                    runner_clean,
                    loader_still_running,
                )
