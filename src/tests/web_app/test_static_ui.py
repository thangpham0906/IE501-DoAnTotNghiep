"""Kiểm thử phục vụ frontend tĩnh cùng origin và tính độc lập kiến trúc (§8.4).

Bao gồm:
- Phục vụ GET / trả về index.html với Content-Type text/html; charset=utf-8
- HEAD / trả về headers đúng và không có body
- GET / trả về 404 JSON chuẩn ErrorResponse khi UI chưa sẵn sàng
- Method sai (POST/PUT/DELETE) tại / trả về 405 JSON METHOD_NOT_ALLOWED
- Assets nội bộ /css/app.css và /js/app.js có Content-Type chuẩn
- Asset không tồn tại trả về 404 JSON chuẩn ErrorResponse
- Method sai trên static assets trả về 405 JSON METHOD_NOT_ALLOWED
- Chống tấn công Path Traversal (/css/../secret, URL-encoded %2e%2e)
- API route không xác định (/api/nonexistent) trả về 404 JSON, không trả HTML
- Method sai trên API (/api/health POST) trả về 405 JSON, không trả HTML
- Không phục vụ các file nội bộ của backend (package.json, main.py, .env)
- Độc lập hoàn toàn với thư mục thực thi (cwd-independent)
- Đảm bảo static route không bắt nhầm hoặc xung đột với API routes (/api/*)
- Tránh race condition C15 bằng wait_client_loaded khi kiểm thử API
"""

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from src.web_app.core.config import WebSettings
from src.web_app.main import create_app
from src.tests.web_app.conftest import wait_client_loaded


@pytest.fixture
def mock_ui_dir(tmp_path: Path) -> Path:
    """Tạo fixture thư mục UI tạm thời với đầy đủ assets mẫu."""
    ui_dir = tmp_path / "mock_ui"
    ui_dir.mkdir(parents=True, exist_ok=True)

    # 1. index.html
    (ui_dir / "index.html").write_text(
        "<!DOCTYPE html><html><head><title>Web Demo</title></head><body><h1>Hello UI</h1></body></html>",
        encoding="utf-8",
    )

    # 2. css/app.css
    css_dir = ui_dir / "css"
    css_dir.mkdir(parents=True, exist_ok=True)
    (css_dir / "app.css").write_text("body { margin: 0; background-color: #f8fafc; }", encoding="utf-8")

    # 3. js/app.js & js/api_client.js
    js_dir = ui_dir / "js"
    js_dir.mkdir(parents=True, exist_ok=True)
    (js_dir / "app.js").write_text("console.log('App initialized');", encoding="utf-8")
    (js_dir / "api_client.js").write_text("export async function apiRequest() {}", encoding="utf-8")

    # 4. favicon.ico
    (ui_dir / "favicon.ico").write_bytes(b"\x00\x00\x01\x00\x01\x00\x10\x10")

    # 5. File nhạy cảm bên ngoài để kiểm tra Traversal
    (tmp_path / "secret_backend_config.txt").write_text("SUPER_SECRET_TOKEN_DO_NOT_EXPOSE", encoding="utf-8")

    return ui_dir


