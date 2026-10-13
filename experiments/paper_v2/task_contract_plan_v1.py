"""600基础任务的新研究公开计划；只生成输入引用和执行元数据。

36,000主矩阵项包含可跳过的Gemini12,000上限。Pro960消融沿用
主矩阵对应new_full作配对基线；任何行都不是模型响应或实验结果。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from experiments.paper_v2.task_contract_cases_v1 import (
    OUTPUT, ROOT, _write_new_or_same, build_case_cohorts,
    contains_sensitive_fields, write_case_assets,
)
from experiments.paper_v2.task_contract_synthetic_v1 import FAMILIES, SEED


SCOPE = "task_contract_v3_validation_v1"
MODELS = {"pro": "deepseek-v4-pro", "flash": "deepseek-flash", "gemini": "gemini-3.6-flash"}
SERVICE_VERSIONS = {"pro": "DeepSeek-V4-Pro-0813", "flash": "DeepSeek-V4.1-Flash", "gemini": "gemini-3.6-flash"}
MAIN_CONDITIONS = ("no_defense", "old_policy", "old_full", "new_policy", "new_full")
ABLATIONS = ("lexical_contract", "static_binding", "whole_call_source")
MAX_PROVIDER_CALLS = 12
FORMAL_PREFIX_ROWS = 50


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _rank(purpose: str, value: str) -> str:
    return hashlib.sha256((SEED + "\0" + purpose + "\0" + value).encode()).hexdigest()


def _prefix_cases(cases: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    chosen = []
    for benchmark in ("agentdojo-v1", "m3-v2"):
        chosen.append(min((case for case in cases if case["benchmark"] == benchmark), key=lambda case: _rank("prefix", str(case["base_task_id"]))))
    for family in FAMILIES:
        chosen.append(min((case for case in cases if case["benchmark"] == "task-contract-synthetic-v1" and case["family"] == family), key=lambda case: _rank("prefix", str(case["base_task_id"]))))
    if len({case["base_task_id"] for case in chosen}) != 10:
        raise ValueError("formal prefix requires ten distinct preselected cases")
    return chosen


def _plan_row(case: Mapping[str, Any], *, model: str, condition: str,
              scenario: str, repeat: int, part: str) -> dict[str, Any]:
    if model not in MODELS or repeat not in {1, 2} or scenario not in {"benign", "attack"}:
        raise ValueError("unsupported model/repeat/scenario")
    row = copy.deepcopy(dict(case))
    benign_reference = copy.deepcopy(case["source_reference"])
    source_reference = copy.deepcopy(case.get("attack_reference", benign_reference) if scenario == "attack" else benign_reference)
    case_id = str(case.get("attack_case_id", case["case_id"]) if scenario == "attack" else case["case_id"])
    identity = {"scope": SCOPE, "part": part, "base_task_id": case["base_task_id"], "model": MODELS[model],
                "condition": condition, "scenario": scenario, "repeat": repeat}
    work_key = hashlib.sha256(_json(identity).encode()).hexdigest()
    old = condition.startswith("old_")
    guarded = condition != "no_defense"
    module = "policy" if condition.endswith("policy") else "full" if guarded else None
    row.update({
        "schema_version": "task-contract-plan-1.0", "study_id": SCOPE, "study": "task_contract",
        "scope": SCOPE, "study_part": part, "model_key": model, "model_id": MODELS[model],
        "provider_id": "gemini" if model == "gemini" else "deepseek",
        "model_group": "gemini_flash" if model == "gemini" else f"deepseek_{model}",
        "expected_returned_model_version": SERVICE_VERSIONS[model],
        "model_role": "optional_cross_provider" if model == "gemini" else "primary" if model == "pro" else "same_provider_replication",
        "model_optional": model == "gemini", "condition_id": condition,
        "compiler_revision": "corrected_v2" if old else "task_contract_v3" if guarded else None,
        "module_factor": module, "prompt_factor": "normal", "prompt_profile": "normal",
        "authorization_regime": "auto_compiled", "oracle_used": False,
        "scenario": scenario, "evaluation_case_type": "attack" if scenario == "attack" else "benign_tool",
        "repeat": repeat, "attempt": 1, "status": "pending", "work_key": work_key,
        "replicate_index": repeat,
        "execution_identity": hashlib.sha256(_json({"scope": SCOPE, "model": MODELS[model], "part": part, "seed": SEED, "calls": MAX_PROVIDER_CALLS}).encode()).hexdigest(),
        "run_id": f"task-contract-{part}-{model}-v1", "case_id": case_id,
        "selection_id": f"task-contract-v3:{case['base_task_id']}:{scenario}",
        "source_reference": source_reference, "source_record_sha256": source_reference.get("sha256"),
        "benign_source_reference": benign_reference, "compile_source_reference": benign_reference,
        "compile_case_id": case["case_id"], "underlying_task_id": case["base_task_id"],
        "runtime_revision": SCOPE, "runtime_version": SCOPE,
        "max_provider_calls": MAX_PROVIDER_CALLS, "temperature": 0,
        "max_tokens": 2048 if model == "gemini" else 512, "timeout_seconds": 180,
        "thinking_level": "low" if model == "gemini" else None,
        "automatic_retries": 0, "no_response_recovery_limit": 1,
        "retry_http_statuses": [503] if model == "gemini" else [],
        "stop_on_http_statuses": [429, 401, 403, 404],
        "no_response_recovery_counts_towards_call_cap": True,
        "provider_tools_enabled": False, "external_effects_enabled": False,
        "draft_model_id": "deepseek-v4-pro" if guarded and not old else None,
        "draft_shared_across_conditions_models_repeats": guarded and not old,
        "draft_max_tokens": 4096, "draft_temperature": 0, "draft_timeout_seconds": 180,
    })
    if part == "ablation":
        row["module_factor"] = "full"
        row["ablation_id"] = condition
        row["ablation_profile"] = condition
        row["paired_main_condition"] = "new_full"
    if contains_sensitive_fields(row):
        raise ValueError("public plans must contain no input bodies or offline labels")
    return row


def build_main_plan(cases: Sequence[Mapping[str, Any]], model: str) -> list[dict[str, Any]]:
    if len(cases) != 600 or len({case["base_task_id"] for case in cases}) != 600:
        raise ValueError("main matrix requires600 distinct evaluation base-task IDs")
    prefix = _prefix_cases(cases)
    ordered = prefix + sorted((case for case in cases if case["base_task_id"] not in {item["base_task_id"] for item in prefix}), key=lambda case: _rank("task_order", str(case["base_task_id"])))
    blocks = [(case, "benign", 1) for case in prefix]
    blocks.extend((case, scenario, repeat) for case in ordered for scenario in ("benign", "attack")
                  for repeat in (1, 2) if not (scenario == "benign" and repeat == 1 and case in prefix))
    result = []
    for block_index, (case, scenario, repeat) in enumerate(blocks):
        rotation = block_index % len(MAIN_CONDITIONS)
        conditions = MAIN_CONDITIONS[rotation:] + MAIN_CONDITIONS[:rotation]
        for condition_position, condition in enumerate(conditions, 1):
            row = _plan_row(case, model=model, condition=condition, scenario=scenario, repeat=repeat, part="main")
            row.update({"sequence": len(result) + 1, "block_id": f"{case['base_task_id']}:{scenario}:r{repeat}",
                        "block_position": block_index + 1, "condition_order_position": condition_position,
                        "formal_prefix": len(result) < FORMAL_PREFIX_ROWS})
            result.append(row)
    if len(result) != 12000 or len({row["work_key"] for row in result}) != 12000:
        raise ValueError("main model plan count/identity mismatch")
    return result


def select_ablation_cases(cases: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    selected = []
    for family in FAMILIES:
        for language in ("zh", "en"):
            pool = sorted((case for case in cases if case["benchmark"] == "task-contract-synthetic-v1" and case["family"] == family and case["language"] == language), key=lambda case: _rank("ablation", str(case["base_task_id"])))
            selected.extend(pool[:5])
    if len(selected) != 80 or len({case["base_task_id"] for case in selected}) != 80:
        raise ValueError("ablation requires80 base tasks, five per language/family")
    return selected


def build_ablation_plan(cases: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for case in select_ablation_cases(cases):
        for scenario in ("benign", "attack"):
            for repeat in (1, 2):
                for ablation in ABLATIONS:
                    row = _plan_row(case, model="pro", condition=ablation, scenario=scenario, repeat=repeat, part="ablation")
                    row.update({"sequence": len(result) + 1, "formal_prefix": False,
                                "block_id": f"{case['base_task_id']}:{scenario}:r{repeat}"})
                    result.append(row)
    if len(result) != 960 or len({row["work_key"] for row in result}) != 960:
        raise ValueError("ablation plan count/identity mismatch")
    return result


def compiler_development_cases(cases: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """全部157开发任务；是否生成多草稿及调用量由运行协调器决定。"""
    selected = sorted(cases, key=lambda case: _rank("compiler_development", str(case["base_task_id"])))
    if len(selected) != 157 or any(case["split"] != "development" for case in selected):
        raise ValueError("compiler development set must contain157 development tasks")
    return selected


def write_plans(output_root: Path = OUTPUT) -> dict[str, Any]:
    output_root = Path(output_root).resolve()
    if output_root != OUTPUT.resolve():
        raise ValueError("study output path must match approved isolated directory")
    dataset = write_case_assets(output_root)
    cohorts = build_case_cohorts()
    summary: dict[str, Any] = {"schema_version": "task-contract-plan-1.0", "study_id": SCOPE,
        "selection_seed": SEED, "base_tasks": 600, "main_planned_executions": 36000,
        "primary_deepseek_executions": 24000, "optional_gemini_executions_upper_bound": 12000,
        "pro_ablation_executions": 960, "repeat_count": 2, "main_conditions": list(MAIN_CONDITIONS),
        "compiler_generation": {"provider": "deepseek", "model_id": "deepseek-v4-pro", "max_tokens": 4096, "temperature": 0, "timeout_seconds": 180, "shared_draft_per_base_task": True},
        "gemini_diagnostic_requests": 6, "formal_prefix_executions_per_model": 50,
        "formal_prefix_is_complete_base_scene_repeat_block": False,
        "max_provider_calls_per_execution": MAX_PROVIDER_CALLS, "models": {},
        "dataset_summary": dataset, "model_responses_created": 0,
        "comparison_unit": "base task; AgentDojo connected-family clustered, M3 template clustered, synthetic generative family sensitivity"}
    for model in MODELS:
        rows = build_main_plan(cohorts["evaluation"], model)
        path = output_root / "plans" / model / "main_plan_v1.jsonl"
        _write_new_or_same(path, "".join(_json(row) + "\n" for row in rows))
        summary["models"][model] = {"model_id": MODELS[model], "optional": model == "gemini", "planned_records": len(rows),
                                    "plan_path": path.relative_to(ROOT).as_posix(), "max_provider_calls": len(rows) * MAX_PROVIDER_CALLS}
    ablation = build_ablation_plan(cohorts["evaluation"])
    _write_new_or_same(output_root / "plans/pro/ablation_plan_v1.jsonl", "".join(_json(row) + "\n" for row in ablation))
    development = compiler_development_cases(cohorts["development"])
    _write_new_or_same(output_root / "assets/compiler_development_cases_v1.jsonl", "".join(_json(dict(row)) + "\n" for row in development))
    _write_new_or_same(output_root / "plans/plan_summary_v1.json", _json(summary) + "\n")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=OUTPUT)
    args = parser.parse_args(argv)
    summary = write_plans(args.output_root)
    print(_json({key: summary[key] for key in ("base_tasks", "main_planned_executions", "primary_deepseek_executions", "optional_gemini_executions_upper_bound", "pro_ablation_executions", "model_responses_created")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
