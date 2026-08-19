from __future__ import annotations

import copy

import pytest

from experiments.paper_v2 import gemini_public_continuation_plan_v2 as plan


@pytest.fixture(scope="module")
def frozen_candidate() -> dict:
    return plan.build_candidate()


def test_candidate_preserves_schedule_and_switches_to_v5_gate(
    frozen_candidate: dict,
) -> None:
    value = copy.deepcopy(frozen_candidate)
    scope = value["scope"]

    assert scope["matrix_records"] == 1_791
    assert scope["formal_canary_prefix_records"] == 12
    assert scope["pending_only_records"] == 1_779
    assert scope["standard_free_tier_quota_segments"] == 1_186
    assert scope["minimum_standard_quota_days_after_canary"] == 1_186
    assert scope["activation_gate"] == {
        "required_review_schema": plan.review_v5.AGGREGATE_SCHEMA_VERSION,
        "required_status": "gemini_public_v5_canary_technical_gate_pass",
        "required_records": 12,
        "aggregate_review_path": plan._display_path(
            plan.review_v5.AGGREGATE_REVIEW_PATH
        ),
        "v4_aggregate_gate_superseded": True,
    }
    assert value["authorization"]["batch_api_authorized"] is False
    assert value["authorization"]["paid_billing_authorized"] is False


def test_candidate_rejects_paid_or_batch_activation(frozen_candidate: dict) -> None:
    value = copy.deepcopy(frozen_candidate)
    for field in ("batch_api_authorized", "paid_billing_authorized"):
        tampered = copy.deepcopy(value)
        tampered["authorization"][field] = True
        with pytest.raises(plan.GeminiPublicContinuationPlanV2Error):
            plan.validate_candidate(tampered)


def test_candidate_rejects_optimistic_calendar_compression(
    frozen_candidate: dict,
) -> None:
    value = copy.deepcopy(frozen_candidate)
    value["scope"]["minimum_standard_quota_days_after_canary"] = 21

    with pytest.raises(plan.GeminiPublicContinuationPlanV2Error):
        plan.validate_candidate(value)
