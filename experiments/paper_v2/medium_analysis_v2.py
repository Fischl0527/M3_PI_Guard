"""扩展的预注册 paper-v2 中等规模研究综合分析模块。

深入分析不同攻击变体下的防御衰减曲线与关键断裂点。
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from experiments.paper_v2.contracts import canonical_json_bytes
from experiments.paper_v2.contracts import (
    EXPERIMENT_RECORD_SCHEMA_VERSION as EXPERIMENT_RECORD_V1_VERSION,
)
from experiments.paper_v2.contracts_v2 import (
    EXPERIMENT_RECORD_SCHEMA_VERSION as EXPERIMENT_RECORD_V2_VERSION,
)
from experiments.paper_v2.contracts_v2 import validate_experiment_record_v2
from experiments.paper_v2.medium_analysis import (
    DEFAULT_CASE_INDEX,
    DEFAULT_CASE_MANIFEST,
    DEFAULT_GATE_SPEC,
    MediumAnalysisError,
    analyze_medium_records,
)
from m3_eval.statistics import mcnemar_exact, proportion_result


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TRACE_ATTESTATION_EVIDENCE_LEVEL = "prospective_formal_trace_eligible_v2"
DEFAULT_RECORDS = (
    PROJECT_ROOT / "outputs/paper_upgrade_v2/medium/experiment_records.jsonl"
)
DEFAULT_REPORT = (
    PROJECT_ROOT / "outputs/paper_upgrade_v2/medium/analysis_v2.json"
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


def _proportion(
    records: Sequence[Mapping[str, Any]],
    predicate: Callable[[Mapping[str, Any]], bool],
    *,
    metric: str,
) -> dict[str, Any]:
    result = proportion_result(sum(predicate(row) for row in records), len(records))
    result["metric"] = metric
    return result


def _percentile(values: Sequence[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _numeric_summary(values: Sequence[float]) -> dict[str, Any]:
    return {
        "n": len(values),
        "sum": sum(values) if values else 0.0,
        "mean": sum(values) / len(values) if values else None,
        "p50": _percentile(values, 0.50),
        "p95": _percentile(values, 0.95),
        "minimum": min(values) if values else None,
        "maximum": max(values) if values else None,
    }


def project_record_for_primary_analysis(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """从经验证的 v2 论据记录创建 v1 分析视图。

    该视图仅更改论据包络的表示形式。结果、决策、条件、体制、延迟和 Token 字段逐字复制。
    """

    version = record.get("schema_version")
    if version == EXPERIMENT_RECORD_V1_VERSION:
        return dict(record)
    if version != EXPERIMENT_RECORD_V2_VERSION:
        raise MediumAnalysisError(f"unsupported experiment record: {version!r}")
    validate_experiment_record_v2(record)
    bundle = record["provider_trace_bundle"]
    attestations = bundle["activated_attestations"]
    if not attestations:
        raise MediumAnalysisError(
            "v2 analysis projection requires an activated provider attestation"
        )
    if record["result_tier"] not in {"formal_candidate", "formal_admitted"}:
        raise MediumAnalysisError(
            "v2 analysis projection requires formally admissible evidence"
        )
    exact_identity = all(
        attestation["official_network"] is True
        and attestation["exact_model_identity"] is True
        and attestation["evidence_level"] == TRACE_ATTESTATION_EVIDENCE_LEVEL
        for attestation in attestations
    )
    if not exact_identity:
        raise MediumAnalysisError(
            "v2 analysis projection requires exact official identity"
        )
    last = attestations[-1]
    excluded = {"provider_trace_bundle", "provider_safety_receipt"}
    projected = {
        key: value for key, value in record.items() if key not in excluded
    }
    projected["schema_version"] = EXPERIMENT_RECORD_V1_VERSION
    projected["provider_attestation"] = {
        "endpoint_type": "official_api",
        "provider_name": "DeepSeek",
        "upstream_provider": "DeepSeek",
        "model_id": bundle["model_id"],
        "model_revision": "provider_managed",
        "request_id": f"bundle:{bundle['bundle_sha256']}",
        "response_id": last["provider_response_id"],
        "requested_at": record["recorded_at"],
        "parameters_sha256": bundle["trace_rows_sha256"],
        "prompt_rewrite_declaration": "none_declared",
        "identity_evidence": "official_response",
        "identity_verified": True,
        "evidence_level": "formal_candidate",
    }
    return projected


def _condition_operational_summary(
    records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    benign = [
        row for row in records if row["evaluation_case_type"] != "attack"
    ]
    attacks = [
        row for row in records if row["evaluation_case_type"] == "attack"
    ]
    asks = [row for row in records if row["initial_guard_decision"] == "ASK"]
    latency = {
        component: _numeric_summary(
            [float(row["latency_ms"][component]) for row in records]
        )
        for component in ("total", "model", "guard", "tool")
    }
    token_rows = [
        row for row in records if row["token_usage"]["available"] is True
    ]
    token_usage = {
        name: _numeric_summary(
            [float(row["token_usage"][name]) for row in token_rows]
        )
        for name in ("input", "output", "total")
    }
    bundle_costs = [
        float(row["provider_trace_bundle"]["usage_summary"]["cumulative_cost_cny"])
        for row in records
        if isinstance(row.get("provider_trace_bundle"), Mapping)
    ]
    provider_calls = [
        int(row["provider_trace_bundle"]["completed_request_count"])
        for row in records
        if isinstance(row.get("provider_trace_bundle"), Mapping)
    ]
    return {
        "record_count": len(records),
        "initial_decision_counts": dict(
            sorted(Counter(row["initial_guard_decision"] for row in records).items())
        ),
        "effective_decision_counts": dict(
            sorted(Counter(row["effective_decision"] for row in records).items())
        ),
        "operational_status_counts": dict(
            sorted(Counter(row["operational_status"] for row in records).items())
        ),
        "ask_rate_all": _proportion(
            records,
            lambda row: row["initial_guard_decision"] == "ASK",
            metric="ask_rate_all",
        ),
        "ask_rate_attack": _proportion(
            attacks,
            lambda row: row["initial_guard_decision"] == "ASK",
            metric="ask_rate_attack",
        ),
        "ask_rate_benign": _proportion(
            benign,
            lambda row: row["initial_guard_decision"] == "ASK",
            metric="ask_rate_benign",
        ),
        "deny_rate_benign": _proportion(
            benign,
            lambda row: row["initial_guard_decision"] == "DENY",
            metric="deny_rate_benign",
        ),
        "confirmation_burden": {
            "ask_count": len(asks),
            "confirmation_result_counts": dict(
                sorted(Counter(row["confirmation_result"] for row in asks).items())
            ),
            "ask_reason_counts": dict(
                sorted(Counter(str(row["ask_reason"]) for row in asks).items())
            ),
        },
        "latency_ms": latency,
        "token_usage": {
            "records_with_usage": len(token_rows),
            "records_without_usage": len(records) - len(token_rows),
            "summaries": token_usage,
        },
        "provider_cost_cny": {
            "identifiable": bool(bundle_costs),
            "method": (
                "sum_of_per_record_trace_bundle_costs"
                if bundle_costs
                else "not_available_in_v1_record"
            ),
            "record_count": len(bundle_costs),
            "sum": sum(bundle_costs) if bundle_costs else None,
        },
        "provider_calls": {
            "identifiable": bool(provider_calls),
            "record_count": len(provider_calls),
            "sum": sum(provider_calls) if provider_calls else None,
        },
    }


def _paired_regime_metric(
    auto: Mapping[str, Mapping[str, Any]],
    exact: Mapping[str, Mapping[str, Any]],
    *,
    field: str,
    transform: Callable[[Any], bool] = bool,
) -> dict[str, Any]:
    case_ids = sorted(set(auto) & set(exact))
    auto_values = [transform(auto[case_id][field]) for case_id in case_ids]
    exact_values = [transform(exact[case_id][field]) for case_id in case_ids]
    auto_rate = sum(auto_values) / len(case_ids) if case_ids else None
    exact_rate = sum(exact_values) / len(case_ids) if case_ids else None
    return {
        "pairs": len(case_ids),
        "auto_compiled_events": sum(auto_values),
        "exact_gold_events": sum(exact_values),
        "auto_compiled_rate": auto_rate,
        "exact_gold_rate": exact_rate,
        "exact_gold_minus_auto_compiled": (
            exact_rate - auto_rate
            if exact_rate is not None and auto_rate is not None
            else None
        ),
        "mcnemar": mcnemar_exact(auto_values, exact_values),
    }


def _authorization_regime_analysis(
    records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for condition in ("m3_policy_only", "m3_full"):
        auto = {
            str(row["case_id"]): row
            for row in records
            if row["condition_id"] == condition
            and row["authorization_regime"] == "auto_compiled"
        }
        alternate_regimes = sorted(
            {
                str(row["authorization_regime"])
                for row in records
                if row["condition_id"] == condition
                and row["authorization_regime"] != "auto_compiled"
            }
        )
        if not alternate_regimes:
            result[condition] = {
                "status": "no_authorization_regime_probe_records",
                "probe_records": 0,
                "regimes": {},
            }
            continue
        regimes: dict[str, Any] = {}
        total_probes = 0
        for regime in alternate_regimes:
            alternate = {
                str(row["case_id"]): row
                for row in records
                if row["condition_id"] == condition
                and row["authorization_regime"] == regime
            }
            total_probes += len(alternate)
            regimes[regime] = {
                "probe_records": len(alternate),
                "unsafe_effect_itt": _paired_regime_metric(
                    auto,
                    alternate,
                    field="unsafe_effect_itt",
                ),
                "task_completion": _paired_regime_metric(
                    auto,
                    alternate,
                    field="task_completion",
                ),
                "initial_ask": _paired_regime_metric(
                    auto,
                    alternate,
                    field="initial_guard_decision",
                    transform=lambda value: value == "ASK",
                ),
            }
        result[condition] = {
            "status": "complete",
            "probe_records": total_probes,
            "regimes": regimes,
        }
    return result


def _heterogeneity(
    records: Sequence[Mapping[str, Any]],
    case_index: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    metadata = {str(row["case_id"]): row for row in case_index}
    primary = [
        row
        for row in records
        if row["authorization_regime"] == "auto_compiled"
    ]
    dimensions = {
        "benchmark": lambda row: str(row["benchmark_id"]),
        "context_dependency": lambda row: (
            "context_dependent"
            if bool(metadata[str(row["case_id"])]["context_dependent"])
            else "context_independent"
        ),
        "source_set": lambda row: str(
            metadata[str(row["case_id"])]["source_set"]
        ),
    }
    output: dict[str, Any] = {}
    for dimension, grouper in dimensions.items():
        grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        for record in primary:
            grouped[grouper(record)].append(record)
        output[dimension] = {}
        for group, rows in sorted(grouped.items()):
            by_condition: dict[str, Any] = {}
            for condition in sorted({str(row["condition_id"]) for row in rows}):
                condition_rows = [
                    row for row in rows if row["condition_id"] == condition
                ]
                attacks = [
                    row
                    for row in condition_rows
                    if row["evaluation_case_type"] == "attack"
                ]
                benign = [
                    row
                    for row in condition_rows
                    if row["evaluation_case_type"] != "attack"
                ]
                by_condition[condition] = {
                    "unsafe_effect_itt": _proportion(
                        attacks,
                        lambda row: bool(row["unsafe_effect_itt"]),
                        metric="unsafe_effect_itt",
                    ),
                    "benign_task_completion": _proportion(
                        benign,
                        lambda row: bool(row["task_completion"]),
                        metric="benign_task_completion",
                    ),
                }
            output[dimension][group] = by_condition
    return output


def analyze_medium_records_v2(
    records: list[dict[str, Any]],
    *,
    case_manifest: Mapping[str, Any],
    case_index: list[Mapping[str, Any]],
    gate_spec: Mapping[str, Any],
    bootstrap_iterations: int | None = None,
) -> dict[str, Any]:
    analysis_records = [
        project_record_for_primary_analysis(record) for record in records
    ]
    primary = analyze_medium_records(
        analysis_records,
        case_manifest=case_manifest,
        case_index=case_index,
        gate_spec=gate_spec,
        bootstrap_iterations=bootstrap_iterations,
    )
    if primary["status"] != "complete":
        return {
            "schema_version": "m3-paper-v2-medium-analysis-2.0",
            "status": primary["status"],
            "primary_analysis": primary,
            "secondary_analysis": None,
        }
    primary_records = [
        row
        for row in records
        if row["authorization_regime"] == "auto_compiled"
        and row["condition_id"] in case_manifest["core_conditions"]
    ]
    by_condition = {
        condition: [
            row for row in primary_records if row["condition_id"] == condition
        ]
        for condition in case_manifest["core_conditions"]
    }
    return {
        "schema_version": "m3-paper-v2-medium-analysis-2.0",
        "status": "complete",
        "primary_analysis": primary,
        "secondary_analysis": {
            "condition_operational_metrics": {
                condition: _condition_operational_summary(rows)
                for condition, rows in by_condition.items()
            },
            "authorization_regime_probes": _authorization_regime_analysis(
                records
            ),
            "heterogeneity": _heterogeneity(records, case_index),
            "metric_identifiability": {
                "unsafe_effect_rate": {
                    "status": "directly_identifiable",
                    "field": "unsafe_effect_itt",
                },
                "task_completion_rate": {
                    "status": "directly_identifiable",
                    "field": "task_completion",
                },
                "UTR": {
                    "status": "not_identifiable_from_frozen_record_contract",
                    "reason": (
                        "No per-action offline authorization label is stored; "
                        "unsafe_effect_itt is not relabelled as UTR."
                    ),
                },
                "DSR": {
                    "status": "not_identifiable_from_frozen_record_contract",
                    "reason": (
                        "The frozen cross-benchmark record does not expose a "
                        "separate data-spill outcome; unsafe_effect_itt is not "
                        "relabelled as DSR."
                    ),
                },
            },
        },
    }


def run(
    *,
    records_path: Path = DEFAULT_RECORDS,
    report_path: Path = DEFAULT_REPORT,
) -> dict[str, Any]:
    report = analyze_medium_records_v2(
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
    expected = analyze_medium_records_v2(
        _read_jsonl(records_path),
        case_manifest=_read_json(DEFAULT_CASE_MANIFEST),
        case_index=_read_jsonl(DEFAULT_CASE_INDEX),
        gate_spec=_read_json(DEFAULT_GATE_SPEC),
    )
    observed = _read_json(report_path)
    if observed != expected:
        raise MediumAnalysisError("medium analysis v2 report does not reproduce")
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
