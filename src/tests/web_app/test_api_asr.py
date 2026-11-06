"""Kiểm thử tích hợp chi tiết cho POST /api/asr/transcribe (§4.4, §5.3, §8.2)."""

import io
import pytest
from fastapi.testclient import TestClient

from src.tests.web_app.audio_fixtures import build_wav_bytes
from src.tests.web_app.conftest import FakeASREngine, wait_client_loaded
from src.web_app.core.config import WebSettings
from src.web_app.main import create_app


def test_asr_transcribe_success(client: TestClient) -> None:
    """POST /api/asr/transcribe thành công với WAV hợp lệ và trả về đúng schema (§4.4)."""
    wav_bytes = build_wav_bytes(duration_sec=1.5)
    files = {"file": ("test.wav", io.BytesIO(wav_bytes), "audio/wav")}
    data = {"language": "vi"}

    resp = client.post("/api/asr/transcribe", files=files, data=data)
    assert resp.status_code == 200
    assert "X-Request-ID" in resp.headers

    body = resp.json()
    assert body["status"] == "success"
    assert "[MOCK ASR]" in body["transcript"]
    assert body["language"] == "vi"
    assert round(body["duration_sec"], 1) == 1.5
    assert body["model_metadata"]["is_mock"] is True
    assert body["model_metadata"]["engine_type"] == "mock"
    assert body["latency_ms"] >= 0
    assert body["queue_ms"] >= 0
    assert "Thử nghiệm giọng nói tiếng Việt" in body["disclaimer"]


def test_asr_multipart_validation_rules(client: TestClient) -> None:
    """Kiểm tra các quy tắc multipart: bắt buộc 1 file, tối đa 1 language, cấm extra field (§4.4, §5.3)."""
    wav_bytes = build_wav_bytes(duration_sec=0.5)

    # 1. Thiếu file
    resp_missing_file = client.post(
        "/api/asr/transcribe",
        data={"language": "vi"},
    )
    assert resp_missing_file.status_code == 400
    assert resp_missing_file.json()["error_code"] == "INVALID_INPUT"

    # 2. Nhiều hơn 1 file
    multiple_files = [
        ("file", ("f1.wav", io.BytesIO(wav_bytes), "audio/wav")),
        ("file", ("f2.wav", io.BytesIO(wav_bytes), "audio/wav")),
    ]
    resp_multi_file = client.post("/api/asr/transcribe", files=multiple_files)
    assert resp_multi_file.status_code == 400
    assert resp_multi_file.json()["error_code"] == "INVALID_INPUT"

    # 3. Thừa trường ngoài hợp đồng (extra field)
    resp_extra = client.post(
        "/api/asr/transcribe",
        files={"file": ("f1.wav", io.BytesIO(wav_bytes), "audio/wav")},
        data={"language": "vi", "extra_field": "disallowed"},
    )
    assert resp_extra.status_code == 400
    assert resp_extra.json()["error_code"] == "INVALID_INPUT"

    # 4. Trùng lặp trường language
    duplicate_lang = [
        ("file", ("f1.wav", io.BytesIO(wav_bytes), "audio/wav")),
        ("language", (None, "vi")),
        ("language", (None, "vi")),
    ]
    resp_dup_lang = client.post("/api/asr/transcribe", files=duplicate_lang)
    assert resp_dup_lang.status_code == 400
    assert resp_dup_lang.json()["error_code"] == "INVALID_INPUT"


def test_asr_unsupported_language(client: TestClient) -> None:
    """Ngôn ngữ ASR khác 'vi' trả về 400 UNSUPPORTED_ASR_LANGUAGE (§4.2, §4.4)."""
    wav_bytes = build_wav_bytes(duration_sec=0.5)
    files = {"file": ("test.wav", io.BytesIO(wav_bytes), "audio/wav")}

    for unsupported_lang in ["en", "tyz", "fr"]:
        resp = client.post(
            "/api/asr/transcribe",
            files=files,
            data={"language": unsupported_lang},
        )
        assert resp.status_code == 400
        assert resp.json()["error_code"] == "UNSUPPORTED_ASR_LANGUAGE"


def test_asr_file_too_large_chunk_bounded() -> None:
    """File vượt quá MAX_AUDIO_FILE_BYTES trong quá trình đọc chunk bị từ chối 413 AUDIO_TOO_LARGE (§5.3)."""
    settings = WebSettings(
        MAX_AUDIO_FILE_BYTES=1000,
        MAX_MULTIPART_BODY_BYTES=5000,
    )
    app = create_app(settings=settings)

    with TestClient(app) as test_client:
        wait_client_loaded(test_client)
        large_wav = build_wav_bytes(pcm_bytes=b"\x00" * 1500)
        files = {"file": ("large.wav", io.BytesIO(large_wav), "audio/wav")}
        resp = test_client.post("/api/asr/transcribe", files=files)

        assert resp.status_code == 413
        assert resp.json()["error_code"] == "AUDIO_TOO_LARGE"


def test_asr_body_too_large_middleware() -> None:
    """Toàn bộ body vượt quá MAX_MULTIPART_BODY_BYTES bị chặn bởi middleware với 413 REQUEST_TOO_LARGE (§4.2, §5.3)."""
    settings = WebSettings(
        MAX_AUDIO_FILE_BYTES=1000,
        MAX_MULTIPART_BODY_BYTES=1200,
    )
    app = create_app(settings=settings)

    with TestClient(app) as test_client:
        wait_client_loaded(test_client)
        very_large_bytes = b"x" * 2000
        files = {"file": ("huge.wav", io.BytesIO(very_large_bytes), "audio/wav")}
        resp = test_client.post("/api/asr/transcribe", files=files)

        assert resp.status_code == 413
        assert resp.json()["error_code"] == "REQUEST_TOO_LARGE"


