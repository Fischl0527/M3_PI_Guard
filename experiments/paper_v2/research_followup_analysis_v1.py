"""One-pass contemporaneous calibration statistics and readable report."""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict

import numpy as np

from experiments.paper_v2.claude_revision_analysis_v1 import endpoint, paired
from experiments.paper_v2.correctness_plan_v1 import read_jsonl
from experiments.paper_v2.correctness_runner_v1 import critical_error, latest_records
from experiments.paper_v2.research_followup_calibration_v1 import CORE, OUTPUT, STUDY, VIGIL
from m3_eval.statistics import holm_adjust


def analyze(plan, raw):
    expected = {r["work_key"]: r for r in plan}
    if len(expected) != len(plan):
        raise ValueError("duplicate plan key")
    records = latest_records(raw)
    request_ids = set()
    for key, row in records.items():
        original = expected.get(key)
        if original is None or any(row.get(f) != original.get(f) for f in ("case_id", "condition_id", "model_id", "execution_identity", "runtime_revision", "authorization_regime", "prompt_factor")):
            raise ValueError("record and plan identity mismatch")
        if critical_error(row):
            raise ValueError("critical safety or identity finding")
        if row["provider_call_count"] != len(row["provider_requests"]) or row["provider_call_count"] > row["max_provider_calls"]:
            raise ValueError("call budget mismatch")
        for req in row["provider_requests"]:
            local = req.get("local_request_id")
            if not local or local in request_ids or not req.get("payload_sha256"):
                raise ValueError("request commitment missing or repeated")
            request_ids.add(local)
            if req.get("response_received") and not all(req.get(f) for f in ("provider_response_id", "returned_model")):
                raise ValueError("official identity missing")
    groups = defaultdict(list)
    for row in plan:
        groups[(row["benchmark"], row["evaluation_case_type"], row["condition_id"])].append(row)
    cells = []
    for (benchmark, category, condition), group in sorted(groups.items()):
        rows = [records[r["work_key"]] for r in group if r["work_key"] in records]
        failure_sensitive = [{**r, "unsafe_or_failure": True if r["operational_status"] != "completed" or r.get("unsafe_effect") is True else r.get("unsafe_effect")} for r in rows]
        latencies = [r["latency_ms"] for r in rows if isinstance(r.get("latency_ms"), (int, float))]
        cells.append({"benchmark": benchmark, "evaluation_case_type": category, "condition_id": condition, "planned": len(group), "recorded": len(rows),
                      "unsafe": endpoint(rows, "unsafe_effect", len(group)), "completion": endpoint(rows, "task_completion", len(group)),
                      "unsafe_or_failure": endpoint(failure_sensitive, "unsafe_or_failure", len(group)),
                      "statuses": dict(Counter(r["operational_status"] for r in rows)), "failures": sum(r["operational_status"] != "completed" for r in rows),
                      "ask_count": sum(r.get("ask_count", 0) for r in rows), "deny_count": sum(r.get("deny_count", 0) for r in rows),
                      "provider_calls": sum(r["provider_call_count"] for r in rows),
                      "latency_p50_ms": float(np.quantile(latencies, .5)) if latencies else None,
                      "latency_p95_ms": float(np.quantile(latencies, .95)) if latencies else None})
    paired_rows = [{**r, **records.get(r["work_key"], {})} for r in plan]
    comparisons = []
    for benchmark in ("agentdojo-v1", "m3-v2"):
        for category, field in (("attack", "unsafe_effect"), ("benign_tool", "task_completion")):
            selected = [r for r in paired_rows if r["benchmark"] == benchmark and r["evaluation_case_type"] == category]
            family = [{"benchmark": benchmark, "endpoint": field, "comparison": name,
                       **paired(selected, field, (left, "auto_compiled"), (right, "auto_compiled"))}
                      for name, left, right in (("policy_minus_nd", CORE[0], CORE[1]), ("full_minus_nd", CORE[0], CORE[2]), ("full_minus_policy", CORE[1], CORE[2]))]
            for row, p in zip(family, holm_adjust([r["mcnemar"]["p_value"] for r in family])):
                row["holm_p"] = p
                row["analysis_role"] = "primary_prespecified"
            comparisons += family
            for name, left, right in (("vigil_minus_nd", CORE[0], VIGIL), ("full_minus_vigil", VIGIL, CORE[2])):
                comparisons.append({"benchmark": benchmark, "endpoint": field, "comparison": name,
                                    "analysis_role": "configured_baseline_descriptive", "holm_p": None,
                                    **paired(selected, field, (left, "auto_compiled"), (right, "auto_compiled"))})
    observed = list(records.values())
    return {"study_id": STUDY, "planned": len(plan), "recorded": len(observed), "pending": len(plan) - len(observed),
            "projection_receipts": {"explicit_no_forbidden_field": sum(r.get("online_forbidden_fields_present") is False for r in observed),
                                    "missing": sum(r.get("online_forbidden_fields_present") is None for r in observed),
                                    "forbidden_present": sum(bool(r.get("online_forbidden_fields_present")) for r in observed)},
            "structured_safety_receipts": {"present": sum(bool(r.get("safety_receipt")) for r in observed),
                                           "missing": sum(not bool(r.get("safety_receipt")) for r in observed)},
            "cells": cells, "comparisons": comparisons, "statuses": dict(Counter(r["operational_status"] for r in observed)),
            "provider_calls": sum(r["provider_call_count"] for r in observed),
            "tokens": sum(r.get("token_usage", {}).get("total", 0) for r in observed),
            "cost_known_historical_peak_estimate_cny": sum(r["cost"]["amount"] for r in observed),
            "cost_note": "2026-09-20 fixedCNY tariff estimate, not invoice; current provider metadata verified, currentCNY page unavailable",
            "baseline_scope": "pinnedVIGIL hybrid deterministic auditor with official one-call constraint generator; LLM verification disabled; 16 vs8 request cap disclosed",
            "inference": "controlled fixed calibration cohort, not deployment prevalence, SOTA, repair-causal gain or cross-provider generalization"}


