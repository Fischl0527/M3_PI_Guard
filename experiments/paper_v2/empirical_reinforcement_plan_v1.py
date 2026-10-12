"""冻结强化实证研究样本：只导出元数据，不访问凭据或调用模型。

生成并固化 2,165 样本项的评测清单，锁定输入与评测边界。
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.e6_cross_provider_calibration_plan_v1 import (
    _historical_control_unsafe,
    _public_source_cases,
    _underlying_task_id,
)
from experiments.paper_v2.research_assets import (
    AGENTDOJO_UTILITY,
    M3_HOLDOUT,
    M3_VALIDATION,
    PROJECT_ROOT,
)


SELECTION_SEED = "m3-reinforcement-20261012-v1"
SCHEMA_VERSION = "m3-empirical-reinforcement-1.0"
ANCHOR_PATH = (
    PROJECT_ROOT / "protocols/paper_upgrade_v2/lean_empirical_case_selection_v1.jsonl"
)
AGENT_FLASH_QUOTAS = {"banking": 10, "slack": 13, "travel": 12, "workspace": 25}
AUTHORIZATION_PROFILES = (
    "auto_compiled_exact",
    "trusted_context_exact",
    "ambiguous_recipient",
    "partial_resource_scope",
    "dynamic_parameter",
    "legal_cross_tool_chain",
)
MODELS = {"pro": "deepseek-v4-pro", "flash": "deepseek-flash"}
SERVICE_VERSIONS = {
    "pro": "DeepSeek-V4-Pro-0813",
    "flash": "DeepSeek-V4.1-Flash",
}
UTILITY_CELLS = (
    ("no_defense", "auto_compiled"),
    ("m3_policy_only", "auto_compiled"),
    ("m3_full_normal_prompt", "auto_compiled"),
    ("m3_policy_only", "exact_target_v2"),
    ("m3_full_normal_prompt", "exact_target_v2"),
)
ACTIVITY_CELLS = (
    ("no_defense", "auto_compiled"),
    ("strongest_peer_reviewed_structural_baseline", "auto_compiled"),
    ("m3_policy_only", "auto_compiled"),
    ("m3_full_normal_prompt", "auto_compiled"),
)
FORBIDDEN_PUBLIC_FIELDS = frozenset(
    {
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
        "authorization",
    }
)


class ReinforcementPlanError(ValueError):
    """固定样本、来源引用或执行条件不满足约定。"""


def _rank(purpose: str, value: str) -> str:
    return hashlib.sha256(f"{SELECTION_SEED}\0{purpose}\0{value}".encode()).hexdigest()


def _read_rows(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def _utility_metadata(path: Path) -> list[dict[str, Any]]:
    """内容只用于既有逐行摘要；公开投影不携带请求、答案或受保护内容。"""
    cases: list[dict[str, Any]] = []
    for number, row in enumerate(_read_rows(path), 1):
        is_agent = "benchmark_case_id" in row
        if not is_agent and row.get("sample_type") != "benign_legal_tool":
            continue
        case_id = str(row["benchmark_case_id"] if is_agent else row["case_id"])
        benchmark = "agentdojo-v1" if is_agent else "m3-v2"
        digest = sha256_canonical_json(row)
        profile = str(row.get("authorization_profile", "native_task"))
        stratum = {
            key: str(row[key])
            for key in (
                "suite",
                "split",
                "language",
                "authorization_profile",
                "scenario_type",
            )
            if key in row
        }
        stratum["sample_type"] = "benign_tool"
        underlying = (
            f"agentdojo:v1:{row['suite']}:{row['user_task_id']}"
            if is_agent
            else str(row["template_id"])
        )
        combined = is_agent and (
            (
                row["suite"] == "slack"
                and row["user_task_id"]
                in {"user_task_17", "user_task_18", "user_task_19", "user_task_20"}
            )
            or (
                row["suite"] == "workspace"
                and row["user_task_id"]
                in {
                    "user_task_4",
                    "user_task_19",
                    "user_task_23",
                    "user_task_36",
                    "user_task_37",
                    "user_task_38",
                    "user_task_39",
                }
            )
        )
        cases.append(
            {
                "schema_version": SCHEMA_VERSION,
                "benchmark": benchmark,
                "case_id": case_id,
                "underlying_task_id": underlying,
                "evaluation_case_type": "benign_tool",
                "selection_id": f"reinforcement-v1:{benchmark}:{case_id}",
                "source_reference": {
                    "path": path.relative_to(PROJECT_ROOT).as_posix(),
                    "line": number,
                    "sha256": digest,
                },
                "source_record_sha256": digest,
                "selection_stratum": stratum,
                "authorization_profile": profile,
                "scenario_type": str(row.get("scenario_type", "native_tool_task")),
                "native_combined_task": bool(combined),
                "requires_confirmation": profile
                in {"ambiguous_recipient", "partial_resource_scope"},
                "context_dependent": profile != "auto_compiled_exact",
                "sample_role": "expanded_benign_utility",
                "prior_outcome_selected": False,
            }
        )
    return cases


def _take_with_anchors(
    rows: Sequence[dict[str, Any]],
    count: int,
    anchors: set[str],
    purpose: str,
) -> list[dict[str, Any]]:
    by_id = {str(row["case_id"]): row for row in rows}
    if len(by_id) != len(rows) or not anchors <= by_id.keys() or len(anchors) > count:
        raise ReinforcementPlanError(
            f"{purpose}: duplicate, absent or excessive anchors"
        )
    chosen = [by_id[key] for key in sorted(anchors)]
    pending = sorted(
        (row for row in rows if row["case_id"] not in anchors),
        key=lambda row: _rank(purpose, str(row["case_id"])),
    )
    chosen.extend(pending[: count - len(chosen)])
    if len(chosen) != count:
        raise ReinforcementPlanError(f"{purpose}: insufficient distinct tasks")
    return chosen


def _interleave(rows: Sequence[dict[str, Any]], purpose: str) -> list[dict[str, Any]]:
    groups = {
        benchmark: sorted(
            [row for row in rows if row["benchmark"] == benchmark],
            key=lambda row: _rank(purpose, str(row["underlying_task_id"])),
        )
        for benchmark in ("agentdojo-v1", "m3-v2")
    }
    ordered: list[dict[str, Any]] = []
    for index in range(max(map(len, groups.values()), default=0)):
        for benchmark in groups:
            if index < len(groups[benchmark]):
                ordered.append(copy.deepcopy(groups[benchmark][index]))
    return ordered


def _activity_candidates() -> list[dict[str, Any]]:
    """仅使用旧 Public primary ND/VIGIL 阳性；不读取 E3/E6 新结果。"""
    sources = _public_source_cases()
    historical = _historical_control_unsafe()
    result: list[dict[str, Any]] = []
    for key, controls in historical.items():
        row = copy.deepcopy(sources[key])
        row.update(
            {
                "schema_version": SCHEMA_VERSION,
                "underlying_task_id": _underlying_task_id(*key),
                "historical_control_conditions": sorted(controls),
                "sample_role": "historical_control_enriched_activity",
                "prior_outcome_selected": True,
                "context_dependent": False,
            }
        )
        result.append(row)
    return result


def _take_activity(
    rows: Sequence[dict[str, Any]],
    count: int,
    purpose: str,
) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        field = "suite" if row["benchmark"] == "agentdojo-v1" else "attack_family"
        groups[str(row["selection_stratum"][field])].append(row)
    selected: list[dict[str, Any]] = []
    used: set[str] = set()
    for group in sorted(groups):
        for row in sorted(
            groups[group], key=lambda item: _rank(purpose, item["case_id"])
        ):
            if row["underlying_task_id"] not in used:
                selected.append(row)
                used.add(row["underlying_task_id"])
                break
    for row in sorted(rows, key=lambda item: _rank(purpose, item["case_id"])):
        if len(selected) == count:
            break
        if row["underlying_task_id"] not in used:
            selected.append(row)
            used.add(row["underlying_task_id"])
    if len(selected) != count or len(selected) < len(groups):
        raise ReinforcementPlanError(f"{purpose}: insufficient unique coverage")
    field = "suite" if rows[0]["benchmark"] == "agentdojo-v1" else "attack_family"
    covered = {str(row["selection_stratum"][field]) for row in selected}
    if covered != set(groups):
        raise ReinforcementPlanError(
            f"{purpose}: eligible coverage lost during task deduplication"
        )
    return selected


def build_cases() -> dict[str, list[dict[str, Any]]]:
    """返回四个冻结队列；Flash 严格嵌套，R1 两模型均包含旧30+30锚点。"""
    anchors: dict[str, set[str]] = defaultdict(set)
    for row in _read_rows(ANCHOR_PATH):
        if row["evaluation_case_type"] == "benign_tool":
            anchors[str(row["benchmark"])].add(str(row["case_id"]))
    if {key: len(value) for key, value in anchors.items()} != {
        "agentdojo-v1": 30,
        "m3-v2": 30,
    }:
        raise ReinforcementPlanError("legacy utility anchor count drift")
    agent = _utility_metadata(AGENTDOJO_UTILITY)
    m3 = _utility_metadata(M3_VALIDATION) + _utility_metadata(M3_HOLDOUT)
    utility_pro = list(agent)
    utility_flash: list[dict[str, Any]] = []
    for suite, quota in AGENT_FLASH_QUOTAS.items():
        pool = [row for row in agent if row["selection_stratum"]["suite"] == suite]
        ids = {row["case_id"] for row in pool}
        utility_flash.extend(
            _take_with_anchors(
                pool, quota, anchors["agentdojo-v1"] & ids, f"utility-flash:{suite}"
            )
        )
    for profile in AUTHORIZATION_PROFILES:
        pool = [row for row in m3 if row["authorization_profile"] == profile]
        ids = {row["case_id"] for row in pool}
        chosen = _take_with_anchors(
            pool, 20, anchors["m3-v2"] & ids, f"utility-pro:{profile}"
        )
        utility_pro.extend(chosen)
        utility_flash.extend(
            _take_with_anchors(
                chosen, 10, anchors["m3-v2"] & ids, f"utility-flash:{profile}"
            )
        )
    for row in (*utility_pro, *utility_flash):
        row["legacy_lean_anchor"] = row["case_id"] in anchors[row["benchmark"]]
    historical = _activity_candidates()
    activity_pro: list[dict[str, Any]] = []
    activity_flash: list[dict[str, Any]] = []
    for benchmark in ("agentdojo-v1", "m3-v2"):
        pool = [row for row in historical if row["benchmark"] == benchmark]
        selected = _take_activity(pool, 40, f"activity-pro:{benchmark}")
        activity_pro.extend(selected)
        activity_flash.extend(
            _take_activity(selected, 20, f"activity-flash:{benchmark}")
        )
    return {
        key: _interleave(rows, key)
        for key, rows in {
            "utility_pro": utility_pro,
            "utility_flash": utility_flash,
            "activity_pro": activity_pro,
            "activity_flash": activity_flash,
        }.items()
    }


def _study_key(study: str) -> str:
    value = {"R1": "utility", "R2": "activity"}.get(study, study)
    if value not in {"utility", "activity"}:
        raise ReinforcementPlanError(f"unknown study: {study}")
    return value


def _model_key(model: str) -> str:
    aliases = {
        "deepseek_pro": "pro",
        "deepseek_flash": "flash",
        **{value: key for key, value in MODELS.items()},
    }
    value = aliases.get(model, model)
    if value not in MODELS:
        raise ReinforcementPlanError(f"unknown model: {model}")
    return value


def _reject_private_fields(value: object) -> None:
    if isinstance(value, Mapping):
        if any(str(key).lower() in FORBIDDEN_PUBLIC_FIELDS for key in value):
            raise ReinforcementPlanError("forbidden content in public case metadata")
        for child in value.values():
            _reject_private_fields(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _reject_private_fields(child)


def _prefix_cases(
    rows: Sequence[dict[str, Any]],
    study: str,
) -> list[dict[str, Any]]:
    chosen: list[dict[str, Any]] = []

    def take(candidates: Sequence[dict[str, Any]], label: str) -> None:
        used = {row["underlying_task_id"] for row in chosen}
        available = [row for row in candidates if row["underlying_task_id"] not in used]
        if not available:
            raise ReinforcementPlanError(f"formal prefix missing stratum: {label}")
        row = copy.deepcopy(
            min(available, key=lambda item: _rank(label, item["case_id"]))
        )
        row["prefix_task_type"] = label
        chosen.append(row)

    agent = [row for row in rows if row["benchmark"] == "agentdojo-v1"]
    m3 = [row for row in rows if row["benchmark"] == "m3-v2"]
    if study == "utility":
        # 三对基准交替；官方组合任务提供多步骤覆盖，不按模型结果挑前缀。
        take([row for row in agent if row["native_combined_task"]], "multistep")
        take(
            [
                row
                for row in m3
                if row["authorization_profile"] == "auto_compiled_exact"
            ],
            "simple",
        )
        suite = chosen[0]["selection_stratum"]["suite"]
        take(
            [row for row in agent if row["selection_stratum"]["suite"] != suite],
            "native_tool_1",
        )
        take([row for row in m3 if row["requires_confirmation"]], "confirmation")
        suites = {
            row["selection_stratum"]["suite"]
            for row in chosen
            if row["benchmark"] == "agentdojo-v1"
        }
        take(
            [row for row in agent if row["selection_stratum"]["suite"] not in suites],
            "native_tool_2",
        )
        take([row for row in m3 if row["scenario_type"] == "api_call"], "mock_api")
    else:
        take(agent, "agent_attack_1")
        take(m3, "m3_attack_1")
        suite = chosen[0]["selection_stratum"]["suite"]
        take(
            [row for row in agent if row["selection_stratum"]["suite"] != suite],
            "agent_attack_2",
        )
        take(m3, "m3_attack_2")
    return chosen


def build_plan(
    cases: Sequence[dict[str, Any]],
    study: str,
    model: str,
) -> list[dict[str, Any]]:
    """将单队列展开成同期配对计划；前缀是正式行，不另造诊断样本。"""
    study = _study_key(study)
    model = _model_key(model)
    _reject_private_fields(cases)
    cells = UTILITY_CELLS if study == "utility" else ACTIVITY_CELLS
    keys = [row["underlying_task_id"] for row in cases]
    if len(set(keys)) != len(keys):
        raise ReinforcementPlanError("duplicate underlying task in cohort")
    expected = {
        ("utility", "pro"): 217,
        ("utility", "flash"): 120,
        ("activity", "pro"): 80,
        ("activity", "flash"): 40,
    }
    if len(cases) != expected[(study, model)]:
        raise ReinforcementPlanError("cohort count does not match frozen design")
    prefix = _prefix_cases(cases, study)
    prefix_ids = {row["underlying_task_id"] for row in prefix}
    ordered = prefix + _interleave(
        [row for row in cases if row["underlying_task_id"] not in prefix_ids],
        f"{study}:{model}:execution",
    )
    study_id = f"m3-empirical-reinforcement-{study}-v1"
    run_id = f"reinforcement-{study}-{model}-v1"
    execution_identity = sha256_canonical_json(
        {
            "study_id": study_id,
            "model_id": MODELS[model],
            "seed": SELECTION_SEED,
            "returned_model_version": SERVICE_VERSIONS[model],
            "runtime_revision": "corrected_v2",
            "compiler_revision": "corrected_v2",
            "cells": cells,
            "temperature": 0,
            "max_tokens": 512,
            "timeout_seconds": 180,
        }
    )
    result: list[dict[str, Any]] = []
    for task_rank, case in enumerate(ordered):
        rotation = task_rank % len(cells)
        rotated = cells[rotation:] + cells[:rotation]
        for position, (condition, regime) in enumerate(rotated):
            identity = {
                "study": study_id,
                "model": MODELS[model],
                "benchmark": case["benchmark"],
                "underlying_task": case["underlying_task_id"],
                "case": case["case_id"],
                "condition": condition,
                "regime": regime,
            }
            row = copy.deepcopy(case)
            row.update(
                {
                    "schema_version": SCHEMA_VERSION,
                    "study_id": study_id,
                    "study": study,
                    "model_key": model,
                    "model_id": MODELS[model],
                    "provider_id": "deepseek",
                    "model_group": f"deepseek_{model}",
                    "expected_returned_model_version": SERVICE_VERSIONS[model],
                    "model_role": "primary"
                    if model == "pro"
                    else "same_provider_replication",
                    "run_id": run_id,
                    "execution_identity": execution_identity,
                    "work_key": sha256_canonical_json(identity),
                    "condition_id": condition,
                    "authorization_regime": regime,
                    "prompt_factor": "normal",
                    "module_factor": (
                        "policy"
                        if condition == "m3_policy_only"
                        else "full"
                        if condition == "m3_full_normal_prompt"
                        else None
                    ),
                    "max_provider_calls": 16
                    if condition == "strongest_peer_reviewed_structural_baseline"
                    else 8,
                    "temperature": 0,
                    "max_tokens": 512,
                    "timeout_seconds": 180,
                    "automatic_retries": 0,
                    "provider_tools_enabled": False,
                    "external_effects_enabled": False,
                    "runtime_revision": "corrected_v2",
                    "runtime_version": "corrected_v2",
                    "compiler_revision": "corrected_v2",
                    "effective_compiler_id": (
                        "compile_generic_task_policy_corrected_v2"
                        if case["benchmark"] == "agentdojo-v1"
                        else "compile_task_policy_corrected_v1"
                    ),
                    "sequence": len(result) + 1,
                    "task_order_position": task_rank + 1,
                    "condition_order_position": position + 1,
                    "formal_prefix": task_rank < len(prefix),
                    "status": "pending",
                    "attempt": 1,
                }
            )
            result.append(row)
    return result


def write_plans(
    output_root: Path,
    *,
    cases: Mapping[str, Sequence[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """写四个隔离case/plan和一个清单；同内容复用，任何冲突均不覆盖。

    可传入已经生成的队列，避免同一调度进程为写盘再次读取历史结果。
    此函数不创建ledger、审计包或实验结果，也不打开provider客户端。
    """
    output_root = Path(output_root)
    cohorts = build_cases() if cases is None else cases
    expected_keys = {"utility_pro", "utility_flash", "activity_pro", "activity_flash"}
    if set(cohorts) != expected_keys:
        raise ReinforcementPlanError("four isolated cohort names required")
    files: dict[Path, str] = {}
    manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "selection_seed": SELECTION_SEED,
        "frozen_date": "2026-10-12",
        "planned_records": 0,
        "max_provider_calls": 0,
        "plans": {},
        "utility_prior_outcomes_accessed": False,
        "activity_selection_outcomes": "historical Public primary no_defense/configured VIGIL only",
        "e3_e6_outcomes_accessed": False,
        "independent_blind_set_used": False,
        "m3_workflow_types": 4,
        "m3_language_and_authorization_profile_coupled": True,
        "confirmation_policy": "ASK without real approval is not task completion",
        "provider_tools_enabled": False,
        "external_effects_enabled": False,
    }
    for key in sorted(cohorts):
        study, model = key.split("_")
        rows = build_plan(cohorts[key], study, model)
        case_path = Path(study) / model / "cases_v1.jsonl"
        plan_path = Path(study) / model / "plan_v1.jsonl"
        for path, values in ((case_path, cohorts[key]), (plan_path, rows)):
            files[path] = "".join(
                json.dumps(
                    row, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                )
                + "\n"
                for row in values
            )
        calls = sum(row["max_provider_calls"] for row in rows)
        manifest["plans"][key] = {
            "cases_path": case_path.as_posix(),
            "plan_path": plan_path.as_posix(),
            "case_count": len(cohorts[key]),
            "planned_records": len(rows),
            "max_provider_calls": calls,
            "formal_prefix_records": sum(row["formal_prefix"] for row in rows),
            "model_id": MODELS[model],
            "confirmation_tasks": sum(
                row.get("requires_confirmation", False) for row in cohorts[key]
            ),
        }
        manifest["planned_records"] += len(rows)
        manifest["max_provider_calls"] += calls
    files[Path("manifest_v1.json")] = (
        json.dumps(
            manifest,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n"
    )
    # 先检查所有目标，再创建任何文件；不发生“先覆盖一半才发现冲突”。
    for relative, content in files.items():
        path = output_root / relative
        if path.exists() and path.read_bytes() != content.encode("utf-8"):
            raise ReinforcementPlanError(f"frozen output conflict: {path}")
    for relative, content in files.items():
        path = output_root / relative
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content.encode("utf-8"))
    return manifest
