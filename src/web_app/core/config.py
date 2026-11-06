"""Cấu hình ứng dụng Web Demo dịch máy Việt - Tày."""

import math
from pathlib import Path
from typing import Literal
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class WebSettings(BaseSettings):
    """Cấu hình vận hành và giới hạn tài nguyên của Web Demo."""

    # Engine dịch
    TRANSLATION_ENGINE_TYPE: Literal["mock", "pipeline"] = "mock"
    MODEL_BUNDLE_PATH: str | None = None
    MODEL_DEVICE: Literal["cpu", "cuda"] = "cpu"

    # Engine ASR
    ASR_ENGINE_TYPE: Literal["mock", "whisper", "disabled"] = "mock"
    WHISPER_MODEL_PATH: str | None = None
    ASR_DEVICE: Literal["cpu", "cuda"] = "cpu"

    # Giới hạn dữ liệu đầu vào
    MAX_TEXT_LENGTH: int = Field(default=1000, gt=0)
    MAX_JSON_BODY_BYTES: int = Field(default=65536, gt=0)
    MAX_AUDIO_FILE_BYTES: int = Field(default=10485760, gt=0)  # 10 MiB
    MAX_MULTIPART_BODY_BYTES: int = Field(default=11534336, gt=0)  # 11 MiB
    MAX_AUDIO_DURATION_SEC: int = Field(default=30, gt=0)

    # Quản lý hàng đợi và worker
    INFERENCE_WORKERS: int = Field(default=1, gt=0)
    MAX_QUEUED_INFERENCES: int = Field(default=8, gt=0)
    QUEUE_TIMEOUT_SEC: float = Field(default=5.0, gt=0)
    TRANSLATION_TIMEOUT_SEC: float = Field(default=15.0, gt=0)
    ASR_TIMEOUT_SEC: float = Field(default=20.0, gt=0)
    SHUTDOWN_GRACE_SEC: float = Field(default=30.0, gt=0)

    # Chế độ mô phỏng / kiểm thử
    MOCK_DELAY_MS: int = Field(default=0, ge=0)

    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator(
        "QUEUE_TIMEOUT_SEC",
        "TRANSLATION_TIMEOUT_SEC",
        "ASR_TIMEOUT_SEC",
        "SHUTDOWN_GRACE_SEC",
        mode="after",
    )
    @classmethod
    def validate_finite_positive_float(cls, v: float) -> float:
        if not math.isfinite(v) or v <= 0:
            raise ValueError(f"Giá trị thời gian chờ phải là số thực hữu hạn và lớn hơn 0 (nhận {v}).")
        return v

    @model_validator(mode="after")
    def validate_cross_field_rules(self) -> "WebSettings":
        if self.MAX_MULTIPART_BODY_BYTES <= self.MAX_AUDIO_FILE_BYTES:
            raise ValueError(
                "MAX_MULTIPART_BODY_BYTES phải lớn hơn MAX_AUDIO_FILE_BYTES để đủ chỗ cho overhead form."
            )
        return self

    def resolve_path(self, path_str: str | Path | None) -> Path | None:
        """Resolve đường dẫn tương đối theo gốc repo."""
        if not path_str:
            return None
        p = Path(path_str)
        if p.is_absolute():
            return p
        return REPO_ROOT / p


# Singleton mặc định cho ứng dụng
settings = WebSettings()
