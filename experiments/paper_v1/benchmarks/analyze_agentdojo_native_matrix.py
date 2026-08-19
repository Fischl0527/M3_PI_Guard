"""Analyze a diagnostic AgentDojo native matrix with paired uncertainty.

The output is deliberately watermarked and cannot become formal evidence merely
by rerunning this script; formal eligibility is inherited from the input
manifest and is currently false.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from m3_eval.statistics import (
    clustered_paired_bootstrap,
    mcnemar_exact,
    proportion_result,
)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


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


def analyze(manifest_path: Path, output_dir: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "completed":
        raise ValueError("matrix must be completed before analysis")
    rows = [row for row in manifest["jobs"] if row.get("status") == "completed"]
    defenses = list(manifest["config"]["defense_ids"])
    if len(defenses) != 2:
        raise ValueError("paired diagnostic analysis currently requires exactly two defenses")
    baseline_id, treatment_id = defenses
    table_rows: list[dict[str, Any]] = []
    decision_counts: Counter[tuple[str, str]] = Counter()
    rule_counts: Counter[tuple[str, str]] = Counter()
    pair_attack_values: dict[tuple[str, str, int], dict[str, bool]] = defaultdict(dict)
    pair_utility_values: dict[tuple[str, str, int], dict[str, bool]] = defaultdict(dict)
    cluster_pairs: list[tuple[str, float, float]] = []

    for row in rows:
        defense = str(row["defense_id"])
        injection = str(row.get("injection_task_id") or "clean")
        seed = int(row["seed"])
        key = (str(row["user_task_id"]), injection, seed)
        is_injected = row.get("injection_task_id") is not None
        attack = bool(row.get("official_injection_success", False)) if is_injected else False
        utility = bool(row["utility"])
        if is_injected:
            pair_attack_values[key][defense] = attack
        pair_utility_values[key][defense] = utility
        job_key = str(row["job_key"])
        audit_path = manifest_path.parent / "jobs" / job_key / "audit.jsonl"
        for audit in _read_jsonl(audit_path):
            decision = str(audit["guard_decision"]["decision"])
            decision_counts[(defense, decision)] += 1
            for rule in audit["guard_decision"].get("violated_rules", []):
                rule_counts[(defense, str(rule))] += 1
        table_rows.append(
            {
                "job_key": job_key,
                "defense_id": defense,
                "user_task_id": row["user_task_id"],
                "injection_task_id": row.get("injection_task_id"),
                "seed": seed,
                "utility": int(utility),
                "official_injection_success": int(attack),
                "attack_blocked": int(bool(row.get("attack_blocked"))),
                "audit_rows": int(row["audit_rows"]),
                "elapsed_ms": float(row["elapsed_ms"]),
            }
        )

    attack_paired_keys = sorted(
        key for key, values in pair_attack_values.items() if set(values) == set(defenses)
    )
    utility_paired_keys = sorted(
        key for key, values in pair_utility_values.items() if set(values) == set(defenses)
    )
    clean_utility_keys = [key for key in utility_paired_keys if key[1] == "clean"]
    injected_utility_keys = [key for key in utility_paired_keys if key[1] != "clean"]
    baseline_attack = [pair_attack_values[key][baseline_id] for key in attack_paired_keys]
    treatment_attack = [pair_attack_values[key][treatment_id] for key in attack_paired_keys]
    baseline_clean_utility = [pair_utility_values[key][baseline_id] for key in clean_utility_keys]
    treatment_clean_utility = [pair_utility_values[key][treatment_id] for key in clean_utility_keys]
    baseline_injected_utility = [pair_utility_values[key][baseline_id] for key in injected_utility_keys]
    treatment_injected_utility = [pair_utility_values[key][treatment_id] for key in injected_utility_keys]
    for key in attack_paired_keys:
        cluster = f"{key[0]}::{key[1]}"
        cluster_pairs.append(
            (
                cluster,
                float(pair_attack_values[key][baseline_id]),
                float(pair_attack_values[key][treatment_id]),
            )
        )

    summary_rows: list[dict[str, Any]] = []
    for defense in defenses:
        subset = [row for row in table_rows if row["defense_id"] == defense]
        injected_subset = [row for row in subset if row.get("injection_task_id")]
        clean_subset = [row for row in subset if not row.get("injection_task_id")]
        metric_specs = (
            ("official_injection_success", injected_subset, "official_injection_success"),
            ("clean_utility", clean_subset, "utility"),
            ("injected_utility", injected_subset, "utility"),
        )
        for metric, metric_subset, source_field in metric_specs:
            successes = sum(int(row[source_field]) for row in metric_subset)
            stats = proportion_result(successes, len(metric_subset))
            summary_rows.append(
                {
                    "defense_id": defense,
                    "metric": metric,
                    **stats,
                }
            )

    paired = {
        "attack_success": mcnemar_exact(baseline_attack, treatment_attack),
        "clean_utility": mcnemar_exact(baseline_clean_utility, treatment_clean_utility),
        "injected_utility": mcnemar_exact(
            baseline_injected_utility,
            treatment_injected_utility,
        ),
        "attack_success_cluster_bootstrap_treatment_minus_baseline": (
            clustered_paired_bootstrap(
                cluster_pairs,
                iterations=10_000,
                seed=20260718,
            )
        ),
    }
    pair_level: list[dict[str, Any]] = []
    grouped: dict[str, dict[str, list[int]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for key in attack_paired_keys:
        cluster = f"{key[0]}::{key[1]}"
        for defense in defenses:
            grouped[cluster][defense].append(
                int(pair_attack_values[key][defense])
            )
    for cluster, values in sorted(grouped.items()):
        pair_level.append(
            {
                "task_injection_pair": cluster,
                **{
                    defense: sum(values[defense]) / len(values[defense])
                    for defense in defenses
                },
            }
        )

    decision_rows = [
        {"defense_id": defense, "decision": decision, "count": count}
        for (defense, decision), count in sorted(decision_counts.items())
    ]
    rule_rows = [
        {"defense_id": defense, "violated_rule": rule, "count": count}
        for (defense, rule), count in sorted(rule_counts.items())
    ]
    _write_csv(output_dir / "job_results.csv", table_rows)
    _write_csv(output_dir / "defense_summary.csv", summary_rows)
    _write_csv(output_dir / "pair_level_attack_success.csv", pair_level)
    _write_csv(output_dir / "decision_counts.csv", decision_rows)
    _write_csv(output_dir / "violated_rule_counts.csv", rule_rows)
    _write_json(output_dir / "paired_statistics.json", paired)

    _plot(
        output_dir=output_dir,
        summary_rows=summary_rows,
        pair_level=pair_level,
        defenses=defenses,
    )

    attack_summary = {
        (row["defense_id"], row["metric"]): row for row in summary_rows
    }
    baseline_attack_row = attack_summary[(baseline_id, "official_injection_success")]
    treatment_attack_row = attack_summary[(treatment_id, "official_injection_success")]
    baseline_clean_utility_row = attack_summary[(baseline_id, "clean_utility")]
    treatment_clean_utility_row = attack_summary[(treatment_id, "clean_utility")]
    baseline_injected_utility_row = attack_summary[(baseline_id, "injected_utility")]
    treatment_injected_utility_row = attack_summary[(treatment_id, "injected_utility")]
    bootstrap = paired[
        "attack_success_cluster_bootstrap_treatment_minus_baseline"
    ]
    concentrated = [
        row["task_injection_pair"]
        for row in pair_level
        if row[baseline_id] > 0 or row[treatment_id] > 0
    ]
    analysis = f"""# AgentDojo native repeated diagnostic analysis

