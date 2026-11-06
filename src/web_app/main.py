"""Entrypoint chính của ứng dụng Web Demo (§4, §8.4)."""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from fastapi import FastAPI

from src.web_app.api.error_handlers import register_error_handlers
from src.web_app.api.middleware import BodyLimitAndRequestIdMiddleware
from src.web_app.api.router import api_router
from src.web_app.api.static import register_static_routes
from src.web_app.core.config import WebSettings, settings as default_settings
from src.web_app.core.logging import setup_logging
from src.web_app.services.asr.base import ASREngine
from src.web_app.services.asr.factory import create_asr_engine
from src.web_app.services.inference_runner import InferenceRunner
from src.web_app.services.supervisor import EngineSupervisor
from src.web_app.services.translation.base import InferenceEngine
from src.web_app.services.translation.factory import create_translation_engine

_UNSET = object()


def create_app(
    settings: WebSettings | None = None,
    translation_engine: InferenceEngine | None = None,
    asr_engine: ASREngine | None | object = _UNSET,
    ui_dir: Path | None = None,
) -> FastAPI:
    """Tạo và cấu hình ứng dụng FastAPI Web Demo."""
    setup_logging()
    app_settings = settings or default_settings

    # Xác định translation engine
    t_engine = translation_engine or create_translation_engine(app_settings)

    # Xác định ASR engine
    if asr_engine is _UNSET:
        a_engine = create_asr_engine(app_settings)
    else:
        a_engine = asr_engine  # Có thể là None (disabled) hoặc instance ASREngine

    supervisor = EngineSupervisor(
        settings=app_settings,
        translation_engine=t_engine,
        asr_engine=a_engine,
    )

    runner = InferenceRunner(
        app_settings,
        on_fatal_error=supervisor.handle_fatal_error,
        is_engine_failed=supervisor.is_engine_failed,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> Any:
        # Khởi động runner và worker threads
        await runner.start()

        # Nạp engine trong background ngoài event loop
        load_task = asyncio.create_task(supervisor.load_engines())

        try:
            yield
        finally:
            # Shutdown: Dừng runner với thời gian grace
            clean = await runner.shutdown(app_settings.SHUTDOWN_GRACE_SEC)

            # Giải phóng engine nếu an toàn (chờ loader nếu cần, không unload khi còn worker/loader)
            await supervisor.shutdown(runner_clean=clean, grace_sec=app_settings.SHUTDOWN_GRACE_SEC)

            # Hủy load task nếu vẫn đang chạy dở
            if not load_task.done():
                load_task.cancel()
                try:
                    await load_task
                except (asyncio.CancelledError, Exception):
                    pass

    app = FastAPI(
        title="Web Demo Dịch Máy Việt - Tày & Thử Nghiệm Giọng Nói",
        description="Backend API phục vụ dịch văn bản hai chiều và nhận dạng tiếng nói tiếng Việt.",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Lưu trữ các dependency vào state ứng dụng
    app.state.settings = app_settings
    app.state.translation_engine = t_engine
    app.state.asr_engine = a_engine
    app.state.runner = runner
    app.state.supervisor = supervisor

    # 1. Đăng ký Middleware kiểm soát Body Limit và X-Request-ID
    app.add_middleware(BodyLimitAndRequestIdMiddleware, settings=app_settings)

    # 2. Đăng ký Exception Handlers chuẩn tắc
    register_error_handlers(app)

    # 3. Đăng ký API Routes
    app.include_router(api_router)

    # 4. Đăng ký Static Routes phục vụ giao diện cùng origin (§8.4)
    resolved_ui_dir = ui_dir.resolve() if ui_dir is not None else Path(__file__).resolve().parent / "ui"
    app.state.ui_dir = resolved_ui_dir
    register_static_routes(app, resolved_ui_dir)

    return app


# Instance mặc định phục vụ Uvicorn
app = create_app()
