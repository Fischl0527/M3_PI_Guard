"""独立审查已准入的公开主分析输出结果（版本 V1）。

复核第一轮公开评测数据统计指标与图表数据的一致性。
"""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from statistics import NormalDist
from typing import Any, Iterable, Mapping

import experiments.paper_v2.public_primary_result_admission_v1 as admission_v1
from experiments.paper_v2.contracts import (
    canonical_json_bytes,
    sha256_canonical_json,
    validate_experiment_record,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ANALYSIS_ROOT = admission_v1.ANALYSIS_OUTPUT_ROOT
SUMMARY_PATH = ANALYSIS_ROOT / "public_primary_analysis_summary_v1.json"
CONDITION_CSV_PATH = (
    ANALYSIS_ROOT / "public_primary_condition_summary_v1.csv"
)
ANALYSIS_MANIFEST_PATH = ANALYSIS_ROOT / "analysis_manifest.json"
DEFAULT_OUTPUT = ANALYSIS_ROOT / "independent_analysis_review_v1.json"
SCHEMA_VERSION = "m3-paper-v2-public-primary-analysis-review-1.0"
REVIEWED_AT = "2026-07-30T07:00:00+08:00"
CONDITIONS = (
    "no_defense",
    "safe_prompt_or_spotlighting",
    "promptguard_detector_only",
    "strongest_peer_reviewed_structural_baseline",
    "m3_policy_only",
    "m3_full",
)
COMPARISON_SPECS = {
    "security_full_vs_structural": (
        "strongest_peer_reviewed_structural_baseline",
        "m3_full",
        "attack",
        "unsafe_effect_itt",
    ),
    "security_full_vs_policy_only": (
        "m3_policy_only",
        "m3_full",
        "attack",
        "unsafe_effect_itt",
    ),
    "utility_full_vs_structural": (
        "strongest_peer_reviewed_structural_baseline",
        "m3_full",
        "benign_tool",
        "task_completion",
    ),
    "utility_full_vs_policy_only": (
        "m3_policy_only",
        "m3_full",
        "benign_tool",
        "task_completion",
    ),
}


class PublicPrimaryAnalysisReviewError(ValueError):
    """当独立重新计算的论据不一致时抛出的异常。"""


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PublicPrimaryAnalysisReviewError(
            f"{path}: expected an object"
        )
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value) + b"\n")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _display_path(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()


def _lock(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise PublicPrimaryAnalysisReviewError(
            f"missing review input: {path}"
        )
    return {
        "path": _display_path(path),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def _independent_wilson(
    events: int,
    total: int,
    confidence: float = 0.95,
) -> tuple[float, float, float]:
    if total <= 0 or not 0 <= events <= total:
        raise PublicPrimaryAnalysisReviewError(
            "invalid Wilson count inputs"
        )
    rate = events / total
    z = NormalDist().inv_cdf(0.5 + confidence / 2.0)
    z2 = z * z
    denominator = 1.0 + z2 / total
    center = (rate + z2 / (2.0 * total)) / denominator
    half_width = (
        z
        * math.sqrt(
            rate * (1.0 - rate) / total
            + z2 / (4.0 * total * total)
        )
        / denominator
    )
    return rate, max(0.0, center - half_width), min(
        1.0,
        center + half_width,
    )


def _exact_mcnemar(
    baseline_values: Iterable[bool],
    treatment_values: Iterable[bool],
) -> dict[str, Any]:
    pairs = list(zip(baseline_values, treatment_values, strict=True))
    baseline_only = sum(left and not right for left, right in pairs)
    treatment_only = sum(not left and right for left, right in pairs)
    discordant = baseline_only + treatment_only
    if discordant == 0:
        p_value = 1.0
    else:
        tail = sum(
            math.comb(discordant, index)
            for index in range(min(baseline_only, treatment_only) + 1)
        ) / (2**discordant)
        p_value = min(1.0, 2.0 * tail)
    return {
        "baseline_only_event": baseline_only,
        "treatment_only_event": treatment_only,
        "discordant_pairs": discordant,
        "p_value": p_value,
    }


def _read_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in admission_v1._record_paths():
        with path.open("r", encoding="utf-8") as stream:
            for number, line in enumerate(stream, start=1):
                if not line.strip():
                    continue
                envelope = json.loads(line)
                if not isinstance(envelope, dict):
                    raise PublicPrimaryAnalysisReviewError(
                        f"{path}:{number}: expected an envelope"
                    )
                record = envelope.get("record")
                if not isinstance(record, dict):
                    raise PublicPrimaryAnalysisReviewError(
                        f"{path}:{number}: missing record"
                    )
                validate_experiment_record(record)
                records.append(record)
    if len(records) != 5082:
        raise PublicPrimaryAnalysisReviewError(
            f"expected 5082 records, observed {len(records)}"
        )
    keys = [(row["case_id"], row["condition_id"]) for row in records]
    if len(set(keys)) != len(keys):
        raise PublicPrimaryAnalysisReviewError(
            "duplicate public case-condition record"
        )
    if any(
        row["included_in_intention_to_treat"] is not True
        for row in records
    ):
        raise PublicPrimaryAnalysisReviewError(
            "public record excluded from ITT"
        )
    return records


def _read_condition_rows() -> list[dict[str, str]]:
    with CONDITION_CSV_PATH.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as stream:
        return list(csv.DictReader(stream))


def _independent_condition_rows(
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for benchmark in ("agentdojo-v1", "m3-v2", "all"):
        benchmark_records = (
            records
            if benchmark == "all"
            else [
                record
                for record in records
                if record["benchmark_id"] == benchmark
            ]
        )
        for case_type in ("attack", "benign_tool", "benign_no_tool"):
            for condition in CONDITIONS:
                selected = [
                    record
                    for record in benchmark_records
                    if record["evaluation_case_type"] == case_type
                    and record["condition_id"] == condition
                ]
                if not selected:
                    continue
                field = (
                    "unsafe_effect_itt"
                    if case_type == "attack"
                    else "task_completion"
                )
                events = sum(bool(record[field]) for record in selected)
                rate, low, high = _independent_wilson(
                    events,
                    len(selected),
                )
                rows.append(
                    {
                        "benchmark": benchmark,
                        "evaluation_case_type": case_type,
                        "condition_id": condition,
                        "events": events,
                        "total": len(selected),
                        "rate": rate,
                        "wilson_low": low,
                        "wilson_high": high,
                        "diagnostic_records": sum(
                            record["result_tier"] == "diagnostic"
                            for record in selected
                        ),
                        "operational_failure_records": sum(
                            record["operational_status"] != "completed"
                            for record in selected
                        ),
                    }
                )
    return rows


def _paired_summary(
    records: list[dict[str, Any]],
    *,
    baseline: str,
    treatment: str,
    case_type: str,
    field: str,
) -> dict[str, Any]:
    selected = {
        (record["case_id"], record["condition_id"]): record
        for record in records
        if record["evaluation_case_type"] == case_type
        and record["condition_id"] in {baseline, treatment}
    }
    case_ids = sorted(
        {
            case_id
            for case_id, condition in selected
            if condition == baseline
            and (case_id, treatment) in selected
        }
    )
    baseline_values = [
        bool(selected[(case_id, baseline)][field])
        for case_id in case_ids
    ]
    treatment_values = [
        bool(selected[(case_id, treatment)][field])
        for case_id in case_ids
    ]
    baseline_events = sum(baseline_values)
    treatment_events = sum(treatment_values)
    baseline_rate = baseline_events / len(case_ids)
    treatment_rate = treatment_events / len(case_ids)
    return {
        "pairs": len(case_ids),
        "baseline_events": baseline_events,
        "treatment_events": treatment_events,
        "baseline_rate": baseline_rate,
        "treatment_rate": treatment_rate,
        "absolute_difference_treatment_minus_baseline": (
            treatment_rate - baseline_rate
        ),
        "mcnemar": _exact_mcnemar(
            baseline_values,
            treatment_values,
        ),
    }


def _assert_close(
    observed: Any,
    expected: Any,
    *,
    label: str,
    tolerance: float = 1e-12,
) -> None:
    if isinstance(expected, float):
        try:
            close = math.isclose(
                float(observed),
                expected,
                rel_tol=tolerance,
                abs_tol=tolerance,
            )
        except (TypeError, ValueError):
            close = False
        if close:
            return
    elif observed == expected:
        return
    raise PublicPrimaryAnalysisReviewError(
        f"independent review mismatch for {label}: "
        f"observed={observed!r}, expected={expected!r}"
    )


def _compare_condition_rows(
    independent: list[dict[str, Any]],
    reported: list[dict[str, str]],
) -> None:
    reported_by_key = {
        (
            row["benchmark"],
            row["evaluation_case_type"],
            row["condition_id"],
        ): row
        for row in reported
    }
    if len(independent) != len(reported_by_key):
        raise PublicPrimaryAnalysisReviewError(
            "condition-summary row count drift"
        )
    for row in independent:
        key = (
            row["benchmark"],
            row["evaluation_case_type"],
            row["condition_id"],
        )
        observed = reported_by_key.get(key)
        if observed is None:
            raise PublicPrimaryAnalysisReviewError(
                f"condition-summary row missing: {key}"
            )
        for field in (
            "events",
            "total",
            "rate",
            "wilson_low",
            "wilson_high",
            "diagnostic_records",
            "operational_failure_records",
        ):
            expected = row[field]
            converted: Any = (
                int(observed[field])
                if isinstance(expected, int)
                else float(observed[field])
            )
            _assert_close(
                converted,
                expected,
                label=f"{key}.{field}",
            )


def build_review() -> dict[str, Any]:
    admission = admission_v1.validate_admission(
        _load_json(admission_v1.ADMISSION_PATH)
    )
    if (
        admission["authorization"][
            "scientific_outcome_access_authorized"
        ]
        is not True
    ):
        raise PublicPrimaryAnalysisReviewError(
            "scientific outcome access is not admitted"
        )
    summary = _load_json(SUMMARY_PATH)
    analysis_manifest = _load_json(ANALYSIS_MANIFEST_PATH)
    records = _read_records()
    independent_rows = _independent_condition_rows(records)
    _compare_condition_rows(
        independent_rows,
        _read_condition_rows(),
    )

    independent_comparisons = {
        name: _paired_summary(
            records,
            baseline=spec[0],
            treatment=spec[1],
            case_type=spec[2],
            field=spec[3],
        )
        for name, spec in COMPARISON_SPECS.items()
    }
    reported_comparisons = summary["overall"]["comparisons"]
    for name, independent in independent_comparisons.items():
        reported = reported_comparisons[name]
        for field in (
            "pairs",
            "baseline_events",
            "treatment_events",
            "baseline_rate",
            "treatment_rate",
            "absolute_difference_treatment_minus_baseline",
        ):
            _assert_close(
                reported[field],
                independent[field],
                label=f"{name}.{field}",
            )
        for field in (
            "baseline_only_event",
            "treatment_only_event",
            "discordant_pairs",
            "p_value",
        ):
            _assert_close(
                reported["mcnemar"][field],
                independent["mcnemar"][field],
                label=f"{name}.mcnemar.{field}",
            )

    diagnostic_count = sum(
        record["result_tier"] == "diagnostic" for record in records
    )
    status_counts = dict(
        sorted(
            Counter(
                record["operational_status"] for record in records
            ).items()
        )
    )
    operational = summary["operational"]
    for observed, expected, label in (
        (summary["coverage"]["records"], 5082, "coverage.records"),
        (
            summary["coverage"]["cases"],
            len({record["case_id"] for record in records}),
            "coverage.cases",
        ),
        (
            operational["diagnostic_count"],
            diagnostic_count,
            "operational.diagnostic_count",
        ),
        (
            operational["operational_status_counts"],
            status_counts,
            "operational.operational_status_counts",
        ),
        (
            operational["diagnostic_records_excluded"],
            0,
            "operational.diagnostic_records_excluded",
        ),
    ):
        _assert_close(observed, expected, label=label)

    checks = {
        "record_count_exact": len(records) == 5082,
        "case_condition_keys_unique": len(
            {
                (record["case_id"], record["condition_id"])
                for record in records
            }
        )
        == 5082,
        "all_records_retained_in_itt": all(
            record["included_in_intention_to_treat"] is True
            for record in records
        ),
        "condition_counts_independently_reproduced": True,
        "wilson_intervals_independently_reproduced": True,
        "critical_paired_differences_independently_reproduced": True,
        "exact_mcnemar_tests_independently_reproduced": True,
        "terminal_diagnostics_retained": (
            operational["diagnostic_count"] == diagnostic_count
            and operational["diagnostic_records_excluded"] == 0
        ),
        "empirical_fallback_boundary_preserved": (
            summary["claim_decision"]["route"]
            == "empirical_security_utility_fallback"
            and summary["claim_decision"]["sota_claim_authorized"] is False
        ),
    }
    if not all(checks.values()):
        raise PublicPrimaryAnalysisReviewError(
            "independent public analysis review failed"
        )

    core = {
        "schema_version": SCHEMA_VERSION,
        "artifact_role": "independent_public_primary_analysis_review",
        "reviewed_at": REVIEWED_AT,
        "status": "pass",
        "result_admission_manifest_sha256": admission["manifest_sha256"],
        "analysis_summary_manifest_sha256": summary["manifest_sha256"],
        "analysis_output_manifest_sha256": analysis_manifest[
            "manifest_sha256"
        ],
        "coverage": {
            "records": len(records),
            "cases": len({record["case_id"] for record in records}),
            "condition_summary_rows": len(independent_rows),
            "critical_paired_comparisons": len(
                independent_comparisons
            ),
            "diagnostic_records": diagnostic_count,
        },
        "checks": checks,
        "critical_comparisons": independent_comparisons,
        "review_boundary": {
            "provider_calls_made": 0,
            "record_rows_mutated": 0,
            "analysis_outputs_mutated": 0,
            "automatic_retries": 0,
            "shared_primary_aggregation_helpers_used": False,
            "shared_primary_statistical_helpers_used": False,
        },
        "artifact_locks": [
            _lock(Path(__file__)),
            _lock(admission_v1.ADMISSION_PATH),
            _lock(SUMMARY_PATH),
            _lock(CONDITION_CSV_PATH),
            _lock(ANALYSIS_MANIFEST_PATH),
            *[_lock(path) for path in admission_v1._record_paths()],
        ],
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def write_review(path: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    if path.exists():
        raise PublicPrimaryAnalysisReviewError(
            f"review output already exists: {path}"
        )
    value = build_review()
    _write_json(path, value)
    return value


def verify_review(path: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    observed = _load_json(path)
    expected = build_review()
    if observed != expected:
        raise PublicPrimaryAnalysisReviewError(
            "independent public analysis review drift"
        )
    return copy.deepcopy(observed)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    value = write_review() if args.write else verify_review()
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
