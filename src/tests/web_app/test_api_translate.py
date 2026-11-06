"""Kiểm thử tích hợp chi tiết cho POST /api/translate (§4.3, §8.2)."""

import threading
import time
import pytest
from fastapi.testclient import TestClient

from src.tests.web_app.conftest import FakeTranslationEngine, wait_client_loaded
from src.web_app.core.config import WebSettings
from src.web_app.main import create_app


def test_translate_success_two_directions(client: TestClient) -> None:
    """POST /api/translate thành công với cả hai chiều vi-tay và tay-vi (§4.3)."""
    # 1. Chiều vi-tay
    resp_vi = client.post(
        "/api/translate",
        json={"text": "Hôm nay trời nắng đẹp.", "direction": "vi-tay"},
    )
    assert resp_vi.status_code == 200
    assert "X-Request-ID" in resp_vi.headers
    data_vi = resp_vi.json()
    assert data_vi["status"] == "success"
    assert data_vi["translation"] == "[MOCK vi->tyz] Hôm nay trời nắng đẹp."
    assert data_vi["direction"] == "vi-tay"
    assert data_vi["source_lang"] == "vi"
    assert data_vi["target_lang"] == "tyz"
    assert data_vi["model_metadata"]["is_mock"] is True
    assert data_vi["latency_ms"] >= 0
    assert data_vi["queue_ms"] >= 0

    # 2. Chiều tay-vi
    resp_tay = client.post(
        "/api/translate",
        json={"text": "Báo cáo tiến độ dự án.", "direction": "tay-vi"},
    )
    assert resp_tay.status_code == 200
    data_tay = resp_tay.json()
    assert data_tay["status"] == "success"
    assert data_tay["translation"] == "[MOCK tyz->vi] Báo cáo tiến độ dự án."
    assert data_tay["direction"] == "tay-vi"
    assert data_tay["source_lang"] == "tyz"
    assert data_tay["target_lang"] == "vi"


def test_translate_unicode_nfc_and_whitespace_trim(client: TestClient) -> None:
    """Chuẩn hóa Unicode NFC và cắt bỏ khoảng trắng hai đầu theo tập WHITESPACE_CHARS (§4.3)."""
    # Chuỗi chứa tổ hợp dấu NFD ('a' + U+0301) và khoảng trắng đặc thù ở hai đầu
    nfd_text = " 　á b c\t\n\xa0"
    resp = client.post(
        "/api/translate",
        json={"text": nfd_text, "direction": "vi-tay"},
    )
    assert resp.status_code == 200
    data = resp.json()
    # Ký tự bên trong ' b c' được giữ nguyên, hai đầu bị cắt, 'á' thành 'á' (NFC)
    assert data["translation"] == "[MOCK vi->tyz] á b c"


def test_translate_non_bmp_characters(client: TestClient) -> None:
    """Hỗ trợ ký tự ngoài BMP (emoji, chữ hiếm) đếm đúng code point (§4.3)."""
    text = "Xin chào 👋 🌟 𠀀"
    resp = client.post(
        "/api/translate",
        json={"text": text, "direction": "vi-tay"},
    )
    assert resp.status_code == 200
    assert "👋 🌟 𠀀" in resp.json()["translation"]


def test_translate_length_boundary(client: TestClient) -> None:
    """Kiểm tra ranh giới độ dài: đúng 1000 code points -> 200; 1001 -> 400 INPUT_TOO_LONG."""
    # 1. Đúng 1000 ký tự
    text_1000 = "a" * 1000
    resp_1000 = client.post(
        "/api/translate",
        json={"text": text_1000, "direction": "vi-tay"},
    )
    assert resp_1000.status_code == 200

    # 2. Vượt quá 1 ký tự: 1001 ký tự
    text_1001 = "a" * 1001
    resp_1001 = client.post(
        "/api/translate",
        json={"text": text_1001, "direction": "vi-tay"},
    )
    assert resp_1001.status_code == 400
    err = resp_1001.json()
    assert err["status"] == "error"
    assert err["error_code"] == "INPUT_TOO_LONG"
    assert err["detail"]["current_length"] == 1001
    assert err["detail"]["max_allowed"] == 1000
    assert err["detail"]["limit_unit"] == "code_points"


def test_translate_empty_after_normalization(client: TestClient) -> None:
    """Văn bản rỗng hoặc chỉ có khoảng trắng trả về 400 INVALID_INPUT (§4.2)."""
    for empty_input in ["", "   ", "\t\n\r 　"]:
        resp = client.post(
            "/api/translate",
            json={"text": empty_input, "direction": "vi-tay"},
        )
        assert resp.status_code == 400
        assert resp.json()["error_code"] == "INVALID_INPUT"


