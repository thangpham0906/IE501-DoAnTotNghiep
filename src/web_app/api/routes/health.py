"""Route GET /api/health (§4.5)."""

from fastapi import APIRouter, Request

from src.web_app.core.schemas import (
    ASRHealthInfo,
    HealthResponse,
    LimitsHealthInfo,
    TranslationHealthInfo,
)
from src.web_app.services.supervisor import EngineSupervisor

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def get_health(request: Request) -> HealthResponse:
    """Trả về trạng thái sẵn sàng của hệ thống và các engine suy luận (§4.5)."""
    supervisor: EngineSupervisor = request.app.state.supervisor
    settings = request.app.state.settings

    # Trạng thái dịch đọc từ snapshot an toàn
    t_ready = supervisor.is_translation_ready()
    t_model_id = (
        supervisor._validated_translation_meta.model_id
        if (t_ready and supervisor._validated_translation_meta)
        else None
    )
    t_directions = (
        supervisor._validated_translation_directions if t_ready else []
    )

    translation_info = TranslationHealthInfo(
        state=supervisor.translation_state,
        engine_type=supervisor._translation_engine_type,
        is_mock=supervisor._translation_is_mock,
        active_model_id=t_model_id,
        supported_directions=t_directions,
    )

    # Trạng thái ASR đọc từ snapshot an toàn
    asr_ready = supervisor.is_asr_ready()
    asr_model_id = (
        supervisor._validated_asr_meta.model_id
        if (asr_ready and supervisor._validated_asr_meta)
        else None
    )
    supported_languages = ["vi"] if asr_ready else []

    asr_info = ASRHealthInfo(
        state=supervisor.asr_state,
        engine_type=supervisor._asr_engine_type,
        is_mock=supervisor._asr_is_mock,
        model_id=asr_model_id,
        supported_languages=supported_languages,
    )

    # Hạn mức hệ thống
    limits_info = LimitsHealthInfo(
        max_text_length=settings.MAX_TEXT_LENGTH,
        max_audio_file_bytes=settings.MAX_AUDIO_FILE_BYTES,
        max_audio_duration_sec=settings.MAX_AUDIO_DURATION_SEC,
        queue_timeout_sec=settings.QUEUE_TIMEOUT_SEC,
        translation_timeout_sec=settings.TRANSLATION_TIMEOUT_SEC,
        asr_timeout_sec=settings.ASR_TIMEOUT_SEC,
        audio_format="wav_pcm_s16le",
        audio_sample_rate_hz=16000,
        audio_channels=1,
    )

    return HealthResponse(
        status=supervisor.get_overall_status(),
        api_version="1",
        translation=translation_info,
        asr=asr_info,
        limits=limits_info,
    )
