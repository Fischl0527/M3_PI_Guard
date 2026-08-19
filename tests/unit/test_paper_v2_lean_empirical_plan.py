from __future__ import annotations

from collections import Counter

from experiments.paper_v2 import lean_empirical_plan as plan


def test_lean_plan_has_fixed_nested_counts_without_independent_blind() -> None:
    cases, rows, manifest = plan.build_plan()

    assert len(cases) == 180
    assert sum(case["regime_subset"] for case in cases) == 60
    assert sum(case["gemini_subset"] for case in cases) == 90
    assert {case["benchmark"] for case in cases} == {"agentdojo-v1", "m3-v2"}
    assert Counter(row["provider_id"] for row in rows) == {
        "deepseek": 900,
        "gemini": 450,
    }
    assert len({row["work_key"] for row in rows}) == 1350
    assert manifest["outcomes_accessed_for_selection"] is False
    assert manifest["independent_blind_set_used"] is False


def test_each_provider_has_six_unique_formal_prefix_records() -> None:
    _, rows, _ = plan.build_plan()

    for provider_id in ("deepseek", "gemini"):
        prefix = [
            row
            for row in rows
            if row["provider_id"] == provider_id and row["formal_prefix"]
        ]
        assert len(prefix) == 6
        assert len({row["work_key"] for row in prefix}) == 6
        assert all(row["status"] == "pending" for row in prefix)
