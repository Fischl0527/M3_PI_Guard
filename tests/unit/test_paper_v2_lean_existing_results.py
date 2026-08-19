from __future__ import annotations

from experiments.paper_v2.lean_existing_results import (
    summarize_adaptive,
    summarize_records,
)


def _record(case_id: str, condition: str, *, unsafe: bool, complete: bool) -> dict:
    return {
        "_work_key": f"{case_id}:{condition}",
        "case_id": case_id,
        "condition_id": condition,
        "authorization_regime": "auto_compiled",
        "evaluation_case_type": "attack",
        "unsafe_effect_itt": unsafe,
        "task_completion": complete,
        "initial_guard_decision": "ASK" if condition == "m3_full" else "ALLOW",
        "effective_decision": "DENY" if condition == "m3_full" else "ALLOW",
        "operational_status": "completed",
        "result_tier": "formal_candidate",
        "latency_ms": {"total": 10.0},
        "token_usage": {"total": 12},
        "provider_trace_bundle": {
            "model_id": "model",
            "completed_request_count": 1,
            "usage_summary": {"cumulative_cost_cny": 0.1},
        },
    }


def test_record_summary_keeps_paired_direction_and_raw_counts() -> None:
    rows = [
        _record("a", "m3_policy_only", unsafe=True, complete=True),
        _record("a", "m3_full", unsafe=False, complete=True),
    ]
    result = summarize_records(rows, expected=2, label="fixture")

    assert result["records"] == 2
    assert result["provider_calls"] == 2
    pair = result["paired_full_vs_policy"][0]
    assert pair["full_minus_policy_pp"] == -100.0
    assert pair["discordant_policy_only"] == 1


def test_adaptive_summary_uses_all_tasks_as_itt_denominator() -> None:
    events = []
    for index in range(40):
        query = 10 if index < 10 else 200
        events.append(
            {
                "case_id": f"case-{index}",
                "work_key": f"case-{index}:q{query}",
                "query_index": query,
                "record": {
                    "unsafe_effect_itt": index < 10,
                    "result_tier": "formal_candidate",
                },
            }
        )
    result = summarize_adaptive(events)

    assert result["budget_50"]["successes"] == 10
    assert result["budget_50"]["total"] == 40
    assert result["budget_200"]["total"] == 40
