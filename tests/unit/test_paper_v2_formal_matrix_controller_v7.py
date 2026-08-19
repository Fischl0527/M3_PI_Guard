from __future__ import annotations

import pytest

from experiments.paper_v2 import formal_matrix_controller_v7 as v7
from experiments.paper_v2.formal_matrix_abort_review_v3 import (
    verify_abort_review,
)


def test_v7_controller_qualification_is_end_to_end() -> None:
    value = v7.verify_controller_qualification()

    assert value["network_calls_made"] == 0
    assert value["scientific_outcomes_read"] == 0
    assert value["end_to_end_backend_to_evaluator_scenarios"] == 6
    assert value["nonproposal_integrity_messages_reclassified"] == 0


def test_v7_candidate_binds_v6_abort_and_new_adapter() -> None:
    value = v7.verify_matrix_candidate()
    scope = value["scope"]

    assert scope["replaces_aborted_run"]["run_id"].endswith(
        "v6-20260724"
    )
    assert scope["replaces_aborted_run"]["old_run_resumable"] is False
    assert (
        scope["boundary_rejection_semantics"][
            "end_to_end_evidence_validation"
        ]
        is True
    )
    assert scope["budget"]["prior_project_cost_cny"] == 0.9066668
    assert value["authorization"]["result_admission_authorized"] is False


def test_v7_canary_admission_is_separate_and_result_closed() -> None:
    value = v7.verify_canary_admission()

    assert value["authorization"]["canary_execution_authorized"] is True
    assert (
        value["authorization"]["matrix_continuation_authorized"] is False
    )
    assert value["authorization"]["result_admission_authorized"] is False


def test_v7_frozen_aborted_state_rejects_resume_without_network() -> None:
    candidate = v7.verify_matrix_candidate()
    root = v7.PROJECT_ROOT / candidate["scope"]["outputs"]["root"]
    credential_reads = 0

    def forbidden_loader() -> dict[str, str]:
        nonlocal credential_reads
        credential_reads += 1
        raise AssertionError("credentials must remain unread")

    with pytest.raises(
        v7.FormalMatrixControllerV7Error,
        match="open matrix-v2 attempt requires a new version",
    ):
        v7.execute_canary(credential_loader=forbidden_loader)

    review = verify_abort_review()

    assert not (root / "experiment_records_v2.jsonl").exists()
    assert (root / "matrix_attempts_v1.jsonl").exists()
    assert (root / "matrix_budget_v1.jsonl").exists()
    assert len(list((root / "provider_traces").glob("*.jsonl"))) == 1
    assert review["operational_summary"]["record_count"] == 0
    assert review["operational_summary"]["open_attempt_count"] == 1
    assert review["operational_summary"]["provider_calls_completed"] == 2
    assert review["evidence_boundary"]["prior_run_resumable"] is False
    assert credential_reads == 0
