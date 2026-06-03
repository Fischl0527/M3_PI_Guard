"""Public Guard interface for M3_PI_Guard."""

from __future__ import annotations

from typing import Any

from .policy_engine import VALID_DECISIONS, decide


def guard_decide(context: dict[str, Any], tool_call: dict[str, Any]) -> tuple[str, float, list[str]]:
    """Return allow/ask/deny, a 0..1 risk score, and human-readable reason codes."""

    result = decide(context, tool_call)
    decision = result.decision if result.decision in VALID_DECISIONS else "deny"
    risk = round(max(0.0, min(1.0, float(result.risk))), 4)
    return decision, risk, list(result.reasons)
