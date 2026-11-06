"""Dịch vụ dịch máy (Translation Service)."""

from src.web_app.services.translation.base import (
    BundleModelInfo,
    InferenceEngine,
    TranslationMetadata,
    TranslationResult,
)
from src.web_app.services.translation.factory import (
    UnavailableTranslationEngine,
    create_translation_engine,
)
from src.web_app.services.translation.mock import MockTranslationEngine

__all__ = [
    "BundleModelInfo",
    "InferenceEngine",
    "MockTranslationEngine",
    "TranslationMetadata",
    "TranslationResult",
    "UnavailableTranslationEngine",
    "create_translation_engine",
]
