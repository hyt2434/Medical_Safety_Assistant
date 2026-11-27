"""Chuẩn hóa văn bản dùng chung (tìm kiếm tên thuốc)."""
from __future__ import annotations

import re
import unicodedata

_SPACES = re.compile(r"\s+")
_NON_ALNUM = re.compile(r"[^0-9a-z]+")


def normalize(text: str | None) -> str:
    """Xóa khoảng trắng thừa, chữ thường, khử dấu tiếng Việt (đ -> d)."""
    if not text:
        return ""
    text = text.replace("đ", "d").replace("Đ", "D")
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return _SPACES.sub(" ", text.lower()).strip()


def compact(text: str | None) -> str:
    """normalize() rồi bỏ mọi ký tự không phải chữ/số.

    Giúp 'T-Esom 20', 't esom20', 'tesom20' cùng ra một khóa tìm kiếm.
    """
    return _NON_ALNUM.sub("", normalize(text))
