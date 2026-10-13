"""从最终实验证据构建规范的便携式报告工件（artifact.json）。

HTML 页面本身由便携式工件构建器生成，本脚本负责准备有明确边界、
完全基于源证据支撑的报告负载数据（Payload），杜绝幻觉与外部推断。
"""

from __future__ import annotations

import csv
import json
import os
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "outputs" / "experiments" / "final_analysis"
E17_REVIEW = ROOT / "outputs" / "experiments" / "E17_human_stratified_360_v1" / "review"
DEFAULT_OUTPUT = ANALYSIS / "report" / "artifact.json"


class HtmlReportArtifactError(RuntimeError):
    """当最终实验证据缺失或内部逻辑不一致时抛出的运行时异常。"""


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise HtmlReportArtifactError(f"expected JSON object: {path}")
    return value


def _csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _number(value: Any) -> float | None:
    if value in (None, "", "NA", "null"):
        return None
    return float(value)


def _integer(value: Any) -> int | None:
    number = _number(value)
    return None if number is None else int(number)


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _source(source_id: str, label: str, path: str, description: str) -> dict[str, Any]:
    reader = "read_csv_auto" if path.casefold().endswith(".csv") else "read_json_auto"
    return {
        "id": source_id,
        "label": label,
        "path": path,
        "query": {
            "engine": "duckdb",
            "language": "sql",
            "sql": f"SELECT * FROM {reader}('{path}')",
            "description": description,
            "filters": ["hash-verified final evidence only", "Stub and smoke excluded from formal effect claims"],
            "tables_used": [path],
        },
    }


