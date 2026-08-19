"""Combine selected-cluster M3 and AgentDojo prompt-baseline diagnostics."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from m3_eval.statistics import (
    clustered_paired_bootstrap,
    mcnemar_exact,
    proportion_result,
)


DEFAULT_DEFENSE_ORDER = [
    "no_defense",
    "agentdojo_repeat_user_prompt",
    "agentdojo_spotlighting_with_delimiting",
    "m3_full",
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


def _load_completed_manifest(path: Path) -> dict[str, Any]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("status") != "completed":
        raise ValueError(f"manifest is not completed: {path}")
    if manifest.get("result_eligible_for_formal_tables") is not False:
        raise ValueError(f"manifest is not explicitly diagnostic-only: {path}")
    return manifest


def _completed_rows(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in manifest.get("jobs", []) if row.get("status") == "completed"]


def _job_key(row: dict[str, Any]) -> tuple[str, str, str, int]:
    return (
        str(row["suite"]),
        str(row["user_task_id"]),
        str(row["injection_task_id"]),
        int(row.get("replicate_id") or 0),
    )


def _cluster_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row["suite"]),
        str(row["user_task_id"]),
        str(row["injection_task_id"]),
        str(row.get("cluster_role", "unknown")),
    )


def _defense_order(rows: Iterable[dict[str, Any]]) -> list[str]:
    present = {str(row["defense_id"]) for row in rows}
    ordered = [defense for defense in DEFAULT_DEFENSE_ORDER if defense in present]
    ordered.extend(sorted(present - set(ordered)))
    return ordered


def _suite_summary(rows: list[dict[str, Any]], defenses: list[str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for suite in sorted({str(row["suite"]) for row in rows}):
        for defense in defenses:
            subset = [
                row
                for row in rows
                if str(row["suite"]) == suite and str(row["defense_id"]) == defense
            ]
            if not subset:
                continue
            count = sum(bool(row.get("official_injection_success")) for row in subset)
            out.append(
                {
                    "suite": suite,
                    "defense_id": defense,
                    "metric": "official_injection_success",
                    **proportion_result(count, len(subset)),
                }
            )
    return out


def _cluster_summary(rows: list[dict[str, Any]], defenses: list[str]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        suite, user_task, injection_task, role = _cluster_key(row)
        grouped[(suite, user_task, injection_task, role, str(row["defense_id"]))].append(row)
    out: list[dict[str, Any]] = []
    for (suite, user_task, injection_task, role, defense), subset in sorted(grouped.items()):
        if defense not in defenses:
            continue
        count = sum(bool(row.get("official_injection_success")) for row in subset)
        out.append(
            {
                "suite": suite,
                "user_task_id": user_task,
                "injection_task_id": injection_task,
                "cluster_role": role,
                "defense_id": defense,
                **proportion_result(count, len(subset)),
            }
        )
    return out


def _paired_statistics(rows: list[dict[str, Any]], defenses: list[str]) -> dict[str, Any]:
    values: dict[tuple[str, str, str, int], dict[str, bool]] = defaultdict(dict)
    for row in rows:
        values[_job_key(row)][str(row["defense_id"])] = bool(
            row.get("official_injection_success")
        )
    result: dict[str, Any] = {}
    for left_index, left in enumerate(defenses):
        for right in defenses[left_index + 1 :]:
            paired_keys = sorted(
                key for key, row_values in values.items() if {left, right} <= set(row_values)
            )
            left_values = [values[key][left] for key in paired_keys]
            right_values = [values[key][right] for key in paired_keys]
            cluster_pairs = [
                (
                    f"{key[0]}::{key[1]}::{key[2]}",
                    float(values[key][left]),
                    float(values[key][right]),
                )
                for key in paired_keys
            ]
            result[f"{left}__vs__{right}"] = {
                "left_defense_id": left,
                "right_defense_id": right,
                "paired_n": len(paired_keys),
                "mcnemar": mcnemar_exact(left_values, right_values),
                "cluster_bootstrap_right_minus_left": clustered_paired_bootstrap(
                    cluster_pairs,
                    iterations=10_000,
                    seed=20260718,
                ),
            }
    return result


def _stability_rows(cluster_rows: list[dict[str, Any]], defenses: list[str]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in cluster_rows:
        grouped[_cluster_key(row)][str(row["defense_id"])] = row
    out: list[dict[str, Any]] = []
    for (suite, user_task, injection_task, role), by_defense in sorted(grouped.items()):
        item: dict[str, Any] = {
            "suite": suite,
            "user_task_id": user_task,
            "injection_task_id": injection_task,
            "cluster_role": role,
        }
        for defense in defenses:
            row = by_defense.get(defense)
            item[f"{defense}_success_n"] = row["numerator"] if row else ""
            item[f"{defense}_total"] = row["denominator"] if row else ""
            item[f"{defense}_rate"] = row["value"] if row else ""
        baseline = by_defense.get("no_defense")
        m3 = by_defense.get("m3_full")
        item["baseline_stable_positive"] = (
            bool(baseline) and int(baseline["numerator"]) >= 2
        )
        item["m3_stable_block"] = bool(m3) and int(m3["numerator"]) == 0
        out.append(item)
    return out


def _plot(output_dir: Path, suite_rows: list[dict[str, Any]], defenses: list[str]) -> None:
    import matplotlib.pyplot as plt
    import numpy as np

    labels = {
        "no_defense": "No defense",
        "agentdojo_repeat_user_prompt": "Repeat user\nprompt",
        "agentdojo_spotlighting_with_delimiting": "Spotlighting\n<< >>",
        "m3_full": "M3 full",
    }
    colors = {
        "no_defense": "#D39A2C",
        "agentdojo_repeat_user_prompt": "#8E7CC3",
        "agentdojo_spotlighting_with_delimiting": "#76A5AF",
        "m3_full": "#2F5D8C",
    }
    suites = sorted({str(row["suite"]) for row in suite_rows})
    lookup = {
        (row["suite"], row["defense_id"]): row
        for row in suite_rows
        if row["metric"] == "official_injection_success"
    }
    fig, ax = plt.subplots(figsize=(12.8, 5.8))
    x = np.arange(len(suites))
    width = min(0.18, 0.78 / max(1, len(defenses)))
    offsets = np.linspace(
        -width * (len(defenses) - 1) / 2,
        width * (len(defenses) - 1) / 2,
        len(defenses),
    )
    for offset, defense in zip(offsets, defenses):
        rows = [lookup.get((suite, defense)) for suite in suites]
        values = [float(row["value"] or 0.0) if row else 0.0 for row in rows]
        lows = [float(row["ci_low"] or 0.0) if row else 0.0 for row in rows]
        highs = [float(row["ci_high"] or 0.0) if row else 0.0 for row in rows]
        bars = ax.bar(
            x + offset,
            values,
            width,
            color=colors.get(defense, "#7F8C8D"),
            edgecolor="#27323A",
            linewidth=0.65,
            label=labels.get(defense, defense),
            yerr=[
                [max(0.0, value - low) for value, low in zip(values, lows)],
                [max(0.0, high - value) for value, high in zip(values, highs)],
            ],
            capsize=2,
        )
        for bar, row, value, high in zip(bars, rows, values, highs):
            if not row:
                continue
            if value >= 0.16:
                label_y = max(0.035, value - 0.075)
                label_color = "white"
                vertical_align = "top"
            else:
                label_y = min(1.075, max(0.035, high + 0.035))
                label_color = "#27323A"
                vertical_align = "bottom"
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                label_y,
                f"{row['numerator']}/{row['denominator']}",
                ha="center",
                va=vertical_align,
                fontsize=7,
                color=label_color,
                fontweight="bold" if value >= 0.16 else "normal",
                rotation=90 if len(defenses) > 3 else 0,
            )
    fig.suptitle(
        "AgentDojo selected-cluster prompt baseline diagnostic",
        x=0.06,
        y=0.975,
        ha="left",
        fontsize=15,
        fontweight="bold",
    )
    ax.set_ylabel("Official injection success")
    ax.set_xticks(x, suites)
    ax.set_ylim(0, 1.12)
    ax.grid(axis="y", color="#D9DEE2", linewidth=0.7)
    ax.legend(frameon=False, ncols=min(4, len(defenses)), loc="upper right")
    fig.text(
        0.06,
        0.905,
        "Exact selected clusters; qwen3:4b-instruct; 3 seeds; diagnostic only",
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
    fig.savefig(output_dir / "prompt_baseline_comparison.png", dpi=200, bbox_inches="tight")
    fig.savefig(output_dir / "prompt_baseline_comparison.svg", bbox_inches="tight")
    plt.close(fig)


def analyze(manifest_paths: list[Path], output_dir: Path) -> dict[str, Any]:
    manifests = [_load_completed_manifest(path) for path in manifest_paths]
    rows: list[dict[str, Any]] = []
    for manifest in manifests:
        rows.extend(_completed_rows(manifest))
    expected_total = sum(int(manifest.get("total_jobs", 0)) for manifest in manifests)
    if len(rows) != expected_total:
        raise ValueError(
            f"completed row count mismatch: completed={len(rows)} expected={expected_total}"
        )
    defenses = _defense_order(rows)
    suite_rows = _suite_summary(rows, defenses)
    cluster_rows = _cluster_summary(rows, defenses)
    stability = _stability_rows(cluster_rows, defenses)
    paired = _paired_statistics(rows, defenses)
    _write_csv(output_dir / "suite_summary.csv", suite_rows)
    _write_csv(output_dir / "cluster_condition_summary.csv", cluster_rows)
    _write_csv(output_dir / "cluster_stability.csv", stability)
    _write_json(output_dir / "paired_statistics.json", paired)
    _plot(output_dir, suite_rows, defenses)
    result = {
        "status": "completed",
        "evidence_status": "diagnostic_not_formal_benchmark",
        "result_eligible_for_formal_tables": False,
        "input_manifests": [str(path.resolve()) for path in manifest_paths],
        "manifest_count": len(manifests),
        "total_jobs": expected_total,
        "completed_jobs": len(rows),
        "defense_ids": defenses,
        "suite_summary": suite_rows,
        "paired_statistics_path": str((output_dir / "paired_statistics.json").resolve()),
        "chart_png": str((output_dir / "prompt_baseline_comparison.png").resolve()),
        "chart_svg": str((output_dir / "prompt_baseline_comparison.svg").resolve()),
    }
    _write_json(output_dir / "analysis_manifest.json", result)
    lines = [
        "# AgentDojo selected-cluster prompt baseline diagnostic",
        "",
        "Evidence status: diagnostic only; not formal benchmark evidence.",
        "",
        f"- Input manifests: {len(manifests)}",
        f"- Completed jobs: {len(rows)}/{expected_total}",
        f"- Conditions: {', '.join(defenses)}",
        "",
        "## Suite-level official injection success",
        "",
        "| Suite | Defense | Success | Rate | Wilson 95% CI |",
        "|---|---|---:|---:|---:|",
    ]
    for row in suite_rows:
        lines.append(
            f"| {row['suite']} | {row['defense_id']} | "
            f"{row['numerator']}/{row['denominator']} | "
            f"{float(row['value']):.3f} | "
            f"[{float(row['ci_low']):.3f}, {float(row['ci_high']):.3f}] |"
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "This analysis joins diagnostic selected-cluster runs. It must not be used as",
            "a formal public-benchmark result until the full frozen AgentDojo protocol",
            "and strong-baseline compatibility rules are finalized.",
            "",
        ]
    )
    (output_dir / "analysis.md").write_text("\n".join(lines), encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifests", nargs="+", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    analyze(args.manifests, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
