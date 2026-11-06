"""Engine ASR mô phỏng (Mock ASR Engine) theo đặc tả."""

import time
from pathlib import Path
from src.web_app.core.exceptions import ModelNotReadyError, UnsupportedASRLanguageError
from src.web_app.services.asr.base import (
    ASREngine,
    ASRMetadata,
    ASRResult,
    AudioInput,
)


class MockASREngine(ASREngine):
    """Mô phỏng engine nhận dạng giọng nói tiếng Việt mà không cần Whisper thật."""

    def __init__(self, mock_delay_ms: int = 0) -> None:
        self.mock_delay_ms = max(0, mock_delay_ms)
        self._ready = False

    def load(self, model_path: str | Path | None = None) -> None:
        """Nạp tài nguyên giả lập cho mock engine."""
        self._ready = True

    def is_ready(self) -> bool:
        """Kiểm tra mock engine đã sẵn sàng."""
        return self._ready

    def get_metadata(self) -> ASRMetadata:
        """Metadata ASR mô phỏng."""
        return ASRMetadata(
            model_id="mock-asr",
            model_version="mock-v1",
            engine_type="mock",
            is_mock=True,
        )

    def transcribe(self, audio: AudioInput, language: str = "vi") -> ASRResult:
        """Nhận dạng mô phỏng từ AudioInput đã kiểm tra."""
        if not self._ready:
            raise ModelNotReadyError("Engine ASR chưa sẵn sàng để phục vụ yêu cầu.")

        if language != "vi":
            raise UnsupportedASRLanguageError(
                f"Ngôn ngữ nhận dạng '{language}' không được hỗ trợ. Chỉ hỗ trợ tiếng Việt ('vi')."
            )

        if self.mock_delay_ms > 0:
            time.sleep(self.mock_delay_ms / 1000.0)

        transcript = "[MOCK ASR] Đây là transcript mẫu để kiểm thử giao diện."
        return ASRResult(
            transcript=transcript,
            language=language,
            duration_sec=audio.duration_sec,
            model_metadata=self.get_metadata(),
        )

    def unload(self) -> None:
        """Giải phóng trạng thái sẵn sàng."""
        self._ready = False