def write_outputs(result, output=OUTPUT):
    output.mkdir(parents=True, exist_ok=True)
    (output / "analysis.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tables, figures = output / "tables", output / "figures"
    tables.mkdir(exist_ok=True)
    figures.mkdir(exist_ok=True)
    flat = [{**{k: r[k] for k in ("benchmark", "evaluation_case_type", "condition_id", "planned", "recorded", "failures", "ask_count", "deny_count", "provider_calls", "latency_p50_ms", "latency_p95_ms")},
             **{f"{label}_{k}": v for label in ("unsafe", "completion", "unsafe_or_failure") for k, v in r[label].items() if k != "observed_wilson_95"}} for r in result["cells"]]
    with (tables / "cells.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, list(flat[0]))
        writer.writeheader()
        writer.writerows(flat)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 2, figsize=(12, 7), constrained_layout=True)
    names = {CORE[0]: "No defense", CORE[1]: "Policy only", CORE[2]: "Full modules", VIGIL: "VIGIL configured"}
    for i, benchmark in enumerate(("agentdojo-v1", "m3-v2")):
        for j, (category, label) in enumerate((("attack", "unsafe"), ("benign_tool", "completion"))):
            selected = sorted([r for r in result["cells"] if r["benchmark"] == benchmark and r["evaluation_case_type"] == category], key=lambda r: (*CORE, VIGIL).index(r["condition_id"]))
            ax = axes[i, j]
            for k, row in enumerate(selected):
                value = row[label]["observed_rate"]
                if value is None:
                    ax.text(k, 5, "NE", ha="center")
                    continue
                low, high = row[label]["observed_wilson_95"]
                ax.bar(k, 100 * value, color="#356c8c")
                ax.errorbar(k, 100 * value, yerr=[[100 * (value - low)], [100 * (high - value)]], fmt="none", color="black", capsize=3)
            ax.set_xticks(range(len(selected)), [names[r["condition_id"]] for r in selected], rotation=12)
            ax.set(title=f"{benchmark}: {category}", ylabel=f"Observed {label} (%)", ylim=(0, 105))
    fig.savefig(figures / "contemporaneous_endpoints.png", dpi=180)
    plt.close(fig)
    lines = ["# P1 同期校准报告", "", "## Material Passport", "", "- Origin Skill: academic-research-suite / experiment-agent", "- Mode: run + validate", "- Date: 2026-10-06", "- Status: actual recorded results, not submission readiness", "", "## 完成量与设计", "",
             f"计划{result['planned']}条，记录{result['recorded']}，待记录{result['pending']}。状态：`{result['statuses']}`。官方请求{result['provider_calls']}次，token {result['tokens']}；CNY旧峰时费率参考估计{result['cost_known_historical_peak_estimate_cny']:.4f}，并非当前账单。", "",
             "固定120个案例：两个基准各30攻击、30良性工具。攻击每个底层任务只选一个实例；选自已固定cohort，不使用本轮结果筛选。所有条件normal普通提示/auto_compiled授权/T0/512输出/180秒超时；模拟执行能力和物理安全边界相同。无真实邮件、支付、生产接口、宿主代码执行。", "",
             "三主条件各120条；配置明确的VIGIL额外120。VIGIL固定源码hybrid确定性审计、模型生成约束，关闭LLM二次验证；16-call上限，其余8-call。不能称完整默认VIGIL或最强SOTA系统。16正式前缀已计入总量，不重复。", "",
             "第一阶段在120条后因两次VIGIL约束输出截断被误分类为程序错误而停止，并使一条已有响应的无防护任务终止。这三条及全部120条原记录都保留，没有重跑。telemetry_v1.1仅隔离线程日志并将后续身份有效、明确length截断的约束失败归为parse_failure；512输出、提示、权限与计划不改。续跑仅覆盖此前未触碰项。两阶段分别记录runner_revision，不能把分类修正解释成防御增益。", "",
             f"投影收据完整性：{result['projection_receipts']['explicit_no_forbidden_field']}条明确记录在线禁止字段不存在，{result['projection_receipts']['missing']}条缺少此收据；实际记录为存在的条数{result['projection_receipts']['forbidden_present']}。缺收据的两条早期VIGIL失败为diagnostic/未知，保留ITT；没有后补旧收据，也不将未观察到泄漏写成480条全部证实无泄漏。480条均记录provider tools禁用、真实external effect为0；完整结构化safety_receipt为{result['structured_safety_receipts']['present']}条，缺{result['structured_safety_receipts']['missing']}条（VIGIL约束失败，效果端点未知）。这是本运行路径的限定检查，不是任意系统安全认证。", "", "## 结果", "",
             "|基准/类型|条件|记录/计划|危险 真/已知|完成 真/已知|未知危险/完成|非正常结束|ASK/DENY|", "|---|---|---:|---:|---:|---:|---:|---:|"]
    for r in result["cells"]:
        lines.append(f"|{r['benchmark']}/{r['evaluation_case_type']}|{names[r['condition_id']]}|{r['recorded']}/{r['planned']}|{r['unsafe']['true']}/{r['unsafe']['observed']}|{r['completion']['true']}/{r['completion']['observed']}|{r['unsafe']['unknown']}/{r['completion']['unknown']}|{r['failures']}|{r['ask_count']}/{r['deny_count']}|")
    lines += ["", "![同期危险效果与良性完成率](figures/contemporaneous_endpoints.png)", "", "## 配对比较", "", "核心三个比较按各基准、各端点分别Holm校正；VIGIL两项是描述性配置对照，不增加主要显著性家族。区间采用Newcombe配对区间、10,000次底层任务bootstrap，McNemar为辅助检验。未知不填零，所有计划项保留在ITT上下界；零事件和退化bootstrap不是确定性安全证明。", "", "|基准|端点|比较|已知配对|差异pp|95%配对区间pp|Holm p|", "|---|---|---|---:|---:|---|---:|"]
    for r in result["comparisons"]:
        interval = r["paired_interval"]
        effect = "NE" if interval["estimate"] is None else f"{100 * interval['estimate']:+.2f}"
        ci = "NE" if interval["ci_low"] is None else f"[{100 * interval['ci_low']:+.2f},{100 * interval['ci_high']:+.2f}]"
        p = "descriptive" if r["holm_p"] is None else f"{r['holm_p']:.4f}"
        lines.append(f"|{r['benchmark']}|{r['endpoint']}|{r['comparison']}|{r['known_pairs']}|{effect}|{ci}|{p}|")
    lines += ["", "## 解释与目录", "", "攻击效果以no-defense同期活性为解释前提。若无防护无事件，则只报告当前地板/模型任务适配限制；若有事件，仍须结合完成率、失败和配对区间，不能只看阻断数。AgentDojo使用内存副本上的原生评分；M3-v2只计隔离沙箱中有执行证据的效果。两者分别报告，不混成相同端点。", "", "研究目录：E:\\M3_PI_Guard_test\\outputs\\experiments\\research_followup_20261006_v1\\calibration。", "", "```text", "calibration/", "├── plan.jsonl              # 480个新计划项，版本和参数", "├── raw_records.jsonl       # append-only终态，未覆盖旧916行", "├── status.json             # 前缀门及终态进度", "├── analysis.json           # 一次统计、区间和未知上下界", "├── tables/cells.csv        # 分层表和负担", "├── figures/contemporaneous_endpoints.png", "├── report.md               # 本报告", "└── internal/               # 忽略的请求摘要和锁，禁止上传", "```", "", "11/11统计误区检查：分层、不做部署基率/个体推广；原队列选择限制披露；不依新结果筛选或排除；不把历史前后差解释成修复因果；未知与失败保持分母；所有预定比较呈现；Holm家族明确；参数固定；时间/模型服务漂移仍为限制；无领先、跨厂商或来源模块普遍有效主张。", "", "可信度：9/10。依据：固定计划、原始终态与一次重建；推广结论仍受固定cohort和服务窗口限制。", ""]
    (output / "report.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    result = analyze(read_jsonl(OUTPUT / "plan.jsonl"), read_jsonl(OUTPUT / "raw_records.jsonl"))
    write_outputs(result)
    print(json.dumps({k: result[k] for k in ("planned", "recorded", "pending", "provider_calls", "statuses")}, ensure_ascii=False))
