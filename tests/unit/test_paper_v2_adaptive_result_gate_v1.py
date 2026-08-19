from __future__ import annotations

import copy

import pytest

from experiments.paper_v2.adaptive_result_gate_v1 import (
    AdaptiveResultGateError,
    validate_technical_review_for_continuation,
    verify_adaptive_result_gate,
)


def _passing_review() -> dict:
    return {
        "technical_gate_passed": True,
        "expected_task_count": 8,
        "task_execution_complete_count": 8,
        "maximum_queries": 400,
        "terminal_query_count": 237,
        "cumulative_cost_cny": 2.5,
        "query_call_cross_binding_complete": True,
        "scientific_outcomes_aggregated": False,
        "scientific_result_admission_authorized": False,
    }


def test_adaptive_result_gate_is_frozen_before_network() -> None:
    gate = verify_adaptive_result_gate()

    assert gate["authorization"]["network_calls_made"] == 0
    assert gate["authorization"]["canary_execution_authorized"] is False
    assert gate["authorization"]["formal_continuation_authorized"] is False
    assert gate["formal_continuation_gate"][
        "new_exact_command_owner_admission_required"
    ] is True
    assert gate["cost_projection_rule"]["projection_uses_outcomes"] is False


def test_adaptive_result_gate_accepts_only_technical_pass() -> None:
    validate_technical_review_for_continuation(_passing_review())


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("technical_gate_passed", False),
        ("task_execution_complete_count", 7),
        ("query_call_cross_binding_complete", False),
        ("scientific_outcomes_aggregated", True),
        ("scientific_result_admission_authorized", True),
    ],
)
def test_adaptive_result_gate_rejects_boundary_drift(
    field: str,
    value: object,
) -> None:
    review = copy.deepcopy(_passing_review())
    review[field] = value

    with pytest.raises(AdaptiveResultGateError):
        validate_technical_review_for_continuation(review)


def test_adaptive_result_gate_rejects_cost_or_query_overrun() -> None:
    over_cost = _passing_review()
    over_cost["cumulative_cost_cny"] = 5.000001
    with pytest.raises(AdaptiveResultGateError):
        validate_technical_review_for_continuation(over_cost)

    over_query = _passing_review()
    over_query["terminal_query_count"] = 401
    with pytest.raises(AdaptiveResultGateError):
        validate_technical_review_for_continuation(over_query)
