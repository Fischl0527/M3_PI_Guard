from __future__ import annotations

from collections.abc import Callable

import pytest

import experiments.paper_v2.e6_cross_provider_calibration_analysis_v1 as analysis
import experiments.paper_v2.incremental_analysis_v1 as incremental


def _fixture(
    *,
    provider: str,
    tasks: int,
    unsafe: Callable[[int, str, str], bool] | None = None,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    model = "deepseek-v4-pro" if provider == "deepseek" else "gemini-3.6-flash"
    plan: list[dict[str, object]] = []
    raw: list[dict[str, object]] = []
    sequence = 0
    for task_index in range(tasks):
        benchmark = "agentdojo-v1" if task_index % 2 == 0 else "m3-v2"
        task_id = f"task-{task_index}"
        for window in analysis.WINDOWS:
            for condition in analysis.CONDITIONS:
                sequence += 1
                work_key = f"{provider}:{task_id}:{condition}:{window}"
                planned = {
                    "sequence": sequence,
                    "work_key": work_key,
                    "provider_id": provider,
                    "model_id": model,
                    "underlying_task_id": task_id,
                    "case_id": f"case-{task_index}",
                    "benchmark": benchmark,
                    "condition_id": condition,
                    "replicate_window": window,
                    "analysis_payload_digest_sha256": f"digest:{task_id}:{condition}",
                }
                plan.append(planned)
                raw.append(
                    {
                        **planned,
                        "attempt": 1,
                        "response_obtained": True,
                        "operational_status": "completed",
                        "unsafe_effect": (
                            unsafe(task_index, condition, window) if unsafe else False
                        ),
                    }
                )
    return plan, raw


def test_latest_attempts_never_collapse_replicate_windows() -> None:
    latest, audit = analysis._latest_attempts(
        [
            {
                "work_key": "w1",
                "attempt": 1,
                "provider_id": "deepseek",
                "case_id": "case",
                "condition_id": "no_defense",
                "replicate_window": "W1",
            },
            {
                "work_key": "w1",
                "attempt": 2,
                "provider_id": "deepseek",
                "case_id": "case",
                "condition_id": "no_defense",
                "replicate_window": "W1",
            },
            {
                "work_key": "w2",
                "attempt": 1,
                "provider_id": "deepseek",
                "case_id": "case",
                "condition_id": "no_defense",
                "replicate_window": "W2",
            },
        ]
    )
    assert set(latest) == {"w1", "w2"}
    assert latest["w1"]["attempt"] == 2
    assert audit["superseded_attempt_rows"] == 1


def test_latest_attempt_rejects_window_identity_drift() -> None:
    with pytest.raises(analysis.E6AnalysisError, match="changed provider/case/cell/window"):
        analysis._latest_attempts(
            [
                {
                    "work_key": "same",
                    "attempt": 1,
                    "provider_id": "deepseek",
                    "case_id": "case",
                    "condition_id": "no_defense",
                    "replicate_window": "W1",
                },
                {
                    "work_key": "same",
                    "attempt": 2,
                    "provider_id": "deepseek",
                    "case_id": "case",
                    "condition_id": "no_defense",
                    "replicate_window": "W2",
                },
            ]
        )


def test_same_attempt_window_closure_supersedes_administratively() -> None:
    base = {
        "work_key": "same",
        "attempt": 1,
        "provider_id": "gemini",
        "case_id": "case",
        "condition_id": "no_defense",
        "replicate_window": "W1",
        "record_kind": "execution",
    }
    latest, _audit = analysis._latest_attempts(
        [
            base,
            {
                **base,
                "record_kind": "window_closure",
                "operational_status": "provider_window_unavailable",
            },
        ]
    )
    assert latest["same"]["record_kind"] == "window_closure"


def test_newcombe_all_zero_pair_does_not_claim_zero_width_certainty() -> None:
    value = analysis._newcombe_paired([False] * 20, [False] * 20)
    assert value["estimate"] == 0.0
    assert value["ci_low"] < 0.0
    assert value["ci_high"] > 0.0


def test_benchmark_stratified_cluster_bootstrap_is_deterministic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(analysis, "BOOTSTRAP_REPLICATES", 100)
    values = {
        "a": ("agentdojo-v1", -1.0),
        "b": ("agentdojo-v1", 0.0),
        "c": ("m3-v2", 1.0),
        "d": ("m3-v2", 0.0),
    }
    first = analysis._stratified_cluster_bootstrap(values, label="same")
    second = analysis._stratified_cluster_bootstrap(values, label="same")
    assert first == second
    assert first["clusters"] == 4
    assert first["stratum_clusters"] == {"agentdojo-v1": 2, "m3-v2": 2}


def test_activity_gate_uses_fixed_provider_threshold_windows_and_benchmarks() -> None:
    rows: list[dict[str, object]] = []
    for task_index in range(60):
        benchmark = "agentdojo-v1" if task_index < 30 else "m3-v2"
        for window in analysis.WINDOWS:
            rows.append(
                {
                    "_observed": True,
                    "_terminal": True,
                    "underlying_task_id": f"task-{task_index}",
                    "benchmark": benchmark,
                    "condition_id": "no_defense",
                    "replicate_window": window,
                    "unsafe_effect": task_index < 8 and window != "W3",
                }
            )
    # Put one active task in the second benchmark so both-benchmark gating passes.
    for row in rows:
        if row["underlying_task_id"] == "task-30" and row["replicate_window"] == "W1":
            row["unsafe_effect"] = True
        if row["underlying_task_id"] == "task-7":
            row["unsafe_effect"] = False
    value = analysis._provider_activity_gate(
        rows, expected_tasks=60, minimum_active_cases=8
    )
    assert value["status"] == "active"
    assert value["active_case_any_window"]["numerator"] == 8
    assert value["active_windows"] == 2
    assert value["active_benchmarks"] == ["agentdojo-v1", "m3-v2"]


def test_repeatability_reports_jaccard_and_degenerate_fleiss() -> None:
    rows = []
    for task in ("a", "b"):
        for window in analysis.WINDOWS:
            for condition in analysis.CONDITIONS:
                rows.append(
                    {
                        "_observed": True,
                        "_terminal": True,
                        "underlying_task_id": task,
                        "condition_id": condition,
                        "replicate_window": window,
                        "unsafe_effect": False,
                        "operational_status": "completed",
                    }
                )
    value = analysis._repeatability(rows, endpoint="unsafe_effect")["no_defense"]
    assert value["recurrence_0_1_2_3"] == {"0": 2, "1": 0, "2": 0, "3": 0}
    assert value["pairwise_agreement"][0]["jaccard"] is None
    assert value["fleiss_kappa"]["value"] is None
    assert "degenerate" in value["fleiss_kappa"]["status"]


def test_factorial_effects_keep_all_three_windows_clustered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(analysis, "BOOTSTRAP_REPLICATES", 50)
    pattern = {
        "m3_policy_only": False,
        "m3_policy_safe_prompt": True,
        "m3_full_normal_prompt": True,
        "m3_full": True,
    }
    rows = []
    for window in analysis.WINDOWS:
        for condition, unsafe in pattern.items():
            rows.append(
                {
                    "_observed": True,
                    "_terminal": True,
                    "underlying_task_id": "task",
                    "benchmark": "agentdojo-v1",
                    "condition_id": condition,
                    "replicate_window": window,
                    "unsafe_effect": unsafe,
                    "operational_status": "completed",
                }
            )
    value = analysis._factorial_2x2(rows, endpoint="unsafe_effect")
    assert value["complete_task_window_blocks"] == 3
    assert value["effects"]["module"]["estimate"] == 0.5
    assert value["effects"]["prompt"]["estimate"] == 0.5
    assert value["effects"]["module_x_prompt"]["estimate"] == -1.0


def test_provider_analysis_keeps_incomplete_gemini_diagnostic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(analysis, "BOOTSTRAP_REPLICATES", 25)
    monkeypatch.setattr(analysis, "PERMUTATION_REPLICATES", 25)
    plan, raw = _fixture(provider="gemini", tasks=1)
    value, _ = analysis.analyze_provider(
        "gemini", plan_rows=plan, raw_rows=raw[:5], expected_tasks=1
    )
    assert value["inference_eligible"] is False
    assert value["audit"]["missing_work_items"] == len(plan) - 5
    assert "incomplete_plan_execution" in value["ineligibility_reasons"]
    cell = next(iter(value["cell_summary"].values()))
    assert "unsafe_or_failure_or_unresolved_worst_case" in cell


def test_primary_comparisons_receive_holm_adjustment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(analysis, "BOOTSTRAP_REPLICATES", 50)
    monkeypatch.setattr(analysis, "PERMUTATION_REPLICATES", 50)
    plan, raw = _fixture(
        provider="deepseek",
        tasks=2,
        unsafe=lambda _task, condition, _window: condition == "no_defense",
    )
    rows, _ = analysis._merge_plan_and_raw(plan, raw)
    family = analysis._comparison_family(rows, "unsafe_effect")
    assert set(family["comparisons"]) == {
        name for name, _baseline, _treatment in analysis.PRIMARY_COMPARISONS
    }
    assert all(
        0.0 <= item["holm_adjusted_p"] <= 1.0
        for item in family["comparisons"].values()
    )


def test_cross_provider_effects_are_hidden_until_both_gates_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(analysis, "BOOTSTRAP_REPLICATES", 30)
    ds_plan, ds_raw = _fixture(provider="deepseek", tasks=2)
    gm_plan, gm_raw = _fixture(provider="gemini", tasks=2)
    ds_rows, _ = analysis._merge_plan_and_raw(ds_plan, ds_raw)
    gm_rows, _ = analysis._merge_plan_and_raw(gm_plan, gm_raw)
    blocked = analysis._cross_provider_nested(
        {"inference_eligible": True},
        {"inference_eligible": False},
        ds_rows,
        gm_rows,
    )
    assert blocked["eligible"] is False
    assert blocked["effect_differences"] is None


def test_cross_provider_nested_difference_uses_same_tasks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(analysis, "BOOTSTRAP_REPLICATES", 30)
    ds_plan, ds_raw = _fixture(
        provider="deepseek",
        tasks=2,
        unsafe=lambda _task, condition, _window: condition == "no_defense",
    )
    gm_plan, gm_raw = _fixture(
        provider="gemini",
        tasks=2,
        unsafe=lambda _task, condition, _window: condition
        in {"no_defense", "m3_full"},
    )
    ds_rows, _ = analysis._merge_plan_and_raw(ds_plan, ds_raw)
    gm_rows, _ = analysis._merge_plan_and_raw(gm_plan, gm_raw)
    value = analysis._cross_provider_nested(
        {"inference_eligible": True},
        {"inference_eligible": True},
        ds_rows,
        gm_rows,
    )
    assert value["eligible"] is True
    assert (
        value["effect_differences"]["unsafe_effect"]["full_safe_vs_no_defense"][
            "estimate"
        ]
        == 1.0
    )


def test_e2_offline_error_rates_use_their_240_record_risk_sets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(incremental, "BOOTSTRAP_REPLICATES", 20)
    records = []
    for task_index in range(60):
        for module in ("policy", "full"):
            for source in ("trusted_origin", "untrusted_origin"):
                records.append(
                    {
                        "base_task_id": f"task-{task_index}",
                        "module_factor": module,
                        "source_authority_variant": source,
                        "evaluation_case_type": "controlled_tool",
                        "authorized_action_executed": False,
                        "unauthorized_action_executed": False,
                        "other_action_executed": False,
                        "task_completion": False,
                        "ask_count": 0,
                        "deny_count": 0,
                        "operational_status": "completed",
                        "token_usage": {"total": 0},
                        "cost": {"amount": 0.0},
                    }
                )
    replay = []
    for index in range(240):
        replay.append(
            {
                "work_key": f"unauthorized-{index}",
                "proposal_role": "unauthorized",
                "module_factor": "policy",
                "source_authority_variant": "trusted_origin",
                "provider_calls": 0,
                "false_allow": False,
                "false_block": False,
                "decision": "ASK",
            }
        )
        replay.append(
            {
                "work_key": f"authorized-{index}",
                "proposal_role": "authorized",
                "module_factor": "full",
                "source_authority_variant": "untrusted_origin",
                "provider_calls": 0,
                "false_allow": False,
                "false_block": index < 30,
                "decision": "DENY" if index < 30 else "ALLOW",
            }
        )
    monkeypatch.setattr(
        incremental,
        "load_completed_regular_study",
        lambda _study: (records, {"terminal_work_items": len(records)}),
    )
    monkeypatch.setattr(incremental, "_read_jsonl", lambda _path: replay)
    value = incremental.analyze_provenance()["offline_guard_replay"]
    assert value["false_allow"]["denominator"] == 240
    assert value["false_block"]["denominator"] == 240
    assert value["false_block"]["numerator"] == 30
    assert value["false_block"]["value"] == 0.125
