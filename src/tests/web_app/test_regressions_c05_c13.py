"""Kiểm thử hồi quy xác thực các điểm sửa lỗi C05–C14 theo review của Coordinator."""

import asyncio
import dataclasses
import io
import json
import threading
import time
from typing import Any
import pytest
from starlette import formparsers
from starlette.formparsers import SpooledTemporaryFile as OrigSpooledTemporaryFile
from fastapi.testclient import TestClient
import httpx

from src.tests.web_app.audio_fixtures import build_wav_bytes
from src.tests.web_app.conftest import (
    FakeASREngine,
    FakeTranslationEngine,
    wait_client_loaded,
)
from src.web_app.core.config import WebSettings
from src.web_app.core.exceptions import InferenceTimeoutError
from src.web_app.main import create_app
from src.web_app.services.asr.base import ASRMetadata
from src.web_app.services.inference_runner import InferenceRunner
from src.web_app.services.translation.base import (
    BundleModelInfo,
    TranslationMetadata,
)


# ==============================================================================
# C05: Middleware chặn body thực nhận, không gửi hai response
# ==============================================================================


@pytest.mark.asyncio
async def test_c05_middleware_blocks_oversized_chunked_body_single_response() -> None:
    """C05: Khi body chunked vượt giới hạn, ngắt ngay lập tức và chỉ trả 1 response 413, không chạy engine."""
    settings = WebSettings(MAX_JSON_BODY_BYTES=70)
    engine_called = False

    class TrackingEngine(FakeTranslationEngine):
        def translate(self, text: str, direction: str):
            nonlocal engine_called
            engine_called = True
            return super().translate(text, direction)

    app = create_app(settings=settings, translation_engine=TrackingEngine())
    response_starts: list[int] = []

    body_payload = json.dumps({"text": "a" * 60, "direction": "vi-tay"}).encode("utf-8")
    assert len(body_payload) == 95  # > 70 bytes

    chunks = [body_payload[i : i + 31] for i in range(0, len(body_payload), 31)]
    chunk_idx = 0

    async def receive():
        nonlocal chunk_idx
        if chunk_idx < len(chunks):
            c = chunks[chunk_idx]
            chunk_idx += 1
            return {"type": "http.request", "body": c, "more_body": chunk_idx < len(chunks)}
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(msg):
        if msg["type"] == "http.response.start":
            response_starts.append(msg["status"])

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/translate",
        "query_string": b"",
        "headers": [(b"content-type", b"application/json")],
    }

    async with app.router.lifespan_context(app):
        await app.state.supervisor.wait_loaded()
        await app(scope, receive, send)

    # Đảm bảo CHÍNH XÁC một response 413, không có [200, 413]
    assert response_starts == [413]
    assert engine_called is False


# ==============================================================================
# C06: Không unload engine khi thread nạp còn chạy
# ==============================================================================


