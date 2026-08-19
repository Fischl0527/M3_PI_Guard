"""Summarize the AgentDojo four-suite diagnostic screen.

The screen is used to choose candidates for a later frozen protocol.  Outputs
remain diagnostic and ineligible for formal paper tables.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from m3_eval.statistics import proportion_result


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ROOT = ROOT / "outputs" / "paper_upgrade_v1" / "agentdojo_native_matrix"
DEFAULT_OUTPUT = DEFAULT_ROOT / "four_suite_screen_summary_v1"
SCREEN_ID = "agentdojo_four_suite_screen_v1"


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


def _read_manifest(path: Path) -> dict[str, Any]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("status") != "completed":
        raise ValueError(f"screen manifest is not completed: {path}")
    if manifest.get("result_eligible_for_formal_tables") is not False:
        raise ValueError(f"screen manifest is not explicitly diagnostic-only: {path}")
    return manifest


def _group_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row["suite"]),
        str(row["user_task_id"]),
        str(row["injection_task_id"]),
        str(row["defense_id"]),
    )


def _suite_rows(manifest: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    suite = str(manifest["config"]["suite"])
    defenses = [str(item) for item in manifest["config"]["defense_ids"]]
    if defenses != ["no_defense", "m3_full"]:
        raise ValueError(f"unexpected defenses for diagnostic screen: {defenses}")
    completed = [row for row in manifest["jobs"] if row.get("status") == "completed"]
    injected = [row for row in completed if row.get("injection_task_id") is not None]
    clean = [row for row in completed if row.get("injection_task_id") is None]

    suite_summary: list[dict[str, Any]] = []
    for defense in defenses:
        defense_clean = [row for row in clean if row["defense_id"] == defense]
        defense_injected = [row for row in injected if row["defense_id"] == defense]
        metrics = (
            (
                "official_injection_success",
                defense_injected,
                lambda row: bool(row.get("official_injection_success")),
            ),
            ("clean_utility", defense_clean, lambda row: bool(row.get("utility"))),
            ("injected_utility", defense_injected, lambda row: bool(row.get("utility"))),
        )
        for metric, rows, predicate in metrics:
            count = sum(1 for row in rows if predicate(row))
            stats = proportion_result(count, len(rows))
            suite_summary.append(
                {
                    "suite": suite,
                    "defense_id": defense,
                    "metric": metric,
                    **stats,
                }
            )

    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in injected:
        grouped[_group_key(row)].append(row)
    cluster_rows: list[dict[str, Any]] = []
    for (suite_name, user_task_id, injection_task_id, defense), rows in sorted(grouped.items()):
        successes = sum(bool(row.get("official_injection_success")) for row in rows)
        stats = proportion_result(successes, len(rows))
        cluster_rows.append(
            {
                "suite": suite_name,
                "user_task_id": user_task_id,
                "injection_task_id": injection_task_id,
                "defense_id": defense,
                **stats,
            }
        )

    clean_by_task: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in clean:
        clean_by_task[(suite, str(row["user_task_id"]), str(row["defense_id"]))].append(row)
    utility_rows: list[dict[str, Any]] = []
    for (suite_name, user_task_id, defense), rows in sorted(clean_by_task.items()):
        successes = sum(bool(row.get("utility")) for row in rows)
        stats = proportion_result(successes, len(rows))
        utility_rows.append(
            {
                "suite": suite_name,
                "user_task_id": user_task_id,
                "defense_id": defense,
                **stats,
            }
        )
    return suite_summary, cluster_rows, utility_rows


def _candidate_security_clusters(cluster_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in cluster_rows:
        key = (str(row["suite"]), str(row["user_task_id"]), str(row["injection_task_id"]))
        grouped[key][str(row["defense_id"])] = row
    candidates: list[dict[str, Any]] = []
    for (suite, user_task, injection_task), values in sorted(grouped.items()):
        baseline = values.get("no_defense")
        treatment = values.get("m3_full")
        if not baseline or not treatment:
            continue
        if int(baseline["numerator"]) <= 0:
            continue
        candidates.append(
            {
                "suite": suite,
                "user_task_id": user_task,
                "injection_task_id": injection_task,
                "baseline_success_n": baseline["numerator"],
                "baseline_total": baseline["denominator"],
                "baseline_rate": baseline["value"],
                "m3_success_n": treatment["numerator"],
                "m3_total": treatment["denominator"],
                "m3_rate": treatment["value"],
                "candidate_reason": "positive_no_defense_official_injection_success",
            }
        )
    return candidates


def _candidate_utility_tasks(utility_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in utility_rows:
        grouped[(str(row["suite"]), str(row["user_task_id"]))][str(row["defense_id"])] = row
    candidates: list[dict[str, Any]] = []
    for (suite, user_task), values in sorted(grouped.items()):
        baseline = values.get("no_defense")
        treatment = values.get("m3_full")
        if not baseline or not treatment:
            continue
        passes = int(baseline["numerator"]) == int(baseline["denominator"]) and int(
            treatment["numerator"]
        ) == int(treatment["denominator"])
        candidates.append(
            {
                "suite": suite,
                "user_task_id": user_task,
                "no_defense_clean_utility": baseline["value"],
                "m3_full_clean_utility": treatment["value"],
                "candidate_utility_task": passes,
            }
        )
    return candidates


def _plot(output_dir: Path, suite_summary: list[dict[str, Any]]) -> None:
    import matplotlib.pyplot as plt
    import numpy as np

    lookup = {
        (row["suite"], row["defense_id"], row["metric"]): row
        for row in suite_summary
    }
    suites = sorted({str(row["suite"]) for row in suite_summary})
    defenses = ["no_defense", "m3_full"]
    metrics = [
        ("official_injection_success", "Injection success"),
        ("clean_utility", "Clean utility"),
        ("injected_utility", "Injected utility"),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.8), sharey=True)
    colors = {"no_defense": "#D39A2C", "m3_full": "#2F5D8C"}
    x = np.arange(len(suites))
    width = 0.34
    for axis, (metric, title) in zip(axes, metrics):
        for index, defense in enumerate(defenses):
            rows = [lookup[(suite, defense, metric)] for suite in suites]
            values = [float(row["value"] or 0.0) for row in rows]
            lows = [float(row["ci_low"] or 0.0) for row in rows]
            highs = [float(row["ci_high"] or 0.0) for row in rows]
            bars = axis.bar(
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
                axis.text(
                    bar.get_x() + bar.get_width() / 2,
                    min(1.04, value + 0.055),
                    f"{row['numerator']}/{row['denominator']}",
                    ha="center",
                    va="bottom",
                    fontsize=8,
                )
        axis.set_title(title, loc="left", fontweight="bold")
        axis.set_xticks(x, suites, rotation=20, ha="right")
        axis.set_ylim(0, 1.08)
        axis.grid(axis="y", color="#D9DEE2", linewidth=0.7)
    axes[0].set_ylabel("Proportion")
    axes[1].legend(frameon=False, loc="upper center", ncol=2)
    fig.suptitle("AgentDojo four-suite diagnostic screen", x=0.06, ha="left", fontsize=15, fontweight="bold")
    fig.text(
        0.06,
        0.91,
        "qwen3:4b-instruct; important-instructions attack; Wilson 95% intervals; diagnostic screen only",
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
    fig.savefig(output_dir / "agentdojo_four_suite_screen.png", dpi=200, bbox_inches="tight")
    fig.savefig(output_dir / "agentdojo_four_suite_screen.svg", bbox_inches="tight")
    plt.close(fig)


def analyze(manifests: list[Path], output_dir: Path) -> dict[str, Any]:
    suite_summary: list[dict[str, Any]] = []
    cluster_rows: list[dict[str, Any]] = []
    utility_rows: list[dict[str, Any]] = []
    manifest_records: list[dict[str, Any]] = []
    for manifest_path in manifests:
        manifest = _read_manifest(manifest_path)
        manifest_records.append(
            {
                "manifest": str(manifest_path.resolve()),
                "suite": manifest["config"]["suite"],
                "total_jobs": manifest["total_jobs"],
                "completed_jobs": manifest["completed_jobs"],
                "failed_jobs": manifest["failed_jobs"],
                "config_sha256": manifest["config_sha256"],
            }
        )
        suite_part, cluster_part, utility_part = _suite_rows(manifest)
        suite_summary.extend(suite_part)
        cluster_rows.extend(cluster_part)
        utility_rows.extend(utility_part)

    security_candidates = _candidate_security_clusters(cluster_rows)
    utility_candidates = _candidate_utility_tasks(utility_rows)
    _write_csv(output_dir / "suite_summary.csv", suite_summary)
    _write_csv(output_dir / "cluster_attack_success.csv", cluster_rows)
    _write_csv(output_dir / "candidate_security_clusters.csv", security_candidates)
    _write_csv(output_dir / "clean_utility_by_task.csv", utility_rows)
    _write_csv(output_dir / "candidate_utility_tasks.csv", utility_candidates)
    _plot(output_dir, suite_summary)
    result = {
        "status": "completed",
        "screen_id": SCREEN_ID,
        "evidence_status": "diagnostic_not_formal_evidence",
        "result_eligible_for_formal_tables": False,
        "manifests": manifest_records,
        "suite_count": len(manifest_records),
        "security_candidate_clusters": len(security_candidates),
        "utility_candidate_tasks": sum(
            1 for row in utility_candidates if row["candidate_utility_task"]
        ),
    }
    _write_json(output_dir / "screen_summary.json", result)
    lines = [
        "# AgentDojo four-suite diagnostic screen summary",
        "",
        "Evidence status: **DIAGNOSTIC / NOT FORMAL EVIDENCE**.",
        "",
        f"- Completed suites: {len(manifest_records)}.",
        f"- Candidate security clusters: {len(security_candidates)}.",
        f"- Candidate clean-utility tasks: {result['utility_candidate_tasks']}.",
        "- Formal eligibility: false.",
        "",
        "The screen identifies candidate clusters for a later frozen public-benchmark protocol. It does not support paper-level effectiveness claims.",
    ]
    (output_dir / "screen_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifests", nargs="+", type=Path)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = analyze(args.manifests, args.output_dir)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