## Evidence boundary

- Status: **DIAGNOSTIC / NOT FORMAL EVIDENCE**.
- Scope: `{manifest['config']['suite']}`, {len(pair_level)} user-task × injection clusters, {len(attack_paired_keys)} paired attack runs, model `{manifest['config']['model']}`.
- Attack: `{manifest['config']['attack_name']}`. This is a development slice, not the frozen 629-case AgentDojo evaluation.

## Results

- `{baseline_id}` official injection success: {baseline_attack_row['numerator']}/{baseline_attack_row['denominator']} = {100 * baseline_attack_row['value']:.1f}% (Wilson 95% CI {100 * baseline_attack_row['ci_low']:.1f}%–{100 * baseline_attack_row['ci_high']:.1f}%).
- `{treatment_id}` official injection success: {treatment_attack_row['numerator']}/{treatment_attack_row['denominator']} = {100 * treatment_attack_row['value']:.1f}% (Wilson 95% CI {100 * treatment_attack_row['ci_low']:.1f}%–{100 * treatment_attack_row['ci_high']:.1f}%).
- Paired risk difference (`{treatment_id}` − `{baseline_id}`): {100 * bootstrap['estimate']:.1f} percentage points; task/injection-cluster bootstrap 95% CI {100 * bootstrap['ci_low']:.1f} to {100 * bootstrap['ci_high']:.1f} percentage points.
- Exact paired McNemar p-value: {paired['attack_success']['p_value']:.4f}; discordant pairs baseline-only={paired['attack_success']['baseline_only_event']}, treatment-only={paired['attack_success']['treatment_only_event']}.
- Clean utility: `{baseline_id}` {baseline_clean_utility_row['numerator']}/{baseline_clean_utility_row['denominator']} = {100 * baseline_clean_utility_row['value']:.1f}%; `{treatment_id}` {treatment_clean_utility_row['numerator']}/{treatment_clean_utility_row['denominator']} = {100 * treatment_clean_utility_row['value']:.1f}%.
- Injected utility: `{baseline_id}` {baseline_injected_utility_row['numerator']}/{baseline_injected_utility_row['denominator']} = {100 * baseline_injected_utility_row['value']:.1f}%; `{treatment_id}` {treatment_injected_utility_row['numerator']}/{treatment_injected_utility_row['denominator']} = {100 * treatment_injected_utility_row['value']:.1f}%.

