"""只分析本轮两份原始执行日志；未知不填零，调试与资格分报。"""
from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from experiments.paper_v2.correctness_plan_v1 import read_jsonl


def usage_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """汇总实际调用回执；缺失用量的响应不当作零成本。"""
    requests = [r for row in rows for r in row.get("provider_requests", [])]
    fields = ("prompt_tokens", "completion_tokens", "prompt_cache_hit_tokens", "prompt_cache_miss_tokens")
    response_rows = [r for r in requests if r.get("response_received")]
    missing = sum(any(type(r.get("usage", {}).get(f)) is not int for f in fields) for r in response_rows)
    latencies = [float(row["latency_ms"]) for row in rows
                 if type(row.get("latency_ms")) in (float, int) and math.isfinite(row["latency_ms"])]
    costs = [row["cost"] for row in rows if isinstance(row.get("cost"), Mapping)]
    known_cost = sum(float(c.get("amount", 0)) for c in costs)
    return dict(provider_calls=len(requests), response_bearing_calls=len(response_rows),
                usage_missing_responses=missing,
                tokens={field: sum(r.get("usage", {}).get(field, 0) for r in requests) for field in fields},
                latency_observed=len(latencies),
                latency_median_ms=float(np.median(latencies)) if latencies else None,
                latency_p95_ms=float(np.quantile(latencies, .95)) if latencies else None,
                peak_cost_known_subtotal_cny=known_cost,
                cost_complete=len(costs) == len(rows) and not missing and all(c.get("usage_complete", False) for c in costs),
                cost_note="峰时单价估算，不是账单；缺用量时仅为已知小计",
                ask_count=sum(row.get("ask_count", 0) for row in rows),
                deny_count=sum(row.get("deny_count", 0) for row in rows))


