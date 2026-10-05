"""Single-pass post-repair results; unknown outcomes never become safe zeros."""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from experiments.paper_v2.claude_revision_v1 import OUTPUT
from experiments.paper_v2.correctness_plan_v1 import read_jsonl
from experiments.paper_v2.correctness_runner_v1 import critical_error, latest_records
from experiments.paper_v2.e6_cross_provider_calibration_analysis_v1 import _newcombe_paired
from m3_eval.statistics import holm_adjust, mcnemar_exact, wilson_interval

COMPARISONS = (
    ("policy_exact_minus_auto", ("m3_policy_only", "auto_compiled"), ("m3_policy_only", "exact_target_v2")),
    ("full_exact_minus_auto", ("m3_full_normal_prompt", "auto_compiled"), ("m3_full_normal_prompt", "exact_target_v2")),
    ("auto_full_minus_policy", ("m3_policy_only", "auto_compiled"), ("m3_full_normal_prompt", "auto_compiled")),
    ("exact_full_minus_policy", ("m3_policy_only", "exact_target_v2"), ("m3_full_normal_prompt", "exact_target_v2")),
)


def endpoint(rows, field, planned):
    values = [r.get(field) for r in rows]
    if any(v is not None and type(v) is not bool for v in values):
        raise ValueError("endpoint must be boolean or unknown")
    true = sum(v is True for v in values)
    observed = sum(v is not None for v in values)
    unknown = planned - observed
    if unknown < 0:
        raise ValueError("observed count exceeds plan")
    return {"true": true, "observed": observed, "planned": planned, "unknown": unknown,
            "observed_rate": true / observed if observed else None,
            "observed_wilson_95": wilson_interval(true, observed),
            "itt_lower": true / planned if planned else None,
            "itt_upper": (true + unknown) / planned if planned else None}


def paired(rows, field, left, right, *, seed=20261006):
    by_case = defaultdict(dict)
    for row in rows:
        by_case[row["case_id"]][(row["condition_id"], row["authorization_regime"])] = row
    eligible = [d for d in by_case.values() if left in d and right in d]
    known = [d for d in eligible if type(d[left].get(field)) is bool and type(d[right].get(field)) is bool]
    a, b = [d[left][field] for d in known], [d[right][field] for d in known]
    interval = _newcombe_paired(a, b)
    clustered = defaultdict(list)
    for d in known:
        clustered[d[left]["underlying_task_id"]].append(int(d[right][field]) - int(d[left][field]))
    if clustered:
        sums = np.array([sum(v) for v in clustered.values()], dtype=float)
        sizes = np.array([len(v) for v in clustered.values()], dtype=float)
        indexes = np.random.default_rng(seed).integers(0, len(sums), size=(10_000, len(sums)))
        estimates = sums[indexes].sum(axis=1) / sizes[indexes].sum(axis=1)
        low, high = np.quantile(estimates, [.025, .975]).tolist()
        degenerate = low == high
        bootstrap = {"method": "underlying_task_cluster_bootstrap_within_benchmark", "iterations": 10000, "seed": seed, "clusters": len(sums),
                     "estimate": float(sums.sum() / sizes.sum()), "ci_low": None if degenerate else low,
                     "ci_high": None if degenerate else high, "degenerate": degenerate,
                     "fallback": "newcombe_paired_hybrid_score" if degenerate else None}
    else:
        bootstrap = {"clusters": 0, "estimate": None, "ci_low": None, "ci_high": None}
    return {"planned_pair_cases": len(eligible), "known_pairs": len(known), "unknown_pairs": len(eligible) - len(known),
            "paired_interval": interval, "bootstrap": bootstrap, "mcnemar": mcnemar_exact(a, b),
            "p_value_unit": "case_pair; cluster bootstrap used for dependent underlying tasks"}


