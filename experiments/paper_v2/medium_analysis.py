"""Analyze paper-v2 medium falsification records without dropping failures."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import NormalDist
from typing import Any, Iterable, Mapping

from experiments.paper_v2.contracts import (
    OPERATIONAL_FAILURE_STATUSES,
    canonical_json_bytes,
    validate_experiment_record,
)
from m3_eval.statistics import (
    clustered_paired_bootstrap,
    holm_adjust,
    mcnemar_exact,
    proportion_result,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CASE_MANIFEST = (
    PROJECT_ROOT / "protocols/paper_upgrade_v2/medium_case_manifest_v1.json"
)
DEFAULT_CASE_INDEX = (
    PROJECT_ROOT / "protocols/paper_upgrade_v2/medium_case_index_v1.jsonl"
)
DEFAULT_GATE_SPEC = (
    PROJECT_ROOT / "protocols/paper_upgrade_v2/medium_gate_spec_v1.json"
)
DEFAULT_RECORDS = (
    PROJECT_ROOT / "outputs/paper_upgrade_v2/medium/experiment_records.jsonl"
)
DEFAULT_REPORT = (
    PROJECT_ROOT / "outputs/paper_upgrade_v2/medium/analysis_v1.json"
)


class MediumAnalysisError(ValueError):
    """Raised when medium-study evidence violates its frozen contract."""


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def paired_binary_power_sample_size(
    *,
    baseline_only_event_probability: float,
    treatment_only_event_probability: float,
    alpha: float = 0.05,
    power: float = 0.80,
) -> dict[str, Any]:
    """Approximate paired sample size from McNemar discordant probabilities.

    The approximation uses the alternative variance of a paired binary
    difference and is intentionally reported as planning evidence, not as an
    exact achieved-power claim.
    """

    p10 = float(baseline_only_event_probability)
    p01 = float(treatment_only_event_probability)
    if not 0.0 <= p10 <= 1.0 or not 0.0 <= p01 <= 1.0 or p10 + p01 > 1.0:
        raise MediumAnalysisError("discordant probabilities must be valid")
    if not 0.0 < alpha < 1.0 or not 0.0 < power < 1.0:
        raise MediumAnalysisError("alpha and power must lie in (0, 1)")
    discordant = p10 + p01
    difference = p10 - p01
    if discordant == 0.0 or difference == 0.0:
        required = None
    else:
        z_alpha = NormalDist().inv_cdf(1.0 - alpha / 2.0)
        z_power = NormalDist().inv_cdf(power)
        alternative_variance = max(0.0, discordant - difference * difference)
        required = math.ceil(
            (
                z_alpha * math.sqrt(discordant)
                + z_power * math.sqrt(alternative_variance)
            )
            ** 2
            / (difference * difference)
        )
    return {
        "method": (
            "paired_binary_normal_approximation_from_discordant_probabilities"
        ),
        "baseline_only_event_probability": p10,
        "treatment_only_event_probability": p01,
        "discordant_probability": discordant,
        "paired_difference": difference,
        "alpha_two_sided": alpha,
        "target_power": power,
        "required_pairs": required,
    }


def _condition_metric(
    records: Iterable[Mapping[str, Any]],
    *,
    case_type: str,
    field: str,
) -> dict[str, Any]:
    selected = [row for row in records if row["evaluation_case_type"] == case_type]
    numerator = sum(bool(row[field]) for row in selected)
    result = proportion_result(numerator, len(selected))
    result["field"] = field
    result["evaluation_case_type"] = case_type
    return result


def _paired_comparison(
    by_condition: Mapping[str, Mapping[str, Mapping[str, Any]]],
    *,
    baseline: str,
    treatment: str,
    case_type: str,
    field: str,
    bootstrap_iterations: int,
    bootstrap_seed: int,
) -> dict[str, Any]:
    left = by_condition[baseline]
    right = by_condition[treatment]
    case_ids = sorted(
        case_id
        for case_id in set(left) & set(right)
        if left[case_id]["evaluation_case_type"] == case_type
        and right[case_id]["evaluation_case_type"] == case_type
    )
    baseline_values = [bool(left[case_id][field]) for case_id in case_ids]
    treatment_values = [bool(right[case_id][field]) for case_id in case_ids]
    baseline_rate = (
        sum(baseline_values) / len(case_ids) if case_ids else None
    )
    treatment_rate = (
        sum(treatment_values) / len(case_ids) if case_ids else None
    )
    absolute_difference = (
        treatment_rate - baseline_rate
        if baseline_rate is not None and treatment_rate is not None
        else None
    )
    relative_difference = (
        absolute_difference / baseline_rate
        if absolute_difference is not None and baseline_rate
        else None
    )
    return {
        "baseline": baseline,
        "treatment": treatment,
        "evaluation_case_type": case_type,
        "field": field,
        "pairs": len(case_ids),
        "baseline_events": sum(baseline_values),
        "treatment_events": sum(treatment_values),
        "baseline_rate": baseline_rate,
        "treatment_rate": treatment_rate,
        "absolute_difference_treatment_minus_baseline": absolute_difference,
        "relative_difference_treatment_minus_baseline": relative_difference,
        "mcnemar": mcnemar_exact(baseline_values, treatment_values),
        "cluster_bootstrap": clustered_paired_bootstrap(
            [
                (case_id, float(left_value), float(right_value))
                for case_id, left_value, right_value in zip(
                    case_ids, baseline_values, treatment_values
                )
            ],
            iterations=bootstrap_iterations,
            seed=bootstrap_seed,
        ),
    }


def _pending_report(
    *,
    manifest: Mapping[str, Any],
    gate_spec: Mapping[str, Any],
) -> dict[str, Any]:
    primary = manifest["case_count"] * len(manifest["core_conditions"])
    probe = manifest["regime_probe_cases"] * 2
    return {
        "schema_version": "m3-paper-v2-medium-analysis-1.0",
        "status": "results_pending",
        "case_count": manifest["case_count"],
        "expected_primary_records": primary,
        "expected_regime_probe_records": probe,
        "expected_total_records": primary + probe,
        "observed_records": 0,
        "gate_spec": gate_spec,
        "statistics": None,
        "power_analysis": None,
        "mechanism_paper_gate": {
            "status": "not_evaluated",
            "mechanism_paper_candidate": False,
            "fallback_empirical_study_triggered": False,
            "reason": "No paper-v2 medium model records exist.",
        },
    }


def analyze_medium_records(
    records: list[dict[str, Any]],
    *,
    case_manifest: Mapping[str, Any],
    case_index: list[Mapping[str, Any]],
    gate_spec: Mapping[str, Any],
    bootstrap_iterations: int | None = None,
) -> dict[str, Any]:
    if not records:
        return _pending_report(manifest=case_manifest, gate_spec=gate_spec)
    for record in records:
        validate_experiment_record(record)
        if record["included_in_intention_to_treat"] is not True:
            raise MediumAnalysisError("all assigned records must remain in ITT")

    expected_cases = {row["case_id"] for row in case_index}
    core_conditions = tuple(case_manifest["core_conditions"])
    primary = [
        row
        for row in records
        if row["authorization_regime"] == "auto_compiled"
        and row["condition_id"] in core_conditions
    ]
    keys = [(row["case_id"], row["condition_id"]) for row in primary]
    duplicates = [key for key, count in Counter(keys).items() if count != 1]
    if duplicates:
        raise MediumAnalysisError(f"duplicate primary records: {duplicates[:5]}")
    missing = sorted(
        (case_id, condition)
        for case_id in expected_cases
        for condition in core_conditions
        if (case_id, condition) not in set(keys)
    )
    extra_cases = sorted({row["case_id"] for row in primary} - expected_cases)
    if missing or extra_cases:
        raise MediumAnalysisError(
            f"incomplete primary matrix: missing={len(missing)}, "
            f"extra_cases={extra_cases[:5]}"
        )

    by_condition: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in primary:
        by_condition[row["condition_id"]][row["case_id"]] = row

    configured_iterations = gate_spec["statistics"][
        "cluster_bootstrap_iterations"
    ]
    iterations = (
        configured_iterations
        if bootstrap_iterations is None
        else int(bootstrap_iterations)
    )
    seed = gate_spec["statistics"]["cluster_bootstrap_seed"]
    comparison_specs = (
        (
            "security_full_vs_structural",
            "strongest_peer_reviewed_structural_baseline",
            "m3_full",
            "attack",
            "unsafe_effect_itt",
        ),
        (
            "security_full_vs_policy_only",
            "m3_policy_only",
            "m3_full",
            "attack",
            "unsafe_effect_itt",
        ),
        (
            "utility_full_vs_structural",
            "strongest_peer_reviewed_structural_baseline",
            "m3_full",
            "benign_tool",
            "task_completion",
        ),
        (
            "utility_full_vs_policy_only",
            "m3_policy_only",
            "m3_full",
            "benign_tool",
            "task_completion",
        ),
    )
    comparisons = {
        name: _paired_comparison(
            by_condition,
            baseline=baseline,
            treatment=treatment,
            case_type=case_type,
            field=field,
            bootstrap_iterations=iterations,
            bootstrap_seed=seed + index,
        )
        for index, (name, baseline, treatment, case_type, field) in enumerate(
            comparison_specs
        )
    }
    raw_p = [item["mcnemar"]["p_value"] for item in comparisons.values()]
    for item, adjusted in zip(comparisons.values(), holm_adjust(raw_p)):
        item["mcnemar"]["holm_adjusted_p_value"] = adjusted

    condition_metrics = {
        condition: {
            "unsafe_effect_itt": _condition_metric(
                rows.values(), case_type="attack", field="unsafe_effect_itt"
            ),
            "benign_tool_tcr": _condition_metric(
                rows.values(), case_type="benign_tool", field="task_completion"
            ),
            "benign_no_tool_tcr": _condition_metric(
                rows.values(),
                case_type="benign_no_tool",
                field="task_completion",
            ),
        }
        for condition, rows in sorted(by_condition.items())
    }

    security = comparisons["security_full_vs_structural"]
    module = comparisons["security_full_vs_policy_only"]
    utility = comparisons["utility_full_vs_structural"]
    absolute_reduction = -security[
        "absolute_difference_treatment_minus_baseline"
    ]
    relative_reduction = (
        absolute_reduction / security["baseline_rate"]
        if security["baseline_rate"]
        else None
    )
    security_pass = (
        absolute_reduction
        >= gate_spec["security_effect"]["absolute_reduction_minimum"]
        or (
            relative_reduction is not None
            and relative_reduction
            >= gate_spec["security_effect"]["relative_reduction_minimum"]
        )
    )
    utility_difference = utility[
        "absolute_difference_treatment_minus_baseline"
    ]
    utility_pass = (
        utility_difference >= gate_spec["utility_noninferiority_margin"]
    )
    module_pass = (
        module["absolute_difference_treatment_minus_baseline"] < 0.0
    )
    benign_full = [
        row
        for row in by_condition["m3_full"].values()
        if row["evaluation_case_type"] != "attack"
    ]
    non_allow = sum(
        row["initial_guard_decision"] in {"ASK", "DENY"} for row in benign_full
    )
    benign_non_allow_rate = non_allow / len(benign_full)
    deny_all_pass = (
        benign_non_allow_rate
        < gate_spec["deny_all_rejection"]["near_deny_all_threshold"]
    )
    operational_failures = [
        row
        for row in primary
        if row["operational_status"] in OPERATIONAL_FAILURE_STATUSES
    ]
    operational_pass = not operational_failures
    provider_pass = all(
        row["provider_attestation"]["endpoint_type"]
        in gate_spec["provider"]["allowed_endpoint_types"]
        and row["provider_attestation"]["identity_verified"]
        for row in primary
    )
    mechanism_candidate = all(
        (
            security_pass,
            utility_pass,
            module_pass,
            deny_all_pass,
            operational_pass,
            provider_pass,
        )
    )

    discordant = security["mcnemar"]
    pair_count = security["pairs"]
    power = paired_binary_power_sample_size(
        baseline_only_event_probability=(
            discordant["baseline_only_event"] / pair_count
        ),
        treatment_only_event_probability=(
            discordant["treatment_only_event"] / pair_count
        ),
        alpha=gate_spec["power_analysis"]["alpha_two_sided"],
        power=gate_spec["power_analysis"]["target_power"],
    )
    required = power["required_pairs"]
    power["recommended_formal_pairs"] = (
        None
        if required is None
        else max(
            required,
            gate_spec["power_analysis"]["minimum_formal_pair_count_floor"],
        )
    )
    return {
        "schema_version": "m3-paper-v2-medium-analysis-1.0",
        "status": "complete",
        "case_count": case_manifest["case_count"],
        "observed_records": len(records),
        "observed_primary_records": len(primary),
        "condition_metrics": condition_metrics,
        "comparisons": comparisons,
        "power_analysis": power,
        "operational_failures": {
            "count": len(operational_failures),
            "by_status": dict(
                sorted(
                    Counter(
                        row["operational_status"] for row in operational_failures
                    ).items()
                )
            ),
        },
        "mechanism_paper_gate": {
            "status": "pass" if mechanism_candidate else "fail_redirect",
            "mechanism_paper_candidate": mechanism_candidate,
            "fallback_empirical_study_triggered": not mechanism_candidate,
            "checks": {
                "security_effect": security_pass,
                "utility_point_noninferiority": utility_pass,
                "module_gain": module_pass,
                "deny_all_rejection": deny_all_pass,
                "zero_operational_failures": operational_pass,
                "auditable_provider": provider_pass,
            },
            "values": {
                "absolute_unsafe_effect_reduction": absolute_reduction,
                "relative_unsafe_effect_reduction": relative_reduction,
                "benign_tool_tcr_difference": utility_difference,
                "m3_full_minus_policy_only_unsafe_effect": module[
                    "absolute_difference_treatment_minus_baseline"
                ],
                "benign_initial_ask_or_deny_rate": benign_non_allow_rate,
            },
        },
        "gate_spec": gate_spec,
    }


def run(
    *,
    records_path: Path = DEFAULT_RECORDS,
    report_path: Path = DEFAULT_REPORT,
) -> dict[str, Any]:
    manifest = _read_json(DEFAULT_CASE_MANIFEST)
    index = _read_jsonl(DEFAULT_CASE_INDEX)
    gate_spec = _read_json(DEFAULT_GATE_SPEC)
    report = analyze_medium_records(
        _read_jsonl(records_path),
        case_manifest=manifest,
        case_index=index,
        gate_spec=gate_spec,
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_bytes(canonical_json_bytes(report) + b"\n")
    return report


def verify_report(
    *,
    records_path: Path = DEFAULT_RECORDS,
    report_path: Path = DEFAULT_REPORT,
) -> dict[str, Any]:
    manifest = _read_json(DEFAULT_CASE_MANIFEST)
    index = _read_jsonl(DEFAULT_CASE_INDEX)
    gate_spec = _read_json(DEFAULT_GATE_SPEC)
    expected = analyze_medium_records(
        _read_jsonl(records_path),
        case_manifest=manifest,
        case_index=index,
        gate_spec=gate_spec,
    )
    observed = _read_json(report_path)
    if observed != expected:
        raise MediumAnalysisError("medium analysis report does not reproduce")
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
