from __future__ import annotations

import copy

import pytest

import experiments.paper_v2.public_primary_analysis_v1 as analysis


def _record(
    *,
    condition: str,
    case_id: str,
    unsafe: bool,
    complete: bool,
    diagnostic: bool = False,
) -> dict:
    return {
        "case_id": case_id,
        "benchmark_id": "agentdojo-v1",
        "condition_id": condition,
        "evaluation_case_type": "attack",
        "authorization_regime": "auto_compiled",
        "unsafe_effect_itt": unsafe,
        "task_completion": complete,
        "result_tier": "diagnostic" if diagnostic else "formal_candidate",
        "operational_status": (
            "provider_transport_error" if diagnostic else "completed"
        ),
        "initial_guard_decision": "DENY" if diagnostic else "ALLOW",
        "latency_ms": {
            "total": 10.0,
            "model": 8.0,
            "guard": 2.0,
            "tool": 0.0,
        },
        "token_usage": {
            "input": 10,
            "output": 2,
            "total": 12,
            "available": True,
        },
    }


def test_condition_summary_retains_diagnostic_in_itt() -> None:
    records = [
        _record(
            condition=condition,
            case_id=f"case-{index}",
            unsafe=index == 0,
            complete=False,
            diagnostic=index == 0,
        )
        for index, condition in enumerate(analysis.CONDITIONS)
    ]

    rows = analysis._condition_rows(records)
    no_defense = next(
        row
        for row in rows
        if row["benchmark"] == "agentdojo-v1"
        and row["condition_id"] == "no_defense"
    )

    assert no_defense["events"] == 1
    assert no_defense["total"] == 1
    assert no_defense["rate"] == 1.0
    assert no_defense["diagnostic_records"] == 1
    assert no_defense["initial_deny"] == 1


def test_matrix_validation_rejects_projection_drift() -> None:
    records = [
        _record(
            condition="m3_full",
            case_id="case-1",
            unsafe=False,
            complete=True,
        )
    ]
    plan = [
        {
            "case_id": "case-1",
            "condition_id": "m3_full",
            "benchmark": "agentdojo-v1",
            "evaluation_case_type": "attack",
        }
    ]
    analysis._validate_matrix(records, plan)

    drifted = copy.deepcopy(records)
    drifted[0]["benchmark_id"] = "m3-v2"
    with pytest.raises(
        analysis.PublicPrimaryAnalysisError,
        match="projection drift",
    ):
        analysis._validate_matrix(drifted, plan)


def test_percentile_is_linear_and_empty_is_explicit() -> None:
    assert analysis._percentile([], 0.95) is None
    assert analysis._percentile([0.0, 10.0], 0.5) == 5.0
