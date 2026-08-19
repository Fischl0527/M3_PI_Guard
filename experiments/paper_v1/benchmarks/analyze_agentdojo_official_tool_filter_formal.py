"""Analyze a completed official AgentDojo tool_filter run."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .common import portable_path, portable_value, rows_sha256, sha256_file
from .analyze_agentdojo_official_detector_formal import (
    _fmt_rate,
    _rate,
    _read_json,
    _read_jsonl,
    _write_json,
    _write_metrics_csv,
    build_figures,
    build_metrics,
)


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RUN_DIR = (
    ROOT
    / "outputs"
    / "paper_upgrade_v1"
    / "baselines"
    / "agentdojo_tool_filter_official_formal_v1"
)
ANALYZER_VERSION = "m3-paper-v1-agentdojo-official-tool-filter-analysis-1.0"


def write_report(
    path: Path,
    run_manifest: Mapping[str, Any],
    metrics: list[Mapping[str, Any]],
    summary: Mapping[str, Any],
) -> None:
    asr = _rate(metrics, "overall", "ASR")
    tcr = _rate(metrics, "overall", "TCR")
    failure = _rate(metrics, "overall", "failure_rate")
    lines = [
        "# AgentDojo official tool_filter formal analysis",
        "",
        f"- Run status: `{run_manifest['status']}`",
        f"- Formal result eligible: `{run_manifest['result_eligible_for_formal_tables']}`",
        f"- Model: `{run_manifest['model_id']}`",
        f"- Cases: {summary['case_count']} ({summary['utility_case_count']} utility + {summary['security_case_count']} security)",
        "",
        "## Main results",
        "",
        f"- Official AgentDojo ASR: {_fmt_rate(asr)}",
        f"- Official AgentDojo utility TCR: {_fmt_rate(tcr)}",
        f"- Failure rate: {_fmt_rate(failure)}",
        f"- End-to-end latency median/p95: {summary['latency_ms']['median']:.2f} / {summary['latency_ms']['p95']:.2f} ms",
        "",
        "## Per-suite results",
        "",
        "| Suite | ASR | TCR | Failure rate |",
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
            "## Interpretation boundary",
            "",
            "These are end-to-end AgentDojo results for the official tool_filter condition only. A paired superiority claim requires matching frozen no-defense/M3 outcomes on identical model/case pairs and a separate paired statistical analysis. These results do not establish M3-v2, InjecAgent, multilingual, adaptive-attack or frontier-model performance.",
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

    metrics, summary = build_metrics(rows)
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = output_dir / "metrics.csv"
    summary_path = output_dir / "summary.json"
    report_path = output_dir / "analysis.md"
    _write_metrics_csv(metrics_path, metrics)
    _write_json(summary_path, summary)
    figures = build_figures(rows, metrics, output_dir / "figures")
    write_report(report_path, run_manifest, metrics, summary)
    manifest = {
        "schema_version": "paper-agentdojo-official-tool-filter-analysis-manifest-1.0",
        "analyzer_version": ANALYZER_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "completed_formal_analysis"
        if run_manifest.get("result_eligible_for_formal_tables")
        else "completed_diagnostic_analysis",
        "result_eligible_for_formal_tables": bool(
            run_manifest.get("result_eligible_for_formal_tables")
        ),
        "run_manifest_path": portable_path(run_manifest_path, root=ROOT),
        "run_manifest_sha256": sha256_file(run_manifest_path),
        "outcomes_path": portable_path(outcomes_path, root=ROOT),
        "outcomes_sha256": sha256_file(outcomes_path),
        "case_rows_sha256": rows_sha256(rows),
        "metrics_path": portable_path(metrics_path, root=ROOT),
        "metrics_sha256": sha256_file(metrics_path),
        "summary_path": portable_path(summary_path, root=ROOT),
        "summary_sha256": sha256_file(summary_path),
        "report_path": portable_path(report_path, root=ROOT),
        "report_sha256": sha256_file(report_path),
        "figures": portable_value(figures, root=ROOT),
        "summary": summary,
        "boundary": (
            "Single-condition descriptive analysis. Paired superiority claims require "
            "a separately frozen paired comparison."
        ),
    }
    manifest_path = output_dir / "analysis_manifest.json"
    _write_json(manifest_path, manifest)
    manifest["manifest_path"] = portable_path(manifest_path, root=ROOT)
    manifest["manifest_sha256"] = sha256_file(manifest_path)
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--allow-diagnostic", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir or (args.run_dir / "analysis")
    manifest = analyze(
        run_dir=args.run_dir.resolve(),
        output_dir=output_dir.resolve(),
        allow_diagnostic=args.allow_diagnostic,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
