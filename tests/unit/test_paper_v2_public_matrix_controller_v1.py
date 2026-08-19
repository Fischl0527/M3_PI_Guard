from __future__ import annotations

import copy
from pathlib import Path

import pytest

from experiments.paper_v2.public_matrix_controller_v1 import (
    build_candidate,
    build_controller_qualification,
    validate_candidate,
    verify_candidate,
    verify_controller_qualification,
    write_candidate,
    write_controller_qualification,
)


def test_public_controller_qualification_is_offline_and_complete() -> None:
    value = build_controller_qualification()

    assert value["plan"]["records"] == 6873
    assert value["condition_shells"]["qualified_pairs"] == 18
    assert value["provider_trace"]["primary"]["model_id"] == (
        "deepseek-v4-pro"
    )
    assert value["provider_trace"]["second"]["model_id"] == (
        "deepseek-v4-flash"
    )
    assert value["negative_coverage"]["expanded_budget_rejected"] is True
    assert value["negative_coverage"]["existing_trace_path_rejected"] is True
    assert value["evidence_boundary"] == {
        "credentials_read": False,
        "network_calls_made": 0,
        "model_calls_made": 0,
        "experiment_records_persisted": 0,
        "formal_results_created": 0,
        "scientific_outcomes_accessed": False,
    }


def test_public_candidate_is_non_executable() -> None:
    value = build_candidate()

    assert value["scope"]["records"] == 6873
    assert value["authorization"] == {
        "candidate_only": True,
        "canary_execution_authorized": False,
        "matrix_continuation_authorized": False,
        "result_admission_authorized": False,
        "active_admission_present": False,
    }
    assert value["scope"]["execution_order"][0] == "primary_canary"
    assert value["scope"]["budget"]["incremental_hard_limit_cny"] == 25.0
    assert value["evidence_boundary"]["candidate_is_executable"] is False


def test_public_candidate_rejects_scope_digest_drift() -> None:
    value = build_candidate()
    drifted = copy.deepcopy(value)
    drifted["scope"]["records"] = 6872

    with pytest.raises(Exception):
        validate_candidate(drifted)


def test_public_controller_artifacts_write_and_verify(
    tmp_path: Path,
) -> None:
    qualification = tmp_path / "qualification.json"
    candidate = tmp_path / "candidate.json"

    assert write_controller_qualification(qualification) == (
        verify_controller_qualification(qualification)
    )
    # Candidate locks the canonical qualification by design; write/verify the
    # candidate only after the canonical Stage-A artifact is present.
    assert write_candidate(candidate) == verify_candidate(candidate)
