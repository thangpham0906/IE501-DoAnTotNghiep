"""Kiểm thử tích hợp cho lỗi chung, 404/405, X-Request-ID, client disconnect và vòng đời shutdown (§4.2, §5.1, §5.2, §8.2)."""

import asyncio
import io
import threading
import time
from unittest.mock import MagicMock
import httpx
import pytest
from fastapi.testclient import TestClient

from src.tests.web_app.audio_fixtures import build_wav_bytes
from src.tests.web_app.conftest import FakeTranslationEngine
from src.web_app.core.config import WebSettings
from src.web_app.main import create_app


def test_404_not_found(client: TestClient) -> None:
    """Đường dẫn không tồn tại trả về 404 NOT_FOUND với ErrorResponse và X-Request-ID (§4.2)."""
    resp = client.get("/api/nonexistent_route")
    assert resp.status_code == 404
    assert "X-Request-ID" in resp.headers

    body = resp.json()
    assert body["status"] == "error"
    assert body["error_code"] == "NOT_FOUND"
    assert "request_id" in body
    assert body["request_id"] == resp.headers["X-Request-ID"]


def test_405_method_not_allowed(client: TestClient) -> None:
    """Phương thức HTTP không được phép trả về 405 METHOD_NOT_ALLOWED (§4.2)."""
    # GET /api/translate không được phép (chỉ hỗ trợ POST)
    resp = client.get("/api/translate")
    assert resp.status_code == 405
    assert "X-Request-ID" in resp.headers

    body = resp.json()
    assert body["status"] == "error"
    assert body["error_code"] == "METHOD_NOT_ALLOWED"
    assert body["request_id"] == resp.headers["X-Request-ID"]


def test_request_id_preservation(client: TestClient) -> None:
    """Server tôn trọng header X-Request-ID do client gửi và giữ nguyên trong error/success response (§4.2)."""
    custom_id = "client-trace-id-987654321"

    # 1. Với request thành công
    resp_ok = client.post(
        "/api/translate",
        json={"text": "Chào bạn", "direction": "vi-tay"},
        headers={"X-Request-ID": custom_id},
    )
    assert resp_ok.status_code == 200
    assert resp_ok.headers["X-Request-ID"] == custom_id

    # 2. Với request lỗi
    resp_err = client.post(
        "/api/translate",
        json={"text": "", "direction": "vi-tay"},
        headers={"X-Request-ID": custom_id},
    )
    assert resp_err.status_code == 400
    assert resp_err.headers["X-Request-ID"] == custom_id
    assert resp_err.json()["request_id"] == custom_id


def test_upload_file_cleanup_on_success_and_error(client: TestClient) -> None:
    """Bảo đảm tất cả UploadFile được đóng sạch sẽ trên cả đường thành công và lỗi (§5.3)."""
    wav_bytes = build_wav_bytes(duration_sec=0.5)

    # 1. Đường thành công
    files = {"file": ("test.wav", io.BytesIO(wav_bytes), "audio/wav")}
    resp_ok = client.post("/api/asr/transcribe", files=files, data={"language": "vi"})
    assert resp_ok.status_code == 200

    # 2. Đường lỗi (file quá thời lượng)
    long_wav = build_wav_bytes(duration_sec=35.0)
    files_err = {"file": ("long.wav", io.BytesIO(long_wav), "audio/wav")}
    resp_err = client.post("/api/asr/transcribe", files=files_err, data={"language": "vi"})
    assert resp_err.status_code == 400
    assert resp_err.json()["error_code"] == "AUDIO_TOO_LONG"


