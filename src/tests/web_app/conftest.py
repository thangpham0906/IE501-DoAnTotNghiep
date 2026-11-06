"""Fixtures và Fake Engines phục vụ kiểm thử tích hợp Web Demo."""

import threading
from pathlib import Path
from typing import Any
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
import httpx

from src.web_app.core.config import WebSettings
from src.web_app.core.exceptions import ModelNotReadyError, OutputTooLongError
from src.web_app.main import create_app
from src.web_app.services.asr.base import (
    ASREngine,
    ASRMetadata,
    ASRResult,
    AudioInput,
)
from src.web_app.services.translation.base import (
    BundleModelInfo,
    InferenceEngine,
    TranslationMetadata,
    TranslationResult,
)


class FakeTranslationEngine(InferenceEngine):
    """Engine dịch giả lập dùng threading.Event kiểm soát tiến trình thực thi."""

    def __init__(
        self,
        *,
        supported_directions: list[str] | None = None,
        model_id: str = "fake-model",
        is_mock: bool = True,
        load_event: threading.Event | None = None,
        block_load: bool = False,
        start_event: threading.Event | None = None,
        release_event: threading.Event | None = None,
        raise_output_too_long: bool = False,
        raise_unexpected_error: bool = False,
        raise_memory_error: bool = False,
    ) -> None:
        self._supported_directions = (
            supported_directions
            if supported_directions is not None
            else ["vi-tay", "tay-vi"]
        )
        self._model_id = model_id
        self._is_mock = is_mock
        self._load_event = load_event
        self._block_load = block_load
        self._start_event = start_event
        self._release_event = release_event
        self._raise_output_too_long = raise_output_too_long
        self._raise_unexpected_error = raise_unexpected_error
        self._raise_memory_error = raise_memory_error
        self._ready = False
        self.unloaded = False

    def load(self, bundle_path: str | Path | None = None) -> None:
        if self._load_event:
            self._load_event.wait()
        if self._block_load:
            return
        self._ready = True

    def is_ready(self) -> bool:
        return self._ready

    def get_supported_directions(self) -> list[str]:
        return self._supported_directions if self._ready else []

    def get_metadata(self) -> TranslationMetadata:
        return TranslationMetadata(
            model_id=self._model_id,
            artifact_id="fake-artifact",
            checkpoint_version="fake-v1",
            tokenizer_version="fake-v1",
            engine_type="mock" if self._is_mock else "pipeline",
            is_mock=self._is_mock,
        )

    def get_bundle_info(self) -> BundleModelInfo | None:
        if not self._ready:
            return None
        return BundleModelInfo(
            id=self._model_id,
            name="Fake Translation Model",
            bundle_version="fake-v1",
            engine_type="mock" if self._is_mock else "pipeline",
            is_mock=self._is_mock,
            supported_directions=self.get_supported_directions(),
            is_default=True,
            metrics=None,
        )

    def translate(self, text: str, direction: str) -> TranslationResult:
        if not self._ready:
            raise ModelNotReadyError("Engine chưa sẵn sàng.")
        if self._start_event:
            self._start_event.set()
        if self._release_event:
            self._release_event.wait()

        if self._raise_output_too_long:
            raise OutputTooLongError("Output sequence reached token limit.")
        if self._raise_memory_error:
            raise MemoryError("CUDA out of memory simulation")
        if self._raise_unexpected_error:
            raise RuntimeError("Fatal runtime failure inside translation engine")

        return TranslationResult(
            translation=f"[FAKE {direction}] {text}",
            direction=direction,
            source_lang="vi" if direction == "vi-tay" else "tyz",
            target_lang="tyz" if direction == "vi-tay" else "vi",
            model_metadata=self.get_metadata(),
        )

    def unload(self) -> None:
        self._ready = False
        self.unloaded = True


class FakeASREngine(ASREngine):
    """Engine ASR giả lập dùng threading.Event kiểm soát tiến trình thực thi."""

    def __init__(
        self,
        *,
        model_id: str = "fake-asr",
        is_mock: bool = True,
        load_event: threading.Event | None = None,
        block_load: bool = False,
        start_event: threading.Event | None = None,
        release_event: threading.Event | None = None,
        return_empty_transcript: bool = False,
        return_whitespace_transcript: bool = False,
        raise_unexpected_error: bool = False,
        raise_memory_error: bool = False,
    ) -> None:
        self._model_id = model_id
        self._is_mock = is_mock
        self._load_event = load_event
        self._block_load = block_load
        self._start_event = start_event
        self._release_event = release_event
        self._return_empty_transcript = return_empty_transcript
        self._return_whitespace_transcript = return_whitespace_transcript
        self._raise_unexpected_error = raise_unexpected_error
        self._raise_memory_error = raise_memory_error
        self._ready = False
        self.unloaded = False

    def load(self, model_path: str | Path | None = None) -> None:
        if self._load_event:
            self._load_event.wait()
        if self._block_load:
            return
        self._ready = True

    def is_ready(self) -> bool:
        return self._ready

    def get_metadata(self) -> ASRMetadata:
        return ASRMetadata(
            model_id=self._model_id,
            model_version="fake-v1",
            engine_type="mock" if self._is_mock else "whisper",
            is_mock=self._is_mock,
        )

    def transcribe(self, audio: AudioInput, language: str = "vi") -> ASRResult:
        if not self._ready:
            raise ModelNotReadyError("ASR Engine chưa sẵn sàng.")
        if self._start_event:
            self._start_event.set()
        if self._release_event:
            self._release_event.wait()

        if self._raise_memory_error:
            raise MemoryError("Out of VRAM during ASR")
        if self._raise_unexpected_error:
            raise RuntimeError("Fatal whisper crash")

        if self._return_empty_transcript:
            transcript = ""
        elif self._return_whitespace_transcript:
            transcript = "   \n\t  "
        else:
            transcript = "[FAKE ASR] Nhận dạng thành công tiếng Việt."

        return ASRResult(
            transcript=transcript,
            language=language,
            duration_sec=audio.duration_sec,
            model_metadata=self.get_metadata(),
        )

    def unload(self) -> None:
        self._ready = False
        self.unloaded = True


@pytest.fixture
def default_settings() -> WebSettings:
    """Settings mặc định cho test nhanh."""
    return WebSettings(
        TRANSLATION_ENGINE_TYPE="mock",
        ASR_ENGINE_TYPE="mock",
        MOCK_DELAY_MS=0,
        QUEUE_TIMEOUT_SEC=1.0,
        TRANSLATION_TIMEOUT_SEC=2.0,
        ASR_TIMEOUT_SEC=2.0,
        SHUTDOWN_GRACE_SEC=2.0,
    )


@pytest.fixture
def test_app(default_settings: WebSettings) -> FastAPI:
    """Tạo ứng dụng test với mock engines."""
    return create_app(settings=default_settings)


def wait_client_loaded(client: TestClient) -> None:
    """Đợi quá trình nạp engine bất đồng bộ hoàn tất trong event loop của TestClient (C15)."""
    supervisor = getattr(client.app.state, "supervisor", None)
    if supervisor is not None and hasattr(client, "portal") and client.portal is not None:
        client.portal.call(supervisor.wait_loaded)


@pytest.fixture
def client(test_app: FastAPI):
    """TestClient chạy trọn vẹn lifespan startup và shutdown, đảm bảo đợi engine nạp xong (C15)."""
    with TestClient(test_app) as c:
        wait_client_loaded(c)
        yield c
