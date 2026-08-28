from __future__ import annotations

from collections import Counter, defaultdict

import pytest

from experiments.paper_v2 import e6_cross_provider_calibration_plan_v1 as subject


def _case_keys(rows: list[dict[str, object]]) -> set[tuple[str, str]]:
    return {
        (str(row["benchmark"]), str(row["underlying_task_id"])) for row in rows
    }


def test_e6_cohorts_are_unique_balanced_eligible_and_nested() -> None:
    value = subject.build_all()
    deepseek = value["deepseek_cases"]
    gemini = value["gemini_cases"]

    assert len(deepseek) == len(_case_keys(deepseek)) == 60
    assert len(gemini) == len(_case_keys(gemini)) == 30
    assert Counter(row["benchmark"] for row in deepseek) == Counter(
        {"agentdojo-v1": 30, "m3-v2": 30}
    )
    assert Counter(row["benchmark"] for row in gemini) == Counter(
        {"agentdojo-v1": 15, "m3-v2": 15}
    )
    assert _case_keys(gemini) < _case_keys(deepseek)
    assert all(row["gemini_nested_replication"] is True for row in gemini)

    controls = subject.HISTORICAL_CONTROL_CONDITIONS
    for row in deepseek + gemini:
        historical = set(row["historical_control_conditions"])
        assert historical
        assert historical <= controls
        assert row["historical_control_unsafe_count"] == len(historical)
        assert row["selection_basis"] == "historical_public_control_unsafe_only"
        assert row["evaluation_case_type"] == "attack"
        assert subject._underlying_task_id(
            str(row["benchmark"]), str(row["case_id"])
        ) == str(row["underlying_task_id"])


def test_e6_selection_is_coverage_first_and_e3_is_membership_only() -> None:
    eligible = subject._eligible_representatives()
    value = subject.build_all()

    for cohort_name in ("deepseek_cases", "gemini_cases"):
        cohort = value[cohort_name]
        for benchmark in subject.BENCHMARKS:
            selected_coverage = {
                str(row["coverage_value"])
                for row in cohort
                if row["benchmark"] == benchmark
            }
            if cohort_name == "deepseek_cases":
                eligible_coverage = {
                    str(row["coverage_value"])
                    for row in eligible
                    if row["benchmark"] == benchmark
                }
            else:
                eligible_coverage = {
                    str(row["coverage_value"])
                    for row in value["deepseek_cases"]
                    if row["benchmark"] == benchmark
                }
            assert selected_coverage == eligible_coverage

    assert value["manifest"]["selection_uses_e3_outcomes"] is False
    assert value["manifest"]["selection_uses_e6_outcomes"] is False
    assert value["manifest"]["provider_activity_gates"] == {
        "deepseek": {
            "minimum_unique_active_tasks": 8,
            "minimum_active_windows": 2,
            "both_benchmarks_required": True,
        },
        "gemini": {
            "minimum_unique_active_tasks": 4,
            "minimum_active_windows": 2,
            "both_benchmarks_required": True,
        },
    }
    assert any(row["e3_anchor"] is True for row in value["deepseek_cases"])
    assert any(row["e3_anchor"] is False for row in value["deepseek_cases"])


def test_e6_plan_counts_provider_identity_and_work_keys() -> None:
    value = subject.build_all()
    deepseek = value["deepseek_plan"]
    gemini = value["gemini_plan"]
    all_rows = deepseek + gemini

    assert value["manifest"]["planned_counts"] == {
        "deepseek_cases": 60,
        "gemini_nested_cases": 30,
        "deepseek_rows": 1080,
        "gemini_rows": 540,
        "total_rows": 1620,
        "windows": 3,
        "conditions": 6,
        "formal_prefix_rows_per_provider_window": 12,
    }
    assert len({row["work_key"] for row in all_rows}) == 1620
    assert Counter(row["provider_id"] for row in all_rows) == Counter(
        {"deepseek": 1080, "gemini": 540}
    )
    assert {row["model_id"] for row in deepseek} == {"deepseek-v4-pro"}
    assert {row["model_id"] for row in gemini} == {"gemini-3.6-flash"}
    assert all(row["free_tier_required"] is False for row in deepseek)
    assert all(row["free_tier_required"] is True for row in gemini)
    assert all(row["paid_billing_allowed"] is False for row in all_rows)

    deepseek_index = {
        (
            row["underlying_task_id"],
            row["condition_id"],
            row["replicate_window"],
        ): row
        for row in deepseek
        if row["gemini_nested_replication"] is True
    }
    for gemini_row in gemini:
        key = (
            gemini_row["underlying_task_id"],
            gemini_row["condition_id"],
            gemini_row["replicate_window"],
        )
        deepseek_row = deepseek_index[key]
        assert gemini_row["work_key"] != deepseek_row["work_key"]
        assert (
            gemini_row["analysis_payload_digest_sha256"]
            == deepseek_row["analysis_payload_digest_sha256"]
        )


