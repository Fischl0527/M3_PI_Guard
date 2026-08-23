"""Analyze the completed lean authorization-regime experiment once.

The input is the frozen 1,350-row plan plus one compact raw JSONL per provider.
For a recovered work item, only its latest terminal attempt contributes to the
scientific denominator; earlier no-response attempts remain in the raw file and
are counted in the recovery audit. Gemini retry state also consults the
content-free pause-event ledger used by the runner. No provider, response trace,
or historical evidence replay is performed here.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from experiments.paper_v2.lean_empirical_runner import (
    EXPECTED_COUNTS,
    PLAN_PATH,
    PROVIDER_OUTPUTS,
    _gemini_paused_work_keys,
    _latest_by_work_key as _runner_latest_by_work_key,
    _read_jsonl,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = (
    PROJECT_ROOT / "docs/research/paper_v2/lean_empirical/authorization_results_v1.json"
)
BOOTSTRAP_REPLICATES = 10_000
BOOTSTRAP_SEED = "m3-q2-lean-analysis-2026-08-20-v1"
FAILURE_STATUSES = {
    "timeout",
    "parse_failure",
    "max_steps",
    "provider_failure",
    "runner_failure",
    "post_response_runner_failure",
    "repeated_pre_response_failure",
    "pre_response_provider_failure",
    "rate_limit_exhausted_after_three_quota_days",
    "refusal",
}
CELL = tuple[str, str]


class LeanAuthorizationAnalysisError(ValueError):
    """Raised when compact evidence is incomplete or internally inconsistent."""


def _wilson(successes: int, total: int) -> dict[str, float | int]:
    if total <= 0:
        return {
            "successes": successes,
            "total": total,
            "rate": 0.0,
            "ci_low": 0.0,
            "ci_high": 0.0,
        }
    z = 1.959963984540054
    rate = successes / total
    denominator = 1 + z * z / total
    center = (rate + z * z / (2 * total)) / denominator
    half = (
        z
        * math.sqrt(rate * (1 - rate) / total + z * z / (4 * total * total))
        / denominator
    )
    return {
        "successes": successes,
        "total": total,
        "rate": round(rate, 8),
        "ci_low": round(max(0.0, center - half), 8),
        "ci_high": round(min(1.0, center + half), 8),
    }


def _exact_mcnemar(discordant_a_only: int, discordant_b_only: int) -> float:
    total = discordant_a_only + discordant_b_only
    if total == 0:
        return 1.0
    tail = min(discordant_a_only, discordant_b_only)
    probability = sum(math.comb(total, value) for value in range(tail + 1)) / (2**total)
    return round(min(1.0, 2 * probability), 12)


def _percentile(values: Sequence[float], probability: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def _bootstrap_difference(pairs: Sequence[tuple[bool, bool]]) -> dict[str, Any]:
    if not pairs:
        return {
            "replicates": BOOTSTRAP_REPLICATES,
            "ci_low": 0.0,
            "ci_high": 0.0,
        }
    seed = f"{BOOTSTRAP_SEED}\0{pairs}".encode()
    rng = random.Random(int.from_bytes(__import__("hashlib").sha256(seed).digest()))
    size = len(pairs)
    differences: list[float] = []
    for _ in range(BOOTSTRAP_REPLICATES):
        sampled = [pairs[rng.randrange(size)] for _ in range(size)]
        differences.append(
            sum(second for _, second in sampled) / size
            - sum(first for first, _ in sampled) / size
        )
    return {
        "replicates": BOOTSTRAP_REPLICATES,
        "ci_low": round(_percentile(differences, 0.025), 8),
        "ci_high": round(_percentile(differences, 0.975), 8),
    }


def _holm(p_values: Mapping[str, float]) -> dict[str, float]:
    ordered = sorted(p_values.items(), key=lambda item: (item[1], item[0]))
    adjusted: dict[str, float] = {}
    running = 0.0
    count = len(ordered)
    for index, (name, value) in enumerate(ordered):
        running = max(running, min(1.0, value * (count - index)))
        adjusted[name] = round(running, 12)
    return adjusted


def _latest_attempts(
    rows: Iterable[Mapping[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    attempt_counts: Counter[int] = Counter()
    for row in rows:
        key = str(row["work_key"])
        attempt = int(row["attempt"])
        attempt_counts[attempt] += 1
        previous = latest.get(key)
        if previous is not None and int(previous["attempt"]) >= attempt:
            raise LeanAuthorizationAnalysisError(
                f"{key}: attempts must increase in append order"
            )
        latest[key] = dict(row)
    return latest, {
        "raw_attempt_rows": sum(attempt_counts.values()),
        "attempt_counts": {
            str(key): value for key, value in sorted(attempt_counts.items())
        },
        "superseded_attempt_rows": sum(attempt_counts.values()) - len(latest),
    }


def _validate_provider(
    provider_id: str,
    plan_rows: Sequence[Mapping[str, Any]],
    raw_rows: Sequence[Mapping[str, Any]],
    *,
    allow_partial: bool,
    paused_work_keys: set[str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    plan = {str(row["work_key"]): dict(row) for row in plan_rows}
    _, recovery = _latest_attempts(raw_rows)
    latest = _runner_latest_by_work_key(
        raw_rows,
        paused_work_keys=paused_work_keys,
    )
    if not set(latest).issubset(plan):
        raise LeanAuthorizationAnalysisError(f"{provider_id}: unknown work key")
    if not allow_partial and len(latest) != EXPECTED_COUNTS[provider_id]:
        raise LeanAuthorizationAnalysisError(
            f"{provider_id}: expected {EXPECTED_COUNTS[provider_id]}, got {len(latest)}"
        )
    records: list[dict[str, Any]] = []
    observed_rows: list[dict[str, Any]] = []
    response_rows = 0
    official_ids: set[str] = set()
    for key, row in latest.items():
        planned = plan[key]
        for field in (
            "case_id",
            "benchmark",
            "condition_id",
            "authorization_regime",
            "provider_id",
            "model_id",
        ):
            observed_field = "configured_model" if field == "model_id" else field
            if row.get(observed_field) != planned.get(field):
                raise LeanAuthorizationAnalysisError(
                    f"{provider_id}:{key}: {field} drift"
                )
        if (
            row.get("online_forbidden_fields_present") is not False
            or row.get("provider_tools_enabled") is not False
            or row.get("external_effects_enabled") is not False
        ):
            raise LeanAuthorizationAnalysisError(
                f"{provider_id}:{key}: safety status drift"
            )
        terminal = (
            row.get("retry_eligible") is False
            and row.get("included_in_primary_itt") is True
        )
        recoverable = (
            row.get("retry_eligible") is True
            and row.get("included_in_primary_itt") is False
        )
        if not terminal and not recoverable:
            raise LeanAuthorizationAnalysisError(
                f"{provider_id}:{key}: terminal status drift"
            )
        if not allow_partial and not terminal:
            raise LeanAuthorizationAnalysisError(
                f"{provider_id}:{key}: nonterminal item in complete analysis"
            )
        requests = row.get("provider_requests")
        if not isinstance(requests, list):
            raise LeanAuthorizationAnalysisError(
                f"{provider_id}:{key}: provider requests missing"
            )
        response_ids = [
            str(request["provider_response_id"])
            for request in requests
            if isinstance(request, Mapping) and request.get("provider_response_id")
        ]
        if bool(response_ids) != bool(row.get("response_obtained")):
            raise LeanAuthorizationAnalysisError(
                f"{provider_id}:{key}: response evidence drift"
            )
        if response_ids:
            if not terminal:
                raise LeanAuthorizationAnalysisError(
                    f"{provider_id}:{key}: response-bearing item is nonterminal"
                )
            expected_model = str(planned["model_id"])
            if row.get("returned_models") != [expected_model]:
                raise LeanAuthorizationAnalysisError(
                    f"{provider_id}:{key}: returned model drift"
                )
            overlap = official_ids.intersection(response_ids)
            if overlap:
                raise LeanAuthorizationAnalysisError(
                    f"{provider_id}: duplicate official response ID"
                )
            official_ids.update(response_ids)
        merged = {**planned, **row}
        observed_rows.append(merged)
        if terminal:
            records.append(merged)
            response_rows += bool(response_ids)
    records.sort(key=lambda row: int(row["sequence"]))
    return records, {
        **recovery,
        "expected_work_items": EXPECTED_COUNTS[provider_id],
        "observed_work_items": len(observed_rows),
        "terminal_work_items": len(records),
        "pending_work_items": EXPECTED_COUNTS[provider_id] - len(records),
        "unstarted_work_items": EXPECTED_COUNTS[provider_id] - len(observed_rows),
        "nonterminal_observed_work_items": len(observed_rows) - len(records),
        "response_bearing_work_items": response_rows,
        "official_response_ids": len(official_ids),
        "operational_statuses": dict(
            sorted(Counter(str(row["operational_status"]) for row in records).items())
        ),
        "observed_operational_statuses": dict(
            sorted(
                Counter(
                    str(row["operational_status"]) for row in observed_rows
                ).items()
            )
        ),
        "provider_tools_enabled": 0,
        "external_effects_enabled": 0,
        "online_forbidden_fields": 0,
    }


def _cell(row: Mapping[str, Any]) -> CELL:
    return str(row["condition_id"]), str(row["authorization_regime"])


def _metric_value(row: Mapping[str, Any], endpoint: str) -> bool:
    if endpoint == "unsafe_effect":
        return bool(row["unsafe_effect"])
    if endpoint == "unsafe_or_operational_failure":
        return bool(row["unsafe_effect"]) or _operational_failure(row)
    if endpoint == "task_completion":
        return bool(row["task_completion"])
    raise LeanAuthorizationAnalysisError(f"unsupported endpoint: {endpoint}")


def _operational_failure(row: Mapping[str, Any]) -> bool:
    return str(row["operational_status"]) in FAILURE_STATUSES


def _paired_stats(
    rows: Sequence[Mapping[str, Any]],
    *,
    first: CELL,
    second: CELL,
    case_type: str,
    endpoint: str,
    benchmark: str | None = None,
) -> dict[str, Any]:
    by_case: dict[str, dict[CELL, Mapping[str, Any]]] = defaultdict(dict)
    for row in rows:
        if row["evaluation_case_type"] == case_type and (
            benchmark is None or row["benchmark"] == benchmark
        ):
            by_case[str(row["case_id"])][_cell(row)] = row
    pairs: list[tuple[bool, bool]] = []
    for values in by_case.values():
        if first in values and second in values:
            pairs.append(
                (
                    _metric_value(values[first], endpoint),
                    _metric_value(values[second], endpoint),
                )
            )
    if not pairs:
        raise LeanAuthorizationAnalysisError(
            f"no pairs for {first} vs {second} / {case_type}"
        )
    first_success = sum(value for value, _ in pairs)
    second_success = sum(value for _, value in pairs)
    first_only = sum(
        first_value and not second_value for first_value, second_value in pairs
    )
    second_only = sum(
        second_value and not first_value for first_value, second_value in pairs
    )
    return {
        "first": {"condition_id": first[0], "authorization_regime": first[1]},
        "second": {"condition_id": second[0], "authorization_regime": second[1]},
        "case_type": case_type,
        "endpoint": endpoint,
        "benchmark": benchmark or "all",
        "paired_cases": len(pairs),
        "first_rate": _wilson(first_success, len(pairs)),
        "second_rate": _wilson(second_success, len(pairs)),
        "absolute_difference_second_minus_first": round(
            second_success / len(pairs) - first_success / len(pairs), 8
        ),
        "discordant_first_only": first_only,
        "discordant_second_only": second_only,
        "exact_mcnemar_p": _exact_mcnemar(first_only, second_only),
        "cluster_bootstrap": _bootstrap_difference(pairs),
    }


def _burden_summary(values: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    latencies = sorted(
        float(row.get("latency_ms", {}).get("total", 0.0)) for row in values
    )
    records = len(values)
    ask_count = sum(int(row.get("ask_count", 0)) for row in values)
    deny_count = sum(int(row.get("deny_count", 0)) for row in values)
    ask_record_count = sum(int(row.get("ask_count", 0)) > 0 for row in values)
    deny_record_count = sum(int(row.get("deny_count", 0)) > 0 for row in values)
    failure_count = sum(_operational_failure(row) for row in values)
    tokens = sum(int(row.get("token_usage", {}).get("total", 0)) for row in values)
    amount = sum(float(row.get("cost", {}).get("amount", 0.0)) for row in values)
    return {
        "records": records,
        "ask_count": ask_count,
        "deny_count": deny_count,
        "ask_record_count": ask_record_count,
        "deny_record_count": deny_record_count,
        "ask_record_rate": round(ask_record_count / records, 8),
        "deny_record_rate": round(deny_record_count / records, 8),
        "mean_ask_events_per_record": round(ask_count / records, 8),
        "mean_deny_events_per_record": round(deny_count / records, 8),
        "failure_count": failure_count,
        "failure_rate": round(failure_count / records, 8),
        "latency_p50_ms": round(_percentile(latencies, 0.5), 6),
        "latency_p95_ms": round(_percentile(latencies, 0.95), 6),
        "tokens": tokens,
        "cost_amount": round(amount, 9),
        "cost_currency": values[0]["cost"]["currency"],
    }


def _burden(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    grouped: dict[CELL, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[_cell(row)].append(row)
    return {
        f"{cell[0]}__{cell[1]}": _burden_summary(values)
        for cell, values in sorted(grouped.items())
    }


def _burden_by_case_and_benchmark(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Stratify system decision incidence and runtime burden without pooling tasks."""

    grouped: dict[tuple[str, str, str, str], list[Mapping[str, Any]]] = defaultdict(
        list
    )
    for row in rows:
        cell = _cell(row)
        grouped[
            (
                cell[0],
                cell[1],
                str(row["evaluation_case_type"]),
                str(row["benchmark"]),
            )
        ].append(row)
    return {
        "__".join(key): {
            "condition_id": key[0],
            "authorization_regime": key[1],
            "case_type": key[2],
            "benchmark": key[3],
            **_burden_summary(values),
        }
        for key, values in sorted(grouped.items())
    }


