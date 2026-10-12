"""强化实验冻结方案的公开接口验收；不调用模型或执行工具。"""

from collections import Counter
import json
from pathlib import Path

import pytest

from experiments.paper_v2 import empirical_reinforcement_plan_v1 as plan


@pytest.fixture(scope="module")
def cohorts() -> dict:
    # 同一次资格化只读取历史选择来源一次，不在每个测试重算旧结果。
    return plan.build_cases()


def test_fixed_utility_and_activity_cohorts_are_available(cohorts: dict) -> None:
    assert {key: len(rows) for key, rows in cohorts.items()} == {
        "utility_pro": 217,
        "utility_flash": 120,
        "activity_pro": 80,
        "activity_flash": 40,
    }


def test_execution_plans_have_fixed_work_and_call_budgets(cohorts: dict) -> None:
    expected = {
        "utility_pro": 1085,
        "utility_flash": 600,
        "activity_pro": 320,
        "activity_flash": 160,
    }
    plans = {
        key: plan.build_plan(rows, *key.split("_")) for key, rows in cohorts.items()
    }

    assert {key: len(rows) for key, rows in plans.items()} == expected
    combined = [row for rows in plans.values() for row in rows]
    assert len({row["work_key"] for row in combined}) == 2165
    assert sum(row["max_provider_calls"] for row in combined) == 18280
    assert Counter(row["max_provider_calls"] for row in combined) == {8: 2045, 16: 120}


def test_exact_target_plans_require_explicit_corrected_runtime(cohorts: dict) -> None:
    rows = plan.build_plan(cohorts["utility_pro"], "utility", "pro")
    assert all(row["runtime_revision"] == "corrected_v2" for row in rows)
    assert all(row["runtime_version"] == "corrected_v2" for row in rows)
    assert all(row["compiler_revision"] == "corrected_v2" for row in rows)
    assert {row["model_group"] for row in rows} == {"deepseek_pro"}
    assert {row["expected_returned_model_version"] for row in rows} == {
        "DeepSeek-V4-Pro-0813"
    }
    assert {row["benchmark"]: row["effective_compiler_id"] for row in rows} == {
        "agentdojo-v1": "compile_generic_task_policy_corrected_v2",
        "m3-v2": "compile_task_policy_corrected_v1",
    }


@pytest.mark.parametrize(
    "model,agent_count,profile_count", [("pro", 97, 20), ("flash", 60, 10)]
)
def test_utility_strata_and_confirmation_denominators_are_preserved(
    cohorts: dict,
    model: str,
    agent_count: int,
    profile_count: int,
) -> None:
    rows = cohorts[f"utility_{model}"]
    agent = [row for row in rows if row["benchmark"] == "agentdojo-v1"]
    m3 = [row for row in rows if row["benchmark"] == "m3-v2"]
    assert len(agent) == agent_count
    assert Counter(row["selection_stratum"]["suite"] for row in agent) == (
        {"banking": 16, "slack": 21, "travel": 20, "workspace": 40}
        if model == "pro"
        else {"banking": 10, "slack": 13, "travel": 12, "workspace": 25}
    )
    assert Counter(row["authorization_profile"] for row in m3) == {
        "auto_compiled_exact": profile_count,
        "trusted_context_exact": profile_count,
        "ambiguous_recipient": profile_count,
        "partial_resource_scope": profile_count,
        "dynamic_parameter": profile_count,
        "legal_cross_tool_chain": profile_count,
    }
    assert sum(row["requires_confirmation"] for row in m3) == 2 * profile_count
    assert {row["scenario_type"] for row in m3} == {
        "file_write",
        "email_send",
        "api_call",
        "multi_step",
    }
    assert len({row["underlying_task_id"] for row in rows}) == len(rows)


@pytest.mark.parametrize("study", ["utility", "activity"])
def test_flash_is_strictly_nested_by_task_case_and_source_reference(
    cohorts: dict, study: str
) -> None:
    primary = {row["case_id"]: row for row in cohorts[f"{study}_pro"]}
    for row in cohorts[f"{study}_flash"]:
        assert row == primary[row["case_id"]]


def test_activity_nested_sample_keeps_all_eligible_selected_attack_families(
    cohorts: dict,
) -> None:
    primary = {
        row["selection_stratum"]["attack_family"]
        for row in cohorts["activity_pro"]
        if row["benchmark"] == "m3-v2"
    }
    nested = {
        row["selection_stratum"]["attack_family"]
        for row in cohorts["activity_flash"]
        if row["benchmark"] == "m3-v2"
    }
    assert nested == primary


