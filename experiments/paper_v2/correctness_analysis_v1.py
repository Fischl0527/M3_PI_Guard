"""One-pass descriptive analysis of the corrected development cohort only.

No provider clients, credentials, historical raw records, or bootstrap replay are
used. Unknown endpoints retain null; native AgentDojo security and M3 simulated
effects are always stratified by benchmark.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from experiments.paper_v2.e6_cross_provider_calibration_analysis_v2 import (
    _newcombe_paired,
)
from m3_eval.statistics import percentile, wilson_interval


DEFAULT_ROOT = Path(__file__).resolve().parents[2] / "outputs/experiments/correctness_repair_v1"
MODEL_GROUPS = ("deepseek_pro", "deepseek_flash", "gemini_flash")
CONDITIONS = (
    "no_defense", "safe_prompt_only", "m3_policy_only",
    "m3_policy_safe_prompt", "m3_full_normal_prompt", "m3_full",
)
CONDITION_LABELS = {
    "no_defense": "无防护/普通提示",
    "safe_prompt_only": "无防护/安全提示",
    "m3_policy_only": "规则/普通提示",
    "m3_policy_safe_prompt": "规则/安全提示",
    "m3_full_normal_prompt": "完整模块/普通提示",
    "m3_full": "完整模块/安全提示",
}
COMPARISONS = (
    ("module_normal", "m3_policy_only", "m3_full_normal_prompt"),
    ("module_safe", "m3_policy_safe_prompt", "m3_full"),
    ("prompt_policy", "m3_policy_only", "m3_policy_safe_prompt"),
    ("prompt_full", "m3_full_normal_prompt", "m3_full"),
)
ADMIN_STATUSES = frozenset({
    "not_run", "pending", "quota_stopped", "not_started", "administratively_closed",
    "provider_window_unavailable", "technical_gate_not_extended", "dispatch_stopped",
})
GROUP_FIELDS = ("model_group", "benchmark", "evaluation_case_type", "condition_id")
DETAIL_ENDPOINTS = (
    "unauthorized_proposal", "guard_false_allow", "isolation_rejected",
    "simulated_action_executed", "simulated_unsafe_effect", "native_security_violation",
)
ENDPOINTS = ("unsafe_effect", "task_completion", "unsafe_or_failure", *DETAIL_ENDPOINTS)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def _administrative(row: Mapping[str, Any]) -> bool:
    return str(row.get("operational_status", "not_run")) in ADMIN_STATUSES


def _failure(row: Mapping[str, Any]) -> bool:
    return not _administrative(row) and row.get("operational_status") != "completed"


def _endpoint(row: Mapping[str, Any], endpoint: str) -> bool | None:
    if endpoint == "unsafe_or_failure":
        unsafe = _endpoint(row, "unsafe_effect")
        return True if _failure(row) or unsafe is True else unsafe
    details = row.get("evaluation_details") or {}
    value = row.get(endpoint) if endpoint in {"unsafe_effect", "task_completion"} else details.get(endpoint)
    if value is not None and not isinstance(value, bool):
        raise ValueError(f"{endpoint} must be boolean or null")
    if details.get(f"{endpoint}_observed") is False and value is not None:
        raise ValueError(f"{endpoint}: observed flag conflicts with endpoint")
    return value


def endpoint_summary(values: Sequence[bool | None]) -> dict[str, Any]:
    n_plan = len(values)
    observed = [value for value in values if value is not None]
    x = sum(value is True for value in observed)
    n_observed = len(observed)
    n_unknown = n_plan - n_observed
    low, high = wilson_interval(x, n_observed)
    return {
        "x": x, "n_observed": n_observed, "n_plan": n_plan, "n_unknown": n_unknown,
        "rate_observed": x / n_observed if n_observed else None,
        "wilson_ci_low": low, "wilson_ci_high": high,
        "planned_lower_bound": x / n_plan if n_plan else None,
        "planned_upper_bound": (x + n_unknown) / n_plan if n_plan else None,
    }


def _select_records(
    plan: Sequence[Mapping[str, Any]], records: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, list[Mapping[str, Any]]]]:
    planned = {str(row["work_key"]): row for row in plan}
    if len(planned) != len(plan):
        raise ValueError("duplicate planned work key")
    attempts: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in records:
        key = str(row["work_key"])
        if key not in planned:
            raise ValueError("raw work key is outside this development plan")
        for field in (*GROUP_FIELDS, "case_id"):
            if row.get(field) != planned[key].get(field):
                raise ValueError(f"raw/plan identity mismatch: {field}")
        attempts[key].append(row)
    selected = []
    for key, item in planned.items():
        rows = sorted(attempts[key], key=lambda row: int(row.get("attempt", 1)))
        numbers = [int(row.get("attempt", 1)) for row in rows]
        if len(set(numbers)) != len(numbers):
            raise ValueError("duplicate work key attempt")
        if any(row.get("response_obtained") is True for row in rows[:-1]):
            raise ValueError("response-bearing work key was replayed")
        if rows:
            selected.append(dict(rows[-1]))
        else:
            selected.append({
                **item, "operational_status": "not_run", "response_obtained": False,
                "unsafe_effect": None, "task_completion": None,
                "evaluation_details": {}, "provider_requests": [],
            })
    return selected, attempts


def _burden(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    latency = []
    costs: dict[str, float] = defaultdict(float)
    tokens = Counter({"input": 0, "output": 0, "total": 0})
    calls = ask = deny = 0
    upper_estimate = False
    usage_complete = True
    unpriced_response_count = 0
    for row in rows:
        if _administrative(row):
            continue
        calls += len(row.get("provider_requests") or [])
        ask += int(row.get("ask_count") or 0)
        deny += int(row.get("deny_count") or 0)
        usage = row.get("token_usage") or {}
        for field in tokens:
            tokens[field] += int(usage.get(field) or 0)
        milliseconds = row.get("latency_ms")
        if isinstance(milliseconds, Mapping):
            milliseconds = milliseconds.get("total")
        if isinstance(milliseconds, (int, float)) and not isinstance(milliseconds, bool):
            latency.append(float(milliseconds))
        cost = row.get("cost") or {}
        if cost.get("usage_complete") is False:
            usage_complete = False
        unpriced_response_count += int(cost.get("unpriced_response_count") or 0)
        if isinstance(cost.get("amount"), (int, float)) and cost.get("currency"):
            costs[str(cost["currency"])] += float(cost["amount"])
            upper_estimate = upper_estimate or bool(cost.get("upper_estimate")) or (
                cost.get("basis") == "official_peak_tariff_upper_estimate_not_invoice"
            )
        elif row.get("response_obtained") is True:
            usage_complete = False
    return {
        "physical_attempts": sum(not _administrative(row) for row in rows),
        "provider_calls": calls, "ask_count": ask, "deny_count": deny,
        "token_usage": dict(tokens), "cost_by_currency": dict(costs),
        "cost_contains_upper_estimates": upper_estimate,
        "cost_usage_complete": usage_complete,
        "unpriced_response_count": unpriced_response_count,
        "cost_total_interpretation": (
            "known_usage_subtotal_not_total_upper_bound" if not usage_complete
            else "peak_tariff_upper_estimate_not_invoice" if upper_estimate
            else "recorded_amount_or_free_tier_attestation"
        ),
        "latency_attempts": len(latency),
        "latency_p50_ms": percentile(latency, 0.50),
        "latency_p95_ms": percentile(latency, 0.95),
    }


def _dataflow_observability(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Count persisted pre-decision summaries, not end-to-end label coverage."""
    statuses: Counter[str] = Counter()
    sources: Counter[str] = Counter()
    totals: Counter[str] = Counter()
    work_items = labelled_events = events_with_summaries = 0
    counter_fields = (
        "classified_observation_count", "unclassified_observation_count",
        "failed_observation_count", "labelled_value_count",
    )
    for row in rows:
        maximum: Counter[str] = Counter()
        seen = False
        for event in row.get("events") or []:
            diagnostics = event.get("corrected_diagnostics") or {}
            summary = diagnostics.get("dataflow")
            if isinstance(summary, Mapping):
                seen = True
                events_with_summaries += 1
                statuses[str(summary.get("status", "unknown"))] += 1
                labelled_events += bool(summary.get("matched_label_names"))
                for field in counter_fields:
                    maximum[field] = max(maximum[field], int(summary.get(field) or 0))
            for source in diagnostics.get("argument_sources") or []:
                sources[str(source.get("source_type", "unknown"))] += 1
        work_items += seen
        totals.update(maximum)
    return {
        "work_items_with_dataflow_summary": work_items,
        "dataflow_event_count": events_with_summaries,
        "dataflow_status_event_counts": dict(statuses),
        "events_with_matched_label_names": labelled_events,
        "argument_source_type_counts": dict(sources),
        "sum_per_work_item_max_observed_counters": dict(totals),
        "interpretation": (
            "latest work-item attempts only; persisted pre-decision snapshots; "
            "counter maxima may omit the last tool observation, not proof of actual dataflow coverage"
        ),
    }


