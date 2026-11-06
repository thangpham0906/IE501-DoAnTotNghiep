"""Router tổng hợp toàn bộ các endpoint /api (§4)."""

from fastapi import APIRouter

from src.web_app.api.routes import asr, health, models, translate

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(models.router, tags=["Models"])
api_router.include_router(translate.router, tags=["Translate"])
api_router.include_router(asr.router, tags=["ASR"])
