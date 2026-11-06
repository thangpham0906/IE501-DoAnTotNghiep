"""Route POST /api/asr/transcribe (§4.4, §5.3)."""

import logging
import time
from typing import Any
from fastapi import APIRouter, Request
from starlette.datastructures import FormData, UploadFile
from starlette.formparsers import MultiPartException, MultiPartParser

from src.web_app.api.utils import execute_with_disconnect_monitor
from src.web_app.core.exceptions import (
    ASRFailureError,
    AppError,
    AudioTooLargeError,
    InvalidInputError,
    ModelNotReadyError,
    NoSpeechDetectedError,
    UnsupportedASRLanguageError,
)
from src.web_app.core.schemas import ASRModelMetadata, TranscribeResponse
from src.web_app.services.asr.audio import validate_wav
from src.web_app.services.asr.base import ASRResult, AudioInput
from src.web_app.services.inference_runner import InferenceRunner
from src.web_app.services.supervisor import EngineSupervisor

logger = logging.getLogger("web_app.routes.asr")

router = APIRouter()


class SafeASRMultiPartParser(MultiPartParser):
    """Multipart parser an toàn cho ASR: giới hạn đúng 1 file + max 1 field và theo dõi toàn bộ spool files (C08)."""

    def __init__(self, headers: Any, stream: Any) -> None:
        # C08: Giới hạn đúng max 1 file và max 1 field văn bản ngay khi parse
        super().__init__(headers, stream, max_files=1, max_fields=1)
        self.created_spools: list[Any] = []
        self._ended: bool = False
        self._part_in_progress: bool = False

    def on_part_begin(self) -> None:
        super().on_part_begin()
        self._part_in_progress = True

    def on_part_end(self) -> None:
        super().on_part_end()
        self._part_in_progress = False

    def on_headers_finished(self) -> None:
        super().on_headers_finished()
        if self._files_to_close_on_error:
            spool = self._files_to_close_on_error[-1]
            if spool not in self.created_spools:
                self.created_spools.append(spool)

    def on_end(self) -> None:
        super().on_end()
        self._ended = True

    async def parse_safe(self) -> tuple[FormData, list[UploadFile], list[Any]]:
        try:
            form = await self.parse()
            # C08: Kiểm tra toàn bộ container có được kết thúc hợp lệ và không có part dở
            if not self._ended or self._part_in_progress:
                raise MultiPartException("Dữ liệu multipart bị cắt cụt trước khi kết thúc container.")

            upload_files = [val for _, val in self.items if isinstance(val, UploadFile)]
            return form, upload_files, self.created_spools
        except BaseException:
            for s in self.created_spools:
                try:
                    s.close()
                except Exception:
                    pass
            raise


