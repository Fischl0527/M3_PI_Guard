"""Analyze a completed v3 source-backed CaMeL AgentDojo run."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .analyze_agentdojo_official_detector_formal import (
    _fmt_rate,
    _metric_row,
    _percentile,
    _rate,
    _read_json,
    _read_jsonl,
    _write_json,
    _write_metrics_csv,
    build_figures,
)
from .common import portable_path, portable_value, resolve_artifact_path, rows_sha256, sha256_file


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RUN_DIR = (
    ROOT / "outputs" / "paper_upgrade_v1" / "baselines" / "camel_source_backed_formal_v3"
)
ANALYZER_VERSION = "m3-paper-v1-camel-source-backed-analysis-1.1"


def build_metrics(rows: list[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    from collections import defaultdict
    from statistics import median

    by_suite: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        by_suite[str(row.get("suite", "unknown"))].append(row)

    metrics: list[dict[str, Any]] = []
    groups = {"overall": rows, **dict(sorted(by_suite.items()))}
    for suite, group in groups.items():
        utility = [row for row in group if row.get("case_kind") == "utility"]
        security = [row for row in group if row.get("case_kind") == "security"]
        resolved_security = [
            row for row in security if row.get("attack_outcome") in {"success", "failure"}
        ]
        completed = [row for row in group if row.get("status") == "completed"]
        attack_successes = sum(row.get("attack_outcome") == "success" for row in security)
        metrics.extend(
            [
                _metric_row(
                    scope="utility",
                    suite=suite,
                    metric="TCR",
                    successes=sum(row.get("utility_success") is True for row in utility),
                    total=len(utility),
                ),
                _metric_row(
                    scope="security",
                    suite=suite,
                    metric="ASR",
                    successes=sum(
                        row.get("attack_outcome") == "success" for row in resolved_security
                    ),
                    total=len(resolved_security),
                ),
                _metric_row(
                    scope="security",
                    suite=suite,
                    metric="ASR_full_denominator_lower_bound",
                    successes=attack_successes,
                    total=len(security),
                ),
                _metric_row(
                    scope="security",
                    suite=suite,
                    metric="ASR_full_denominator_upper_bound",
                    successes=attack_successes
                    + sum(row.get("attack_outcome") == "unresolved" for row in security),
                    total=len(security),
                ),
                _metric_row(
                    scope="detector",
                    suite=suite,
                    metric="redacted_case_rate",
                    successes=sum(
                        int(row.get("detector_redaction_marker_count", 0)) > 0
                        for row in completed
                    ),
                    total=len(completed),
                ),
                _metric_row(
                    scope="engineering",
                    suite=suite,
                    metric="failure_rate",
                    successes=sum(row.get("status") == "failed" for row in group),
                    total=len(group),
                ),
                _metric_row(
                    scope="engineering",
                    suite=suite,
                    metric="unresolved_attack_rate",
                    successes=sum(row.get("attack_outcome") == "unresolved" for row in security),
                    total=len(security),
                ),
            ]
        )

    latencies = [
        float(row["elapsed_ms"])
        for row in rows
        if isinstance(row.get("elapsed_ms"), (int, float))
    ]
    summary = {
        "case_count": len(rows),
        "utility_case_count": sum(row.get("case_kind") == "utility" for row in rows),
        "security_case_count": sum(row.get("case_kind") == "security" for row in rows),
        "failure_count": sum(row.get("status") == "failed" for row in rows),
        "resolved_security_case_count": sum(
            row.get("attack_outcome") in {"success", "failure"} for row in rows
        ),
        "unresolved_security_case_count": sum(
            row.get("attack_outcome") == "unresolved" for row in rows
        ),
        "latency_ms": {
            "n": len(latencies),
            "median": median(latencies) if latencies else None,
            "p95": _percentile(latencies, 0.95),
            "max": max(latencies) if latencies else None,
        },
    }
    return metrics, summary


def write_report(
    path: Path,
    run_manifest: Mapping[str, Any],
    metrics: list[Mapping[str, Any]],
    summary: Mapping[str, Any],
) -> None:
    asr = _rate(metrics, "overall", "ASR")
    tcr = _rate(metrics, "overall", "TCR")
    failure = _rate(metrics, "overall", "failure_rate")
    unresolved = _rate(metrics, "overall", "unresolved_attack_rate")
    latency = summary["latency_ms"]
    bindings = run_manifest.get("runtime_binding", {}).get("transport_bindings", {})
    lines = [
        "# CaMeL source-backed AgentDojo analysis",
        "",
        f"- Run status: `{run_manifest['status']}`",
        f"- Formal result eligible: `{run_manifest['result_eligible_for_formal_tables']}`",
        f"- Model: `{run_manifest['model_id']}`",
        f"- Cases: {summary['case_count']} ({summary['utility_case_count']} utility + {summary['security_case_count']} security)",
        "",
        "## Main results",
        "",
        f"- ASR (resolved security cases, AgentDojo official-v2 semantics): {_fmt_rate(asr)}",
        f"- Utility TCR: {_fmt_rate(tcr)}",
        f"- Unresolved attack rate: {_fmt_rate(unresolved)}",
        f"- Failure rate: {_fmt_rate(failure)}",
        f"- End-to-end latency median/p95: {float(latency['median'] or 0.0):.2f} / {float(latency['p95'] or 0.0):.2f} ms",
        "",
        "## Per-suite results",
        "",
        "| Suite | ASR | TCR | Unresolved attack rate | Failure rate | Policy engine |",
        "|---|---:|---:|---:|---:|---|",
    ]
    suites = sorted({str(row["suite"]) for row in metrics if row["suite"] != "overall"})
    for suite in suites:
        policy = bindings.get(suite, {}).get("policy_engine_class", "")
        lines.append(
            f"| `{suite}` | {_fmt_rate(_rate(metrics, suite, 'ASR'))} | "
            f"{_fmt_rate(_rate(metrics, suite, 'TCR'))} | "
            f"{_fmt_rate(_rate(metrics, suite, 'unresolved_attack_rate'))} | "
            f"{_fmt_rate(_rate(metrics, suite, 'failure_rate'))} | `{policy}` |"
        )
    lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            "This cell uses the pinned Google CaMeL interpreter, capability labels and suite policies through a disclosed process-local AgentDojo import-order compatibility preload. v3 additionally records AgentDojo official-v2 attack semantics and keeps operational failures unresolved rather than counting them as safe. Both privileged code generation and quarantined structured parsing use the frozen local Qwen3 8B model through loopback OpenAI-compatible transports. It is a common-universe AgentDojo reproduction, not a claim that the original frontier-model CaMeL numbers were reproduced, and it does not establish M3-v2, InjecAgent, adaptive-attack or frontier-model performance.",
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
        row.get("status") == "completed"
        and (
            not row.get("official_trace_path")
            or not resolve_artifact_path(str(row.get("official_trace_path")), root=ROOT).is_file()
            or not row.get("camel_transport_binding")
        )
        for row in rows
    ):
        raise ValueError("completed CaMeL rows require trace and transport-binding evidence")

    metrics, summary = build_metrics(rows)
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = output_dir / "metrics.csv"
    summary_path = output_dir / "summary.json"
    report_path = output_dir / "analysis.md"
    _write_metrics_csv(metrics_path, metrics)
    _write_json(summary_path, summary)
    figures = portable_value(build_figures(rows, metrics, output_dir / "figures"), root=ROOT)
    write_report(report_path, run_manifest, metrics, summary)
    manifest = {
        "schema_version": "paper-camel-source-backed-analysis-manifest-1.0",
        "analyzer_version": ANALYZER_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": (
            "completed_formal_analysis"
            if run_manifest.get("result_eligible_for_formal_tables")
            else "completed_diagnostic_analysis"
        ),
        "result_eligible_for_formal_tables": bool(
            run_manifest.get("result_eligible_for_formal_tables")
        ),
        "run_manifest_path": portable_path(run_manifest_path, root=ROOT),
        "run_manifest_sha256": sha256_file(run_manifest_path),
        "outcomes_path": portable_path(outcomes_path, root=ROOT),
        "outcomes_sha256": sha256_file(outcomes_path),
        "outcome_rows_sha256": rows_sha256(rows),
        "case_count": len(rows),
        "metrics_path": portable_path(metrics_path, root=ROOT),
        "metrics_sha256": sha256_file(metrics_path),
        "summary_path": portable_path(summary_path, root=ROOT),
        "summary_sha256": sha256_file(summary_path),
        "report_path": portable_path(report_path, root=ROOT),
        "report_sha256": sha256_file(report_path),
        "figures": figures,
        "boundary": (
            "Formal analysis is admitted only from a completed_formal 726-case "
            "CaMeL run with exact frozen coverage, trace evidence and zero failures."
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
                "analysis_manifest": portable_path(output_dir / "analysis_manifest.json", root=ROOT),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
