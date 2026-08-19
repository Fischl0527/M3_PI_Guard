from __future__ import annotations

import copy
from pathlib import Path

import pytest

from experiments.paper_v2.deepseek_nonthinking_client_v1 import (
    THINKING_CONTROL,
    build_qualification as build_client_qualification,
    verify_qualification as verify_client_qualification,
)
from experiments.paper_v2.formal_matrix_controller_v2 import (
    FailureAwareOutcomeEvaluator,
    FormalMatrixControllerV2Error,
    authorize_matrix,
    build_controller_qualification,
    build_matrix_candidate,
    execute_canary,
    matrix_status,
    validate_matrix_manifest,
    verify_controller_qualification,
    verify_matrix_candidate,
)


def test_nonthinking_client_qualification_reproduces() -> None:
    value = verify_client_qualification()
    assert value == build_client_qualification()
    assert value["thinking_payload"] == THINKING_CONTROL
    assert value["thinking_mode_persisted"] == "disabled"
    assert value["provider_attempts"] == 1
    assert value["network_calls_made"] == 0


def test_matrix_v2_controller_qualification_reproduces() -> None:
    value = verify_controller_qualification()
    assert value == build_controller_qualification()
    assert value["nonthinking_payloads_observed"] == 2
    assert value["operational_failure_delegate_calls"] == 0
    assert value["operational_failure_retained_for_itt"] is True
    assert value["v1_run_resumed"] is False
    assert value["network_calls_made"] == 0


def test_matrix_v2_candidate_reproduces_and_replaces_v1() -> None:
    value = verify_matrix_candidate()
    assert value == build_matrix_candidate()
    assert value["scope"]["provider"]["thinking_mode"] == "disabled"
    assert value["scope"]["budget"]["prior_project_cost_cny"] == 0.0200974
    assert value["scope"]["canary"]["work_items"] == 6
    assert value["scope"]["replaces_aborted_run"]["old_run_resumable"] is False
    assert value["authorization"]["canary_execution_authorized"] is False
    assert value["authorization"]["matrix_continuation_authorized"] is False
    assert value["authorization"]["result_admission_authorized"] is False


def test_failure_aware_evaluator_does_not_call_delegate() -> None:
    calls = 0

    class Delegate:
        def evaluate(self, *_args, **_kwargs):
            nonlocal calls
            calls += 1
            raise AssertionError

    outcome = FailureAwareOutcomeEvaluator(Delegate()).evaluate(
        {},
        {"operational_status": "provider_failure"},
    )
    assert calls == 0
    assert outcome["unsafe_effect"] is None
    assert outcome["task_completion"] is False


def test_aborted_v2_canary_cannot_resume_or_report_status() -> None:
    admission = Path(
        "protocols/paper_upgrade_v2/admissions/"
        "deepseek_medium_matrix_canary_admission_v2.json"
    )
    with pytest.raises(
        FormalMatrixControllerV2Error,
        match="open matrix-v2 attempt requires a new version",
    ):
        authorize_matrix(admission, required_scope="canary")
    with pytest.raises(
        FormalMatrixControllerV2Error,
        match="open matrix-v2 attempt requires a new version",
    ):
        matrix_status(admission, required_scope="canary")


def test_missing_canary_admission_rejects_before_credentials(
    tmp_path: Path,
) -> None:
    reads = 0

    def credential_loader() -> dict[str, str]:
        nonlocal reads
        reads += 1
        return {}

    with pytest.raises(
        FormalMatrixControllerV2Error,
        match="active matrix-v2 admission is missing",
    ):
        execute_canary(
            tmp_path / "missing.json",
            credential_loader=credential_loader,
        )
    assert reads == 0


def test_matrix_v2_manifest_digest_tamper_is_rejected() -> None:
    value = copy.deepcopy(build_matrix_candidate())
    value["next_gate"] = "tampered"
    with pytest.raises(
        FormalMatrixControllerV2Error,
        match="matrix-v2 manifest digest drift",
    ):
        validate_matrix_manifest(value)
