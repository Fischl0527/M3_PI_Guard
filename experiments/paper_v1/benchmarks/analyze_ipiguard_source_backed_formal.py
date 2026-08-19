"""Analyze a completed source-backed IPIGuard AgentDojo run."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

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
from .common import rows_sha256, sha256_file


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RUN_DIR = (
    ROOT / "outputs" / "paper_upgrade_v1" / "baselines" / "ipiguard_source_backed_formal_v1"
)
ANALYZER_VERSION = "m3-paper-v1-ipiguard-source-backed-analysis-1.0"


def write_report(
    path: Path,
    run_manifest: Mapping[str, Any],
    metrics: list[Mapping[str, Any]],
    summary: Mapping[str, Any],
) -> None:
    asr = _rate(metrics, "overall", "ASR")
    tcr = _rate(metrics, "overall", "TCR")
    failure = _rate(metrics, "overall", "failure_rate")
    run_summary = run_manifest.get("summary", {})
    lines = [
        "# IPIGuard source-backed AgentDojo analysis",
        "",
        f"- Run status: `{run_manifest['status']}`",
        f"- Formal result eligible: `{run_manifest['result_eligible_for_formal_tables']}`",
        f"- Model: `{run_manifest['model_id']}`",
        f"- Cases: {summary['case_count']} ({summary['utility_case_count']} utility + {summary['security_case_count']} security)",
        f"- Cases with serialized DAG evidence: {run_summary.get('cases_with_dag', 0)}",
        "",
        "## Main results",
        "",
        f"- AgentDojo ASR: {_fmt_rate(asr)}",
        f"- AgentDojo utility TCR: {_fmt_rate(tcr)}",
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
            "## Compatibility and interpretation boundary",
            "",
            "This cell uses the pinned IPIGuard construct/traverse/DAG source with a disclosed local OpenAI-compatible transport and an import-only isolation for the unused Vertex provider. It is therefore source-backed but not the upstream CLI byte-for-byte. It may be compared only against identical frozen AgentDojo cases and attacks. It does not establish M3-v2, InjecAgent, multilingual, adaptive-attack or frontier-model performance.",
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
    if not allow_diagnostic and any(
        int(row.get("dag_node_count", 0)) <= 0 for row in rows if row.get("status") == "completed"
    ):
        raise ValueError("formally admitted IPIGuard outcomes must retain non-empty DAG evidence")

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
        "schema_version": "paper-ipiguard-source-backed-analysis-manifest-1.0",
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
        "boundary": (
            "Formal analysis is admitted only when the source run itself is completed_formal. "
            "Diagnostic analysis remains outside paper effect tables."
        ),
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
                "analysis_manifest": str((output_dir / "analysis_manifest.json").resolve()),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