@pytest.mark.asyncio
async def test_c06_shutdown_while_translation_loader_running_does_not_unload() -> None:
    """C06: Khi shutdown diễn ra trong lúc loader thread đang chạy, không gọi unload() nếu hết grace; shutdown lặp lại an toàn."""
    load_entered = threading.Event()
    load_release = threading.Event()
    load_ended = threading.Event()
    unload_called = False
    unload_count = 0

    class SlowLoadTranslationEngine(FakeTranslationEngine):
        def load(self, bundle_path=None):
            load_entered.set()
            load_release.wait(timeout=3.0)
            try:
                super().load(bundle_path)
            finally:
                load_ended.set()

        def unload(self):
            nonlocal unload_called, unload_count
            unload_called = True
            unload_count += 1
            super().unload()

    settings = WebSettings(SHUTDOWN_GRACE_SEC=0.02)
    engine = SlowLoadTranslationEngine()
    app = create_app(settings=settings, translation_engine=engine, asr_engine=None)

    try:
        async with app.router.lifespan_context(app):
            # Chờ loader thực sự bước vào load()
            await asyncio.to_thread(load_entered.wait, 2.0)
            assert app.state.supervisor.is_loader_running() is True

        # Sau lifespan exit: thread load vẫn đang chạy, unload KHÔNG được gọi
        assert load_ended.is_set() is False
        assert unload_called is False
        assert app.state.supervisor.is_loader_running() is True
        assert app.state.supervisor.translation_state == "stopping"

        # Gọi lại shutdown lần nữa trước khi release: unload vẫn không được gọi
        await app.state.supervisor.shutdown(runner_clean=True, grace_sec=0.02)
        assert unload_called is False
        assert unload_count == 0

        # Release thread load
        load_release.set()
        await asyncio.to_thread(load_ended.wait, 2.0)
        assert load_ended.is_set() is True

        # Gọi shutdown sau khi loader đã xong: unload được gọi sạch sẽ đúng 1 lần
        await app.state.supervisor.shutdown(runner_clean=True, grace_sec=0.5)
        assert unload_called is True
        assert unload_count == 1
    finally:
        load_release.set()


@pytest.mark.asyncio
async def test_c06_shutdown_while_asr_loader_running_does_not_unload() -> None:
    """C06: Kiểm tra tương tự với luồng nạp của ASR Engine."""
    asr_entered = threading.Event()
    asr_release = threading.Event()
    asr_ended = threading.Event()
    asr_unload_called = False

    class SlowLoadASREngine(FakeASREngine):
        def load(self, model_path=None):
            asr_entered.set()
            asr_release.wait(timeout=3.0)
            try:
                super().load(model_path)
            finally:
                asr_ended.set()

        def unload(self):
            nonlocal asr_unload_called
            asr_unload_called = True
            super().unload()

    settings = WebSettings(SHUTDOWN_GRACE_SEC=0.02)
    app = create_app(settings=settings, asr_engine=SlowLoadASREngine())

    try:
        async with app.router.lifespan_context(app):
            await asyncio.to_thread(asr_entered.wait, 2.0)
            assert app.state.supervisor.is_loader_running() is True

        assert asr_ended.is_set() is False
        assert asr_unload_called is False

        # Release
        asr_release.set()
        await asyncio.to_thread(asr_ended.wait, 2.0)
        await app.state.supervisor.shutdown(runner_clean=True, grace_sec=0.5)
        assert asr_unload_called is True
    finally:
        asr_release.set()


@pytest.mark.asyncio
async def test_c06_translation_load_failure_during_shutdown_does_not_start_asr() -> None:
    """C06: Translation load lỗi trong lúc shutdown thì ASR tuyệt đối không được gọi, state giữ stopping."""
    t_entered = threading.Event()
    t_gate = threading.Event()
    asr_load_called = False
    asr_entered = threading.Event()
    asr_gate = threading.Event()

    class FailingTranslationEngine(FakeTranslationEngine):
        def load(self, bundle_path=None):
            t_entered.set()
            t_gate.wait(timeout=2.0)
            raise RuntimeError("fake load failure during shutdown")

    class ProbedASREngine(FakeASREngine):
        def load(self, model_path=None):
            nonlocal asr_load_called
            asr_load_called = True
            asr_entered.set()
            asr_gate.wait(timeout=2.0)
            super().load(model_path)

    settings = WebSettings(SHUTDOWN_GRACE_SEC=0.3)
    t_engine = FailingTranslationEngine()
    a_engine = ProbedASREngine()
    app = create_app(settings=settings, translation_engine=t_engine, asr_engine=a_engine)

    try:
        ctx = app.router.lifespan_context(app)
        await ctx.__aenter__()

        # Đợi translation bắt đầu nạp
        await asyncio.to_thread(t_entered.wait, 2.0)

        # Kích hoạt exit lifespan
        exit_task = asyncio.create_task(ctx.__aexit__(None, None, None))

        # Đợi supervisor._is_stopping == True
        for _ in range(50):
            if app.state.supervisor._is_stopping:
                break
            await asyncio.sleep(0.01)
        assert app.state.supervisor._is_stopping is True

        # Mở cổng cho translation load ném exception
        t_gate.set()

        # Chờ exit hoàn tất
        await exit_task

        # Khẳng định ASR không bao giờ được gọi và state giữ stopping
        assert asr_load_called is False, "ASR.load TUYỆT ĐỐI không được gọi sau khi shutdown bắt đầu!"
        assert app.state.supervisor.translation_state == "stopping"
        assert app.state.supervisor.asr_state == "stopping"
    finally:
        t_gate.set()
        asr_gate.set()


