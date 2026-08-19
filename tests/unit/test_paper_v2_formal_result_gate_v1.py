from __future__ import annotations

from copy import deepcopy

from experiments.paper_v2.formal_result_gate_v1 import (
    _fixture_record,
    build_gate_candidate,
    build_qualification,
    evaluate_operational_gate,
    verify_gate_candidate,
    verify_qualification,
)


def _gate(records: list[dict]) -> dict:
    return evaluate_operational_gate(
        records,
        expected_records=2,
        remaining_work_items=0,
        open_attempts=0,
        budget_paused=False,
    )


def test_positive_operational_gate_is_outcome_blind() -> None:
    first = _fixture_record()
    second = _fixture_record(status="refusal")
    first["unsafe_effect"] = True
    first["task_completion"] = False
    second["unsafe_effect"] = False
    second["task_completion"] = True

    value = _gate([first, second])

    assert value["status"] == "technical_result_gate_pass"
    assert value["result_admission_eligible"] is True
    assert value["operational_failure_count"] == 0
    assert "unsafe_effect" not in value
    assert "task_completion" not in value


def test_gate_rejects_incomplete_or_open_matrix() -> None:
    value = evaluate_operational_gate(
        [_fixture_record()],
        expected_records=2,
        remaining_work_items=1,
        open_attempts=1,
        budget_paused=False,
    )

    assert value["result_admission_eligible"] is False
    assert value["checks"]["complete_record_matrix"] is False
    assert value["checks"]["no_open_attempts"] is False


def test_gate_rejects_diagnostic_record_and_operational_failure() -> None:
    diagnostic = _fixture_record(tier="diagnostic")
    failed = _fixture_record(status="provider_failure")

    value = _gate([diagnostic, failed])

    assert value["result_admission_eligible"] is False
    assert value["checks"]["all_records_formal_candidate"] is False
    assert value["checks"]["zero_operational_failures"] is False


def test_gate_rejects_unverified_identity_or_unsafe_boundary() -> None:
    identity = _fixture_record(official=False)
    unsafe = _fixture_record()
    unsafe["provider_safety_receipt"]["evidence"][
        "external_connectors_enabled"
    ] = True

    value = _gate([identity, unsafe])

    assert value["result_admission_eligible"] is False
    assert value["checks"]["official_exact_identity_chain"] is False
    assert value["checks"]["isolated_effect_boundary"] is False


def test_gate_rejects_incomplete_trace_bundle_or_budget_pause() -> None:
    incomplete = _fixture_record()
    incomplete["provider_trace_bundle"]["open_request_count"] = 1
    incomplete["provider_trace_bundle"]["bundle_status"] = "open"

    value = evaluate_operational_gate(
        [incomplete, _fixture_record()],
        expected_records=2,
        remaining_work_items=0,
        open_attempts=0,
        budget_paused=True,
    )

    assert value["result_admission_eligible"] is False
    assert value["checks"]["complete_trace_bundles"] is False
    assert value["checks"]["budget_not_paused"] is False


def test_qualification_covers_fail_closed_scenarios() -> None:
    value = build_qualification()

    assert value["status"] == "formal_result_gate_qualified_offline"
    assert value["positive_scenarios"] == 1
    assert value["negative_scenarios"] == 4
    assert value["network_calls_made"] == 0
    assert value["scientific_outcomes_read"] == 0


def test_frozen_qualification_and_candidate_reproduce() -> None:
    qualification = verify_qualification()
    candidate = verify_gate_candidate()

    assert qualification == build_qualification()
    assert candidate == build_gate_candidate()
    assert candidate["evidence_boundary"]["scientific_outcomes_reviewed"] is False
    assert candidate["evidence_boundary"]["analysis_authorized"] is False


def test_gate_does_not_mutate_records() -> None:
    records = [_fixture_record(), _fixture_record()]
    before = deepcopy(records)

    _gate(records)

    assert records == before
