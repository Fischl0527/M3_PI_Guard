from __future__ import annotations

import experiments.paper_v2.formal_result_gate_v6 as gate


def test_v6_qualification_covers_combined_shard_fail_closed_rules() -> None:
    qualification = gate._read_json(gate.DEFAULT_QUALIFICATION)

    assert qualification["status"] == (
        "combined_v8_v9_result_gate_qualified_offline"
    )
    assert qualification["expected_records"] == 480
    assert qualification["source_records"] == 303
    assert qualification["remainder_records"] == 177
    assert all(qualification["qualified_checks"].values())
    assert qualification["diagnostic_rows_retained_in_itt"] is True
    assert qualification["network_calls_made"] == 0
    assert qualification["scientific_outcomes_read"] == 0


def test_v6_frozen_candidate_precedes_remainder_execution() -> None:
    candidate = gate._validate_artifact(
        gate._read_json(gate.DEFAULT_GATE_CANDIDATE),
        expected_role="prospective_result_gate_candidate",
    )

    assert candidate["status"] == (
        "frozen_before_remainder_execution_and_"
        "scientific_outcome_access"
    )
    assert candidate["source_record_count"] == 303
    assert candidate["remainder_record_count"] == 177
    assert candidate["expected_records"] == 480
    assert candidate["coverage_contract"][
        "duplicate_work_keys_allowed"
    ] == 0
    assert candidate["coverage_contract"]["missing_work_keys_allowed"] == 0
    assert candidate["coverage_contract"]["unknown_work_keys_allowed"] == 0
    assert candidate["coverage_contract"][
        "terminal_source_items_retryable"
    ] is False
    boundary = candidate["evidence_boundary"]
    assert boundary["remainder_v9_executed_while_building"] is False
    assert boundary["scientific_outcomes_reviewed"] is False
    assert boundary["result_admission_authorized"] is False


def test_v6_operational_gate_accepts_one_closed_diagnostic_in_480() -> None:
    records = [gate.base._fixture_record() for _ in range(479)]
    records.append(
        gate.base._fixture_record(
            status="provider_failure",
            tier="diagnostic",
        )
    )
    result = gate.base.evaluate_operational_gate(
        records,
        expected_records=480,
        remaining_work_items=0,
        open_attempts=0,
        budget_paused=False,
        gate_spec=gate._read_json(gate.DEFAULT_GATE_SPEC),
    )

    assert result["result_admission_eligible"] is True
    assert result["diagnostic_count"] == 1


def test_v6_operational_gate_blocks_one_missing_record() -> None:
    records = [gate.base._fixture_record() for _ in range(479)]
    result = gate.base.evaluate_operational_gate(
        records,
        expected_records=480,
        remaining_work_items=1,
        open_attempts=0,
        budget_paused=False,
        gate_spec=gate._read_json(gate.DEFAULT_GATE_SPEC),
    )

    assert result["result_admission_eligible"] is False
    assert result["checks"]["complete_record_matrix"] is False