def test_e6_windows_conditions_rotation_and_prefix_are_complete() -> None:
    value = subject.build_all()
    condition_ids = {condition["condition_id"] for condition in subject.CONDITIONS}
    for provider, rows, per_benchmark in (
        ("deepseek", value["deepseek_plan"], 30),
        ("gemini", value["gemini_plan"], 15),
    ):
        assert Counter(row["replicate_window"] for row in rows) == Counter(
            {"W1": per_benchmark * 12, "W2": per_benchmark * 12, "W3": per_benchmark * 12}
        )
        by_task_window: dict[tuple[str, str, str], list[dict[str, object]]] = defaultdict(list)
        for row in rows:
            by_task_window[
                (
                    str(row["benchmark"]),
                    str(row["underlying_task_id"]),
                    str(row["replicate_window"]),
                )
            ].append(row)
        assert len(by_task_window) == per_benchmark * 2 * 3
        for task_rows in by_task_window.values():
            assert {row["condition_id"] for row in task_rows} == condition_ids
            assert {row["condition_order_position"] for row in task_rows} == set(
                range(1, 7)
            )

        for window in subject.WINDOWS:
            window_rows = [row for row in rows if row["replicate_window"] == window]
            prefix = [row for row in window_rows if row["formal_prefix"] is True]
            assert len(prefix) == 12
            assert {row["provider_window_sequence"] for row in prefix} == set(
                range(1, 13)
            )
            assert Counter(row["benchmark"] for row in prefix) == Counter(
                {"agentdojo-v1": 6, "m3-v2": 6}
            )
            prefix_tasks = {
                (row["benchmark"], row["underlying_task_id"]) for row in prefix
            }
            assert len(prefix_tasks) == 2

            starts = Counter(
                (row["benchmark"], row["condition_id"])
                for row in window_rows
                if row["condition_order_position"] == 1
            )
            for benchmark in subject.BENCHMARKS:
                benchmark_counts = [starts[(benchmark, condition)] for condition in condition_ids]
                if provider == "deepseek":
                    assert benchmark_counts == [5] * 6
                else:
                    assert max(benchmark_counts) - min(benchmark_counts) <= 1
            global_starts = Counter(
                row["condition_id"]
                for row in window_rows
                if row["condition_order_position"] == 1
            )
            expected_global = 10 if provider == "deepseek" else 5
            assert global_starts == Counter(
                {condition: expected_global for condition in condition_ids}
            )


def test_e6_execution_identities_are_provider_window_scoped() -> None:
    value = subject.build_all()
    for provider, rows in (
        ("deepseek", value["deepseek_plan"]),
        ("gemini", value["gemini_plan"]),
    ):
        by_window = defaultdict(set)
        for row in rows:
            by_window[row["replicate_window"]].add(row["execution_identity"])
        assert set(by_window) == set(subject.WINDOWS)
        assert all(len(identities) == 1 for identities in by_window.values())
        assert len({next(iter(identities)) for identities in by_window.values()}) == 3
        assert all(row["provider_id"] == provider for row in rows)


def test_e6_frozen_artifacts_reproduce() -> None:
    manifest = subject.verify_plan()
    assert manifest["status"] == "design_frozen_execution_pending"
    assert manifest["provider_tools_enabled"] is False
    assert manifest["real_external_effects_enabled"] is False
    assert manifest["gemini_free_tier_only"] is True
    assert manifest["gemini_paid_ceiling_usd"] == 0.0


def test_e6_fails_closed_if_historical_control_set_drifts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(subject, "HISTORICAL_CONTROL_CONDITIONS", frozenset())
    with pytest.raises(subject.E6PlanError, match="candidate drift"):
        subject._historical_control_unsafe()
