from __future__ import annotations

import copy
from pathlib import Path

import pytest

import experiments.paper_v2.formal_matrix_controller_v1 as v1
import experiments.paper_v2.formal_matrix_remainder_controller_v9 as v9


def test_v9_frozen_candidate_and_admission_are_pending_only() -> None:
    candidate = v9._validate_manifest(
        v9._load_json(v9.DEFAULT_CANDIDATE),
        expected_role="owner_review_candidate",
    )
    admission = v9._validate_manifest(
        v9._load_json(v9.DEFAULT_ADMISSION),
        expected_role="remainder_shard_execution_authorization",
    )
    scope = candidate["scope"]

    assert scope["source_v8"]["record_count"] == 303
    assert scope["source_v8"]["diagnostic_records"] == 1
    assert scope["source_v8"]["open_attempts"] == 0
    assert scope["source_v8"]["source_run_resumable"] is False
    assert scope["selection"]["work_items"] == 177
    assert scope["selection"]["selection_kind"] == (
        "v8_never_started_work_items_only"
    )
    assert scope["selection"]["source_terminal_items_retryable"] is False
    assert scope["selection"]["pending_only_manual_resume"] is True
    assert scope["provider"]["automatic_retries"] == 0
    assert scope["provider"]["provider_managed_tools"] is False
    assert admission["authorization"][
        "remainder_shard_execution_authorized"
    ] is True
    assert admission["authorization"]["result_admission_authorized"] is False
    assert admission["authorization"]["candidate_manifest_sha256"] == (
        candidate["manifest_sha256"]
    )


def test_v9_qualification_records_zero_network_boundary() -> None:
    value = v9._load_json(v9.DEFAULT_QUALIFICATION)

    assert value["status"] == (
        "pending_only_remainder_shard_qualified_offline"
    )
    assert value["source_terminal_records"] == 303
    assert value["selected_pending_work_items"] == 177
    assert value["combined_work_items"] == 480
    assert value["selection_intersection_count"] == 0
    assert value["offline_fixture_records"] == 2
    assert value["offline_fixture_diagnostics"] == 0
    assert value["network_calls_made"] == 0
    assert value["scientific_outcomes_read"] == 0
    assert value["source_v8_mutated"] is False
    assert value["terminal_source_items_retryable"] is False


def test_v9_pending_selection_digest_rejects_terminal_overlap() -> None:
    candidate = v9._load_json(v9.DEFAULT_CANDIDATE)
    source_scope = candidate["scope"]["source_v8"]
    selection = candidate["scope"]["selection"]

    assert source_scope["terminal_work_keys_sha256"] != (
        selection["pending_work_keys_sha256"]
    )
    assert source_scope["pending_work_keys_sha256"] == (
        selection["pending_work_keys_sha256"]
    )
    assert source_scope["pending_rows_sha256"] == (
        selection["pending_rows_sha256"]
    )


def test_v9_segment_blocks_completed_shard_before_credentials(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    row = copy.deepcopy(v1._plan_rows()[0])
    permit = v1.MatrixExecutionPermit(
        admission_file_sha256="9" * 64,
        run_id=v9.RUN_ID,
        execution_identity=str(row["execution_identity"]),
        work_items=(row,),
        output_root=tmp_path,
        record_ledger_path=tmp_path / "records.jsonl",
        attempt_ledger_path=tmp_path / "attempts.jsonl",
        budget_ledger_path=tmp_path / "budget.jsonl",
        trace_root=tmp_path / "traces",
        max_tokens=32,
        timeout_seconds=1.0,
        scope={
            "source_v8": {"diagnostic_records": 1},
            "budget": {"prior_project_usage": copy.deepcopy(v9.PRIOR_PROJECT_USAGE)},
        },
    )
    authorization = v9.source.previous.previous.base.V5Authorization(
        permit=permit,
        authorization_scope="remainder",
        active_manifest={},
    )
    monkeypatch.setattr(
        v9,
        "authorize_remainder_shard",
        lambda: authorization,
    )
    monkeypatch.setattr(
        v9,
        "_state_from_paths",
        lambda _permit: {
            "pending_work_items": [],
            "record_entries": [],
            "budget_status": {"paused": False},
        },
    )
    credentials_loaded = False

    def load_credentials() -> dict[str, str]:
        nonlocal credentials_loaded
        credentials_loaded = True
        return {}

    with pytest.raises(
        v9.FormalMatrixRemainderV9Error,
        match="already complete",
    ):
        v9.execute_pending_segment(credential_loader=load_credentials)

    assert credentials_loaded is False
