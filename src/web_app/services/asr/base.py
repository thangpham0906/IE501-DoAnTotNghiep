"""Giao diện trừu tượng và kiểu dữ liệu cho Engine ASR."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass(slots=True, frozen=True)
class AudioInput:
    """Dữ liệu âm thanh PCM đã được kiểm tra tính hợp lệ và chuẩn hóa."""

    pcm_bytes: bytes
    sample_rate_hz: int
    channels: int
    frame_count: int
    duration_sec: float


@dataclass(slots=True, frozen=True)
class ASRMetadata:
    """Metadata mô tả mô hình / engine ASR."""

    model_id: str
    model_version: str
    engine_type: str
    is_mock: bool


@dataclass(slots=True, frozen=True)
class ASRResult:
    """Kết quả nhận dạng tiếng nói (ASR)."""

    transcript: str
    language: str
    duration_sec: float
    model_metadata: ASRMetadata


@runtime_checkable
class ASREngine(Protocol):
    """Hợp đồng giao diện cho ASREngine theo mục 3.3 của đặc tả."""

    def load(self, model_path: str | Path | None = None) -> None:
        """Nạp tài nguyên mô hình ASR."""
        ...

    def is_ready(self) -> bool:
        """Kiểm tra engine ASR đã sẵn sàng phục vụ chưa."""
        ...

    def get_metadata(self) -> ASRMetadata:
        """Trả về metadata định danh mô hình ASR đang phục vụ."""
        ...

    def transcribe(self, audio: AudioInput, language: str = "vi") -> ASRResult:
        """Thực hiện nhận dạng giọng nói từ AudioInput (chỉ hỗ trợ tiếng Việt 'vi')."""
        ...

    def unload(self) -> None:
        """Giải phóng tài nguyên của engine ASR."""
        ...