@pytest.mark.asyncio
async def test_c06_shutdown_when_load_job_queued_before_thread_start() -> None:
    """C06: Kiểm tra race window: load job đã xếp chờ nhưng thread chưa bắt đầu thì shutdown không unload/start đua nhau."""
    load_called = False

    class TestEngine(FakeTranslationEngine):
        def load(self, bundle_path=None):
            nonlocal load_called
            load_called = True
            super().load(bundle_path)

    settings = WebSettings(SHUTDOWN_GRACE_SEC=0.5)
    engine = TestEngine()
    app = create_app(settings=settings, translation_engine=engine, asr_engine=None)
    supervisor = app.state.supervisor

    # Giả lập 1 load work đã được nhận/xếp chờ trước khi worker thread được cấp phát
    with supervisor._loader_lock:
        supervisor._pending_load_count += 1
        supervisor._loader_finished_event.clear()

    # Xác nhận ngay lúc này is_loader_running() đã phải trả về True (không có window race)
    assert supervisor.is_loader_running() is True

    # Kích hoạt shutdown trong lúc job đang chờ
    shutdown_task = asyncio.create_task(supervisor.shutdown(runner_clean=True, grace_sec=0.5))
    await asyncio.sleep(0.01)
    assert supervisor._is_stopping is True
    assert supervisor.translation_state == "stopping"

    # Luồng worker thread thức dậy
    def simulated_worker():
        tid = threading.get_ident()
        with supervisor._loader_lock:
            supervisor._active_loader_tids.add(tid)
            should_run = not supervisor._is_stopping

        try:
            if should_run:
                engine.load()
        finally:
            with supervisor._loader_lock:
                supervisor._active_loader_tids.discard(tid)
                supervisor._pending_load_count -= 1
                if supervisor._pending_load_count == 0 and not supervisor._active_loader_tids:
                    supervisor._loader_finished_event.set()

    worker_thread = threading.Thread(target=simulated_worker)
    worker_thread.start()
    worker_thread.join()

    await shutdown_task

    assert load_called is False, "engine.load() phải được bỏ qua vì supervisor đang stopping!"
    assert supervisor._unloaded is True, "engine phải được unload an toàn sau khi thread kết thúc"


@pytest.mark.asyncio
async def test_r4_pipeline_translation_fails_but_mock_asr_ready() -> None:
    """R4: Cấu hình pipeline translation lỗi load bình thường (chưa có weights), ASR mock vẫn nạp và phục vụ HTTP 200."""
    settings = WebSettings(_env_file=None, TRANSLATION_ENGINE_TYPE="pipeline", ASR_ENGINE_TYPE="mock")
    app = create_app(settings=settings)
    supervisor = app.state.supervisor

    async with app.router.lifespan_context(app):
        await supervisor.wait_loaded()
        assert supervisor._is_stopping is False
        assert supervisor.translation_state == "failed"
        assert supervisor.asr_state == "ready"
        assert supervisor.get_overall_status() == "degraded"

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            h = await client.get("/api/health")
            assert h.status_code == 200
            assert h.json()["status"] == "degraded"
            assert h.json()["translation"]["state"] == "failed"
            assert h.json()["asr"]["state"] == "ready"

            t = await client.post("/api/translate", json={"text": "hello", "direction": "vi-tay"})
            assert t.status_code == 503
            assert t.json()["error_code"] == "MODEL_NOT_READY"

            wav = build_wav_bytes(duration_sec=1.0)
            files = {"file": ("test.wav", io.BytesIO(wav), "audio/wav")}
            a = await client.post("/api/asr/transcribe", files=files, data={"language": "vi"})
            assert a.status_code == 200
            assert "[MOCK ASR]" in a.json()["transcript"]


