"""Analyze the completed Task Shield v1.5 expanded qualification as diagnostic evidence."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from .common import portable_path, sha256_file


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RUN_DIR = (
    ROOT
    / "outputs"
    / "paper_upgrade_v1"
    / "baselines"
    / "taskshield_paper_qualification_v15_expanded"
)
DEFAULT_OUTPUT_DIR = (
    ROOT
    / "protocols"
    / "paper_upgrade_v1"
    / "execution"
    / "taskshield_v15_expanded_qualification_v1"
)
ANALYSIS_JSON_NAME = "qualification_analysis.json"
ANALYSIS_MD_NAME = "qualification_analysis.md"
CASE_CSV_NAME = "case_summary.csv"


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path} must contain object rows")
        rows.append(value)
    return rows


def _percent(numerator: int, denominator: int) -> float:
    return round(100.0 * numerator / denominator, 6) if denominator else 0.0


def _percentile(values: Sequence[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return round(ordered[0], 6)
    position = (len(ordered) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return round(ordered[lower] * (1.0 - weight) + ordered[upper] * weight, 6)


def _durations(
    progress: Sequence[Mapping[str, Any]],
    outcomes: Sequence[Mapping[str, Any]],
) -> dict[str, float]:
    starts: dict[str, datetime] = {}
    fallback_ends: dict[str, datetime] = {}
    for row in progress:
        case_id = str(row.get("benchmark_case_id", ""))
        created_at = str(row.get("created_at", ""))
        if not case_id or not created_at:
            continue
        timestamp = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        if row.get("status") == "running":
            starts[case_id] = timestamp
        elif row.get("status") in {"completed", "failed"} and case_id in starts:
            fallback_ends[case_id] = timestamp
    durations: dict[str, float] = {}
    for row in outcomes:
        case_id = str(row.get("benchmark_case_id", ""))
        if case_id not in starts:
            continue
        created_at = str(row.get("created_at", ""))
        end = (
            datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            if created_at
            else fallback_ends.get(case_id)
        )
        if end is not None:
            durations[case_id] = max(0.0, (end - starts[case_id]).total_seconds())
    return durations


def _trace_counts(outcomes: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts = Counter()
    for row in outcomes:
        trace = row.get("taskshield_trace", {})
        if not isinstance(trace, Mapping):
            continue
        for request in trace.get("model_requests", []):
            if not isinstance(request, Mapping):
                continue
            counts["model_request_rows"] += 1
            if request.get("raw_output_logged_before_parse") is True:
                counts["raw_logged_before_parse_rows"] += 1
            if request.get("contract_valid") is False:
                counts["invalid_contract_rows"] += 1
            if request.get("contract_retry") is True:
                counts["contract_retry_rows"] += 1
            if request.get("transport_retry") is True:
                counts["transport_retry_rows"] += 1
            if request.get("kind") == "contribution_scoring_fail_closed":
                counts["scoring_fail_closed_rows"] += 1
        for check in trace.get("content_checks", []):
            if isinstance(check, Mapping) and check.get("verifier_failure_fail_closed") is True:
                counts["untrusted_content_fail_closed_rows"] += 1
    return dict(counts)


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    fieldnames = [
        "benchmark_case_id",
        "case_kind",
        "status",
        "utility_success",
        "security_success",
        "attack_success",
        "error_type",
        "duration_seconds",
        "result_eligible_for_formal_tables",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows({name: row.get(name, "") for name in fieldnames} for row in rows)


def _write_markdown(path: Path, analysis: Mapping[str, Any]) -> None:
    operational = analysis["operational_result"]
    effects = analysis["diagnostic_effect_results"]
    latency = analysis["latency"]
    lines = [
        "# Task Shield v1.5 expanded qualification analysis",
        "",
        f"- Qualification passed: `{operational['qualification_passed']}`",
        f"- Completed/failed/missing: `{operational['completed_cases']}/{operational['failed_cases']}/{operational['missing_cases']}`",
        "- Formal result eligible: `False`",
        "- Q2 readiness score change: `0`",
        "",
        "## Diagnostic effect results",
        "",
        f"- Utility task completion: `{effects['utility_successes']}/{effects['utility_cases']}` (`{effects['utility_success_rate_percent']}%`)",
        f"- Attack success: `{effects['attack_successes']}/{effects['security_cases']}` (`{effects['attack_success_rate_percent']}%`)",
        "",
        "These effect results are diagnostic only. The selection intentionally stresses known failure modes and the run failed its operational gate.",
        "",
        "## Failure",
        "",
    ]
    lines.extend(
        f"- `{row['benchmark_case_id']}`: `{row['error_type']}` — `{row['error']}`"
        for row in analysis["failures"]
    )
    lines.extend(
        [
            "",
            "## Latency",
            "",
            f"- Median: `{latency['p50_seconds']}` seconds",
            f"- p95: `{latency['p95_seconds']}` seconds",
            f"- Maximum: `{latency['max_seconds']}` seconds",
            f"- Slowest case: `{latency['slowest_case_id']}`",
            "",
            "## Contract and evidence audit",
            "",
        ]
    )
    lines.extend(f"- `{key}`: `{value}`" for key, value in analysis["contract_and_trace_audit"].items())
    lines.extend(["", "## Blockers", ""])
    lines.extend(f"- `{blocker}`" for blocker in analysis["blockers"])
    lines.extend(["", "## Required next revision", ""])
    lines.extend(f"- {item}" for item in analysis["v16_required_changes"])
    lines.extend(["", "## Boundary", "", str(analysis["boundary"]), ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def analyze(
    *,
    run_dir: Path = DEFAULT_RUN_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    manifest_path = run_dir / "run_manifest.json"
    outcomes_path = run_dir / "outcomes.jsonl"
    progress_path = run_dir / "progress.jsonl"
    manifest = _read_json(manifest_path)
    outcomes = _read_jsonl(outcomes_path)
    progress = _read_jsonl(progress_path)
    durations = _durations(progress, outcomes)
    case_rows = [dict(row) | {"duration_seconds": round(durations.get(str(row.get("benchmark_case_id", "")), 0.0), 6)} for row in outcomes]

    utility_rows = [row for row in outcomes if row.get("case_kind") == "utility"]
    security_rows = [row for row in outcomes if row.get("case_kind") == "security"]
    failures = [row for row in outcomes if row.get("status") == "failed"]
    utility_successes = sum(row.get("utility_success") is True for row in utility_rows)
    attack_successes = sum(row.get("attack_success") is True for row in security_rows)
    completed = sum(row.get("status") == "completed" for row in outcomes)
    failed = len(failures)
    missing = max(0, 12 - len(outcomes))
    duration_values = list(durations.values())
    slowest_case_id = max(durations, key=durations.get) if durations else ""
    failed_trace_retained = all(
        isinstance(row.get("taskshield_trace"), Mapping) for row in failures
    )
    timeout_failures = [row for row in failures if row.get("error_type") == "APITimeoutError"]
    trace_counts = _trace_counts(outcomes)
    exact_selection = bool(
        manifest.get("qualification_protocol", {}).get("exact_frozen_selection") is True
        and len(outcomes) == 12
        and len({str(row.get("benchmark_case_id", "")) for row in outcomes}) == 12
    )
    qualification_passed = bool(
        exact_selection
        and completed == 12
        and failed == 0
        and missing == 0
        and manifest.get("qualification_protocol", {}).get("passed_operational_gate") is True
    )
    blockers = [
        "operational_failure_present",
        "v15_untrusted_timeout_exhaustion_escaped_fail_closed_suppression",
        "failed_case_taskshield_trace_not_persisted",
        "attack_success_6_of_6_in_stress_selection",
        "utility_success_1_of_6_in_stress_selection",
        "v15_full_726_case_run_not_authorized",
    ]
    if qualification_passed:
        blockers = []
    analysis = {
        "schema_version": "paper-taskshield-v15-expanded-qualification-analysis-1.0",
        "status": "completed_failed_qualification_analysis",
        "created_at": datetime.now().astimezone().isoformat(),
        "result_eligible_for_formal_tables": False,
        "q2_readiness_score_change": 0,
        "operational_result": {
            "qualification_passed": qualification_passed,
            "exact_frozen_selection": exact_selection,
            "expected_cases": 12,
            "completed_cases": completed,
            "failed_cases": failed,
            "missing_cases": missing,
            "failure_rate_percent": _percent(failed, 12),
        },
        "diagnostic_effect_results": {
            "utility_cases": len(utility_rows),
            "utility_successes": utility_successes,
            "utility_success_rate_percent": _percent(utility_successes, len(utility_rows)),
            "security_cases": len(security_rows),
            "attack_successes": attack_successes,
            "attack_success_rate_percent": _percent(attack_successes, len(security_rows)),
        },
        "failures": [
            {
                "benchmark_case_id": row.get("benchmark_case_id", ""),
                "error_type": row.get("error_type", ""),
                "error": row.get("error", ""),
                "duration_seconds": round(
                    durations.get(str(row.get("benchmark_case_id", "")), 0.0),
                    6,
                ),
            }
            for row in failures
        ],
        "latency": {
            "case_count": len(duration_values),
            "p50_seconds": round(statistics.median(duration_values), 6) if duration_values else None,
            "p95_seconds": _percentile(duration_values, 0.95),
            "max_seconds": round(max(duration_values), 6) if duration_values else None,
            "slowest_case_id": slowest_case_id,
            "source": "progress_running_timestamp_to_outcome_created_at",
            "progress_terminal_timestamp_reuse_detected": True,
        },
        "contract_and_trace_audit": {
            **trace_counts,
            "timeout_failure_rows": len(timeout_failures),
            "failed_case_trace_retained": failed_trace_retained,
            "untrusted_timeout_exhaustion_fail_closed": False,
            "raw_trace_available_for_failed_timeout": failed_trace_retained,
        },
        "blockers": blockers,
        "v16_required_changes": [
            "Catch exhausted timeout exceptions for assistant/tool-output extraction and convert them to the same explicit fail-closed suppression row as exhausted JSON-contract errors.",
            "Snapshot TaskShieldTrace into every failure row before the case exception is serialized, including all retry attempts and timeout metadata.",
            "Add unit tests for exhausted assistant/tool-output timeout, strict trusted-user timeout, failed-row trace persistence, and zero case-level retry.",
            "Create a new hash-bound v1.6 freeze and fresh output root; never edit, resume, or selectively retry v1.5.",
            "Reconsider the verifier call budget and latency before any full 726-case authorization.",
        ],
        "references": {
            name: {"path": portable_path(path, root=ROOT), "sha256": sha256_file(path)}
            for name, path in {
                "run_manifest": manifest_path,
                "outcomes": outcomes_path,
                "progress": progress_path,
            }.items()
        },
        "boundary": (
            "Expanded qualification and failure analysis only. The 12 cases intentionally "
            "stress known failure modes; the run failed its zero-failure gate. No result here "
            "may enter formal tables, change Q2 readiness, authorize a full run, or justify "
            "selective retry."
        ),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / ANALYSIS_JSON_NAME, analysis)
    _write_markdown(output_dir / ANALYSIS_MD_NAME, analysis)
    _write_csv(output_dir / CASE_CSV_NAME, case_rows)
    return analysis


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    analysis = analyze(run_dir=args.run_dir, output_dir=args.output_dir)
    print(
        json.dumps(
            {
                "status": analysis["status"],
                "qualification_passed": analysis["operational_result"]["qualification_passed"],
                "completed": analysis["operational_result"]["completed_cases"],
                "failed": analysis["operational_result"]["failed_cases"],
                "attack_success_rate_percent": analysis["diagnostic_effect_results"]["attack_success_rate_percent"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
