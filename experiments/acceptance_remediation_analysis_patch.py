"""针对 Remediation V2 的冻结后报告字段透明适配补丁。

在不篡改底层实验原始记录的前提下，安全映射分析报告字段以对齐最新评估规范。
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import experiments.acceptance_remediation as frozen
import m3_eval.evidence_dashboard as evidence_dashboard


def adapt_legal_result(value: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(value)
    if "estimate" not in result:
        result["estimate"] = result["value"]
    return result


def normalize_figure_manifest_anchor(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """添加仪表盘的构件类型鉴别器，且不改变论据证据内容。"""
    result = dict(manifest)
    records: list[Any] = []
    for value in result.get("artifacts", []):
        if not isinstance(value, Mapping):
            records.append(value)
            continue
        record = dict(value)
        if record.get("path") == "figure_manifest.json":
            record["kind"] = "figure_manifest"
        records.append(record)
    result["artifacts"] = records
    return result


def repair_chart_presentation() -> dict[str, Any]:
    """重新渲染两张原始数据标签未通过视觉质量验收（QA）的图表。"""
    import matplotlib.pyplot as plt

    output = frozen.OUTPUT

    performance_rows: list[dict[str, str]] = []
    with (output / "performance_overhead_data.csv").open(encoding="utf-8-sig", newline="") as handle:
        performance_rows.extend(csv.DictReader(handle))
    fig, ax = plt.subplots(figsize=(12, 6.5))
    for concurrency, color in ((1, "#2563eb"), (2, "#f97316"), (4, "#16a34a")):
        selected = [row for row in performance_rows if int(row["offered_concurrency"]) == concurrency]
        x = [int(row["target_prompt_tokens"]) for row in selected]
        y = [float(row["median_paired_overhead"]) * 100.0 for row in selected]
        ax.plot(x, y, marker="o", linewidth=2.2, color=color, label=f"concurrency={concurrency}")
    worst_percent = max(float(row["median_paired_overhead"]) * 100.0 for row in performance_rows)
    gate_multiple = 10.0 / worst_percent
    ax.text(
        0.99,
        0.97,
        f"Acceptance gate: 10% (off scale)\nWorst observed: {worst_percent:.4f}% ({gate_multiple:,.0f}x below gate)",
        transform=ax.transAxes,
        ha="right",
        va="top",
        bbox={"boxstyle": "round,pad=0.45", "facecolor": "#ecfdf5", "edgecolor": "#16a34a"},
    )
    ax.set_title("Same-output counterfactual Guard overhead")
    ax.set_xlabel("Target prompt tokens")
    ax.set_ylabel("Median paired overhead (%)")
    ax.set_xticks([2048, 4096, 8192, 16384], ["2K", "4K", "8K", "16K"])
    ax.set_ylim(bottom=0)
    ax.grid(axis="y", alpha=0.25)
    ax.legend(loc="upper right", bbox_to_anchor=(1.0, 0.77))
    fig.tight_layout()
    fig.savefig(output / "performance_overhead.png", dpi=180)
    fig.savefig(output / "performance_overhead.svg")
    plt.close(fig)

    recovery_rows: list[dict[str, str]] = []
    with (output / "recovery_profile_data.csv").open(encoding="utf-8-sig", newline="") as handle:
        recovery_rows.extend(csv.DictReader(handle))
    labels = [row["recovery_type"] for row in recovery_rows]
    values = [int(row["case_runs"]) for row in recovery_rows]
    total = sum(values)
    colors = ["#2563eb", "#f97316", "#16a34a", "#dc2626", "#8b5cf6", "#a855f7", "#64748b"]
    fig, ax = plt.subplots(figsize=(12, 7))
    wedges, _, _ = ax.pie(
        values,
        labels=None,
        colors=colors,
        startangle=90,
        counterclock=False,
        autopct=lambda pct: f"{pct:.1f}%" if pct >= 2.0 else "",
        pctdistance=0.72,
        wedgeprops={"width": 0.52, "edgecolor": "white"},
        textprops={"fontsize": 11},
    )
    legend_labels = [
        f"{label}: {value:,} ({value / total * 100:.1f}%)"
        for label, value in zip(labels, values)
    ]
    ax.legend(
        wedges,
        legend_labels,
        title="Recovery type",
        loc="center left",
        bbox_to_anchor=(1.0, 0.5),
        frameon=False,
    )
    ax.text(0, 0, f"Full Guard\n{total:,} case-runs", ha="center", va="center", fontsize=13)
    ax.set_title("Full-Guard case-runs by recovery profile")
    ax.axis("equal")
    fig.tight_layout()
    fig.savefig(output / "recovery_profile.png", dpi=180, bbox_inches="tight")
    fig.savefig(output / "recovery_profile.svg", bbox_inches="tight")
    plt.close(fig)

    figure_manifest_path = output / "figure_manifest.json"
    figure_manifest = frozen.read_json(figure_manifest_path)
    repaired_ids = {"performance_overhead", "recovery_profile"}
    for figure in figure_manifest.get("figures", []):
        if figure.get("id") not in repaired_ids:
            continue
        for kind in ("png", "svg"):
            path = output / figure["files"][kind]["path"]
            figure["files"][kind] = {
                "path": path.name,
                "bytes": path.stat().st_size,
                "sha256": frozen.sha256_file(path),
            }
        warnings = list(figure.get("warnings", []))
        warnings.append("Rendering was repaired post-freeze for legibility; source CSV values are unchanged.")
        figure["warnings"] = warnings
    frozen.write_json(figure_manifest_path, figure_manifest)
    return figure_manifest


def run() -> dict[str, Any]:
    frozen.verify_freeze()
    original = frozen._legal_tool_result
    original_dashboard_loader = evidence_dashboard.load_dashboard_sources

    def adapted(metrics: Mapping[str, Any], cases: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        return adapt_legal_result(original(metrics, cases))

    frozen._legal_tool_result = adapted

    def adapted_dashboard_loader(*args: Any, **kwargs: Any) -> dict[str, Any]:
        manifest_path = frozen.OUTPUT / "manifest.json"
        manifest = normalize_figure_manifest_anchor(frozen.read_json(manifest_path))
        frozen.write_json(manifest_path, manifest)
        return original_dashboard_loader(*args, **kwargs)

    evidence_dashboard.load_dashboard_sources = adapted_dashboard_loader
    result = frozen.analyze()
    repair_chart_presentation()

    patch_path = Path(__file__).resolve()
    patch_manifest_path = frozen.OUTPUT / "analysis_patch_manifest.json"
    patch_manifest = {
        "schema_version": "1.0",
        "protocol_id": frozen.protocol()["protocol_id"],
        "patch_scope": "report_layer_adapter_and_visual_repair_only",
        "frozen_analyzer": frozen.relative(Path(frozen.__file__).resolve()),
        "frozen_analyzer_sha256": frozen.sha256_file(Path(frozen.__file__).resolve()),
        "patch_source": frozen.relative(patch_path),
        "patch_source_sha256": frozen.sha256_file(patch_path),
        "original_errors": [
            "KeyError: estimate",
            "main manifest must declare exactly one figure_manifest artifact; found 0"
        ],
        "mappings": [
            "proportion_result.value -> report alias estimate",
            "figure_manifest.json artifact -> add kind=figure_manifest",
            "performance and recovery charts -> legible re-render from unchanged CSV data"
        ],
        "unchanged": [
            "formal RunLogs",
            "case set and tuple audit",
            "metric implementation",
            "thresholds",
            "numerator and denominator",
            "Wilson interval",
            "pass/fail comparator",
            "chart source CSV values",
            "dashboard validation implementation"
        ]
    }
    frozen.write_json(patch_manifest_path, patch_manifest)

    analysis_path = frozen.OUTPUT / "analysis.md"
    marker = "## Post-freeze analysis adapter"
    analysis = analysis_path.read_text(encoding="utf-8")
    if marker not in analysis:
        analysis += (
            "\n## Post-freeze analysis adapter\n\n"
            "冻结分析器在序列化 A07 时把统计 API 的 `value` 字段误写为 "
            "`estimate`，导致 tuple 审计通过后报告生成中止。`analysis_patch_manifest.json` "
            "记录了最小字段别名适配；原始 RunLog、指标函数、阈值、分子分母、Wilson "
            "区间和 pass/fail 比较均未变化。主清单还为已有 `figure_manifest.json` "
            "记录补充了 Dashboard 要求的 `kind=figure_manifest` 类型字段；该字段适配"
            "不改变图表证据或 Dashboard 校验实现。性能折线图和恢复类型饼图"
            "另从完全相同的 CSV 数据重新渲染，以解决数值贴近零轴和小类别标签重叠；"
            "此操作只改变视觉呈现，更新后的图表哈希已写回 `figure_manifest.json`。\n"
        )
        analysis_path.write_text(analysis, encoding="utf-8")

    manifest_path = frozen.OUTPUT / "manifest.json"
    manifest = frozen.read_json(manifest_path)
    records = [dict(item) for item in manifest.get("artifacts", [])]
    for path in (analysis_path, patch_manifest_path, frozen.OUTPUT / "figure_manifest.json"):
        record = {
            "path": path.name,
            "bytes": path.stat().st_size,
            "sha256": frozen.sha256_file(path),
        }
        if path.name == "figure_manifest.json":
            record["kind"] = "figure_manifest"
        for index, existing in enumerate(records):
            if existing.get("path") == path.name:
                records[index] = record
                break
        else:
            records.append(record)
    manifest["artifacts"] = records
    manifest["analysis_patch"] = patch_manifest
    frozen.write_json(manifest_path, manifest)

    dashboard = original_dashboard_loader(bundle_paths=[frozen.OUTPUT])
    validation = {
        "status": "pass" if dashboard["metrics"] and dashboard["logs"] and not dashboard["warnings"] else "fail",
        "metric_rows": len(dashboard["metrics"]),
        "log_rows": len(dashboard["logs"]),
        "manifest_rows": len(dashboard["manifests"]),
        "figure_rows": len(dashboard["figures"]),
        "warnings": dashboard["warnings"],
    }
    frozen.write_json(frozen.OUTPUT / "dashboard_validation.json", validation)
    if validation["status"] != "pass":
        raise ValueError(f"post-repair dashboard validation failed: {validation}")
    return manifest


def main() -> int:
    print(json.dumps(run(), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