@pytest.mark.asyncio
async def test_r4_mock_translation_ready_but_whisper_asr_fails() -> None:
    """R4: Cấu hình mock translation nạp thành công, whisper ASR lỗi load bình thường (thiếu weights), dịch vẫn HTTP 200."""
    settings = WebSettings(_env_file=None, TRANSLATION_ENGINE_TYPE="mock", ASR_ENGINE_TYPE="whisper")
    app = create_app(settings=settings)
    supervisor = app.state.supervisor

    async with app.router.lifespan_context(app):
        await supervisor.wait_loaded()
        assert supervisor._is_stopping is False
        assert supervisor.translation_state == "ready"
        assert supervisor.asr_state == "failed"
        assert supervisor.get_overall_status() == "degraded"

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            h = await client.get("/api/health")
            assert h.status_code == 200
            assert h.json()["status"] == "degraded"
            assert h.json()["translation"]["state"] == "ready"
            assert h.json()["asr"]["state"] == "failed"

            t = await client.post("/api/translate", json={"text": "hello", "direction": "vi-tay"})
            assert t.status_code == 200
            assert "[MOCK vi->tyz]" in t.json()["translation"]

            wav = build_wav_bytes(duration_sec=1.0)
            files = {"file": ("test.wav", io.BytesIO(wav), "audio/wav")}
            a = await client.post("/api/asr/transcribe", files=files, data={"language": "vi"})
            assert a.status_code == 503
            assert a.json()["error_code"] == "MODEL_NOT_READY"


# ==============================================================================
# C07: Worker bỏ qua job đã quá queue deadline khi event loop bị nghẽn
# ==============================================================================


@pytest.mark.asyncio
async def test_c07_worker_skips_job_after_queue_deadline_event_loop_stalled() -> None:
    """C07: Tái hiện đúng probe coordinator: Timer release worker trong lúc event loop bị stall, worker tự phát hiện quá hạn."""
    job_a_entered = threading.Event()
    job_a_release = threading.Event()
    job_b_called = False

    settings = WebSettings(
        INFERENCE_WORKERS=1,
        MAX_QUEUED_INFERENCES=2,
        QUEUE_TIMEOUT_SEC=0.03,
    )
    runner = InferenceRunner(settings)
    await runner.start()

    def run_a():
        job_a_entered.set()
        job_a_release.wait(timeout=2.0)
        return "a_done"

    def run_b():
        nonlocal job_b_called
        job_b_called = True
        return "b_done"

    try:
        task_a = asyncio.create_task(runner.run(run_a, task_type="translation", request_id="req-a"))
        await asyncio.to_thread(job_a_entered.wait, 2.0)
        assert runner.active_count == 1

        task_b = asyncio.create_task(runner.run(run_b, task_type="translation", request_id="req-b"))
        # Yield để event loop admit Job B vào queue
        await asyncio.sleep(0)
        assert runner.queued_count == 1

        # Timer sau 0.07s release A trong lúc event loop bị giữ 0.15s
        threading.Timer(0.07, job_a_release.set).start()
        # Event loop bị stall 0.15s
        time.sleep(0.15)

        # Worker bốc B tại thời điểm 0.07s (> queue_deadline 0.03s), hủy B và ném phase=queue
        res_a = await task_a
        assert res_a.value == "a_done"

        with pytest.raises(InferenceTimeoutError) as exc_info:
            await task_b
        assert exc_info.value.phase == "queue"

        # Đảm bảo hàm run_b KHÔNG BAO GIỜ được gọi
        assert job_b_called is False
    finally:
        job_a_release.set()
        await runner.shutdown(0.5)


