from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

import experiments.paper_v2.formal_result_gate_v5 as gate
from experiments.paper_v2.contracts import canonical_json_bytes


def _valid_canary_review(candidate: dict[str, object]) -> dict[str, object]:
    scope = candidate["scope"]
    assert isinstance(scope, dict)
    canary = scope["canary"]
    assert isinstance(canary, dict)
    conditions = canary["conditions"]
    assert isinstance(conditions, list)
    assert canary["work_items"] == 6
    return {
        "schema_version": "m3-paper-v2-six-condition-canary-review-8.0",
        "generated_at": "2026-07-26T12:00:00+08:00",
        "status": "six_condition_canary_technical_gate_pass",
        "run_id": gate.RUN_ID,
        "candidate_manifest_sha256": candidate["manifest_sha256"],
        "canary_admission_file_sha256": hashlib.sha256(
            gate.matrix.DEFAULT_CANARY_ADMISSION.read_bytes()
        ).hexdigest(),
        "record_count": 6,
        "conditions": [str(condition) for condition in conditions],
        "operational_statuses": ["completed"] * 6,
        "result_tiers": ["formal_candidate"] * 6,
        "boundary_rejection_events": 1,
        "diagnostic_records": 0,
        "operational_failures": 0,
        "provider_calls_completed": 13,
        "project_cumulative_cost_cny": 1.0,
        "thinking_mode": "disabled",
        "rejected_effects_executed": 0,
        "scientific_outcomes_reviewed": False,
        "operational_metadata_reviewed": True,
        "matrix_continuation_eligible": True,
        "matrix_continuation_authorized": False,
        "result_admission_authorized": False,
    }


def test_v5_qualification_is_blind_frozen_and_reproducible(
    tmp_path: Path,
) -> None:
    target = tmp_path / "qualification.json"
    written = gate.write_qualification(target)

    assert gate.verify_qualification(target) == written
    assert written["bound_matrix_run_id"] == gate.RUN_ID
    assert written["scientific_outcomes_read"] == 0
    assert written["network_calls_made"] == 0
    assert written["gate_candidate_requires_passing_canary_review"] is True
    contract = written["boundary_rejection_contract"]
    assert contract["adapter_binding_scope"] == "full_execute_scope"
    locked = {item["path"] for item in written["precanary_locked_inputs"]}
    assert "experiments/paper_v2/formal_result_gate_v5.py" in locked
    assert "experiments/paper_v2/formal_matrix_controller_v8.py" in locked
    assert "experiments/paper_v2/formal_matrix_abort_review_v3.py" in locked


def test_v5_candidate_requires_passing_technical_canary_review(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    review_path = tmp_path / gate.matrix.DEFAULT_CANARY_REVIEW_NAME
    monkeypatch.setattr(gate, "_canary_review_path", lambda: review_path)

    with pytest.raises(
        gate.FormalResultGateV5Error,
        match="passing v8 canary technical review is required",
    ):
        gate._verify_canary_review()


def test_v5_candidate_binds_v8_and_rejects_outcome_open_canary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = gate.matrix.verify_matrix_candidate()
    review_path = tmp_path / gate.matrix.DEFAULT_CANARY_REVIEW_NAME
    review = _valid_canary_review(candidate)
    review_path.write_bytes(canonical_json_bytes(review) + b"\n")
    monkeypatch.setattr(gate, "_canary_review_path", lambda: review_path)

    observed = gate._verify_canary_review()
    assert observed["scientific_outcomes_reviewed"] is False

    review["scientific_outcomes_reviewed"] = True
    review_path.write_bytes(canonical_json_bytes(review) + b"\n")
    with pytest.raises(
        gate.FormalResultGateV5Error,
        match="outcomes_closed",
    ):
        gate._verify_canary_review()


def test_v5_reuses_prespecified_operational_gate() -> None:
    result = gate.evaluate_operational_gate(
        [gate._fixture_record(), gate._fixture_record(status="refusal")],
        expected_records=2,
        remaining_work_items=0,
        open_attempts=0,
        budget_paused=False,
        gate_spec=gate._read_json(gate.DEFAULT_GATE_SPEC),
    )

    assert result["result_admission_eligible"] is True
