"""Kiểm thử tích hợp cho GET /api/health và GET /api/models (§4.5, §4.6, §8.2)."""

import threading
import time
import pytest
from fastapi.testclient import TestClient

from src.tests.web_app.conftest import (
    FakeASREngine,
    FakeTranslationEngine,
    wait_client_loaded,
)
from src.web_app.core.config import WebSettings
from src.web_app.main import create_app


def test_health_default_mock_ready(client: TestClient) -> None:
    """GET /api/health trả về status ready với đầy đủ metadata mock khi cả hai engine nạp thành công."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert "X-Request-ID" in resp.headers

    data = resp.json()
    assert data["status"] == "ready"
    assert data["api_version"] == "1"

    # Kiểm tra metadata translation
    t_info = data["translation"]
    assert t_info["state"] == "ready"
    assert t_info["engine_type"] == "mock"
    assert t_info["is_mock"] is True
    assert t_info["active_model_id"] == "mock-demo"
    assert set(t_info["supported_directions"]) == {"vi-tay", "tay-vi"}

    # Kiểm tra metadata ASR
    a_info = data["asr"]
    assert a_info["state"] == "ready"
    assert a_info["engine_type"] == "mock"
    assert a_info["is_mock"] is True
    assert a_info["model_id"] == "mock-asr"
    assert a_info["supported_languages"] == ["vi"]

    # Kiểm tra limits
    limits = data["limits"]
    assert limits["max_text_length"] == 1000
    assert limits["max_audio_file_bytes"] == 10485760
    assert limits["audio_format"] == "wav_pcm_s16le"


def test_health_during_engine_loading() -> None:
    """GET /api/health trả về status loading khi engine đang trong quá trình nạp nền."""
    load_gate = threading.Event()
    fake_engine = FakeTranslationEngine(load_event=load_gate)
    app = create_app(translation_engine=fake_engine)

    with TestClient(app) as test_client:
        # Khi load_gate chưa mở, engine ở trạng thái loading
        resp = test_client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "loading"
        assert data["translation"]["state"] == "loading"
        assert data["translation"]["active_model_id"] is None
        assert data["translation"]["supported_directions"] == []

        # Giải phóng load_gate để hoàn tất nạp
        load_gate.set()
        wait_client_loaded(test_client)  # Chờ luồng nền cập nhật state xác định (C15)

        resp_after = test_client.get("/api/health")
        assert resp_after.status_code == 200
        data_after = resp_after.json()
        assert data_after["status"] == "ready"
        assert data_after["translation"]["state"] == "ready"
        assert data_after["translation"]["active_model_id"] == "fake-model"


def test_health_asr_disabled_does_not_affect_translation() -> None:
    """ASR disabled không làm hỏng readiness dịch văn bản (§4.5)."""
    settings = WebSettings(ASR_ENGINE_TYPE="disabled")
    app = create_app(settings=settings, asr_engine=None)

    with TestClient(app) as test_client:
        wait_client_loaded(test_client)
        resp = test_client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ready"
        assert data["translation"]["state"] == "ready"
        assert data["asr"]["state"] == "disabled"
        assert data["asr"]["engine_type"] == "disabled"
        assert data["asr"]["is_mock"] is False
        assert data["asr"]["model_id"] is None
        assert data["asr"]["supported_languages"] == []


def test_health_engine_failed_returns_degraded() -> None:
    """Khi engine gặp lỗi nạp, health trả status degraded và không fallback sang mock."""
    fake_engine = FakeTranslationEngine(block_load=True)
    app = create_app(translation_engine=fake_engine)

    with TestClient(app) as test_client:
        wait_client_loaded(test_client)
        resp = test_client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "degraded"
        assert data["translation"]["state"] == "failed"


def test_health_and_models_withheld_worker_does_not_wait() -> None:
    """Health và models đọc trạng thái trong bộ nhớ, không chờ hàng đợi suy luận (§4.5, §8.2)."""
    worker_started = threading.Event()
    worker_release = threading.Event()

    fake_engine = FakeTranslationEngine(
        start_event=worker_started,
        release_event=worker_release,
    )
    settings = WebSettings(INFERENCE_WORKERS=1, MAX_QUEUED_INFERENCES=2)
    app = create_app(settings=settings, translation_engine=fake_engine)

    with TestClient(app) as test_client:
        wait_client_loaded(test_client)
        # Gửi request dịch trong background thread để chiếm worker slot
        bg_error: list[Exception] = []

        def run_busy_inference():
            try:
                test_client.post(
                    "/api/translate",
                    json={"text": "Văn bản thử nghiệm", "direction": "vi-tay"},
                )
            except Exception as e:
                bg_error.append(e)

        bg_thread = threading.Thread(target=run_busy_inference, daemon=True)
        bg_thread.start()

        # Đợi worker thực sự nhận việc và bị giữ
        assert worker_started.wait(timeout=2.0)

        # Trong lúc worker đang bị giữ, gọi GET /api/health
        start_time = time.monotonic()
        health_resp = test_client.get("/api/health")
        elapsed_health = time.monotonic() - start_time

        assert health_resp.status_code == 200
        assert elapsed_health < 0.2  # Phải phản hồi ngay lập tức, không đợi worker kết thúc
        assert health_resp.json()["status"] == "ready"

        # Tương tự, gọi GET /api/models cũng phải trả lời ngay
        start_time = time.monotonic()
        models_resp = test_client.get("/api/models")
        elapsed_models = time.monotonic() - start_time

        assert models_resp.status_code == 200
        assert elapsed_models < 0.2
        assert len(models_resp.json()["models"]) == 1

        # Giải phóng worker để hoàn tất kiểm thử sạch
        worker_release.set()
        bg_thread.join(timeout=2.0)
        assert len(bg_error) == 0


def test_models_when_translation_not_ready() -> None:
    """GET /api/models trả về models: [] khi engine chưa sẵn sàng (§4.6)."""
    fake_engine = FakeTranslationEngine(block_load=True)
    app = create_app(translation_engine=fake_engine)

    with TestClient(app) as test_client:
        wait_client_loaded(test_client)
        resp = test_client.get("/api/models")
        assert resp.status_code == 200
        data = resp.json()
        assert data == {"models": []}