def _condition_metrics(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Return chart-ready endpoint summaries without changing study denominators."""

    grouped: dict[CELL, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[_cell(row)].append(row)
    output: dict[str, Any] = {}
    for cell, values in sorted(grouped.items()):
        attacks = [row for row in values if row["evaluation_case_type"] == "attack"]
        benign_tool = [
            row for row in values if row["evaluation_case_type"] == "benign_tool"
        ]
        benign_no_tool = [
            row for row in values if row["evaluation_case_type"] == "benign_no_tool"
        ]
        output[f"{cell[0]}__{cell[1]}"] = {
            "condition_id": cell[0],
            "authorization_regime": cell[1],
            "records": len(values),
            "attack_unsafe_effect": _wilson(
                sum(bool(row["unsafe_effect"]) for row in attacks), len(attacks)
            ),
            "attack_unsafe_or_operational_failure": _wilson(
                sum(
                    bool(row["unsafe_effect"]) or _operational_failure(row)
                    for row in attacks
                ),
                len(attacks),
            ),
            "benign_tool_tcr": _wilson(
                sum(bool(row["task_completion"]) for row in benign_tool),
                len(benign_tool),
            ),
            "benign_no_tool_tcr": _wilson(
                sum(bool(row["task_completion"]) for row in benign_no_tool),
                len(benign_no_tool),
            ),
        }
    return output


DEEPSEEK_COMPARISONS: tuple[tuple[str, CELL, CELL], ...] = (
    (
        "policy_auto_to_exact",
        ("m3_policy_only", "auto_compiled"),
        ("m3_policy_only", "exact_gold"),
    ),
    (
        "full_auto_to_exact",
        ("m3_full", "auto_compiled"),
        ("m3_full", "exact_gold"),
    ),
    (
        "auto_policy_to_full",
        ("m3_policy_only", "auto_compiled"),
        ("m3_full", "auto_compiled"),
    ),
    (
        "exact_policy_to_full",
        ("m3_policy_only", "exact_gold"),
        ("m3_full", "exact_gold"),
    ),
)

GEMINI_COMPARISONS: tuple[tuple[str, CELL, CELL], ...] = (
    (
        "auto_structural_to_full",
        ("strongest_peer_reviewed_structural_baseline", "auto_compiled"),
        ("m3_full", "auto_compiled"),
    ),
    (
        "auto_policy_to_full",
        ("m3_policy_only", "auto_compiled"),
        ("m3_full", "auto_compiled"),
    ),
    (
        "policy_auto_to_exact",
        ("m3_policy_only", "auto_compiled"),
        ("m3_policy_only", "exact_gold"),
    ),
    (
        "full_auto_to_exact",
        ("m3_full", "auto_compiled"),
        ("m3_full", "exact_gold"),
    ),
)


def _comparisons(
    rows: Sequence[Mapping[str, Any]],
    definitions: Sequence[tuple[str, CELL, CELL]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for case_type, endpoint in (
        ("attack", "unsafe_effect"),
        ("benign_tool", "task_completion"),
    ):
        endpoint_rows: dict[str, Any] = {}
        for name, first, second in definitions:
            endpoint_rows[name] = _paired_stats(
                rows,
                first=first,
                second=second,
                case_type=case_type,
                endpoint=endpoint,
            )
        adjusted = _holm(
            {name: value["exact_mcnemar_p"] for name, value in endpoint_rows.items()}
        )
        for name, value in endpoint_rows.items():
            value["holm_adjusted_p_within_endpoint"] = adjusted[name]
        result[endpoint] = endpoint_rows
    return result


def _regime_extension(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    first = ("m3_full", "auto_compiled")
    output: dict[str, Any] = {}
    for regime in ("broad", "underspecified", "conflicting"):
        second = ("m3_full", regime)
        output[regime] = {
            "unsafe_effect": _paired_stats(
                rows,
                first=first,
                second=second,
                case_type="attack",
                endpoint="unsafe_effect",
            ),
            "benign_tool_tcr": _paired_stats(
                rows,
                first=first,
                second=second,
                case_type="benign_tool",
                endpoint="task_completion",
            ),
        }
    return output


def _failure_sensitive_security(
    rows: Sequence[Mapping[str, Any]],
    definitions: Sequence[tuple[str, CELL, CELL]],
) -> dict[str, Any]:
    """Return a pessimistic robustness bound; it is not an attack-success label."""

    attacks = [row for row in rows if row["evaluation_case_type"] == "attack"]
    grouped: dict[CELL, list[Mapping[str, Any]]] = defaultdict(list)
    for row in attacks:
        grouped[_cell(row)].append(row)
    condition_rates = {
        f"{cell[0]}__{cell[1]}": {
            "condition_id": cell[0],
            "authorization_regime": cell[1],
            "unsafe_effects": sum(bool(row["unsafe_effect"]) for row in values),
            "operational_failures": sum(_operational_failure(row) for row in values),
            "unsafe_or_operational_failure": _wilson(
                sum(
                    bool(row["unsafe_effect"]) or _operational_failure(row)
                    for row in values
                ),
                len(values),
            ),
        }
        for cell, values in sorted(grouped.items())
    }
    comparisons = {
        name: _paired_stats(
            rows,
            first=first,
            second=second,
            case_type="attack",
            endpoint="unsafe_or_operational_failure",
        )
        for name, first, second in definitions
    }
    return {
        "interpretation": (
            "pessimistic robustness bound; operational failures are not relabeled "
            "as observed unsafe effects"
        ),
        "condition_rates": condition_rates,
        "paired_comparisons": comparisons,
    }


def _benchmark_stratified_comparisons(
    rows: Sequence[Mapping[str, Any]],
    definitions: Sequence[tuple[str, CELL, CELL]],
) -> dict[str, Any]:
    benchmarks = sorted({str(row["benchmark"]) for row in rows})
    output: dict[str, Any] = {}
    for benchmark in benchmarks:
        output[benchmark] = {
            "benign_tool_tcr": {
                name: _paired_stats(
                    rows,
                    first=first,
                    second=second,
                    case_type="benign_tool",
                    endpoint="task_completion",
                    benchmark=benchmark,
                )
                for name, first, second in definitions
            },
            "attack_unsafe_or_operational_failure": {
                name: _paired_stats(
                    rows,
                    first=first,
                    second=second,
                    case_type="attack",
                    endpoint="unsafe_or_operational_failure",
                    benchmark=benchmark,
                )
                for name, first, second in definitions
            },
        }
    return output


def _heterogeneity(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    groups: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        family = str(
            row.get("selection_stratum", {}).get("attack_family", "not_attack")
        )
        groups[(str(row["benchmark"]), family)].append(row)
    for (benchmark, family), values in sorted(groups.items()):
        output[f"{benchmark}__{family}"] = {
            "records": len(values),
            "attack_records": sum(
                row["evaluation_case_type"] == "attack" for row in values
            ),
            "unsafe_effects": sum(bool(row["unsafe_effect"]) for row in values),
            "operational_failures": sum(
                str(row["operational_status"]) in FAILURE_STATUSES for row in values
            ),
        }
    return output


def build_analysis(
    *,
    allow_partial_gemini: bool = False,
    deepseek_only: bool = False,
) -> dict[str, Any]:
    plan_rows = _read_jsonl(PLAN_PATH)
    by_provider = {
        provider: [row for row in plan_rows if row["provider_id"] == provider]
        for provider in EXPECTED_COUNTS
    }
    records: dict[str, list[dict[str, Any]]] = {}
    integrity: dict[str, Any] = {}
    providers = ("deepseek",) if deepseek_only else ("deepseek", "gemini")
    for provider in providers:
        records[provider], integrity[provider] = _validate_provider(
            provider,
            by_provider[provider],
            _read_jsonl(PROVIDER_OUTPUTS[provider]),
            allow_partial=(provider == "gemini" and allow_partial_gemini),
            paused_work_keys=(
                _gemini_paused_work_keys(PROVIDER_OUTPUTS[provider].parent)
                if provider == "gemini"
                else set()
            ),
        )
    if deepseek_only:
        records["gemini"] = []
        integrity["gemini"] = {
            "status": "not_analyzed_pending_provider_completion",
            "planned_work_items": EXPECTED_COUNTS["gemini"],
            "terminal_work_items": 0,
        }
    gemini_complete = (
        not deepseek_only
        and integrity["gemini"]["terminal_work_items"]
        == EXPECTED_COUNTS["gemini"]
    )
    analysis = {
        "schema_version": "m3-paper-v2-lean-authorization-analysis-1.1",
        "study_id": "m3-q2-lean-authorization-v1",
        "analysis_policy": {
            "latest_terminal_attempt_per_work_key": True,
            "superseded_no_response_attempts_retained_but_not_double_counted": True,
            "all_terminal_work_items_in_itt": True,
            "bootstrap_replicates": BOOTSTRAP_REPLICATES,
            "full_harness_used": False,
            "historical_recursive_replay_used": False,
            "deepseek_only": deepseek_only,
            "allow_partial_gemini": allow_partial_gemini,
        },
        "integrity": integrity,
        "deepseek": {
            "condition_metrics": _condition_metrics(records["deepseek"]),
            "comparisons": _comparisons(records["deepseek"], DEEPSEEK_COMPARISONS),
            "regime_extension": _regime_extension(records["deepseek"]),
            "failure_sensitive_security": _failure_sensitive_security(
                records["deepseek"], DEEPSEEK_COMPARISONS
            ),
            "benchmark_stratified_comparisons": _benchmark_stratified_comparisons(
                records["deepseek"], DEEPSEEK_COMPARISONS
            ),
            "burden": _burden(records["deepseek"]),
            "burden_by_case_and_benchmark": _burden_by_case_and_benchmark(
                records["deepseek"]
            ),
            "heterogeneity": _heterogeneity(records["deepseek"]),
        },
        "gemini": {
            "condition_metrics": _condition_metrics(records["gemini"]),
            "comparisons": (
                {}
                if deepseek_only or not gemini_complete
                else _comparisons(records["gemini"], GEMINI_COMPARISONS)
            ),
            "burden": _burden(records["gemini"]),
            "heterogeneity": _heterogeneity(records["gemini"]),
            "cross_vendor_claim_eligible": (
                gemini_complete
            ),
            "analysis_status": (
                "pending_provider_completion"
                if deepseek_only
                else "complete"
                if gemini_complete
                else "diagnostic_partial"
            ),
        },
    }
    return analysis


def write_analysis(
    *,
    output: Path = DEFAULT_OUTPUT,
    allow_partial_gemini: bool = False,
    deepseek_only: bool = False,
) -> dict[str, Any]:
    analysis = build_analysis(
        allow_partial_gemini=allow_partial_gemini,
        deepseek_only=deepseek_only,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(analysis, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return analysis


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--allow-partial-gemini", action="store_true")
    mode.add_argument("--deepseek-only", action="store_true")
    args = parser.parse_args()
    analysis = write_analysis(
        output=args.output,
        allow_partial_gemini=args.allow_partial_gemini,
        deepseek_only=args.deepseek_only,
    )
    print(
        json.dumps(
            {
                "deepseek": analysis["integrity"]["deepseek"],
                "gemini": analysis["integrity"]["gemini"],
                "output": str(args.output),
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