@pytest.mark.parametrize("model", ["pro", "flash"])
def test_utility_old_thirty_tasks_per_benchmark_are_anchors(
    cohorts: dict, model: str
) -> None:
    # 直接读取独立冻结锚点，不按生成器输出推导。
    anchors = [
        json.loads(line)
        for line in plan.ANCHOR_PATH.read_text(encoding="utf-8").splitlines()
    ]
    old = {
        (row["benchmark"], row["case_id"])
        for row in anchors
        if row["evaluation_case_type"] == "benign_tool"
    }
    selected = {
        (row["benchmark"], row["case_id"])
        for row in cohorts[f"utility_{model}"]
        if row["legacy_lean_anchor"]
    }
    assert selected == old
    assert len(selected) == 60


@pytest.mark.parametrize("model", ["pro", "flash"])
def test_activity_uses_historical_control_candidates_once_per_task(
    cohorts: dict, model: str
) -> None:
    rows = cohorts[f"activity_{model}"]
    quota = 40 if model == "pro" else 20
    assert Counter(row["benchmark"] for row in rows) == {
        "agentdojo-v1": quota,
        "m3-v2": quota,
    }
    assert len({row["underlying_task_id"] for row in rows}) == 2 * quota
    assert {
        row["selection_stratum"]["suite"]
        for row in rows
        if row["benchmark"] == "agentdojo-v1"
    } == {"banking", "slack", "travel", "workspace"}
    assert all(row["prior_outcome_selected"] for row in rows)
    for row in rows:
        assert row["historical_control_conditions"]
        assert set(row["historical_control_conditions"]) <= {
            "no_defense",
            "strongest_peer_reviewed_structural_baseline",
        }


@pytest.mark.parametrize(
    "study,model,prefix_count,task_count",
    [
        ("utility", "pro", 30, 6),
        ("utility", "flash", 30, 6),
        ("activity", "pro", 16, 4),
        ("activity", "flash", 16, 4),
    ],
)
def test_formal_prefix_and_order_are_part_of_the_same_plan(
    cohorts: dict,
    study: str,
    model: str,
    prefix_count: int,
    task_count: int,
) -> None:
    rows = plan.build_plan(cohorts[f"{study}_{model}"], study, model)
    assert sum(row["formal_prefix"] for row in rows) == prefix_count
    assert all(row["formal_prefix"] for row in rows[:prefix_count])
    assert not any(row["formal_prefix"] for row in rows[prefix_count:])
    prefix = rows[:prefix_count]
    assert len({row["underlying_task_id"] for row in prefix}) == task_count
    assert Counter(row["benchmark"] for row in prefix) == {
        "agentdojo-v1": prefix_count // 2,
        "m3-v2": prefix_count // 2,
    }
    if study == "utility":
        assert {"simple", "multistep", "confirmation", "mock_api"} <= {
            row["prefix_task_type"] for row in prefix
        }
    tasks = [row for row in rows if row["condition_order_position"] == 1]
    assert all(
        tasks[index]["benchmark"] != tasks[index - 1]["benchmark"]
        for index in range(
            1,
            min(
                2 * sum(row["benchmark"] == "agentdojo-v1" for row in tasks), len(tasks)
            ),
        )
    )
    assert (
        max(
            Counter(
                row["condition_id"] + ":" + row["authorization_regime"] for row in tasks
            ).values()
        )
        - min(
            Counter(
                row["condition_id"] + ":" + row["authorization_regime"] for row in tasks
            ).values()
        )
        <= 1
    )


@pytest.mark.parametrize("study", ["utility", "activity"])
def test_only_preregistered_condition_regime_cells_are_created(
    cohorts: dict, study: str
) -> None:
    rows = plan.build_plan(cohorts[f"{study}_pro"], study, "pro")
    cells = {(row["condition_id"], row["authorization_regime"]) for row in rows}
    assert cells == (
        {
            ("no_defense", "auto_compiled"),
            ("m3_policy_only", "auto_compiled"),
            ("m3_full_normal_prompt", "auto_compiled"),
            ("m3_policy_only", "exact_target_v2"),
            ("m3_full_normal_prompt", "exact_target_v2"),
        }
        if study == "utility"
        else {
            ("no_defense", "auto_compiled"),
            ("strongest_peer_reviewed_structural_baseline", "auto_compiled"),
            ("m3_policy_only", "auto_compiled"),
            ("m3_full_normal_prompt", "auto_compiled"),
        }
    )
    assert all(row["prompt_factor"] == "normal" for row in rows)
    assert all(
        row["automatic_retries"] == 0
        and not row["provider_tools_enabled"]
        and not row["external_effects_enabled"]
        for row in rows
    )


