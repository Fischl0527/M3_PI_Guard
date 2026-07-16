from __future__ import annotations

import pytest

from experiments.e17_human_sample_review import (
    HumanSampleReviewError,
    REPRESENTATIVE_GROUP,
    _weighted_estimates,
)


def _rows() -> list[dict[str, object]]:
    codes = ("leak", "none", "ask", "parse_failure")
    rows: list[dict[str, object]] = []
    for index in range(300):
        rows.append(
            {
                "blind_id": f"representative-{index:03d}",
                "sample_group": REPRESENTATIVE_GROUP,
                "flag_combination": f"stratum-{index % 3}",
                "analysis_weight": float(1 + index % 5),
                "final_primary_code": codes[index % len(codes)],
            }
        )
    rows.extend(
        {
            "blind_id": f"targeted-{index:03d}",
            "sample_group": "automated_disagreement_targeted",
            "flag_combination": "targeted",
            "analysis_weight": None,
            "final_primary_code": "false_block",
        }
        for index in range(60)
    )
    return rows


def test_weighted_estimates_are_deterministic_and_exclude_targeted_rows() -> None:
    rows = _rows()
    first = _weighted_estimates(rows, iterations=200, seed=20260717)
    second = _weighted_estimates(rows, iterations=200, seed=20260717)

    assert first == second
    assert sum(float(row["weighted_share"]) for row in first) == pytest.approx(1.0)
    assert {int(row["representative_sample_n"]) for row in first} == {300}
    assert {int(row["bootstrap_iterations"]) for row in first} == {200}

    for row in rows[300:]:
        row["final_primary_code"] = "timeout"
    assert _weighted_estimates(rows, iterations=200, seed=20260717) == first


def test_weighted_estimates_require_exact_representative_cohort() -> None:
    with pytest.raises(HumanSampleReviewError, match="exactly 300 representative rows"):
        _weighted_estimates(_rows()[:-61], iterations=10, seed=1)


def test_weighted_estimates_reject_nonpositive_design_weight() -> None:
    rows = _rows()
    rows[0]["analysis_weight"] = 0.0
    with pytest.raises(HumanSampleReviewError, match="positive weight"):
        _weighted_estimates(rows, iterations=10, seed=1)