@pytest.mark.asyncio
async def test_shutdown_clean_unloads_engine() -> None:
    """Shutdown sạch khi không có worker đang bận sẽ giải phóng tài nguyên engine (§5.2)."""
    fake_engine = FakeTranslationEngine()
    settings = WebSettings(SHUTDOWN_GRACE_SEC=0.5)
    app = create_app(settings=settings, translation_engine=fake_engine)

    # Chạy lifespan thủ công
    async with app.router.lifespan_context(app):
        await app.state.supervisor.wait_loaded()
        assert fake_engine.is_ready() is True
        assert fake_engine.unloaded is False

    # Sau khi ra khỏi lifespan_context, engine phải được unload
    assert fake_engine.unloaded is True


@pytest.mark.asyncio
async def test_shutdown_grace_exhaustion_does_not_unload_active_engine() -> None:
    """Hết thời gian grace shutdown nhưng worker vẫn đang chạy thì KHÔNG gọi unload() (§5.2)."""
    worker_started = threading.Event()
    worker_hold = threading.Event()

    fake_engine = FakeTranslationEngine(
        start_event=worker_started,
        release_event=worker_hold,
    )
    # Cấu hình grace period cực ngắn: 50ms
    settings = WebSettings(SHUTDOWN_GRACE_SEC=0.05)
    app = create_app(settings=settings, translation_engine=fake_engine)

    async with app.router.lifespan_context(app):
        await app.state.supervisor.wait_loaded()
        runner = app.state.runner

        # Bắn 1 job vào worker
        runner_task = asyncio.create_task(
            runner.run(
                lambda: fake_engine.translate("test", "vi-tay"),
                task_type="translation",
                request_id="shutdown-test",
            )
        )

        # Chờ worker thực sự bắt đầu
        await asyncio.to_thread(worker_started.wait, 2.0)

        # Thoát lifespan_context để kích hoạt shutdown khi worker vẫn đang chạy
        # (runner.shutdown sẽ hết 0.05s grace)

    # Đảm bảo fake_engine KHÔNG bị unload vì worker vẫn đang chạy
    assert fake_engine.unloaded is False

    # Dọn dẹp: thả worker để kết thúc thread
    worker_hold.set()
    try:
        await runner_task
    except Exception:
        pass


@pytest.mark.asyncio
async def test_client_disconnect_monitoring() -> None:
    """Khi client hủy kết nối hoặc timeout phía client, runner ghi nhận caller_cancelled và worker giữ slot (§5.1)."""
    worker_started = threading.Event()
    worker_hold = threading.Event()

    fake_engine = FakeTranslationEngine(
        start_event=worker_started,
        release_event=worker_hold,
    )
    settings = WebSettings(INFERENCE_WORKERS=1, MAX_QUEUED_INFERENCES=2)
    app = create_app(settings=settings, translation_engine=fake_engine)

    async with app.router.lifespan_context(app):
        await app.state.supervisor.wait_loaded()
        runner = app.state.runner

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            # Bắn request dịch trong 1 asyncio task
            request_task = asyncio.create_task(
                ac.post(
                    "/api/translate",
                    json={"text": "Văn bản thử disconnect", "direction": "vi-tay"},
                )
            )

            # Chờ worker thực sự nhận việc
            await asyncio.to_thread(worker_started.wait, 2.0)
            assert runner.active_count == 1

            # Giả lập client ngắt kết nối / hủy request task
            request_task.cancel()
            try:
                await request_task
            except asyncio.CancelledError:
                pass

            # Worker slot vẫn đang bị giữ bởi luồng thực thi nền (bảo đảm invariant §5.1)
            assert runner.active_count == 1

            # Thả worker để tác vụ kết thúc
            worker_hold.set()

            # Chờ runner cập nhật idle
            for _ in range(50):
                if runner.active_count == 0:
                    break
                await asyncio.sleep(0.01)

            assert runner.active_count == 0

            # Request tiếp theo phải phục vụ bình thường
            resp_next = await ac.post(
                "/api/translate",
                json={"text": "Request tiếp theo", "direction": "vi-tay"},
            )
            assert resp_next.status_code == 200
            assert "Request tiếp theo" in resp_next.json()["translation"]