class TestStaticUIServing:
    """Kiểm thử các hành vi phục vụ file tĩnh và hợp đồng lỗi."""

    def test_root_serves_index_html(self, mock_ui_dir: Path, default_settings: WebSettings) -> None:
        """GET / phải phục vụ đúng index.html với Content-Type text/html; charset=utf-8."""
        app = create_app(settings=default_settings, ui_dir=mock_ui_dir)
        with TestClient(app) as client:
            res = client.get("/")
            assert res.status_code == 200
            assert "text/html" in res.headers["content-type"]
            assert "charset=utf-8" in res.headers["content-type"].lower()
            assert "<h1>Hello UI</h1>" in res.text

    def test_root_head_request(self, mock_ui_dir: Path, default_settings: WebSettings) -> None:
        """HEAD / phải trả về 200 với headers đúng và body rỗng."""
        app = create_app(settings=default_settings, ui_dir=mock_ui_dir)
        with TestClient(app) as client:
            res = client.head("/")
            assert res.status_code == 200
            assert "text/html" in res.headers["content-type"]
            assert res.text == ""

    def test_root_when_ui_not_ready(self, tmp_path: Path, default_settings: WebSettings) -> None:
        """Khi index.html chưa tồn tại, GET / phải trả về 404 JSON chuẩn ErrorResponse."""
        empty_dir = tmp_path / "empty_ui"
        empty_dir.mkdir(parents=True, exist_ok=True)

        app = create_app(settings=default_settings, ui_dir=empty_dir)
        with TestClient(app) as client:
            res = client.get("/")
            assert res.status_code == 404
            assert res.headers["content-type"].startswith("application/json")
            data = res.json()
            assert data["status"] == "error"
            assert data["error_code"] == "NOT_FOUND"
            assert "Giao diện người dùng chưa sẵn sàng" in data["message"] or "Tài nguyên" in data["message"]
            assert "request_id" in data

    def test_root_wrong_method_returns_json_405(self, mock_ui_dir: Path, default_settings: WebSettings) -> None:
        """POST, PUT, DELETE vào / phải trả về 405 JSON METHOD_NOT_ALLOWED, không trả HTML."""
        app = create_app(settings=default_settings, ui_dir=mock_ui_dir)
        with TestClient(app) as client:
            for method in ["post", "put", "delete", "patch"]:
                res = client.request(method, "/")
                assert res.status_code == 405
                assert res.headers["content-type"].startswith("application/json")
                data = res.json()
                assert data["status"] == "error"
                assert data["error_code"] == "METHOD_NOT_ALLOWED"
                assert "request_id" in data

    def test_css_content_type(self, mock_ui_dir: Path, default_settings: WebSettings) -> None:
        """GET /css/app.css phải phục vụ file CSS với Content-Type text/css."""
        app = create_app(settings=default_settings, ui_dir=mock_ui_dir)
        with TestClient(app) as client:
            res = client.get("/css/app.css")
            assert res.status_code == 200
            assert "text/css" in res.headers["content-type"]
            assert "background-color: #f8fafc" in res.text

    def test_js_content_type(self, mock_ui_dir: Path, default_settings: WebSettings) -> None:
        """GET /js/app.js và /js/api_client.js phải phục vụ file JavaScript với Content-Type chuẩn."""
        app = create_app(settings=default_settings, ui_dir=mock_ui_dir)
        with TestClient(app) as client:
            for js_file in ["app.js", "api_client.js"]:
                res = client.get(f"/js/{js_file}")
                assert res.status_code == 200
                content_type = res.headers["content-type"]
                assert ("javascript" in content_type)
                assert len(res.text) > 0

    def test_static_asset_missing_returns_json_404(
        self, mock_ui_dir: Path, default_settings: WebSettings
    ) -> None:
        """Yêu cầu asset không tồn tại trong /css hoặc /js phải trả về 404 JSON, không trả HTML."""
        app = create_app(settings=default_settings, ui_dir=mock_ui_dir)
        with TestClient(app) as client:
            for missing_path in ["/css/nonexistent.css", "/js/missing.js", "/css/sub/missing.css"]:
                res = client.get(missing_path)
                assert res.status_code == 404
                assert res.headers["content-type"].startswith("application/json")
                data = res.json()
                assert data["status"] == "error"
                assert data["error_code"] == "NOT_FOUND"

    def test_static_asset_wrong_method_returns_json_405(
        self, mock_ui_dir: Path, default_settings: WebSettings
    ) -> None:
        """Phương thức không hợp lệ (POST/PUT) trên asset tĩnh phải trả về 405 JSON METHOD_NOT_ALLOWED."""
        app = create_app(settings=default_settings, ui_dir=mock_ui_dir)
        with TestClient(app) as client:
            for method in ["post", "put", "delete"]:
                res = client.request(method, "/css/app.css")
                assert res.status_code == 405
                assert res.headers["content-type"].startswith("application/json")
                data = res.json()
                assert data["status"] == "error"
                assert data["error_code"] == "METHOD_NOT_ALLOWED"

    def test_path_traversal_attacks_blocked(self, mock_ui_dir: Path, default_settings: WebSettings) -> None:
        """Tấn công Path Traversal qua ../ hoặc URL-encoded phải bị chặn và trả về 404 JSON."""
        app = create_app(settings=default_settings, ui_dir=mock_ui_dir)
        with TestClient(app) as client:
            payloads = [
                "/css/../secret_backend_config.txt",
                "/css/..%2fsecret_backend_config.txt",
                "/css/%2e%2e/secret_backend_config.txt",
                "/css/..%2F..%2Fsecret_backend_config.txt",
                "/js/../secret_backend_config.txt",
                "/js/..%2f..%2fsecret_backend_config.txt",
                "/css/../../etc/passwd",
                "/css/..%2F..%2F..%2Fetc%2Fpasswd",
            ]
            for p in payloads:
                res = client.get(p)
                assert res.status_code == 404
                assert "SUPER_SECRET_TOKEN_DO_NOT_EXPOSE" not in res.text
                assert "root:" not in res.text
                assert res.headers["content-type"].startswith("application/json")
                data = res.json()
                assert data["status"] == "error"
                assert data["error_code"] == "NOT_FOUND"

    def test_favicon_serving(self, mock_ui_dir: Path, default_settings: WebSettings) -> None:
        """GET /favicon.ico phải phục vụ biểu tượng nếu có, hoặc trả về 404 JSON nếu thiếu."""
        # 1. Trường hợp có favicon
        app_with_fav = create_app(settings=default_settings, ui_dir=mock_ui_dir)
        with TestClient(app_with_fav) as client:
            res = client.get("/favicon.ico")
            assert res.status_code == 200
            assert len(res.content) > 0

        # 2. Trường hợp thiếu favicon
        empty_dir = mock_ui_dir.parent / "no_fav_ui"
        empty_dir.mkdir(parents=True, exist_ok=True)
        app_no_fav = create_app(settings=default_settings, ui_dir=empty_dir)
        with TestClient(app_no_fav) as client:
            res_missing = client.get("/favicon.ico")
            assert res_missing.status_code == 404
            assert res_missing.headers["content-type"].startswith("application/json")
            assert res_missing.json()["error_code"] == "NOT_FOUND"

    def test_internal_project_files_not_exposed(
        self, mock_ui_dir: Path, default_settings: WebSettings
    ) -> None:
        """Các file nội bộ của backend không được lộ qua web root."""
        app = create_app(settings=default_settings, ui_dir=mock_ui_dir)
        with TestClient(app) as client:
            internal_targets = [
                "/package.json",
                "/main.py",
                "/.env",
                "/.env.example",
                "/requirements.txt",
                "/src/web_app/main.py",
                "/conftest.py",
            ]
            for target in internal_targets:
                res = client.get(target)
                assert res.status_code == 404
                assert res.headers["content-type"].startswith("application/json")
                data = res.json()
                assert data["status"] == "error"
                assert data["error_code"] == "NOT_FOUND"


