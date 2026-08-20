from __future__ import annotations

import csv
from pathlib import Path

from experiments.paper_v2.lean_empirical_tables import (
    _table_1,
    _table_2,
    _table_3,
    _table_4,
    _table_5,
    _table_6,
    _write_csv,
)


def _metric(successes: int, total: int) -> dict:
    return {
        "successes": successes,
        "total": total,
        "rate": successes / total,
        "ci_low": 0.1,
        "ci_high": 0.9,
    }


def _comparison() -> dict:
    return {
        "paired_cases": 10,
        "absolute_difference_second_minus_first": 0.1,
        "cluster_bootstrap": {"ci_low": 0.0, "ci_high": 0.2},
        "discordant_first_only": 1,
        "discordant_second_only": 2,
        "exact_mcnemar_p": 1.0,
        "holm_adjusted_p_within_endpoint": 1.0,
    }


def _analysis(*, gemini_complete: bool = True) -> dict:
    provider = {
        "condition_metrics": {
            "m3_full__auto_compiled": {
                "condition_id": "m3_full",
                "authorization_regime": "auto_compiled",
                "attack_unsafe_effect": _metric(1, 10),
                "benign_tool_tcr": _metric(8, 10),
            }
        },
        "comparisons": {
            "unsafe_effect": {"full_auto_to_exact": _comparison()},
            "task_completion": {"full_auto_to_exact": _comparison()},
        },
        "burden": {
            "m3_full__auto_compiled": {
                "records": 20,
                "ask_count": 1,
                "deny_count": 2,
                "failure_count": 3,
                "latency_p50_ms": 10,
                "latency_p95_ms": 20,
                "tokens": 30,
                "cost_amount": 0.01,
                "cost_currency": "CNY",
            }
        },
        "heterogeneity": {
            "agentdojo__family-a": {
                "records": 10,
                "attack_records": 10,
                "unsafe_effects": 1,
                "operational_failures": 0,
            }
        },
    }
    return {
        "deepseek": {
            **provider,
            "regime_extension": {
                "broad": {
                    "unsafe_effect": _comparison(),
                    "benign_tool_tcr": _comparison(),
                }
            },
        },
        "gemini": {
            **provider,
            "cross_vendor_claim_eligible": gemini_complete,
        },
    }


def test_table_shapes_and_csv_export(tmp_path: Path) -> None:
    analysis = _analysis()
    plan = [
        {
            "provider_id": "deepseek",
            "benchmark": "agentdojo",
            "condition_id": "m3_full",
            "authorization_regime": "auto_compiled",
        },
        {
            "provider_id": "deepseek",
            "benchmark": "agentdojo",
            "condition_id": "m3_full",
            "authorization_regime": "auto_compiled",
        },
    ]
    existing = {
        "adaptive_deepseek_v4_pro": {
            "budget_50": _metric(4, 40),
            "budget_200": _metric(18, 40),
            "claim_boundary": "no_saturation_claim",
        }
    }

    assert _table_1(plan)[0]["planned_records"] == 2
    assert len(_table_2(analysis)) == 2
    assert len(_table_3(analysis)) == 6
    assert len(_table_4(analysis)) == 2
    assert len(_table_5(analysis)) == 2
    assert [row["budget"] for row in _table_6(existing)] == [50, 200]

    path = tmp_path / "table.csv"
    assert _write_csv(path, _table_2(analysis)) == 2
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert rows[0]["condition"] == "m3_full"


def test_partial_gemini_is_excluded_from_inferential_tables() -> None:
    partial = _analysis(gemini_complete=False)

    assert {row["provider"] for row in _table_2(partial)} == {"deepseek"}
    assert len(_table_2(partial)) == 1
    assert len(_table_3(partial)) == 4
    assert len(_table_4(partial)) == 1
    assert len(_table_5(partial)) == 1