def build_artifact(output: str | Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    output_path = Path(output).resolve()
    manifest = _json(ANALYSIS / "manifest.json")
    executive = _json(ANALYSIS / "executive_summary.json")
    statistical_validation = _json(ANALYSIS / "statistical_validation.json")
    e17_statistics = _json(E17_REVIEW / "statistics.json")
    agreement = _json(E17_REVIEW / "reviewer_agreement.json")
    acceptance = _csv(ANALYSIS / "acceptance_matrix.csv")
    main_rows = _csv(ANALYSIS / "main_defense_effect.csv")
    weighted_rows = _csv(E17_REVIEW / "weighted_population_estimates.csv")

    if manifest.get("status") != "completed" or manifest.get("acceptance_status") != "fail":
        raise HtmlReportArtifactError("final analysis identity or acceptance state drifted")
    if statistical_validation.get("verification_status", {}).get("label") != "PASS":
        raise HtmlReportArtifactError("independent statistical validation is not PASS")
    if agreement.get("agreements") != 360 or agreement.get("disagreements") != 0:
        raise HtmlReportArtifactError("E17 reviewer agreement is not 360/360")

    by_id = {row["target_id"]: row for row in acceptance}
    required_targets = {f"A{index:02d}" for index in range(12)}
    if set(by_id) != required_targets:
        raise HtmlReportArtifactError("acceptance matrix does not contain exactly A00-A11")

    summary = {
        "scope": "final",
        "asr_reduction": _number(by_id["A01"]["estimate"]),
        "precision": _number(by_id["A03"]["estimate"]),
        "recall": _number(by_id["A04"]["estimate"]),
        "benign_fpr": _number(by_id["A05"]["estimate"]),
        "legal_tool_tcr": _number(by_id["A07"]["estimate"]),
        "parse_success": _number(by_id["A11"]["estimate"]),
        "targets_passed": sum(row["status"] == "pass" for row in acceptance),
        "targets_total": len(acceptance),
        "human_review_agreement": float(agreement["percent_agreement"]),
    }

    short_panels = {
        "Security · ASR": "Attack success rate",
        "Security · DSR": "Data-spill rate",
        "Security · malicious-call Recall": "Malicious-call recall",
        "Utility · overall TCR": "Overall benign TCR",
        "Utility · legitimate-tool TCR": "Legal-tool TCR",
        "Utility · benign call FPR": "Benign call FPR",
        "Utility · benign ASK rate": "Benign ASK rate",
    }
    main_dataset = [
        {
            "metric": short_panels.get(row["panel"], row["panel"]),
            "condition": "Guard off" if row["series"] == "regular_none" else "Full Guard",
            "value": _number(row["value"]),
            "numerator": _integer(row["numerator"]),
            "denominator": _integer(row["denominator"]),
            "source_experiment": row["source_experiment"],
        }
        for row in main_rows
        if row.get("value_status") == "observed"
        and row["panel"]
        in {
            "Security · ASR",
            "Security · malicious-call Recall",
            "Utility · overall TCR",
            "Utility · legitimate-tool TCR",
        }
    ]
    weighted_dataset = [
        {
            "failure_class": row["failure_class"].replace("_", " "),
            "weighted_share": _number(row["weighted_share"]),
            "ci_low": _number(row["ci_low"]),
            "ci_high": _number(row["ci_high"]),
            "representative_sample_n": _integer(row["representative_sample_n"]),
            "bootstrap_iterations": _integer(row["bootstrap_iterations"]),
        }
        for row in weighted_rows
    ]
    status_dataset = [
        {"status": status, "count": count}
        for status, count in sorted(Counter(row["status"] for row in acceptance).items())
    ]

    def display(row: Mapping[str, str]) -> str:
        value = _number(row.get("estimate"))
        if value is None:
            return "NA"
        if row.get("unit") == "ms":
            return f"{value:.3f} ms"
        if row.get("unit") == "boolean":
            return "met" if value == 1 else "not met"
        return f"{100.0 * value:.1f}%"

    acceptance_dataset = [
        {
            "target_id": row["target_id"],
            "criterion": row["criterion"],
            "status": row["status"],
            "estimate": display(row),
            "counts": (
                "—"
                if row.get("numerator", "") == "" or row.get("denominator", "") == ""
                else f"{row['numerator']}/{row['denominator']}"
            ),
            "threshold": row["comparator"],
            "uncertainty": row["uncertainty_assessment"],
            "source": row["source_experiments"],
        }
        for row in acceptance
    ]
    failed_dataset = [row for row in acceptance_dataset if row["status"] == "fail"]

    generated_at = str(manifest.get("completed_at") or manifest.get("created_at"))
    source_specs = [
        _source(
            "acceptance_matrix",
            "Final acceptance matrix",
            "outputs/experiments/final_analysis/acceptance_matrix.csv",
            "A00-A11 point estimates, denominators, thresholds, intervals, and acceptance states.",
        ),
        _source(
            "main_defense",
            "Main defense and utility chart data",
            "outputs/experiments/final_analysis/main_defense_effect.csv",
            "Hash-verified E1/E12 Guard-off and Full-Guard security and benign-utility rates.",
        ),
        _source(
            "e17_weighted",
            "E17 weighted human-audit estimates",
            "outputs/experiments/E17_human_stratified_360_v1/review/weighted_population_estimates.csv",
            "Hajek design-weighted class shares using only the 300 representative rows and 10,000 stratified bootstrap repetitions.",
        ),
        _source(
            "e17_statistics",
            "E17 sampled human-review statistics",
            "outputs/experiments/E17_human_stratified_360_v1/review/statistics.json",
            "Two-reviewer agreement, sampling groups, weighting rule, confidence, and scope guardrails.",
        ),
        _source(
            "statistical_validation",
            "Independent final statistical validation",
            "outputs/experiments/final_analysis/statistical_validation.json",
            "Independent recomputation of artifact integrity, denominators, inference contracts, and statistical-fallacy checks.",
        ),
        _source(
            "registry",
            "E0-E17 experiment registry",
            "experiments/registry.json",
            "Active primary manifests, evidence paths, completion status, E11 scope amendment, and E17 sampling contract.",
        ),
    ]

    title = "M3_PI_Guard 最终实验技术报告"
    report = {
        "surface": "report",
        "manifest": {
            "version": 1,
            "surface": "report",
            "title": title,
            "description": "E0-E17 全量实验、E17 双人分层抽样盲审、验收结果与统计边界。",
            "generatedAt": generated_at,
            "cards": [
                {"id": "asr", "description": "同提示条件下 Full Guard 相对无 Guard 的总体 ASR 降幅。", "dataset": "summary", "sourceId": "acceptance_matrix", "metrics": [{"label": "ASR relative reduction", "field": "asr_reduction", "format": "percent"}]},
                {"id": "precision", "description": "Full Guard 下恶意调用检测精确率。", "dataset": "summary", "sourceId": "acceptance_matrix", "metrics": [{"label": "Malicious-call precision", "field": "precision", "format": "percent"}]},
                {"id": "recall", "description": "Full Guard 下恶意调用检测召回率；低于 90% 目标。", "dataset": "summary", "sourceId": "acceptance_matrix", "metrics": [{"label": "Malicious-call recall", "field": "recall", "format": "percent"}]},
                {"id": "fpr", "description": "正常任务调用级误拦率。", "dataset": "summary", "sourceId": "acceptance_matrix", "metrics": [{"label": "Benign call FPR", "field": "benign_fpr", "format": "percent"}]},
                {"id": "legal_tcr", "description": "需要合法工具的正常任务完成率；低于 90% 目标。", "dataset": "summary", "sourceId": "acceptance_matrix", "metrics": [{"label": "Legal-tool TCR", "field": "legal_tool_tcr", "format": "percent"}]},
                {"id": "targets", "description": "12 项预设验收条件中的通过数。", "dataset": "summary", "sourceId": "acceptance_matrix", "metrics": [{"label": "Targets passed (of 12)", "field": "targets_passed", "format": "number"}]},
            ],
            "charts": [
                {
                    "id": "acceptance_status",
                    "title": "Acceptance target status",
                    "subtitle": "Eight targets passed and four failed; no target was unevaluable.",
                    "intent": "composition",
                    "type": "pie",
                    "dataset": "acceptance_status",
                    "sourceId": "acceptance_matrix",
                    "encodings": {
                        "x": {"field": "status", "type": "nominal", "label": "Status"},
                        "y": {"field": "count", "type": "quantitative", "label": "Targets"},
                        "tooltip": [{"field": "count", "type": "quantitative", "label": "Targets"}],
                    },
                },
                {
                    "id": "main_rates",
                    "title": "Guard-off and Full-Guard security and utility rates",
                    "subtitle": "Attack success collapses under Full Guard, while benign and legal-tool completion remain the main cost.",
                    "intent": "comparison",
                    "type": "bar",
                    "dataset": "main_rates",
                    "sourceId": "main_defense",
                    "valueFormat": "percent",
                    "encodings": {
                        "x": {"field": "metric", "type": "nominal", "label": "Metric"},
                        "y": {"field": "value", "type": "quantitative", "label": "Rate", "format": "percent"},
                        "color": {"field": "condition", "type": "nominal", "label": "Condition"},
                        "tooltip": [
                            {"field": "numerator", "type": "quantitative", "label": "Numerator"},
                            {"field": "denominator", "type": "quantitative", "label": "Denominator"},
                            {"field": "source_experiment", "type": "nominal", "label": "Experiment"},
                        ],
                    },
                    "surface": {"legend": {"position": "bottom", "title": "Condition"}, "labels": {"values": "endpoints"}},
                },
                {
                    "id": "e17_weighted_classes",
                    "title": "Design-weighted E17 primary-class estimates",
                    "subtitle": "Leak and none are the two largest estimated classes; intervals come from stratified bootstrap.",
                    "intent": "comparison",
                    "type": "pie",
                    "dataset": "e17_weighted",
                    "sourceId": "e17_weighted",
                    "valueFormat": "percent",
                    "encodings": {
                        "x": {"field": "failure_class", "type": "nominal", "label": "Primary class"},
                        "y": {"field": "weighted_share", "type": "quantitative", "label": "Estimated share", "format": "percent"},
                        "tooltip": [
                            {"field": "ci_low", "type": "quantitative", "label": "95% CI low", "format": "percent"},
                            {"field": "ci_high", "type": "quantitative", "label": "95% CI high", "format": "percent"},
                            {"field": "representative_sample_n", "type": "quantitative", "label": "Representative n"},
                        ],
                    },
                    "surface": {"labels": {"values": "all"}},
                },
            ],
            "tables": [
                {
                    "id": "failed_targets",
                    "title": "Four unmet acceptance targets",
                    "subtitle": "These are result failures, not evidence-pipeline failures.",
                    "dataset": "failed_targets",
                    "sourceId": "acceptance_matrix",
                    "defaultSort": {"field": "target_id", "direction": "asc"},
                    "density": "dense",
                    "columns": [
                        {"field": "target_id", "label": "ID", "type": "text"},
                        {"field": "criterion", "label": "Criterion", "type": "text"},
                        {"field": "estimate", "label": "Observed", "type": "text"},
                        {"field": "threshold", "label": "Target", "type": "text"},
                        {"field": "source", "label": "Source", "type": "text"},
                    ],
                },
                {
                    "id": "acceptance_detail",
                    "title": "Complete A00-A11 acceptance matrix",
                    "subtitle": "Exact status, k/n, threshold, uncertainty assessment, and source experiment.",
                    "dataset": "acceptance",
                    "sourceId": "acceptance_matrix",
                    "defaultSort": {"field": "target_id", "direction": "asc"},
                    "density": "dense",
                    "columns": [
                        {"field": "target_id", "label": "ID", "type": "text"},
                        {"field": "criterion", "label": "Criterion", "type": "text"},
                        {"field": "status", "label": "Status", "type": "text"},
                        {"field": "estimate", "label": "Observed", "type": "text"},
                        {"field": "counts", "label": "k/n", "type": "text"},
                        {"field": "threshold", "label": "Target", "type": "text"},
                    ],
                },
                {
                    "id": "e17_estimates",
                    "title": "E17 weighted class estimates and bootstrap intervals",
                    "subtitle": "Only the 300 representative rows enter these population estimates.",
                    "dataset": "e17_weighted",
                    "sourceId": "e17_weighted",
                    "defaultSort": {"field": "weighted_share", "direction": "desc"},
                    "density": "dense",
                    "columns": [
                        {"field": "failure_class", "label": "Class", "type": "text"},
                        {"field": "weighted_share", "label": "Estimate", "format": "percent"},
                        {"field": "ci_low", "label": "95% CI low", "format": "percent"},
                        {"field": "ci_high", "label": "95% CI high", "format": "percent"},
                        {"field": "representative_sample_n", "label": "n", "format": "number"},
                    ],
                },
            ],
            "sources": [{"id": source["id"], "label": source["label"], "path": source["path"]} for source in source_specs],
            "blocks": [
                {"id": "title", "type": "markdown", "body": f"# {title}\n\nE0-E17 最终证据、真人抽样审计与工程验收的可追溯综合。"},
                {"id": "technical_summary", "type": "markdown", "sourceId": "acceptance_matrix", "body": "## Full Guard 的攻击抑制显著，但总体工程验收仍未通过\n\n12 项预设目标中 8 项通过、4 项失败。Full Guard 使总体 ASR 相对下降 99.2%，恶意调用 Precision 为 99.2%，但 Recall 仅 86.5%。主要短板是恶意调用漏检、正常任务完成率下降 6.8 个百分点、合法工具 TCR 仅 65.5%，以及最差 E14 cell 的端到端延迟开销 92.4%。"},
                {"id": "headline_metrics", "type": "metric-strip", "cardIds": ["asr", "precision", "recall", "fpr", "legal_tcr", "targets"]},
                {"id": "status_heading", "type": "markdown", "sourceId": "acceptance_matrix", "body": "## 证据链通过独立复核，但四项产品目标明确未达标\n\n统计验证与 Dashboard 哈希门禁均通过；`fail` 表示实验结果低于阈值，不表示数据缺失或流程失败。"},
                {"id": "status_chart", "type": "chart", "chartId": "acceptance_status", "layout": "half"},
                {"id": "main_heading", "type": "markdown", "sourceId": "main_defense", "body": "## 安全收益集中而明确，可用性代价仍需要专项修复\n\n相同提示下，Full Guard 将 ASR 从 382/756 降到 3/756，并把 DSR 从 10/432 降到 0/432；与此同时，总体 benign TCR 从 190/324 降到 168/324，合法工具 TCR 从 120/168 降到 110/168。"},
                {"id": "main_chart", "type": "chart", "chartId": "main_rates"},
                {"id": "failed_heading", "type": "markdown", "sourceId": "acceptance_matrix", "body": "## 失败项指向三类优先修复：漏检、合法工具可用性与端到端开销\n\n四项失败均保留原始分母与来源实验；修复后应完整复跑受影响条件，不能只补单个有利案例。"},
                {"id": "failed_table", "type": "table", "tableId": "failed_targets"},
                {"id": "e17_heading", "type": "markdown", "sourceId": "e17_statistics", "body": "## 两名真人对 360 行盲审结果完全一致，但结论严格限定为分层抽样审计\n\n两名不同 reviewer_id 的评审者完成同一冻结样本，主标签与次级代码集合 360/360 一致，Cohen's κ=1.000，无需第三人裁决。只有 300 行代表性层进入总体加权估计；40 行自动分歧定向样本和 20 行稀有/复杂定向样本只作诊断。不得声称 3,299 行候选均经真人评审。"},
                {"id": "e17_chart", "type": "chart", "chartId": "e17_weighted_classes"},
                {"id": "e17_table", "type": "table", "tableId": "e17_estimates"},
                {"id": "scope_heading", "type": "markdown", "body": "## 设计与统计边界保证结论可复核，而不是把所有分母混在一起\n\n主矩阵、E13 校准、E14 性能、E16 自适应红队、E17 人工审计和 E11 post-hoc 补充使用各自独立分母。比例报告 k/n 与 Wilson 95% 区间；配对二元结果使用 McNemar，差值使用按案例聚类的 10,000 次 bootstrap，延迟使用 Wilcoxon 与效应量，多重比较使用 Holm 校正。E0、Stub 与 smoke 仅作诊断或回归，不进入正式效果结论。"},
                {"id": "limitations_heading", "type": "markdown", "sourceId": "statistical_validation", "body": "## 结论可靠但并不等同于所有目标达成\n\n独立统计复核结果为 PASS，说明输入账本、图表、分母、阈值与统计契约可重验。仍需注意：DSR 观测为 0 时 Wilson 上界非零；E9 有 14/120 unresolved；E14 性能只代表当前硬件与运行时；E17 加权区间受 300 行代表性样本与分层权重影响。"},
                {"id": "matrix_heading", "type": "markdown", "sourceId": "acceptance_matrix", "body": "## 完整验收矩阵\n\n下表是 A00-A11 的最终权威摘要，保留阈值、不确定性判断和来源。"},
                {"id": "matrix_table", "type": "table", "tableId": "acceptance_detail"},
                {"id": "next_steps", "type": "markdown", "body": "## 下一轮应优先修复 Recall、合法工具 TCR 与延迟开销\n\n1. 将 E17 的 leak、parse_failure、false_block、ASK 和 max_steps 样本按 Guard reason code 与攻击链回放聚类。\n2. 对 E11 `memory_to_file` 等低召回链路增加状态传播和跨工具授权回归。\n3. 分离解析失败与安全判定，提升 run-level 无解析失败率。\n4. 优化合法工具的 ASK/授权流程，并复跑完整 E12 与受影响主矩阵。\n5. 对 E14 最差 context×concurrency cell 做 profiler 定位，修复后完整复测。"},
                {"id": "questions", "type": "markdown", "body": "## 仍需回答的问题\n\n- 漏检是否集中于特定模型、攻击族、语言或跨工具链？\n- 合法工具 TCR 的损失主要来自 ASK、DENY、解析失败还是任务规划？\n- E17 加权结果在扩大代表性样本后是否稳定？\n- 在不同 GPU、Ollama 版本与量化标签下，性能目标能否复现？"},
            ],
        },
        "snapshot": {
            "version": 1,
            "generatedAt": generated_at,
            "status": "ready",
            "datasets": {
                "summary": [summary],
                "acceptance_status": status_dataset,
                "main_rates": main_dataset,
                "failed_targets": failed_dataset,
                "acceptance": acceptance_dataset,
                "e17_weighted": weighted_dataset,
            },
        },
        "sources": source_specs,
        "package_info": {
            "root": "outputs/experiments/final_analysis/report",
            "manifestPath": "artifact.json",
            "snapshotPath": "artifact.json",
        },
    }
    _atomic_json(output_path, report)
    return {"artifact": report, "output": str(output_path)}


def main() -> int:
    result = build_artifact()
    print(json.dumps({"status": "completed", "output": result["output"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