def test_translate_schema_validation_priority(client: TestClient) -> None:
    """Lỗi sai kiểu/thiếu trường/thừa trường được ưu tiên mã INVALID_INPUT (§4.2)."""
    # 1. Thiếu trường bắt buộc
    resp_missing = client.post("/api/translate", json={"text": "hello"})
    assert resp_missing.status_code == 400
    assert resp_missing.json()["error_code"] == "INVALID_INPUT"

    # 2. Sai kiểu dữ liệu (text là số nguyên)
    resp_type = client.post(
        "/api/translate", json={"text": 12345, "direction": "vi-tay"}
    )
    assert resp_type.status_code == 400
    assert resp_type.json()["error_code"] == "INVALID_INPUT"

    # 3. Thừa trường ngoài hợp đồng (extra="forbid")
    resp_extra = client.post(
        "/api/translate",
        json={
            "text": "hello",
            "direction": "vi-tay",
            "temperature": 0.7,
        },
    )
    assert resp_extra.status_code == 400
    assert resp_extra.json()["error_code"] == "INVALID_INPUT"


def test_translate_direction_validation_priority(client: TestClient) -> None:
    """Direction không phải string -> INVALID_INPUT; direction là string nhưng sai -> UNSUPPORTED_DIRECTION."""
    # 1. Direction sai kiểu (là số hoặc mảng) -> INVALID_INPUT
    resp_wrong_type = client.post(
        "/api/translate", json={"text": "hello", "direction": 123}
    )
    assert resp_wrong_type.status_code == 400
    assert resp_wrong_type.json()["error_code"] == "INVALID_INPUT"

    # 2. Direction là string nhưng không được hỗ trợ -> UNSUPPORTED_DIRECTION
    resp_unsupported = client.post(
        "/api/translate", json={"text": "hello", "direction": "en-vi"}
    )
    assert resp_unsupported.status_code == 400
    assert resp_unsupported.json()["error_code"] == "UNSUPPORTED_DIRECTION"


def test_translate_model_id_validation(client: TestClient) -> None:
    """model_id rỗng -> INVALID_INPUT; model_id không khớp -> 404 MODEL_NOT_FOUND."""
    # 1. model_id là chuỗi rỗng
    resp_empty = client.post(
        "/api/translate",
        json={"text": "hello", "direction": "vi-tay", "model_id": "   "},
    )
    assert resp_empty.status_code == 400
    assert resp_empty.json()["error_code"] == "INVALID_INPUT"

    # 2. model_id không tồn tại
    resp_not_found = client.post(
        "/api/translate",
        json={"text": "hello", "direction": "vi-tay", "model_id": "unknown-model"},
    )
    assert resp_not_found.status_code == 404
    assert resp_not_found.json()["error_code"] == "MODEL_NOT_FOUND"

    # 3. model_id đúng
    resp_ok = client.post(
        "/api/translate",
        json={"text": "hello", "direction": "vi-tay", "model_id": "mock-demo"},
    )
    assert resp_ok.status_code == 200


def test_translate_model_not_ready() -> None:
    """Trả về 503 MODEL_NOT_READY khi engine dịch chưa hoàn tất nạp (§4.2)."""
    fake_engine = FakeTranslationEngine(block_load=True)
    app = create_app(translation_engine=fake_engine)

    with TestClient(app) as test_client:
        wait_client_loaded(test_client)
        resp = test_client.post(
            "/api/translate",
            json={"text": "hello", "direction": "vi-tay"},
        )
        assert resp.status_code == 503
        assert resp.json()["error_code"] == "MODEL_NOT_READY"


def test_translate_body_too_large() -> None:
    """Vượt quá MAX_JSON_BODY_BYTES bị chặn với 413 REQUEST_TOO_LARGE (§4.2, §5.3)."""
    settings = WebSettings(MAX_JSON_BODY_BYTES=512)
    app = create_app(settings=settings)

    with TestClient(app) as test_client:
        wait_client_loaded(test_client)
        # Gửi payload 1000 bytes vượt quá giới hạn 512 bytes
        large_text = "x" * 800
        resp = test_client.post(
            "/api/translate",
            json={"text": large_text, "direction": "vi-tay"},
        )
        assert resp.status_code == 413
        assert resp.json()["error_code"] == "REQUEST_TOO_LARGE"
        assert "X-Request-ID" in resp.headers


