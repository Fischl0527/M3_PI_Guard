"""Single-pass public-event diagnosis; never inspect model bodies or labels."""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict

from experiments.paper_v2.correctness_plan_v1 import ROOT, read_jsonl

SOURCE = ROOT / "outputs/experiments/claude_revision_v1/deepseek_pro_raw.jsonl"
OUTPUT = ROOT / "outputs/experiments/research_followup_20261006_v1/diagnosis"


def classify(row):
    events = row.get("events", [])
    blocking = next((e for e in events if e.get("parse_ok") is False
                     or e.get("guard_decision") in {"ASK", "DENY"}
                     or e.get("isolation_rejected") is True
                     or e.get("execution_attempted") is True and e.get("execution_succeeded") is False), None)
    category = "no_observed_block"
    if blocking:
        reason = blocking.get("reason_code", "")
        constraints = blocking.get("violated_constraints", [])
        if blocking.get("parse_ok") is False:
            category = "invalid_model_proposal"
        elif blocking.get("isolation_rejected") is True:
            category = "isolated_boundary_rejection"
        elif reason == "permission_expansion":
            category = "missing_tool_permission" if "tool_outside_current_permission" in constraints else "missing_argument_permission"
        elif reason.startswith("oracle_exact_gold"):
            category = "exact_target_or_sequence_restriction"
        elif blocking.get("guard_decision") in {"ASK", "DENY"}:
            category = "source_order_dataflow_or_confirmation_restriction"
        else:
            category = "execution_failed_or_rejected"
    executed = sum(e.get("simulated_action_executed") is True for e in events)
    completed = row.get("task_completion")
    if completed is True:
        final = "observed_task_completed"
    elif completed is None:
        final = "completion_unknown"
    elif executed:
        final = "executed_actions_but_task_not_completed"
    elif blocking:
        final = "blocked_without_observed_execution"
    else:
        final = "no_completion_cause_in_public_events"
    requests = row.get("provider_requests", [])
    return {
        **{k: row.get(k) for k in ("work_key", "case_id", "benchmark", "evaluation_case_type", "condition_id", "authorization_regime", "operational_status", "task_completion", "task_completion_observed")},
        "first_block_category": category,
        "first_block_step": blocking.get("step") if blocking else None,
        "first_block_tool": blocking.get("tool") if blocking else None,
        "first_block_reason": blocking.get("reason_code") if blocking else None,
        "first_block_constraints": json.dumps(blocking.get("violated_constraints", []) if blocking else [], ensure_ascii=False),
        "final_completion_category": final,
        "observed_execution_count": executed,
        "parse_failures": sum(e.get("parse_ok") is False for e in events),
        "length_finish_count": sum(r.get("finish_reason") == "length" for r in requests),
        "failure_after_observed_completion": completed is True and row.get("operational_status") != "completed",
        "dynamic_target_cause": "unknown_not_inferable_from_redacted_events",
    }


def diagnose(rows):
    if len({r["work_key"] for r in rows}) != len(rows):
        raise ValueError("duplicate public work key")
    all_diagnoses = [classify(r) for r in rows]
    main_benign = [r for r in all_diagnoses if r["evaluation_case_type"] == "benign_tool"
                   and r["authorization_regime"] in {"auto_compiled", "exact_target_v2"}]
    abnormal = [r for r in all_diagnoses if r["operational_status"] != "completed"]
    selected_keys = {r["work_key"] for r in main_benign + abnormal}
    selected = [r for r in all_diagnoses if r["work_key"] in selected_keys]
    groups = defaultdict(list)
    for row in main_benign:
        groups[(row["benchmark"], row["authorization_regime"], row["condition_id"])].append(row)
    cells = []
    for (benchmark, regime, condition), group in sorted(groups.items()):
        cells.append({"benchmark": benchmark, "regime": regime, "condition": condition, "rows": len(group),
                      "completed_tasks": sum(r["task_completion"] is True for r in group),
                      "first_blocks": dict(Counter(r["first_block_category"] for r in group)),
                      "final_states": dict(Counter(r["final_completion_category"] for r in group))})
    summary = {"source_rows": len(rows), "main_benign_rows": len(main_benign), "abnormal_rows": len(abnormal),
               "diagnostic_rows": len(selected), "cells": cells,
               "abnormal_statuses": dict(Counter(r["operational_status"] for r in abnormal)),
               "length_truncated_rows": sum(r["length_finish_count"] > 0 for r in all_diagnoses),
               "completion_before_failure_rows": sum(r["failure_after_observed_completion"] for r in all_diagnoses),
               "scope": "public events only; no retrospective causal repair claim; no API or historical statistics replay"}
    return selected, summary


def write_outputs(selected, summary, output=OUTPUT):
    output.mkdir(parents=True, exist_ok=True)
    with (output / "task_diagnosis.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, list(selected[0]))
        writer.writeheader()
        writer.writerows(selected)
    (output / "analysis.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# P0 公开事件诊断", "", "## 实际范围", "",
             f"只读一次当前900行：主良性{summary['main_benign_rows']}行，非正常结束{summary['abnormal_rows']}行；重叠去重后{summary['diagnostic_rows']}行任务解释表。未读内部请求正文或模型响应。", "",
             "首次阻断与最终完成独立记录。缺权限只说明运行许可不足，不说明编译器必须生成该许可；动态目标原因在脱敏事件中不可识别，保留未知。执行过动作但未完成仅表示原生/模拟评分不通过，不认定评分器错误。", "",
             "|基准|授权|条件|完成/行数|首次阻断分类|", "|---|---|---|---:|---|"]
    for cell in summary["cells"]:
        lines.append(f"|{cell['benchmark']}|{cell['regime']}|{cell['condition']}|{cell['completed_tasks']}/{cell['rows']}|{json.dumps(cell['first_blocks'], ensure_ascii=False)}|")
    lines += ["", "## 运行问题与修复边界", "",
              f"非正常状态：`{summary['abnormal_statuses']}`；已观察完成后仍发生运行失败{summary['completion_before_failure_rows']}行，两者同时保留。请求finish_reason=length的行数{summary['length_truncated_rows']}；未截断的解析错误不能归因于输出预算。", "",
              "本诊断没有发现足以单凭公开事件确定的实现违约，因此不自动扩权、不改历史corrected_v2或512输出限制。下一步使用独立的新同期无防护对照判断攻击活性和模型/任务能力。", "",
              "输出：task_diagnosis.csv（逐行原因）、analysis.json（分组摘要）、report.md（本说明）。本文件夹不是新模型实验结果。", "",
              "可信度：9/10。依据：公开事件直接分类；隐藏参数和动态目标根因仍未知。", ""]
    (output / "report.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    selected, summary = diagnose(read_jsonl(SOURCE))
    if summary["source_rows"] != 900 or summary["main_benign_rows"] != 240 or summary["abnormal_rows"] != 105:
        raise ValueError("current study shape differs; do not silently change diagnosis population")
    write_outputs(selected, summary)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
