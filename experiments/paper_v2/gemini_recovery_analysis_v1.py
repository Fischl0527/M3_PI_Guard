"""Separate Gemini recovery generations without rewriting the original study."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from experiments.paper_v2.correctness_analysis_v1 import (
    CONDITIONS, CONDITION_LABELS, GROUP_FIELDS, _burden, _csv, _endpoint,
    _figures, _pct, analyze, read_jsonl,
)


PROFILE = "gemini_recovery_v1"
DEFAULT_OLD_ROOT = Path(__file__).resolve().parents[2] / "outputs/experiments/correctness_repair_v1"
DEFAULT_OUTPUT = DEFAULT_OLD_ROOT / PROFILE


def _http_statuses(row: Mapping[str, Any]) -> list[int]:
    return [int(request["http_status"]) for request in row.get("provider_requests", []) if request.get("http_status") is not None]


def _eligible_kind(row: Mapping[str, Any]) -> str:
    if row.get("response_obtained") is True:
        return "original_response"
    if row.get("operational_status") == "not_run" and row.get("attempt") == 0:
        return "not_run"
    requests = row.get("provider_requests") or []
    if row.get("attempt") == 1 and requests and all(
        request.get("http_status") == 503 and request.get("response_received") is not True
        for request in requests
    ):
        return "pure_503"
    raise ValueError("original work item is neither response-bearing, not_run, nor pure 503")


def _diagnostic_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    actions = Counter(str(row.get("action_kind")) for row in rows)
    pairs = {(row.get("action_kind"), row.get("repetition")) for row in rows}
    identity_ok = all(
        row.get("generation_profile_id") == PROFILE and row.get("max_tokens") == 2048
        and row.get("reasoning_effort") == "low"
        for row in rows
    )
    return {
        "n_planned": 6, "n_recorded": len(rows),
        "n_passed": sum(row.get("passed") is True for row in rows),
        "all_six_passed": (
            len(rows) == len(pairs) == 6
            and len({row.get("diagnostic_id") for row in rows}) == 6
            and actions == {"read_file": 2, "write_file": 2, "final": 2}
            and identity_ok and all(row.get("passed") is True for row in rows)
        ),
        "action_counts": dict(actions), "profile_identity_valid": identity_ok,
        "failure_class_counts": dict(Counter(str(row["failure_class"]) for row in rows if row.get("failure_class"))),
        "provider_calls": sum(len(row.get("provider_requests") or []) for row in rows),
        "http_status_counts": dict(Counter(str(status) for row in rows for status in _http_statuses(row))),
        "interpretation": "diagnostic schema probes only; excluded from scientific task denominators",
    }


def analyze_recovery(
    plan: Sequence[Mapping[str, Any]],
    old_rows: Sequence[Mapping[str, Any]],
    recovery_rows: Sequence[Mapping[str, Any]],
    diagnostics: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Analyze the 512-token original and 2048-token recovery separately."""
    plan = [row for row in plan if row["model_group"] == "gemini_flash"]
    plan_by_key = {str(row["work_key"]): row for row in plan}
    old_by_key = {str(row["work_key"]): row for row in old_rows}
    if len(plan_by_key) != len(plan) or len(old_by_key) != len(old_rows):
        raise ValueError("duplicate work key in original plan or original records")
    if set(plan_by_key) != set(old_by_key):
        raise ValueError("original records must cover exactly the original Gemini plan")
    for key, row in old_by_key.items():
        for field in (*GROUP_FIELDS, "case_id", "underlying_task_id", "model_id"):
            if row.get(field) != plan_by_key[key].get(field):
                raise ValueError(f"original raw/plan identity mismatch: {field}")
    original = [row for row in old_rows if row.get("response_obtained") is True]
    kinds = {str(row["work_key"]): _eligible_kind(row) for row in old_rows}
    eligible = [row for row in plan if kinds[str(row["work_key"])] != "original_response"]
    eligible_by_key = {str(row["work_key"]): row for row in eligible}
    for row in recovery_rows:
        key = str(row["work_key"])
        if key not in eligible_by_key:
            raise ValueError("recovery cannot rerun an original response-bearing or foreign work key")
        expected_attempt = 2 if kinds[key] == "pure_503" else 1
        if row.get("attempt") != expected_attempt:
            raise ValueError("recovery attempt does not match original execution history")
        for field, expected in {
            "generation_profile_id": PROFILE, "max_tokens": 2048, "reasoning_effort": "low",
            "prior_operational_status": old_by_key[key]["operational_status"],
            "model_id": eligible_by_key[key]["model_id"],
            "underlying_task_id": eligible_by_key[key]["underlying_task_id"],
        }.items():
            if row.get(field) != expected:
                raise ValueError(f"recovery identity mismatch: {field}")
        if not isinstance(row.get("recovery_batch_id"), str) or not row["recovery_batch_id"].strip():
            raise ValueError("recovery_batch_id is required")
    analysis = analyze(eligible, recovery_rows)
    new_by_key = {str(row["work_key"]): row for row in recovery_rows}
    by_task: dict[tuple[str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for item in plan:
        by_task[(str(item["benchmark"]), str(item["evaluation_case_type"]), str(item["underlying_task_id"]))].append(item)
    complete = [
        items for items in by_task.values()
        if {row["condition_id"] for row in items} == set(CONDITIONS)
        and all(str(row["work_key"]) in new_by_key for row in items)
        and all(
            new_by_key[str(row["work_key"])].get("response_obtained") is True
            and _endpoint(
                new_by_key[str(row["work_key"])],
                "unsafe_effect" if row["evaluation_case_type"] == "attack" else "task_completion",
            ) is not None
            for row in items
        )
    ]
    paired_plan = [item for task in complete for item in task]
    paired_rows = [new_by_key[str(item["work_key"])] for item in paired_plan]
    paired = analyze(paired_plan, paired_rows)["paired_comparisons"] if paired_plan else []
    analysis["paired_comparisons"] = paired
    analysis["method"]["pairing"] = "recovery profile only; all six conditions response-bearing and task-type endpoint observed"
    original_response_keys = {str(row["work_key"]) for row in original}
    original_plan = [item for item in plan if str(item["work_key"]) in original_response_keys]
    original_analysis = analyze(original_plan, original)
    original_analysis["paired_comparisons"] = []
    original_failures = [row for row in old_rows if kinds[str(row["work_key"])] == "pure_503"]
    return {
        "schema_version": "m3-gemini-recovery-analysis-1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "evidence_level": "development_only_not_confirmatory",
        "cross_provider_formal_claim": False,
        "diagnostics": _diagnostic_summary(diagnostics),
        "original_512": {
            "max_tokens": 512, "response_bearing": len(original),
            "status_counts": dict(Counter(str(row["operational_status"]) for row in original)),
            "n_original_plan": len(plan),
            "all_original_status_counts": dict(Counter(str(row["operational_status"]) for row in old_rows)),
            "response_only_analysis": original_analysis,
            "response_bearing_resources": _burden(original),
            "response_bearing_http_status_counts": dict(Counter(str(status) for row in original for status in _http_statuses(row))),
            "pure_503_resources": _burden(original_failures),
            "pure_503_http_status_counts": dict(Counter(str(status) for row in original_failures for status in _http_statuses(row))),
        },
        "recovery_2048": {
            "generation_profile_id": PROFILE, "max_tokens": 2048, "reasoning_effort": "low",
            "n_eligible_plan": len(eligible),
            "eligible_from_pure_503": sum(value == "pure_503" for value in kinds.values()),
            "eligible_from_not_run": sum(value == "not_run" for value in kinds.values()),
            "response_bearing": sum(row.get("response_obtained") is True for row in recovery_rows),
            "n_recorded_attempts": len(recovery_rows),
            "not_yet_recorded": len(eligible) - len(recovery_rows),
            "http_status_counts": dict(Counter(str(status) for row in recovery_rows for status in _http_statuses(row))),
            "failure_class_counts": dict(Counter(str(row["failure_class"]) for row in recovery_rows if row.get("failure_class"))),
            "recovery_batch_ids": sorted({str(row["recovery_batch_id"]) for row in recovery_rows}),
            "analysis": analysis,
        },
        "pairing": {
            "complete_six_condition_tasks": len(complete),
            "excluded_incomplete_tasks": len(by_task) - len(complete),
            "rule": "all six conditions response-bearing with the task-type endpoint observed in recovery profile only",
        },
        "paired_comparisons": paired,
        "recovery_attempts": [
            {
                "work_key": key, "case_id": item["case_id"],
                "prior_operational_status": old_by_key[key]["operational_status"],
                "original_attempt": old_by_key[key]["attempt"],
                "original_http_statuses": _http_statuses(old_by_key[key]),
                "recovery_attempt": new_by_key.get(key, {}).get("attempt"),
                "recovery_operational_status": new_by_key.get(key, {}).get("operational_status", "not_run"),
                "recovery_http_statuses": _http_statuses(new_by_key.get(key, {})),
            }
            for key, item in eligible_by_key.items()
        ],
    }


def _endpoint_table(analysis: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            **{field: group[field] for field in GROUP_FIELDS}, "endpoint": endpoint,
            "endpoint_semantics": group["endpoint_semantics"], **values,
            **{field: group[field] for field in ("response_bearing", "operational_failure", "administrative_or_not_run")},
        }
        for group in analysis["groups"] for endpoint, values in group["endpoints"].items()
    ]


def _endpoint_report_lines(analysis: Mapping[str, Any]) -> list[str]:
    lines = [
        "|基准|任务类型|条件|事件/观测/计划|观测率与 Wilson 95%区间|缺失保守范围|运行失败|未执行|",
        "|---|---|---|---|---|---|---:|---:|",
    ]
    for group in analysis["groups"]:
        value = group["endpoints"]["unsafe_effect" if group["evaluation_case_type"] == "attack" else "task_completion"]
        lines.append(
            f"|{group['benchmark']}|{group['evaluation_case_type']}|{CONDITION_LABELS.get(group['condition_id'], group['condition_id'])}"
            f"|{value['x']}/{value['n_observed']}/{value['n_plan']}"
            f"|{_pct(value['rate_observed'])} [{_pct(value['wilson_ci_low'])}, {_pct(value['wilson_ci_high'])}]"
            f"|[{_pct(value['planned_lower_bound'])}, {_pct(value['planned_upper_bound'])}]"
            f"|{group['operational_failure']}|{group['administrative_or_not_run']}|"
        )
    if not analysis["groups"]:
        lines.append("|无符合条件的记录|—|—|0/0/0|NA|NA|0|0|")
    return lines


def report_markdown(result: Mapping[str, Any], figures: Sequence[str]) -> str:
    original, recovery = result["original_512"], result["recovery_2048"]
    diagnostic, status = result["diagnostics"], result["run_status"]
    analysis = recovery["analysis"]
    burden = _burden([]) if not analysis["models"] else analysis["models"][0]["burden_all_attempts"]
    lines = [
        "# Gemini 恢复试跑：分配置分析报告", "",
        f"生成时间：{result['generated_at']}。本报告只读取原批 Gemini 记录和本次恢复记录，不修改原结果或论文。", "",
        "## 一、执行到哪里", "",
        f"运行器登记状态：`{status.get('state', 'unknown')}`；原因：`{status.get('stop_reason') or '未登记'}`；状态记录时间：`{status.get('recorded_at', '未登记')}`。",
        "该状态来自 run_status.json，不是根据失败数量猜测。状态文件若缺失则为未知，不能自动宣布完成或暂停。", "",
        f"原 Gemini 计划 {original['n_original_plan']} 项；其中 {original['response_bearing']} 项已获得模型响应，保留原 512 输出 token 配置。"
        f"本轮可恢复 {recovery['n_eligible_plan']} 项：原未运行 {recovery['eligible_from_not_run']} 项，原无响应 HTTP 503 {recovery['eligible_from_pure_503']} 项。", "",
        f"新配置：`{PROFILE}`，最大输出 2048 token（模型计量文本单位），reasoning_effort=low（低推理预算）。"
        f"本轮记录 {recovery['n_recorded_attempts']} 次尝试，{recovery['response_bearing']} 项有模型响应，{recovery['not_yet_recorded']} 项尚无恢复记录。", "",
        "这是开发验证，不是新的正式跨厂商主实验。旧 512 与新 2048 配置不同，不拼成单一同配置矩阵、不用旧五项填补新条件，也不把恢复前后差异直接归因于修复或防御有效。", "",
        "## 二、诊断和旧 HTTP 503 单独记账", "",
        f"格式诊断：记录 {diagnostic['n_recorded']}/6，通过 {diagnostic['n_passed']}，六项全部通过：`{diagnostic['all_six_passed']}`。"
        f"诊断调用 {diagnostic['provider_calls']} 次，HTTP 状态：`{json.dumps(diagnostic['http_status_counts'], ensure_ascii=False)}`。",
        f"诊断失败类别：`{json.dumps(diagnostic['failure_class_counts'], ensure_ascii=False)}`。诊断测试读取动作、写入动作和最终回答的结构，每类两次；不是实验任务，不进入效果分母。", "",
        (
            "六项格式诊断已通过；这仅支持协议可运行，不证明任何安全或效用提升。"
            if diagnostic["all_six_passed"] else
            "六项格式诊断尚未全部通过；2048/low 参数组合尚未通过完整在线验证。若因无响应服务错误停下，不能据此断言参数修复成功或失败；尚未调用的诊断及实验项均非模型结果。"
        ), "",
        f"原有响应部分：{original['response_bearing_resources']['provider_calls']} 次调用，HTTP 状态 `{json.dumps(original['response_bearing_http_status_counts'])}`；"
        f"原纯 503 部分：{original['pure_503_resources']['provider_calls']} 次调用，HTTP 状态 `{json.dumps(original['pure_503_http_status_counts'])}`；"
        f"恢复部分：{burden['provider_calls']} 次调用，HTTP 状态 `{json.dumps(recovery['http_status_counts'])}`。三者与诊断不混计。", "",
        "HTTP 503 表示该次服务不可用，不等于防御失败或模型回答；原失败记录仍存在。原未运行项的新尝试编号是 1，原纯 503 项的新尝试编号是 2；旧已响应行不可再运行。逐项历史见 tables/recovery_attempts.csv。", "",
        "## 三、旧 512 配置：仅已响应子集", "",
        f"原响应状态：`{json.dumps(original['status_counts'], ensure_ascii=False)}`。本节分母仅为原已响应项，不声称代表原全部计划。原计划整体状态另保存在 analysis.json。", "",
        *_endpoint_report_lines(original["response_only_analysis"]), "",
        "## 四、新 2048 配置：保留全部可恢复计划分母", "",
        "下表每格为事件数/已观测端点数/计划项数。NA 是未知、不是零；Wilson 区间仅适用于已观测子集。缺失保守范围把未知分别计为无事件和有事件，不能消除非随机缺失偏差。攻击任务报告安全端点，良性工具及无工具任务报告完成端点。", "",
        *_endpoint_report_lines(analysis), "",
        "AgentDojo 的端点为原生安全检查器判定，可能检查调用、输出及状态；M3-v2 的端点是成功模拟动作与离线危险标签的匹配，不把两者混成统一实际损害率。运行失败与有响应可能重叠，例如解析失败。安全或失败的悲观合并端点、越权提案、错误放行、隔离拒绝和模拟效果分别见 recovery_endpoints.csv。", "",
    ]
    for path in figures:
        lines += [f"![新配置开发结果]({path})", ""]
    lines += [
        "## 五、同配置配对对照", "",
        f"新配置六条件齐全、全部有响应且任务对应端点均可观测的底层任务：{result['pairing']['complete_six_condition_tasks']}；"
        f"因旧配置排除、未执行或端点缺失而不能组成完整同配置任务：{result['pairing']['excluded_incomplete_tasks']}。", "",
        "四项比较：普通提示下完整模块−规则模块、安全提示下完整模块−规则模块、规则模块下安全提示−普通提示、完整模块下安全提示−普通提示。全部按同基准、同任务类型、同底层任务配对；报告 Newcombe 配对区间，不做新增正式显著性检验。完整观测子集可能有选择偏差，不代替全计划结果。", "",
        "|基准|任务类型|比较|完整配对任务|差值|95%区间|", "|---|---|---|---:|---|---|",
    ]
    for row in result["paired_comparisons"]:
        lines.append(f"|{row['benchmark']}|{row['evaluation_case_type']}|{row['comparison']}|{row['n_pairs_observed']}|{_pct(row.get('estimate'))}|[{_pct(row['ci_low'])}, {_pct(row['ci_high'])}]|")
    if not result["paired_comparisons"]:
        lines += ["|没有完整新配置任务|—|—|0|NA|NA|"]
    lines += [
        "", "## 六、调用、费用与解释边界", "",
        f"恢复记录 token：`{json.dumps(burden['token_usage'])}`；已记录费用（按币种、不换算）：`{json.dumps(burden['cost_by_currency'])}`；"
        f"费用数据完整：`{burden['cost_usage_complete']}`。未记录金额不是零；免费层 USD 0 以执行配置及收据声明为准，此分析器不核验账户 Billing。",
        f"ASK（请求确认）{burden['ask_count']}，DENY（拒绝）{burden['deny_count']}；延迟 p50/p95（50%/95%分位）毫秒：{burden['latency_p50_ms']}/{burden['latency_p95_ms']}。所有恢复尝试计入资源，不丢弃失败调用。", "",
    ]
    for model in analysis["models"]:
        observed = model["dataflow_observability"]
        lines += [
            f"数据来源检查快照：{observed['work_items_with_dataflow_summary']} 个工作项、{observed['dataflow_event_count']} 个事件；"
            f"分类及标签计数器（逐工作项已保存最大值求和）：`{json.dumps(observed['sum_per_work_item_max_observed_counters'])}`；"
            f"检查状态：`{json.dumps(observed['dataflow_status_event_counts'])}`。", "",
        ]
    lines += [
        "classified 是返回内容已分类，labelled 是记录到带标签的值；计数不同，且快照可能不含最后一次返回。无标签或无摘要不等于检查通过，不能声称来源传播已全覆盖或端到端安全已被证明。越权标签只覆盖固定离线合法/危险效果，未覆盖动作仍为未知。", "",
        "无真实邮件、支付、浏览器、代码执行或生产副作用。本报告不增加真实部署、跨厂商泛化或机制领先主张。旧 DeepSeek Flash 已变为 V4.1 服务身份的边界也不由这次 Gemini 恢复消除。", "",
        "## 七、outputs 目录如何阅读", "", "```text", "outputs/experiments/",
        "├── correctness_repair_v1/           # 原开发批，以下旧文件只读",
        "│   ├── plan.jsonl                  # 原三模型计划，本次仅筛 Gemini",
        "│   ├── gemini_flash/raw_records.jsonl # 原 512 响应、纯 503、not_run",
        "│   ├── analysis.json               # 原分析，不由本程序改写",
        "│   ├── report.md                   # 原报告，不由本程序改写",
        "│   └── gemini_recovery_v1/         # 本次恢复，独立子目录",
        "│       ├── raw_records.jsonl       # 仅可恢复项的新尝试，不含原响应行",
        "│       ├── diagnostics.jsonl       # 六项格式诊断，不计任务分母",
        "│       ├── run_status.json         # 运行器的暂停/结束状态与未执行清单",
        "│       ├── analysis.json           # 分配置端点、分母、恢复历史",
        "│       ├── tables/",
        "│       │   ├── original_512_response_endpoints.csv # 原响应子集单列",
        "│       │   ├── recovery_endpoints.csv  # 新配置全计划分母与未知范围",
        "│       │   ├── paired_differences.csv  # 完整六条件任务配对比较",
        "│       │   └── recovery_attempts.csv   # 原 503 与追加尝试、未执行项",
        "│       ├── figures/               # 最多两张新配置图，不运行模型",
        "│       ├── report.md              # 本文",
        "│       └── internal/              # 运行器内部收据/锁；Git 忽略",
        "└── 其他历史实验目录/               # E1–E8/Public/Adaptive 不在重算范围",
        "```", "",
        "JSONL 为逐行记录，JSON 为结构化汇总，CSV 可用表格软件打开。先读本报告，再按 work_key（工作项标识）对照 recovery_attempts.csv 与两份原始记录。不要按目录修改日期把不同配置混并。", "",
    ]
    return "\n".join(lines)


def write_analysis(
    old_root: Path = DEFAULT_OLD_ROOT, output: Path = DEFAULT_OUTPUT, *, figures: bool = True,
) -> dict[str, Any]:
    """Read original Gemini once and write only the independent recovery folder."""
    old_root, output = Path(old_root).resolve(), Path(output).resolve()
    if (
        output == old_root or output in old_root.parents
        or (old_root in output.parents and output != old_root / PROFILE)
    ):
        raise ValueError("analysis output cannot overwrite original files; only its designated recovery subdirectory is allowed")
    plan = read_jsonl(old_root / "plan.jsonl")
    if not plan:
        raise ValueError("original development plan is missing or empty")
    result = analyze_recovery(
        plan, read_jsonl(old_root / "gemini_flash/raw_records.jsonl"),
        read_jsonl(output / "raw_records.jsonl"), read_jsonl(output / "diagnostics.jsonl"),
    )
    status_path = output / "run_status.json"
    status = json.loads(status_path.read_text(encoding="utf-8")) if status_path.exists() else {"state": "unknown"}
    # Only runner metadata, never arbitrary extension payloads, goes into public analysis.
    result["run_status"] = {
        field: status[field] for field in (
            "state", "stop_reason", "profile", "planned_recovery", "attempt_records",
            "touched_work_keys", "pending_work_keys", "recorded_at",
        ) if field in status
    }
    output.mkdir(parents=True, exist_ok=True)
    _csv(output / "tables/original_512_response_endpoints.csv", _endpoint_table(result["original_512"]["response_only_analysis"]))
    _csv(output / "tables/recovery_endpoints.csv", _endpoint_table(result["recovery_2048"]["analysis"]))
    _csv(output / "tables/paired_differences.csv", result["paired_comparisons"])
    _csv(output / "tables/recovery_attempts.csv", result["recovery_attempts"])
    figure_paths = _figures(result["recovery_2048"]["analysis"], output / "figures") if figures else []
    result["figures"] = figure_paths
    (output / "analysis.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    (output / "report.md").write_text(report_markdown(result, figure_paths), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old-root", type=Path, default=DEFAULT_OLD_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--no-figures", action="store_true")
    args = parser.parse_args()
    result = write_analysis(args.old_root, args.output, figures=not args.no_figures)
    print(json.dumps({
        "state": result["run_status"].get("state"),
        "recovery_attempts": result["recovery_2048"]["n_recorded_attempts"],
        "report": str(args.output / "report.md"),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