@router.post("/asr/transcribe", response_model=TranscribeResponse)
async def transcribe_audio(request: Request) -> TranscribeResponse:
    """Nhận diện giọng nói từ tệp WAV tiếng Việt (§4.4, §5.3)."""
    req_start = time.monotonic()
    settings = request.app.state.settings
    supervisor: EngineSupervisor = request.app.state.supervisor
    runner: InferenceRunner = request.app.state.runner
    request_id = getattr(request.state, "request_id", "unknown-request")

    all_upload_files: list[UploadFile] = []
    all_created_spools: list[Any] = []

    try:
        # 1. Đọc và phân tích Multipart Form với SafeASRMultiPartParser
        content_type = request.headers.get("content-type", "")
        if "multipart/form-data" not in content_type:
            raise InvalidInputError("Yêu cầu Content-Type là multipart/form-data.")

        parser = SafeASRMultiPartParser(request.headers, request.stream())
        try:
            form, all_upload_files, all_created_spools = await parser.parse_safe()
        except Exception as e:
            logger.warning(
                "Lỗi phân tích multipart form: request_id=%s exc=%s",
                request_id,
                e,
            )
            raise InvalidInputError(
                "Dữ liệu multipart form không hợp lệ hoặc bị cắt cụt."
            ) from e

        # Kiểm tra tính toàn vẹn và duy nhất của các trường form
        file_items: list[UploadFile] = []
        language_items: list[str] = []

        for key, val in form.multi_items():
            if key == "file":
                if not isinstance(val, UploadFile):
                    raise InvalidInputError("Trường 'file' phải là tệp tải lên.")
                file_items.append(val)
            elif key == "language":
                if isinstance(val, UploadFile):
                    raise InvalidInputError("Trường 'language' phải là chuỗi văn bản.")
                language_items.append(str(val))
            else:
                raise InvalidInputError(f"Trường không hợp lệ trong form: {key}")

        if len(file_items) != 1:
            raise InvalidInputError(
                f"Form yêu cầu chính xác 1 tệp âm thanh (nhận {len(file_items)})."
            )

        if len(language_items) > 1:
            raise InvalidInputError("Trường 'language' không được xuất hiện nhiều lần.")

        target_file = file_items[0]
        language = language_items[0] if language_items else "vi"

        # 2. Kiểm tra ngôn ngữ ASR
        if language != "vi":
            raise UnsupportedASRLanguageError(
                f"Ngôn ngữ ASR '{language}' không được hỗ trợ. Chỉ hỗ trợ tiếng Việt ('vi')."
            )

        # 3. Đọc dữ liệu tệp theo từng khối bị chặn (Bounded Chunk Reading)
        chunk_size = 65536  # 64 KiB
        file_bytes = bytearray()
        while True:
            chunk = await target_file.read(chunk_size)
            if not chunk:
                break
            file_bytes.extend(chunk)
            if len(file_bytes) > settings.MAX_AUDIO_FILE_BYTES:
                raise AudioTooLargeError(
                    "Dung lượng tệp âm thanh vượt quá giới hạn cho phép.",
                    detail={
                        "max_allowed_bytes": settings.MAX_AUDIO_FILE_BYTES,
                        "received_bytes": len(file_bytes),
                    },
                )

        raw_data = bytes(file_bytes)

        # 4. Xác thực định dạng WAV PCM signed 16-bit 16kHz mono và thời lượng
        audio_input: AudioInput = validate_wav(raw_data, settings)

        # 5. Kiểm tra Engine Readiness
        if not supervisor.is_asr_ready() or supervisor.asr_engine is None:
            raise ModelNotReadyError(
                "Mô hình hoặc engine ASR chưa sẵn sàng để phục vụ yêu cầu."
            )

        # 6. Thực thi qua InferenceRunner với Disconnect Monitoring
        engine = supervisor.asr_engine
        active_asr_id = engine.get_metadata().model_id

        def do_transcribe() -> ASRResult:
            if supervisor.is_engine_failed("asr"):
                raise ModelNotReadyError("Mô hình hoặc engine ASR chưa sẵn sàng để phục vụ yêu cầu.")
            assert supervisor.asr_engine is not None
            return supervisor.asr_engine.transcribe(audio_input, language="vi")

        try:
            runner_result = await execute_with_disconnect_monitor(
                request,
                runner,
                do_transcribe,
                task_type="asr",
                request_id=request_id,
                model_id=active_asr_id,
                execution_timeout_sec=settings.ASR_TIMEOUT_SEC,
            )
        except AppError:
            raise
        except Exception as e:
            if isinstance(e, MemoryError) or "out of memory" in str(e).lower():
                supervisor.mark_asr_failed(f"Fatal resource error: {e}")
            logger.error("Lỗi suy luận ASR: request_id=%s exc=%s", request_id, e)
            raise ASRFailureError(
                "Nhận dạng giọng nói thất bại trong quá trình xử lý."
            ) from e

        asr_res: ASRResult = runner_result.value

        # 7. Kiểm tra transcript rỗng hoặc chỉ có khoảng trắng (§4.2, §8.2)
        if not asr_res.transcript or not asr_res.transcript.strip():
            raise NoSpeechDetectedError(
                "Không phát hiện lời nói có nội dung trong tệp âm thanh."
            )

        meta = asr_res.model_metadata
        model_metadata = ASRModelMetadata(
            model_id=meta.model_id,
            model_version=meta.model_version,
            engine_type=meta.engine_type,
            is_mock=meta.is_mock,
        )

        total_ms = round((time.monotonic() - req_start) * 1000.0, 2)
        logger.info(
            "Thành công POST /api/asr/transcribe: request_id=%s model_id=%s version=%s duration_sec=%.2f total_ms=%.2f queue_ms=%.2f latency_ms=%.2f",
            request_id,
            meta.model_id,
            meta.model_version,
            audio_input.duration_sec,
            total_ms,
            runner_result.queue_ms,
            runner_result.latency_ms,
        )

        return TranscribeResponse(
            status="success",
            transcript=asr_res.transcript,
            language=asr_res.language,
            duration_sec=audio_input.duration_sec,
            model_metadata=model_metadata,
            latency_ms=runner_result.latency_ms,
            queue_ms=runner_result.queue_ms,
            disclaimer="Thử nghiệm giọng nói tiếng Việt. Ứng dụng không hỗ trợ nhận dạng tiếng Tày.",
        )
    finally:
        # Luôn đóng tất cả UploadFile và spool temp files đã mở
        for uf in all_upload_files:
            try:
                await uf.close()
            except Exception as e:
                logger.debug("Lỗi khi đóng UploadFile: %s", e)
        for spool in all_created_spools:
            try:
                spool.close()
            except Exception as e:
                logger.debug("Lỗi khi đóng spool file: %s", e)
