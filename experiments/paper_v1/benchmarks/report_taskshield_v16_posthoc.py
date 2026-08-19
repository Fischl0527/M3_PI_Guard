"""Build the post-hoc Task Shield v1.6 failure report and diagnostic figures.

This reporter is intentionally outside the v1.6 freeze.  It never modifies
P3/P4 outcomes and labels all derived material diagnostic/non-formal.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

from .common import portable_path, resolve_artifact_path, sha256_file


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_P3 = ROOT / "outputs" / "paper_upgrade_v1" / "baselines" / "taskshield_v16_preflight_4case"
DEFAULT_P4 = ROOT / "outputs" / "paper_upgrade_v1" / "baselines" / "taskshield_v16_qualification_12case"
DEFAULT_G2 = ROOT / "protocols" / "paper_upgrade_v1" / "execution" / "taskshield_v16_p3_preflight_v1" / "gate_g2.json"
DEFAULT_G3 = ROOT / "protocols" / "paper_upgrade_v1" / "execution" / "taskshield_v16_p4_expanded_v1" / "gate_g3.json"
DEFAULT_COMPARATOR = ROOT / "outputs" / "paper_upgrade_v1" / "baselines" / "agentdojo_tool_filter_official_formal_v1" / "outcomes.jsonl"
DEFAULT_OUTPUT = ROOT / "outputs" / "paper_upgrade_v1" / "analysis_v2" / "taskshield_v16_qualification"


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _percentile(values: Sequence[float], q: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _official_metric(row: Mapping[str, Any]) -> bool | None:
    if row.get("case_kind") != "security" or not row.get("official_trace_path"):
        return None
    path = resolve_artifact_path(str(row["official_trace_path"]), root=ROOT)
    if not path.is_file():
        return None
    value = _read_json(path).get("security")
    return value if isinstance(value, bool) else None


def _diagnostics(rows: Sequence[Mapping[str, Any]], comparator_rows: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    comparator = {str(row.get("benchmark_case_id", "")): row for row in comparator_rows}
    case_rows: list[dict[str, Any]] = []
    error_counts: Counter[str] = Counter()
    total_requests = 0
    invalid_requests = 0
    second_attempts = 0
    fail_closed = 0
    verifier_ms = 0.0
    total_tool_calls = 0
    denied_tool_calls = 0
    for row in rows:
        trace = row.get("taskshield_trace", {})
        requests = trace.get("model_requests", []) if isinstance(trace, Mapping) else []
        invalid = [request for request in requests if request.get("contract_valid") is False]
        for request in invalid:
            error_counts[str(request.get("error", "unknown"))] += 1
        request_ms = sum(float(request.get("duration_ms", 0.0) or 0.0) for request in requests)
        comp = comparator.get(str(row.get("benchmark_case_id", "")), {})
        comp_ms = float(comp.get("elapsed_ms", 0.0) or 0.0)
        case_ms = float(row.get("duration_ms", 0.0) or 0.0)
        total_requests += len(requests)
        invalid_requests += len(invalid)
        second_attempts += sum(request.get("request_attempt") == 2 for request in requests)
        fail_closed += sum(request.get("fail_closed") is True for request in requests)
        verifier_ms += request_ms
        tool_calls = trace.get("tool_calls", []) if isinstance(trace, Mapping) else []
        total_tool_calls += len(tool_calls)
        denied_tool_calls += int(trace.get("denied_tool_calls", 0) or 0) if isinstance(trace, Mapping) else 0
        case_rows.append(
            {
                "case_index": row.get("case_index"),
                "benchmark_case_id": row.get("benchmark_case_id"),
                "suite": row.get("suite"),
                "case_kind": row.get("case_kind"),
                "status": row.get("status"),
                "failure_class": row.get("failure_class", ""),
                "utility_success": row.get("utility_success"),
                "official_injection_success": _official_metric(row),
                "taskshield_duration_seconds": round(case_ms / 1000.0, 6),
                "comparator_duration_seconds": round(comp_ms / 1000.0, 6),
                "latency_ratio": round(case_ms / comp_ms, 6) if comp_ms else None,
                "verifier_requests": len(requests),
                "invalid_contract_attempts": len(invalid),
                "second_attempts": sum(request.get("request_attempt") == 2 for request in requests),
                "verifier_seconds": round(request_ms / 1000.0, 6),
                "tool_calls": len(tool_calls),
                "denied_tool_calls": int(trace.get("denied_tool_calls", 0) or 0) if isinstance(trace, Mapping) else 0,
                "trace_sha256": row.get("taskshield_trace_sha256", ""),
            }
        )
    durations = [float(row["taskshield_duration_seconds"]) for row in case_rows]
    comp_durations = [float(row["comparator_duration_seconds"]) for row in case_rows]
    metrics = {
        "verifier_requests": total_requests,
        "invalid_contract_attempts": invalid_requests,
        "second_attempts": second_attempts,
        "exhausted_fail_closed_rows": fail_closed,
        "invalid_contract_error_counts": dict(sorted(error_counts.items())),
        "verifier_seconds": round(verifier_ms / 1000.0, 6),
        "total_case_seconds": round(sum(durations), 6),
        "verifier_time_share_percent": round(100.0 * verifier_ms / (1000.0 * sum(durations)), 6),
        "tool_calls": total_tool_calls,
        "denied_tool_calls": denied_tool_calls,
        "taskshield_p50_seconds": round(statistics.median(durations), 6),
        "taskshield_p95_seconds": round(_percentile(durations, 0.95), 6),
        "taskshield_max_seconds": round(max(durations), 6),
        "comparator_p95_seconds": round(_percentile(comp_durations, 0.95), 6),
        "p95_latency_ratio": round(_percentile(durations, 0.95) / _percentile(comp_durations, 0.95), 6),
    }
    return case_rows, metrics


def _write_case_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    fieldnames = list(rows[0])
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _figures(output_dir: Path, cases: Sequence[Mapping[str, Any]], g3: Mapping[str, Any]) -> list[Path]:
    import matplotlib.pyplot as plt
    import numpy as np

    figure_dir = output_dir / "figures"
    figure_dir.mkdir(parents=True, exist_ok=True)
    labels = [f"{row['case_index']} {row['suite']}\n{row['case_kind']}" for row in cases]
    taskshield = [float(row["taskshield_duration_seconds"]) for row in cases]
    comparator = [float(row["comparator_duration_seconds"]) for row in cases]
    x = np.arange(len(cases))
    fig, ax = plt.subplots(figsize=(13, 5.8))
    ax.bar(x - 0.19, comparator, 0.38, label="Matched ToolFilter", color="#7aa6c2")
    colors = ["#c94c4c" if row["status"] == "failed" else "#e5a84b" for row in cases]
    ax.bar(x + 0.19, taskshield, 0.38, label="Task Shield v1.6", color=colors)
    ax.axhline(600, color="#7f1d1d", linestyle="--", linewidth=1.5, label="600 s cap")
    ax.set_xticks(x, labels, rotation=35, ha="right")
    ax.set_ylabel("Case latency (seconds)")
    ax.set_title("Task Shield v1.6 latency and timeout outcomes")
    ax.legend(ncol=3)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    latency_png = figure_dir / "case_latency_vs_comparator.png"
    latency_svg = figure_dir / "case_latency_vs_comparator.svg"
    fig.savefig(latency_png, dpi=180)
    fig.savefig(latency_svg)
    plt.close(fig)

    checks = list(g3["checks"])
    values = [1 if g3["checks"][name] else 0 for name in checks]
    fig, ax = plt.subplots(figsize=(10, 7.2))
    y = np.arange(len(checks))
    ax.barh(y, [1] * len(checks), color=["#3c9d78" if value else "#cf4f4f" for value in values])
    ax.set_yticks(y, [name.replace("_", " ") for name in checks])
    ax.set_xticks([])
    ax.set_xlim(0, 1.05)
    ax.invert_yaxis()
    ax.set_title(f"G3 checks: {g3['passed_checks']}/{g3['total_checks']} passed")
    for index, value in enumerate(values):
        ax.text(0.5, index, "PASS" if value else "FAIL", ha="center", va="center", color="white", fontweight="bold")
    fig.tight_layout()
    gate_png = figure_dir / "g3_gate_checks.png"
    gate_svg = figure_dir / "g3_gate_checks.svg"
    fig.savefig(gate_png, dpi=180)
    fig.savefig(gate_svg)
    plt.close(fig)

    invalid = [int(row["invalid_contract_attempts"]) for row in cases]
    requests = [int(row["verifier_requests"]) for row in cases]
    valid = [total - bad for total, bad in zip(requests, invalid, strict=True)]
    fig, ax = plt.subplots(figsize=(12, 5.6))
    ax.bar(x, valid, label="Valid/administrative request rows", color="#5b8db8")
    ax.bar(x, invalid, bottom=valid, label="Invalid contract attempts", color="#d4625d")
    ax.set_xticks(x, labels, rotation=35, ha="right")
    ax.set_ylabel("Verifier request rows")
    ax.set_title("Verifier call pressure and contract recovery")
    ax.legend()
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    contract_png = figure_dir / "verifier_contract_pressure.png"
    contract_svg = figure_dir / "verifier_contract_pressure.svg"
    fig.savefig(contract_png, dpi=180)
    fig.savefig(contract_svg)
    plt.close(fig)
    return [latency_png, latency_svg, gate_png, gate_svg, contract_png, contract_svg]


def build_report(
    *,
    p3_dir: Path = DEFAULT_P3,
    p4_dir: Path = DEFAULT_P4,
    g2_path: Path = DEFAULT_G2,
    g3_path: Path = DEFAULT_G3,
    comparator_path: Path = DEFAULT_COMPARATOR,
    output_dir: Path = DEFAULT_OUTPUT,
) -> dict[str, Any]:
    p3_manifest = _read_json(p3_dir / "run_manifest.json")
    p4_manifest = _read_json(p4_dir / "run_manifest.json")
    p4_rows = _read_jsonl(p4_dir / "outcomes.jsonl")
    comparator_rows = _read_jsonl(comparator_path)
    g2 = _read_json(g2_path)
    g3 = _read_json(g3_path)
    cases, runtime = _diagnostics(p4_rows, comparator_rows)
    utility = [row for row in p4_rows if row.get("case_kind") == "utility"]
    attack = [row for row in p4_rows if row.get("case_kind") == "security"]
    completed_attack = [row for row in attack if row.get("status") == "completed"]
    comparator_selected = [
        row
        for row in comparator_rows
        if row.get("benchmark_case_id") in {item.get("benchmark_case_id") for item in p4_rows}
    ]
    comparator_attack = [row for row in comparator_selected if row.get("case_kind") == "security"]
    summary = {
        "schema_version": "paper-taskshield-v16-posthoc-report-1.0",
        "status": "completed_negative_qualification_evidence",
        "result_eligible_for_formal_tables": False,
        "q2_readiness_score_change": 0,
        "p3": {
            "gate": g2.get("status"),
            "completed": p3_manifest["summary"]["completed_cases"],
            "failed": p3_manifest["summary"]["failed_cases"],
        },
        "p4": {
            "gate": g3.get("status"),
            "run_status": p4_manifest.get("status"),
            "terminal_cases": len(p4_rows),
            "completed_cases": sum(row.get("status") == "completed" for row in p4_rows),
            "failed_cases": sum(row.get("status") == "failed" for row in p4_rows),
            "failure_classes": dict(Counter(str(row.get("failure_class", "")) for row in p4_rows if row.get("status") == "failed")),
            "standalone_utility": f"{sum(row.get('utility_success') is True for row in utility)}/{len(utility)}",
            "attack_condition_utility": f"{sum(row.get('utility_success') is True for row in attack)}/{len(attack)}",
            "observed_attack_success_completed_only": f"{sum(row.get('attack_success') is True for row in completed_attack)}/{len(completed_attack)}",
            "unresolved_attack_operational_failures": sum(row.get("status") != "completed" for row in attack),
            "comparator_standalone_utility": f"{sum(row.get('utility_success') is True for row in comparator_selected if row.get('case_kind') == 'utility')}/6",
            "comparator_attack_condition_utility": f"{sum(row.get('utility_success') is True for row in comparator_attack)}/6",
            "comparator_raw_attack_success": f"{sum(_official_metric(row) is True for row in comparator_attack)}/6",
        },
        "runtime": runtime,
        "decision": {
            "p5_authorized": False,
            "p6_authorized": False,
            "taskshield_formal_route": "stop_and_preserve_as_negative_engineering_evidence",
            "next_strong_baseline_route": ["Progent", "CaMeL_or_equivalent_information_flow_baseline"],
            "reason": [
                "G3 failed 4 of 16 checks",
                "three of twelve cases reached the 600 second hard cap",
                "p95 latency was more than fifteen times the matched comparator",
                "attack-condition utility was zero of six",
                "the matched comparator already had zero raw injection success on the same six attack cases",
            ],
        },
        "material_passport": {
            "sources": [
                "P3/P4 immutable outcome rows and verifier traces",
                "G2/G3 machine-readable gate artifacts",
                "matched same-model ToolFilter outcomes and raw AgentDojo traces",
            ],
            "transformations": [
                "case-level join by benchmark_case_id",
                "latency percentiles without excluding failed rows",
                "raw official security read directly from official trace",
                "verifier request/error aggregation from terminal trace snapshots",
            ],
            "excluded_claims": [
                "no formal efficacy claim",
                "no claim that timeout equals attack prevention",
                "no Q2 readiness increase",
                "no P5/P6 authorization",
            ],
        },
        "fallacy_scan": {
            "failed_rows_excluded": False,
            "timeout_counted_as_attack_failure": False,
            "historical_complement_metric_reused": False,
            "qualification_called_blind": False,
            "low_asr_interpreted_without_utility": False,
            "single_p_value_used_as_decision": False,
        },
        "boundary": "Post-hoc diagnostic synthesis of sealed P3/P4 qualification. It is not formal, confirmatory, blind, or registry-eligible evidence.",
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_case_csv(output_dir / "case_diagnostics.csv", cases)
    figure_paths = _figures(output_dir, cases, g3)
    references = {
        name: {"path": portable_path(path, root=ROOT), "sha256": sha256_file(path)}
        for name, path in {
            "p3_manifest": p3_dir / "run_manifest.json",
            "p3_outcomes": p3_dir / "outcomes.jsonl",
            "g2": g2_path,
            "p4_manifest": p4_dir / "run_manifest.json",
            "p4_outcomes": p4_dir / "outcomes.jsonl",
            "g3": g3_path,
            "comparator": comparator_path,
        }.items()
    }
    summary["references"] = references
    summary["figures"] = [portable_path(path, root=ROOT) for path in figure_paths]
    _write_json(output_dir / "summary.json", summary)
    lines = [
        "# Task Shield v1.6 资格实验最终分析",
        "",
        "## 结论",
        "",
        "P3 的 4 案例正确性预检通过，但 P4 的 12 案例扩大资格未通过 G3。Task Shield v1.6 不具备进入 P5/P6 或论文正式主表的资格，应作为负面工程证据封存，并把强基线资源转向 Progent 与 CaMeL/同类信息流基线。",
        "",
        "## 关键结果",
        "",
        f"- P3：`{summary['p3']['completed']}/4 completed`，G2 `{summary['p3']['gate']}`。",
        f"- P4：`{summary['p4']['completed_cases']}/12 completed`，`{summary['p4']['failed_cases']}` 个 timeout，G3 `{summary['p4']['gate']}`（`{g3['passed_checks']}/{g3['total_checks']}`）。",
        f"- Standalone utility：`{summary['p4']['standalone_utility']}`，只刚好达到门槛；attack-condition utility：`{summary['p4']['attack_condition_utility']}`。",
        f"- 已完成攻击案例上的 raw attack success：`{summary['p4']['observed_attack_success_completed_only']}`；另有 `{summary['p4']['unresolved_attack_operational_failures']}` 条攻击案例因超时不可判定，不能计作防御成功。",
        f"- Matched comparator：standalone utility `{summary['p4']['comparator_standalone_utility']}`、attack-condition utility `{summary['p4']['comparator_attack_condition_utility']}`、raw attack success `{summary['p4']['comparator_raw_attack_success']}`。因此 Task Shield 没有显示安全增益，反而损失 attack-condition utility。",
        f"- Task Shield p50/p95/max：`{runtime['taskshield_p50_seconds']}/{runtime['taskshield_p95_seconds']}/{runtime['taskshield_max_seconds']}` 秒；matched comparator p95 `{runtime['comparator_p95_seconds']}` 秒，倍率 `{runtime['p95_latency_ratio']}×`。",
        f"- Verifier 共 `{runtime['verifier_requests']}` 次 request rows，其中 `{runtime['invalid_contract_attempts']}` 次完整契约不合格并进入第 2 次逻辑尝试；未发生 exhausted fail-closed 拒绝。Verifier 时间占总 case 时间约 `{runtime['verifier_time_share_percent']}%`。",
        "",
        "## 失败原因",
        "",
        "1. **系统性延迟，而非单次崩溃。** Slack utility、Workspace utility 和 Workspace attack 均达到 600 秒上限；另一个 Slack attack 也耗时 455 秒。服务、GPU 与 runner 在运行期间保持活跃。",
        "2. **评分输出契约不稳定，显著放大成本。** 主要错误为 invalid JSON、cardinality 少行、非数值 score 和 transport timeout。v1.6 的恢复机制成功避免了 silent parse failure，但 29 次第二尝试带来了真实时间成本。",
        "3. **安全结果与可用性不可分离。** 六条 attack-condition utility 全部失败；一条攻击案例本身超时。观察到的低攻击成功率不能作为有效防御结论。",
        "4. **同一选择上没有安全优势。** Matched ToolFilter 的六条 raw injection success 也是 0/6；Task Shield 没有改善安全点估计，却增加了 15.17 倍 p95 延迟并降低 attack-condition utility。",
        "",
        "## 可行方案",
        "",
        "- **论文主线：停止 Task Shield formal 路线。** 保留 v1.3–v1.6 为透明 negative reproduction，不提高 Q2 readiness，不运行 P5/P6。",
        "- **资源转移：优先实现 Progent，并并行准备 CaMeL/同类信息流基线。** 这两类方法与 M3 的授权/来源追踪机制更直接可比，也不要求用同一个 8B 模型进行大量自然语言评分。",
        "- **若单独研究 Task Shield 优化：另立新方法标签。** 可尝试专用小 verifier、grammar-constrained decoding、一次性批量评分、trusted-task extraction 缓存和 request budget；这些会改变 reproduction 条件，必须新建 freeze 和 fresh root，不能叫 v1.6 修复或重跑。",
        "- **正式结论仍需公共基准、独立 blind 与前沿 API。** 本批次只回答 Task Shield 在当前 8GB 本地环境和该 8B 模型上的资格问题。",
        "",
        "## 图表",
        "",
        "- `figures/case_latency_vs_comparator.png`：逐案例 Task Shield 与 comparator 延迟，红色为 timeout。",
        "- `figures/g3_gate_checks.png`：G3 16 项门禁的通过/失败状态。",
        "- `figures/verifier_contract_pressure.png`：每案例 verifier request 与不合格契约尝试。",
        "",
        "## 证据边界",
        "",
        str(summary["boundary"]),
        "",
    ]
    (output_dir / "analysis.md").write_text("\n".join(lines), encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--p3-dir", type=Path, default=DEFAULT_P3)
    parser.add_argument("--p4-dir", type=Path, default=DEFAULT_P4)
    parser.add_argument("--g2", type=Path, default=DEFAULT_G2)
    parser.add_argument("--g3", type=Path, default=DEFAULT_G3)
    parser.add_argument("--comparator", type=Path, default=DEFAULT_COMPARATOR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_report(
        p3_dir=args.p3_dir.resolve(),
        p4_dir=args.p4_dir.resolve(),
        g2_path=args.g2.resolve(),
        g3_path=args.g3.resolve(),
        comparator_path=args.comparator.resolve(),
        output_dir=args.output_dir.resolve(),
    )
    print(json.dumps({"status": result["status"], "p5_authorized": result["decision"]["p5_authorized"], "output": portable_path(args.output_dir / "analysis.md", root=ROOT)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
