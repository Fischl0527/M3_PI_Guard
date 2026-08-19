"""Paper-v2 medium analysis with protocol-terminal ITT quality semantics.

Version 3 preserves every outcome and statistic produced by version 2.  It
changes only the mechanism-paper operational check: known protocol terminal
states remain in the ITT denominator, while a prespecified quality envelope
replaces the brittle requirement that every record end as ``completed``.
"""

from __future__ import annotations

import argparse
import copy
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

from experiments.paper_v2.contracts import canonical_json_bytes
from experiments.paper_v2.medium_analysis import MediumAnalysisError
from experiments.paper_v2.medium_analysis_v2 import analyze_medium_records_v2


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CASE_MANIFEST = (
    PROJECT_ROOT / "protocols/paper_upgrade_v2/medium_case_manifest_v1.json"
)
DEFAULT_CASE_INDEX = (
    PROJECT_ROOT / "protocols/paper_upgrade_v2/medium_case_index_v1.jsonl"
)
DEFAULT_GATE_SPEC = (
    PROJECT_ROOT / "protocols/paper_upgrade_v2/medium_gate_spec_v2.json"
)
DEFAULT_RECORDS = (
    PROJECT_ROOT / "outputs/paper_upgrade_v2/medium/experiment_records.jsonl"
)
DEFAULT_REPORT = (
    PROJECT_ROOT / "outputs/paper_upgrade_v2/medium/analysis_v3.json"
)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise MediumAnalysisError(f"{path}: expected an object")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    values: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                raise MediumAnalysisError(
                    f"{path}:{line_number}: blank JSONL row"
                )
            value = json.loads(line)
            if not isinstance(value, dict):
                raise MediumAnalysisError(
                    f"{path}:{line_number}: expected an object"
                )
            values.append(value)
    return values


def evaluate_operational_quality(
    records: Sequence[Mapping[str, Any]],
    *,
    gate_spec: Mapping[str, Any],
) -> dict[str, Any]:
    """Evaluate the prespecified claim-quality envelope."""

    quality = gate_spec["operational_quality"]
    statuses = Counter(str(row["operational_status"]) for row in records)
    failure_statuses = set(quality["failure_statuses"])
    failure_count = sum(statuses[status] for status in failure_statuses)
    provider_or_timeout = statuses["provider_failure"] + statuses["timeout"]
    denominator = len(records)
    failure_fraction = failure_count / denominator if denominator else 0.0
    provider_fraction = (
        provider_or_timeout / denominator if denominator else 0.0
    )
    checks = {
        "overall_failure_fraction": (
            failure_fraction
            <= float(quality["overall_failure_fraction_maximum"])
        ),
        "provider_or_timeout_fraction": (
            provider_fraction
            <= float(quality["provider_or_timeout_fraction_maximum"])
        ),
        "runner_failure_count": (
            statuses["runner_failure"]
            <= int(quality["runner_failure_max_count"])
        ),
    }
    return {
        "status": "pass" if all(checks.values()) else "fail_empirical_fallback",
        "mechanism_claim_quality_eligible": all(checks.values()),
        "record_count": denominator,
        "operational_status_counts": dict(sorted(statuses.items())),
        "failure_count": failure_count,
        "failure_fraction": failure_fraction,
        "provider_or_timeout_count": provider_or_timeout,
        "provider_or_timeout_fraction": provider_fraction,
        "checks": checks,
        "thresholds": copy.deepcopy(dict(quality)),
        "all_records_retained_in_itt": True,
    }


def analyze_medium_records_v3(
    records: list[dict[str, Any]],
    *,
    case_manifest: Mapping[str, Any],
    case_index: list[Mapping[str, Any]],
    gate_spec: Mapping[str, Any],
    bootstrap_iterations: int | None = None,
) -> dict[str, Any]:
    report = analyze_medium_records_v2(
        records,
        case_manifest=case_manifest,
        case_index=case_index,
        gate_spec=gate_spec,
        bootstrap_iterations=bootstrap_iterations,
    )
    if report["status"] != "complete":
        return {
            **report,
            "schema_version": "m3-paper-v2-medium-analysis-3.0",
            "operational_quality": None,
        }

    primary_records = [
        row
        for row in records
        if row["authorization_regime"] == "auto_compiled"
        and row["condition_id"] in case_manifest["core_conditions"]
    ]
    operational = evaluate_operational_quality(
        primary_records,
        gate_spec=gate_spec,
    )
    result = copy.deepcopy(report)
    result["schema_version"] = "m3-paper-v2-medium-analysis-3.0"
    result["operational_quality"] = operational

    mechanism = result["primary_analysis"]["mechanism_paper_gate"]
    checks = mechanism["checks"]
    checks["legacy_zero_operational_failures_observed"] = checks.pop(
        "zero_operational_failures"
    )
    checks["prespecified_operational_quality"] = operational[
        "mechanism_claim_quality_eligible"
    ]
    claim_checks = {
        key: value
        for key, value in checks.items()
        if key != "legacy_zero_operational_failures_observed"
    }
    eligible = all(bool(value) for value in claim_checks.values())
    mechanism["status"] = "pass" if eligible else "fail_redirect"
    mechanism["mechanism_paper_candidate"] = eligible
    mechanism["fallback_empirical_study_triggered"] = not eligible
    mechanism["operational_interpretation"] = (
        "Known terminal states remain in the ITT denominator. The legacy "
        "zero-failure value is descriptive; the prospectively frozen v2 "
        "quality envelope controls the mechanism-paper claim."
    )
    return result


def run(
    *,
    records_path: Path = DEFAULT_RECORDS,
    report_path: Path = DEFAULT_REPORT,
) -> dict[str, Any]:
    report = analyze_medium_records_v3(
        _read_jsonl(records_path),
        case_manifest=_read_json(DEFAULT_CASE_MANIFEST),
        case_index=_read_jsonl(DEFAULT_CASE_INDEX),
        gate_spec=_read_json(DEFAULT_GATE_SPEC),
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_bytes(canonical_json_bytes(report) + b"\n")
    return report


def verify_report(
    *,
    records_path: Path = DEFAULT_RECORDS,
    report_path: Path = DEFAULT_REPORT,
) -> dict[str, Any]:
    expected = analyze_medium_records_v3(
        _read_jsonl(records_path),
        case_manifest=_read_json(DEFAULT_CASE_MANIFEST),
        case_index=_read_jsonl(DEFAULT_CASE_INDEX),
        gate_spec=_read_json(DEFAULT_GATE_SPEC),
    )
    observed = _read_json(report_path)
    if observed != expected:
        raise MediumAnalysisError("medium analysis v3 report does not reproduce")
    return observed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=Path, default=DEFAULT_RECORDS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    def resolve(path: Path) -> Path:
        return path if path.is_absolute() else PROJECT_ROOT / path

    operation = verify_report if args.verify_only else run
    report = operation(
        records_path=resolve(args.records),
        report_path=resolve(args.report),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
