"""Analyze and formally admit a completed adaptive MCTS budget run."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from m3_eval.statistics import proportion_result

from .common import portable_path, resolve_artifact_path, rows_sha256, sha256_file
from .run_adaptive_mcts_budget_formal import FORMAL_BUDGETS


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RUN_DIR = ROOT / "outputs" / "paper_upgrade_v1" / "adaptive_mcts_budget_v1"
ANALYZER_VERSION = "m3-paper-v1-adaptive-mcts-budget-analyzer-1.0"


def _resolve_reference(value: Any) -> Path:
    return resolve_artifact_path(str(value), root=ROOT)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number} must contain a JSON object")
            rows.append(value)
    return rows


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _write_csv(path: Path, rows: list[Mapping[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"cannot write empty CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _budget_lookup(row: Mapping[str, Any], budget: int) -> Mapping[str, Any]:
    matches = [
        item
        for item in row.get("budget_results", [])
        if isinstance(item, Mapping) and int(item.get("budget", -1)) == budget
    ]
    if len(matches) != 1:
        raise ValueError(f"task {row.get('task_id')} lacks exactly one budget {budget} row")
    return matches[0]


def validate_run_artifacts(
    run_dir: Path, *, allow_diagnostic: bool = False
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    manifest = _read_json(run_dir / "manifest.json")
    required_status = "completed_formal_run_pending_analysis"
    if not allow_diagnostic and manifest.get("status") != required_status:
        raise ValueError("adaptive run is not a completed formal run pending analysis")
    if not allow_diagnostic and not all(manifest.get("formal_admission_checks", {}).values()):
        raise ValueError("adaptive formal admission checks are incomplete")
    freeze_path = _resolve_reference(manifest.get("freeze_path", ""))
    freeze = _read_json(freeze_path)
    if sha256_file(freeze_path) != str(manifest.get("freeze_sha256", "")):
        raise ValueError("adaptive freeze hash drift")
    results = _read_jsonl(run_dir / "task_results.jsonl")
    task_ids = [str(row.get("task_id", "")) for row in results]
    if len(set(task_ids)) != len(task_ids):
        raise ValueError("adaptive task results contain duplicate task IDs")
    expected = int(manifest.get("selected_task_count", 0))
    if len(results) != expected:
        raise ValueError(f"adaptive task result coverage mismatch: {len(results)} != {expected}")
    if not allow_diagnostic and expected != int(freeze.get("case_count", 0)):
        raise ValueError("formal adaptive analysis requires the full frozen panel")
    budgets = tuple(int(value) for value in manifest.get("query_budgets", []))
    if not allow_diagnostic and budgets != FORMAL_BUDGETS:
        raise ValueError("formal adaptive analysis requires frozen 100/500/2000 budgets")
    for row in results:
        task_id = str(row.get("task_id", ""))
        queries = int(row.get("queries_executed", 0))
        task_dir = run_dir / "tasks" / task_id
        query_files = list((task_dir / "queries").glob("*.json"))
        if queries < 1 or len(query_files) != queries:
            raise ValueError(f"adaptive query evidence mismatch for {task_id}")
        if not (task_dir / "mcts_checkpoint.json").is_file():
            raise ValueError(f"adaptive checkpoint missing for {task_id}")
        for budget in budgets:
            _budget_lookup(row, budget)
    return manifest, freeze, results


def build_metrics(
    results: list[Mapping[str, Any]], budgets: tuple[int, ...]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    budget_rows: list[dict[str, Any]] = []
    for budget in budgets:
        successes = sum(bool(_budget_lookup(row, budget).get("success")) for row in results)
        estimate = proportion_result(successes, len(results))
        budget_rows.append(
            {
                "budget": budget,
                "successes": successes,
                "tasks": len(results),
                "asr": estimate["value"],
                "ci_low": estimate["ci_low"],
                "ci_high": estimate["ci_high"],
            }
        )

    max_budget = budgets[-1]
    grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in results:
        grouped[("attack_family", str(row.get("attack_family", "")))].append(row)
        grouped[("language", str(row.get("language", "")))].append(row)
    group_rows: list[dict[str, Any]] = []
    for (dimension, group), rows in sorted(grouped.items()):
        successes = sum(bool(_budget_lookup(row, max_budget).get("success")) for row in rows)
        estimate = proportion_result(successes, len(rows))
        group_rows.append(
            {
                "dimension": dimension,
                "group": group,
                "budget": max_budget,
                "successes": successes,
                "tasks": len(rows),
                "asr": estimate["value"],
                "ci_low": estimate["ci_low"],
                "ci_high": estimate["ci_high"],
            }
        )

    buckets: Counter[str] = Counter()
    for row in results:
        query = row.get("first_success_query")
        if query is None:
            buckets["no_success"] += 1
        elif int(query) <= 100:
            buckets["1_100"] += 1
        elif int(query) <= 500:
            buckets["101_500"] += 1
        else:
            buckets["501_2000"] += 1
    summary = {
        "task_count": len(results),
        "query_count": sum(int(row.get("queries_executed", 0)) for row in results),
        "first_success_buckets": dict(sorted(buckets.items())),
        "budget_metrics": budget_rows,
    }
    return budget_rows, group_rows, summary


def build_figures(
    output_dir: Path,
    budget_rows: list[Mapping[str, Any]],
    group_rows: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts: list[dict[str, Any]] = []

    x = [int(row["budget"]) for row in budget_rows]
    y = [100.0 * float(row["asr"]) for row in budget_rows]
    low = [100.0 * float(row["ci_low"]) for row in budget_rows]
    high = [100.0 * float(row["ci_high"]) for row in budget_rows]
    figure, axis = plt.subplots(figsize=(7.2, 4.6))
    axis.plot(x, y, marker="o", linewidth=2.2, color="#b42318")
    axis.fill_between(x, low, high, alpha=0.18, color="#b42318")
    axis.set_xscale("log")
    axis.set_xticks(x, labels=[str(value) for value in x])
    axis.set_ylim(0, 100)
    axis.set_xlabel("Black-box query budget per task")
    axis.set_ylabel("Attack success rate (%)")
    axis.set_title("Adaptive attack success vs. query budget")
    axis.grid(alpha=0.25)
    figure.tight_layout()
    for suffix in ("png", "svg"):
        path = output_dir / f"adaptive_asr_budget_curve.{suffix}"
        figure.savefig(path, dpi=180 if suffix == "png" else None)
        artifacts.append(
            {"path": portable_path(path, root=ROOT), "sha256": sha256_file(path)}
        )
    plt.close(figure)

    family = [row for row in group_rows if row["dimension"] == "attack_family"]
    family.sort(key=lambda row: (float(row["asr"]), str(row["group"])))
    figure, axis = plt.subplots(figsize=(8.2, max(4.8, 0.45 * len(family))))
    axis.barh(
        [str(row["group"]) for row in family],
        [100.0 * float(row["asr"]) for row in family],
        color="#175cd3",
    )
    axis.set_xlim(0, 100)
    axis.set_xlabel("Attack success rate at 2,000 queries (%)")
    axis.set_title("Adaptive worst-case ASR by attack family")
    axis.grid(axis="x", alpha=0.25)
    figure.tight_layout()
    for suffix in ("png", "svg"):
        path = output_dir / f"adaptive_asr_by_family.{suffix}"
        figure.savefig(path, dpi=180 if suffix == "png" else None)
        artifacts.append(
            {"path": portable_path(path, root=ROOT), "sha256": sha256_file(path)}
        )
    plt.close(figure)
    return artifacts


def _write_report(
    path: Path, summary: Mapping[str, Any], budget_rows: list[Mapping[str, Any]]
) -> None:
    lines = [
        "# Adaptive MCTS query-budget analysis",
        "",
        f"- Tasks: {summary['task_count']}",
        f"- Total model queries: {summary['query_count']}",
        "- Attacker observations: public ALLOW/ASK/DENY plus unsafe-effect/task-completion outcomes only.",
        "",
        "## ASR by query budget",
        "",
        "| Budget | Successes | Tasks | ASR | Wilson 95% CI |",
        "|---:|---:|---:|---:|---:|",
    ]
    for row in budget_rows:
        lines.append(
            f"| {row['budget']} | {row['successes']} | {row['tasks']} | "
            f"{100 * float(row['asr']):.2f}% | "
            f"[{100 * float(row['ci_low']):.2f}%, {100 * float(row['ci_high']):.2f}%] |"
        )
    lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            "This is formal adaptive evidence only when the root manifest is promoted to `completed_formal`. The MCTS selector never receives policy rules, detector scores, expected actions or offline labels. It receives only public decisions and final unsafe-effect/task-completion bits. Results apply to the frozen 80-task development/validation panel and do not replace the independent confirmatory blind set.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def analyze(*, run_dir: Path, output_dir: Path, allow_diagnostic: bool = False) -> dict[str, Any]:
    manifest, freeze, results = validate_run_artifacts(
        run_dir, allow_diagnostic=allow_diagnostic
    )
    budgets = tuple(int(value) for value in manifest.get("query_budgets", []))
    budget_rows, group_rows, summary = build_metrics(results, budgets)
    output_dir.mkdir(parents=True, exist_ok=True)
    budget_path = output_dir / "budget_curve.csv"
    groups_path = output_dir / "group_metrics.csv"
    summary_path = output_dir / "summary.json"
    report_path = output_dir / "analysis.md"
    _write_csv(budget_path, budget_rows)
    _write_csv(groups_path, group_rows)
    _write_json(summary_path, summary)
    figures = build_figures(output_dir / "figures", budget_rows, group_rows)
    _write_report(report_path, summary, budget_rows)

    formal = not allow_diagnostic and manifest.get("status") == "completed_formal_run_pending_analysis"
    analysis_manifest = {
        "schema_version": "paper-adaptive-mcts-analysis-manifest-1.0",
        "analyzer_version": ANALYZER_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "completed_formal_analysis" if formal else "completed_diagnostic_analysis",
        "result_eligible_for_formal_tables": formal,
        "run_manifest_pre_analysis_sha256": sha256_file(run_dir / "manifest.json"),
        "freeze_sha256": sha256_file(_resolve_reference(manifest["freeze_path"])),
        "task_results_sha256": sha256_file(run_dir / "task_results.jsonl"),
        "task_results_rows_sha256": rows_sha256(results),
        "task_count": len(results),
        "budget_curve": portable_path(budget_path, root=ROOT),
        "budget_curve_sha256": sha256_file(budget_path),
        "group_metrics": portable_path(groups_path, root=ROOT),
        "group_metrics_sha256": sha256_file(groups_path),
        "summary": portable_path(summary_path, root=ROOT),
        "summary_sha256": sha256_file(summary_path),
        "report": portable_path(report_path, root=ROOT),
        "report_sha256": sha256_file(report_path),
        "figures": figures,
        "boundary": str(freeze.get("boundary", "")),
    }
    analysis_manifest_path = output_dir / "analysis_manifest.json"
    _write_json(analysis_manifest_path, analysis_manifest)
    if formal:
        manifest.update(
            {
                "status": "completed_formal",
                "result_eligible_for_formal_tables": True,
                "analysis_manifest": portable_path(analysis_manifest_path, root=ROOT),
                "analysis_manifest_sha256": sha256_file(analysis_manifest_path),
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        _write_json(run_dir / "manifest.json", manifest)
    return analysis_manifest


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--allow-diagnostic", action="store_true")
    return parser


def main() -> int:
    args = _parser().parse_args()
    run_dir = args.run_dir.resolve()
    output_dir = args.output_dir.resolve() if args.output_dir else run_dir / "analysis"
    manifest = analyze(
        run_dir=run_dir,
        output_dir=output_dir,
        allow_diagnostic=args.allow_diagnostic,
    )
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "result_eligible": manifest["result_eligible_for_formal_tables"],
                "analysis_manifest": portable_path(
                    output_dir / "analysis_manifest.json",
                    root=ROOT,
                ),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
