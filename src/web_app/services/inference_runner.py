"""Inference Runner quản lý hàng đợi hữu hạn, worker threads và vòng đời suy luận."""

import asyncio
import logging
import threading
import time
import uuid
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from src.web_app.core.config import WebSettings
from src.web_app.core.exceptions import (
    InferenceTimeoutError,
    ModelNotReadyError,
    ServiceOverloadedError,
)

logger = logging.getLogger("web_app.inference_runner")

T = TypeVar("T")


@dataclass(frozen=True)
class RunnerResult(Generic[T]):
    """Kết quả trả về từ InferenceRunner sau khi thực thi suy luận thành công."""

    value: T
    queue_ms: float
    latency_ms: float


@dataclass(eq=False)
class _InferenceJob(Generic[T]):
    """Thông tin và trạng thái nội bộ của một tác vụ suy luận."""

    job_id: str
    request_id: str
    task_type: str
    model_id: str | None
    func: Callable[[], T]
    admit_time: float
    queue_deadline: float
    exec_timeout_sec: float

    # Trạng thái vòng đời
    status: str = "queued"  # "queued", "running", "finished", "discarded"
    caller_timed_out: bool = False
    caller_cancelled: bool = False
    discard_reason: str | None = None

    # Đo thời gian
    start_time: float = 0.0
    finish_time: float = 0.0
    queue_ms: float = 0.0
    latency_ms: float = 0.0

    # Thread ID đang thực thi
    worker_thread_id: int | None = None

    # Kết quả và ngoại lệ
    result: T | None = None
    exception: BaseException | None = None

    # Futures để đồng bộ với event loop
    started_future: asyncio.Future[bool] | None = None
    done_future: asyncio.Future[RunnerResult[T]] | None = None


