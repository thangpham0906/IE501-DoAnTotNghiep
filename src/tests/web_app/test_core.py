"""Unit tests cho module core: language, config, exceptions."""

import math
from pathlib import Path
import pytest
from pydantic import ValidationError

from src.web_app.core.config import REPO_ROOT, WebSettings
from src.web_app.core.exceptions import (
    AppError,
    AudioInvalidError,
    AudioTooLargeError,
    AudioTooLongError,
    AudioUnsupportedFormatError,
    InferenceFailedError,
    InferenceTimeoutError,
    InputTooLongError,
    InternalError,
    InvalidInputError,
    MethodNotAllowedError,
    ModelNotFoundError,
    ModelNotReadyError,
    NoSpeechDetectedError,
    NotFoundError,
    OutputTooLongError,
    RequestTooLargeError,
    ServiceOverloadedError,
    UnsupportedASRLanguageError,
    UnsupportedDirectionError,
)
from src.web_app.core.language import (
    DIRECTION_LANG_MAP,
    SUPPORTED_DIRECTIONS,
    WHITESPACE_CHARS,
    get_language_pair,
    normalize_and_trim_text,
)


class TestLanguageCore:
    """Kiểm tra xử lý ngôn ngữ và hàm normalize_and_trim_text."""

    def test_normalize_empty_or_none_string(self) -> None:
        assert normalize_and_trim_text("") == ""
        assert normalize_and_trim_text("   ") == ""

    def test_normalize_nfc_composition(self) -> None:
        # Chuỗi decomposed (NFD): 'a' + dấu sắc (U+0301)
        decomposed = "á"
        composed = "\xe1"
        assert normalize_and_trim_text(decomposed) == composed

        # Cụm từ tiếng Việt có dấu tổ hợp
        text_nfd = "Việt Nam quê hương tôi, đ\xe1ng sống"
        assert normalize_and_trim_text(text_nfd) == "Việt Nam quê hương tôi, đáng sống"

    def test_trim_all_whitespace_chars_from_spec(self) -> None:
        # Kiểm tra từng ký tự trong WHITESPACE_CHARS
        for ws in WHITESPACE_CHARS:
            padded = f"{ws}Xin chào{ws}"
            assert normalize_and_trim_text(padded) == "Xin chào"

        # Kiểm tra chuỗi chứa nhiều loại whitespace ở đầu và cuối
        mixed_ws = f"\t\r\n\xa0 　Văn bản thử nghiệm    "
        assert normalize_and_trim_text(mixed_ws) == "Văn bản thử nghiệm"

    def test_internal_whitespace_preserved(self) -> None:
        # Khoảng trắng bên trong (spaces, tabs, newlines, ideographic space) phải giữ nguyên
        internal = "Từ thứ nhất\t từ thứ hai\n từ thứ ba　từ thứ tư."
        assert normalize_and_trim_text(f"  {internal}  ") == internal

    def test_non_bmp_characters(self) -> None:
        # Ký tự emoji / non-BMP
        emoji_text = "  🌾 Chào mừng bà con lên nương 🌟  "
        assert normalize_and_trim_text(emoji_text) == "🌾 Chào mừng bà con lên nương 🌟"

    def test_get_language_pair(self) -> None:
        assert get_language_pair("vi-tay") == ("vi", "tyz")
        assert get_language_pair("tay-vi") == ("tyz", "vi")
        with pytest.raises(ValueError, match="Unsupported direction"):
            get_language_pair("en-vi")