# ==============================================================================
# C08: Multipart cắt cụt đóng sạch toàn bộ spool files và từ chối part dở
# ==============================================================================


def test_c08_truncated_multipart_language_field_returns_400_invalid_input() -> None:
    """C08: Tái hiện đúng repro coordinator: part language bị cắt cụt không có closing boundary trả về 400 INVALID_INPUT."""
    created_files: list[Any] = []

    class TrackingSpooledTemporaryFile:
        def __init__(self, *args, **kwargs):
            self._f = OrigSpooledTemporaryFile(*args, **kwargs)
            created_files.append(self)

        def __getattr__(self, name):
            return getattr(self._f, name)

        @property
        def closed(self):
            return self._f.closed

    saved_spool = formparsers.SpooledTemporaryFile
    formparsers.SpooledTemporaryFile = TrackingSpooledTemporaryFile  # type: ignore

    try:
        app = create_app()
        # Repro từ coordinator: file hoàn chỉnh nhưng language bị cắt cụt và thiếu closing boundary
        body = (
            b'--B\r\nContent-Disposition: form-data; name="file"; filename="x.wav"\r\nContent-Type: audio/wav\r\n\r\n'
            + build_wav_bytes(duration_sec=0.001)
            + b'\r\n--B\r\nContent-Disposition: form-data; name="language"\r\n\r\nen'
        )
        headers = {"Content-Type": "multipart/form-data; boundary=B"}

        with TestClient(app) as client:
            resp = client.post("/api/asr/transcribe", content=body, headers=headers)
            assert resp.status_code == 400
            assert resp.json()["error_code"] == "INVALID_INPUT"

        # Đảm bảo 100% spool files tạo ra đã được đóng
        assert len(created_files) >= 1
        for f in created_files:
            assert f.closed is True, "Phát hiện spool file bị bỏ quên không đóng!"
    finally:
        formparsers.SpooledTemporaryFile = saved_spool
        for f in created_files:
            if not f.closed:
                f.close()


def test_c08_missing_closing_boundary_after_complete_parts_returns_400() -> None:
    """C08: Cả 2 part đều có nội dung hoàn chỉnh nhưng thiếu boundary kết thúc container (--B--) phải trả về 400."""
    app = create_app()
    body = (
        b'--B\r\nContent-Disposition: form-data; name="file"; filename="x.wav"\r\nContent-Type: audio/wav\r\n\r\n'
        + build_wav_bytes(duration_sec=0.001)
        + b'\r\n--B\r\nContent-Disposition: form-data; name="language"\r\n\r\nvi\r\n'
    )
    headers = {"Content-Type": "multipart/form-data; boundary=B"}

    with TestClient(app) as client:
        resp = client.post("/api/asr/transcribe", content=body, headers=headers)
        assert resp.status_code == 400
        assert resp.json()["error_code"] == "INVALID_INPUT"


# ==============================================================================
# C09: Không rò rỉ exception nội bộ hoặc đường dẫn file
# ==============================================================================


def test_c09_internal_exception_sanitized_no_leak() -> None:
    """C09: Lỗi nội bộ không lộ stack trace, private path hoặc sentinels trong translation."""
    fake_engine = FakeTranslationEngine(raise_unexpected_error=True)
    app = create_app(translation_engine=fake_engine)

    with TestClient(app) as client:
        wait_client_loaded(client)
        resp = client.post(
            "/api/translate",
            json={"text": "Hello", "direction": "vi-tay"},
        )
        assert resp.status_code == 500
        data = resp.json()
        assert data["error_code"] == "INFERENCE_FAILED"
        assert data["message"] == "Suy luận dịch thất bại trong quá trình xử lý."
        assert "private" not in resp.text.lower()
        assert "sentinel" not in resp.text.lower()
        assert "traceback" not in resp.text.lower()


