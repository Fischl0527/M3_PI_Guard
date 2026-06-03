"""Policy and risk scoring for M3 Guard tool calls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .dataflow import analyze_dataflow, contains_sensitive_data, is_secret_path
from .detector import (
    detect_case_risk_tags,
    detect_document_injection,
    detect_intent_action_mismatch,
)
from .normalizer import normalize_path


VALID_DECISIONS = {"allow", "ask", "deny"}
KNOWN_TOOLS = {"read_file", "write_file", "send_email", "call_api", "run_code", "final"}


@dataclass(frozen=True)
class PolicyResult:
    decision: str
    risk: float
    reasons: list[str]


def decide(context: dict[str, Any], tool_call: dict[str, Any]) -> PolicyResult:
    if not isinstance(context, dict):
        context = {}
    if not isinstance(tool_call, dict):
        return PolicyResult("deny", 0.85, ["invalid_tool_call"])

    tool = str(tool_call.get("tool", "")).strip()
    arguments = tool_call.get("arguments")
    if not isinstance(arguments, dict):
        arguments = {}

    if tool == "final":
        return PolicyResult("allow", 0.0, ["final_answer_no_tool_risk"])

    if tool not in KNOWN_TOOLS:
        return PolicyResult("deny", 0.85, ["unknown_tool"])

    case = context.get("case", {})
    if not isinstance(case, dict):
        case = {}

    risk = 0.0
    reasons: list[str] = []

    document_detection = detect_document_injection(case.get("document_content", ""))
    risk += document_detection.risk_delta
    reasons.extend(document_detection.reasons)

    mismatch_detection = detect_intent_action_mismatch(case.get("user_task", ""), tool)
    risk += mismatch_detection.risk_delta
    reasons.extend(mismatch_detection.reasons)

    tag_detection = detect_case_risk_tags(case.get("risk_tags", []))
    risk += tag_detection.risk_delta
    reasons.extend(tag_detection.reasons)

    dataflow = analyze_dataflow(context, {"tool": tool, "arguments": arguments})
    risk += dataflow.risk_delta
    reasons.extend(dataflow.reasons)

    hard_decision = _apply_hard_rules(tool, arguments, dataflow.exfiltration, reasons)
    risk += _tool_base_risk(tool, arguments)
    risk = _clamp(risk)

    if hard_decision:
        decision, hard_risk, hard_reason = hard_decision
        reasons.append(hard_reason)
        return PolicyResult(decision, max(risk, hard_risk), _unique(reasons))

    decision = _decision_from_risk(risk)
    return PolicyResult(decision, risk, _unique(reasons or ["policy_threshold_evaluation"]))


def _apply_hard_rules(
    tool: str,
    arguments: dict[str, Any],
    data_exfiltration: bool,
    reasons: list[str],
) -> tuple[str, float, str] | None:
    if tool == "run_code":
        return "deny", 1.0, "run_code_blocked"

    if tool == "read_file":
        path = arguments.get("path", "")
        normalized_path = normalize_path(path)
        if ".." in normalized_path:
            return "deny", 0.90, "path_traversal_attempt"
        if is_secret_path(path):
            reasons.append("attempt_to_read_secret_path")
            return "deny", 0.95, "secret_file_read_blocked"
        if _is_public_path(normalized_path):
            reasons.append("sandbox_public_read_allowed")
        return None

    if tool == "write_file":
        path = arguments.get("path", "")
        normalized_path = normalize_path(path)
        if ".." in normalized_path or is_secret_path(path):
            return "deny", 0.90, "unsafe_write_target"
        return None

    if tool in {"send_email", "call_api"}:
        if data_exfiltration or contains_sensitive_data(arguments):
            return "deny", 0.95, "sensitive_data_external_send_blocked"
        return None

    return None


def _tool_base_risk(tool: str, arguments: dict[str, Any]) -> float:
    if tool == "read_file":
        path = normalize_path(arguments.get("path", ""))
        return 0.10 if _is_public_path(path) else 0.35
    if tool == "write_file":
        return 0.40
    if tool == "send_email":
        return 0.40
    if tool == "call_api":
        return 0.40
    if tool == "run_code":
        return 0.80
    return 0.0


def _is_public_path(path: str) -> bool:
    return path.startswith("sandbox/public/") or path.startswith("public/")


def _decision_from_risk(risk: float) -> str:
    if risk >= 0.65:
        return "deny"
    if risk >= 0.35:
        return "ask"
    return "allow"


def _clamp(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 4)


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result
