from __future__ import annotations

import copy
from pathlib import Path

import pytest

from experiments.paper_v2.deepseek_json_client_v2 import (
    JSON_OUTPUT_CONTROL,
    build_qualification as build_json_client_qualification,
    verify_qualification as verify_json_client_qualification,
)
from experiments.paper_v2.formal_matrix_controller_v4 import (
    PRIOR_PROJECT_COST_CNY,
    PRIOR_PROJECT_USAGE,
    FormalMatrixControllerV4Error,
    build_canary_admission,
    build_controller_qualification,
    build_matrix_candidate,
    execute_canary,
    validate_matrix_manifest,
    verify_canary_admission,
    verify_controller_qualification,
    verify_matrix_candidate,
)


def test_deepseek_json_client_qualification_reproduces() -> None:
    value = verify_json_client_qualification()
    assert value == build_json_client_qualification()
    assert value["response_format_payload"] == JSON_OUTPUT_CONTROL
    assert value["thinking_payload"] == {"type": "disabled"}
    assert value["payload_and_commitment_match"] is True
    assert value["automatic_retries"] == 0
    assert value["network_calls_made"] == 0


def test_matrix_v4_controller_qualification_reproduces() -> None:
    value = verify_controller_qualification()
    assert value == build_controller_qualification()
    assert value["successful_work_items"] == 2
    assert value["provider_calls_completed"] == 4
    assert value["json_output_payloads_observed"] == 4
    assert value["nonthinking_payloads_observed"] == 4
    assert value["strict_parser_unchanged"] is True
    assert value["response_repair_allowed"] is False
    assert value["network_calls_made"] == 0


def test_matrix_v4_candidate_reproduces_and_replaces_v3() -> None:
    value = verify_matrix_candidate()
    assert value == build_matrix_candidate()
    assert value["scope"]["budget"]["prior_project_usage"] == (
        PRIOR_PROJECT_USAGE
    )
    assert value["scope"]["budget"]["prior_project_cost_cny"] == (
        PRIOR_PROJECT_COST_CNY
    )
    assert value["scope"]["replaces_aborted_run"]["run_id"] == (
        "paper-v2-deepseek-medium-v3-20260724"
    )
    assert value["scope"]["replaces_aborted_run"]["old_run_resumable"] is False
    assert value["scope"]["json_output"]["response_format"] == (
        JSON_OUTPUT_CONTROL
    )
    assert value["scope"]["json_output"]["strict_parser_unchanged"] is True
    assert value["scope"]["json_output"]["response_repair_allowed"] is False
    assert value["authorization"]["canary_execution_authorized"] is False
    assert value["authorization"]["result_admission_authorized"] is False


def test_matrix_v4_canary_admission_reproduces_and_has_started() -> None:
    value = verify_canary_admission()
    assert value == build_canary_admission()
    candidate = verify_matrix_candidate()
    output_root = Path(candidate["scope"]["outputs"]["root"])
    assert (output_root / "experiment_records_v2.jsonl").exists()
    assert (output_root / "matrix_attempts_v1.jsonl").exists()
    assert (output_root / "matrix_budget_v1.jsonl").exists()
    assert (output_root / "six_condition_canary_review_v4.json").exists()


def test_matrix_v4_manifest_digest_tamper_is_rejected() -> None:
    value = copy.deepcopy(build_matrix_candidate())
    value["next_gate"] = "tampered"
    with pytest.raises(
        FormalMatrixControllerV4Error,
        match="matrix-v4 manifest digest drift",
    ):
        validate_matrix_manifest(value)


def test_missing_v4_canary_admission_rejects_before_credentials(
    tmp_path: Path,
) -> None:
    reads = 0

    def credential_loader() -> dict[str, str]:
        nonlocal reads
        reads += 1
        return {}

    with pytest.raises(
        FormalMatrixControllerV4Error,
        match="active matrix-v4 admission is missing",
    ):
        execute_canary(
            tmp_path / "missing.json",
            credential_loader=credential_loader,
        )
    assert reads == 0
