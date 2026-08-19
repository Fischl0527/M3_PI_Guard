from __future__ import annotations

import pytest

from experiments.paper_v2 import formal_matrix_abort_review_v2 as abort_review
from experiments.paper_v2 import formal_matrix_controller_v6 as v6


def test_v6_qualification_covers_narrow_proposal_boundary() -> None:
    value = v6.build_controller_qualification()

    assert value["network_calls_made"] == 0
    assert value["proposal_effect_rejection_message_count"] == 6
    assert value["nonproposal_integrity_messages_reclassified"] == 0
    assert value["rejected_effects_executed"] == 0


def test_v6_candidate_replaces_stopped_v5_without_result_access() -> None:
    value = v6.build_matrix_candidate()
    scope = value["scope"]

    assert scope["replaces_aborted_run"]["run_id"].endswith("-v5-20260724")
    assert scope["replaces_aborted_run"]["old_run_resumable"] is False
    assert (
        scope["boundary_rejection_semantics"][
            "proposal_effect_rejection_messages"
        ]
        == sorted(v6.PROPOSAL_EFFECT_REJECTION_MESSAGES)
    )
    assert value["authorization"]["result_admission_authorized"] is False


def test_v6_canary_admission_is_separate() -> None:
    value = v6.build_canary_admission()

    assert value["authorization"]["canary_execution_authorized"] is True
    assert value["authorization"]["matrix_continuation_authorized"] is False
    assert value["authorization"]["result_admission_authorized"] is False
    assert (
        value["authorization"]["owner_approval"]["approval_scope"]
        == "deepseek_v6_six_condition_canary"
    )


def test_v6_frozen_aborted_state_rejects_resume_without_network() -> None:
    with pytest.raises(
        v6.FormalMatrixControllerV6Error,
        match="open matrix-v2 attempt requires a new version",
    ):
        v6.matrix_status(
            v6.DEFAULT_CANARY_ADMISSION,
            required_scope="canary",
        )

    review = abort_review.verify_abort_review()
    assert review["operational_summary"]["record_count"] == 64
    assert review["operational_summary"]["open_attempt_count"] == 1
    assert review["evidence_boundary"]["prior_run_resumable"] is False
    assert review["evidence_boundary"]["network_calls_made_by_review"] == 0
