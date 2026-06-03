"""Normalization helpers for local, rule-based Guard checks."""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any


ZERO_WIDTH_CHARS = {
    "\u200b",
    "\u200c",
    "\u200d",
    "\u2060",
    "\ufeff",
}
WHITESPACE_RE = re.compile(r"\s+")


def to_text(value: Any) -> str:
    """Convert arbitrary JSON-like data to stable text for scanning."""

    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except TypeError:
        return str(value)


def normalize_text(value: Any) -> str:
    """Lowercase, Unicode-normalize, strip zero-width chars, collapse spaces."""

    text = unicodedata.normalize("NFKC", to_text(value))
    text = "".join(ch for ch in text if ch not in ZERO_WIDTH_CHARS)
    text = text.lower()
    text = WHITESPACE_RE.sub(" ", text)
    return text.strip()


def normalize_path(path: Any) -> str:
    """Normalize a sandbox path for policy comparisons."""

    text = normalize_text(path).replace("\\", "/")
    text = text.strip("'\" ")
    while text.startswith("./"):
        text = text[2:]
    text = re.sub(r"/+", "/", text)
    return text


def mixed_language_signal(value: Any) -> bool:
    """Return True when text mixes CJK with Latin words."""

    text = normalize_text(value)
    has_cjk = any("\u4e00" <= ch <= "\u9fff" for ch in text)
    has_latin = any("a" <= ch <= "z" for ch in text)
    return has_cjk and has_latin


def suspicious_homoglyph_signal(value: Any) -> bool:
    """Detect common non-Latin scripts mixed into otherwise Latin-looking text."""

    raw = unicodedata.normalize("NFKC", to_text(value))
    has_latin = any("LATIN" in unicodedata.name(ch, "") for ch in raw if ch.isalpha())
    has_confusable = any(
        ("CYRILLIC" in unicodedata.name(ch, "") or "GREEK" in unicodedata.name(ch, ""))
        for ch in raw
        if ch.isalpha()
    )
    return has_latin and has_confusable
