"""Factory tạo ASR Engine theo cấu hình WebSettings."""

from pathlib import Path
from src.web_app.core.config import WebSettings
from src.web_app.core.exceptions import ModelNotReadyError
from src.web_app.services.asr.base import (
    ASREngine,
    ASRMetadata,
    ASRResult,
    AudioInput,
)
from src.web_app.services.asr.mock import MockASREngine


class UnavailableASREngine(ASREngine):
    """Engine đại diện cho cấu hình Whisper khi chưa có weights/artifact thật."""

    def __init__(self, reason: str = "Whisper ASR engine chưa có weights/artifact khả dụng.") -> None:
        self.reason = reason

    def load(self, model_path: str | Path | None = None) -> None:
        """Báo lỗi khi được yêu cầu nạp mô hình chưa sẵn sàng."""
        raise ModelNotReadyError(self.reason)

    def is_ready(self) -> bool:
        """Luôn trả False vì chưa sẵn sàng."""
        return False

    def get_metadata(self) -> ASRMetadata:
        """Metadata phản ánh loại engine whisper nhưng chưa có weights."""
        return ASRMetadata(
            model_id="whisper-unavailable",
            model_version="none",
            engine_type="whisper",
            is_mock=False,
        )

    def transcribe(self, audio: AudioInput, language: str = "vi") -> ASRResult:
        """Từ chối nhận dạng khi chưa sẵn sàng."""
        raise ModelNotReadyError(self.reason)

    def unload(self) -> None:
        """Không cần dọn tài nguyên."""
        pass


def create_asr_engine(settings: WebSettings) -> ASREngine | None:
    """Tạo ASR Engine dựa trên cấu hình WebSettings.

    Factory không thực hiện load() blocking. Trả về None nếu ASR_ENGINE_TYPE="disabled".
    """
    if settings.ASR_ENGINE_TYPE == "disabled":
        return None
    if settings.ASR_ENGINE_TYPE == "mock":
        return MockASREngine(mock_delay_ms=settings.MOCK_DELAY_MS)
    if settings.ASR_ENGINE_TYPE == "whisper":
        return UnavailableASREngine()
    raise ValueError(f"Không hỗ trợ ASR_ENGINE_TYPE: {settings.ASR_ENGINE_TYPE}")
