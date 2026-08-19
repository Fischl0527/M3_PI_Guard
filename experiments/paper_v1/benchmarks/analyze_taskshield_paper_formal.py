"""Analyze an admitted Task Shield paper-reproduction AgentDojo run."""

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
DEFAULT_RUN_DIR = ROOT / "outputs" / "paper_upgrade_v1" / "baselines" / "taskshield_paper_formal_v1"
ANALYZER_VERSION = "m3-paper-v1-taskshield-paper-analysis-1.0"


def _intervention_metrics(rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    completed = [row for row in rows if row.get("status") == "completed"]
    denied = sum(int(row.get("taskshield_trace", {}).get("denied_tool_calls", 0)) > 0 for row in completed)
    suppressed = sum(int(row.get("taskshield_trace", {}).get("suppressed_content_messages", 0)) > 0 for row in completed)
    revised = sum(int(row.get("taskshield_trace", {}).get("assistant_revisions", 0)) > 0 for row in completed)
    return [
        _metric_row(scope="intervention", suite="overall", metric="denied_tool_call_case_rate", successes=denied, total=len(completed)),
        _metric_row(scope="intervention", suite="overall", metric="suppressed_content_case_rate", successes=suppressed, total=len(completed)),
        _metric_row(scope="intervention", suite="overall", metric="assistant_revision_case_rate", successes=revised, total=len(completed)),
    ]


def _intervention_figure(metrics: list[Mapping[str, Any]], output_dir: Path) -> dict[str, str]:
    import matplotlib.pyplot as plt

    output_dir.mkdir(parents=True, exist_ok=True)
    labels = ["Denied tool call", "Suppressed content", "Assistant revision"]
    names = ["denied_tool_call_case_rate", "suppressed_content_case_rate", "assistant_revision_case_rate"]
    values = [float(_rate(metrics, "overall", name)["rate"] or 0.0) * 100.0 for name in names]
    fig, ax = plt.subplots(figsize=(7.2, 4.3))
    bars = ax.bar(labels, values, color=["#c0392b", "#8e44ad", "#2471a3"])
    ax.set_title("Task Shield paper-reproduction intervention rates")
    ax.set_ylabel("Completed cases with intervention (%)")
    ax.set_ylim(0, 100)
    ax.grid(axis="y", alpha=0.25)
    ax.bar_label(bars, fmt="%.1f", padding=3)
    paths: dict[str, str] = {}
    for suffix in ("png", "svg"):
        path = output_dir / f"taskshield_interventions.{suffix}"
        fig.savefig(path, dpi=220, bbox_inches="tight")
        paths[suffix] = str(path.resolve())
    plt.close(fig)
    return paths


def write_report(path: Path, run_manifest: Mapping[str, Any], metrics: list[Mapping[str, Any]], summary: Mapping[str, Any]) -> None:
    lines = [
        "# Task Shield disclosed paper-reproduction analysis",
        "",
        f"- Run status: `{run_manifest['status']}`",
        f"- Formal result eligible: `{run_manifest['result_eligible_for_formal_tables']}`",
        f"- Model: `{run_manifest['model_id']}`",
        f"- Cases: {summary['case_count']} ({summary['utility_case_count']} utility + {summary['security_case_count']} security)",
        "",
        "## Main results",
        "",
        f"- AgentDojo ASR: {_fmt_rate(_rate(metrics, 'overall', 'ASR'))}",
        f"- Utility TCR: {_fmt_rate(_rate(metrics, 'overall', 'TCR'))}",
        f"- Failure rate: {_fmt_rate(_rate(metrics, 'overall', 'failure_rate'))}",
        f"- Cases with denied tool calls: {_fmt_rate(_rate(metrics, 'overall', 'denied_tool_call_case_rate'))}",
        f"- Cases with suppressed content: {_fmt_rate(_rate(metrics, 'overall', 'suppressed_content_case_rate'))}",
        f"- Cases with assistant revision: {_fmt_rate(_rate(metrics, 'overall', 'assistant_revision_case_rate'))}",
        f"- End-to-end latency median/p95: {float(summary['latency_ms']['median'] or 0.0):.2f} / {float(summary['latency_ms']['p95'] or 0.0):.2f} ms",
        "",
        "## Interpretation boundary",
        "",
        "This condition is a disclosed reproduction from the ACL paper, not official Task Shield source. Prompt wording is a frozen semantic restatement, and the local Qwen3 8B alias serves as both agent and verifier rather than the paper's GPT models. Any paired superiority claim requires a separately frozen matching comparison.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def analyze(*, run_dir: Path, output_dir: Path, allow_diagnostic: bool) -> dict[str, Any]:
    run_manifest_path = run_dir / "run_manifest.json"
    outcomes_path = run_dir / "outcomes.jsonl"
    run_manifest = _read_json(run_manifest_path)
    if not allow_diagnostic and (run_manifest.get("status") != "completed_formal" or not run_manifest.get("result_eligible_for_formal_tables")):
        raise ValueError("run is not formally admitted; use --allow-diagnostic only for diagnostics")
    rows = _read_jsonl(outcomes_path)
    expected = int(run_manifest.get("summary", {}).get("expected_cases", 0))
    if len(rows) != expected:
        raise ValueError(f"outcome coverage mismatch: {len(rows)} != {expected}")
    if len({str(row.get("benchmark_case_id", "")) for row in rows}) != len(rows):
        raise ValueError("duplicate benchmark_case_id in outcomes")
    metrics, summary = build_metrics(rows)
    metrics.extend(_intervention_metrics(rows))
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = output_dir / "metrics.csv"
    summary_path = output_dir / "summary.json"
    report_path = output_dir / "analysis.md"
    _write_metrics_csv(metrics_path, metrics)
    _write_json(summary_path, summary)
    figures = build_figures(rows, metrics, output_dir / "figures")
    figures["taskshield_interventions"] = _intervention_figure(metrics, output_dir / "figures")
    write_report(report_path, run_manifest, metrics, summary)
    manifest = {
        "schema_version": "paper-taskshield-analysis-manifest-1.0",
        "analyzer_version": ANALYZER_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "completed_formal_analysis" if run_manifest.get("result_eligible_for_formal_tables") else "completed_diagnostic_analysis",
        "result_eligible_for_formal_tables": bool(run_manifest.get("result_eligible_for_formal_tables")),
        "run_manifest_path": str(run_manifest_path.resolve()),
        "run_manifest_sha256": sha256_file(run_manifest_path),
        "outcomes_path": str(outcomes_path.resolve()),
        "outcomes_sha256": sha256_file(outcomes_path),
        "case_rows_sha256": rows_sha256(rows),
        "metrics_path": str(metrics_path.resolve()),
        "metrics_sha256": sha256_file(metrics_path),
        "summary_path": str(summary_path.resolve()),
        "summary_sha256": sha256_file(summary_path),
        "report_path": str(report_path.resolve()),
        "report_sha256": sha256_file(report_path),
        "figures": figures,
        "summary": summary,
        "boundary": "Single-condition disclosed paper-reproduction analysis; not an official-source Task Shield result.",
    }
    _write_json(output_dir / "analysis_manifest.json", manifest)
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--allow-diagnostic", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = args.output_dir or (args.run_dir / "analysis")
    manifest = analyze(run_dir=args.run_dir.resolve(), output_dir=output_dir.resolve(), allow_diagnostic=args.allow_diagnostic)
    print(json.dumps({"status": manifest["status"], "eligible": manifest["result_eligible_for_formal_tables"], "report": manifest["report_path"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
