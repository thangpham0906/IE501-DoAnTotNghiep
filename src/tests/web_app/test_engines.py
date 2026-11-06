"""Unit tests cho các engine dịch, ASR và factory."""

import time
import pytest

from src.web_app.core.config import WebSettings
from src.web_app.core.exceptions import (
    ModelNotReadyError,
    UnsupportedASRLanguageError,
    UnsupportedDirectionError,
)
from src.web_app.services.asr.base import AudioInput
from src.web_app.services.asr.factory import (
    UnavailableASREngine,
    create_asr_engine,
)
from src.web_app.services.asr.mock import MockASREngine
from src.web_app.services.translation.factory import (
    UnavailableTranslationEngine,
    create_translation_engine,
)
from src.web_app.services.translation.mock import MockTranslationEngine


class TestTranslationEngines:
    """Kiểm thử MockTranslationEngine và UnavailableTranslationEngine."""

    def test_mock_translation_lifecycle(self) -> None:
        engine = MockTranslationEngine()
        assert not engine.is_ready()
        assert engine.get_supported_directions() == []

        # Thử dịch khi chưa load -> ModelNotReadyError
        with pytest.raises(ModelNotReadyError):
            engine.translate("Xin chào", "vi-tay")

        # Load engine
        engine.load()
        assert engine.is_ready()
        assert engine.get_supported_directions() == ["vi-tay", "tay-vi"]

        # Unload
        engine.unload()
        assert not engine.is_ready()
        assert engine.get_supported_directions() == []

    def test_mock_translation_two_directions(self) -> None:
        engine = MockTranslationEngine()
        engine.load()

        # Chiều vi -> tay
        res_vi_tay = engine.translate("Hôm nay đi nương.", "vi-tay")
        assert res_vi_tay.translation == "[MOCK vi->tyz] Hôm nay đi nương."
        assert res_vi_tay.direction == "vi-tay"
        assert res_vi_tay.source_lang == "vi"
        assert res_vi_tay.target_lang == "tyz"
        assert res_vi_tay.model_metadata.is_mock is True
        assert res_vi_tay.model_metadata.model_id == "mock-demo"
        assert res_vi_tay.model_metadata.checkpoint_version == "mock-v1"

        # Chiều tay -> vi
        res_tay_vi = engine.translate("Báu khửn đông.", "tay-vi")
        assert res_tay_vi.translation == "[MOCK tyz->vi] Báu khửn đông."
        assert res_tay_vi.direction == "tay-vi"
        assert res_tay_vi.source_lang == "tyz"
        assert res_tay_vi.target_lang == "vi"

    def test_mock_translation_unsupported_direction(self) -> None:
        engine = MockTranslationEngine()
        engine.load()
        with pytest.raises(UnsupportedDirectionError):
            engine.translate("Hello", "en-vi")

    def test_mock_translation_delay(self) -> None:
        engine = MockTranslationEngine(mock_delay_ms=30)
        engine.load()
        start = time.perf_counter()
        engine.translate("Test delay", "vi-tay")
        elapsed = time.perf_counter() - start
        assert elapsed >= 0.025

    def test_mock_translation_bundle_info(self) -> None:
        engine = MockTranslationEngine()
        info = engine.get_bundle_info()
        assert info.id == "mock-demo"
        assert info.is_mock is True
        assert info.metrics is None
        assert info.supported_directions == ["vi-tay", "tay-vi"]

    def test_unavailable_translation_engine(self) -> None:
        engine = UnavailableTranslationEngine()
        assert not engine.is_ready()
        assert engine.get_supported_directions() == []
        assert engine.get_bundle_info() is None
        assert engine.get_metadata().engine_type == "pipeline"
        assert engine.get_metadata().is_mock is False

        with pytest.raises(ModelNotReadyError):
            engine.load()

        with pytest.raises(ModelNotReadyError):
            engine.translate("Xin chào", "vi-tay")

    def test_create_translation_engine_factory(self) -> None:
        settings_mock = WebSettings(TRANSLATION_ENGINE_TYPE="mock")
        engine_mock = create_translation_engine(settings_mock)
        assert isinstance(engine_mock, MockTranslationEngine)
        assert not engine_mock.is_ready()  # Factory không thực hiện load()

        settings_pipeline = WebSettings(TRANSLATION_ENGINE_TYPE="pipeline")
        engine_pipeline = create_translation_engine(settings_pipeline)
        assert isinstance(engine_pipeline, UnavailableTranslationEngine)


class TestASREngines:
    """Kiểm thử MockASREngine, UnavailableASREngine và factory."""

    @pytest.fixture
    def sample_audio(self) -> AudioInput:
        return AudioInput(
            pcm_bytes=b"\x00" * 32000,
            sample_rate_hz=16000,
            channels=1,
            frame_count=16000,
            duration_sec=1.0,
        )

    def test_mock_asr_lifecycle(self, sample_audio: AudioInput) -> None:
        engine = MockASREngine()
        assert not engine.is_ready()

        with pytest.raises(ModelNotReadyError):
            engine.transcribe(sample_audio, language="vi")

        engine.load()
        assert engine.is_ready()

        engine.unload()
        assert not engine.is_ready()

    def test_mock_asr_transcribe(self, sample_audio: AudioInput) -> None:
        engine = MockASREngine()
        engine.load()

        res = engine.transcribe(sample_audio, language="vi")
        assert res.transcript.startswith("[MOCK ASR]")
        assert res.language == "vi"
        assert res.duration_sec == 1.0
        assert res.model_metadata.is_mock is True
        assert res.model_metadata.engine_type == "mock"

    def test_mock_asr_unsupported_language(self, sample_audio: AudioInput) -> None:
        engine = MockASREngine()
        engine.load()

        with pytest.raises(UnsupportedASRLanguageError):
            engine.transcribe(sample_audio, language="en")

        with pytest.raises(UnsupportedASRLanguageError):
            engine.transcribe(sample_audio, language="tyz")

    def test_mock_asr_delay(self, sample_audio: AudioInput) -> None:
        engine = MockASREngine(mock_delay_ms=30)
        engine.load()
        start = time.perf_counter()
        engine.transcribe(sample_audio, language="vi")
        elapsed = time.perf_counter() - start
        assert elapsed >= 0.025

    def test_unavailable_asr_engine(self, sample_audio: AudioInput) -> None:
        engine = UnavailableASREngine()
        assert not engine.is_ready()
        assert engine.get_metadata().engine_type == "whisper"
        assert engine.get_metadata().is_mock is False

        with pytest.raises(ModelNotReadyError):
            engine.load()

        with pytest.raises(ModelNotReadyError):
            engine.transcribe(sample_audio, language="vi")

    def test_create_asr_engine_factory(self) -> None:
        # ASR disabled
        settings_disabled = WebSettings(ASR_ENGINE_TYPE="disabled")
        assert create_asr_engine(settings_disabled) is None

        # ASR mock
        settings_mock = WebSettings(ASR_ENGINE_TYPE="mock")
        engine_mock = create_asr_engine(settings_mock)
        assert isinstance(engine_mock, MockASREngine)
        assert not engine_mock.is_ready()

        # ASR whisper
        settings_whisper = WebSettings(ASR_ENGINE_TYPE="whisper")
        engine_whisper = create_asr_engine(settings_whisper)
        assert isinstance(engine_whisper, UnavailableASREngine)
