"""Dịch vụ nhận dạng giọng nói (ASR Service)."""

from src.web_app.services.asr.audio import validate_wav
from src.web_app.services.asr.base import (
    ASREngine,
    ASRMetadata,
    ASRResult,
    AudioInput,
)
from src.web_app.services.asr.factory import (
    UnavailableASREngine,
    create_asr_engine,
)
from src.web_app.services.asr.mock import MockASREngine

__all__ = [
    "ASREngine",
    "ASRMetadata",
    "ASRResult",
    "AudioInput",
    "MockASREngine",
    "UnavailableASREngine",
    "create_asr_engine",
    "validate_wav",
]
