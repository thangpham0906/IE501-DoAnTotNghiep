"""Engine dịch mô phỏng (Mock Translation Engine) theo đặc tả."""

import time
from pathlib import Path
from src.web_app.core.exceptions import ModelNotReadyError, UnsupportedDirectionError
from src.web_app.services.translation.base import (
    BundleModelInfo,
    InferenceEngine,
    TranslationMetadata,
    TranslationResult,
)


class MockTranslationEngine(InferenceEngine):
    """Mô phỏng engine dịch hai chiều Việt - Tày mà không nạp mô hình thật."""

    def __init__(self, mock_delay_ms: int = 0) -> None:
        self.mock_delay_ms = max(0, mock_delay_ms)
        self._ready = False

    def load(self, bundle_path: str | Path | None = None) -> None:
        """Nạp tài nguyên giả lập cho mock engine."""
        self._ready = True

    def is_ready(self) -> bool:
        """Kiểm tra mock engine đã sẵn sàng."""
        return self._ready

    def get_supported_directions(self) -> list[str]:
        """Danh sách chiều dịch hỗ trợ khi đã ready."""
        if not self._ready:
            return []
        return ["vi-tay", "tay-vi"]

    def get_metadata(self) -> TranslationMetadata:
        """Metadata mô phỏng cố định."""
        return TranslationMetadata(
            model_id="mock-demo",
            artifact_id="mock-text",
            checkpoint_version="mock-v1",
            tokenizer_version="mock-v1",
            engine_type="mock",
            is_mock=True,
        )

    def get_bundle_info(self) -> BundleModelInfo:
        """Thông tin bundle phục vụ GET /api/models."""
        return BundleModelInfo(
            id="mock-demo",
            name="Mô phỏng dịch văn bản",
            bundle_version="mock-v1",
            engine_type="mock",
            is_mock=True,
            supported_directions=["vi-tay", "tay-vi"],
            is_default=True,
            metrics=None,
        )

    def translate(self, text: str, direction: str) -> TranslationResult:
        """Thực hiện dịch mô phỏng với tiền tố cố định."""
        if not self._ready:
            raise ModelNotReadyError("Engine dịch chưa sẵn sàng để phục vụ yêu cầu.")

        if direction not in ("vi-tay", "tay-vi"):
            raise UnsupportedDirectionError(
                f"Chiều dịch '{direction}' không được hỗ trợ bởi bundle hiện tại."
            )

        if self.mock_delay_ms > 0:
            time.sleep(self.mock_delay_ms / 1000.0)

        if direction == "vi-tay":
            prefix = "[MOCK vi->tyz] "
            source_lang = "vi"
            target_lang = "tyz"
        else:
            prefix = "[MOCK tyz->vi] "
            source_lang = "tyz"
            target_lang = "vi"

        translation = f"{prefix}{text}"
        return TranslationResult(
            translation=translation,
            direction=direction,
            source_lang=source_lang,
            target_lang=target_lang,
            model_metadata=self.get_metadata(),
        )

    def unload(self) -> None:
        """Giải phóng trạng thái sẵn sàng."""
        self._ready = False
