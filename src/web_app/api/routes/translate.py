"""Route POST /api/translate (§4.3)."""

import logging
import time
from fastapi import APIRouter, Request

from src.web_app.api.utils import execute_with_disconnect_monitor
from src.web_app.core.exceptions import (
    AppError,
    InferenceFailedError,
    InputTooLongError,
    InvalidInputError,
    ModelNotFoundError,
    ModelNotReadyError,
    OutputTooLongError,
    UnsupportedDirectionError,
)
from src.web_app.core.language import (
    SUPPORTED_DIRECTIONS,
    normalize_and_trim_text,
)
from src.web_app.core.schemas import (
    TranslateRequest,
    TranslateResponse,
    TranslationModelMetadata,
)
from src.web_app.services.inference_runner import InferenceRunner
from src.web_app.services.supervisor import EngineSupervisor
from src.web_app.services.translation.base import TranslationResult

logger = logging.getLogger("web_app.routes.translate")

router = APIRouter()


@router.post("/translate", response_model=TranslateResponse)
async def translate_text(
    payload: TranslateRequest, request: Request
) -> TranslateResponse:
    """Thực hiện dịch văn bản hai chiều Việt - Tày (§4.3)."""
    settings = request.app.state.settings
    supervisor: EngineSupervisor = request.app.state.supervisor
    runner: InferenceRunner = request.app.state.runner
    request_id = getattr(request.state, "request_id", "unknown-request")

    req_start = time.monotonic()

    # 1. Chuẩn hóa Unicode NFC và trim khoảng trắng hai đầu
    normalized_text = normalize_and_trim_text(payload.text)
    if not normalized_text:
        raise InvalidInputError("Văn bản rỗng sau chuẩn hóa.")

    # 2. Kiểm tra độ dài theo Unicode code point
    text_length = len(normalized_text)
    if text_length > settings.MAX_TEXT_LENGTH:
        raise InputTooLongError(
            "Văn bản vượt quá giới hạn cho phép.",
            detail={
                "current_length": text_length,
                "max_allowed": settings.MAX_TEXT_LENGTH,
                "limit_unit": "code_points",
            },
        )

    # 3. Kiểm tra semantic của direction string
    if payload.direction not in SUPPORTED_DIRECTIONS:
        raise UnsupportedDirectionError(
            f"Chiều dịch không được hỗ trợ: {payload.direction}"
        )

    # 4. Kiểm tra model_id (nếu có cung cấp thì không được là chuỗi rỗng)
    if payload.model_id is not None and not payload.model_id.strip():
        raise InvalidInputError("model_id không được là chuỗi rỗng.")

    # 5. Kiểm tra Engine Readiness
    if not supervisor.is_translation_ready():
        raise ModelNotReadyError(
            "Mô hình hoặc engine dịch chưa sẵn sàng để phục vụ yêu cầu."
        )

    # 6. Kiểm tra chiều dịch được hỗ trợ bởi active engine
    engine = supervisor.translation_engine
    supported_by_engine = engine.get_supported_directions()
    if payload.direction not in supported_by_engine:
        raise UnsupportedDirectionError(
            f"Chiều dịch '{payload.direction}' không có trong bundle đang phục vụ."
        )

    # 7. Kiểm tra model_id khớp với bundle đang phục vụ
    meta = engine.get_metadata()
    bundle_info = engine.get_bundle_info()
    active_id = meta.model_id
    if payload.model_id is not None:
        matches = payload.model_id == active_id or (
            bundle_info is not None and payload.model_id == bundle_info.id
        )
        if not matches:
            raise ModelNotFoundError(
                f"Không tìm thấy mô hình với model_id: {payload.model_id}"
            )

    # 8. Thực thi qua InferenceRunner với Disconnect Monitoring
    def do_translate() -> TranslationResult:
        if supervisor.is_engine_failed("translation"):
            raise ModelNotReadyError("Mô hình hoặc engine dịch chưa sẵn sàng để phục vụ yêu cầu.")
        return engine.translate(normalized_text, payload.direction)

    try:
        runner_result = await execute_with_disconnect_monitor(
            request,
            runner,
            do_translate,
            task_type="translation",
            request_id=request_id,
            model_id=active_id,
            execution_timeout_sec=settings.TRANSLATION_TIMEOUT_SEC,
        )
    except AppError:
        raise
    except Exception as e:
        # Nếu gặp lỗi cạn kiệt tài nguyên / MemoryError thì đánh dấu failed
        if isinstance(e, MemoryError) or "out of memory" in str(e).lower():
            supervisor.mark_translation_failed(f"Fatal resource error: {e}")
        logger.error(
            "Lỗi suy luận dịch văn bản: request_id=%s exc=%s", request_id, e
        )
        raise InferenceFailedError(
            "Suy luận dịch thất bại trong quá trình xử lý."
        ) from e

    res: TranslationResult = runner_result.value
    res_meta = res.model_metadata
    model_metadata = TranslationModelMetadata(
        model_id=res_meta.model_id,
        artifact_id=res_meta.artifact_id,
        checkpoint_version=res_meta.checkpoint_version,
        tokenizer_version=res_meta.tokenizer_version,
        engine_type=res_meta.engine_type,
        is_mock=res_meta.is_mock,
    )

    total_ms = round((time.monotonic() - req_start) * 1000.0, 2)
    logger.info(
        "Thành công POST /api/translate: request_id=%s model_id=%s version=%s total_ms=%.2f queue_ms=%.2f latency_ms=%.2f",
        request_id,
        res_meta.model_id,
        res_meta.checkpoint_version,
        total_ms,
        runner_result.queue_ms,
        runner_result.latency_ms,
    )

    return TranslateResponse(
        status="success",
        translation=res.translation,
        direction=res.direction,
        source_lang=res.source_lang,
        target_lang=res.target_lang,
        model_metadata=model_metadata,
        latency_ms=runner_result.latency_ms,
        queue_ms=runner_result.queue_ms,
    )
