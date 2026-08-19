"""Joined diagnostic analysis for paired InjecAgent stage score outputs."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from m3_eval.statistics import mcnemar_exact, proportion_result


ANALYZER_VERSION = "m3-paper-v1-injecagent-stage-pair-analysis-1.0"


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("expected JSON object: " + str(path))
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                value = json.loads(line)
                if isinstance(value, dict):
                    rows.append(value)
    return rows


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _score_output_dir(score_manifest: dict[str, Any]) -> Path:
    return Path(str(score_manifest["output_dir"]))


def _success(row: dict[str, Any]) -> bool:
    if str(row.get("suite")) == "data_security":
        return row.get("eval") == "succ" and row.get("eval Step 2") == "succ"
    return row.get("eval") == "succ"


def _attack_type(row: dict[str, Any]) -> str:
    return str(row.get("Attack Type") or row.get("attack_type") or "unknown")


def _case_rows(score_manifest_path: Path) -> tuple[str, list[dict[str, Any]]]:
    manifest = _read_json(score_manifest_path)
    defenses = manifest.get("defense_ids", [])
    if not isinstance(defenses, list) or len(defenses) != 1:
        raise ValueError("paired stage analysis expects one defense per score manifest")
    defense = str(defenses[0])
    output_dir = _score_output_dir(manifest)
    rows = (
        _read_jsonl(output_dir / "scored_cases" / defense / "test_cases_ds_base.jsonl")
        + _read_jsonl(output_dir / "scored_cases" / defense / "test_cases_dh_base.jsonl")
    )
    for row in rows:
        row["defense_id"] = defense
        row["attack_success"] = _success(row)
    return defense, rows


def analyze_pair(
    *,
    baseline_score_manifest: Path,
    treatment_score_manifest: Path,
    output_dir: Path,
) -> dict[str, Any]:
    baseline_id, baseline_rows = _case_rows(baseline_score_manifest)
    treatment_id, treatment_rows = _case_rows(treatment_score_manifest)
    baseline_by_id = {str(row["benchmark_case_id"]): row for row in baseline_rows}
    treatment_by_id = {str(row["benchmark_case_id"]): row for row in treatment_rows}
    paired_ids = sorted(set(baseline_by_id) & set(treatment_by_id))
    if not paired_ids:
        raise ValueError("no paired InjecAgent cases found")

    pair_rows: list[dict[str, Any]] = []
    for case_id in paired_ids:
        left = baseline_by_id[case_id]
        right = treatment_by_id[case_id]
        pair_rows.append(
            {
                "benchmark_case_id": case_id,
                "suite": left.get("suite"),
                "attack_type": _attack_type(left),
                "baseline_id": baseline_id,
                "treatment_id": treatment_id,
                "baseline_eval": left.get("eval"),
                "baseline_eval_step2": left.get("eval Step 2", ""),
                "treatment_eval": right.get("eval"),
                "treatment_eval_step2": right.get("eval Step 2", ""),
                "baseline_attack_success": bool(left["attack_success"]),
                "treatment_attack_success": bool(right["attack_success"]),
                "paired_outcome": (
                    "both_success"
                    if left["attack_success"] and right["attack_success"]
                    else "baseline_only"
                    if left["attack_success"] and not right["attack_success"]
                    else "treatment_only"
                    if right["attack_success"] and not left["attack_success"]
                    else "both_not_success"
                ),
            }
        )

    summary_rows: list[dict[str, Any]] = []
    for defense, rows in ((baseline_id, baseline_rows), (treatment_id, treatment_rows)):
        for suite in sorted({str(row.get("suite")) for row in rows} | {"all"}):
            suite_rows = rows if suite == "all" else [row for row in rows if str(row.get("suite")) == suite]
            if not suite_rows:
                continue
            successes = sum(bool(row["attack_success"]) for row in suite_rows)
            prop = proportion_result(successes, len(suite_rows))
            summary_rows.append(
                {
                    "defense_id": defense,
                    "suite": suite,
                    "successes": successes,
                    "total": len(suite_rows),
                    "rate": prop["value"],
                    "ci_low": prop["ci_low"],
                    "ci_high": prop["ci_high"],
                }
            )
    bucket_summary_rows: list[dict[str, Any]] = []
    for defense, rows in ((baseline_id, baseline_rows), (treatment_id, treatment_rows)):
        keys = sorted({(str(row.get("suite")), _attack_type(row)) for row in rows})
        for suite, attack_type in keys:
            bucket_rows = [
                row
                for row in rows
                if str(row.get("suite")) == suite and _attack_type(row) == attack_type
            ]
            successes = sum(bool(row["attack_success"]) for row in bucket_rows)
            prop = proportion_result(successes, len(bucket_rows))
            bucket_summary_rows.append(
                {
                    "defense_id": defense,
                    "suite": suite,
                    "attack_type": attack_type,
                    "bucket": f"{suite}|{attack_type}",
                    "successes": successes,
                    "total": len(bucket_rows),
                    "rate": prop["value"],
                    "ci_low": prop["ci_low"],
                    "ci_high": prop["ci_high"],
                }
            )

    baseline_values = [bool(row["baseline_attack_success"]) for row in pair_rows]
    treatment_values = [bool(row["treatment_attack_success"]) for row in pair_rows]
    paired = {
        "event": "injecagent_attack_success",
        "baseline_id": baseline_id,
        "treatment_id": treatment_id,
        "paired_n": len(pair_rows),
        "mcnemar": mcnemar_exact(baseline_values, treatment_values),
        "risk_difference_treatment_minus_baseline": (
            sum(treatment_values) / len(treatment_values)
            - sum(baseline_values) / len(baseline_values)
        ),
        "paired_outcomes": dict(Counter(str(row["paired_outcome"]) for row in pair_rows)),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "paired_cases.csv", pair_rows)
    _write_csv(output_dir / "summary.csv", summary_rows)
    _write_csv(output_dir / "bucket_summary.csv", bucket_summary_rows)
    _write_json(output_dir / "paired_statistics.json", paired)
    figure_manifest = _write_figures(
        output_dir=output_dir,
        baseline_id=baseline_id,
        treatment_id=treatment_id,
        summary_rows=summary_rows,
        bucket_summary_rows=bucket_summary_rows,
        pair_rows=pair_rows,
    )
    manifest = {
        "schema_version": "paper-injecagent-stage-pair-analysis-1.0",
        "analyzer_version": ANALYZER_VERSION,
        "status": "completed",
        "evidence_status": "diagnostic_not_formal_evidence",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "baseline_score_manifest": str(baseline_score_manifest.resolve()),
        "treatment_score_manifest": str(treatment_score_manifest.resolve()),
        "output_dir": str(output_dir.resolve()),
        "baseline_id": baseline_id,
        "treatment_id": treatment_id,
        "paired_n": len(pair_rows),
        "figure_manifest": figure_manifest,
        "result_eligible_for_formal_tables": False,
    }
    _write_json(output_dir / "analysis_manifest.json", manifest)
    baseline_successes = sum(baseline_values)
    treatment_successes = sum(treatment_values)
    lines = [
        "# InjecAgent stage paired diagnostic analysis",
        "",
        "Evidence status: diagnostic only; not a formal public-benchmark result.",
        "",
        f"- Baseline `{baseline_id}` attack success: {baseline_successes}/{len(pair_rows)}.",
        f"- Treatment `{treatment_id}` attack success: {treatment_successes}/{len(pair_rows)}.",
        f"- Risk difference (`{treatment_id}` - `{baseline_id}`): {100 * paired['risk_difference_treatment_minus_baseline']:.1f} percentage points.",
        f"- McNemar baseline-only events: {paired['mcnemar']['baseline_only_event']}; treatment-only events: {paired['mcnemar']['treatment_only_event']}; p={paired['mcnemar']['p_value']:.4g}.",
        f"- Paired outcomes: {paired['paired_outcomes']}.",
        "",
        "Generated diagnostic figures:",
        "",
        "- `attack_success_by_defense.png` / `.svg`: overall and suite-level ASR with Wilson 95% CIs.",
        "- `attack_success_by_bucket.png` / `.svg`: bucket-level ASR heatmap by defense.",
        "- `paired_outcomes.png` / `.svg`: paired outcome composition.",
        "",
        "Boundary: joined score manifests are generated from M3 stage-runner logs and",
        "InjecAgent-style formulas. They are not byte-identical official InjecAgent",
        "prompted/function-calling runs.",
        "",
    ]
    (output_dir / "analysis.md").write_text("\n".join(lines), encoding="utf-8")
    return manifest


def _write_figures(
    *,
    output_dir: Path,
    baseline_id: str,
    treatment_id: str,
    summary_rows: list[dict[str, Any]],
    bucket_summary_rows: list[dict[str, Any]],
    pair_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Write small diagnostic figures for stage-pair analysis."""

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    figures: list[dict[str, Any]] = []

    overall = [
        row
        for row in summary_rows
        if str(row.get("suite")) == "all"
        and str(row.get("defense_id")) in {baseline_id, treatment_id}
    ]
    suites = [
        row
        for row in summary_rows
        if str(row.get("suite")) != "all"
        and str(row.get("defense_id")) in {baseline_id, treatment_id}
    ]
    plot_rows = overall + suites
    labels = [
        f"{row['defense_id']}\n{row['suite']}"
        for row in sorted(plot_rows, key=lambda row: (str(row["suite"]) != "all", str(row["suite"]), str(row["defense_id"])))
    ]
    ordered = sorted(
        plot_rows,
        key=lambda row: (str(row["suite"]) != "all", str(row["suite"]), str(row["defense_id"])),
    )
    rates = [float(row["rate"] or 0.0) for row in ordered]
    lows = [float(row["ci_low"] or 0.0) for row in ordered]
    highs = [float(row["ci_high"] or 0.0) for row in ordered]
    fig, ax = plt.subplots(figsize=(max(7.5, len(ordered) * 0.75), 4.8))
    x = np.arange(len(ordered))
    colors = ["#d95f02" if row["defense_id"] == baseline_id else "#1b9e77" for row in ordered]
    ax.bar(x, [100 * value for value in rates], color=colors, alpha=0.9)
    ax.errorbar(
        x,
        [100 * value for value in rates],
        yerr=[
            [100 * (value - low) for value, low in zip(rates, lows)],
            [100 * (high - value) for value, high in zip(rates, highs)],
        ],
        fmt="none",
        ecolor="#222222",
        capsize=3,
        linewidth=1,
    )
    ax.set_ylim(0, 100)
    ax.set_ylabel("Attack success rate (%)")
    ax.set_title("InjecAgent stage diagnostic ASR by defense")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=35, ha="right")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    for suffix in ("png", "svg"):
        fig.savefig(output_dir / f"attack_success_by_defense.{suffix}", dpi=200, bbox_inches="tight")
    plt.close(fig)
    figures.append(
        {
            "id": "attack_success_by_defense",
            "files": [
                "attack_success_by_defense.png",
                "attack_success_by_defense.svg",
            ],
            "description": "Overall and suite-level attack success rate with Wilson 95% confidence intervals.",
        }
    )

    buckets = sorted({str(row["bucket"]) for row in bucket_summary_rows})
    defenses = [baseline_id, treatment_id]
    matrix = np.full((len(buckets), len(defenses)), np.nan)
    by_key = {
        (str(row["bucket"]), str(row["defense_id"])): row for row in bucket_summary_rows
    }
    for i, bucket in enumerate(buckets):
        for j, defense in enumerate(defenses):
            row = by_key.get((bucket, defense))
            if row and row.get("rate") is not None:
                matrix[i, j] = 100 * float(row["rate"])
    fig, ax = plt.subplots(figsize=(7.0, max(4.2, len(buckets) * 0.45)))
    im = ax.imshow(matrix, vmin=0, vmax=100, cmap="YlOrRd")
    ax.set_xticks(np.arange(len(defenses)))
    ax.set_xticklabels(defenses)
    ax.set_yticks(np.arange(len(buckets)))
    ax.set_yticklabels(buckets)
    ax.set_title("InjecAgent stage ASR by attack bucket")
    for i, bucket in enumerate(buckets):
        for j, defense in enumerate(defenses):
            value = matrix[i, j]
            text = "NA" if np.isnan(value) else f"{value:.0f}%"
            ax.text(j, i, text, ha="center", va="center", color="#111111", fontsize=8)
    fig.colorbar(im, ax=ax, label="Attack success rate (%)")
    fig.tight_layout()
    for suffix in ("png", "svg"):
        fig.savefig(output_dir / f"attack_success_by_bucket.{suffix}", dpi=200, bbox_inches="tight")
    plt.close(fig)
    figures.append(
        {
            "id": "attack_success_by_bucket",
            "files": [
                "attack_success_by_bucket.png",
                "attack_success_by_bucket.svg",
            ],
            "description": "Bucket-level attack success heatmap by defense.",
        }
    )

    outcome_counts = Counter(str(row["paired_outcome"]) for row in pair_rows)
    outcome_order = ["baseline_only", "treatment_only", "both_success", "both_not_success"]
    fig, ax = plt.subplots(figsize=(6.8, 3.8))
    ax.bar(
        outcome_order,
        [outcome_counts.get(outcome, 0) for outcome in outcome_order],
        color=["#d95f02", "#1b9e77", "#7570b3", "#999999"],
    )
    ax.set_ylabel("Paired cases")
    ax.set_title("Paired attack-success outcomes")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    for suffix in ("png", "svg"):
        fig.savefig(output_dir / f"paired_outcomes.{suffix}", dpi=200, bbox_inches="tight")
    plt.close(fig)
    figures.append(
        {
            "id": "paired_outcomes",
            "files": ["paired_outcomes.png", "paired_outcomes.svg"],
            "description": "Counts of baseline-only, treatment-only, both-success and both-not-success pairs.",
        }
    )

    manifest = {
        "schema_version": "paper-injecagent-stage-pair-figures-1.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "figures": figures,
    }
    _write_json(output_dir / "figure_manifest.json", manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-score-manifest", type=Path, required=True)
    parser.add_argument("--treatment-score-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    manifest = analyze_pair(
        baseline_score_manifest=args.baseline_score_manifest,
        treatment_score_manifest=args.treatment_score_manifest,
        output_dir=args.output_dir,
    )
    print(json.dumps(manifest, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