class TestAPIAndStaticIsolation:
    """Kiểm thử sự cách ly giữa Static Routes và API Routes."""

    def test_unknown_api_route_returns_json_404(
        self, mock_ui_dir: Path, default_settings: WebSettings
    ) -> None:
        """Đường dẫn /api/* không tồn tại phải trả về JSON 404, tuyệt đối không trả HTML."""
        app = create_app(settings=default_settings, ui_dir=mock_ui_dir)
        with TestClient(app) as client:
            for unknown_api in [
                "/api/nonexistent",
                "/api/v1/translate",
                "/api/models/unknown",
                "/api/unknown/deep/path",
            ]:
                res = client.get(unknown_api)
                assert res.status_code == 404
                assert res.headers["content-type"].startswith("application/json")
                data = res.json()
                assert data["status"] == "error"
                assert data["error_code"] == "NOT_FOUND"
                assert "Tài nguyên hoặc đường dẫn API không tồn tại" in data["message"]

    def test_api_method_wrong_returns_json_405(
        self, mock_ui_dir: Path, default_settings: WebSettings
    ) -> None:
        """Method không được phép trên API (/api/health POST) phải trả về JSON 405 METHOD_NOT_ALLOWED."""
        app = create_app(settings=default_settings, ui_dir=mock_ui_dir)
        with TestClient(app) as client:
            res = client.post("/api/health")
            assert res.status_code == 405
            assert res.headers["content-type"].startswith("application/json")
            data = res.json()
            assert data["status"] == "error"
            assert data["error_code"] == "METHOD_NOT_ALLOWED"

    def test_static_does_not_intercept_existing_api_endpoints(
        self, mock_ui_dir: Path, default_settings: WebSettings
    ) -> None:
        """Đảm bảo static routes không bắt nhầm các endpoint API thực tế (§4)."""
        app = create_app(settings=default_settings, ui_dir=mock_ui_dir)
        with TestClient(app) as client:
            # Chờ engine sẵn sàng để tránh race C15
            wait_client_loaded(client)

            # 1. GET /api/health
            r_health = client.get("/api/health")
            assert r_health.status_code == 200
            assert r_health.json()["status"] == "ready"

            # 2. GET /api/models
            r_models = client.get("/api/models")
            assert r_models.status_code == 200
            models_data = r_models.json()
            assert "models" in models_data
            assert len(models_data["models"]) >= 1
            assert models_data["models"][0]["id"] == "mock-demo"

            # 3. POST /api/translate
            r_trans = client.post(
                "/api/translate",
                json={"text": "Chào bạn", "direction": "vi-tay"},
            )
            assert r_trans.status_code == 200
            assert r_trans.json()["status"] == "success"
            assert "translation" in r_trans.json()

    def test_cwd_independent_path_resolution(
        self, tmp_path: Path, default_settings: WebSettings, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Đảm bảo ứng dụng tính toán thư mục static từ __file__, không phụ thuộc cwd."""
        # Chuyển cwd sang một thư mục bất kỳ
        arbitrary_dir = tmp_path / "arbitrary_cwd"
        arbitrary_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.chdir(arbitrary_dir)

        # Khởi tạo app không truyền ui_dir (dùng mặc định từ __file__)
        app = create_app(settings=default_settings)
        resolved_ui = app.state.ui_dir

        assert resolved_ui.is_absolute()
        assert resolved_ui.name == "ui"
        assert resolved_ui.parent.name == "web_app"
        assert str(arbitrary_dir) not in str(resolved_ui)

    def test_backend_runs_safely_when_real_ui_absent(
        self, tmp_path: Path, default_settings: WebSettings
    ) -> None:
        """Đảm bảo backend chạy và test được bình thường ngay cả khi UI chưa được tạo."""
        nonexistent_ui = tmp_path / "completely_nonexistent_ui_dir"
        app = create_app(settings=default_settings, ui_dir=nonexistent_ui)
        with TestClient(app) as client:
            res_root = client.get("/")
            assert res_root.status_code == 404
            assert res_root.json()["error_code"] == "NOT_FOUND"

            res_css = client.get("/css/app.css")
            assert res_css.status_code == 404
            assert res_css.json()["error_code"] == "NOT_FOUND"
