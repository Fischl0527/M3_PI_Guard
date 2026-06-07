"""Policy matrix for M3 Guard tool calls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .dataflow import analyze_dataflow, contains_sensitive_data, is_sandbox_path, is_secret_path
from .normalizer import normalize_path, normalize_text


VALID_DECISIONS = {"allow", "ask", "deny"}
KNOWN_TOOLS = {"read_file", "write_file", "send_email", "call_api", "run_code", "final"}
HIGH_RISK_TOOLS = {"read_file", "write_file", "send_email", "call_api", "run_code"}


@dataclass(frozen=True)
class PolicyResult:
    decision: str
    risk: float
    reasons: list[str]
    forced: bool = False


def decide(context: dict[str, Any], tool_call: dict[str, Any]) -> PolicyResult:
    """Apply the DAY3 policy matrix before threshold-based risk escalation."""

    if not isinstance(context, dict):
        context = {}
    if not isinstance(tool_call, dict):
        return PolicyResult("deny", 0.85, ["invalid_tool_call"], forced=True)

    tool = str(tool_call.get("tool", "")).strip()
    arguments = tool_call.get("arguments")
    if not isinstance(arguments, dict):
        arguments = {}

    if tool == "final":
        return PolicyResult("allow", 0.0, ["final_answer_no_tool_risk"])

    if tool not in KNOWN_TOOLS:
        return PolicyResult("deny", 0.85, ["unknown_tool"], forced=True)

    reasons: list[str] = []
    if tool in HIGH_RISK_TOOLS:
        reasons.append("high_risk_tool")

    dataflow = analyze_dataflow(context, {"tool": tool, "arguments": arguments})
    reasons.extend(dataflow.reasons)
    reasons.extend(dataflow.labels)

    if tool == "read_file":
        return _decide_read_file(arguments, reasons)
    if tool == "write_file":
        return _decide_write_file(arguments, reasons)
    if tool == "send_email":
        return _decide_send_email(arguments, dataflow.canary_exfiltration, dataflow.exfiltration, reasons)
    if tool == "call_api":
        return _decide_call_api(arguments, dataflow.canary_exfiltration, dataflow.exfiltration, reasons)
    if tool == "run_code":
        reasons.append("code_execution_disabled")
        return PolicyResult("deny", 1.0, _unique(reasons), forced=True)

    return PolicyResult("deny", 0.85, _unique(reasons or ["unknown_tool"]), forced=True)


def _decide_read_file(arguments: dict[str, Any], reasons: list[str]) -> PolicyResult:
    path = arguments.get("path", "")
    normalized_path = normalize_path(path)
    if not is_sandbox_path(path):
        reasons.append("non_sandbox_path")
        return PolicyResult("deny", 0.95, _unique(reasons), forced=True)
    if is_secret_path(path):
        reasons.append("secret_path_access")
        return PolicyResult("deny", 0.95, _unique(reasons), forced=True)
    if _is_public_path(normalized_path):
        reasons.append("sandbox_public_read_allowed")
        return PolicyResult("allow", 0.25, _unique(reasons))
    reasons.append("sandbox_file_access_requires_review")
    return PolicyResult("ask", 0.35, _unique(reasons))


def _decide_write_file(arguments: dict[str, Any], reasons: list[str]) -> PolicyResult:
    path = arguments.get("path", "")
    normalized_path = normalize_path(path)
    if not is_sandbox_path(path):
        reasons.append("non_sandbox_path")
        return PolicyResult("deny", 0.95, _unique(reasons), forced=True)
    if is_secret_path(path):
        reasons.append("secret_path_access")
        return PolicyResult("deny", 0.95, _unique(reasons), forced=True)
    if contains_sensitive_data(arguments.get("content", "")):
        reasons.extend(["attempt_to_persist_secret_or_canary", "unsafe_write_content"])
        return PolicyResult("deny", 0.95, _unique(reasons), forced=True)
    if _is_public_path(normalized_path):
        reasons.append("sandbox_public_write_requires_review")
        return PolicyResult("ask", 0.40, _unique(reasons))
    reasons.append("sandbox_write_requires_review")
    return PolicyResult("ask", 0.40, _unique(reasons))


def _decide_send_email(
    arguments: dict[str, Any],
    canary_exfiltration: bool,
    sensitive_flow: bool,
    reasons: list[str],
) -> PolicyResult:
    reasons.append("external_side_effect_tool")
    if canary_exfiltration:
        reasons.append("canary_exfiltration")
        return PolicyResult("deny", 0.95, _unique(reasons), forced=True)
    if sensitive_flow or contains_sensitive_data(arguments):
        reasons.append("sensitive_data_flow_detected")
        return PolicyResult("deny", 0.95, _unique(reasons), forced=True)
    return PolicyResult("ask", 0.55, _unique(reasons))


def _decide_call_api(
    arguments: dict[str, Any],
    canary_exfiltration: bool,
    sensitive_flow: bool,
    reasons: list[str],
) -> PolicyResult:
    reasons.append("external_side_effect_tool")
    endpoint = normalize_text(arguments.get("endpoint", ""))
    if not _is_mock_endpoint(endpoint):
        reasons.append("non_mock_endpoint")
        return PolicyResult("deny", 0.95, _unique(reasons), forced=True)
    if canary_exfiltration:
        reasons.append("canary_exfiltration")
        return PolicyResult("deny", 0.95, _unique(reasons), forced=True)
    if sensitive_flow or contains_sensitive_data(arguments.get("params", arguments)):
        reasons.append("sensitive_data_flow_detected")
        return PolicyResult("deny", 0.95, _unique(reasons), forced=True)
    reasons.append("mock_endpoint_requires_review")
    return PolicyResult("ask", 0.55, _unique(reasons))


def _is_public_path(path: str) -> bool:
    return path == "sandbox/public" or path.startswith("sandbox/public/") or path == "public" or path.startswith("public/")


def _is_mock_endpoint(endpoint: str) -> bool:
    return (
        endpoint == "/mock"
        or endpoint == "mock"
        or endpoint.startswith("/mock/")
        or endpoint.startswith("mock/")
        or endpoint.startswith("mock://")
    )


def decision_rank(decision: str) -> int:
    if decision == "deny":
        return 2
    if decision == "ask":
        return 1
    return 0


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result
