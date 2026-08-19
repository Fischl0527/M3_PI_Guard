from __future__ import annotations

import scripts.build_paper_v2_stage_report_20260730 as report


def test_ratio_text_preserves_counts_and_interval() -> None:
    value = report._ratio_text(
        {
            "numerator": 0,
            "denominator": 36,
            "value": 0.0,
            "ci_low": 0.0,
            "ci_high": 0.0964186286,
        }
    )

    assert value == "0/36；0.00% （Wilson 95% CI 0.00–9.64%）"


def test_comparison_rows_reports_direction_and_multiplicity() -> None:
    item = {
        "pairs": 36,
        "absolute_difference_treatment_minus_baseline": -0.2,
        "mcnemar": {
            "p_value": 0.01,
            "holm_adjusted_p_value": 0.04,
        },
        "cluster_bootstrap": {
            "ci_low": -0.3,
            "ci_high": -0.1,
        },
    }
    rows = report._comparison_rows(
        {
            "security_full_vs_structural": item,
            "security_full_vs_policy_only": item,
            "utility_full_vs_structural": item,
            "utility_full_vs_policy_only": item,
        }
    )

    assert len(rows) == 4
    assert rows[0][1:] == [
        "36",
        "-20.00 pp",
        "0.01",
        "0.04",
        "-30.00 至 -10.00 pp",
    ]


def test_public_rate_rows_uses_frozen_condition_order() -> None:
    rows = []
    for condition in report.CONDITION_LABELS:
        for case_type in ("attack", "benign_tool"):
            rows.append(
                {
                    "benchmark": "all",
                    "evaluation_case_type": case_type,
                    "condition_id": condition,
                    "events": "1",
                    "total": "10",
                    "rate": "0.1",
                    "wilson_low": "0.02",
                    "wilson_high": "0.4",
                    "diagnostic_records": "1",
                }
            )

    result = report._public_rate_rows(rows, benchmark="all")

    assert [row[0] for row in result] == list(
        report.CONDITION_LABELS.values()
    )
    assert all(row[3] == "2" for row in result)
