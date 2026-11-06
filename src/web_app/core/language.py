"""Xử lý ngôn ngữ, chiều dịch và chuẩn hóa văn bản theo đặc tả."""

import unicodedata
from typing import Final

# Các chiều dịch được hỗ trợ
SUPPORTED_DIRECTIONS: Final[tuple[str, ...]] = ("vi-tay", "tay-vi")

# Ánh xạ direction -> (source_lang, target_lang) theo quy ước API
DIRECTION_LANG_MAP: Final[dict[str, tuple[str, str]]] = {
    "vi-tay": ("vi", "tyz"),
    "tay-vi": ("tyz", "vi"),
}

# Tập ký tự khoảng trắng dùng chung theo mục 4.3 của đặc tả:
# U+0009–000D, U+0020, U+0085, U+00A0, U+1680, U+2000–200A, U+2028–2029, U+202F, U+205F, U+3000
WHITESPACE_CHARS: Final[str] = (
    "\t\n\x0b\x0c\r"  # U+0009-000D
    " "  # U+0020
    "\x85"  # U+0085
    "\xa0"  # U+00A0
    " "  # U+1680
    "           "  # U+2000-200A
    "  "  # U+2028-2029
    " "  # U+202F
    " "  # U+205F
    "　"  # U+3000
)


def get_language_pair(direction: str) -> tuple[str, str]:
    """Lấy cặp (source_lang, target_lang) cho chiều dịch."""
    if direction not in DIRECTION_LANG_MAP:
        raise ValueError(f"Unsupported direction: {direction}")
    return DIRECTION_LANG_MAP[direction]


def normalize_and_trim_text(text: str) -> str:
    """Chuẩn hóa văn bản sang Unicode NFC và cắt bỏ khoảng trắng hai đầu theo tập WHITESPACE_CHARS.

    Khoảng trắng bên trong văn bản được giữ nguyên.
    """
    if not text:
        return ""
    normalized = unicodedata.normalize("NFC", text)
    return normalized.strip(WHITESPACE_CHARS)