def test_c09_asr_internal_exception_sanitized_no_leak() -> None:
    """C09: Lỗi nội bộ không lộ stack trace hoặc sentinels trong ASR."""
    fake_asr = FakeASREngine(raise_unexpected_error=True)
    app = create_app(asr_engine=fake_asr)

    with TestClient(app) as client:
        wait_client_loaded(client)
        wav = build_wav_bytes(duration_sec=0.5)
        resp = client.post(
            "/api/asr/transcribe",
            files={"file": ("test.wav", io.BytesIO(wav), "audio/wav")},
            data={"language": "vi"},
        )
        assert resp.status_code == 500
        data = resp.json()
        assert data["error_code"] == "ASR_FAILURE"
        assert data["message"] == "Nhận dạng giọng nói thất bại trong quá trình xử lý."
        assert "traceback" not in resp.text.lower()


# ==============================================================================
# C11: Lỗi tài nguyên sau timeout chuyển engine failed
# ==============================================================================


@pytest.mark.asyncio
async def test_c11_late_resource_error_transitions_engine_to_failed() -> None:
    """C11: Lỗi tài nguyên sau khi request đã timeout vẫn chuyển engine sang failed và request sau 503."""
    worker_started = threading.Event()
    worker_hold = threading.Event()

    class OOMEngine(FakeTranslationEngine):
        def translate(self, text: str, direction: str):
            worker_started.set()
            worker_hold.wait(timeout=2.0)
            raise MemoryError("Simulated late out-of-memory error")

    settings = WebSettings(
        INFERENCE_WORKERS=1,
        TRANSLATION_TIMEOUT_SEC=0.05,
    )
    app = create_app(settings=settings, translation_engine=OOMEngine())

    async with app.router.lifespan_context(app):
        await app.state.supervisor.wait_loaded()
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            resp1 = await ac.post(
                "/api/translate",
                json={"text": "test oom", "direction": "vi-tay"},
            )
            assert resp1.status_code == 504
            assert resp1.json()["error_code"] == "INFERENCE_TIMEOUT"

            # Giải phóng worker để ném MemoryError muộn
            worker_hold.set()
            for _ in range(50):
                if app.state.supervisor.translation_state == "failed":
                    break
                await asyncio.sleep(0.01)

            assert app.state.supervisor.translation_state == "failed"
            h_resp = await ac.get("/api/health")
            assert h_resp.json()["status"] == "degraded"
            assert h_resp.json()["translation"]["state"] == "failed"

            resp2 = await ac.post(
                "/api/translate",
                json={"text": "test next", "direction": "vi-tay"},
            )
            assert resp2.status_code == 503
            assert resp2.json()["error_code"] == "MODEL_NOT_READY"


# ==============================================================================
# C12: Validate metadata bắt buộc, không publish ready rỗng
# ==============================================================================


@pytest.mark.parametrize(
    "field,bad_value",
    [
        ("artifact_id", ""),
        ("artifact_id", "   "),
        ("checkpoint_version", ""),
        ("tokenizer_version", ""),
        ("model_id", ""),
    ],
)
@pytest.mark.asyncio
async def test_c12_translation_mandatory_fields_fail_ready(field: str, bad_value: str) -> None:
    """C12: Bất kỳ trường metadata dịch bắt buộc nào bị rỗng đều làm hỏng readiness."""

    class BadFieldEngine(FakeTranslationEngine):
        def get_metadata(self):
            meta = super().get_metadata()
            return dataclasses.replace(meta, **{field: bad_value})

    app = create_app(translation_engine=BadFieldEngine())
    async with app.router.lifespan_context(app):
        await app.state.supervisor.wait_loaded()
        assert app.state.supervisor.translation_state == "failed"

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            h_resp = await ac.get("/api/health")
            assert h_resp.json()["status"] == "degraded"
            assert h_resp.json()["translation"]["state"] == "failed"
            assert h_resp.json()["translation"]["active_model_id"] is None


