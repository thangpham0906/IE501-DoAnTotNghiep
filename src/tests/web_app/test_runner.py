"""Bộ kiểm thử đơn vị toàn diện cho InferenceRunner theo đặc tả §5 và §8.2."""

import asyncio
import threading
import time
from typing import Any

import pytest

from src.web_app.core.config import WebSettings
from src.web_app.core.exceptions import (
    InferenceTimeoutError,
    InvalidInputError,
    ModelNotReadyError,
    ServiceOverloadedError,
)
from src.web_app.services.inference_runner import InferenceRunner, RunnerResult


async def wait_event_async(event: threading.Event, timeout: float = 3.0) -> bool:
    """Chờ một threading.Event mà không làm block asyncio event loop."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if event.is_set():
            return True
        await asyncio.sleep(0.005)
    return event.is_set()


@pytest.fixture
def base_settings() -> WebSettings:
    """Fixture cung cấp cấu hình kiểm thử nhanh."""
    return WebSettings(
        INFERENCE_WORKERS=1,
        MAX_QUEUED_INFERENCES=2,
        QUEUE_TIMEOUT_SEC=1.0,
        TRANSLATION_TIMEOUT_SEC=2.0,
        ASR_TIMEOUT_SEC=2.0,
        SHUTDOWN_GRACE_SEC=1.0,
    )


@pytest.mark.asyncio
async def test_runner_queue_full_raises_service_overloaded(base_settings: WebSettings) -> None:
    """Kiểm tra khi N active + Q waiting đã đủ, request tiếp theo bị từ chối 503 ngay lập tức."""
    runner = InferenceRunner(base_settings)
    await runner.start()

    blocker = threading.Event()
    worker_started = threading.Event()

    def blocking_work() -> str:
        worker_started.set()
        blocker.wait(timeout=5.0)
        return "job_0_done"

    def fast_work() -> str:
        return "fast_done"

    tasks: list[asyncio.Task[Any]] = []
    try:
        # Job 1: Chiếm suất active duy nhất
        task_0 = asyncio.create_task(
            runner.run(blocking_work, task_type="translation", request_id="req-0")
        )
        tasks.append(task_0)

        # Chờ worker thực sự nhận job 0 (không block event loop)
        assert await wait_event_async(worker_started, timeout=3.0)
        assert runner.active_count == 1
        assert runner.queued_count == 0

        # Job 2 & 3: Lấp đầy hàng đợi chờ (MAX_QUEUED_INFERENCES = 2)
        task_1 = asyncio.create_task(
            runner.run(fast_work, task_type="translation", request_id="req-1")
        )
        task_2 = asyncio.create_task(
            runner.run(fast_work, task_type="translation", request_id="req-2")
        )
        tasks.extend([task_1, task_2])

        # Cho event loop lặp để admit job 1 và job 2
        await asyncio.sleep(0.01)
        assert runner.active_count == 1
        assert runner.queued_count == 2

        # Job 4: Vượt quá sức chứa N (1) + Q (2) = 3 -> Phải raise ServiceOverloadedError ngay
        with pytest.raises(ServiceOverloadedError) as exc_info:
            await runner.run(fast_work, task_type="translation", request_id="req-overload")
        assert exc_info.value.status_code == 503
        assert exc_info.value.error_code == "SERVICE_OVERLOADED"

    finally:
        blocker.set()
        await runner.shutdown()
        await asyncio.gather(*tasks, return_exceptions=True)


@pytest.mark.asyncio
async def test_runner_fifo_execution_order(base_settings: WebSettings) -> None:
    """Kiểm tra các công việc trong hàng đợi chờ được phục vụ đúng thứ tự FIFO."""
    runner = InferenceRunner(base_settings)
    await runner.start()

    blocker = threading.Event()
    worker_started = threading.Event()
    execution_order: list[int] = []

    def blocking_work() -> str:
        worker_started.set()
        blocker.wait(timeout=5.0)
        return "initial_done"

    def make_work(job_id: int):
        def work() -> int:
            execution_order.append(job_id)
            return job_id

        return work

    tasks: list[asyncio.Task[Any]] = []
    try:
        # Job 0 chiếm worker
        task_0 = asyncio.create_task(
            runner.run(blocking_work, task_type="translation", request_id="req-0")
        )
        tasks.append(task_0)
        assert await wait_event_async(worker_started, timeout=3.0)

        # Enqueue lần lượt Job 1 và Job 2
        task_1 = asyncio.create_task(
            runner.run(make_work(1), task_type="translation", request_id="req-1")
        )
        task_2 = asyncio.create_task(
            runner.run(make_work(2), task_type="translation", request_id="req-2")
        )
        tasks.extend([task_1, task_2])

        await asyncio.sleep(0.01)
        assert runner.queued_count == 2

        # Giải phóng job 0 để worker tiếp nhận tuần tự
        blocker.set()
        results = await asyncio.gather(*tasks)

        assert results[0].value == "initial_done"
        assert results[1].value == 1
        assert results[2].value == 2
        # Kiểm tra thứ tự thực thi đúng FIFO
        assert execution_order == [1, 2]

    finally:
        blocker.set()
        await runner.shutdown()


@pytest.mark.asyncio
async def test_runner_queue_expiry_never_executes_engine() -> None:
    """Kiểm tra công việc hết queue deadline sẽ bị loại bỏ và TUYỆT ĐỐI không gọi engine."""
    settings = WebSettings(
        INFERENCE_WORKERS=1,
        MAX_QUEUED_INFERENCES=2,
        QUEUE_TIMEOUT_SEC=0.05,  # Hết hạn queue cực nhanh
        TRANSLATION_TIMEOUT_SEC=2.0,
    )
    runner = InferenceRunner(settings)
    await runner.start()

    blocker = threading.Event()
    worker_started = threading.Event()
    engine_called = False

    def blocking_work() -> str:
        worker_started.set()
        blocker.wait(timeout=5.0)
        return "blocker_done"

    def expired_work() -> str:
        nonlocal engine_called
        engine_called = True
        return "should_never_run"

    tasks: list[asyncio.Task[Any]] = []
    try:
        # Job 0 chiếm worker
        task_0 = asyncio.create_task(
            runner.run(blocking_work, task_type="translation", request_id="req-0")
        )
        tasks.append(task_0)
        assert await wait_event_async(worker_started, timeout=3.0)

        # Job 1 vào hàng đợi với queue_timeout = 0.05s
        with pytest.raises(InferenceTimeoutError) as exc_info:
            await runner.run(expired_work, task_type="translation", request_id="req-expired")

        assert exc_info.value.status_code == 504
        assert exc_info.value.error_code == "INFERENCE_TIMEOUT"
        assert exc_info.value.detail == {"phase": "queue"}

        # Hàng đợi phải trở về 0 vì job đã bị loại
        assert runner.queued_count == 0

        # Thả worker để job 0 kết thúc
        blocker.set()
        await task_0

        # Xác nhận engine của job 1 không bao giờ được gọi
        assert engine_called is False

    finally:
        blocker.set()
        await runner.shutdown()


@pytest.mark.asyncio
async def test_runner_cancel_queued_job_removes_from_queue(base_settings: WebSettings) -> None:
    """Kiểm tra khi client hủy request lúc đang ở hàng đợi, job bị loại ngay và không gọi engine."""
    runner = InferenceRunner(base_settings)
    await runner.start()

    blocker = threading.Event()
    worker_started = threading.Event()
    engine_called = False

    def blocking_work() -> str:
        worker_started.set()
        blocker.wait(timeout=5.0)
        return "blocker_done"

    def queued_work() -> str:
        nonlocal engine_called
        engine_called = True
        return "should_not_run"

    try:
        task_0 = asyncio.create_task(
            runner.run(blocking_work, task_type="translation", request_id="req-0")
        )
        assert await wait_event_async(worker_started, timeout=3.0)

        task_1 = asyncio.create_task(
            runner.run(queued_work, task_type="translation", request_id="req-cancel-queued")
        )
        await asyncio.sleep(0.01)
        assert runner.queued_count == 1

        # Hủy task 1 khi đang chờ trong queue
        task_1.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task_1

        # Job phải bị loại khỏi queue ngay lập tức
        assert runner.queued_count == 0

        # Thả worker
        blocker.set()
        await task_0

        # Engine không được gọi
        assert engine_called is False

    finally:
        blocker.set()
        await runner.shutdown()


@pytest.mark.asyncio
async def test_runner_cancel_running_job_holds_worker_slot(base_settings: WebSettings) -> None:
    """Kiểm tra khi client hủy request lúc ĐANG CHẠY, worker slot vẫn bị giữ đến khi thread thực sự finish."""
    runner = InferenceRunner(base_settings)
    await runner.start()

    worker_started = threading.Event()
    release_work = threading.Event()
    work_finished = threading.Event()

    def long_work() -> str:
        worker_started.set()
        release_work.wait(timeout=5.0)
        work_finished.set()
        return "done_eventually"

    tasks: list[asyncio.Task[Any]] = []
    try:
        task = asyncio.create_task(
            runner.run(long_work, task_type="translation", request_id="req-cancel-running")
        )

        assert await wait_event_async(worker_started, timeout=3.0)
        assert runner.active_count == 1

        # Client hủy request khi job đang chạy
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        # QUAN TRỌNG: Client đã hủy nhưng worker thread vẫn đang chạy, slot PHẢI còn giữ!
        assert runner.active_count == 1
        assert work_finished.is_set() is False

        # Thử lấp đầy hàng đợi: sức chứa vẫn tính cả slot đang chạy này!
        task_q1 = asyncio.create_task(
            runner.run(lambda: "q1", task_type="translation", request_id="req-q1")
        )
        task_q2 = asyncio.create_task(
            runner.run(lambda: "q2", task_type="translation", request_id="req-q2")
        )
        tasks.extend([task_q1, task_q2])
        await asyncio.sleep(0.01)
        assert runner.queued_count == 2

        with pytest.raises(ServiceOverloadedError):
            await runner.run(lambda: "q3", task_type="translation", request_id="req-q3")

        # Bây giờ mới thả cho thread thực sự kết thúc
        release_work.set()
        assert await wait_event_async(work_finished, timeout=3.0)

        # Chờ các job q1, q2 hoàn tất
        res_q1 = await task_q1
        res_q2 = await task_q2
        assert res_q1.value == "q1"
        assert res_q2.value == "q2"
        assert runner.active_count == 0
        assert runner.queued_count == 0

    finally:
        release_work.set()
        await runner.shutdown()
        await asyncio.gather(*tasks, return_exceptions=True)


@pytest.mark.asyncio
async def test_runner_execution_timeout_holds_worker_slot(base_settings: WebSettings) -> None:
    """Kiểm tra khi quá thời hạn thực thi (Execution Timeout), slot vẫn được giữ đến khi thread xong."""
    runner = InferenceRunner(base_settings)
    await runner.start()

    worker_started = threading.Event()
    release_work = threading.Event()
    work_finished = threading.Event()

    def slow_work() -> str:
        worker_started.set()
        release_work.wait(timeout=5.0)
        work_finished.set()
        return "slow_done"

    try:
        # Chạy với execution_timeout_sec cực ngắn (0.05s)
        with pytest.raises(InferenceTimeoutError) as exc_info:
            await runner.run(
                slow_work,
                task_type="translation",
                request_id="req-exec-timeout",
                execution_timeout_sec=0.05,
            )

        assert exc_info.value.status_code == 504
        assert exc_info.value.detail == {"phase": "execution"}

        # QUAN TRỌNG: Client nhận 504 nhưng worker thread vẫn đang chạy, active_count vẫn là 1!
        assert runner.active_count == 1
        assert work_finished.is_set() is False

        # Thả cho worker kết thúc
        release_work.set()
        assert await wait_event_async(work_finished, timeout=3.0)

        # Cho event loop dọn dẹp và thu hồi late completion
        for _ in range(50):
            if runner.active_count == 0:
                break
            await asyncio.sleep(0.01)

        assert runner.active_count == 0

    finally:
        release_work.set()
        await runner.shutdown()


@pytest.mark.asyncio
async def test_runner_mixed_task_types_and_results(base_settings: WebSettings) -> None:
    """Kiểm tra chạy đồng thời hai loại tác vụ translation và ASR trên cùng một runner."""
    settings = WebSettings(
        INFERENCE_WORKERS=2,  # 2 workers để chạy đồng thời
        MAX_QUEUED_INFERENCES=4,
        TRANSLATION_TIMEOUT_SEC=2.0,
        ASR_TIMEOUT_SEC=3.0,
    )
    runner = InferenceRunner(settings)
    await runner.start()

    def translation_fn() -> dict[str, str]:
        time.sleep(0.02)
        return {"translated": "test"}

    def asr_fn() -> dict[str, str]:
        time.sleep(0.02)
        return {"transcript": "audio test"}

    try:
        res_trans, res_asr = await asyncio.gather(
            runner.run(
                translation_fn,
                task_type="translation",
                request_id="req-trans",
                model_id="mock-demo",
            ),
            runner.run(
                asr_fn,
                task_type="asr",
                request_id="req-asr",
                model_id="mock-asr",
            ),
        )

        assert isinstance(res_trans, RunnerResult)
        assert res_trans.value == {"translated": "test"}
        assert res_trans.queue_ms >= 0.0
        assert res_trans.latency_ms >= 10.0  # do sleep 0.02s

        assert isinstance(res_asr, RunnerResult)
        assert res_asr.value == {"transcript": "audio test"}
        assert res_asr.queue_ms >= 0.0
        assert res_asr.latency_ms >= 10.0

    finally:
        await runner.shutdown()


@pytest.mark.asyncio
async def test_runner_late_exception_consumed_safely(base_settings: WebSettings) -> None:
    """Kiểm tra ngoại lệ phát sinh muộn sau khi request đã timeout được thu hồi an toàn, không crash loop."""
    runner = InferenceRunner(base_settings)
    await runner.start()

    worker_started = threading.Event()
    release_work = threading.Event()

    def buggy_work() -> None:
        worker_started.set()
        release_work.wait(timeout=5.0)
        raise RuntimeError("Late critical crash inside worker")

    try:
        # Request timeout trước
        with pytest.raises(InferenceTimeoutError) as exc_info:
            await runner.run(
                buggy_work,
                task_type="translation",
                request_id="req-late-exc",
                execution_timeout_sec=0.05,
            )
        assert exc_info.value.detail == {"phase": "execution"}

        # Thread ném ngoại lệ muộn
        release_work.set()

        # Đợi thread kết thúc và runner thu hồi ngoại lệ
        for _ in range(50):
            if runner.active_count == 0:
                break
            await asyncio.sleep(0.01)

        assert runner.active_count == 0

        # Kiểm tra runner vẫn hoạt động bình thường cho job tiếp theo
        next_res = await runner.run(
            lambda: "healed",
            task_type="translation",
            request_id="req-next",
        )
        assert next_res.value == "healed"

    finally:
        release_work.set()
        await runner.shutdown()


@pytest.mark.asyncio
async def test_runner_shutdown_clean(base_settings: WebSettings) -> None:
    """Kiểm tra shutdown sạch sẽ khi không có công việc nào bị kẹt."""
    runner = InferenceRunner(base_settings)
    await runner.start()

    res = await runner.run(lambda: "ok", task_type="translation", request_id="req-ok")
    assert res.value == "ok"

    # Gọi shutdown
    shutdown_ok = await runner.shutdown(grace_sec=0.5)
    assert shutdown_ok is True
    assert runner.is_stopping is True
    assert runner.active_count == 0
    assert runner.queued_count == 0

    # Lặp lại shutdown vẫn trả True an toàn
    assert await runner.shutdown() is True

    # Gọi run sau khi shutdown phải nhận ModelNotReadyError (503)
    with pytest.raises(ModelNotReadyError) as exc_info:
        await runner.run(lambda: "never", task_type="translation", request_id="req-after-stop")
    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_runner_shutdown_grace_exhaustion(base_settings: WebSettings) -> None:
    """Kiểm tra khi hết grace period mà worker vẫn chạy: shutdown trả False, giữ nguyên slot và không giả vờ dừng."""
    runner = InferenceRunner(base_settings)
    await runner.start()

    worker_started = threading.Event()
    release_work = threading.Event()

    def stuck_work() -> str:
        worker_started.set()
        release_work.wait(timeout=5.0)
        return "stuck_done"

    tasks: list[asyncio.Task[Any]] = []
    try:
        task = asyncio.create_task(
            runner.run(stuck_work, task_type="translation", request_id="req-stuck")
        )
        tasks.append(task)
        assert await wait_event_async(worker_started, timeout=3.0)
        assert runner.active_count == 1

        # Đồng thời đưa 1 job vào hàng đợi
        queued_task = asyncio.create_task(
            runner.run(lambda: "discarded", task_type="translation", request_id="req-q")
        )
        tasks.append(queued_task)
        await asyncio.sleep(0.01)
        assert runner.queued_count == 1

        # Gọi shutdown với grace cực ngắn (0.05s)
        shutdown_ok = await runner.shutdown(grace_sec=0.05)

        # Hết grace: shutdown trả False!
        assert shutdown_ok is False
        # Slot active PHẢI giữ nguyên!
        assert runner.active_count == 1
        # Job đang chờ trong queue bị hủy với ModelNotReadyError
        with pytest.raises(ModelNotReadyError):
            await queued_task

        # Giờ mới thả cho worker hoàn tất
        release_work.set()
        res = await task
        assert res.value == "stuck_done"

        # Đợi thread giải phóng
        for _ in range(50):
            if runner.active_count == 0:
                break
            await asyncio.sleep(0.01)

        # Gọi shutdown lại lần nữa: bây giờ phải thành công trả True
        shutdown_ok_2 = await runner.shutdown(grace_sec=0.05)
        assert shutdown_ok_2 is True

    finally:
        release_work.set()
        await runner.shutdown()
        await asyncio.gather(*tasks, return_exceptions=True)


@pytest.mark.asyncio
async def test_runner_max_active_threads_never_exceeds_config() -> None:
    """Kiểm chứng số lượng worker thread thực tế chạy đồng thời không bao giờ vượt quá cấu hình."""
    max_workers = 2
    settings = WebSettings(
        INFERENCE_WORKERS=max_workers,
        MAX_QUEUED_INFERENCES=6,
        TRANSLATION_TIMEOUT_SEC=3.0,
    )
    runner = InferenceRunner(settings)
    await runner.start()

    barrier = threading.Barrier(max_workers)
    active_thread_ids: set[int] = set()
    lock = threading.Lock()
    max_observed_simultaneous = 0

    def concurrent_work() -> int:
        tid = threading.get_ident()
        with lock:
            active_thread_ids.add(tid)
            nonlocal max_observed_simultaneous
            if len(active_thread_ids) > max_observed_simultaneous:
                max_observed_simultaneous = len(active_thread_ids)

        # Đợi đủ 2 worker cùng chạm barrier để kiểm tra peak concurrency
        barrier.wait(timeout=2.0)
        time.sleep(0.02)

        with lock:
            active_thread_ids.remove(tid)
        return tid

    tasks: list[asyncio.Task[Any]] = []
    try:
        # Bắn 4 request đồng thời
        for i in range(4):
            t = asyncio.create_task(
                runner.run(concurrent_work, task_type="translation", request_id=f"req-thread-{i}")
            )
            tasks.append(t)

        results = await asyncio.gather(*tasks)
        assert len(results) == 4

        # Số thread đồng thời đo được tối đa phải đúng bằng INFERENCE_WORKERS (2)
        assert max_observed_simultaneous == max_workers
        assert max_observed_simultaneous <= max_workers

    finally:
        await runner.shutdown()


@pytest.mark.asyncio
async def test_runner_propagates_app_error(base_settings: WebSettings) -> None:
    """Kiểm tra các lỗi nghiệp vụ thuộc AppError được giữ nguyên khi raise từ sync callback."""
    runner = InferenceRunner(base_settings)
    await runner.start()

    def bad_work() -> None:
        raise InvalidInputError("Dữ liệu đầu vào sai cấu trúc.")

    try:
        with pytest.raises(InvalidInputError) as exc_info:
            await runner.run(bad_work, task_type="translation", request_id="req-err")
        assert exc_info.value.status_code == 400
        assert exc_info.value.error_code == "INVALID_INPUT"
        assert exc_info.value.message == "Dữ liệu đầu vào sai cấu trúc."

    finally:
        await runner.shutdown()


@pytest.mark.asyncio
async def test_runner_propagates_unexpected_exception(base_settings: WebSettings) -> None:
    """Kiểm tra ngoại lệ bất ngờ được chuyển tiếp nguyên vẹn để tầng API xử lý."""
    runner = InferenceRunner(base_settings)
    await runner.start()

    def unexpected_fail() -> None:
        raise ValueError("Lỗi toán học bất thường")

    try:
        with pytest.raises(ValueError) as exc_info:
            await runner.run(unexpected_fail, task_type="translation", request_id="req-unexp")
        assert str(exc_info.value) == "Lỗi toán học bất thường"

    finally:
        await runner.shutdown()