class InferenceRunner:
    """Quản lý N worker thread dài hạn và hàng đợi hữu hạn phục vụ suy luận dịch/ASR."""

    def __init__(
        self,
        settings: WebSettings,
        on_fatal_error: Callable[[str, BaseException], None] | None = None,
        is_engine_failed: Callable[[str], bool] | None = None,
    ) -> None:
        self._settings = settings
        self._max_workers = settings.INFERENCE_WORKERS
        self._max_queued = settings.MAX_QUEUED_INFERENCES
        self._on_fatal_error = on_fatal_error
        self._is_engine_failed = is_engine_failed

        self._lock = threading.Lock()
        self._work_condition = threading.Condition(self._lock)

        self._queued_jobs: deque[_InferenceJob[Any]] = deque()
        self._active_jobs: set[_InferenceJob[Any]] = set()
        self._all_jobs: set[_InferenceJob[Any]] = set()

        self._workers: list[threading.Thread] = []
        self._started = False
        self._is_stopping = False
        self._shutdown_event = threading.Event()

        self._loop: asyncio.AbstractEventLoop | None = None
        self._idle_event: asyncio.Event | None = None

    @property
    def is_stopping(self) -> bool:
        """Báo hiệu runner đang trong tiến trình dừng."""
        return self._is_stopping

    @property
    def active_count(self) -> int:
        """Số lượng worker thread hiện đang thực sự thực thi tác vụ suy luận."""
        with self._lock:
            return len(self._active_jobs)

    @property
    def queued_count(self) -> int:
        """Số lượng tác vụ hiện đang chờ trong hàng đợi phân phối."""
        with self._lock:
            return len(self._queued_jobs)

    async def start(self) -> None:
        """Khởi động N worker thread dài hạn phục vụ hàng đợi suy luận."""
        if self._started:
            with self._lock:
                any_alive = any(w.is_alive() for w in self._workers)
                if self._is_stopping or any_alive or self._active_jobs:
                    raise RuntimeError(
                        "Không thể tái khởi động InferenceRunner khi runner đang dừng hoặc các worker threads trước đó chưa kết thúc hoàn toàn (§5.2)."
                    )
                return

        self._loop = asyncio.get_running_loop()
        if self._idle_event is None:
            self._idle_event = asyncio.Event()
            self._idle_event.set()

        with self._lock:
            self._is_stopping = False
            self._shutdown_event.clear()
            self._workers.clear()
            for i in range(self._max_workers):
                worker = threading.Thread(
                    target=self._worker_loop,
                    name=f"InferenceWorker-{i+1}",
                    daemon=True,
                )
                self._workers.append(worker)
                worker.start()
            self._started = True

        logger.info(
            "InferenceRunner đã khởi động: %d workers, tối đa %d queued jobs.",
            self._max_workers,
            self._max_queued,
        )

    def _worker_loop(self) -> None:
        """Vòng lặp chạy nền trong worker thread: bốc job theo FIFO và thực thi."""
        current_thread_id = threading.get_ident()
        while True:
            job: _InferenceJob[Any] | None = None
            with self._work_condition:
                while (
                    not self._queued_jobs
                    and not self._shutdown_event.is_set()
                    and not self._is_stopping
                ):
                    self._work_condition.wait()

                if (self._shutdown_event.is_set() or self._is_stopping) and not self._queued_jobs:
                    break

                if not self._queued_jobs:
                    continue

                candidate = self._queued_jobs.popleft()
                now = time.monotonic()

                # C07: Kiểm tra monotonic deadline và trạng thái hủy trước khi worker nhận việc
                if candidate.status != "queued" or now >= candidate.queue_deadline:
                    if candidate.status == "queued" and now >= candidate.queue_deadline:
                        candidate.status = "discarded"
                        candidate.discard_reason = "queue_timeout"
                        self._all_jobs.discard(candidate)
                        if (
                            self._loop
                            and candidate.started_future
                            and not candidate.started_future.done()
                        ):
                            self._loop.call_soon_threadsafe(
                                self._safe_set_future_exception,
                                candidate.started_future,
                                InferenceTimeoutError(
                                    phase="queue",
                                    message=f"Quá thời hạn chờ trong hàng đợi ({self._settings.QUEUE_TIMEOUT_SEC}s).",
                                ),
                            )
                    continue

                # C11: Kiểm tra xem engine đã bị đánh dấu failed chưa
                if self._is_engine_failed and self._is_engine_failed(candidate.task_type):
                    candidate.status = "discarded"
                    candidate.discard_reason = "engine_failed"
                    self._all_jobs.discard(candidate)
                    if (
                        self._loop
                        and candidate.started_future
                        and not candidate.started_future.done()
                    ):
                        self._loop.call_soon_threadsafe(
                            self._safe_set_future_exception,
                            candidate.started_future,
                            ModelNotReadyError("Mô hình hoặc engine chưa sẵn sàng để phục vụ yêu cầu."),
                        )
                    continue

                candidate.status = "running"
                candidate.worker_thread_id = current_thread_id
                candidate.start_time = now
                candidate.queue_ms = round(
                    (candidate.start_time - candidate.admit_time) * 1000.0, 2
                )
                self._active_jobs.add(candidate)

                if self._loop and self._idle_event:
                    self._loop.call_soon_threadsafe(self._idle_event.clear)

                job = candidate

            if job is None:
                continue

            # Báo cho event loop biết job đã được nhận vào worker slot
            if self._loop and job.started_future:
                self._loop.call_soon_threadsafe(
                    self._safe_set_future_result,
                    job.started_future,
                    True,
                )

            logger.info(
                "Bắt đầu thực thi job: job_id=%s request_id=%s task_type=%s model_id=%s queue_ms=%.2f worker_tid=%d",
                job.job_id,
                job.request_id,
                job.task_type,
                job.model_id,
                job.queue_ms,
                current_thread_id,
            )

            # Thực thi tác vụ blocking
            val = None
            exc = None
            try:
                val = job.func()
            except BaseException as e:
                exc = e

            finish_time = time.monotonic()
            job.finish_time = finish_time
            job.latency_ms = round((finish_time - job.start_time) * 1000.0, 2)
            job.result = val
            job.exception = exc

            # C11: Bất kể job là on-time hay late, nếu gặp fatal resource error thì kích hoạt on_fatal_error
            if exc is not None:
                if isinstance(exc, MemoryError) or "out of memory" in str(exc).lower():
                    logger.error(
                        "Phát hiện lỗi tài nguyên nghiêm trọng trong worker: job_id=%s task_type=%s exc=%s",
                        job.job_id,
                        job.task_type,
                        exc,
                    )
                    if self._on_fatal_error is not None:
                        try:
                            self._on_fatal_error(job.task_type, exc)
                        except Exception as cb_err:
                            logger.error("Lỗi khi gọi on_fatal_error callback: %s", cb_err)

            with self._lock:
                job.status = "finished"
                self._active_jobs.discard(job)
                if len(self._active_jobs) == 0 and self._loop and self._idle_event:
                    self._loop.call_soon_threadsafe(self._idle_event.set)

                is_late = job.caller_timed_out or job.caller_cancelled
                self._all_jobs.discard(job)

            if is_late:
                logger.warning(
                    "Hoàn tất muộn (late completion): job_id=%s request_id=%s task_type=%s model_id=%s queue_ms=%.2f latency_ms=%.2f status=%s timed_out=%s cancelled=%s",
                    job.job_id,
                    job.request_id,
                    job.task_type,
                    job.model_id,
                    job.queue_ms,
                    job.latency_ms,
                    "error" if job.exception else "success",
                    job.caller_timed_out,
                    job.caller_cancelled,
                )
                if job.exception is not None:
                    logger.warning(
                        "Thu hồi ngoại lệ muộn (late exception): job_id=%s request_id=%s err_type=%s err=%s",
                        job.job_id,
                        job.request_id,
                        type(job.exception).__name__,
                        str(job.exception),
                    )
            else:
                logger.info(
                    "Hoàn tất job: job_id=%s request_id=%s task_type=%s model_id=%s queue_ms=%.2f latency_ms=%.2f status=%s",
                    job.job_id,
                    job.request_id,
                    job.task_type,
                    job.model_id,
                    job.queue_ms,
                    job.latency_ms,
                    "error" if job.exception else "success",
                )
                if self._loop and job.done_future:
                    if job.exception is not None:
                        self._loop.call_soon_threadsafe(
                            self._safe_set_future_exception,
                            job.done_future,
                            job.exception,
                        )
                    else:
                        runner_result = RunnerResult(
                            value=job.result,
                            queue_ms=job.queue_ms,
                            latency_ms=job.latency_ms,
                        )
                        self._loop.call_soon_threadsafe(
                            self._safe_set_future_result,
                            job.done_future,
                            runner_result,
                        )

            # Nếu runner đang dừng và không còn job nào trong queue, worker tự thoát vòng lặp
            with self._lock:
                if (self._is_stopping or self._shutdown_event.is_set()) and not self._queued_jobs:
                    break

    async def run(
        self,
        func: Callable[[], T],
        *,
        task_type: str,
        request_id: str,
        model_id: str | None = None,
        execution_timeout_sec: float | None = None,
    ) -> RunnerResult[T]:
        """Tiếp nhận và thực thi một tác vụ suy luận đồng bộ qua hàng đợi runner."""
        if not self._started:
            await self.start()

        if self._is_stopping:
            raise ModelNotReadyError("Dịch vụ đang dừng hoặc engine chưa sẵn sàng phục vụ.")

        if self._is_engine_failed and self._is_engine_failed(task_type):
            raise ModelNotReadyError("Mô hình hoặc engine chưa sẵn sàng để phục vụ yêu cầu.")

        loop = asyncio.get_running_loop()
        admit_time = time.monotonic()
        queue_timeout = self._settings.QUEUE_TIMEOUT_SEC
        queue_deadline = admit_time + queue_timeout

        if execution_timeout_sec is None:
            if task_type == "asr":
                exec_timeout = self._settings.ASR_TIMEOUT_SEC
            else:
                exec_timeout = self._settings.TRANSLATION_TIMEOUT_SEC
        else:
            exec_timeout = float(execution_timeout_sec)

        job_id = uuid.uuid4().hex[:8]
        job: _InferenceJob[T] = _InferenceJob(
            job_id=job_id,
            request_id=request_id,
            task_type=task_type,
            model_id=model_id,
            func=func,
            admit_time=admit_time,
            queue_deadline=queue_deadline,
            exec_timeout_sec=exec_timeout,
            started_future=loop.create_future(),
            done_future=loop.create_future(),
        )

        with self._lock:
            if self._is_stopping:
                raise ModelNotReadyError("Dịch vụ đang dừng hoặc engine chưa sẵn sàng phục vụ.")

            if len(self._active_jobs) + len(self._queued_jobs) >= self._max_workers + self._max_queued:
                logger.warning(
                    "Từ chối yêu cầu do quá tải: request_id=%s active=%d queued=%d max_workers=%d max_queued=%d",
                    request_id,
                    len(self._active_jobs),
                    len(self._queued_jobs),
                    self._max_workers,
                    self._max_queued,
                )
                raise ServiceOverloadedError("Hệ thống đang bận. Hàng đợi suy luận đã đầy.")

            self._queued_jobs.append(job)
            self._all_jobs.add(job)
            self._work_condition.notify()

        logger.info(
            "Đã tiếp nhận job: job_id=%s request_id=%s task_type=%s model_id=%s",
            job.job_id,
            job.request_id,
            job.task_type,
            job.model_id,
        )

        # Giai đoạn 1: Chờ worker nhận việc với queue deadline
        now = time.monotonic()
        time_left_queue = max(0.0, job.queue_deadline - now)
        try:
            assert job.started_future is not None
            await asyncio.wait_for(asyncio.shield(job.started_future), timeout=time_left_queue)
        except (TimeoutError, asyncio.CancelledError) as wait_err:
            with self._lock:
                if job.status == "queued":
                    job.status = "discarded"
                    if isinstance(wait_err, TimeoutError):
                        job.discard_reason = "queue_timeout"
                        if job in self._queued_jobs:
                            self._queued_jobs.remove(job)
                        self._all_jobs.discard(job)
                        logger.warning(
                            "Quá thời hạn chờ hàng đợi: job_id=%s request_id=%s queue_timeout=%.2fs",
                            job.job_id,
                            job.request_id,
                            queue_timeout,
                        )
                        raise InferenceTimeoutError(
                            phase="queue",
                            message=f"Quá thời hạn chờ trong hàng đợi ({queue_timeout}s).",
                        )
                    else:
                        job.caller_cancelled = True
                        job.discard_reason = "client_cancelled_queued"
                        if job in self._queued_jobs:
                            self._queued_jobs.remove(job)
                        self._all_jobs.discard(job)
                        logger.info(
                            "Yêu cầu bị hủy khi đang chờ trong hàng đợi: job_id=%s request_id=%s",
                            job.job_id,
                            job.request_id,
                        )
                        raise
                elif job.status == "discarded":
                    self._all_jobs.discard(job)
                    if job.discard_reason == "queue_timeout":
                        raise InferenceTimeoutError(
                            phase="queue",
                            message=f"Quá thời hạn chờ trong hàng đợi ({queue_timeout}s).",
                        )
                    raise ModelNotReadyError("Dịch vụ đang dừng hoặc engine chưa sẵn sàng phục vụ.")
                else:
                    if isinstance(wait_err, asyncio.CancelledError):
                        job.caller_cancelled = True
                        raise

        # Giai đoạn 2: Chờ thực thi suy luận với execution deadline
        now = time.monotonic()
        exec_deadline = job.start_time + job.exec_timeout_sec
        time_left_exec = max(0.0, exec_deadline - now)
        try:
            assert job.done_future is not None
            return await asyncio.wait_for(asyncio.shield(job.done_future), timeout=time_left_exec)
        except TimeoutError:
            with self._lock:
                job.caller_timed_out = True
            logger.warning(
                "Quá thời hạn thực thi suy luận: job_id=%s request_id=%s exec_timeout=%.2fs. Worker tiếp tục chạy và giữ slot.",
                job.job_id,
                job.request_id,
                job.exec_timeout_sec,
            )
            raise InferenceTimeoutError(
                phase="execution",
                message=f"Quá thời hạn xử lý suy luận ({job.exec_timeout_sec}s).",
            )
        except asyncio.CancelledError:
            with self._lock:
                job.caller_cancelled = True
            logger.info(
                "Client hủy kết nối khi đang suy luận: job_id=%s request_id=%s. Worker tiếp tục chạy và giữ slot đến khi kết thúc.",
                job.job_id,
                job.request_id,
            )
            raise

    async def shutdown(self, grace_sec: float | None = None) -> bool:
        """Dừng tiếp nhận, hủy các job đang chờ và đợi worker hoàn tất trong thời gian grace."""
        if not self._started:
            return True

        if grace_sec is None:
            grace_sec = self._settings.SHUTDOWN_GRACE_SEC

        with self._lock:
            self._is_stopping = True
            while self._queued_jobs:
                q_job = self._queued_jobs.popleft()
                q_job.status = "discarded"
                q_job.discard_reason = "shutdown"
                self._all_jobs.discard(q_job)
                if q_job.started_future and not q_job.started_future.done():
                    assert self._loop is not None
                    self._loop.call_soon_threadsafe(
                        self._safe_set_future_exception,
                        q_job.started_future,
                        ModelNotReadyError("Dịch vụ đang dừng hoặc engine chưa sẵn sàng phục vụ."),
                    )

            # Thức dậy tất cả worker thread đang chờ
            self._work_condition.notify_all()

            active_remaining = len(self._active_jobs)
            if active_remaining == 0:
                self._shutdown_event.set()
                self._work_condition.notify_all()
                logger.info("Shutdown hoàn tất: 0 worker đang chạy.")
                return True

        logger.info(
            "Bắt đầu chờ grace period shutdown: %d workers đang chạy, grace=%.2fs.",
            active_remaining,
            grace_sec,
        )

        assert self._idle_event is not None
        try:
            await asyncio.wait_for(self._idle_event.wait(), timeout=grace_sec)
            with self._lock:
                self._shutdown_event.set()
                self._work_condition.notify_all()
            logger.info("Shutdown thành công: tất cả workers đã hoàn tất trong thời gian grace.")
            return True
        except TimeoutError:
            with self._lock:
                still_active = len(self._active_jobs)
            logger.warning(
                "Hết thời gian grace shutdown (%.2fs) nhưng vẫn còn %d worker đang chạy. Giữ nguyên slot và reference.",
                grace_sec,
                still_active,
            )
            return False

    @staticmethod
    def _safe_set_future_result(fut: asyncio.Future[Any], val: Any) -> None:
        """Đặt kết quả cho Future an toàn trên event loop."""
        if not fut.done():
            fut.set_result(val)

    @staticmethod
    def _safe_set_future_exception(fut: asyncio.Future[Any], exc: BaseException) -> None:
        """Đặt ngoại lệ cho Future an toàn trên event loop."""
        if not fut.done():
            fut.set_exception(exc)
