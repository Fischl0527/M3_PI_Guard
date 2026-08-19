"""Analyze the frozen PromptGuard detector-only formal run and build figures."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from m3_eval.statistics import proportion_result

from .common import rows_sha256, sha256_file


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_FREEZE = ROOT / "protocols" / "paper_upgrade_v1" / "promptguard_detector_formal_freeze_v1.json"
DEFAULT_RUN = (
    ROOT
    / "outputs"
    / "paper_upgrade_v1"
    / "baselines"
    / "promptguard_detector_formal_v1"
    / "run"
    / "run_manifest.json"
)
DEFAULT_OUTPUT = (
    ROOT
    / "outputs"
    / "paper_upgrade_v1"
    / "baselines"
    / "promptguard_detector_formal_v1"
    / "analysis"
)
ANALYZER_VERSION = "m3-paper-v1-promptguard-detector-formal-analysis-1.0"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number} is not an object")
            rows.append(value)
    return rows


def _safe_ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _percentile(values: Sequence[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def confusion_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    tp = sum(
        row["ground_truth_label"] == "malicious"
        and row["effective_decision"] == "malicious"
        for row in rows
    )
    fn = sum(
        row["ground_truth_label"] == "malicious"
        and row["effective_decision"] != "malicious"
        for row in rows
    )
    fp = sum(
        row["ground_truth_label"] == "benign"
        and row["effective_decision"] == "malicious"
        for row in rows
    )
    tn = sum(
        row["ground_truth_label"] == "benign"
        and row["effective_decision"] != "malicious"
        for row in rows
    )
    precision = _safe_ratio(tp, tp + fp)
    recall = _safe_ratio(tp, tp + fn)
    fpr = _safe_ratio(fp, fp + tn)
    f1 = (
        2.0 * precision * recall / (precision + recall)
        if precision is not None
        and recall is not None
        and precision + recall > 0
        else None
    )
    accuracy = _safe_ratio(tp + tn, len(rows))
    latencies = [float(row["total_latency_ms"]) for row in rows]
    precision_ci = proportion_result(tp, tp + fp)
    recall_ci = proportion_result(tp, tp + fn)
    fpr_ci = proportion_result(fp, fp + tn)
    success_ci = proportion_result(
        sum(row["status"] == "completed" for row in rows), len(rows)
    )
    return {
        "n": len(rows),
        "positive_n": tp + fn,
        "negative_n": fp + tn,
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "fpr": fpr,
        "accuracy": accuracy,
        "precision_ci_low": precision_ci["ci_low"],
        "precision_ci_high": precision_ci["ci_high"],
        "recall_ci_low": recall_ci["ci_low"],
        "recall_ci_high": recall_ci["ci_high"],
        "fpr_ci_low": fpr_ci["ci_low"],
        "fpr_ci_high": fpr_ci["ci_high"],
        "inference_success_rate": success_ci["value"],
        "inference_success_ci_low": success_ci["ci_low"],
        "inference_success_ci_high": success_ci["ci_high"],
        "inference_failure_n": sum(row["status"] != "completed" for row in rows),
        "latency_ms_median": _percentile(latencies, 0.5),
        "latency_ms_p95": _percentile(latencies, 0.95),
    }


def _metric_row(group_type: str, group_value: str, rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {"group_type": group_type, "group_value": group_value, **confusion_summary(rows)}


def build_metric_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    metrics = [_metric_row("overall", "all", rows)]
    for field, group_type in (
        ("benchmark", "benchmark"),
        ("split", "split"),
        ("category", "category"),
        ("language", "language"),
    ):
        grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        for row in rows:
            value = str(row.get(field, ""))
            if value:
                grouped[value].append(row)
        for value in sorted(grouped):
            metrics.append(_metric_row(group_type, value, grouped[value]))
    return metrics


def roc_pr_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"status": "undefined_empty"}
    positives = sum(row["ground_truth_label"] == "malicious" for row in rows)
    negatives = len(rows) - positives
    if positives == 0 or negatives == 0:
        return {
            "status": "undefined_single_class",
            "positive_n": positives,
            "negative_n": negatives,
        }
    scored = [
        (
            float(row["aggregate_malicious_probability"])
            if row.get("aggregate_malicious_probability") is not None
            else 1.0,
            row["ground_truth_label"] == "malicious",
        )
        for row in rows
    ]
    thresholds = [float("inf")] + sorted({score for score, _ in scored}, reverse=True)
    points: list[dict[str, Any]] = []
    for threshold in thresholds:
        tp = sum(label and score >= threshold for score, label in scored)
        fp = sum((not label) and score >= threshold for score, label in scored)
        recall = tp / positives
        fpr = fp / negatives
        precision = tp / (tp + fp) if tp + fp else 1.0
        points.append(
            {
                "threshold": None if math.isinf(threshold) else threshold,
                "tpr": recall,
                "fpr": fpr,
                "precision": precision,
                "recall": recall,
            }
        )
    roc_sorted = sorted(points, key=lambda row: (row["fpr"], row["tpr"]))
    auroc = sum(
        (right["fpr"] - left["fpr"]) * (right["tpr"] + left["tpr"]) / 2.0
        for left, right in zip(roc_sorted, roc_sorted[1:])
    )
    pr_sorted = sorted(points, key=lambda row: row["recall"])
    average_precision = sum(
        max(0.0, right["recall"] - left["recall"]) * right["precision"]
        for left, right in zip(pr_sorted, pr_sorted[1:])
    )
    return {
        "status": "completed",
        "positive_n": positives,
        "negative_n": negatives,
        "auroc": auroc,
        "average_precision": average_precision,
        "points": points,
        "points_sha256": rows_sha256(points),
        "failure_scores_are_fail_closed_one": True,
    }


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _save_figure(fig: Any, base: Path) -> list[Path]:
    png = base.with_suffix(".png")
    svg = base.with_suffix(".svg")
    fig.savefig(png, dpi=180, bbox_inches="tight", facecolor="white")
    fig.savefig(svg, bbox_inches="tight", facecolor="white")
    return [png, svg]


def _metric_index(metrics: Sequence[Mapping[str, Any]], group_type: str) -> dict[str, Mapping[str, Any]]:
    return {
        str(row["group_value"]): row
        for row in metrics
        if row["group_type"] == group_type
    }


def build_figures(
    rows: Sequence[Mapping[str, Any]],
    metrics: Sequence[Mapping[str, Any]],
    curves: Mapping[str, Any],
    *,
    output_dir: Path,
) -> list[dict[str, Any]]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts: list[dict[str, Any]] = []

    benchmark = _metric_index(metrics, "benchmark")
    names = [name for name in ("m3_v2", "agentdojo", "injecagent") if name in benchmark]
    x = np.arange(len(names))
    recall = [benchmark[name]["recall"] or 0.0 for name in names]
    fpr = [benchmark[name]["fpr"] for name in names]
    fig, ax = plt.subplots(figsize=(9.2, 5.3))
    width = 0.36
    ax.bar(x - width / 2, recall, width, label="Recall", color="#2962A3")
    ax.bar(
        x + width / 2,
        [value if value is not None else 0.0 for value in fpr],
        width,
        label="FPR",
        color="#D97941",
    )
    for index, value in enumerate(fpr):
        if value is None:
            ax.text(index + width / 2, 0.025, "N/A", ha="center", va="bottom", fontsize=9)
    ax.set_xticks(x, [name.replace("_", "-") for name in names])
    ax.set_ylim(0, 1.06)
    ax.set_ylabel("Rate")
    ax.set_title("PromptGuard detector performance by benchmark")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(frameon=True, facecolor="white", framealpha=0.96)
    paths = _save_figure(fig, output_dir / "benchmark_recall_fpr")
    plt.close(fig)
    artifacts.extend(
        {"figure_id": "promptguard_benchmark_recall_fpr", "path": str(path), "sha256": sha256_file(path)}
        for path in paths
    )

    m3_attack = [
        row
        for row in rows
        if row["benchmark"] == "m3_v2" and row["ground_truth_label"] == "malicious"
    ]
    family_groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in m3_attack:
        family_groups[str(row["category"])].append(row)
    families = sorted(family_groups)
    family_values = [confusion_summary(family_groups[name])["recall"] or 0.0 for name in families]
    fig, ax = plt.subplots(figsize=(10.5, 6.0))
    bars = ax.barh(families, family_values, color="#3A7D6E")
    ax.set_xlim(0, 1.05)
    ax.set_xlabel("Recall")
    ax.set_title("M3-v2 malicious recall by attack family")
    ax.grid(axis="x", alpha=0.25)
    for bar, value in zip(bars, family_values):
        ax.text(min(value + 0.012, 1.01), bar.get_y() + bar.get_height() / 2, f"{value:.1%}", va="center", fontsize=8)
    paths = _save_figure(fig, output_dir / "m3_attack_family_recall")
    plt.close(fig)
    artifacts.extend(
        {"figure_id": "promptguard_m3_attack_family_recall", "path": str(path), "sha256": sha256_file(path)}
        for path in paths
    )

    m3_rows = [row for row in rows if row["benchmark"] == "m3_v2"]
    language_groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in m3_rows:
        language_groups[str(row["language"])].append(row)
    languages = sorted(language_groups)
    lang_recall = [confusion_summary(language_groups[name])["recall"] or 0.0 for name in languages]
    lang_fpr = [confusion_summary(language_groups[name])["fpr"] or 0.0 for name in languages]
    x = np.arange(len(languages))
    fig, ax = plt.subplots(figsize=(10.2, 5.6))
    ax.bar(x - width / 2, lang_recall, width, label="Recall", color="#2962A3")
    ax.bar(x + width / 2, lang_fpr, width, label="FPR", color="#D97941")
    ax.set_xticks(x, languages, rotation=20, ha="right")
    ax.set_ylim(0, 1.06)
    ax.set_ylabel("Rate")
    ax.set_title("M3-v2 PromptGuard performance by language")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(frameon=True, facecolor="white", framealpha=0.96)
    paths = _save_figure(fig, output_dir / "m3_language_performance")
    plt.close(fig)
    artifacts.extend(
        {"figure_id": "promptguard_m3_language_performance", "path": str(path), "sha256": sha256_file(path)}
        for path in paths
    )

    score_groups: list[list[float]] = []
    score_labels: list[str] = []
    for benchmark_name in ("m3_v2", "agentdojo", "injecagent"):
        for label in ("benign", "malicious"):
            values = [
                float(row["aggregate_malicious_probability"])
                for row in rows
                if row["benchmark"] == benchmark_name
                and row["ground_truth_label"] == label
                and row.get("aggregate_malicious_probability") is not None
            ]
            if values:
                score_groups.append(values)
                score_labels.append(f"{benchmark_name}\n{label}")
    fig, ax = plt.subplots(figsize=(10.5, 5.8))
    ax.boxplot(score_groups, labels=score_labels, showfliers=False, patch_artist=True)
    ax.axhline(0.5, color="#B23A48", linestyle="--", linewidth=1.2, label="Frozen threshold")
    ax.set_ylim(-0.02, 1.02)
    ax.set_ylabel("Malicious probability")
    ax.set_title("PromptGuard score distributions")
    ax.tick_params(axis="x", rotation=20)
    ax.grid(axis="y", alpha=0.25)
    ax.legend(frameon=True, facecolor="white", framealpha=0.96)
    paths = _save_figure(fig, output_dir / "score_distributions")
    plt.close(fig)
    artifacts.extend(
        {"figure_id": "promptguard_score_distributions", "path": str(path), "sha256": sha256_file(path)}
        for path in paths
    )

    fig, axes = plt.subplots(1, 2, figsize=(11.2, 4.8))
    for name, curve in curves.items():
        if curve.get("status") != "completed":
            continue
        points = curve["points"]
        axes[0].plot([row["fpr"] for row in points], [row["tpr"] for row in points], label=f"{name} AUC={curve['auroc']:.3f}")
        axes[1].plot([row["recall"] for row in points], [row["precision"] for row in points], label=f"{name} AP={curve['average_precision']:.3f}")
    axes[0].plot([0, 1], [0, 1], color="#777777", linestyle="--", linewidth=1)
    axes[0].set(xlabel="False-positive rate", ylabel="True-positive rate", title="ROC")
    axes[1].set(xlabel="Recall", ylabel="Precision", title="Precision-recall")
    for ax in axes:
        ax.set_xlim(0, 1.01)
        ax.set_ylim(0, 1.01)
        ax.grid(alpha=0.25)
        ax.legend(fontsize=8, frameon=True, facecolor="white", framealpha=0.96)
    paths = _save_figure(fig, output_dir / "roc_pr_curves")
    plt.close(fig)
    artifacts.extend(
        {"figure_id": "promptguard_roc_pr_curves", "path": str(path), "sha256": sha256_file(path)}
        for path in paths
    )

    fig, ax = plt.subplots(figsize=(9.2, 5.2))
    for benchmark_name in ("m3_v2", "agentdojo", "injecagent"):
        values = sorted(
            float(row["total_latency_ms"])
            for row in rows
            if row["benchmark"] == benchmark_name
        )
        if not values:
            continue
        y = [(index + 1) / len(values) for index in range(len(values))]
        ax.plot(values, y, label=benchmark_name)
    ax.set_xlabel("Per-case detector latency (ms)")
    ax.set_ylabel("Empirical CDF")
    ax.set_title("PromptGuard detector latency ECDF")
    ax.grid(alpha=0.25)
    ax.legend(frameon=True, facecolor="white", framealpha=0.96)
    paths = _save_figure(fig, output_dir / "latency_ecdf")
    plt.close(fig)
    artifacts.extend(
        {"figure_id": "promptguard_latency_ecdf", "path": str(path), "sha256": sha256_file(path)}
        for path in paths
    )
    return artifacts


def _format_rate(value: Any) -> str:
    return "undefined" if value is None else f"{100 * float(value):.2f}%"


def _write_analysis(path: Path, manifest: Mapping[str, Any], metrics: Sequence[Mapping[str, Any]]) -> None:
    overall = next(row for row in metrics if row["group_type"] == "overall")
    benchmarks = [row for row in metrics if row["group_type"] == "benchmark"]
    lines = [
        "# PromptGuard detector-only formal analysis v1",
        "",
        f"- Status: `{manifest['status']}`",
        f"- Formal detector-table eligible: `{manifest['result_eligible_for_formal_tables']}`",
        f"- Cases: `{overall['n']}`",
        f"- Recall: `{overall['tp']}/{overall['positive_n']} = {_format_rate(overall['recall'])}`",
        f"- FPR: `{overall['fp']}/{overall['negative_n']} = {_format_rate(overall['fpr'])}`",
        f"- Precision: `{_format_rate(overall['precision'])}`",
        f"- F1: `{_format_rate(overall['f1'])}`",
        f"- Inference failures: `{overall['inference_failure_n']}`",
        f"- Median / p95 per-case latency: `{overall['latency_ms_median']:.3f} / {overall['latency_ms_p95']:.3f} ms`",
        "",
        "## By benchmark",
        "",
        "| Benchmark | TP/positive | Recall | FP/negative | FPR | Precision | F1 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in benchmarks:
        lines.append(
            f"| `{row['group_value']}` | {row['tp']}/{row['positive_n']} | "
            f"{_format_rate(row['recall'])} | {row['fp']}/{row['negative_n']} | "
            f"{_format_rate(row['fpr'])} | {_format_rate(row['precision'])} | "
            f"{_format_rate(row['f1'])} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            manifest["boundary"],
            "",
            "The fixed threshold was not tuned after observing these results. M3-v2 split-specific "
            "rows must distinguish development, validation and automated holdout; the automated "
            "holdout is not an independently authored blind set. InjecAgent has no benign rows in "
            "this release, so its standalone FPR is undefined. Failures, if any, remain in the "
            "denominator under the frozen fail-closed policy.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def analyze_promptguard_formal(
    *,
    freeze_path: Path = DEFAULT_FREEZE,
    run_manifest_path: Path = DEFAULT_RUN,
    output_dir: Path = DEFAULT_OUTPUT,
) -> dict[str, Any]:
    freeze_path = freeze_path.resolve()
    run_manifest_path = run_manifest_path.resolve()
    output_dir = output_dir.resolve()
    freeze = _read_json(freeze_path)
    run = _read_json(run_manifest_path)
    if run.get("status") != "completed" or not run.get("result_eligible_for_formal_tables"):
        raise ValueError("PromptGuard formal run has not passed its completeness gate")
    if run.get("freeze_sha256") != sha256_file(freeze_path):
        raise ValueError("run manifest does not match current freeze")

    labels_path = Path(str(freeze["frozen_inputs"]["labels_path"]))
    predictions_path = Path(str(run["output_files"]["raw_predictions"]))
    if sha256_file(labels_path) != freeze["frozen_inputs"]["labels_file_sha256"]:
        raise ValueError("frozen label file hash drift")
    if sha256_file(predictions_path) != run["output_files"]["raw_predictions_sha256"]:
        raise ValueError("raw prediction file hash drift")
    labels = _read_jsonl(labels_path)
    predictions = _read_jsonl(predictions_path)
    labels_by_id = {str(row["case_id"]): row for row in labels}
    predictions_by_id = {str(row["case_id"]): row for row in predictions}
    if len(labels_by_id) != len(labels) or len(predictions_by_id) != len(predictions):
        raise ValueError("duplicate labels or predictions")
    if set(labels_by_id) != set(predictions_by_id):
        raise ValueError("label/prediction case universe mismatch")
    joined = [
        {**predictions_by_id[case_id], **labels_by_id[case_id]}
        for case_id in labels_by_id
    ]
    metrics = build_metric_rows(joined)
    curves = {
        "overall": roc_pr_summary(joined),
        "m3_v2": roc_pr_summary([row for row in joined if row["benchmark"] == "m3_v2"]),
        "agentdojo": roc_pr_summary(
            [row for row in joined if row["benchmark"] == "agentdojo"]
        ),
        "injecagent": roc_pr_summary(
            [row for row in joined if row["benchmark"] == "injecagent"]
        ),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = output_dir / "metrics.csv"
    statistics_path = output_dir / "statistics.json"
    joined_path = output_dir / "scored_cases.jsonl"
    figure_dir = output_dir / "figures"
    _write_csv(metrics_path, metrics)
    _write_json(statistics_path, {"curves": curves, "metric_rows_sha256": rows_sha256(metrics)})
    from .common import write_jsonl

    write_jsonl(joined_path, joined)
    figures = build_figures(joined, metrics, curves, output_dir=figure_dir)
    figure_manifest_path = output_dir / "figure_manifest.json"
    figure_manifest = {
        "schema_version": "paper-promptguard-detector-figure-manifest-1.0",
        "created_at": _utc_now(),
        "source_predictions_sha256": sha256_file(predictions_path),
        "source_labels_sha256": sha256_file(labels_path),
        "figures": figures,
        "figures_sha256": rows_sha256(figures),
    }
    _write_json(figure_manifest_path, figure_manifest)
    checks = {
        "freeze_run_hash_match": run["freeze_sha256"] == sha256_file(freeze_path),
        "expected_case_count": len(joined) == 3280,
        "unique_joined_ids": len(joined) == len({row["case_id"] for row in joined}),
        "all_failures_retained": len(joined) == run["summary"]["prediction_count"],
        "metrics_generated": bool(metrics),
        "statistics_generated": statistics_path.is_file(),
        "six_figure_pairs_generated": len(figures) == 12,
        "raw_source_hashes_match": sha256_file(predictions_path)
        == run["output_files"]["raw_predictions_sha256"],
    }
    eligible = all(checks.values())
    manifest = {
        "schema_version": "paper-promptguard-detector-formal-analysis-1.0",
        "analyzer_version": ANALYZER_VERSION,
        "status": "completed_source_backed_formal_detector_baseline"
        if eligible
        else "failed_analysis_gate",
        "created_at": _utc_now(),
        "freeze_path": str(freeze_path),
        "freeze_sha256": sha256_file(freeze_path),
        "run_manifest_path": str(run_manifest_path),
        "run_manifest_sha256": sha256_file(run_manifest_path),
        "summary": next(row for row in metrics if row["group_type"] == "overall"),
        "checks": checks,
        "checks_passed": eligible,
        "artifacts": {
            "metrics": str(metrics_path),
            "metrics_sha256": sha256_file(metrics_path),
            "statistics": str(statistics_path),
            "statistics_sha256": sha256_file(statistics_path),
            "scored_cases": str(joined_path),
            "scored_cases_sha256": sha256_file(joined_path),
            "figure_manifest": str(figure_manifest_path),
            "figure_manifest_sha256": sha256_file(figure_manifest_path),
        },
        "result_eligible_for_formal_tables": eligible,
        "eligible_table_scope": ["detector_performance"],
        "ineligible_table_scope": ["end_to_end_agent_asr", "agent_tcr", "tool_execution_utility"],
        "boundary": (
            "This is a formal, source-backed detector-only result over frozen external-content "
            "inputs. It may support detector recall/FPR/precision/F1 and latency claims, but it "
            "does not support end-to-end agent ASR, task completion or tool-utility claims."
        ),
    }
    analysis_path = output_dir / "analysis.md"
    manifest_path = output_dir / "analysis_manifest.json"
    _write_analysis(analysis_path, manifest, metrics)
    manifest["artifacts"]["analysis"] = str(analysis_path)
    manifest["artifacts"]["analysis_sha256"] = sha256_file(analysis_path)
    _write_json(manifest_path, manifest)
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", type=Path, default=DEFAULT_FREEZE)
    parser.add_argument("--run-manifest", type=Path, default=DEFAULT_RUN)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = analyze_promptguard_formal(
        freeze_path=args.freeze,
        run_manifest_path=args.run_manifest,
        output_dir=args.output_dir,
    )
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "summary": manifest["summary"],
                "checks": manifest["checks"],
                "result_eligible_for_formal_tables": manifest[
                    "result_eligible_for_formal_tables"
                ],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