class TestConfigCore:
    """Kiểm tra lớp cấu hình WebSettings."""

    def test_default_settings(self) -> None:
        settings = WebSettings()
        assert settings.TRANSLATION_ENGINE_TYPE == "mock"
        assert settings.ASR_ENGINE_TYPE == "mock"
        assert settings.MAX_TEXT_LENGTH == 1000
        assert settings.MAX_JSON_BODY_BYTES == 65536
        assert settings.MAX_AUDIO_FILE_BYTES == 10485760
        assert settings.MAX_MULTIPART_BODY_BYTES == 11534336
        assert settings.MAX_AUDIO_DURATION_SEC == 30
        assert settings.INFERENCE_WORKERS == 1
        assert settings.MAX_QUEUED_INFERENCES == 8
        assert settings.QUEUE_TIMEOUT_SEC == 5.0
        assert settings.TRANSLATION_TIMEOUT_SEC == 15.0
        assert settings.ASR_TIMEOUT_SEC == 20.0
        assert settings.SHUTDOWN_GRACE_SEC == 30.0
        assert settings.MOCK_DELAY_MS == 0

    def test_cross_field_validation_body_bytes(self) -> None:
        # MAX_MULTIPART_BODY_BYTES phải lớn hơn MAX_AUDIO_FILE_BYTES
        with pytest.raises(ValidationError, match="MAX_MULTIPART_BODY_BYTES phải lớn hơn"):
            WebSettings(
                MAX_AUDIO_FILE_BYTES=10000,
                MAX_MULTIPART_BODY_BYTES=10000,
            )

        with pytest.raises(ValidationError, match="MAX_MULTIPART_BODY_BYTES phải lớn hơn"):
            WebSettings(
                MAX_AUDIO_FILE_BYTES=10000,
                MAX_MULTIPART_BODY_BYTES=9999,
            )

    @pytest.mark.parametrize(
        "field_name",
        [
            "QUEUE_TIMEOUT_SEC",
            "TRANSLATION_TIMEOUT_SEC",
            "ASR_TIMEOUT_SEC",
            "SHUTDOWN_GRACE_SEC",
        ],
    )
    def test_timeout_finite_positive_validation(self, field_name: str) -> None:
        # Không chấp nhận số âm, 0, nan, inf
        for invalid_val in [0.0, -1.0, float("nan"), float("inf"), float("-inf")]:
            kwargs = {field_name: invalid_val}
            with pytest.raises(ValidationError):
                WebSettings(**kwargs)

    def test_resolve_path(self) -> None:
        settings = WebSettings()
        assert settings.resolve_path(None) is None
        assert settings.resolve_path("") is None

        rel_path = "models/demo-bundle"
        resolved = settings.resolve_path(rel_path)
        assert resolved == REPO_ROOT / rel_path

        abs_path = Path("/tmp/absolute/path")
        assert settings.resolve_path(abs_path) == abs_path
        assert settings.resolve_path("/tmp/absolute/path") == Path("/tmp/absolute/path")


class TestExceptionsCore:
    """Kiểm tra các Domain Exceptions và mã trạng thái chuẩn."""

    def test_app_error_base(self) -> None:
        err = AppError("Lỗi tùy biến", detail={"info": 123})
        assert err.status_code == 500
        assert err.error_code == "INTERNAL_ERROR"
        assert err.message == "Lỗi tùy biến"
        assert err.detail == {"info": 123}

    def test_inference_timeout_error_phase(self) -> None:
        err_queue = InferenceTimeoutError(phase="queue")
        assert err_queue.status_code == 504
        assert err_queue.error_code == "INFERENCE_TIMEOUT"
        assert err_queue.phase == "queue"
        assert err_queue.detail == {"phase": "queue"}

        err_exec = InferenceTimeoutError(phase="execution", message="Quá hạn thực thi.")
        assert err_exec.phase == "execution"
        assert err_exec.message == "Quá hạn thực thi."
        assert err_exec.detail == {"phase": "execution"}

    def test_error_status_and_codes_mapping(self) -> None:
        cases = [
            (InvalidInputError, 400, "INVALID_INPUT"),
            (UnsupportedDirectionError, 400, "UNSUPPORTED_DIRECTION"),
            (InputTooLongError, 400, "INPUT_TOO_LONG"),
            (RequestTooLargeError, 413, "REQUEST_TOO_LARGE"),
            (AudioTooLargeError, 413, "AUDIO_TOO_LARGE"),
            (AudioTooLongError, 400, "AUDIO_TOO_LONG"),
            (AudioUnsupportedFormatError, 400, "AUDIO_UNSUPPORTED_FORMAT"),
            (AudioInvalidError, 400, "AUDIO_INVALID"),
            (UnsupportedASRLanguageError, 400, "UNSUPPORTED_ASR_LANGUAGE"),
            (NoSpeechDetectedError, 400, "NO_SPEECH_DETECTED"),
            (ModelNotFoundError, 404, "MODEL_NOT_FOUND"),
            (ModelNotReadyError, 503, "MODEL_NOT_READY"),
            (ServiceOverloadedError, 503, "SERVICE_OVERLOADED"),
            (OutputTooLongError, 500, "OUTPUT_TOO_LONG"),
            (InferenceFailedError, 500, "INFERENCE_FAILED"),
            (InternalError, 500, "INTERNAL_ERROR"),
            (NotFoundError, 404, "NOT_FOUND"),
            (MethodNotAllowedError, 405, "METHOD_NOT_ALLOWED"),
        ]
        for exc_cls, expected_status, expected_code in cases:
            inst = exc_cls()
            assert inst.status_code == expected_status
            assert inst.error_code == expected_code
