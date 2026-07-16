"""Separate runtime-visible case data from offline evaluation labels.

AttackCase rows intentionally contain both the task presented to an Agent and
labels used by the evaluator.  Passing the original dictionary through the
runtime makes it very easy to leak an answer field into a prompt or a Guard.
This module provides the only two supported projections of an AttackCase.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict


RUNTIME_CASE_FIELDS = (
    "user_task",
    "document_content",
    "requires_tool",
    "authorized_actions",
    "conversation_turns",
)

EVALUATION_FIELDS = (
    "case_id",
    "sample_type",
    "template_id",
    "split",
    "mutation_id",
    "attack_family",
    "carrier",
    "language",
    "expected_safe_behavior",
    "unsafe_target_actions",
    "risk_tags",
    "severity",
    "expected_detectors",
    "success_indicators",
    "safe_indicators",
    "notes",
)

# These fields are especially dangerous because their value directly describes
# the intended answer or detector outcome.  Tests use this list as a contract.
FORBIDDEN_RUNTIME_FIELDS = frozenset(
    {
        "case_id",
        "sample_type",
        "template_id",
        "split",
        "mutation_id",
        "attack_family",
        "carrier",
        "language",
        "injected_content",
        "expected_safe_behavior",
        "unsafe_target_actions",
        "risk_tags",
        "severity",
        "expected_detectors",
        "success_indicators",
        "safe_indicators",
        "notes",
    }
)


def runtime_case_view(case: Dict[str, Any] | None) -> Dict[str, Any]:
    """Return an allow-listed copy safe for prompts and online Guard logic."""

    source = case if isinstance(case, dict) else {}
    view: Dict[str, Any] = {}
    for field in RUNTIME_CASE_FIELDS:
        if field in source:
            view[field] = deepcopy(source[field])

    view.setdefault("user_task", "")
    view.setdefault("document_content", "")
    view.setdefault("requires_tool", False)
    view.setdefault("authorized_actions", [])
    view.setdefault("conversation_turns", [])
    return view


def evaluation_metadata(case: Dict[str, Any] | None) -> Dict[str, Any]:
    """Return labels retained for offline scoring, never runtime decisions."""

    source = case if isinstance(case, dict) else {}
    return {
        field: deepcopy(source[field])
        for field in EVALUATION_FIELDS
        if field in source
    }
