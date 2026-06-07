"""Normalization helpers for local, rule-based Guard checks."""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any


ZERO_WIDTH_CHARS = {
    "\u00ad",
    "\u034f",
    "\u061c",
    "\u115f",
    "\u1160",
    "\u17b4",
    "\u17b5",
    "\u180e",
    "\u200b",
    "\u200c",
    "\u200d",
    "\u200e",
    "\u200f",
    "\u202a",
    "\u202b",
    "\u202c",
    "\u202d",
    "\u202e",
    "\u2060",
    "\u2061",
    "\u2062",
    "\u2063",
    "\u2064",
    "\u2066",
    "\u2067",
    "\u2068",
    "\u2069",
    "\u206a",
    "\u206b",
    "\u206c",
    "\u206d",
    "\u206e",
    "\u206f",
    "\ufeff",
}
WHITESPACE_RE = re.compile(r"\s+")
PINYIN_EVASION_TERMS = (
    "hulue",
    "wushi",
    "fasong",
    "fayoujian",
    "duqu",
    "duwenjian",
    "xianzhixing",
    "zongjieqian",
    "buyaogaosuyonghu",
    "xitongtishi",
    "kaifazhexiaoxi",
)


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


def remove_zero_width(text: Any) -> str:
    """Remove zero-width, soft-hyphen, and bidi control characters."""

    return "".join(ch for ch in to_text(text) if ch not in ZERO_WIDTH_CHARS)


def normalize_text(text: Any) -> str:
    """Apply NFKC, strip zero-width chars, lowercase, and collapse spaces."""

    normalized = unicodedata.normalize("NFKC", to_text(text))
    normalized = remove_zero_width(normalized)
    normalized = normalized.lower()
    normalized = WHITESPACE_RE.sub(" ", normalized)
    return normalized.strip()


def normalize_path(path: Any) -> str:
    """Normalize a sandbox path for policy comparisons."""

    text = normalize_text(path).replace("\\", "/")
    text = text.strip("'\" ")
    while text.startswith("./"):
        text = text[2:]
    text = re.sub(r"/+", "/", text)
    return text


def detect_language_mix(text: Any) -> dict[str, Any]:
    """Detect Chinese/English/Japanese/Russian/Korean script mixing."""

    raw = normalize_text(text)
    scripts = {
        "latin": False,
        "chinese": False,
        "japanese": False,
        "korean": False,
        "russian": False,
    }

    for ch in raw:
        codepoint = ord(ch)
        name = unicodedata.name(ch, "")
        if "LATIN" in name and ch.isalpha():
            scripts["latin"] = True
        if _is_chinese(codepoint):
            scripts["chinese"] = True
        if _is_japanese(codepoint):
            scripts["japanese"] = True
        if _is_korean(codepoint):
            scripts["korean"] = True
        if _is_cyrillic(codepoint):
            scripts["russian"] = True

    active = [name for name, present in scripts.items() if present]
    cjk_or_cyrillic = any(scripts[name] for name in ("chinese", "japanese", "korean", "russian"))
    return {
        **scripts,
        "scripts": active,
        "script_count": len(active),
        "mixed": len(active) >= 2,
        "cjk_latin": scripts["latin"] and any(
            scripts[name] for name in ("chinese", "japanese", "korean")
        ),
        "jp_ko_ru_with_latin": scripts["latin"]
        and any(scripts[name] for name in ("japanese", "korean", "russian")),
        "non_latin_with_tool_surface": cjk_or_cyrillic,
    }


def has_suspicious_unicode(text: Any) -> bool:
    """Flag common Unicode tricks used for prompt-injection obfuscation."""

    raw = to_text(text)
    normalized = unicodedata.normalize("NFKC", raw)
    if any(ch in ZERO_WIDTH_CHARS for ch in raw):
        return True
    if raw != normalized and any(ord(ch) > 127 for ch in raw):
        return True
    if _has_latin_confusable_mix(raw):
        return True
    combining_marks = sum(1 for ch in raw if unicodedata.category(ch).startswith("M"))
    return combining_marks >= 3


def has_pinyin_evasion(text: Any) -> bool:
    """Detect rough pinyin/homophone spellings of sensitive instructions."""

    normalized = normalize_text(text).replace("ü", "u").replace("v", "u")
    compact = re.sub(r"[^a-z0-9]+", "", normalized)
    return any(term in compact for term in PINYIN_EVASION_TERMS)


def mixed_language_signal(value: Any) -> bool:
    """Backward-compatible boolean for CJK/Latin language mixing."""

    return bool(detect_language_mix(value)["cjk_latin"])


def suspicious_homoglyph_signal(value: Any) -> bool:
    """Backward-compatible boolean for homoglyph/confusable script mixing."""

    return _has_latin_confusable_mix(to_text(value))


def _has_latin_confusable_mix(text: str) -> bool:
    has_latin = False
    has_confusable = False
    for ch in unicodedata.normalize("NFKC", text):
        if not ch.isalpha():
            continue
        name = unicodedata.name(ch, "")
        has_latin = has_latin or "LATIN" in name
        has_confusable = has_confusable or "CYRILLIC" in name or "GREEK" in name
    return has_latin and has_confusable


def _is_chinese(codepoint: int) -> bool:
    return (
        0x4E00 <= codepoint <= 0x9FFF
        or 0x3400 <= codepoint <= 0x4DBF
        or 0xF900 <= codepoint <= 0xFAFF
    )


def _is_japanese(codepoint: int) -> bool:
    return 0x3040 <= codepoint <= 0x30FF or 0x31F0 <= codepoint <= 0x31FF


def _is_korean(codepoint: int) -> bool:
    return (
        0xAC00 <= codepoint <= 0xD7AF
        or 0x1100 <= codepoint <= 0x11FF
        or 0x3130 <= codepoint <= 0x318F
    )


def _is_cyrillic(codepoint: int) -> bool:
    return 0x0400 <= codepoint <= 0x052F
