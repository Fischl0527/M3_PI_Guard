from __future__ import annotations

import copy
import json
from pathlib import Path

import experiments.paper_v2.formal_result_gate_v2 as gate


def _spec() -> dict:
    return json.loads(gate.DEFAULT_GATE_SPEC.read_text(encoding="utf-8"))


def _evaluate(records: list[dict]) -> dict:
    return gate.evaluate_operational_gate(
        records,
        expected_records=len(records),
        remaining_work_items=0,
        open_attempts=0,
        budget_paused=False,
        gate_spec=_spec(),
    )


def test_completed_and_refusal_records_pass() -> None:
    result = _evaluate(
        [gate._fixture_record(), gate._fixture_record(status="refusal")]
    )
    assert result["result_admission_eligible"] is True


def test_runner_failure_blocks_result_access() -> None:
    result = _evaluate(
        [
            gate._fixture_record(),
            gate._fixture_record(status="runner_failure"),
        ]
    )
    assert result["result_admission_eligible"] is False
    assert result["checks"]["runner_failure_ceiling"] is False


def test_small_closed_provider_failure_is_admissible() -> None:
    records = [gate._fixture_record() for _ in range(99)]
    records.append(
        gate._fixture_record(status="provider_failure", tier="diagnostic")
    )
    result = _evaluate(records)
    assert result["result_admission_eligible"] is True
    assert result["diagnostic_count"] == 1


def test_diagnostic_parse_failure_is_not_admissible() -> None:
    records = [gate._fixture_record() for _ in range(99)]
    records.append(
        gate._fixture_record(status="parse_failure", tier="diagnostic")
    )
    result = _evaluate(records)
    assert result["result_admission_eligible"] is False
    assert result["checks"]["diagnostic_closed_failure_trace"] is False


def test_unverified_formal_identity_blocks_result_access() -> None:
    result = _evaluate(
        [gate._fixture_record(), gate._fixture_record(official=False)]
    )
    assert result["result_admission_eligible"] is False
    assert result["checks"]["formal_exact_identity_chain"] is False


def test_qualification_is_blind_and_reproducible(tmp_path: Path) -> None:
    target = tmp_path / "qualification.json"
    written = gate.write_qualification(target)
    assert gate.verify_qualification(target) == written
    assert written["scientific_outcomes_read"] == 0
    assert written["network_calls_made"] == 0


def test_gate_candidate_reproduces(tmp_path: Path) -> None:
    gate.verify_qualification()
    target = tmp_path / "candidate.json"
    written = gate.write_gate_candidate(target)
    assert gate.verify_gate_candidate(target) == written
    assert written["evidence_boundary"]["scientific_outcomes_reviewed"] is False


def test_operational_quality_retains_terminal_failures_in_itt() -> None:
    from experiments.paper_v2.medium_analysis_v3 import (
        evaluate_operational_quality,
    )

    records = [
        {"operational_status": "completed"},
        {"operational_status": "max_steps"},
    ]
    spec = _spec()
    spec = copy.deepcopy(spec)
    spec["operational_quality"]["overall_failure_fraction_maximum"] = 0.5
    result = evaluate_operational_quality(records, gate_spec=spec)
    assert result["mechanism_claim_quality_eligible"] is True
    assert result["all_records_retained_in_itt"] is True
