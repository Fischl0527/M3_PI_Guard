from __future__ import annotations

import json

import pytest

from experiments.paper_v2 import formal_matrix_abort_review_v1 as abort_review
from experiments.paper_v2 import formal_matrix_controller_v5 as v5
from experiments.paper_v2.provider_budget import (
    check_deepseek_headroom,
    validate_policy,
)


def test_v5_controller_qualification_reproduces_without_network() -> None:
    value = v5.verify_controller_qualification()

    assert value["network_calls_made"] == 0
    assert value["boundary_rejection_records"] == 1
    assert value["rejected_effects_executed"] == 0
    assert value["boundary_online_allow_preserved"] is True
    assert value["unsafe_effect_itt_for_rejection"] is True
    assert value["task_completion_for_rejection"] is False


def test_v5_candidate_is_non_executable_and_binds_blocked_v4() -> None:
    value = v5.verify_matrix_candidate()
    scope = value["scope"]

    assert value["authorization"] == {
        "candidate_only": True,
        "canary_execution_authorized": False,
        "matrix_continuation_authorized": False,
        "result_admission_authorized": False,
        "candidate_manifest_sha256": None,
        "canary_review_sha256": None,
        "owner_approval": None,
    }
    assert scope["replaces_aborted_run"]["old_run_resumable"] is False
    assert (
        scope["replaces_aborted_run"]["old_records_result_eligible"]
        is False
    )
    assert (
        scope["boundary_rejection_semantics"][
            "provider_safety_policy_modified"
        ]
        is False
    )
    assert (
        scope["boundary_rejection_semantics"]["rejected_effect_executed"]
        is False
    )


def test_v5_canary_admission_is_separate_and_result_closed() -> None:
    value = v5.build_canary_admission()
    authorization = value["authorization"]

    assert authorization["candidate_only"] is False
    assert authorization["canary_execution_authorized"] is True
    assert authorization["matrix_continuation_authorized"] is False
    assert authorization["result_admission_authorized"] is False
    assert (
        authorization["owner_approval"]["approval_scope"]
        == "deepseek_v5_six_condition_canary"
    )


def test_v5_budget_revision_keeps_money_cap_and_actual_fuse() -> None:
    policy = json.loads(
        v5.DEFAULT_BUDGET_POLICY.read_text(encoding="utf-8")
    )
    validate_policy(policy)
    headroom = check_deepseek_headroom(
        policy,
        {
            "prompt_tokens": 500382,
            "prompt_cache_hit_tokens": 356352,
            "prompt_cache_miss_tokens": 144030,
            "completion_tokens": 50589,
        },
    )

    assert policy["deepseek"]["hard_spend_limit_cny"] == 30.0
    assert policy["deepseek"]["abort_ceiling_cny"] == 27.0
    assert policy["deepseek"]["untouched_reserve_cny"] == 3.0
    assert headroom["status"] == "continue"
    assert headroom["projected_full_plan_cost_cny"] is None
    assert headroom["actual_cost_cny"] == pytest.approx(0.744533)


def test_v5_stopped_state_is_nonresumable_and_abort_review_replays() -> None:
    with pytest.raises(
        v5.FormalMatrixControllerV5Error,
        match="attempt and record ledgers are not aligned",
    ):
        v5.matrix_status(
            v5.DEFAULT_CANARY_ADMISSION,
            required_scope="canary",
        )

    review = abort_review.verify_abort_review()
    assert review["status"] == (
        "aborted_result_ineligible_new_version_required"
    )
    assert review["operational_summary"]["record_count"] == 94
    assert review["operational_summary"]["open_attempt_count"] == 1
    assert review["evidence_boundary"]["prior_run_resumable"] is False
    assert review["evidence_boundary"]["scientific_outcomes_reviewed"] is False
