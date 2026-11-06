"""Factory tạo Translation Engine theo cấu hình WebSettings."""

from pathlib import Path
from src.web_app.core.config import WebSettings
from src.web_app.core.exceptions import ModelNotReadyError
from src.web_app.services.translation.base import (
    BundleModelInfo,
    InferenceEngine,
    TranslationMetadata,
    TranslationResult,
)
from src.web_app.services.translation.mock import MockTranslationEngine


class UnavailableTranslationEngine(InferenceEngine):
    """Engine đại diện cho cấu hình pipeline khi chưa có artifact/adapter thật."""

    def __init__(self, reason: str = "Pipeline translation engine chưa có artifact/adapter khả dụng.") -> None:
        self.reason = reason

    def load(self, bundle_path: str | Path | None = None) -> None:
        """Báo lỗi khi được yêu cầu nạp artifact chưa sẵn sàng."""
        raise ModelNotReadyError(self.reason)

    def is_ready(self) -> bool:
        """Luôn trả False vì chưa sẵn sàng."""
        return False

    def get_supported_directions(self) -> list[str]:
        """Không hỗ trợ chiều dịch nào khi chưa nạp thành công."""
        return []

    def get_metadata(self) -> TranslationMetadata:
        """Metadata phản ánh loại engine pipeline nhưng chưa có artifact."""
        return TranslationMetadata(
            model_id="pipeline-unavailable",
            artifact_id="none",
            checkpoint_version="none",
            tokenizer_version="none",
            engine_type="pipeline",
            is_mock=False,
        )

    def get_bundle_info(self) -> BundleModelInfo | None:
        """Không trả thông tin bundle khi chưa sẵn sàng."""
        return None

    def translate(self, text: str, direction: str) -> TranslationResult:
        """Từ chối dịch khi chưa sẵn sàng."""
        raise ModelNotReadyError(self.reason)

    def unload(self) -> None:
        """Không cần dọn tài nguyên."""
        pass


def create_translation_engine(settings: WebSettings) -> InferenceEngine:
    """Tạo Translation Engine dựa trên cấu hình WebSettings.

    Factory không thực hiện load() blocking.
    """
    if settings.TRANSLATION_ENGINE_TYPE == "mock":
        return MockTranslationEngine(mock_delay_ms=settings.MOCK_DELAY_MS)
    if settings.TRANSLATION_ENGINE_TYPE == "pipeline":
        return UnavailableTranslationEngine()
    raise ValueError(f"Không hỗ trợ TRANSLATION_ENGINE_TYPE: {settings.TRANSLATION_ENGINE_TYPE}")
