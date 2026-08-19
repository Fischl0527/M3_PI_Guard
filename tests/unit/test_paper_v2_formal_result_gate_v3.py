from __future__ import annotations

from pathlib import Path

import experiments.paper_v2.formal_result_gate_v3 as gate


def test_v3_qualification_is_blind_and_reproducible(
    tmp_path: Path,
) -> None:
    target = tmp_path / "qualification.json"
    written = gate.write_qualification(target)

    assert gate.verify_qualification(target) == written
    assert written["bound_matrix_run_id"] == gate.RUN_ID
    assert written["scientific_outcomes_read"] == 0
    assert written["network_calls_made"] == 0


def test_v3_candidate_binds_v6_and_stays_result_closed(
    tmp_path: Path,
) -> None:
    gate.verify_qualification()
    target = tmp_path / "candidate.json"
    written = gate.write_gate_candidate(target)

    assert gate.verify_gate_candidate(target) == written
    assert written["run_id"] == gate.RUN_ID
    assert written["evidence_boundary"][
        "scientific_outcomes_reviewed"
    ] is False
    assert written["evidence_boundary"][
        "result_admission_authorized"
    ] is False
    assert written["evidence_boundary"]["analysis_authorized"] is False


def test_v3_reuses_prespecified_operational_gate() -> None:
    result = gate.evaluate_operational_gate(
        [gate._fixture_record(), gate._fixture_record(status="refusal")],
        expected_records=2,
        remaining_work_items=0,
        open_attempts=0,
        budget_paused=False,
        gate_spec=gate._read_json(gate.DEFAULT_GATE_SPEC),
    )

    assert result["result_admission_eligible"] is True
