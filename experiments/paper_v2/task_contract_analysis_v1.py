"""只分析任务契约v3研究；重复按任务聚类，未观察结果不填安全零。"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from experiments.paper_v2.e6_cross_provider_calibration_analysis_v1 import _newcombe_paired
from experiments.paper_v2.empirical_reinforcement_analysis_v1 import endpoint_summary
from m3_eval.statistics import holm_adjust, mcnemar_exact

OUTPUT = Path(__file__).resolve().parents[2] / "outputs/experiments/task_contract_compiler_v3_validation_v1"
SEED = "m3-task-contract-v3-analysis-20261013"
MAIN_CONDITIONS = ("no_defense", "old_policy", "old_full", "new_policy", "new_full")


def _base(row: Mapping[str, Any]) -> str:
    """公开索引采用统一基础任务键，不按条件或重复生成新任务。"""
    value = row.get("base_task_id", row.get("underlying_task_id"))
    if not isinstance(value, str) or not value:
        raise ValueError("base task identity missing")
    return value


def _cell_key(row: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return tuple(str(row[key]) for key in ("model_key", "benchmark", "scenario", "condition_id"))


def _validate(plan: Sequence[Mapping[str, Any]], raw: Sequence[Mapping[str, Any]]):
    """恢复只能跟在无响应尝试之后；收据及安全异常不能被统计吞掉。"""
    expected = {row["work_key"]: row for row in plan}
    if len(expected) != len(plan):
        raise ValueError("duplicate planned work key")
    latest: dict[str, Mapping[str, Any]] = {}
    calls: Counter[str] = Counter()
    local_ids: set[str] = set()
    response_ids: set[tuple[str, str]] = set()
    identity = ("base_task_id", "cluster_id", "benchmark", "scenario", "model_key", "model_id", "condition_id", "replicate_index")
    for row in raw:
        key = row.get("work_key")
        if key not in expected or any(row.get(field) != expected[key].get(field) for field in identity):
            raise ValueError("record identity differs from planned work item")
        for field in ("task_completion", "unsafe_effect"):
            if row.get(field) is not None and type(row[field]) is not bool:
                raise ValueError("endpoint must be boolean or unknown")
        if (row.get("provider_tools_enabled") is not False
                or row.get("real_external_effects") != 0
                or row.get("evaluator_fields_online") != 0):
            raise ValueError("safety receipt missing or violation present")
        attempt = row.get("attempt")
        if type(attempt) is not int or attempt not in (0, 1, 2):
            raise ValueError("invalid explicit attempt")
        previous = latest.get(key)
        if previous is None:
            if attempt not in (0, 1):
                raise ValueError("first attempt must be one or explicit not_run zero")
        elif previous.get("response_obtained"):
            raise ValueError("response-bearing work item repeated")
        elif attempt != previous["attempt"] + 1:
            raise ValueError("recovery attempt repeated or skipped")
        requests = row.get("provider_requests", [])
        if row.get("provider_call_count") != len(requests):
            raise ValueError("provider call count differs from receipts")
        calls[key] += len(requests)
        if calls[key] > expected[key].get("max_provider_calls", 12):
            raise ValueError("cumulative work-item call budget exceeded")
        for request in requests:
            local = request.get("local_request_id")
            if not local or local in local_ids or not request.get("payload_sha256"):
                raise ValueError("request ID or payload digest missing or duplicated")
            local_ids.add(local)
            if request.get("response_received"):
                response = request.get("provider_response_id")
                if not response or request.get("returned_model") != expected[key]["model_id"]:
                    raise ValueError("official response or exact model identity missing/drifted")
                response_key = (str(row.get("provider_id", row["model_key"])), str(response))
                if response_key in response_ids:
                    raise ValueError("official response ID duplicated")
                response_ids.add(response_key)
        latest[key] = row
    return latest


def _contrast(rows, baseline, treatment, endpoint, draws, label):
    """先按任务/重复配对，再整组重采样；不覆盖同任务第二次执行。"""
    blocks: dict[tuple[str, int], dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for row in rows:
        condition = row["condition_id"]
        if condition not in (baseline, treatment):
            continue
        key = (_base(row), int(row["replicate_index"]))
        if condition in blocks[key]:
            raise ValueError("duplicate task/condition/replicate")
        blocks[key][condition] = row
    if any(baseline not in block or treatment not in block for block in blocks.values()):
        raise ValueError("plan must have complete paired work items")
    known = []
    lower = upper = 0.0
    per_repeat: dict[int, list[tuple[bool, bool]]] = defaultdict(list)
    for (task, repeat), block in blocks.items():
        left, right = block[baseline], block[treatment]
        a, b = left.get(endpoint), right.get(endpoint)
        lower += (int(b) if b is not None else 0) - (int(a) if a is not None else 1)
        upper += (int(b) if b is not None else 1) - (int(a) if a is not None else 0)
        if type(a) is bool and type(b) is bool:
            cluster = str(left.get("cluster_id", task))
            if cluster != str(right.get("cluster_id", task)):
                raise ValueError("paired cluster identity differs")
            stratum = str(left.get("suite", left.get("family", "unspecified")))
            known.append((cluster, stratum, int(b) - int(a)))
            per_repeat[repeat].append((a, b))
    repetitions = []
    for repeat, values in sorted(per_repeat.items()):
        a, b = zip(*values)
        repetitions.append({"replicate_index": repeat, "known_pairs": len(values),
                            "paired_interval": _newcombe_paired(a, b),
                            "mcnemar": mcnemar_exact(a, b)})
    bootstrap = {"method": "benchmark_stratified_task_cluster_bootstrap", "draws": draws,
                 "clusters": len({row[0] for row in known}), "ci_low": None,
                 "ci_high": None, "degenerate": False}
    # 每任务先汇总预定重复；缺失一个重复不能让另一任务得到双倍权重。
    task_values = defaultdict(list)
    task_groups = {}
    for (task, _), block in blocks.items():
        a, b = block[baseline].get(endpoint), block[treatment].get(endpoint)
        if type(a) is bool and type(b) is bool:
            task_values[task].append(int(b) - int(a))
            left = block[baseline]
            group = (str(left.get("cluster_id", task)),
                     str(left.get("suite", left.get("family", "unspecified"))))
            if task in task_groups and task_groups[task] != group:
                raise ValueError("task cluster or stratum changes across replicates")
            task_groups[task] = group
    task_means = [(task_groups[task][0], task_groups[task][1], float(np.mean(values)))
                  for task, values in task_values.items()]
    estimate = float(np.mean([row[2] for row in task_means])) if task_means else None
    p_value = None
    if known:
        cluster_rows: dict[tuple[str, str], list[float]] = defaultdict(list)
        cluster_strata: dict[str, str] = {}
        for cluster, stratum, difference in task_means:
            if cluster in cluster_strata and cluster_strata[cluster] != stratum:
                raise ValueError("one cluster spans incompatible sampling strata")
            cluster_strata[cluster] = stratum
            cluster_rows[(stratum, cluster)].append(difference)
        seed = int.from_bytes(hashlib.sha256(f"{SEED}:{label}".encode()).digest()[:8], "big")
        rng = np.random.default_rng(seed)
        numerator, denominator = np.zeros(draws), np.zeros(draws)
        strata = defaultdict(list)
        for (stratum, _), values in sorted(cluster_rows.items()):
            strata[stratum].append((sum(values), len(values)))
        for stratum in sorted(strata):
            values = np.asarray(strata[stratum], dtype=float)
            indices = rng.integers(0, len(values), size=(draws, len(values)))
            numerator += values[indices, 0].sum(axis=1)
            denominator += values[indices, 1].sum(axis=1)
        low, high = map(float, np.quantile(numerator / denominator, [.025, .975]))
        degenerate = low == high
        bootstrap.update({"seed_label": SEED, "seed": seed, "degenerate": degenerate,
                          "ci_low": None if degenerate else low, "ci_high": None if degenerate else high,
                          "fallback": "per_replicate_paired_intervals_not_zero_certainty" if degenerate else None})
        # 同一任务族的全部重复一起交换条件，不把两次执行当独立随机符号。
        sums = np.asarray([sum(values) for values in cluster_rows.values()], dtype=float)
        signs = rng.choice((-1.0, 1.0), size=(draws, len(sums)))
        observed = abs(float(sums.sum()))
        p_value = (1 + int(np.count_nonzero(np.abs(signs @ sums) >= observed - 1e-12))) / (draws + 1)
    n = len(blocks)
    return {"baseline": baseline, "treatment": treatment, "endpoint": endpoint,
            "planned_execution_pairs": n, "base_tasks": len({key[0] for key in blocks}),
            "known_execution_pairs": len(known), "unknown_execution_pairs": n - len(known),
            "known_base_tasks": len(task_means), "repeat_aggregation": "within_task_mean_then_cluster",
            "estimate": estimate, "itt_difference_lower": lower / n if n else None,
            "itt_difference_upper": upper / n if n else None, "bootstrap": bootstrap,
            "per_replicate": repetitions, "p_value": p_value, "holm_p": None}


def summarize(plan: Sequence[Mapping[str, Any]], raw: Sequence[Mapping[str, Any]], *, bootstrap_draws=10_000):
    """纯函数：只读已传入的本研究计划/记录，不访问历史或内部正文。"""
    if type(bootstrap_draws) is not int or bootstrap_draws < 1:
        raise ValueError("bootstrap draws must be positive")
    latest = _validate(plan, raw)
    cells, groups = [], defaultdict(list)
    projected = [{**row, **{field: latest.get(row["work_key"], {}).get(field)
                 for field in ("task_completion", "unsafe_effect")}} for row in plan]
    for row in projected:
        groups[_cell_key(row)].append(row)
    for key, rows in sorted(groups.items()):
        observed = [latest[row["work_key"]] for row in rows if row["work_key"] in latest]
        cells.append({"model_key": key[0], "benchmark": key[1], "scenario": key[2], "condition_id": key[3],
                      "planned_records": len(rows), "recorded": len(observed),
                      "base_tasks": len({_base(row) for row in rows}),
                      "clusters": len({row.get("cluster_id", _base(row)) for row in rows}),
                      "operational_status": dict(Counter(row["operational_status"] for row in observed)),
                      "task_completion": endpoint_summary(observed, "task_completion", planned=len(rows)),
                      "unsafe_effect": endpoint_summary(observed, "unsafe_effect", planned=len(rows)),
                      "wilson_scope": "observed_execution_descriptive_only_replicates_not_independent"})
    comparisons = []
    scopes = sorted({key[:3] for key in groups})
    for model, benchmark, scenario in scopes:
        subset = [row for row in projected if _cell_key(row)[:3] == (model, benchmark, scenario)]
        conditions = {row["condition_id"] for row in subset}
        endpoint = "task_completion" if scenario in {"normal", "benign"} else "unsafe_effect"
        for baseline, treatment in (("old_policy", "new_policy"), ("old_full", "new_full")):
            if {baseline, treatment} <= conditions:
                result = _contrast(subset, baseline, treatment, endpoint, bootstrap_draws,
                                   f"{model}:{benchmark}:{scenario}:{baseline}:{treatment}")
                comparisons.append({"model_key": model, "benchmark": benchmark, "scenario": scenario, **result})
    family = [row for row in comparisons if row["model_key"] == "pro"]
    if family:
        adjusted = holm_adjust([row["p_value"] if row["p_value"] is not None else 1.0 for row in family])
        for row, value in zip(family, adjusted):
            row["holm_p"] = value if row["p_value"] is not None else None
    providers = {}
    for model in sorted({row["model_key"] for row in plan}):
        expected = [row for row in plan if row["model_key"] == model]
        observed = [latest[row["work_key"]] for row in expected if row["work_key"] in latest]
        paired_blocks = defaultdict(set)
        for row in observed:
            if row.get("response_obtained") and row["condition_id"] in MAIN_CONDITIONS:
                paired_blocks[(_base(row), row["scenario"], row["replicate_index"])].add(row["condition_id"])
        complete = sum(set(MAIN_CONDITIONS) <= conditions for conditions in paired_blocks.values())
        pending = len(expected) - len(observed)
        status = "not_started" if not observed else ("partial_diagnostic" if pending else "terminal_plan")
        planned_blocks = {(_base(row), row["scenario"], row["replicate_index"]) for row in expected
                          if row["condition_id"] in MAIN_CONDITIONS}
        providers[model] = {"planned": len(expected), "recorded": len(observed), "pending": pending,
                            "status": status, "complete_five_condition_blocks": complete,
                            "planned_five_condition_blocks": len(planned_blocks),
                            "complete_response_pairing": bool(planned_blocks) and complete == len(planned_blocks),
                            "response_bearing": sum(bool(row.get("response_obtained")) for row in observed),
                            "inference": "provider_within_effects_only_no_raw_model_ranking"}
    cost_values = [row.get("cost_estimate_cny") for row in raw]
    return {"study_id": "m3-task-contract-v3-validation-v1", "cells": cells, "comparisons": comparisons,
            "providers": providers,
            "coverage": {"planned": len(plan), "terminal_records": len(latest), "attempts": len(raw),
                         "pending": len(plan) - len(latest), "base_tasks": len({_base(row) for row in plan})},
            "burden": {"provider_calls": sum(row["provider_call_count"] for row in raw),
                       "cost_estimate_cny": sum(float(value) for value in cost_values if value is not None),
                       "unpriced_attempts": sum(value is None for value in cost_values),
                       "basis": "recorded_estimate_not_provider_invoice"},
            "limitations": ["任务重复、攻击版本和模型不是新增独立任务",
                            "部分Gemini只保留观察与全计划缺失边界，不代表完整跨厂商复现",
                            "描述性Wilson不能代替重复测量聚类区间，零事件退化不作确定性结论"]}


def _read(path: Path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def summarize_ablations(main_plan, main_raw, ablation_plan, ablation_raw, *, bootstrap_draws=10_000):
    """复用预选任务主矩阵new_full，不为消融另跑完整版本。"""
    main_latest = _validate(main_plan, main_raw)
    latest = _validate(ablation_plan, ablation_raw)
    projected = [{**row, **{field: latest.get(row["work_key"], {}).get(field)
                 for field in ("task_completion", "unsafe_effect")}} for row in ablation_plan]
    baselines = [{**row, **{field: main_latest.get(row["work_key"], {}).get(field)
                 for field in ("task_completion", "unsafe_effect")}} for row in main_plan
                 if row["model_key"] == "pro" and row["condition_id"] == "new_full"]
    comparisons = []
    for condition, scenario in sorted({(row["condition_id"], row["scenario"]) for row in projected}):
        selected = [row for row in projected if row["condition_id"] == condition and row["scenario"] == scenario]
        identities = {(_base(row), row["replicate_index"]) for row in selected}
        baseline = [row for row in baselines if row["scenario"] == scenario
                    and (_base(row), row["replicate_index"]) in identities]
        endpoint = "task_completion" if scenario in {"benign", "normal"} else "unsafe_effect"
        comparisons.append({"condition_id": condition, "scenario": scenario,
            **_contrast(baseline + selected, "new_full", condition, endpoint,
                        bootstrap_draws, f"ablation:{condition}:{scenario}"),
            "inference": "prespecified_conservative_ablation_no_new_significance_family"})
    return {"planned": len(ablation_plan), "recorded": len(latest), "pending": len(ablation_plan) - len(latest),
            "base_tasks": len({_base(row) for row in ablation_plan}), "comparisons": comparisons,
            "full_version_source": "reused_main_matrix_new_full"}


def compilation_summary(rows):
    """三稿只报告固定首稿和表示稳定性，不能按后两稿择优。"""
    groups = defaultdict(dict)
    for row in rows:
        task, index = row["base_task_id"], row["draft_index"]
        if type(index) is not int or index not in (1, 2, 3) or index in groups[task]:
            raise ValueError("duplicate or invalid compiler draft identity")
        groups[task][index] = row
    stability = []
    for task, drafts in sorted(groups.items()):
        first = drafts.get(1)
        if first is None:
            raise ValueError("compiler records missing fixed first draft")
        if len({row.get("compiler_input_sha256") for row in drafts.values()}) != 1:
            raise ValueError("compiler inputs changed between stability drafts")
        # 去引文/offset，保留动作顺序及标识；这是表示一致性，不是完整语义等价证明。
        representations = []
        for row in drafts.values():
            value = row.get("draft")
            if isinstance(value, dict):
                value = {**value, "actions": [{k: v for k, v in action.items() if k != "evidence"}
                                               for action in value.get("actions", [])],
                         "prohibitions": [{k: v for k, v in action.items() if k != "evidence"}
                                          for action in value.get("prohibitions", [])]}
                representations.append(json.dumps(value, ensure_ascii=False, sort_keys=True))
        stability.append({"base_task_id": task, "drafts_recorded": len(drafts),
                          "first_compile_status": first["compile_status"],
                          "all_three_available": set(drafts) == {1, 2, 3},
                          "exact_representation_agreement": len(representations) == 3 and len(set(representations)) == 1,
                          "successful_drafts": sum(row.get("compile_status") == "compiled" for row in drafts.values())})
    return {"recorded_drafts": len(rows), "base_tasks": len(groups),
            "first_statuses": dict(Counter(row[1]["compile_status"] for row in groups.values())),
            "selection_policy": "first_draft_fixed_no_best_of_three",
            "stability_scope": "exact_DSL_representation_ignoring_evidence_not_full_semantic_equivalence",
            "tasks": stability}


def write_report(result, root: Path):
    """输出一份自足中文报告，明确计划、观察和未运行状态。"""
    coverage = result["coverage"]
    lines = ["# 复杂任务权限编译v3：实验报告", "", "## 当前完成范围", "",
             f"计划 {coverage['planned']} 条；已记录终态 {coverage['terminal_records']} 条；未执行 {coverage['pending']} 条；"
             f"原始尝试 {coverage['attempts']} 条。基础任务 {coverage['base_tasks']} 个，不能以执行数替代任务数量。", "",
             "|模型|计划|终态|未执行|完整五条件观察块|状态|", "|---|---:|---:|---:|---:|---|"]
    for model, row in result["providers"].items():
        lines.append(f"|{model}|{row['planned']}|{row['recorded']}|{row['pending']}|{row['complete_five_condition_blocks']}|{row['status']}|")
    lines += ["", "## 结果口径", "", "统计JSON保留观察分子/分母、计划分母、未知及ITT上下界；"
              "真实模拟效果、任务完成与程序失败分别报告。没有观察值不等于安全零。", "",
              "主比较是同任务、同重复的新旧链路差异；按任务族聚类。部分提供商的完整配对块只是观察子集，"
              "不能据此补齐剩余未执行任务或推广全部跨厂商结果。", "", "## 目录", "",
              "- `plans/`：本研究三个模型的工作项，不含评分答案。",
              "- `assets/`：在线任务与独立离线评分输入。",
              "- `compilation/`：固定Pro三份草稿的状态摘要；第一份是正式输入。",
              "- `pro/`、`flash/`、`gemini/`：独立原始执行记录与停止原因。",
              "- `ablation/pro/`：仅Pro的保守消融记录。",
              "- `analysis_v1.json`、`tables/`、`figures/`：正式一次性分析及表图。",
              "- `internal/`：仅本地请求/响应正文，Git忽略，不是公开证据。", "",
              "## 证据边界", "", *[f"- {value}" for value in result["limitations"]], ""]
    (root / "report.md").write_text("\n".join(lines), encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--bootstrap-draws", type=int, default=10_000)
    args = parser.parse_args(argv)
    destination = args.output / "analysis_v1.json"
    if destination.exists():
        raise SystemExit("正式分析已存在；不自动重算或覆盖")
    plan = [row for model in ("pro", "flash", "gemini")
            for row in _read(args.output / "plans" / model / "main_plan_v1.jsonl")]
    raw = [row for model in ("pro", "flash", "gemini") for row in _read(args.output / model / "raw_records_v1.jsonl")]
    if not plan:
        raise SystemExit("本研究计划不存在；不从历史计划猜补")
    latest = _validate(plan, raw)
    if any(row["work_key"] not in latest for row in plan if row["model_key"] in ("pro", "flash")):
        raise SystemExit("DeepSeek矩阵仍未闭合；不提前运行正式bootstrap")
    ablation_plan = _read(args.output / "plans/pro/ablation_plan_v1.jsonl")
    ablation_raw = _read(args.output / "ablation/pro/raw_records_v1.jsonl")
    if not ablation_plan:
        raise SystemExit("预定消融计划缺失；不伪称整项研究闭合")
    ablation_latest = _validate(ablation_plan, ablation_raw)
    if any(row["work_key"] not in ablation_latest for row in ablation_plan):
        raise SystemExit("预定消融仍未闭合；不提前运行正式bootstrap")
    result = summarize(plan, raw, bootstrap_draws=args.bootstrap_draws)
    result["ablations"] = summarize_ablations(plan, raw, ablation_plan, ablation_raw,
                                              bootstrap_draws=args.bootstrap_draws)
    result["compilation"] = compilation_summary(_read(args.output / "compilation/raw_records_v1.jsonl"))
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    tables = args.output / "tables"
    tables.mkdir(exist_ok=True)
    with (tables / "coverage.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=("model", "planned", "recorded", "pending", "status", "complete_five_condition_blocks", "planned_five_condition_blocks", "complete_response_pairing", "response_bearing", "inference"))
        writer.writeheader()
        writer.writerows({"model": model, **row} for model, row in result["providers"].items())
    write_report(result, args.output)
    print(json.dumps(result["coverage"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
