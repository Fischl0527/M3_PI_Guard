"""Sensitive-data flow checks for the local M3 Guard."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .normalizer import normalize_path, normalize_text


CANARY_MARKERS = (
    "m3_synthetic_canary",
    "local-redteam-fixture",
    "m3_canary",
    "sk-local-redteam-demo-not-real",
)
API_KEY_MARKERS = ("api_key", "apikey", "secret_api_key")
TOKEN_MARKERS = ("token", "bearer ")
PASSWORD_MARKERS = ("password", "passwd", "pwd=")
SECRET_MARKERS = ("secret",)

EXFIL_TOOLS = {"send_email", "call_api"}


@dataclass(frozen=True)
class DataflowFinding:
    risk_delta: float
    reasons: list[str]
    labels: list[str]
    contains_sensitive: bool = False
    exfiltration: bool = False
    canary_exfiltration: bool = False


def contains_sensitive_data(text: Any) -> bool:
    """Return True if text contains local canary or common secret markers."""

    return bool(extract_data_labels(text))


def extract_data_labels(text: Any) -> list[str]:
    """Extract coarse labels for sensitive data seen in text."""

    normalized = normalize_text(text)
    labels: list[str] = []

    if _has_any(normalized, CANARY_MARKERS):
        labels.append("secret.canary")
    if _has_any(normalized, API_KEY_MARKERS):
        labels.append("secret.api_key")
    if _has_any(normalized, TOKEN_MARKERS):
        labels.append("secret.token")
    if _has_any(normalized, PASSWORD_MARKERS):
        labels.append("secret.password")
    if "secret" in normalized and not any(label.startswith("secret.") for label in labels):
        labels.append("file.secret_content")
    if _looks_like_secret_file_content(normalized):
        labels.append("file.secret_content")

    return _unique(labels)


def detect_sensitive_flow(context: dict[str, Any], tool_call: dict[str, Any]) -> list[str]:
    """Detect sensitive labels flowing from observations into external tools."""

    if not isinstance(context, dict):
        context = {}
    if not isinstance(tool_call, dict):
        return []

    tool = str(tool_call.get("tool", "")).strip()
    arguments = tool_call.get("arguments")
    if not isinstance(arguments, dict):
        arguments = {}

    labels: list[str] = []
    argument_labels = extract_data_labels(arguments)
    observation_labels = extract_data_labels(context.get("observations", []))
    labels.extend(argument_labels)

    if "secret.canary" in observation_labels:
        labels.append("secret.canary")

    if tool == "send_email":
        body_labels = extract_data_labels(arguments.get("body", ""))
        labels.extend(body_labels)
        if body_labels or observation_labels:
            labels.append("external.destination")

    if tool == "call_api":
        params = arguments.get("params", arguments)
        params_labels = extract_data_labels(params)
        labels.extend(params_labels)
        if params_labels or observation_labels:
            labels.append("external.destination")

    if tool in EXFIL_TOOLS and observation_labels:
        labels.extend(observation_labels)
        labels.append("file.secret_content")
        labels.append("external.destination")

    return _unique(labels)


def is_secret_path(path: Any) -> bool:
    normalized = normalize_path(path)
    return (
        normalized == "sandbox/secrets"
        or normalized.startswith("sandbox/secrets/")
        or normalized == "secrets"
        or normalized.startswith("secrets/")
    )


def is_sandbox_path(path: Any) -> bool:
    normalized = normalize_path(path)
    if ".." in normalized:
        return False
    return normalized.startswith("sandbox/") or normalized.startswith("public/") or normalized.startswith("secrets/")


def analyze_dataflow(context: dict[str, Any], tool_call: dict[str, Any]) -> DataflowFinding:
    tool = str(tool_call.get("tool", "")).strip() if isinstance(tool_call, dict) else ""
    arguments = tool_call.get("arguments") if isinstance(tool_call, dict) else {}
    if not isinstance(arguments, dict):
        arguments = {}

    labels = detect_sensitive_flow(context, {"tool": tool, "arguments": arguments})
    observation_labels = extract_data_labels(context.get("observations", [])) if isinstance(context, dict) else []
    argument_labels = extract_data_labels(arguments)
    reasons: list[str] = []

    if "secret.canary" in observation_labels:
        reasons.append("observation_contains_canary")
    if argument_labels:
        reasons.append("tool_arguments_contain_sensitive_data")
    if observation_labels:
        reasons.append("prior_observation_contains_sensitive_data")
    if tool == "send_email" and "secret.canary" in extract_data_labels(arguments.get("body", "")):
        reasons.append("email_body_contains_canary")
    if tool == "call_api" and extract_data_labels(arguments.get("params", arguments)):
        reasons.append("api_params_contain_sensitive_data")
    if tool in EXFIL_TOOLS and observation_labels:
        reasons.append("file_read_result_flows_to_external_tool")
    if tool in EXFIL_TOOLS and labels:
        reasons.append("sensitive_data_flow_detected")

    contains_sensitive = bool(labels or argument_labels or observation_labels)
    exfiltration = tool in EXFIL_TOOLS and contains_sensitive
    canary_exfiltration = tool in EXFIL_TOOLS and "secret.canary" in labels
    risk_delta = 0.45 if exfiltration else 0.0

    return DataflowFinding(
        risk_delta=risk_delta,
        reasons=_unique(reasons),
        labels=labels,
        contains_sensitive=contains_sensitive,
        exfiltration=exfiltration,
        canary_exfiltration=canary_exfiltration,
    )


def _has_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def _looks_like_secret_file_content(text: str) -> bool:
    return "m3_canary_secret_api_key" in text or "secret_api_key" in text


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result
