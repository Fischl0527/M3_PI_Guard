"""Analyze a completed source-backed Progent AgentDojo run."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .analyze_agentdojo_official_detector_formal import (
    _fmt_rate,
    _metric_row,
    _rate,
    _read_json,
    _read_jsonl,
    _write_json,
    _write_metrics_csv,
    build_figures,
    build_metrics,
)
from .common import rows_sha256, sha256_file


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RUN_DIR = (
    ROOT / "outputs" / "paper_upgrade_v1" / "baselines" / "progent_source_backed_formal_v1"
)
ANALYZER_VERSION = "m3-paper-v1-progent-source-backed-analysis-1.0"


def _checker_metrics(rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    security = [row for row in rows if row.get("case_kind") == "security"]
    official_attack = sum(row.get("security_success_official") is False for row in security)
    grounded_attack = sum(
        row.get("security_success_execution_grounded") is False for row in security
    )
    corrections = sum(bool(row.get("checker_correction_applied")) for row in security)
    return [
        _metric_row(
            scope="security_checker",
            suite="overall",
            metric="ASR_official_trace_checker",
            successes=official_attack,
            total=len(security),
        ),
        _metric_row(
            scope="security_checker",
            suite="overall",
            metric="ASR_execution_grounded",
            successes=grounded_attack,
            total=len(security),
        ),
        _metric_row(
            scope="security_checker",
            suite="overall",
            metric="checker_correction_rate",
            successes=corrections,
            total=len(security),
        ),
    ]


def _build_checker_figure(metrics: list[Mapping[str, Any]], output_dir: Path) -> list[str]:
    import matplotlib.pyplot as plt

    output_dir.mkdir(parents=True, exist_ok=True)
    names = ["Official trace checker", "Execution grounded"]
    values = [
        float(_rate(metrics, "overall", "ASR_official_trace_checker")["rate"] or 0.0)
        * 100.0,
        float(_rate(metrics, "overall", "ASR_execution_grounded")["rate"] or 0.0)
        * 100.0,
    ]
    fig, ax = plt.subplots(figsize=(6.6, 4.2))
    bars = ax.bar(names, values, color=["#7f8c8d", "#c0392b"])
    ax.set_title("Progent ASR under pre-registered checker semantics")
    ax.set_ylabel("ASR (%)")
    ax.set_ylim(0, 100)
    ax.grid(axis="y", alpha=0.25)
    ax.bar_label(bars, fmt="%.1f", padding=3)
    paths: list[str] = []
    for suffix in ("png", "svg"):
        path = output_dir / f"checker_asr_comparison.{suffix}"
        fig.savefig(path, dpi=220, bbox_inches="tight")
        paths.append(str(path.resolve()))
    plt.close(fig)
    return paths


def write_report(
    path: Path,
    run_manifest: Mapping[str, Any],
    metrics: list[Mapping[str, Any]],
    summary: Mapping[str, Any],
) -> None:
    asr = _rate(metrics, "overall", "ASR")
    official_asr = _rate(metrics, "overall", "ASR_official_trace_checker")
    grounded_asr = _rate(metrics, "overall", "ASR_execution_grounded")
    correction = _rate(metrics, "overall", "checker_correction_rate")
    tcr = _rate(metrics, "overall", "TCR")
    failure = _rate(metrics, "overall", "failure_rate")
    latency = summary["latency_ms"]
    lines = [
        "# Progent source-backed AgentDojo analysis",
        "",
        f"- Run status: `{run_manifest['status']}`",
        f"- Formal result eligible: `{run_manifest['result_eligible_for_formal_tables']}`",
        f"- Model: `{run_manifest['model_id']}`",
        f"- Cases: {summary['case_count']} ({summary['utility_case_count']} utility + {summary['security_case_count']} security)",
        "",
        "## Main results",
        "",
        f"- Primary execution-grounded ASR: {_fmt_rate(asr)}",
        f"- Raw official trace-checker ASR: {_fmt_rate(official_asr)}",
        f"- Explicit execution-grounded ASR: {_fmt_rate(grounded_asr)}",
        f"- Pre-registered checker-correction rate: {_fmt_rate(correction)}",
        f"- Utility TCR: {_fmt_rate(tcr)}",
        f"- Failure rate: {_fmt_rate(failure)}",
        f"- End-to-end latency median/p95: {float(latency['median'] or 0.0):.2f} / {float(latency['p95'] or 0.0):.2f} ms",
        "",
        "## Per-suite results",
        "",
        "| Suite | Execution-grounded ASR | TCR | Failure rate |",
        "|---|---:|---:|---:|",
    ]
    suites = sorted({str(row["suite"]) for row in metrics if row["suite"] != "overall"})
    for suite in suites:
        lines.append(
            f"| `{suite}` | {_fmt_rate(_rate(metrics, suite, 'ASR'))} | "
            f"{_fmt_rate(_rate(metrics, suite, 'TCR'))} | "
            f"{_fmt_rate(_rate(metrics, suite, 'failure_rate'))} |"
        )
    lines.extend(
        [
            "",
            "## Compatibility and interpretation boundary",
            "",
            "This result uses official Progent policy prompts, JSON-schema enforcement and update logic through a disclosed port to the common 726-case AgentDojo checkout. The official repository bundles only 686 cases, and both agent and policy generation use the frozen local Qwen3 8B model rather than the paper's GPT-4o setting. The Slack injection-task-5 official trace checker counts denied calls; its raw metric is retained while the pre-registered execution-grounded metric excludes denied side effects. This cell does not establish M3-v2, InjecAgent, adaptive-attack or frontier-model performance.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def analyze(*, run_dir: Path, output_dir: Path, allow_diagnostic: bool) -> dict[str, Any]:
    run_manifest_path = run_dir / "run_manifest.json"
    outcomes_path = run_dir / "outcomes.jsonl"
    run_manifest = _read_json(run_manifest_path)
    if not allow_diagnostic and (
        run_manifest.get("status") != "completed_formal"
        or not run_manifest.get("result_eligible_for_formal_tables")
    ):
        raise ValueError("run is not formally admitted; use --allow-diagnostic only for diagnostics")
    rows = _read_jsonl(outcomes_path)
    expected = int(run_manifest.get("summary", {}).get("expected_cases", 0))
    if len(rows) != expected:
        raise ValueError(f"outcome coverage mismatch: {len(rows)} != {expected}")
    if len({str(row.get("benchmark_case_id", "")) for row in rows}) != len(rows):
        raise ValueError("duplicate benchmark_case_id in outcomes")
    if any(
        row.get("case_kind") == "security"
        and (
            row.get("security_success_official") is None
            or row.get("security_success_execution_grounded") is None
        )
        for row in rows
    ):
        raise ValueError("security outcomes must retain both checker semantics")

    metrics, summary = build_metrics(rows)
    metrics.extend(_checker_metrics(rows))
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = output_dir / "metrics.csv"
    summary_path = output_dir / "summary.json"
    report_path = output_dir / "analysis.md"
    _write_metrics_csv(metrics_path, metrics)
    summary = {
        **summary,
        "checker_corrections_applied": sum(
            bool(row.get("checker_correction_applied")) for row in rows
        ),
    }
    _write_json(summary_path, summary)
    figures = build_figures(rows, metrics, output_dir / "figures")
    figures["checker_asr_comparison"] = _build_checker_figure(
        metrics, output_dir / "figures"
    )
    write_report(report_path, run_manifest, metrics, summary)
    manifest = {
        "schema_version": "paper-progent-source-backed-analysis-manifest-1.0",
        "analyzer_version": ANALYZER_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "completed_formal_analysis"
        if run_manifest.get("result_eligible_for_formal_tables")
        else "completed_diagnostic_analysis",
        "result_eligible_for_formal_tables": bool(
            run_manifest.get("result_eligible_for_formal_tables")
        ),
        "run_manifest_path": str(run_manifest_path.resolve()),
        "run_manifest_sha256": sha256_file(run_manifest_path),
        "outcomes_path": str(outcomes_path.resolve()),
        "outcomes_sha256": sha256_file(outcomes_path),
        "outcome_rows_sha256": rows_sha256(rows),
        "case_count": len(rows),
        "metrics_path": str(metrics_path.resolve()),
        "metrics_sha256": sha256_file(metrics_path),
        "summary_path": str(summary_path.resolve()),
        "summary_sha256": sha256_file(summary_path),
        "report_path": str(report_path.resolve()),
        "report_sha256": sha256_file(report_path),
        "figures": figures,
        "boundary": "Formal analysis is admitted only when the source run is completed_formal. Diagnostic analysis remains outside paper effect tables, and official versus execution-grounded checker metrics remain separate.",
    }
    manifest_path = output_dir / "analysis_manifest.json"
    _write_json(manifest_path, manifest)
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--allow-diagnostic", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_dir = args.run_dir.resolve()
    output_dir = args.output_dir.resolve() if args.output_dir else run_dir / "analysis"
    manifest = analyze(run_dir=run_dir, output_dir=output_dir, allow_diagnostic=args.allow_diagnostic)
    print(json.dumps({"status": manifest["status"], "result_eligible": manifest["result_eligible_for_formal_tables"], "analysis_manifest": str((output_dir / "analysis_manifest.json").resolve())}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