@pytest.mark.asyncio
async def test_c12_inconsistent_is_mock_fails_ready() -> None:
    """C12: is_mock không khớp engine_type (như engine_type='mock' nhưng is_mock=False) phải fail readiness."""

    class InconsistentMockEngine(FakeTranslationEngine):
        def get_metadata(self):
            meta = super().get_metadata()
            return dataclasses.replace(meta, is_mock=False, engine_type="mock")

    app = create_app(translation_engine=InconsistentMockEngine())
    async with app.router.lifespan_context(app):
        await app.state.supervisor.wait_loaded()
        assert app.state.supervisor.translation_state == "failed"


@pytest.mark.asyncio
async def test_c12_crashing_get_metadata_does_not_crash_health_snapshot() -> None:
    """C12: Engine ném lỗi trong get_metadata() lúc chưa ready thì /api/health vẫn đọc snapshot an toàn."""

    class CrashingMetadataEngine(FakeTranslationEngine):
        def get_metadata(self):
            if not self.is_ready():
                raise RuntimeError("Crashing before ready!")
            return super().get_metadata()

    app = create_app(translation_engine=CrashingMetadataEngine())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/api/health")
        assert r.status_code == 200
        # Đọc snapshot an toàn theo config
        assert r.json()["translation"]["engine_type"] == "mock"
        assert r.json()["translation"]["is_mock"] is True


# ==============================================================================
# C13: Body JSON sai encoding trả INVALID_INPUT (400)
# ==============================================================================


def test_c13_invalid_json_encoding_returns_invalid_input() -> None:
    """C13: Payload JSON có byte mã hóa sai (b'\\xff') trả về 400 INVALID_INPUT, không trả HTTP_ERROR."""
    app = create_app()
    with TestClient(app) as client:
        resp = client.post(
            "/api/translate",
            content=b"\xff",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400
        body = resp.json()
        assert body["error_code"] == "INVALID_INPUT"
        assert body["status"] == "error"
        assert "request_id" in body


# ==============================================================================
# C14: Cấm tái khởi động runner khi chưa dừng / không vượt quá INFERENCE_WORKERS
# ==============================================================================


@pytest.mark.asyncio
async def test_c14_start_prohibited_while_running_or_stopping() -> None:
    """C14: start() cấm tái khởi động khi runner đang dừng hoặc worker chưa drain; không nhân đôi worker thread."""
    job_started = threading.Event()
    job_hold = threading.Event()

    def long_task():
        job_started.set()
        job_hold.wait(timeout=2.0)
        return "done"

    settings = WebSettings(INFERENCE_WORKERS=1, SHUTDOWN_GRACE_SEC=0.01)
    runner = InferenceRunner(settings)
    await runner.start()

    try:
        task = asyncio.create_task(runner.run(long_task, task_type="translation", request_id="req-14"))
        await asyncio.to_thread(job_started.wait, 2.0)
        assert runner.active_count == 1

        # Shutdown với grace cực ngắn -> timed out
        clean = await runner.shutdown(grace_sec=0.01)
        assert clean is False

        # Cố tình gọi start() lại trong khi worker cũ vẫn đang chạy: BẮT BUỘC ném RuntimeError
        with pytest.raises(RuntimeError) as exc_info:
            await runner.start()
        assert "Không thể tái khởi động InferenceRunner" in str(exc_info.value)

        # Số worker active không vượt quá INFERENCE_WORKERS=1
        assert runner.active_count == 1
    finally:
        job_hold.set()
        await task
        await runner.shutdown(0.5)
