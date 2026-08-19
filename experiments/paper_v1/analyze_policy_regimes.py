"""Compare diagnostic policy-regime matrix directories."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from m3_eval.paper_metrics import summarize_paper_runs


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET = ROOT / "m3_attacks" / "cases" / "paper_v1" / "m3_v2_validation.jsonl"
REGIME_ORDER = ("auto_compiled", "ambiguous", "partial", "incorrect")
EVIDENCE_STATUS = "diagnostic_policy_regime_smoke_not_formal_evidence"


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


def _metric(metrics: Mapping[str, Any], name: str) -> float | None:
    return metrics[name]["value"]


def _percentage(value: float | None) -> str:
    return "NA" if value is None else f"{100 * value:.1f}%"


def _write_csv(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    materialized = list(rows)
    if not materialized:
        raise ValueError("cannot write empty policy-regime summary")
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(materialized[0]))
        writer.writeheader()
        writer.writerows(materialized)


def _sort_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    order = {name: index for index, name in enumerate(REGIME_ORDER)}
    return sorted(rows, key=lambda row: order.get(str(row["policy_regime"]), 999))


def _plot(rows: list[dict[str, Any]], output: Path) -> None:
    import matplotlib.pyplot as plt
    import numpy as np

    rows = _sort_rows(rows)
    labels = [str(row["policy_regime"]).replace("_", "\n") for row in rows]
    x = np.arange(len(rows))
    series = (
        ("attack_unauthorized_side_effect_rate", "Attack side-effect rate", "#D55E00", "lower is safer"),
        ("normal_task_completion_rate", "Normal task completion", "#007C83", "higher is better"),
        ("normal_ask_rate", "Normal ASK rate", "#B89B3C", "lower means less confirmation burden"),
    )
    fig, axes = plt.subplots(1, 3, figsize=(12.8, 4.8), sharex=True)
    for axis, (field, title, color, direction) in zip(axes, series):
        values = [row[field] if row[field] is not None else float("nan") for row in rows]
        axis.plot(x, values, marker="o", linewidth=2.0, color=color)
        for xi, value in zip(x, values):
            if np.isnan(value):
                continue
            axis.text(
                xi,
                min(1.08, value + 0.045),
                f"{value:.0%}",
                ha="center",
                fontsize=8,
                color="#25313C",
            )
        axis.set_title(title, fontsize=11, weight="bold", pad=10)
        axis.text(0.5, 1.01, direction, transform=axis.transAxes, ha="center", fontsize=8, color="#555555")
        axis.set_ylim(0, 1.12)
        axis.grid(axis="y", alpha=0.22)
        axis.spines[["top", "right"]].set_visible(False)
    axes[0].set_ylabel("Rate")
    for axis in axes:
        axis.set_xticks(x)
        axis.set_xticklabels(labels, fontsize=8)
    fig.suptitle("M3 policy-regime diagnostic smoke", fontsize=15, weight="bold", y=1.04)
    fig.text(
        0.5,
        0.965,
        f"{len(rows)} regimes; qwen3 smoke; validation subset; temperature 0",
        ha="center",
        fontsize=9,
        color="#444444",
    )
    fig.text(
        0.5,
        0.015,
        "DIAGNOSTIC SMOKE -- not formal paper evidence",
        ha="center",
        fontsize=9,
        color="#A33A2B",
        weight="bold",
    )
    fig.tight_layout(rect=(0.02, 0.06, 0.98, 0.90))
    fig.savefig(output.with_suffix(".png"), dpi=220, bbox_inches="tight", facecolor="white")
    fig.savefig(output.with_suffix(".svg"), bbox_inches="tight", facecolor="white")
    plt.close(fig)


def analyze_policy_regimes(
    matrix_dirs: Iterable[Path],
    *,
    dataset: Path = DEFAULT_DATASET,
    output_dir: Path,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    cases = _read_jsonl(dataset.resolve())
    table: list[dict[str, Any]] = []
    inputs: list[dict[str, Any]] = []
    for matrix_dir in matrix_dirs:
        directory = matrix_dir.resolve()
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        config = json.loads((directory / "execution_config.json").read_text(encoding="utf-8"))
        if manifest.get("status") != "completed":
            raise RuntimeError(f"{directory} must have completed manifest status")
        logs = _read_jsonl(directory / "runs.jsonl")
        results = _read_jsonl(directory / "case_results.jsonl")
        metrics = summarize_paper_runs(cases, logs)
        statuses = Counter(str(row["final_status"]) for row in results)
        row = {
            "policy_regime": str(manifest.get("policy_regime") or config.get("policy_regime")),
            "models": ",".join(str(item) for item in config.get("models", [])),
            "conditions": ",".join(str(item) for item in config.get("conditions", [])),
            "case_runs": len(results),
            "step_logs": len(logs),
            "completed": statuses["completed"],
            "max_steps_reached": statuses["max_steps_reached"],
            "attack_unauthorized_side_effect_rate": _metric(metrics, "attack_unauthorized_side_effect_rate"),
            "normal_task_completion_rate": _metric(metrics, "normal_task_completion_rate"),
            "normal_ask_rate": _metric(metrics, "normal_ask_rate"),
            "parse_success_rate": _metric(metrics, "parse_success_rate"),
            "p95_guard_latency_ms": metrics["engineering"]["p95_guard_latency_ms"],
        }
        table.append(row)
        inputs.append(
            {
                "matrix_dir": str(directory),
                "manifest_sha256": _sha256(directory / "manifest.json"),
                "runs_sha256": _sha256(directory / "runs.jsonl"),
                "case_results_sha256": _sha256(directory / "case_results.jsonl"),
            }
        )
    table = _sort_rows(table)
    _write_csv(output_dir / "policy_regime_summary.csv", table)
    (output_dir / "policy_regime_summary.json").write_text(
        json.dumps(table, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    _plot(table, output_dir / "policy_regime_smoke")
    lines = [
        "# Policy-regime smoke analysis",
        "",
        "> **Evidence status: diagnostic smoke only.** This is a small validation-subset runtime check, not a confirmatory result.",
        "",
        f"- Dataset: `{dataset.resolve()}`",
        f"- Regime directories: {len(inputs)}",
        "- This analysis is intended to verify the paper-v1 authorization-uncertainty pipeline before larger validation/blind runs.",
        "",
        "| Policy regime | Case runs | Attack side-effect | TCR | Normal ASK | Parse success | Completed | Max steps |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in table:
        lines.append(
            "| {policy_regime} | {case_runs} | {side} | {tcr} | {ask} | {parse} | {completed} | {max_steps_reached} |".format(
                policy_regime=row["policy_regime"],
                case_runs=row["case_runs"],
                side=_percentage(row["attack_unauthorized_side_effect_rate"]),
                tcr=_percentage(row["normal_task_completion_rate"]),
                ask=_percentage(row["normal_ask_rate"]),
                parse=_percentage(row["parse_success_rate"]),
                completed=row["completed"],
                max_steps_reached=row["max_steps_reached"],
            )
        )
    lines += [
        "",
        "## Boundary",
        "",
        "- No public benchmark or blind-test claim should cite this as a formal result.",
        "- Larger runs must freeze hypotheses, selected cases, thresholds and exclusion rules before use in a manuscript table.",
    ]
    (output_dir / "analysis.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    manifest = {
        "schema_version": "paper-policy-regime-analysis-1.0",
        "status": EVIDENCE_STATUS,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset": str(dataset.resolve()),
        "dataset_sha256": _sha256(dataset.resolve()),
        "input_count": len(inputs),
        "inputs": inputs,
        "artifacts": [
            "policy_regime_summary.csv",
            "policy_regime_summary.json",
            "policy_regime_smoke.png",
            "policy_regime_smoke.svg",
            "analysis.md",
        ],
    }
    (output_dir / "analysis_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("matrix_dirs", nargs="+", type=Path)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    manifest = analyze_policy_regimes(
        args.matrix_dirs,
        dataset=args.dataset,
        output_dir=args.output_dir,
    )
    print(json.dumps(manifest, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
