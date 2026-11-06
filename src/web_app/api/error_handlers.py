"""Xử lý ngoại lệ tập trung cho FastAPI, ánh xạ mọi lỗi về ErrorResponse (§4.2)."""

import logging
from typing import Any
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.web_app.core.exceptions import AppError
from src.web_app.core.schemas import ErrorResponse

logger = logging.getLogger("web_app.errors")


def _get_request_id(request: Request) -> str:
    """Lấy request_id đã được middleware lưu vào request.state."""
    req_id = getattr(request.state, "request_id", None)
    if not req_id:
        req_id = request.headers.get("x-request-id", "unknown-request")
    return req_id


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Xử lý các ngoại lệ nghiệp vụ AppError."""
    req_id = _get_request_id(request)
    logger.warning(
        "Ngoại lệ nghiệp vụ AppError: request_id=%s code=%s status=%d message=%s",
        req_id,
        exc.error_code,
        exc.status_code,
        exc.message,
    )
    content = ErrorResponse(
        status="error",
        error_code=exc.error_code,
        message=exc.message,
        detail=exc.detail,
        request_id=req_id,
    ).model_dump()
    return JSONResponse(
        status_code=exc.status_code,
        content=content,
        headers={"X-Request-ID": req_id},
    )


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Xử lý lỗi schema/kiểu dữ liệu từ Pydantic, chuẩn hóa về INVALID_INPUT."""
    req_id = _get_request_id(request)
    errors = exc.errors()

    # Thu thập chi tiết lỗi an toàn, không lộ đường dẫn nội bộ
    sanitized_errors: list[dict[str, Any]] = []
    for err in errors:
        loc = [str(x) for x in err.get("loc", []) if x != "body"]
        field_name = ".".join(loc) if loc else "body"
        sanitized_errors.append(
            {
                "field": field_name,
                "issue": err.get("msg", "Giá trị không hợp lệ"),
                "type": err.get("type", "value_error"),
            }
        )

    logger.warning(
        "Lỗi xác thực dữ liệu đầu vào: request_id=%s errors=%s",
        req_id,
        sanitized_errors,
    )
    content = ErrorResponse(
        status="error",
        error_code="INVALID_INPUT",
        message="Dữ liệu đầu vào không hợp lệ hoặc thiếu trường bắt buộc.",
        detail={"validation_errors": sanitized_errors},
        request_id=req_id,
    ).model_dump()
    return JSONResponse(
        status_code=400,
        content=content,
        headers={"X-Request-ID": req_id},
    )


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """Xử lý các ngoại lệ HTTP chuẩn từ Starlette/FastAPI, chuẩn hóa mã lỗi theo §4.2."""
    req_id = _get_request_id(request)
    status_code = exc.status_code

    if status_code == 400:
        error_code = "INVALID_INPUT"
        message = "Dữ liệu đầu vào không hợp lệ hoặc thiếu trường bắt buộc."
    elif status_code == 404:
        error_code = "NOT_FOUND"
        message = "Tài nguyên hoặc đường dẫn API không tồn tại."
    elif status_code == 405:
        error_code = "METHOD_NOT_ALLOWED"
        message = "Phương thức HTTP không được phép cho endpoint này."
    elif status_code == 413:
        error_code = "REQUEST_TOO_LARGE"
        message = "Kích thước yêu cầu vượt quá giới hạn cho phép."
    elif status_code == 422:
        error_code = "INVALID_INPUT"
        message = "Dữ liệu đầu vào không hợp lệ hoặc thiếu trường bắt buộc."
    elif status_code == 503:
        error_code = "MODEL_NOT_READY"
        message = "Mô hình hoặc engine chưa sẵn sàng để phục vụ yêu cầu."
    elif status_code == 504:
        error_code = "INFERENCE_TIMEOUT"
        message = "Thời gian xử lý suy luận đã vượt quá giới hạn cho phép."
    else:
        error_code = "INTERNAL_ERROR"
        message = "Đã xảy ra lỗi nội bộ không mong muốn."

    content = ErrorResponse(
        status="error",
        error_code=error_code,
        message=message,
        detail=None,
        request_id=req_id,
    ).model_dump()
    return JSONResponse(
        status_code=status_code,
        content=content,
        headers={"X-Request-ID": req_id},
    )


async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Bắt và bảo vệ mọi ngoại lệ bất ngờ còn lại, ngăn lộ stack trace (§4.2)."""
    req_id = _get_request_id(request)
    logger.exception(
        "Lỗi không mong muốn trong quá trình xử lý request: request_id=%s exc=%s",
        req_id,
        exc,
    )
    content = ErrorResponse(
        status="error",
        error_code="INTERNAL_ERROR",
        message="Đã xảy ra lỗi nội bộ không mong muốn.",
        detail=None,
        request_id=req_id,
    ).model_dump()
    return JSONResponse(
        status_code=500,
        content=content,
        headers={"X-Request-ID": req_id},
    )


def register_error_handlers(app: FastAPI) -> None:
    """Đăng ký toàn bộ error handlers với ứng dụng FastAPI."""
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
