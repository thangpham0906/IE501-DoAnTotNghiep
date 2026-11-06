"""Package test cho Web Demo."""

import unittest


def load_tests(
    loader: unittest.TestLoader,
    standard_tests: unittest.TestSuite,
    pattern: str | None,
) -> unittest.TestSuite:
    """Tùy biến discovery cho unittest khi quét từ thư mục gốc src/tests.

    Nếu môi trường không cài đặt các phụ thuộc web (như khi chạy với `python3 -S`
    chỉ có thư viện chuẩn để kiểm tra pipeline dữ liệu), bỏ qua việc nạp các module
    test web để giữ cam kết pipeline độc lập không cần phụ thuộc web.
    """
    try:
        import pytest  # noqa: F401
        import fastapi  # noqa: F401
    except ImportError:
        return unittest.TestSuite()

    this_dir = __path__[0]
    return loader.discover(start_dir=this_dir, pattern=pattern or "test_*.py")
