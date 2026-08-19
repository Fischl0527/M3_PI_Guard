"""Analyze a completed paper-v1 matrix and build diagnostic tables/figures."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from m3_eval.paper_metrics import summarize_paper_runs

from .benchmarks.common import portable_path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET = ROOT / "m3_attacks" / "cases" / "paper_v1" / "m3_v2_validation.jsonl"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                value = json.loads(line)
                if isinstance(value, dict):
                    rows.append(value)
    return rows


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _metric(metrics: Mapping[str, Any], name: str) -> tuple[int, int, float | None]:
    value = metrics[name]
    return int(value["numerator"]), int(value["denominator"]), value["value"]


def _percentage(value: float | None) -> str:
    return "NA" if value is None else f"{100 * value:.1f}%"


def _write_csv(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    materialized = list(rows)
    if not materialized:
        raise ValueError("cannot write an empty summary")
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(materialized[0]))
        writer.writeheader()
        writer.writerows(materialized)


def _build_effect_chart(rows: list[dict[str, Any]], output: Path, subtitle: str) -> None:
    import matplotlib.pyplot as plt
    import numpy as np

    models = list(dict.fromkeys(str(row["model"]) for row in rows))
    conditions = list(dict.fromkeys(str(row["defense_id"]) for row in rows))
    lookup = {(row["model"], row["defense_id"]): row for row in rows}
    colors = {"no_defense": "#D55E00", "m3_full": "#007C83"}
    metrics = (
        ("attack_unauthorized_side_effect_rate", "Unauthorized side effects on attacks", "Lower is safer"),
        ("normal_task_completion_rate", "Normal task completion", "Higher is better"),
        ("parse_success_rate", "Tool-call parse success", "Higher is better"),
    )
    x = np.arange(len(models))
    width = min(0.34, 0.78 / max(1, len(conditions)))
    fig, axes = plt.subplots(1, 3, figsize=(16, 5.7), sharey=True)
    for axis, (field, title, direction) in zip(axes, metrics):
        for index, condition in enumerate(conditions):
            values = [lookup[(model, condition)][field] for model in models]
            positions = x + (index - (len(conditions) - 1) / 2) * width
            bars = axis.bar(
                positions,
                values,
                width=width,
                label=condition,
                color=colors.get(condition, "#6C7A89"),
                alpha=0.92,
            )
            for bar, value in zip(bars, values):
                inside = value >= 0.15
                rotate_label = value >= 0.9 and len(conditions) > 1
                axis.text(
                    bar.get_x() + bar.get_width() / 2,
                    value - (0.055 if rotate_label else 0.035) if inside else value + 0.02,
                    f"{value:.0%}",
                    ha="center",
                    va="top" if inside else "bottom",
                    fontsize=7.5,
                    color="white" if inside else "#222222",
                    weight="bold" if inside else "normal",
                    rotation=90 if rotate_label else 0,
                )
        axis.set_title(title, fontsize=11, weight="bold", pad=10)
        axis.text(0.5, 1.01, direction, transform=axis.transAxes, ha="center", fontsize=8, color="#555555")
        axis.set_xticks(x)
        axis.set_xticklabels([model.replace(":", "\n") for model in models], fontsize=8)
        axis.set_ylim(0, 1.13)
        axis.grid(axis="y", alpha=0.22)
        axis.spines[["top", "right"]].set_visible(False)
    axes[0].set_ylabel("Rate")
    handles, labels = axes[-1].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=len(labels), frameon=False, bbox_to_anchor=(0.5, 0.96))
    fig.suptitle("M3 paper-v1 local-model smoke gate", fontsize=15, weight="bold", y=1.04)
    fig.text(0.5, 0.965, subtitle, ha="center", fontsize=9, color="#444444")
    fig.text(
        0.5,
        0.015,
        "DIAGNOSTIC SMOKE — not formal paper evidence",
        ha="center",
        fontsize=10,
        color="#A33A2B",
        weight="bold",
    )
    fig.tight_layout(rect=(0.02, 0.06, 0.98, 0.90))
    fig.savefig(output.with_suffix(".png"), dpi=220, bbox_inches="tight", facecolor="white")
    fig.savefig(output.with_suffix(".svg"), bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _build_status_chart(
    results: list[dict[str, Any]], output: Path, subtitle: str
) -> None:
    import matplotlib.pyplot as plt
    import numpy as np

    groups = list(
        dict.fromkeys((str(row["model"]), str(row["defense_id"])) for row in results)
    )
    counts: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    for row in results:
        counts[(str(row["model"]), str(row["defense_id"]))][str(row["final_status"])] += 1
    statuses = ["completed", "max_steps_reached", "timeout", "error"]
    colors = {
        "completed": "#2A9D8F",
        "max_steps_reached": "#E9C46A",
        "timeout": "#F4A261",
        "error": "#E76F51",
    }
    labels = [f"{model} | {condition}" for model, condition in groups]
    y = np.arange(len(groups))
    left = np.zeros(len(groups))
    fig, axis = plt.subplots(figsize=(11.5, 6.8))
    for status in statuses:
        values = np.array([counts[group][status] for group in groups])
        axis.barh(y, values, left=left, label=status, color=colors[status], height=0.68)
        for index, value in enumerate(values):
            if value:
                axis.text(left[index] + value / 2, index, str(value), ha="center", va="center", fontsize=8)
        left += values
    axis.set_yticks(y)
    axis.set_yticklabels(labels, fontsize=8)
    axis.invert_yaxis()
    axis.set_xlabel("Case runs")
    axis.set_title("Completion outcomes by model and defense", fontsize=14, weight="bold", pad=28)
    axis.text(0.5, 1.015, subtitle, transform=axis.transAxes, ha="center", fontsize=9, color="#444444")
    axis.legend(loc="upper center", bbox_to_anchor=(0.5, -0.10), ncol=4, frameon=False)
    axis.grid(axis="x", alpha=0.2)
    axis.spines[["top", "right"]].set_visible(False)
    fig.text(0.5, 0.01, "DIAGNOSTIC SMOKE — not formal paper evidence", ha="center", fontsize=10, color="#A33A2B", weight="bold")
    fig.tight_layout(rect=(0.02, 0.06, 0.98, 0.95))
    fig.savefig(output.with_suffix(".png"), dpi=220, bbox_inches="tight", facecolor="white")
    fig.savefig(output.with_suffix(".svg"), bbox_inches="tight", facecolor="white")
    plt.close(fig)


def analyze(matrix_dir: Path, dataset: Path, output_dir: Path | None = None) -> dict[str, Any]:
    matrix_dir = matrix_dir.resolve()
    dataset = dataset.resolve()
    output = (output_dir or matrix_dir / "analysis").resolve()
    output.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((matrix_dir / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("status") != "completed":
        raise RuntimeError("matrix must have status=completed before analysis")
    cases = _read_jsonl(dataset)
    logs = _read_jsonl(matrix_dir / "runs.jsonl")
    results = _read_jsonl(matrix_dir / "case_results.jsonl")
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in logs:
        grouped[(str(row.get("model")), str(row.get("defense_id")))].append(row)

    summaries: dict[str, Any] = {}
    table: list[dict[str, Any]] = []
    result_status: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    for result in results:
        result_status[(str(result["model"]), str(result["defense_id"]))][
            str(result["final_status"])
        ] += 1
    for (model, defense), group_logs in sorted(grouped.items()):
        metrics = summarize_paper_runs(cases, group_logs)
        summaries[f"{model}|{defense}"] = metrics
        values = {
            name: _metric(metrics, name)[2]
            for name in (
                "asr",
                "attack_unauthorized_action_execution_rate",
                "attack_unauthorized_side_effect_rate",
                "normal_task_completion_rate",
                "normal_intervention_rate",
                "legitimate_tool_false_positive_rate",
                "normal_ask_rate",
                "parse_success_rate",
            )
        }
        table.append(
            {
                "model": model,
                "defense_id": defense,
                "case_runs": sum(result_status[(model, defense)].values()),
                **values,
                "completed": result_status[(model, defense)]["completed"],
                "max_steps_reached": result_status[(model, defense)]["max_steps_reached"],
                "median_case_latency_ms": metrics["engineering"]["median_case_latency_ms"],
                "p95_case_latency_ms": metrics["engineering"]["p95_case_latency_ms"],
                "p95_guard_latency_ms": metrics["engineering"]["p95_guard_latency_ms"],
            }
        )
    _write_csv(output / "metrics_summary.csv", table)
    (output / "metrics_by_condition.json").write_text(
        json.dumps(summaries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    subtitle = (
        f"{len(results)} case runs; 6 fixed validation cases per cell "
        "(4 attacks, 2 benign); temperature 0"
    )
    _build_effect_chart(table, output / "smoke_effects", subtitle)
    _build_status_chart(results, output / "smoke_completion_status", subtitle)

    lines = [
        "# Local-model smoke analysis",
        "",
        "> **Evidence status: diagnostic smoke only.** This batch is a runtime gate, not a confirmatory result.",
        "",
        f"- Matrix: `{portable_path(matrix_dir, root=ROOT)}`",
        f"- Completed case runs: {len(results)}",
        "- Cell size: 6 fixed validation cases (4 attacks, 2 benign).",
        "- This sample is too small for paper-level confidence intervals or model ranking.",
        "- TCR requires both a completed terminal response and every required legitimate tool effect.",
        "- Unauthorized action and unauthorized side-effect rates include only successful mock executions; failed tool attempts are separate engineering failures.",
        "",
        "| Model | Defense | ASR | Attack unauthorized action | Attack unauthorized side effect | TCR | Legitimate-tool FPR | Parse success | Completed | Max steps |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in table:
        lines.append(
            "| {model} | {defense_id} | {asr} | {uaa} | {use} | {tcr} | {fpr} | {parse} | {completed} | {max_steps_reached} |".format(
                model=row["model"],
                defense_id=row["defense_id"],
                asr=_percentage(row["asr"]),
                uaa=_percentage(row["attack_unauthorized_action_execution_rate"]),
                use=_percentage(row["attack_unauthorized_side_effect_rate"]),
                tcr=_percentage(row["normal_task_completion_rate"]),
                fpr=_percentage(row["legitimate_tool_false_positive_rate"]),
                parse=_percentage(row["parse_success_rate"]),
                completed=row["completed"],
                max_steps_reached=row["max_steps_reached"],
            )
        )
    lines += [
        "",
        "## Interpretation boundary",
        "",
        "The smoke gate can reveal parser crashes, missing task effects, repeated ASK/DENY loops and model-format incompatibilities. It cannot establish superiority over external baselines, adaptive robustness, or generalization. Those claims require the frozen M3-v2 holdout plus AgentDojo/InjecAgent and the query-budgeted adaptive matrix.",
        "",
    ]
    (output / "analysis.md").write_text("\n".join(lines), encoding="utf-8")
    analysis_manifest = {
        "schema_version": "paper-matrix-analysis-1.0",
        "status": "diagnostic_not_formal_evidence",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "matrix_manifest_sha256": _sha256(matrix_dir / "manifest.json"),
        "runs_sha256": _sha256(matrix_dir / "runs.jsonl"),
        "case_results_sha256": _sha256(matrix_dir / "case_results.jsonl"),
        "dataset_sha256": _sha256(dataset),
        "case_runs": len(results),
        "groups": len(table),
        "artifacts": [
            "metrics_summary.csv",
            "metrics_by_condition.json",
            "smoke_effects.png",
            "smoke_effects.svg",
            "smoke_completion_status.png",
            "smoke_completion_status.svg",
            "analysis.md",
        ],
    }
    (output / "analysis_manifest.json").write_text(
        json.dumps(analysis_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return analysis_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("matrix_dir", type=Path)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    result = analyze(args.matrix_dir, args.dataset, args.output_dir)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
