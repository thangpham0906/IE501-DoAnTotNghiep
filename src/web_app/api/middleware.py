"""ASGI Middleware kiểm soát giới hạn kích thước request body và gắn X-Request-ID."""

import json
import uuid
from starlette.datastructures import Headers
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from src.web_app.core.config import WebSettings


class BodySizeLimitExceeded(Exception):
    """Ngoại lệ nội bộ khi luồng byte thực nhận vượt quá hạn mức tối đa."""

    def __init__(self, max_allowed: int, received: int) -> None:
        super().__init__(f"Request body exceeded limit: {received} > {max_allowed}")
        self.max_allowed = max_allowed
        self.received = received


class BodyLimitAndRequestIdMiddleware:
    """Kiểm tra giới hạn body trước khi multipart spooling và quản lý X-Request-ID."""

    def __init__(self, app: ASGIApp, settings: WebSettings) -> None:
        self.app = app
        self.settings = settings

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # 1. Trích xuất hoặc sinh X-Request-ID
        headers = Headers(scope=scope)
        request_id = headers.get("x-request-id", "").strip()
        if not request_id:
            request_id = uuid.uuid4().hex

        # Lưu request_id vào scope state để handlers và routes truy cập
        if "state" not in scope:
            scope["state"] = {}
        scope["state"]["request_id"] = request_id

        path = scope.get("path", "")

        # Xác định hạn mức byte theo endpoint
        if path == "/api/asr/transcribe":
            max_bytes = self.settings.MAX_MULTIPART_BODY_BYTES
        else:
            max_bytes = self.settings.MAX_JSON_BODY_BYTES

        # 2. Kiểm tra sớm qua header Content-Length nếu có
        content_length_header = headers.get("content-length")
        if content_length_header is not None:
            try:
                content_length = int(content_length_header)
                if content_length > max_bytes:
                    await self._send_request_too_large(
                        send,
                        request_id=request_id,
                        max_allowed=max_bytes,
                        received=content_length,
                    )
                    return
            except ValueError:
                pass

        # 3. Đếm byte thực nhận qua streaming chunk (chống lying length / chunked)
        received_bytes = 0
        limit_exceeded = False
        response_started = False

        async def bounded_receive() -> Message:
            nonlocal received_bytes, limit_exceeded
            if limit_exceeded:
                raise BodySizeLimitExceeded(max_bytes, received_bytes)

            message = await receive()
            if message["type"] == "http.request":
                chunk = message.get("body", b"")
                received_bytes += len(chunk)
                if received_bytes > max_bytes:
                    limit_exceeded = True
                    # Ngắt ngay lập tức, KHÔNG trả chunk cho app hay parser
                    raise BodySizeLimitExceeded(max_bytes, received_bytes)
            return message

        async def send_wrapper(message: Message) -> None:
            nonlocal response_started
            if limit_exceeded:
                # Chặn hoàn toàn không cho app gửi response (200, 500...) nếu đã vượt limit
                return

            if message["type"] == "http.response.start":
                response_started = True
                response_headers = list(message.get("headers", []))
                has_req_id = any(
                    h[0].lower() == b"x-request-id" for h in response_headers
                )
                if not has_req_id:
                    response_headers.append(
                        (b"x-request-id", request_id.encode("latin-1"))
                    )
                message["headers"] = response_headers
            await send(message)

        try:
            await self.app(scope, bounded_receive, send_wrapper)
        except BodySizeLimitExceeded as exc:
            if not response_started:
                response_started = True
                await self._send_request_too_large(
                    send,
                    request_id=request_id,
                    max_allowed=exc.max_allowed,
                    received=exc.received,
                )
            return
        except Exception:
            if limit_exceeded and not response_started:
                response_started = True
                await self._send_request_too_large(
                    send,
                    request_id=request_id,
                    max_allowed=max_bytes,
                    received=received_bytes,
                )
                return
            raise

        if limit_exceeded and not response_started:
            response_started = True
            await self._send_request_too_large(
                send,
                request_id=request_id,
                max_allowed=max_bytes,
                received=received_bytes,
            )

    async def _send_request_too_large(
        self,
        send: Send,
        *,
        request_id: str,
        max_allowed: int,
        received: int,
    ) -> None:
        """Gửi trực tiếp phản hồi 413 REQUEST_TOO_LARGE theo đúng schema chuẩn (§4.2)."""
        error_payload = {
            "status": "error",
            "error_code": "REQUEST_TOO_LARGE",
            "message": "Kích thước yêu cầu vượt quá giới hạn cho phép.",
            "detail": {
                "max_allowed_bytes": max_allowed,
                "received_bytes": received,
            },
            "request_id": request_id,
        }
        body = json.dumps(error_payload, ensure_ascii=False).encode("utf-8")
        headers = [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode("latin-1")),
            (b"x-request-id", request_id.encode("latin-1")),
        ]
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": headers,
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": body,
            }
        )