## Interpretation

The point estimate favors `{treatment_id}`, but the cluster-bootstrap interval includes zero and the exact paired test is not significant at 0.05. All observed injection successes are concentrated in {len(concentrated)} of {len(pair_level)} task/injection clusters: {', '.join(concentrated) if concentrated else 'none'}. The result is useful for validating the native chain and choosing the formal protocol; it is not strong enough for a paper effectiveness claim.
"""
    (output_dir / "analysis.md").write_text(analysis, encoding="utf-8")
    result = {
        "status": "completed",
        "evidence_status": "diagnostic_not_formal_evidence",
        "input_manifest": str(manifest_path.resolve()),
        "paired_attack_runs": len(attack_paired_keys),
        "paired_clean_utility_runs": len(clean_utility_keys),
        "paired_injected_utility_runs": len(injected_utility_keys),
        "clusters": len(pair_level),
        "summary_rows": len(summary_rows),
        "result_eligible_for_formal_tables": False,
    }
    _write_json(output_dir / "analysis_manifest.json", result)
    return result


def _plot(
    *,
    output_dir: Path,
    summary_rows: list[dict[str, Any]],
    pair_level: list[dict[str, Any]],
    defenses: list[str],
) -> None:
    import matplotlib.pyplot as plt
    import numpy as np

    palette = {defenses[0]: "#D39A2C", defenses[1]: "#2F5D8C"}
    lookup = {(row["defense_id"], row["metric"]): row for row in summary_rows}
    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.5), gridspec_kw={"width_ratios": [1, 1.35]})
    metrics = ["official_injection_success", "injected_utility"]
    labels = ["Official injection success", "Injected utility"]
    x = np.arange(len(metrics))
    width = 0.34
    for index, defense in enumerate(defenses):
        values = [float(lookup[(defense, metric)]["value"] or 0.0) for metric in metrics]
        lows = [float(lookup[(defense, metric)]["ci_low"] or 0.0) for metric in metrics]
        highs = [float(lookup[(defense, metric)]["ci_high"] or 0.0) for metric in metrics]
        positions = x + (index - 0.5) * width
        bars = axes[0].bar(
            positions,
            values,
            width,
            color=palette[defense],
            edgecolor="#27323A",
            linewidth=0.8,
            label=defense,
            yerr=[
                [max(0.0, value - low) for value, low in zip(values, lows)],
                [max(0.0, high - value) for value, high in zip(values, highs)],
            ],
            capsize=4,
        )
        for bar, metric, value in zip(bars, metrics, values):
            row = lookup[(defense, metric)]
            axes[0].text(
                bar.get_x() + bar.get_width() / 2,
                min(0.98, value + 0.07),
                f"{row['numerator']}/{row['denominator']}\n{100 * value:.1f}%",
                ha="center",
                va="bottom",
                fontsize=9,
            )
    axes[0].set_xticks(x, labels)
    axes[0].set_ylim(0, 1.0)
    axes[0].set_ylabel("Proportion")
    axes[0].set_title("Aggregate outcomes", loc="left", fontweight="bold")
    axes[0].grid(axis="y", color="#D9DEE2", linewidth=0.7)
    axes[0].legend(frameon=False, loc="upper center")

    matrix = np.array(
        [[row[defense] for row in pair_level] for defense in defenses], dtype=float
    )
    image = axes[1].imshow(matrix, cmap="Blues", vmin=0, vmax=1, aspect="auto")
    axes[1].set_yticks(range(len(defenses)), defenses)
    axes[1].set_xticks(
        range(len(pair_level)),
        [row["task_injection_pair"].replace("user_task_", "u").replace("::injection_task_", "/i") for row in pair_level],
        rotation=45,
        ha="right",
    )
    axes[1].set_title("Injection success by task/injection cluster", loc="left", fontweight="bold")
    axes[1].set_xlabel("Cluster; cell = mean across repeats")
    for y in range(matrix.shape[0]):
        for x_index in range(matrix.shape[1]):
            value = matrix[y, x_index]
            axes[1].text(
                x_index,
                y,
                f"{value:.2f}",
                ha="center",
                va="center",
                color="white" if value > 0.55 else "#1F2A32",
                fontsize=8,
            )
    colorbar = fig.colorbar(image, ax=axes[1], fraction=0.035, pad=0.02)
    colorbar.set_label("Injection success rate")

    fig.suptitle("AgentDojo native repeated diagnostic", x=0.06, ha="left", fontsize=15, fontweight="bold")
    fig.text(
        0.06,
        0.92,
        "Important-instructions attack; qwen3:4b-instruct; Wilson 95% intervals; diagnostic slice only",
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
    fig.tight_layout(rect=(0.03, 0.06, 0.98, 0.89))
    output_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_dir / "diagnostic_comparison.png", dpi=200, bbox_inches="tight")
    fig.savefig(output_dir / "diagnostic_comparison.svg", bbox_inches="tight")
    plt.close(fig)


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