def test_translate_queue_overloaded() -> None:
    """Hàng đợi suy luận đầy trả về 503 SERVICE_OVERLOADED (§4.2, §5.1)."""
    worker_started = threading.Event()
    worker_release = threading.Event()

    # 1 worker, 1 queue slot
    settings = WebSettings(INFERENCE_WORKERS=1, MAX_QUEUED_INFERENCES=1)
    fake_engine = FakeTranslationEngine(
        start_event=worker_started, release_event=worker_release
    )
    app = create_app(settings=settings, translation_engine=fake_engine)

    with TestClient(app) as test_client:
        wait_client_loaded(test_client)
        # Request 1: Chiếm worker
        t1 = threading.Thread(
            target=lambda: test_client.post(
                "/api/translate", json={"text": "req1", "direction": "vi-tay"}
            ),
            daemon=True,
        )
        t1.start()
        assert worker_started.wait(timeout=2.0)

        # Request 2: Chiếm queue slot duy nhất
        t2 = threading.Thread(
            target=lambda: test_client.post(
                "/api/translate", json={"text": "req2", "direction": "vi-tay"}
            ),
            daemon=True,
        )
        t2.start()
        time.sleep(0.05)

        # Request 3: Vượt quá sức chứa -> 503 SERVICE_OVERLOADED
        resp_overloaded = test_client.post(
            "/api/translate", json={"text": "req3", "direction": "vi-tay"}
        )
        assert resp_overloaded.status_code == 503
        assert resp_overloaded.json()["error_code"] == "SERVICE_OVERLOADED"

        worker_release.set()
        t1.join(timeout=2.0)
        t2.join(timeout=2.0)


def test_translate_execution_timeout() -> None:
    """Quá thời hạn thực thi trả về 504 INFERENCE_TIMEOUT với phase=execution (§4.2, §5.1)."""
    worker_release = threading.Event()
    settings = WebSettings(
        INFERENCE_WORKERS=1,
        TRANSLATION_TIMEOUT_SEC=0.1,  # 100ms timeout
    )
    fake_engine = FakeTranslationEngine(release_event=worker_release)
    app = create_app(settings=settings, translation_engine=fake_engine)

    with TestClient(app) as test_client:
        wait_client_loaded(test_client)
        resp = test_client.post(
            "/api/translate",
            json={"text": "timeout test", "direction": "vi-tay"},
        )
        assert resp.status_code == 504
        data = resp.json()
        assert data["error_code"] == "INFERENCE_TIMEOUT"
        assert data["detail"]["phase"] == "execution"

        worker_release.set()


def test_translate_output_too_long() -> None:
    """Mô hình chạm giới hạn độ dài đầu ra trả về 500 OUTPUT_TOO_LONG (§4.2)."""
    fake_engine = FakeTranslationEngine(raise_output_too_long=True)
    app = create_app(translation_engine=fake_engine)

    with TestClient(app) as test_client:
        wait_client_loaded(test_client)
        resp = test_client.post(
            "/api/translate",
            json={"text": "output too long", "direction": "vi-tay"},
        )
        assert resp.status_code == 500
        assert resp.json()["error_code"] == "OUTPUT_TOO_LONG"


def test_translate_unexpected_inference_error() -> None:
    """Lỗi suy luận bất ngờ được ánh xạ về 500 INFERENCE_FAILED (§4.2)."""
    fake_engine = FakeTranslationEngine(raise_unexpected_error=True)
    app = create_app(translation_engine=fake_engine)

    with TestClient(app) as test_client:
        wait_client_loaded(test_client)
        resp = test_client.post(
            "/api/translate",
            json={"text": "crash text", "direction": "vi-tay"},
        )
        assert resp.status_code == 500
        assert resp.json()["error_code"] == "INFERENCE_FAILED"
        # Bảo đảm không lộ traceback
        assert "traceback" not in resp.text.lower()


def test_translate_fatal_memory_error_marks_supervisor_failed() -> None:
    """Lỗi cạn bộ nhớ (MemoryError) làm supervisor đánh dấu engine dịch failed (§4.2, §5.2)."""
    fake_engine = FakeTranslationEngine(raise_memory_error=True)
    app = create_app(translation_engine=fake_engine)

    with TestClient(app) as test_client:
        wait_client_loaded(test_client)
        resp = test_client.post(
            "/api/translate",
            json={"text": "oom text", "direction": "vi-tay"},
        )
        assert resp.status_code == 500
        assert resp.json()["error_code"] == "INFERENCE_FAILED"

        # Kiểm tra health sau lỗi nghiêm trọng: trạng thái phải là degraded và translation failed
        health_resp = test_client.get("/api/health")
        assert health_resp.json()["status"] == "degraded"
        assert health_resp.json()["translation"]["state"] == "failed"
