"""Prompt-injection and intent/action mismatch detectors."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Iterable

from .normalizer import (
    detect_language_mix,
    has_pinyin_evasion,
    has_suspicious_unicode,
    normalize_text,
)


INSTRUCTION_PATTERNS: tuple[tuple[str, str], ...] = (
    ("instruction_ignore_previous", "ignore previous instructions"),
    ("instruction_ignore_all", "ignore all instructions"),
    ("instruction_ignore_all", "ignore all previous instructions"),
    ("instruction_disregard_previous", "disregard previous"),
    ("instruction_developer_message", "developer message"),
    ("instruction_system_prompt", "system prompt"),
    ("instruction_maintenance_mode", "maintenance mode"),
    ("instruction_stealth", "do not tell the user"),
    ("instruction_stealth", "don't tell the user"),
    ("instruction_priority", "run this first"),
    ("instruction_priority", "before summarizing"),
    ("instruction_ignore_previous", "忽略之前"),
    ("instruction_ignore_previous", "忽略以上"),
    ("instruction_ignore_all", "忽略所有"),
    ("instruction_system_prompt", "系统提示"),
    ("instruction_developer_message", "开发者消息"),
    ("instruction_maintenance_mode", "维护模式"),
    ("instruction_stealth", "不要告诉用户"),
    ("instruction_priority", "先执行"),
    ("instruction_priority", "总结前"),
)

TOOL_LURE_PATTERNS: tuple[tuple[str, str], ...] = (
    ("tool_lure_read_file", "read_file"),
    ("tool_lure_write_file", "write_file"),
    ("tool_lure_send_email", "send_email"),
    ("tool_lure_call_api", "call_api"),
    ("tool_lure_run_code", "run_code"),
    ("tool_lure_function_call", "function_call"),
    ("tool_lure_tool_call", "tool_call"),
    ("tool_lure_tool_calls", "tool_calls"),
    ("tool_lure_arguments", "arguments"),
)

STRUCTURED_FIELDS = (
    "instruction",
    "system",
    "developer",
    "tool",
    "tool_calls",
    "function",
    "function_call",
    "rpc",
    "method",
    "params",
    "arguments",
    "execute",
    "next_step",
)

STRUCTURED_FIELD_RE = re.compile(
    r'["\']?(instruction|system|developer|tool|tool_calls|function|function_call|rpc|method|params|arguments|execute|next_step)["\']?\s*[:=]',
    re.I,
)
JSON_RPC_RE = re.compile(r"\bjson\s*-?\s*rpc\b|\bjsonrpc\b|\brpc\s*[:=]", re.I)
SUMMARY_TASK_RE = re.compile(
    r"\b(summarize|summary|translate|translation|extract|extracting|review|analyze|classify|compare)\b"
    r"|总结|摘要|翻译|抽取|提取|分析|审阅|分类|比较"
)

MISMATCH_TOOLS = {"send_email", "call_api", "run_code"}
TOOL_WORD_RE = re.compile(
    r"\b(read_file|write_file|send_email|call_api|run_code|function_call|tool_call|tool_calls|arguments)\b"
)


@dataclass(frozen=True)
class Detection:
    risk_delta: float
    reasons: list[str]


def detect_instruction_like_text(text: Any) -> list[str]:
    """Detect imperative prompt-injection phrases in trusted or untrusted text."""

    normalized = normalize_text(text)
    reasons = [
        reason
        for reason, needle in INSTRUCTION_PATTERNS
        if needle in normalized
    ]
    return _unique(reasons)


def detect_tool_lure(text: Any) -> list[str]:
    """Detect attempts to lure the agent into tool-call syntax or tool names."""

    normalized = normalize_text(text)
    reasons = [
        reason
        for reason, needle in TOOL_LURE_PATTERNS
        if needle in normalized
    ]
    return _unique(reasons)


def detect_structured_injection(text: Any) -> list[str]:
    """Detect JSON/RPC-style fields commonly used to smuggle tool instructions."""

    normalized = normalize_text(text)
    reasons: list[str] = []
    for match in STRUCTURED_FIELD_RE.finditer(normalized):
        reasons.append(f"structured_field_{match.group(1).lower()}")
    if JSON_RPC_RE.search(normalized):
        reasons.append("json_rpc_injection")

    for key in _extract_json_keys(text):
        if key in STRUCTURED_FIELDS:
            reasons.append(f"structured_field_{key}")
        if key in {"jsonrpc", "rpc"}:
            reasons.append("json_rpc_injection")

    if reasons:
        reasons.append("structured_injection_detected")
    return _unique(reasons)


def detect_multilingual_obfuscation(text: Any) -> list[str]:
    """Detect multilingual and pinyin/homophone obfuscation around tool lures."""

    normalized = normalize_text(text)
    language_mix = detect_language_mix(text)
    has_tool_word = bool(TOOL_WORD_RE.search(normalized))
    reasons: list[str] = []

    if language_mix["cjk_latin"] and has_tool_word:
        reasons.append("mixed_cjk_latin_tool_lure")
    if language_mix["jp_ko_ru_with_latin"] and has_tool_word:
        reasons.append("jp_ko_ru_tool_lure")
    if language_mix["mixed"] and has_tool_word:
        reasons.append("multilingual_tool_lure")
    if has_pinyin_evasion(text):
        reasons.append("pinyin_homophone_evasion")
    if has_suspicious_unicode(text):
        reasons.append("suspicious_unicode_obfuscation")

    return _unique(reasons)


def detect_document_injection(document_content: Any) -> Detection:
    reasons: list[str] = []
    reasons.extend(detect_instruction_like_text(document_content))
    reasons.extend(detect_tool_lure(document_content))
    reasons.extend(detect_structured_injection(document_content))
    reasons.extend(detect_multilingual_obfuscation(document_content))
    reasons = _unique(reasons)

    risk = 0.0
    if any(reason.startswith("instruction_") for reason in reasons):
        risk += 0.25
    if any(reason.startswith("tool_lure_") for reason in reasons):
        risk += 0.15
    if any(reason.startswith("structured_field_") for reason in reasons):
        risk += 0.20
    if "json_rpc_injection" in reasons:
        risk += 0.20
    if any(reason in reasons for reason in _multilingual_reason_names()):
        risk += 0.10
    return Detection(min(risk, 0.60), reasons)


def detect_intent_action_mismatch(user_task: Any, tool_name: str) -> Detection:
    if tool_name not in MISMATCH_TOOLS:
        return Detection(0.0, [])
    if SUMMARY_TASK_RE.search(normalize_text(user_task)):
        return Detection(0.25, ["intent_action_mismatch"])
    return Detection(0.0, [])


def detect_case_risk_tags(risk_tags: Iterable[Any]) -> Detection:
    normalized = {normalize_text(tag) for tag in risk_tags}
    reasons: list[str] = []
    risk = 0.0
    if any("prompt_injection" in tag or "jailbreak" in tag for tag in normalized):
        reasons.append("case_marked_prompt_injection")
        risk += 0.10
    if any("tool_hijacking" in tag for tag in normalized):
        reasons.append("case_marked_tool_hijacking")
        risk += 0.05
    if any("data_exfiltration" in tag for tag in normalized):
        reasons.append("case_marked_data_exfiltration")
        risk += 0.05
    return Detection(min(risk, 0.20), reasons)


def _extract_json_keys(value: Any) -> set[str]:
    text = value if isinstance(value, str) else normalize_text(value)
    candidates = [text]
    match = re.search(r"\{.*\}", str(text), re.S)
    if match:
        candidates.append(match.group(0))

    keys: set[str] = set()
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except (TypeError, json.JSONDecodeError):
            continue
        _collect_keys(parsed, keys)
    return keys


def _collect_keys(value: Any, keys: set[str]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            keys.add(normalize_text(key))
            _collect_keys(child, keys)
    elif isinstance(value, list):
        for child in value:
            _collect_keys(child, keys)


def _multilingual_reason_names() -> set[str]:
    return {
        "mixed_cjk_latin_tool_lure",
        "jp_ko_ru_tool_lure",
        "multilingual_tool_lure",
        "pinyin_homophone_evasion",
        "suspicious_unicode_obfuscation",
    }


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result
