"""Pydantic schemas cho API Request/Response và ErrorResponse."""

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class ErrorResponse(BaseModel):
    """Cấu trúc phản hồi lỗi chuẩn tắc của toàn bộ API Web Demo (§4.2)."""

    status: Literal["error"] = "error"
    error_code: str
    message: str
    detail: dict[str, Any] | None = None
    request_id: str


class TranslateRequest(BaseModel):
    """Request body cho POST /api/translate (§4.3)."""

    model_config = ConfigDict(extra="forbid")

    text: str
    direction: str
    model_id: str | None = None


class TranslationModelMetadata(BaseModel):
    """Metadata mô hình dịch đính kèm kết quả (§4.3)."""

    model_id: str
    artifact_id: str
    checkpoint_version: str
    tokenizer_version: str
    engine_type: str
    is_mock: bool


class TranslateResponse(BaseModel):
    """Response body cho POST /api/translate (§4.3)."""

    status: Literal["success"] = "success"
    translation: str
    direction: str
    source_lang: str
    target_lang: str
    model_metadata: TranslationModelMetadata
    latency_ms: float
    queue_ms: float


class ASRModelMetadata(BaseModel):
    """Metadata mô hình ASR đính kèm kết quả (§4.4)."""

    model_id: str
    model_version: str
    engine_type: str
    is_mock: bool


class TranscribeResponse(BaseModel):
    """Response body cho POST /api/asr/transcribe (§4.4)."""

    status: Literal["success"] = "success"
    transcript: str
    language: str
    duration_sec: float
    model_metadata: ASRModelMetadata
    latency_ms: float
    queue_ms: float
    disclaimer: str = (
        "Thử nghiệm giọng nói tiếng Việt. Ứng dụng không hỗ trợ nhận dạng tiếng Tày."
    )


class TranslationHealthInfo(BaseModel):
    """Trạng thái engine dịch trong GET /api/health (§4.5)."""

    state: Literal["ready", "loading", "failed", "stopping"]
    engine_type: str
    is_mock: bool
    active_model_id: str | None
    supported_directions: list[str]


class ASRHealthInfo(BaseModel):
    """Trạng thái engine ASR trong GET /api/health (§4.5)."""

    state: Literal["ready", "loading", "failed", "disabled", "stopping"]
    engine_type: str
    is_mock: bool
    model_id: str | None
    supported_languages: list[str]


class LimitsHealthInfo(BaseModel):
    """Hạn mức vận hành công bố qua GET /api/health (§4.5)."""

    max_text_length: int
    max_audio_file_bytes: int
    max_audio_duration_sec: int
    queue_timeout_sec: float
    translation_timeout_sec: float
    asr_timeout_sec: float
    audio_format: str = "wav_pcm_s16le"
    audio_sample_rate_hz: int = 16000
    audio_channels: int = 1


class HealthResponse(BaseModel):
    """Response body cho GET /api/health (§4.5)."""

    status: Literal["ready", "loading", "degraded"]
    api_version: str = "1"
    translation: TranslationHealthInfo
    asr: ASRHealthInfo
    limits: LimitsHealthInfo


class ModelItem(BaseModel):
    """Thông tin bundle mô hình trong GET /api/models (§4.6)."""

    id: str
    name: str
    bundle_version: str
    engine_type: str
    is_mock: bool
    supported_directions: list[str]
    is_default: bool = True
    metrics: dict[str, Any] | None = None


class ModelsResponse(BaseModel):
    """Response body cho GET /api/models (§4.6)."""

    models: list[ModelItem]
