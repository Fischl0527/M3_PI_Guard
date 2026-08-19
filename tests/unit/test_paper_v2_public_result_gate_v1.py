from __future__ import annotations

from experiments.paper_v2.public_result_gate_v1 import (
    build_public_result_gate,
)


def test_public_result_gate_requires_all_6873_records() -> None:
    value = build_public_result_gate()
    criteria = value["admission_criteria"]

    assert criteria["exact_terminal_records"] == 6873
    assert criteria["primary_terminal_records"] == 5082
    assert criteria["second_terminal_records"] == 1791
    assert criteria["failures_retained_in_intention_to_treat"] is True
    assert criteria["primary_technical_canary_pass"] is True
    assert criteria["second_technical_canary_pass"] is True
    assert value["authorization"]["result_admission_authorized"] is False
    assert value["evidence_boundary"]["scientific_outcomes_accessed"] is False