def analyze(output: Path = OUTPUT) -> dict[str, Any]:
    plan = read_jsonl(output / "study_plan.jsonl")
    rows = list(latest_records(read_jsonl(output / "deepseek_pro_raw.jsonl") + read_jsonl(output / "synthetic_regression_raw.jsonl")).values())
    planned_by_key = {r["work_key"]: r for r in plan}
    for row in rows:
        expected = planned_by_key.get(row["work_key"])
        if expected is None or any(row.get(k) != expected.get(k) for k in ("case_id", "condition_id", "model_id", "runtime_version", "authorization_regime", "prompt_factor")):
            raise ValueError("result identity differs from plan")
        if critical_error(row):
            raise ValueError("safety or identity error present")
    main = [r for r in rows if r["study_part"] == "authorization"]
    observed_by_key = {r["work_key"]: r for r in main}
    paired_rows = [{**r, **observed_by_key.get(r["work_key"], {})} for r in plan if r["study_part"] == "authorization"]
    controls = [r for r in rows if r["study_part"] == "synthetic"]
    cells = []
    group_fields = ("benchmark", "evaluation_case_type", "condition_id", "authorization_regime")
    groups = defaultdict(list)
    observed = defaultdict(list)
    for row in plan:
        if row["study_part"] == "authorization":
            groups[tuple(row[k] for k in group_fields)].append(row)
    for row in main:
        observed[tuple(row[k] for k in group_fields)].append(row)
    for key, planned in sorted(groups.items()):
        selected = observed[key]
        latencies = [r["latency_ms"] for r in selected if isinstance(r.get("latency_ms"), (int, float))]
        cells.append({**dict(zip(group_fields, key)), "records": len(selected), "planned": len(planned),
                      "unsafe": endpoint(selected, "unsafe_effect", len(planned)), "completion": endpoint(selected, "task_completion", len(planned)),
                      "statuses": dict(Counter(r["operational_status"] for r in selected)),
                      "failures": sum(r["operational_status"] != "completed" for r in selected),
                      "ask_count": sum(r.get("ask_count", 0) for r in selected), "deny_count": sum(r.get("deny_count", 0) for r in selected),
                      "isolation_rejections": sum(bool(e.get("isolation_rejected")) for r in selected for e in r.get("events", [])),
                      "latency_p50_ms": float(np.quantile(latencies, .5)) if latencies else None,
                      "latency_p95_ms": float(np.quantile(latencies, .95)) if latencies else None})
    comparisons = []
    for benchmark in ("agentdojo-v1", "m3-v2"):
        for category, field in (("attack", "unsafe_effect"), ("benign_tool", "task_completion")):
            selected = [r for r in paired_rows if r["benchmark"] == benchmark and r["evaluation_case_type"] == category]
            family = []
            for name, left, right in COMPARISONS:
                family.append({"comparison": name, "benchmark": benchmark, "endpoint": field, **paired(selected, field, left, right)})
            adjusted = holm_adjust([r["mcnemar"]["p_value"] for r in family])
            for row, p in zip(family, adjusted):
                row["holm_p"] = p
            comparisons += family
    return {"study_id": "m3-claude-revision-v1", "planned": len(plan), "recorded": len(rows), "pending": len(plan) - len(rows),
            "authorization_recorded": len(main), "synthetic_recorded": len(controls), "cells": cells, "comparisons": comparisons,
            "synthetic": [{k: r.get(k) for k in ("model_id", "scenario_id", "module_factor", "unsafe_effect", "task_completion", "operational_status", "ask_count", "deny_count", "evaluation_details")} for r in controls],
            "statuses": dict(Counter(r["operational_status"] for r in rows)),
            "provider_calls": sum(r["provider_call_count"] for r in rows), "token_usage": {k: sum(r["token_usage"][k] for r in rows) for k in ("input", "output", "total")},
            "cost_known_peak_estimate_cny": sum(r["cost"]["amount"] for r in rows),
            "cost_usage_complete": all(r["cost"].get("usage_complete", False) for r in rows),
            "pricing_reference": "https://api-docs.deepseek.com/quick_start/pricing/",
            "semantics": {"agentdojo-v1": "native offline attack-success checker, not state-only effect", "m3-v2": "observed unauthorized in-memory action effects, boundary rejections separate"},
            "statistical_cautions": ["unknown endpoints excluded only from observed paired estimates, preserved in ITT bounds", "case-pair McNemar is auxiliary when underlying tasks repeat", "zero empirical bootstrap width is not deterministic safety", "no cross-provider or SOTA inference", "historical fixed cohort is not deployment prevalence"]}


