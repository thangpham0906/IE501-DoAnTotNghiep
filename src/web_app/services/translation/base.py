"""Giao diện trừu tượng và kiểu dữ liệu cho Engine dịch máy."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


@dataclass(slots=True, frozen=True)
class TranslationMetadata:
    """Metadata mô tả mô hình / bundle dịch."""

    model_id: str
    artifact_id: str
    checkpoint_version: str
    tokenizer_version: str
    engine_type: str
    is_mock: bool


@dataclass(slots=True, frozen=True)
class TranslationResult:
    """Kết quả suy luận dịch máy."""

    translation: str
    direction: str
    source_lang: str
    target_lang: str
    model_metadata: TranslationMetadata


@dataclass(slots=True, frozen=True)
class BundleModelInfo:
    """Thông tin bundle mô hình phục vụ endpoint GET /api/models."""

    id: str
    name: str
    bundle_version: str
    engine_type: str
    is_mock: bool
    supported_directions: list[str]
    is_default: bool = True
    metrics: dict[str, Any] | None = None


@runtime_checkable
class InferenceEngine(Protocol):
    """Hợp đồng giao diện cho InferenceEngine theo mục 3.2 của đặc tả."""

    def load(self, bundle_path: str | Path | None = None) -> None:
        """Nạp bundle/mô hình phục vụ suy luận."""
        ...

    def is_ready(self) -> bool:
        """Kiểm tra engine đã nạp và sẵn sàng phục vụ chưa."""
        ...

    def get_supported_directions(self) -> list[str]:
        """Danh sách các chiều dịch thực sự phục vụ được."""
        ...

    def translate(self, text: str, direction: str) -> TranslationResult:
        """Thực hiện suy luận dịch từ chuỗi đã chuẩn hóa."""
        ...

    def get_metadata(self) -> TranslationMetadata:
        """Trả về metadata định danh mô hình/bundle đang phục vụ."""
        ...

    def get_bundle_info(self) -> BundleModelInfo | None:
        """Trả về thông tin bundle công bố cho GET /api/models (nếu có)."""
        ...

    def unload(self) -> None:
        """Giải phóng tài nguyên của engine."""
        ...
