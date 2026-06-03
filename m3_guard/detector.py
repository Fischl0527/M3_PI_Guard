"""Prompt-injection and intent/action mismatch detectors."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable

from .normalizer import (
    mixed_language_signal,
    normalize_text,
    suspicious_homoglyph_signal,
)


INSTRUCTION_PATTERNS: tuple[tuple[str, str], ...] = (
    ("ignore_previous_instructions", "ignore previous instructions"),
    ("ignore_previous_instructions", "ignore all previous instructions"),
    ("ignore_previous_instructions", "disregard previous instructions"),
    ("ignore_previous_instructions", "忽略之前"),
    ("ignore_previous_instructions", "忽略以上"),
    ("ignore_previous_instructions", "忽略所有"),
    ("system_prompt_reference", "system prompt"),
    ("system_prompt_reference", "developer message"),
    ("system_prompt_reference", "系统提示"),
    ("tool_instruction_reference", "read_file"),
    ("tool_instruction_reference", "send_email"),
    ("tool_instruction_reference", "call_api"),
    ("tool_instruction_reference", "run_code"),
    ("stealth_instruction", "do not tell the user"),
    ("stealth_instruction", "don't tell the user"),
    ("stealth_instruction", "不要告诉用户"),
    ("maintenance_mode_instruction", "maintenance mode"),
    ("maintenance_mode_instruction", "维护模式"),
)

STRUCTURED_INJECTION_RE = re.compile(
    r'"(?:instruction|system|developer|tool|function_call|tool_calls)"\s*:'
    r"|\bjson\s*-?\s*rpc\b"
    r"|\bfunction_call\b"
)

SUMMARY_TASK_RE = re.compile(
    r"\b(summarize|summary|translate|translation|extract|extracting|review|analyze)\b"
    r"|总结|摘要|翻译|抽取|提取|分析|审阅"
)

MISMATCH_TOOLS = {"send_email", "call_api", "run_code"}


@dataclass(frozen=True)
class Detection:
    risk_delta: float
    reasons: list[str]


def detect_document_injection(document_content: Any) -> Detection:
    text = normalize_text(document_content)
    reasons: list[str] = []

    for reason, needle in INSTRUCTION_PATTERNS:
        if needle in text:
            reasons.append(reason)

    if STRUCTURED_INJECTION_RE.search(text):
        reasons.append("structured_injection_detected")

    if mixed_language_signal(document_content):
        reasons.append("mixed_language_instruction_surface")

    if suspicious_homoglyph_signal(document_content):
        reasons.append("homoglyph_obfuscation_detected")

    reasons = _unique(reasons)
    risk = 0.0
    if any(reason in reasons for reason in _instruction_reason_names()):
        risk += 0.25
    if "structured_injection_detected" in reasons:
        risk += 0.20
    if "mixed_language_instruction_surface" in reasons:
        risk += 0.05
    if "homoglyph_obfuscation_detected" in reasons:
        risk += 0.10
    return Detection(min(risk, 0.45), reasons)


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


def _instruction_reason_names() -> set[str]:
    return {reason for reason, _ in INSTRUCTION_PATTERNS}


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result