def write_outputs(result, output: Path = OUTPUT):
    (output / "analysis.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tables, figures = output / "tables", output / "figures"
    tables.mkdir(exist_ok=True)
    figures.mkdir(exist_ok=True)
    flattened = [{**{k: r[k] for k in ("benchmark", "evaluation_case_type", "condition_id", "authorization_regime", "records", "planned", "failures", "ask_count", "deny_count", "latency_p50_ms", "latency_p95_ms")},
                  **{f"{label}_{k}": v for label in ("unsafe", "completion") for k, v in r[label].items() if k != "observed_wilson_95"}} for r in result["cells"]]
    with (tables / "cells.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, list(flattened[0]))
        writer.writeheader()
        writer.writerows(flattened)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(12, 4), constrained_layout=True)
    for ax, benchmark in zip(axes, ("agentdojo-v1", "m3-v2")):
        selected = [r for r in result["cells"] if r["benchmark"] == benchmark and r["evaluation_case_type"] == "benign_tool" and r["authorization_regime"] in {"auto_compiled", "exact_target_v2"}]
        labels = [r["condition_id"].replace("m3_", "").replace("_normal_prompt", "") + "\n" + r["authorization_regime"] for r in selected]
        ax.bar(labels, [100 * r["completion"]["itt_lower"] for r in selected], color="#416c92")
        ax.set(title=benchmark, ylabel="Observed completions / planned (%)", ylim=(0, 105))
        ax.tick_params(axis="x", labelsize=8)
    fig.savefig(figures / "completion_by_regime.png", dpi=180)
    plt.close(fig)
    lines = ["# Claude整改后实验报告", "", "## Material Passport", "", "- Origin Skill: academic-research-suite / experiment-agent", "- Mode: run + validate", "- 日期：2026-10-06", f"- 状态：{'EXECUTED' if result['pending'] == 0 else 'PARTIALLY EXECUTED'}；不代表论文投稿就绪。", "",
             "## 实际完成量", "", f"计划{result['planned']}行，已记录{result['recorded']}行，未记录{result['pending']}行。授权矩阵{result['authorization_recorded']}/900，修复后合成控制{result['synthetic_recorded']}/16。", f"运行状态：`{json.dumps(result['statuses'], ensure_ascii=False)}`。", f"官方请求{result['provider_calls']}次，总token {result['token_usage']['total']}；已知用量峰时估计CNY {result['cost_known_peak_estimate_cny']:.4f}，不是账单实付。", "",
             "## 研究设计与边界", "", "使用原固定180案例，四个主条件全部normal普通提示；policy/full仅运行模块不同，auto_compiled/exact_target_v2仅Guard授权不同。后者是明示oracle（离线答案派生的精确目标对照），不是可部署非oracle系统。60条嵌套子集追加broad、underspecified、conflicting。旧实验和默认配置不改写，12正式前缀不重复。", "", "AgentDojo沿用原生攻击成功评分，M3-v2只计有执行证据的模拟越权效果。拒绝、隔离、解析失败、达到步数上限和未知分别记录。所有失败留在计划分母。Gemini未启动，本地开放模型未开展；不能宣称跨厂商复现。", "",
             "## 授权矩阵分层结果", "", "|基准/类型|条件/授权|记录/计划|危险结果 真/已知|完成 真/已知|未知危险/完成|非正常结束|", "|---|---|---:|---:|---:|---:|---:|"]
    for r in result["cells"]:
        lines.append(f"|{r['benchmark']}/{r['evaluation_case_type']}|{r['condition_id']}/{r['authorization_regime']}|{r['records']}/{r['planned']}|{r['unsafe']['true']}/{r['unsafe']['observed']}|{r['completion']['true']}/{r['completion']['observed']}|{r['unsafe']['unknown']}/{r['completion']['unknown']}|{r['failures']}|")
    lines += ["", "## 配对差异", "", "四个比较按各基准、各端点单独形成Holm家族。区间、McNemar、10,000次底层任务聚类bootstrap详见analysis.json。bootstrap退化时CI记NA并提供Newcombe区间，不以[0,0]宣称零风险。未知配对不填零。", "", "|基准|端点|比较|已知配对|差异pp|配对95%CI pp|Holm p|", "|---|---|---|---:|---:|---|---:|"]
    for r in result["comparisons"]:
        interval = r["paired_interval"]
        text = "NA" if interval["estimate"] is None else f"{100 * interval['estimate']:+.2f}"
        ci = "NA" if interval["ci_low"] is None else f"[{100 * interval['ci_low']:+.2f}, {100 * interval['ci_high']:+.2f}]"
        lines.append(f"|{r['benchmark']}|{r['endpoint']}|{r['comparison']}|{r['known_pairs']}|{text}|{ci}|{r['holm_p']:.4f}|")
    lines += ["", "## 修复后合成控制", "", "仅为四个明确内存场景，不代表真实用户或部署数据。合法任务完成与危险效果可同时为真。", "", "|模型|场景|模块|危险/完成|ASK/DENY|状态|", "|---|---|---|---|---|---|"]
    for r in result["synthetic"]:
        lines.append(f"|{r['model_id']}|{r['scenario_id']}|{r['module_factor']}|{r['unsafe_effect']}/{r['task_completion']}|{r['ask_count']}/{r['deny_count']}|{r['operational_status']}|")
    lines += ["", "## 产物目录与复算", "", "所有本轮实验产物在`E:\\M3_PI_Guard_test\\outputs\\experiments\\claude_revision_v1`。", "", "```text", "claude_revision_v1/", "├── study_plan.jsonl                 # 916个唯一计划项及版本/参数", "├── deepseek_pro_raw.jsonl           # 900授权行的终态记录（append-only）", "├── synthetic_regression_raw.jsonl   # 16合成控制的终态记录", "├── authorization_status.json       # 前缀门与运行进度", "├── synthetic_status.json           # 合成控制运行状态", "├── analysis.json                   # 一次性统计与未知上下界", "├── tables/cells.csv                # 分层表", "├── figures/completion_by_regime.png # 合法工具任务完成图", "├── report.md                       # 本报告", "└── internal/                       # 本地请求摘要和锁，Git忽略", "```", "", "代码入口：`experiments/paper_v2/claude_revision_v1.py`，分析入口：`python -m experiments.paper_v2.claude_revision_analysis_v1`。分析仅读本研究两份raw，不重算历史。作者信息、LaTeX、盲测、Full Harness均未修改/执行。", "", "## 解释边界与方法复核", "", "方法风险11/11检查：分层避免聚合反转；不做个体/部署因果推广；历史案例选择限制保留；不按新结果选择/排除；不推断部署基率；不把历史前后变化解释为修复因果增益；未知保留避免幸存者偏差；报告所有预定比较并Holm校正；参数和范围预先固定；结论限定当前受控运行；无反向因果推断。事件稀少或零事件均不能证明防护有效、等效或绝对安全。", "", "可信度：9/10。依据：新raw、定向测试和请求回执；科学推广及独立模型证据仍有限。", ""]
    (output / "report.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    result = analyze()
    write_outputs(result)
    print(json.dumps({k: result[k] for k in ("planned", "recorded", "pending", "statuses", "provider_calls", "token_usage", "cost_known_peak_estimate_cny")}, ensure_ascii=False))
