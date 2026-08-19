from __future__ import annotations

import copy

import pytest

import experiments.paper_v2.adaptive_cost_canary_controller_v2 as canary_v2
from experiments.paper_v2.adaptive_result_gate_v2 import (
    AdaptiveResultGateV2Error,
    _conservative_query_cost,
    validate_technical_review_for_continuation,
    verify_adaptive_result_gate,
)
from experiments.paper_v2.contracts import sha256_canonical_json


def _passing_review() -> dict:
    candidate = canary_v2.verify_candidate()
    core = {
        "schema_version": (
            "m3-paper-v2-adaptive-technical-cost-review-2.0"
        ),
        "artifact_role": "outcome_blind_adaptive_cost_review",
        "reviewed_at": "2026-07-30T03:00:00+08:00",
        "run_id": canary_v2.RUN_ID,
        "execution_identity": candidate["execution_identity"],
        "admission_file_sha256": canary_v2._sha256_file(
            canary_v2.ADMISSION_PATH
        ),
        "technical_gate_passed": True,
        "task_execution_complete_count": 8,
        "expected_task_count": 8,
        "terminal_query_count": 237,
        "maximum_queries": 400,
        "completed_provider_call_count": 480,
        "cumulative_cost_cny": 2.5,
        "hard_limit_cny": 5.0,
        "query_ledger_tail_sha256": "1" * 64,
        "budget_ledger_tail_sha256": "2" * 64,
        "query_call_cross_binding_complete": True,
        "old_v1_query_records_reused": False,
        "scientific_outcomes_aggregated": False,
        "scientific_result_admission_authorized": False,
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def test_fresh_adaptive_gate_is_frozen_outcome_blind() -> None:
    gate = verify_adaptive_result_gate()

    assert gate["inputs"]["run_id"] == "adaptive-cost-canary-primary-v2"
    assert gate["inputs"]["adaptive_maximum_query_budget"] == 75_000
    assert gate["authorization"][
        "formal_continuation_authorized"
    ] is False
    assert gate["authorization"][
        "scientific_outcome_access_authorized"
    ] is False
    assert gate["cost_projection_rule"]["projection_uses_outcomes"] is False


def test_fresh_adaptive_gate_accepts_exact_technical_review() -> None:
    review = _passing_review()

    assert validate_technical_review_for_continuation(review) == review


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("technical_gate_passed", False),
        ("execution_identity", "0" * 64),
        ("task_execution_complete_count", 7),
        ("query_call_cross_binding_complete", False),
        ("old_v1_query_records_reused", True),
        ("scientific_outcomes_aggregated", True),
        ("scientific_result_admission_authorized", True),
    ],
)
def test_fresh_adaptive_gate_rejects_boundary_drift(
    field: str,
    value: object,
) -> None:
    review = copy.deepcopy(_passing_review())
    review[field] = value
    core = {
        key: child
        for key, child in review.items()
        if key != "manifest_sha256"
    }
    review["manifest_sha256"] = sha256_canonical_json(core)

    with pytest.raises(AdaptiveResultGateV2Error):
        validate_technical_review_for_continuation(review)


def test_fresh_adaptive_gate_rejects_manifest_or_count_drift() -> None:
    manifest_drift = _passing_review()
    manifest_drift["manifest_sha256"] = "f" * 64
    with pytest.raises(AdaptiveResultGateV2Error):
        validate_technical_review_for_continuation(manifest_drift)

    over_query = _passing_review()
    over_query["terminal_query_count"] = 401
    core = {
        key: child
        for key, child in over_query.items()
        if key != "manifest_sha256"
    }
    over_query["manifest_sha256"] = sha256_canonical_json(core)
    with pytest.raises(AdaptiveResultGateV2Error):
        validate_technical_review_for_continuation(over_query)


def test_cost_projection_rule_is_deterministic_and_conservative() -> None:
    small = _conservative_query_cost([0.1, 0.2, 0.3])
    assert small["method"] == "small_sample_1_25_times_maximum"
    assert small["conservative_query_cost_cny"] == 0.375

    large = _conservative_query_cost([float(index) for index in range(1, 31)])
    assert (
        large["method"]
        == "maximum_of_nearest_rank_p95_and_upper_mean"
    )
    assert large["conservative_query_cost_cny"] >= (
        large["empirical_p95_query_cost_cny"]
    )


def test_cost_projection_rule_rejects_empty_or_negative_costs() -> None:
    with pytest.raises(AdaptiveResultGateV2Error):
        _conservative_query_cost([])
    with pytest.raises(AdaptiveResultGateV2Error):
        _conservative_query_cost([0.1, -0.1])