def test_public_plan_contains_only_source_digests_not_prompt_gold_or_secrets(
    cohorts: dict,
) -> None:
    forbidden = {
        "trusted_user_request",
        "trusted_app_context",
        "untrusted_content",
        "untrusted_memory",
        "offline_evaluation",
        "gold",
        "evaluator",
        "unsafe_effect_itt",
        "task_completion_itt",
        "response_body",
        "request_body",
        "messages",
        "api_key",
        "Authorization",
    }

    def check(value: object) -> None:
        if isinstance(value, dict):
            assert not (forbidden & value.keys())
            for child in value.values():
                check(child)
        elif isinstance(value, list):
            for child in value:
                check(child)

    for key, cases in cohorts.items():
        rows = plan.build_plan(cases, *key.split("_"))
        check(rows)
        for row in rows:
            source = row["source_reference"]
            assert set(source) == {"path", "line", "sha256"}
            assert source["line"] >= 1
            assert source["sha256"] == row["source_record_sha256"]
            assert len(source["sha256"]) == 64
            assert (plan.PROJECT_ROOT / source["path"]).is_file()


def test_repeated_builds_and_aliases_have_identical_work_identity(
    cohorts: dict,
) -> None:
    first = plan.build_plan(cohorts["utility_pro"], "utility", "pro")
    second = plan.build_plan(cohorts["utility_pro"], "R1", "deepseek_pro")
    assert first == second
    assert plan.build_plan(
        cohorts["activity_flash"], "R2", "deepseek-flash"
    ) == plan.build_plan(cohorts["activity_flash"], "activity", "flash")


def test_duplicate_tasks_and_unknown_dispatch_are_rejected(cohorts: dict) -> None:
    duplicate = cohorts["utility_flash"][:-1] + [cohorts["utility_flash"][0]]
    with pytest.raises(plan.ReinforcementPlanError, match="duplicate underlying"):
        plan.build_plan(duplicate, "utility", "flash")
    with pytest.raises(plan.ReinforcementPlanError, match="unknown study"):
        plan.build_plan(cohorts["utility_pro"], "E7", "pro")
    with pytest.raises(plan.ReinforcementPlanError, match="unknown model"):
        plan.build_plan(cohorts["utility_pro"], "utility", "gemini")
    with pytest.raises(plan.ReinforcementPlanError, match="cohort count"):
        plan.build_plan(cohorts["utility_pro"][:-1], "utility", "pro")


def test_accidental_evaluator_fields_cannot_enter_exported_plan(cohorts: dict) -> None:
    injected = [dict(row) for row in cohorts["utility_flash"]]
    injected[0]["offline_evaluation"] = {"gold": "synthetic-test-only"}
    with pytest.raises(plan.ReinforcementPlanError, match="forbidden"):
        plan.build_plan(injected, "utility", "flash")


def test_written_freeze_is_reproducible_and_does_not_overwrite_conflicts(
    tmp_path: Path,
    cohorts: dict,
) -> None:
    manifest = plan.write_plans(tmp_path, cases=cohorts)
    assert manifest["planned_records"] == 2165
    assert manifest["max_provider_calls"] == 18280
    assert manifest["selection_seed"] == "m3-reinforcement-20261012-v1"
    assert manifest["plans"]["utility_pro"]["plan_path"] == "utility/pro/plan_v1.jsonl"
    assert (
        manifest["plans"]["activity_flash"]["cases_path"]
        == "activity/flash/cases_v1.jsonl"
    )
    saved = {
        file.relative_to(tmp_path).as_posix(): file.read_bytes()
        for file in tmp_path.rglob("*")
        if file.is_file()
    }
    assert len(saved) == 9  # 每队列case/plan及唯一manifest，不生成递归包。
    assert json.loads(saved["manifest_v1.json"]) == manifest
    assert plan.write_plans(tmp_path, cases=cohorts) == manifest
    assert saved == {
        file.relative_to(tmp_path).as_posix(): file.read_bytes()
        for file in tmp_path.rglob("*")
        if file.is_file()
    }
    broken = tmp_path / "utility" / "pro" / "plan_v1.jsonl"
    broken.write_text("user-owned conflicting freeze\n", encoding="utf-8")
    with pytest.raises(plan.ReinforcementPlanError, match="conflict"):
        plan.write_plans(tmp_path, cases=cohorts)
    assert broken.read_text(encoding="utf-8") == "user-owned conflicting freeze\n"