def test_asr_audio_format_validation(client: TestClient) -> None:
    """Kiểm tra từ chối định dạng không hợp lệ: non-PCM, stereo, sample rate khác 16kHz (§4.2, §5.3)."""
    # 1. Non-RIFF
    corrupted_data = b"NOT_A_WAV_FILE_HEADER" + b"\x00" * 100
    resp_corrupt = client.post(
        "/api/asr/transcribe",
        files={"file": ("corrupt.wav", io.BytesIO(corrupted_data), "audio/wav")},
    )
    assert resp_corrupt.status_code == 400
    assert resp_corrupt.json()["error_code"] == "AUDIO_UNSUPPORTED_FORMAT"

    # 2. Sample rate 44.1 kHz (khác 16kHz)
    wav_44k = build_wav_bytes(sample_rate=44100, duration_sec=0.5)
    resp_44k = client.post(
        "/api/asr/transcribe",
        files={"file": ("44k.wav", io.BytesIO(wav_44k), "audio/wav")},
    )
    assert resp_44k.status_code == 400
    assert resp_44k.json()["error_code"] == "AUDIO_UNSUPPORTED_FORMAT"

    # 3. Stereo (2 kênh)
    wav_stereo = build_wav_bytes(num_channels=2, duration_sec=0.5)
    resp_stereo = client.post(
        "/api/asr/transcribe",
        files={"file": ("stereo.wav", io.BytesIO(wav_stereo), "audio/wav")},
    )
    assert resp_stereo.status_code == 400
    assert resp_stereo.json()["error_code"] == "AUDIO_UNSUPPORTED_FORMAT"


def test_asr_audio_duration_too_long(client: TestClient) -> None:
    """Thời lượng audio vượt quá MAX_AUDIO_DURATION_SEC (30s) trả về 400 AUDIO_TOO_LONG (§4.2, §5.3)."""
    wav_31s = build_wav_bytes(duration_sec=30.5)
    files = {"file": ("long.wav", io.BytesIO(wav_31s), "audio/wav")}

    resp = client.post("/api/asr/transcribe", files=files)
    assert resp.status_code == 400
    assert resp.json()["error_code"] == "AUDIO_TOO_LONG"


def test_asr_model_not_ready_or_disabled() -> None:
    """Trả về 503 MODEL_NOT_READY khi ASR disabled hoặc chưa sẵn sàng (§4.2)."""
    # 1. ASR disabled
    settings_disabled = WebSettings(ASR_ENGINE_TYPE="disabled")
    app_disabled = create_app(settings=settings_disabled, asr_engine=None)
    with TestClient(app_disabled) as test_client:
        wait_client_loaded(test_client)
        wav = build_wav_bytes(duration_sec=0.5)
        resp = test_client.post(
            "/api/asr/transcribe",
            files={"file": ("test.wav", io.BytesIO(wav), "audio/wav")},
        )
        assert resp.status_code == 503
        assert resp.json()["error_code"] == "MODEL_NOT_READY"

    # 2. ASR chưa nạp xong
    fake_asr = FakeASREngine(block_load=True)
    app_unready = create_app(asr_engine=fake_asr)
    with TestClient(app_unready) as test_client:
        wait_client_loaded(test_client)
        wav = build_wav_bytes(duration_sec=0.5)
        resp = test_client.post(
            "/api/asr/transcribe",
            files={"file": ("test.wav", io.BytesIO(wav), "audio/wav")},
        )
        assert resp.status_code == 503
        assert resp.json()["error_code"] == "MODEL_NOT_READY"


def test_asr_empty_or_whitespace_transcript_returns_no_speech() -> None:
    """ASR trả về transcript rỗng hoặc chỉ có khoảng trắng được ánh xạ sang 400 NO_SPEECH_DETECTED (§4.2, §8.2)."""
    # 1. Transcript rỗng hoàn toàn
    fake_asr_empty = FakeASREngine(return_empty_transcript=True)
    app_empty = create_app(asr_engine=fake_asr_empty)
    with TestClient(app_empty) as test_client:
        wait_client_loaded(test_client)
        wav = build_wav_bytes(duration_sec=0.5)
        resp = test_client.post(
            "/api/asr/transcribe",
            files={"file": ("test.wav", io.BytesIO(wav), "audio/wav")},
        )
        assert resp.status_code == 400
        assert resp.json()["error_code"] == "NO_SPEECH_DETECTED"

    # 2. Transcript chỉ có whitespace
    fake_asr_ws = FakeASREngine(return_whitespace_transcript=True)
    app_ws = create_app(asr_engine=fake_asr_ws)
    with TestClient(app_ws) as test_client:
        wait_client_loaded(test_client)
        wav = build_wav_bytes(duration_sec=0.5)
        resp = test_client.post(
            "/api/asr/transcribe",
            files={"file": ("test.wav", io.BytesIO(wav), "audio/wav")},
        )
        assert resp.status_code == 400
        assert resp.json()["error_code"] == "NO_SPEECH_DETECTED"


def test_asr_unexpected_failure() -> None:
    """Lỗi bất ngờ trong quá trình nhận dạng giọng nói trả về 500 ASR_FAILURE (§4.2)."""
    fake_asr = FakeASREngine(raise_unexpected_error=True)
    app = create_app(asr_engine=fake_asr)

    with TestClient(app) as test_client:
        wait_client_loaded(test_client)
        wav = build_wav_bytes(duration_sec=0.5)
        resp = test_client.post(
            "/api/asr/transcribe",
            files={"file": ("test.wav", io.BytesIO(wav), "audio/wav")},
        )
        assert resp.status_code == 500
        assert resp.json()["error_code"] == "ASR_FAILURE"
        assert "traceback" not in resp.text.lower()
