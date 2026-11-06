"""Thiết lập logging có cấu trúc và an toàn thông tin cho Web Demo."""

import logging
import sys


def setup_logging(level: str | int = logging.INFO) -> None:
    """Cấu hình định dạng log chuẩn cho toàn bộ ứng dụng."""
    format_str = (
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
    )
    logging.basicConfig(
        level=level,
        format=format_str,
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )


def get_logger(name: str) -> logging.Logger:
    """Lấy logger theo tên module."""
    return logging.getLogger(name)
