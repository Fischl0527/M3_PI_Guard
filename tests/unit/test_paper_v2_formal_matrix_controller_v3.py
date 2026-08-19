from __future__ import annotations

import copy
from pathlib import Path

import pytest

from experiments.paper_v2.formal_matrix_controller_v3 import (
    PRIOR_PROJECT_COST_CNY,
    PRIOR_PROJECT_USAGE,
    FormalMatrixControllerV3Error,
    authorize_matrix,
    build_canary_admission,
    build_controller_qualification,
    build_matrix_candidate,
    execute_canary,
    validate_matrix_manifest,
    verify_canary_admission,
    verify_controller_qualification,
    verify_matrix_candidate,
)


def test_matrix_v3_controller_qualification_reproduces() -> None:
    value = verify_controller_qualification()
    assert value == build_controller_qualification()
    assert value["trusted_context_path_observed"] is True
    assert value["evaluator_or_gold_fields_exposed"] is False
    assert value["post_response_failure_records"] == 1
    assert value["post_response_failure_status"] == "runner_failure"
    assert value["post_response_failure_unsafe_effect_itt"] is True
    assert value["open_attempts_after_failure"] == 0
    assert value["network_calls_made"] == 0


def test_matrix_v3_candidate_reproduces_and_replaces_v2() -> None:
    value = verify_matrix_candidate()
    assert value == build_matrix_candidate()
    assert value["scope"]["budget"]["prior_project_usage"] == (
        PRIOR_PROJECT_USAGE
    )
    assert value["scope"]["budget"]["prior_project_cost_cny"] == (
        PRIOR_PROJECT_COST_CNY
    )
    assert value["scope"]["replaces_aborted_run"]["run_id"] == (
        "paper-v2-deepseek-medium-v2-20260724"
    )
    assert value["scope"]["replaces_aborted_run"]["old_run_resumable"] is False
    assert value["scope"]["trusted_context_prompt"][
        "evaluator_or_gold_fields"
    ] is False
    assert value["scope"]["failure_persistence"][
        "response_content_persisted"
    ] is False
    assert value["authorization"]["canary_execution_authorized"] is False
    assert value["authorization"]["result_admission_authorized"] is False


def test_failed_matrix_v3_canary_cannot_execute_again() -> None:
    value = verify_canary_admission()
    assert value == build_canary_admission()
    authorization = authorize_matrix(
        Path(
            "protocols/paper_upgrade_v2/admissions/"
            "deepseek_medium_matrix_canary_admission_v3.json"
        ),
        required_scope="canary",
    )
    assert authorization.authorization_scope == "canary"
    assert len(authorization.permit.work_items) == 480
    assert authorization.permit.record_ledger_path.exists()
    with pytest.raises(
        FormalMatrixControllerV3Error,
        match="six-condition canary is single-use and already started",
    ):
        execute_canary(
            Path(
                "protocols/paper_upgrade_v2/admissions/"
                "deepseek_medium_matrix_canary_admission_v3.json"
            ),
            credential_loader=lambda: {},
        )


def test_matrix_v3_manifest_digest_tamper_is_rejected() -> None:
    value = copy.deepcopy(build_matrix_candidate())
    value["next_gate"] = "tampered"
    with pytest.raises(
        FormalMatrixControllerV3Error,
        match="matrix-v3 manifest digest drift",
    ):
        validate_matrix_manifest(value)


def test_missing_v3_canary_admission_rejects_before_credentials(
    tmp_path: Path,
) -> None:
    reads = 0

    def credential_loader() -> dict[str, str]:
        nonlocal reads
        reads += 1
        return {}

    with pytest.raises(
        FormalMatrixControllerV3Error,
        match="active matrix-v3 admission is missing",
    ):
        execute_canary(
            tmp_path / "missing.json",
            credential_loader=credential_loader,
        )
    assert reads == 0