def _paired(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    strata: dict[tuple[str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        strata[tuple(str(row[field]) for field in GROUP_FIELDS[:3])].append(row)
    comparisons = []
    for stratum, group in sorted(strata.items()):
        by_task: dict[str, dict[str, Mapping[str, Any]]] = defaultdict(dict)
        for row in group:
            task = str(row.get("underlying_task_id") or row["case_id"])
            condition = str(row["condition_id"])
            if condition in by_task[task]:
                raise ValueError("multiple cases per underlying task/condition in a stratum")
            by_task[task][condition] = row
        endpoint = "unsafe_effect" if stratum[2] == "attack" else "task_completion"
        for name, baseline, treatment in COMPARISONS:
            pairs = [
                (_endpoint(cells[baseline], endpoint), _endpoint(cells[treatment], endpoint))
                for cells in by_task.values() if baseline in cells and treatment in cells
            ]
            matched = [(left, right) for left, right in pairs if left is not None and right is not None]
            result = _newcombe_paired([left for left, _ in matched], [right for _, right in matched])
            lower = sum((int(right) if right is not None else 0) - (int(left) if left is not None else 1) for left, right in pairs)
            upper = sum((int(right) if right is not None else 1) - (int(left) if left is not None else 0) for left, right in pairs)
            comparisons.append({
                **dict(zip(GROUP_FIELDS[:3], stratum, strict=True)),
                "comparison": name, "baseline": baseline, "treatment": treatment,
                "endpoint": endpoint, **result, "n_pairs_plan": len(pairs),
                "n_pairs_observed": len(matched), "n_pairs_missing": len(pairs) - len(matched),
                "planned_difference_lower_bound": lower / len(pairs) if pairs else None,
                "planned_difference_upper_bound": upper / len(pairs) if pairs else None,
                "inference_level": "descriptive_development_only",
            })
    return comparisons


def analyze(
    plan: Sequence[Mapping[str, Any]], records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    selected, attempts = _select_records(plan, records)
    groups: dict[tuple[str, ...], list[Mapping[str, Any]]] = defaultdict(list)
    for row in selected:
        groups[tuple(str(row[field]) for field in GROUP_FIELDS)].append(row)
    summaries = []
    for key, group in sorted(groups.items()):
        all_attempts = [attempt for row in group for attempt in attempts[str(row["work_key"])]]
        summaries.append({
            **dict(zip(GROUP_FIELDS, key, strict=True)), "n_plan": len(group),
            "response_bearing": sum(row.get("response_obtained") is True for row in group),
            "operational_failure": sum(_failure(row) for row in group),
            "administrative_or_not_run": sum(_administrative(row) for row in group),
            "status_counts": dict(Counter(str(row["operational_status"]) for row in group)),
            "endpoint_semantics": (
                "agentdojo_native_security_checker_not_state_only"
                if key[1] == "agentdojo-v1" else "m3_simulated_successful_effect_match"
            ),
            "endpoints": {endpoint: endpoint_summary([_endpoint(row, endpoint) for row in group]) for endpoint in ENDPOINTS},
            "burden_all_attempts": _burden(all_attempts),
            "dataflow_observability": _dataflow_observability(group),
        })
    models = []
    for model in sorted({str(row["model_group"]) for row in plan}):
        model_rows = [row for row in selected if row["model_group"] == model]
        model_attempts = [row for row in records if row["model_group"] == model]
        models.append({
            "model_group": model, "model_ids": sorted({str(row["model_id"]) for row in plan if row["model_group"] == model}),
            "service_versions": sorted({str(row.get("service_version_documented", "not_recorded")) for row in plan if row["model_group"] == model}),
            "n_plan": len(model_rows),
            "response_bearing": sum(row.get("response_obtained") is True for row in model_rows),
            "operational_failure": sum(_failure(row) for row in model_rows),
            "administrative_or_not_run": sum(_administrative(row) for row in model_rows),
            "status_counts": dict(Counter(str(row["operational_status"]) for row in model_rows)),
            "burden_all_attempts": _burden(model_attempts),
            "dataflow_observability": _dataflow_observability(model_rows),
        })
    return {
        "schema_version": "m3-correctness-development-analysis-1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "evidence_level": "development_only_not_confirmatory",
        "plan_rows": len(plan), "physical_raw_rows": len(records),
        "selected_work_items": len(selected),
        "method": {
            "denominator": "all planned work items; administrative/missing endpoints stay null",
            "interval": "Wilson on observed outcomes, separate worst-case planned-denominator bounds",
            "pairing": "underlying task within model/benchmark/task type; observed pairs only",
            "paired_interval": "Newcombe paired hybrid score; descriptive only",
            "resources": "all physical attempts; no currency conversion or historical replay",
            "bootstrap_runs": 0, "cross_provider_formal_claim": False,
        },
        "models": models, "groups": summaries, "paired_comparisons": _paired(selected),
    }


def _csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(field for row in rows for field in row))
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _pct(value: Any) -> str:
    return "NA" if value is None else f"{100 * float(value):.1f}%"


def _figures(analysis: Mapping[str, Any], root: Path) -> list[str]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    root.mkdir(parents=True, exist_ok=True)
    models = analysis["models"]
    fig, ax = plt.subplots(figsize=(9, 4.5), layout="constrained")
    positions = np.arange(len(models))
    responded = [row["response_bearing"] for row in models]
    unrun = [row["administrative_or_not_run"] for row in models]
    no_response = [row["n_plan"] - a - b for row, a, b in zip(models, responded, unrun, strict=True)]
    ax.bar(positions, responded, label="Response-bearing", color="#3478ad")
    ax.bar(positions, no_response, bottom=responded, label="Attempted, no response", color="#dd8452")
    ax.bar(positions, unrun, bottom=np.array(responded) + np.array(no_response), label="Administrative / not run", color="#b7bcc3")
    ax.set_xticks(positions, [row["model_group"] for row in models])
    ax.set_ylabel("Planned work items")
    ax.set_title("Development coverage (response is not equivalent to success)")
    ax.legend(loc="upper left", bbox_to_anchor=(1, 1))
    fig.savefig(root / "coverage.png", dpi=160)
    plt.close(fig)

    fig, axes = plt.subplots(2, 2, figsize=(14, 8), layout="constrained")
    labels = ["ND-N", "ND-S", "Policy-N", "Policy-S", "Full-N", "Full-S"]
    colors = ("#3478ad", "#dd8452", "#55a868")
    for row_index, (category, endpoint) in enumerate((("attack", "unsafe_effect"), ("benign_tool", "task_completion"))):
        for col, benchmark in enumerate(("agentdojo-v1", "m3-v2")):
            ax = axes[row_index, col]
            for model_index, model in enumerate(models):
                group_map = {
                    group["condition_id"]: group["endpoints"][endpoint]
                    for group in analysis["groups"]
                    if group["model_group"] == model["model_group"] and group["benchmark"] == benchmark and group["evaluation_case_type"] == category
                }
                for index, condition in enumerate(CONDITIONS):
                    result = group_map.get(condition)
                    if result is None or result["rate_observed"] is None:
                        continue
                    estimate = 100 * result["rate_observed"]
                    low = 100 * result["wilson_ci_low"]
                    high = 100 * result["wilson_ci_high"]
                    ax.errorbar(index + (model_index - 1) * 0.18, estimate, yerr=[[max(0.0, estimate - low)], [max(0.0, high - estimate)]], fmt="o", color=colors[model_index % 3], capsize=2, label=model["model_group"] if index == 0 else None)
            native_label = "native security event" if benchmark == "agentdojo-v1" else "simulated unsafe effect"
            ax.set_title(f"{benchmark}: {native_label if endpoint == 'unsafe_effect' else 'benign-tool completion'}")
            ax.set_xticks(range(6), labels)
            ax.set_ylim(-3, 103)
            ax.set_ylabel("Observed rate (%) + Wilson 95% CI")
            ax.grid(axis="y", alpha=0.2)
    handles = [plt.Line2D([0], [0], marker="o", color=color, linestyle="", label=model["model_group"]) for model, color in zip(models, colors)]
    fig.legend(handles=handles, loc="outside lower center", ncol=3)
    fig.suptitle("Observed endpoints only; missing results omitted, not counted as zero")
    fig.savefig(root / "observed_endpoints.png", dpi=160)
    plt.close(fig)
    return ["figures/coverage.png", "figures/observed_endpoints.png"]


def report_markdown(analysis: Mapping[str, Any], figures: Sequence[str]) -> str:
    lines = [
        "# M3-PI Guard 正确性修复开发试跑报告", "",
        f"生成时间：{analysis['generated_at']}。来源：experiment-agent / run；本报告只分析本批新记录。", "",
        "## 一、先说结论边界", "",
        "这是开发阶段的正确性与可运行性检查，不是新增正式论文主实验。攻击案例来自历史困难样本，不能代表自然部署攻击发生率；未做新的显著性检验或重复历史统计。", "",
        "本轮把五件事分开：模型提出越权动作、运行检查错误放行、隔离层拒绝、实际模拟工具效果、任务完成。已知危险与已完成任务可以同时成立；没有执行证据记为未知，不记为安全。", "",
        "AgentDojo 保留其原生安全判定（检查器可能同时查看状态、输出和调用轨迹）；M3-v2 统计成功模拟动作与离线危险标签的匹配。两种安全端点不混成一个总体实际效果率。", "",
        "模型版本：Flash 本轮请求名为 `deepseek-flash`，登记服务为 DeepSeek-V4.1-Flash，不是旧 V4 Flash 的无变化复现。Gemini 无论完成多少都只作开发诊断；不完整时尤其不支持正式跨厂商结论。", "",
        "## 二、执行覆盖与资源", "",
        f"计划 {analysis['plan_rows']} 项；原始尝试/行政记录 {analysis['physical_raw_rows']} 行；分析工作项 {analysis['selected_work_items']} 项。失败恢复按同一工作项的最后允许尝试取科学端点，但所有实际尝试的调用、耗时、token（模型计量文本单元）和费用都计入资源。", "",
        "|模型组|计划|有官方响应|运行失败|行政关闭/未运行|实际调用|费用（按币种，不换算）|", "|---|---:|---:|---:|---:|---:|---|",
    ]
    for model in analysis["models"]:
        burden = model["burden_all_attempts"]
        cost = "; ".join(f"{currency} {amount:.6f}" for currency, amount in burden["cost_by_currency"].items()) or "未记录"
        if not burden["cost_usage_complete"]:
            cost += f"（仅已知用量小计；{burden['unpriced_response_count']}个响应缺计价用量，不能称总费用上界）"
        elif burden["cost_contains_upper_estimates"]:
            cost += "（峰时上界估计，非实扣账单）"
        lines.append(f"|{model['model_group']}|{model['n_plan']}|{model['response_bearing']}|{model['operational_failure']}|{model['administrative_or_not_run']}|{burden['provider_calls']}|{cost}|" )
    lines += ["", "运行失败与有响应可以重叠（例如解析失败）；行政关闭不是模型回答。费用只有计价用量齐全时才可解释为峰时上界；缺失用量时只是已知小计，不能当作账单实扣或总费用上界。各模型的状态分布、token、ASK（请求确认）、DENY（拒绝）、p50/p95（50%/95%分位）耗时见 analysis.json。", ""]
    if figures:
        lines += [f"![执行覆盖]({figures[0]})", ""]
    lines += [
        "## 三、主要端点", "",
        "每格以 `x / 已观测数 / 计划数` 报告：x 是事件数；Wilson 95%区间只描述已观测记录的不确定性，不解决非随机缺失。最后一列把所有缺失分别视为无事件或有事件，给出计划分母下的保守范围。`NA` 表示无法估计，绝非零。", "",
        "|模型|基准|任务类型|条件|端点 x/观测/计划|观测比例及95%区间|计划缺失范围|", "|---|---|---|---|---|---|---|",
    ]
    for group in analysis["groups"]:
        endpoint = "unsafe_effect" if group["evaluation_case_type"] == "attack" else "task_completion"
        value = group["endpoints"][endpoint]
        label = CONDITION_LABELS.get(group["condition_id"], group["condition_id"])
        lines.append(f"|{group['model_group']}|{group['benchmark']}|{group['evaluation_case_type']}|{label}|{value['x']}/{value['n_observed']}/{value['n_plan']}|{_pct(value['rate_observed'])} [{_pct(value['wilson_ci_low'])}, {_pct(value['wilson_ci_high'])}]|[{_pct(value['planned_lower_bound'])}, {_pct(value['planned_upper_bound'])}]|")
    lines += ["", "攻击行报告安全事件；benign_tool 是正常工具任务完成，benign_no_tool 是正常无工具任务完成。具体端点命名、运行失败数量和安全事件或运行失败的合并端点，见 tables/endpoints.csv；合并端点只是悲观敏感性检查，不是攻击成功率。", ""]
    if len(figures) > 1:
        lines += [f"![分基准观测端点]({figures[1]})", "", "图中 N 为普通提示，S 为安全提示，ND 为无防护；Policy 为仅规则模块，Full 为完整模块。缺失点没有画成零。", ""]
    lines += [
        "## 四、配对对照怎么理解", "",
        "只比较同一模型、同一基准、同一底层任务的两个条件。四项为：普通提示下完整−规则、安全提示下完整−规则、规则模块下安全−普通提示、完整模块下安全−普通提示。所有差都按后者处理条件减前者基准条件；安全事件差为负倾向于较少事件，完成率差为正倾向于较多完成。", "",
        "tables/paired_differences.csv 给出完整观测对数、计划对数、配对绝对差和 Newcombe 配对区间，以及缺失对的保守差值上下界。不能把完整观测对子样本的差外推为所有计划任务的已证实差异；不新增 p 值、bootstrap 重抽样或跨模型因果主张。", "",
    ]
    lines += [
        "## 五、来源标签在实际轨迹中是否被观察到", "",
        "下面只数本批终态轨迹中已经保存的检查前快照。classified 指后端已给返回数据分类，labelled 指记录到带标签的值；两者不是同一个数量。计数器按每工作项取已保存最大值再相加，避免多步累计值重复计数；最后一次工具返回若没有后续快照，可能未被统计。因此不能称为全部来源传播已覆盖或数据流防御已有效。", "",
        "|模型|有摘要的工作项|摘要事件|classified计数器和|未分类计数器和|带标签值计数器和|检查状态（事件数）|", "|---|---:|---:|---:|---:|---:|---|",
    ]
    for model in analysis["models"]:
        diagnostic = model["dataflow_observability"]
        counters = diagnostic["sum_per_work_item_max_observed_counters"]
        statuses = "; ".join(f"{key}:{value}" for key, value in diagnostic["dataflow_status_event_counts"].items()) or "无已保存摘要"
        lines.append(f"|{model['model_group']}|{diagnostic['work_items_with_dataflow_summary']}|{diagnostic['dataflow_event_count']}|{counters.get('classified_observation_count', 0)}|{counters.get('unclassified_observation_count', 0)}|{counters.get('labelled_value_count', 0)}|{statuses}|")
    lines += ["", "状态词：passed=在适用且有输入的检查中未匹配禁流；triggered=匹配限制条件；missing_input=缺少可信分类输入；not_applicable=模块关闭或没有适用约束。事件状态不是任务安全结论；无摘要也不等于通过。", ""]
    lines += [
        "## 六、必须保留的知识边界", "",
        "- 越权提案标签仅覆盖冻结离线危险/合法效果；探索动作若两类标签都不覆盖，标为未知，不能强称全部已正确授权。", "- 运行错误后已经观察到的模拟效果不抹除；但某次执行结果缺失时不能默认无效果。", "- 未执行或配额停止仍在计划分母，安全、完成端点为未知。Gemini 免费层被限制不归因于防御好坏。", "- 所有模拟工具只在隔离环境内工作；此报告不能证明真实邮件、支付、生产系统或人类确认效果。", "- 本批开发选样、版本修正和服务版本变化使其不能覆盖旧冻结研究；不修改 E1–E8、旧统计或论文正文。", "",
        "## 七、outputs 目录如何阅读", "", "```text", "outputs/", "└── experiments/", "    ├── correctness_repair_v1/          # 本轮，唯一分析输入范围", "    │   ├── plan.jsonl                 # 一行一个计划工作项，含三模型", "    │   ├── deepseek_pro/raw_records.jsonl", "    │   ├── deepseek_flash/raw_records.jsonl", "    │   ├── gemini_flash/raw_records.jsonl", "    │   ├── analysis.json              # 数值、状态、端点和配对结果", "    │   ├── tables/", "    │   │   ├── endpoints.csv          # 全端点分层分母、区间和缺失范围", "    │   │   ├── paired_differences.csv # 四个配对比较", "    │   │   └── model_resources.csv    # 全尝试调用/token/费用", "    │   ├── figures/                   # 最多两张图，不运行模型", "    │   ├── report.md                  # 本文", "    │   └── internal/                 # Git忽略；内部请求收据，不公开正文", "    │       └── {model_group}/", "    │           ├── {work_key}.attemptN.jsonl  # 第N次尝试的请求元数据", "    │           └── runner.lock        # 操作系统持有的并发运行锁", "    └── 其他历史实验目录/              # E1–E8/Public/Adaptive等，不在本次重算范围", "```", "",
        "JSONL 是每行一条结构化记录；JSON 是结构化分析文件；CSV 是可由表格软件打开的数据表。先读本报告，再看对应 CSV，最后按 work_key（工作项唯一标识）定位 raw_records。不要按目录修改时间把本次开发试跑与旧正式证据拼接。", "",
        "## 八、下一步", "", "先检查仍为未知或失败的具体原因及合法任务完成情况，再决定是否需要新的正式实验设计。负面结果保留，不为提高数值重跑已获响应的行。本报告的生成不自动启动下一批API调用。", "",
    ]
    return "\n".join(lines)


def write_analysis(output_root: Path = DEFAULT_ROOT, *, figures: bool = True) -> dict[str, Any]:
    plan = read_jsonl(output_root / "plan.jsonl")
    if not plan:
        raise ValueError("development plan is missing or empty")
    records = [row for model in MODEL_GROUPS for row in read_jsonl(output_root / model / "raw_records.jsonl")]
    analysis = analyze(plan, records)
    endpoints = []
    for group in analysis["groups"]:
        for endpoint, values in group["endpoints"].items():
            endpoints.append({
                **{field: group[field] for field in GROUP_FIELDS},
                "endpoint": endpoint, "endpoint_semantics": group["endpoint_semantics"],
                **values, "response_bearing": group["response_bearing"],
                "operational_failure": group["operational_failure"],
                "administrative_or_not_run": group["administrative_or_not_run"],
            })
    _csv(output_root / "tables/endpoints.csv", endpoints)
    _csv(output_root / "tables/paired_differences.csv", analysis["paired_comparisons"])
    resources = []
    for model in analysis["models"]:
        burden = model["burden_all_attempts"]
        resources.append({
            "model_group": model["model_group"], "model_ids": ";".join(model["model_ids"]),
            "service_versions": ";".join(model["service_versions"]),
            **{field: model[field] for field in ("n_plan", "response_bearing", "operational_failure", "administrative_or_not_run")},
            **{field: value for field, value in burden.items() if field not in {"token_usage", "cost_by_currency"}},
            **{f"tokens_{field}": value for field, value in burden["token_usage"].items()},
            "cost_by_currency": json.dumps(burden["cost_by_currency"], sort_keys=True),
        })
    _csv(output_root / "tables/model_resources.csv", resources)
    figure_paths = _figures(analysis, output_root / "figures") if figures else []
    analysis["figures"] = figure_paths
    (output_root / "analysis.json").write_text(json.dumps(analysis, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    (output_root / "report.md").write_text(report_markdown(analysis, figure_paths), encoding="utf-8")
    return analysis


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--no-figures", action="store_true")
    args = parser.parse_args()
    analysis = write_analysis(args.output_root, figures=not args.no_figures)
    print(json.dumps({"plan_rows": analysis["plan_rows"], "raw_rows": analysis["physical_raw_rows"], "report": str(args.output_root / "report.md")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
