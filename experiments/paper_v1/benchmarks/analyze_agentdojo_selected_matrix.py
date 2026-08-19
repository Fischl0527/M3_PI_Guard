"""Analyze an exact selected-cluster AgentDojo diagnostic matrix."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from m3_eval.statistics import (
    clustered_paired_bootstrap,
    mcnemar_exact,
    proportion_result,
)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _plot(output_dir: Path, suite_summary: list[dict[str, Any]], cluster_rows: list[dict[str, Any]]) -> None:
    import matplotlib.pyplot as plt
    import numpy as np

    defenses = ["no_defense", "m3_full"]
    colors = {"no_defense": "#D39A2C", "m3_full": "#2F5D8C"}
    suites = sorted({str(row["suite"]) for row in suite_summary})
    lookup = {
        (row["suite"], row["defense_id"]): row
        for row in suite_summary
        if row["metric"] == "official_injection_success"
    }
    fig, axes = plt.subplots(1, 2, figsize=(14.5, 5.2), gridspec_kw={"width_ratios": [1.0, 1.35]})
    x = np.arange(len(suites))
    width = 0.34
    for index, defense in enumerate(defenses):
        rows = [lookup[(suite, defense)] for suite in suites]
        values = [float(row["value"] or 0.0) for row in rows]
        lows = [float(row["ci_low"] or 0.0) for row in rows]
        highs = [float(row["ci_high"] or 0.0) for row in rows]
        bars = axes[0].bar(
            x + (index - 0.5) * width,
            values,
            width,
            color=colors[defense],
            edgecolor="#27323A",
            linewidth=0.7,
            label=defense,
            yerr=[
                [max(0.0, value - low) for value, low in zip(values, lows)],
                [max(0.0, high - value) for value, high in zip(values, highs)],
            ],
            capsize=3,
        )
        for bar, row, value in zip(bars, rows, values):
            axes[0].text(
                bar.get_x() + bar.get_width() / 2,
                min(1.04, value + 0.055),
                f"{row['numerator']}/{row['denominator']}",
                ha="center",
                va="bottom",
                fontsize=8,
            )
    axes[0].set_title("Injection success by suite", loc="left", fontweight="bold")
    axes[0].set_xticks(x, suites, rotation=20, ha="right")
    axes[0].set_ylabel("Proportion")
    axes[0].set_ylim(0, 1.08)
    axes[0].grid(axis="y", color="#D9DEE2", linewidth=0.7)
    axes[0].legend(frameon=False, loc="upper center")

    cluster_subset = [
        row
        for row in cluster_rows
        if row["defense_id"] == "no_defense"
    ]
    cluster_subset = sorted(
        cluster_subset,
        key=lambda row: (float(row["value"] or 0.0), row["suite"], row["user_task_id"]),
        reverse=True,
    )[:16]
    labels = [
        f"{row['suite']}/{row['user_task_id'].replace('user_task_', 'u')}/{row['injection_task_id'].replace('injection_task_', 'i')}"
        for row in cluster_subset
    ]
    values = [float(row["value"] or 0.0) for row in cluster_subset]
    y = np.arange(len(labels))
    bars = axes[1].barh(y, values, color="#D39A2C", edgecolor="#27323A", linewidth=0.7)
    axes[1].set_yticks(y, labels)
    axes[1].invert_yaxis()
    axes[1].set_xlim(0, 1.05)
    axes[1].set_title("Top baseline-vulnerable clusters", loc="left", fontweight="bold")
    axes[1].grid(axis="x", color="#D9DEE2", linewidth=0.7)
    for bar, row, value in zip(bars, cluster_subset, values):
        axes[1].text(
            min(1.02, value + 0.025),
            bar.get_y() + bar.get_height() / 2,
            f"{row['numerator']}/{row['denominator']}",
            va="center",
            fontsize=8,
        )

    fig.suptitle("AgentDojo selected-cluster repeat diagnostic", x=0.06, ha="left", fontsize=15, fontweight="bold")
    fig.text(
        0.06,
        0.91,
        "Exact clusters from selection v1; qwen3:4b-instruct; 3 seeds; diagnostic repeat only",
        fontsize=10,
        color="#4F5B63",
    )
    fig.text(
        0.5,
        0.015,
        "DIAGNOSTIC / NOT FORMAL EVIDENCE",
        ha="center",
        fontsize=11,
        color="#9C4F2E",
        fontweight="bold",
    )
    fig.tight_layout(rect=(0.03, 0.06, 0.98, 0.88))
    output_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_dir / "selected_cluster_repeat.png", dpi=200, bbox_inches="tight")
    fig.savefig(output_dir / "selected_cluster_repeat.svg", bbox_inches="tight")
    plt.close(fig)


def analyze(manifest_path: Path, output_dir: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "completed":
        raise ValueError("selected matrix must be completed before analysis")
    if manifest.get("result_eligible_for_formal_tables") is not False:
        raise ValueError("selected matrix is not explicitly diagnostic-only")
    rows = [row for row in manifest["jobs"] if row.get("status") == "completed"]
    defenses = [str(item) for item in manifest["config"]["defense_ids"]]
    baseline_id, treatment_id = defenses

    suite_summary: list[dict[str, Any]] = []
    for suite in sorted({str(row["suite"]) for row in rows}):
        suite_rows = [row for row in rows if row["suite"] == suite]
        for defense in defenses:
            subset = [row for row in suite_rows if row["defense_id"] == defense]
            count = sum(bool(row.get("official_injection_success")) for row in subset)
            stats = proportion_result(count, len(subset))
            suite_summary.append(
                {
                    "suite": suite,
                    "defense_id": defense,
                    "metric": "official_injection_success",
                    **stats,
                }
            )

    grouped: dict[tuple[str, str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[
            (
                str(row["suite"]),
                str(row["user_task_id"]),
                str(row["injection_task_id"]),
                str(row["cluster_role"]),
                str(row["defense_id"]),
            )
        ].append(row)
    cluster_rows: list[dict[str, Any]] = []
    for (suite, user_task, injection_task, role, defense), subset in sorted(grouped.items()):
        count = sum(bool(row.get("official_injection_success")) for row in subset)
        stats = proportion_result(count, len(subset))
        cluster_rows.append(
            {
                "suite": suite,
                "user_task_id": user_task,
                "injection_task_id": injection_task,
                "cluster_role": role,
                "defense_id": defense,
                **stats,
            }
        )

    paired_values: dict[tuple[str, str, str, int], dict[str, bool]] = defaultdict(dict)
    for row in rows:
        key = (
            str(row["suite"]),
            str(row["user_task_id"]),
            str(row["injection_task_id"]),
            int(row["replicate_id"]),
        )
        paired_values[key][str(row["defense_id"])] = bool(row.get("official_injection_success"))
    paired_keys = sorted(key for key, values in paired_values.items() if set(values) == set(defenses))
    baseline = [paired_values[key][baseline_id] for key in paired_keys]
    treatment = [paired_values[key][treatment_id] for key in paired_keys]
    cluster_pairs = [
        (f"{key[0]}::{key[1]}::{key[2]}", float(paired_values[key][baseline_id]), float(paired_values[key][treatment_id]))
        for key in paired_keys
    ]
    paired_statistics = {
        "attack_success": mcnemar_exact(baseline, treatment),
        "attack_success_cluster_bootstrap_treatment_minus_baseline": clustered_paired_bootstrap(
            cluster_pairs,
            iterations=10_000,
            seed=20260718,
        ),
    }

    stability_rows: list[dict[str, Any]] = []
    by_cluster: dict[tuple[str, str, str, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in cluster_rows:
        key = (
            str(row["suite"]),
            str(row["user_task_id"]),
            str(row["injection_task_id"]),
            str(row["cluster_role"]),
        )
        by_cluster[key][str(row["defense_id"])] = row
    for (suite, user_task, injection_task, role), values in sorted(by_cluster.items()):
        baseline_row = values[baseline_id]
        treatment_row = values[treatment_id]
        stability_rows.append(
            {
                "suite": suite,
                "user_task_id": user_task,
                "injection_task_id": injection_task,
                "cluster_role": role,
                "baseline_success_n": baseline_row["numerator"],
                "baseline_total": baseline_row["denominator"],
                "baseline_rate": baseline_row["value"],
                "m3_success_n": treatment_row["numerator"],
                "m3_total": treatment_row["denominator"],
                "m3_rate": treatment_row["value"],
                "baseline_stable_positive": int(baseline_row["numerator"]) >= 2,
                "m3_stable_block": int(treatment_row["numerator"]) == 0,
            }
        )

    _write_csv(output_dir / "suite_summary.csv", suite_summary)
    _write_csv(output_dir / "cluster_repeat_summary.csv", cluster_rows)
    _write_csv(output_dir / "candidate_stability.csv", stability_rows)
    _write_json(output_dir / "paired_statistics.json", paired_statistics)
    _plot(output_dir, suite_summary, cluster_rows)
    stable_positive = sum(1 for row in stability_rows if row["baseline_stable_positive"])
    stable_blocked = sum(
        1
        for row in stability_rows
        if row["baseline_stable_positive"] and row["m3_stable_block"]
    )
    result = {
        "status": "completed",
        "evidence_status": "diagnostic_not_formal_evidence",
        "input_manifest": str(manifest_path.resolve()),
        "paired_runs": len(paired_keys),
        "clusters": len(stability_rows),
        "stable_positive_baseline_clusters": stable_positive,
        "stable_positive_and_m3_blocked_clusters": stable_blocked,
        "result_eligible_for_formal_tables": False,
    }
    _write_json(output_dir / "analysis_manifest.json", result)
    lines = [
        "# AgentDojo selected-cluster repeat diagnostic",
        "",
        "Evidence status: **DIAGNOSTIC / NOT FORMAL EVIDENCE**.",
        "",
        f"- Paired attack runs: {len(paired_keys)}.",
        f"- Clusters: {len(stability_rows)}.",
        f"- Stable positive baseline clusters: {stable_positive}.",
        f"- Stable positive baseline clusters still blocked by m3_full: {stable_blocked}.",
        f"- McNemar p-value: {paired_statistics['attack_success']['p_value']:.4f}.",
        "",
        "This repeat is a stability diagnostic for the later formal protocol; it is not a confirmatory benchmark result.",
    ]
    (output_dir / "analysis.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()
    output_dir = args.output_dir or args.manifest.parent / "analysis"
    result = analyze(args.manifest, output_dir)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
