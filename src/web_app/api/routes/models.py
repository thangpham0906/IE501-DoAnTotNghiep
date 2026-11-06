"""Route GET /api/models (§4.6)."""

from fastapi import APIRouter, Request

from src.web_app.core.schemas import ModelItem, ModelsResponse
from src.web_app.services.supervisor import EngineSupervisor

router = APIRouter()


@router.get("/models", response_model=ModelsResponse)
async def get_models(request: Request) -> ModelsResponse:
    """Trả về danh sách bundle mô hình đang phục vụ (§4.6)."""
    supervisor: EngineSupervisor = request.app.state.supervisor

    if not supervisor.is_translation_ready() or supervisor._validated_bundle_info is None:
        return ModelsResponse(models=[])

    bundle_info = supervisor._validated_bundle_info
    model_item = ModelItem(
        id=bundle_info.id,
        name=bundle_info.name,
        bundle_version=bundle_info.bundle_version,
        engine_type=bundle_info.engine_type,
        is_mock=bundle_info.is_mock,
        supported_directions=bundle_info.supported_directions,
        is_default=bundle_info.is_default,
        metrics=bundle_info.metrics,
    )
    return ModelsResponse(models=[model_item])
