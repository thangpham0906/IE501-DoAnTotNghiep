"""Module phục vụ tài nguyên tĩnh cho giao diện Web Demo (§8.4).

Đảm bảo:
- Phục vụ index.html tại GET / và assets nội bộ tại /css, /js.
- Đường dẫn tính từ __file__, hoàn toàn độc lập với thư mục thực thi hiện tại (cwd).
- Không dùng catch-all SPA router tại root để tránh lộ source code hoặc làm API 404/405 trả về HTML.
- Khả năng chịu lỗi khi thư mục UI chưa được tạo (SafeStaticFiles trả 404 thay vì RuntimeError).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.responses import FileResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.staticfiles import StaticFiles

if TYPE_CHECKING:
    from starlette.responses import Response
    from starlette.types import Scope


class SafeStaticFiles(StaticFiles):
    """StaticFiles tùy biến an toàn cho môi trường phát triển song song.

    1. Không gây crash ứng dụng nếu thư mục tài nguyên chưa được tạo trên đĩa.
    2. Trả về 404 chuẩn tắc thay vì RuntimeError khi thư mục chưa sẵn sàng.
    3. Tận dụng cơ chế phòng thủ Path Traversal bằng os.path.commonpath của Starlette.
    4. Từ chối các HTTP method không phải GET/HEAD bằng HTTP 405.
    """

    async def check_config(self) -> None:
        """Bỏ qua kiểm tra cấu hình cứng tại thời điểm khởi tạo để hỗ trợ nạp lười."""
        pass

    async def get_response(self, path: str, scope: Scope) -> Response:
        """Xử lý yêu cầu lấy file tĩnh an toàn."""
        if self.directory is None or not os.path.isdir(self.directory):
            raise StarletteHTTPException(
                status_code=404,
                detail="Thư mục tài nguyên tĩnh chưa sẵn sàng.",
            )
        return await super().get_response(path, scope)


def register_static_routes(app: FastAPI, ui_dir: Path) -> None:
    """Đăng ký các route phục vụ frontend tĩnh tại cùng origin.

    - GET /: Phục vụ index.html
    - /css: Phục vụ file CSS nội bộ
    - /js: Phục vụ file JavaScript nội bộ
    - /favicon.ico: Phục vụ biểu tượng nếu có
    """
    resolved_ui = Path(ui_dir).resolve()
    css_dir = resolved_ui / "css"
    js_dir = resolved_ui / "js"

    # 1. Mount các thư mục assets nội bộ /css và /js với SafeStaticFiles
    app.mount(
        "/css",
        SafeStaticFiles(directory=str(css_dir), check_dir=False),
        name="static_css",
    )
    app.mount(
        "/js",
        SafeStaticFiles(directory=str(js_dir), check_dir=False),
        name="static_js",
    )

    # 2. Endpoint phục vụ trang chủ index.html (hỗ trợ cả GET và HEAD)
    @app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
    async def serve_index() -> FileResponse:
        """Phục vụ file index.html cho trang chủ."""
        index_path = resolved_ui / "index.html"
        if not index_path.is_file():
            raise StarletteHTTPException(
                status_code=404,
                detail="Giao diện người dùng chưa sẵn sàng.",
            )
        return FileResponse(index_path, media_type="text/html; charset=utf-8")

    # 3. Endpoint phục vụ favicon.ico nếu tồn tại
    @app.api_route("/favicon.ico", methods=["GET", "HEAD"], include_in_schema=False)
    async def serve_favicon() -> FileResponse:
        """Phục vụ favicon nếu tồn tại."""
        fav_path = resolved_ui / "favicon.ico"
        if fav_path.is_file():
            return FileResponse(fav_path)
        raise StarletteHTTPException(
            status_code=404,
            detail="Favicon không tồn tại.",
        )