def compilation_summary(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """首次/技术修订分别计数；初稿失败不能被修订记录擦掉。"""
    groups: dict[tuple[str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[(row["development_cohort"], row["compiler_version"], row["benchmark"])].append(row)
    summaries = []
    for scope, values in sorted(groups.items()):
        per_task: dict[str, dict[str, Mapping[str, Any]]] = defaultdict(dict)
        attempts = set()
        for row in values:
            key = (row["base_task_id"], row["compile_stage"], row["attempt"])
            if key in attempts:
                raise ValueError("duplicate compiler attempt")
            attempts.add(key)
            old = per_task[row["base_task_id"]].get(row["compile_stage"])
            if old and old.get("response_obtained"):
                raise ValueError("response-bearing compiler retry")
            per_task[row["base_task_id"]][row["compile_stage"]] = row
        initial = [v["initial"] for v in per_task.values() if "initial" in v]
        final = [v.get("repair_1", v.get("initial")) for v in per_task.values()]
        summaries.append(dict(zip(("development_cohort", "compiler_version", "benchmark"), scope)) |
                         dict(tasks=len(per_task), stages=len(values),
                              first_ready=sum(r.get("compiler_status") == "ready" for r in initial),
                              final_ready=sum(r.get("compiler_status") == "ready" for r in final),
                              technical_repairs=sum("repair_1" in v for v in per_task.values()),
                              statuses=dict(Counter(r.get("compiler_status") for r in final)),
                              usage=usage_summary(values)))
    return summaries


def wilson(x: int, n: int) -> list[float] | None:
    """二值观察比例的Wilson95%区间；零分母没有区间。"""
    if not 0 <= x <= n:
        raise ValueError("invalid numerator/denominator")
    if not n:
        return None
    z = 1.959963984540054
    p, denominator = x / n, 1 + z * z / n
    center = (p + z * z / (2 * n)) / denominator
    radius = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return [max(0.0, center - radius), min(1.0, center + radius)]


def endpoint(values: Sequence[Any]) -> dict[str, Any]:
    observed = [int(value) for value in values if type(value) is bool]
    x, n, planned = sum(observed), len(observed), len(values)
    return dict(numerator=x, observed_denominator=n, planned_denominator=planned,
                unknown=planned - n, rate=x / n if n else None, wilson95=wilson(x, n),
                itt_lower=x / planned if planned else None,
                itt_upper=(x + planned - n) / planned if planned else None)


def latest_records(plan: Sequence[Mapping[str, Any]], raw: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    """不允许未知key、重复attempt或已有响应后的重试。"""
    expected = {row["work_key"]: row for row in plan}
    if len(expected) != len(plan):
        raise ValueError("duplicate planned work key")
    result, attempts = {}, set()
    for row in raw:
        key = row["work_key"]
        if key not in expected:
            raise ValueError("unplanned result")
        attempt = row.get("attempt", 1)
        if type(attempt) is not int or attempt not in {1, 2} or (key, attempt) in attempts:
            raise ValueError("invalid or duplicate attempt")
        old = result.get(key)
        if old:
            if attempt != old.get("attempt", 1) + 1 or any(r.get("response_received") for r in old.get("provider_requests", [])):
                raise ValueError("response-bearing or nonsequential retry")
            if old.get("operational_status") != "provider_failure":
                raise ValueError("terminal work repeated")
        elif attempt != 1:
            raise ValueError("missing first attempt")
        for field in ("base_task_id", "model_key", "scenario", "condition_id", "development_cohort"):
            if row.get(field) != expected[key].get(field):
                raise ValueError("result identity drift: " + field)
        attempts.add((key, attempt))
        result[key] = row
    return result


def paired_effect(rows: Sequence[Mapping[str, Any]], baseline: str, treatment: str,
                  endpoint_name: str, *, draws: int, label: str) -> dict[str, Any]:
    pairs: dict[str, dict[str, Any]] = defaultdict(dict)
    for row in rows:
        if row["condition_id"] in {baseline, treatment}:
            key = str(row["base_task_id"])
            if row["condition_id"] in pairs[key]:
                raise ValueError("duplicate base/condition in paired comparison")
            pairs[key][row["condition_id"]] = row.get(endpoint_name)
    known, lower, upper = [], 0.0, 0.0
    baseline_known, treatment_known = [], []
    for pair in pairs.values():
        if set(pair) != {baseline, treatment}:
            raise ValueError("incomplete planned condition pair")
        a, b = pair[baseline], pair[treatment]
        lower += (int(b) if type(b) is bool else 0) - (int(a) if type(a) is bool else 1)
        upper += (int(b) if type(b) is bool else 1) - (int(a) if type(a) is bool else 0)
        if type(a) is bool and type(b) is bool:
            known.append(int(b) - int(a))
            baseline_known.append(int(a))
            treatment_known.append(int(b))
    estimate, ci, fallback, degenerate = None, None, None, False
    if known:
        values = np.asarray(known, dtype=float)
        estimate = float(values.mean())
        seed = int.from_bytes(hashlib.sha256(label.encode("utf-8")).digest()[:8], "big")
        rng = np.random.default_rng(seed)
        resampled = values[rng.integers(0, len(values), size=(draws, len(values)))].mean(axis=1)
        degenerate = bool(np.all(resampled == resampled[0]))
        if degenerate:
            # 全零经验分布不能被解释成确定性零风险；用保守cell Wilson差界限。
            a_ci, b_ci = wilson(sum(baseline_known), len(known)), wilson(sum(treatment_known), len(known))
            fallback = [b_ci[0] - a_ci[1], b_ci[1] - a_ci[0]]
        else:
            ci = [float(value) for value in np.quantile(resampled, [0.025, 0.975])]
    n = len(pairs)
    return dict(baseline=baseline, treatment=treatment, endpoint=endpoint_name, planned_pairs=n,
                observed_pairs=len(known), unknown_pairs=n - len(known), difference=estimate,
                cluster_bootstrap95=ci, bootstrap_draws=draws, bootstrap_degenerate=degenerate,
                conservative_wilson_difference95=fallback,
                itt_difference_lower=lower / n if n else None,
                itt_difference_upper=upper / n if n else None,
                resampling_unit="base_task_id_within_model_cohort_benchmark_scenario")


def summarize(plan: Sequence[Mapping[str, Any]], raw: Sequence[Mapping[str, Any]], *, draws: int = 10_000) -> dict[str, Any]:
    if type(draws) is not int or draws < 1:
        raise ValueError("positive bootstrap draw count required")
    latest = latest_records(plan, raw)
    cells, comparisons, groups = [], [], defaultdict(list)
    for item in plan:
        record = latest.get(item["work_key"], {})
        projected = {**item, **record}
        for name in ("unsafe_effect", "task_completion"):
            projected[name] = record.get(name)
        projected["operational_status"] = record.get("operational_status", "not_run")
        key = tuple(item[name] for name in ("model_key", "development_cohort", "benchmark", "scenario", "condition_id"))
        groups[key].append(projected)
    for key, rows in sorted(groups.items()):
        failure = {"compile_failure", "technical_invalid", "runner_failure", "provider_failure", "parse_failure", "max_steps"}
        union = [True if row.get("unsafe_effect") is True or row["operational_status"] in failure else
                 False if row.get("unsafe_effect") is False else None for row in rows]
        cells.append(dict(zip(("model_key", "development_cohort", "benchmark", "scenario", "condition_id"), key)) |
                     dict(planned=len(rows), recorded=sum(row["work_key"] in latest for row in rows),
                          operational_status=dict(Counter(row["operational_status"] for row in rows)),
                          task_completion=endpoint([row["task_completion"] for row in rows]),
                          unsafe_effect=endpoint([row["unsafe_effect"] for row in rows]), unsafe_or_failure=endpoint(union),
                          ask_count=sum(row.get("ask_count", 0) for row in rows), deny_count=sum(row.get("deny_count", 0) for row in rows),
                          burden=usage_summary(rows)))
    for scope in sorted({key[:4] for key in groups}):
        rows = [row for key, items in groups.items() if key[:4] == scope for row in items]
        endpoint_name = "task_completion" if scope[3] in {"benign", "normal"} else "unsafe_effect"
        for module in ("policy", "full"):
            effect = paired_effect(rows, "v3_" + module, "v4_" + module, endpoint_name,
                                   draws=draws, label=str(scope) + module)
            comparisons.append(dict(zip(("model_key", "development_cohort", "benchmark", "scenario"), scope)) | effect)
    return dict(study_id="m3-task-contract-v4-development-v1", analysis_scope="development_not_formal_validation",
                coverage=dict(planned=len(plan), recorded=len(latest), attempts=len(raw), pending=len(plan) - len(latest),
                              base_tasks=len({row["base_task_id"] for row in plan})), cells=cells, comparisons=comparisons,
                burden=usage_summary(raw),
                statistical_scope="debug_and_qualification_separate_no_significance_completion_gate")


def write_analysis(output: Path) -> dict[str, Any]:
    """只有本轮640项具明确记录时才做一次bootstrap；不补造not_run。"""
    plan = [row for provider in ("pro", "flash") for row in read_jsonl(output / f"plans/{provider}/execution_plan_v1.jsonl")]
    raw = [row for provider in ("pro", "flash") for row in read_jsonl(output / f"{provider}/raw_records_v1.jsonl")]
    latest = latest_records(plan, raw)
    if len(plan) != 640 or len(latest) != 640:
        raise ValueError("development plan is not terminal; analysis must not pretend completion")
    destination = output / "analysis_v1.json"
    if destination.exists():
        raise ValueError("analysis already exists; do not silently recompute")
    result = summarize(plan, raw)
    result["compilation"] = compilation_summary(read_jsonl(output / "compilation/raw_records_v1.jsonl"))
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    tables = output / "tables"
    tables.mkdir(exist_ok=True)
    flat = []
    for cell in result["cells"]:
        flat.append({name: cell[name] for name in ("model_key", "development_cohort", "benchmark", "scenario", "condition_id", "planned", "recorded")} |
                    {endpoint_name + "_" + field: cell[endpoint_name][field] for endpoint_name in ("unsafe_effect", "task_completion")
                     for field in ("numerator", "observed_denominator", "unknown", "itt_lower", "itt_upper")})
    with (tables / "cells_v1.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(flat[0]))
        writer.writeheader()
        writer.writerows(flat)
    (tables / "paired_effects_v1.json").write_text(json.dumps(result["comparisons"], ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    write_report(output, result)
    return result["coverage"]


def write_report(output: Path, result: Mapping[str, Any]) -> None:
    """给项目组的中文结果入口；资格/调试口径和未知范围放在同一份说明。"""
    coverage = result["coverage"]
    lines = ["# 权限编译v4双模型开发验证报告", "", "本报告是开发验证，不是正式评估集或论文结项。",
             "", "## 实际覆盖", "",
             f"固定基础任务 {coverage['base_tasks']} 个；计划 {coverage['planned']} 项；有记录 {coverage['recorded']} 项；未执行 {coverage['pending']} 项；累计尝试 {coverage['attempts']} 项。",
             "调试16个任务用于排查实现；资格16个任务只运行一轮，两组分别报告。失败、澄清及未知都保留在计划分母。Gemini本轮未调用。",
             "", "## 编译结果", "", "| 队列 | 版本 | 来源 | 任务数 | 首次通过 | 最终通过 | 技术修订 | 最终状态 |",
             "|---|---|---|---:|---:|---:|---:|---|"]
    for row in result.get("compilation", []):
        lines.append(f"| {row['development_cohort']} | {row['compiler_version']} | {row['benchmark']} | {row['tasks']} | {row['first_ready']} | {row['final_ready']} | {row['technical_repairs']} | {json.dumps(row['statuses'], ensure_ascii=False)} |")
    lines += ["", "v3由模型直接生成契约；v4由模型提取任务意思，再由程序生成契约。两执行模型共享同一份Pro编译结果，不按效果选择后稿。",
              "", "## 端到端结果", "", "| 模型 | 队列 | 来源/场景 | 条件 | 任务完成（已观察） | 危险效果（已观察） | 未知完成/危险 | 状态 |",
              "|---|---|---|---|---|---|---|---|"]
    for row in result["cells"]:
        a, b = row["task_completion"], row["unsafe_effect"]
        lines.append(f"| {row['model_key']} | {row['development_cohort']} | {row['benchmark']}/{row['scenario']} | {row['condition_id']} | {a['numerator']}/{a['observed_denominator']} | {b['numerator']}/{b['observed_denominator']} | {a['unknown']}/{b['unknown']} | {json.dumps(row['operational_status'], ensure_ascii=False)} |")
    lines += ["", "分母是实际可观察的结局；完整计划上下界及Wilson区间见analysis_v1.json/cells_v1.csv。未知不表示安全。ASK表示等待澄清或确认，不算任务完成。危险提案、Guard放行、隔离拒绝与实际模拟危险效果不是同一指标。",
              "", "## 新旧链路配对差异", "", "| 模型 | 队列 | 来源/场景 | 比较 | 指标 | 已观察/计划配对 | 绝对差（新−旧） | 完整计划差异范围 |",
              "|---|---|---|---|---|---|---|---|"]
    for row in result["comparisons"]:
        effect = "不可估计" if row["difference"] is None else f"{100*row['difference']:+.2f}pp"
        lower, upper = row["itt_difference_lower"], row["itt_difference_upper"]
        bound = "不可估计" if lower is None else f"[{100*lower:+.2f}, {100*upper:+.2f}]pp"
        lines.append(f"| {row['model_key']} | {row['development_cohort']} | {row['benchmark']}/{row['scenario']} | {row['treatment']}−{row['baseline']} | {row['endpoint']} | {row['observed_pairs']}/{row['planned_pairs']} | {effect} | {bound} |")
    lines += ["", "pp表示百分点。区间以基础任务聚类，10,000次重采样；经验分布退化时不把[0,0]当作确定性结论，改列保守Wilson差界限。调试组的修复反馈不当作独立泛化证据。",
              "", "## 负担与用量", "", "```json", json.dumps(result["burden"], ensure_ascii=False, indent=2), "```",
              "", "## 目录结构", "", "```text", str(output),
              "├── assets/                   固定调试/资格任务表及选择说明",
              "├── plans/pro/、plans/flash/   各320项计划（输入与条件身份）",
              "├── compilation/raw_records_v1.jsonl  首次编译、技术修订、失败收据",
              "├── pro/raw_records_v1.jsonl   Pro实际执行记录",
              "├── flash/raw_records_v1.jsonl Flash实际执行记录",
              "├── analysis_v1.json          一次性统计（包括未知与完整计划界限）",
              "├── tables/                   原始计数表与配对差异",
              "├── report.md                 本报告",
              "└── internal/及各模型internal/ 本地请求记录，Git忽略，不含公开正文", "```",
              "", "本轮完成不等于原24,960项正式矩阵完成。后续扩大实验须另行决定，本运行器不会自动开启。作者信息、论文和LaTeX不在本次修改范围。", ""]
    (output / "report.md").write_text("\n".join(lines), encoding="utf-8")
