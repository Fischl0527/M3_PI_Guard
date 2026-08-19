from __future__ import annotations

import experiments.paper_v2.lean_authorization_analysis as analysis


def _row(case_id: str, condition: str, regime: str, value: bool) -> dict:
    return {
        "case_id": case_id,
        "condition_id": condition,
        "authorization_regime": regime,
        "evaluation_case_type": "attack",
        "unsafe_effect": value,
        "task_completion": False,
    }


def test_latest_attempts_keep_raw_recovery_but_select_latest_terminal() -> None:
    rows = [
        {"work_key": "a", "attempt": 1, "response_obtained": False},
        {"work_key": "b", "attempt": 1, "response_obtained": True},
        {"work_key": "a", "attempt": 2, "response_obtained": True},
    ]
    latest, summary = analysis._latest_attempts(rows)
    assert set(latest) == {"a", "b"}
    assert latest["a"]["attempt"] == 2
    assert summary["raw_attempt_rows"] == 3
    assert summary["superseded_attempt_rows"] == 1


def test_exact_mcnemar_is_two_sided_and_exact() -> None:
    assert analysis._exact_mcnemar(0, 0) == 1.0
    assert analysis._exact_mcnemar(0, 5) == 0.0625
    assert analysis._exact_mcnemar(1, 4) == 0.375


def test_paired_stats_report_direction_and_discordance(monkeypatch) -> None:
    monkeypatch.setattr(analysis, "BOOTSTRAP_REPLICATES", 100)
    first = ("m3_policy_only", "auto_compiled")
    second = ("m3_full", "auto_compiled")
    rows = [
        _row("a", *first, False),
        _row("a", *second, True),
        _row("b", *first, False),
        _row("b", *second, False),
        _row("c", *first, True),
        _row("c", *second, False),
    ]
    result = analysis._paired_stats(
        rows,
        first=first,
        second=second,
        case_type="attack",
        endpoint="unsafe_effect",
    )
    assert result["paired_cases"] == 3
    assert result["absolute_difference_second_minus_first"] == 0.0
    assert result["discordant_first_only"] == 1
    assert result["discordant_second_only"] == 1
    assert result["exact_mcnemar_p"] == 1.0
    assert result["cluster_bootstrap"]["replicates"] == 100


def test_holm_adjustment_is_monotone_in_sorted_p_values() -> None:
    adjusted = analysis._holm({"a": 0.01, "b": 0.03, "c": 0.2, "d": 0.8})
    assert adjusted == {"a": 0.04, "b": 0.09, "c": 0.4, "d": 0.8}
