from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from experiments.paper_v2.formal_matrix_controller_v1 import (
    FormalMatrixControllerError,
    authorize_matrix,
    build_controller_qualification,
    build_matrix_candidate,
    execute_admitted_matrix,
    matrix_status,
    validate_matrix_manifest,
    verify_controller_qualification,
    verify_matrix_candidate,
)


def _write(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def test_frozen_matrix_candidate_reproduces_and_cannot_execute() -> None:
    value = verify_matrix_candidate()
    assert value == build_matrix_candidate()
    assert value["scope"]["plan"]["work_items"] == 480
    assert value["scope"]["plan"]["primary_records"] == 432
    assert value["scope"]["plan"]["authorization_regime_probes"] == 48
    assert value["scope"]["plan"]["provider_calls_upper_bound"] == 4416
    assert value["scope"]["provider"]["concurrency"] == 1
    assert value["scope"]["provider"]["automatic_retries"] == 0
    assert value["scope"]["provider"]["cross_provider_fallback"] is False
    assert value["authorization"]["candidate_only"] is True
    assert value["authorization"]["matrix_execution_authorized"] is False
    assert value["authorization"]["result_admission_authorized"] is False


def test_controller_qualification_reproduces_without_network() -> None:
    value = verify_controller_qualification()
    assert value == build_controller_qualification()
    assert value["work_items_executed"] == 2
    assert value["provider_calls_completed"] == 2
    assert value["negative_cases_rejected"] == [
        "budget_cost_tamper",
        "open_attempt_auto_resume",
        "pending_trace_reuse",
    ]
    assert value["credentials_read"] == 0
    assert value["network_calls_made"] == 0
    assert value["formal_results_created"] == 0


def test_aborted_v1_admission_cannot_resume_open_attempt() -> None:
    with pytest.raises(
        FormalMatrixControllerError,
        match="open matrix attempt requires explicit recovery",
    ):
        authorize_matrix()
    with pytest.raises(
        FormalMatrixControllerError,
        match="open matrix attempt requires explicit recovery",
    ):
        matrix_status()


def test_missing_active_admission_rejects_before_credentials(
    tmp_path: Path,
) -> None:
    credential_reads = 0

    def credential_loader() -> dict[str, str]:
        nonlocal credential_reads
        credential_reads += 1
        return {}

    with pytest.raises(
        FormalMatrixControllerError,
        match="active DeepSeek matrix admission is missing",
    ):
        execute_admitted_matrix(
            tmp_path / "missing-active.json",
            credential_loader=credential_loader,
        )
    assert credential_reads == 0


def test_candidate_cannot_be_substituted_for_active_admission(
    tmp_path: Path,
) -> None:
    candidate = build_matrix_candidate()
    candidate_path = tmp_path / "candidate.json"
    _write(candidate_path, candidate)
    with pytest.raises(
        FormalMatrixControllerError,
        match="deepseek_medium_matrix_execution_authorization",
    ):
        authorize_matrix(
            candidate_path,
            candidate_path=candidate_path,
        )


def test_manifest_digest_tamper_is_rejected() -> None:
    value = copy.deepcopy(build_matrix_candidate())
    value["next_gate"] = "tampered"
    with pytest.raises(
        FormalMatrixControllerError,
        match="matrix manifest digest drift",
    ):
        validate_matrix_manifest(value)
