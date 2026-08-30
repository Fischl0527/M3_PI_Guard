"""One-pass analysis and Markdown reporting for the non-temporal E6-v2 B1 block.

This module is intentionally provider-free: it reads only the frozen v1 plan,
projects the untouched source-W3 rows to the independently identified B1 block,
and analyzes sanitized E6-v2 public records.  It never imports a provider client,
opens a credential file, replays E6-v1 outcomes, or treats B1 as a temporal
replicate.

Scientific endpoints use the latest valid outer attempt for each work item.
Operational burden uses every physical attempt so a response-less attempt that
is later recovered cannot disappear from resource accounting.  Missing or
unstarted rows remain explicit and are never silently counted as safe.
"""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import html
import json
import math
import random
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any, Iterable, Mapping, Sequence

from experiments.paper_v2.contracts import sha256_canonical_json
from m3_eval.statistics import (
    holm_adjust,
    mcnemar_exact,
    percentile,
    proportion_result,
    wilson_interval,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_PROTOCOL_ROOT = (
    PROJECT_ROOT / "protocols/paper_upgrade_v2/e6_cross_provider_calibration_v1"
)
OUTPUT_ROOT = PROJECT_ROOT / "outputs/experiments/e6_cross_provider_calibration_v2"
SOURCE_PLAN_PATHS = {
    "deepseek": SOURCE_PROTOCOL_ROOT / "execution_plan_deepseek_v1.jsonl",
    "gemini": SOURCE_PROTOCOL_ROOT / "execution_plan_gemini_v1.jsonl",
}
PROVIDER_ROOT_NAMES = {"deepseek": "deepseek_pro", "gemini": "gemini_flash"}
EXPECTED_MODELS = {
    "deepseek": "deepseek-v4-pro",
    "gemini": "gemini-3.6-flash",
}
EXPECTED_PLAN_COUNTS = {"deepseek": 360, "gemini": 180}
EXPECTED_TASK_COUNTS = {"deepseek": 60, "gemini": 30}
RAW_PATHS = {
    provider: OUTPUT_ROOT / root / "raw_records_v2.jsonl"
    for provider, root in PROVIDER_ROOT_NAMES.items()
}
GATE_PATHS = {
    provider: OUTPUT_ROOT / root / "window_gate_B1_v2.json"
    for provider, root in PROVIDER_ROOT_NAMES.items()
}
STATE_PATHS = {
    provider: OUTPUT_ROOT / root / "internal/window_state_B1_v2.json"
    for provider, root in PROVIDER_ROOT_NAMES.items()
}
CLOSE_PATHS = {
    provider: OUTPUT_ROOT / root / "block_seal_B1_v2.json"
    for provider, root in PROVIDER_ROOT_NAMES.items()
}

ANALYSIS_PATH = OUTPUT_ROOT / "analysis_v2.json"
REPORT_PATH = OUTPUT_ROOT / "report_v2.md"
TABLE_ROOT = OUTPUT_ROOT / "tables"
FIGURE_ROOT = OUTPUT_ROOT / "figures"

STUDY_ID = "m3-q2-e6-cross-provider-calibration-v2"
SOURCE_STUDY_ID = "m3-q2-e6-cross-provider-calibration-v1"
RAW_SCHEMA_VERSION = "m3-paper-v2-e6-raw-record-2.0"
ANALYSIS_SCHEMA_VERSION = "m3-paper-v2-e6-diagnostic-analysis-2.0"
BLOCK_ID = "B1"
SOURCE_WINDOW = "W3"
BLOCK_ROLE = "single_diagnostic_execution_block"
BOOTSTRAP_REPLICATES = 10_000
BOOTSTRAP_SEED = "m3-e6-b1-diagnostic-analysis-v2"

CONDITIONS = (
    "no_defense",
    "strongest_peer_reviewed_structural_baseline",
    "m3_policy_only",
    "m3_policy_safe_prompt",
    "m3_full_normal_prompt",
    "m3_full",
)
CONDITION_LABELS = {
    "no_defense": "No defense",
    "strongest_peer_reviewed_structural_baseline": "VIGIL",
    "m3_policy_only": "Policy / normal",
    "m3_policy_safe_prompt": "Policy / safe",
    "m3_full_normal_prompt": "Full / normal",
    "m3_full": "Full / safe",
}
PRIMARY_COMPARISONS = (
    (
        "vigil_vs_no_defense",
        "no_defense",
        "strongest_peer_reviewed_structural_baseline",
    ),
    ("policy_normal_vs_no_defense", "no_defense", "m3_policy_only"),
    ("full_safe_vs_no_defense", "no_defense", "m3_full"),
    (
        "full_safe_vs_vigil",
        "strongest_peer_reviewed_structural_baseline",
        "m3_full",
    ),
)
FACTOR_CELLS = {
    "policy_normal": "m3_policy_only",
    "policy_safe": "m3_policy_safe_prompt",
    "full_normal": "m3_full_normal_prompt",
    "full_safe": "m3_full",
}
SUCCESS_STATUS = "completed"


class E6B1AnalysisError(ValueError):
    """Raised when the B1 plan, attempts, or public evidence drift."""


def _read_jsonl(path: Path, *, missing_ok: bool = False) -> list[dict[str, Any]]:
    if not path.is_file():
        if missing_ok:
            return []
        raise E6B1AnalysisError(f"missing JSONL: {path}")
    rows: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            raise E6B1AnalysisError(f"{path}:{number}: blank JSONL row")
        value = json.loads(line)
        if not isinstance(value, dict):
            raise E6B1AnalysisError(f"{path}:{number}: expected object")
        rows.append(value)
    return rows


def _read_json(path: Path, *, missing_ok: bool = False) -> dict[str, Any] | None:
    if not path.is_file():
        if missing_ok:
            return None
        raise E6B1AnalysisError(f"missing JSON: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise E6B1AnalysisError(f"{path}: expected object")
    return value


def _execution_identity(provider: str) -> str:
    return sha256_canonical_json(
        {
            "schema_version": "m3-paper-v2-e6-execution-identity-2.0",
            "study_id": STUDY_ID,
            "provider_id": provider,
            "model_id": EXPECTED_MODELS[provider],
            "execution_block_id": BLOCK_ID,
            "source_design": "e6-cross-provider-calibration-v1",
            "repair_contract": "immediate-block-isolated-response-less-attempt-2",
        }
    )


def _project_source_row(source: Mapping[str, Any]) -> dict[str, Any]:
    if source.get("study_id") != SOURCE_STUDY_ID:
        raise E6B1AnalysisError("source plan study identity drift")
    if source.get("replicate_window") != SOURCE_WINDOW:
        raise E6B1AnalysisError("B1 projection accepts source-W3 rows only")
    provider = str(source.get("provider_id", ""))
    if provider not in EXPECTED_MODELS:
        raise E6B1AnalysisError(f"unsupported provider: {provider}")
    source_key = str(source.get("work_key", ""))
    if not source_key:
        raise E6B1AnalysisError("source work key is missing")
    value = copy.deepcopy(dict(source))
    value.update(
        {
            "schema_version": "m3-paper-v2-e6-work-item-2.0",
            "study_id": STUDY_ID,
            "run_id": f"e6-v2-{provider}-{BLOCK_ID}",
            "execution_identity": _execution_identity(provider),
            "work_key": f"e6-v2-immediate__{source_key}",
            "source_protocol_version": "e6-cross-provider-calibration-v1",
            "source_v1_work_key": source_key,
            "source_replicate_window": SOURCE_WINDOW,
            "source_replicate_index": source.get("replicate_index"),
            "replicate_window": BLOCK_ID,
            "replicate_index": 1,
            "sample_role": "risk_enriched_activity_diagnostic",
            "execution_block_id": BLOCK_ID,
            "execution_block_role": BLOCK_ROLE,
            "repair_protocol_version": "e6-response-less-recovery-v2",
            "temporal_replication_claim": False,
        }
    )
    return value


def load_projected_plan(provider: str) -> list[dict[str, Any]]:
    if provider not in SOURCE_PLAN_PATHS:
        raise E6B1AnalysisError(f"unsupported provider: {provider}")
    rows = [
        _project_source_row(row)
        for row in _read_jsonl(SOURCE_PLAN_PATHS[provider])
        if row.get("replicate_window") == SOURCE_WINDOW
    ]
    expected = EXPECTED_PLAN_COUNTS[provider]
    if len(rows) != expected or len({str(row["work_key"]) for row in rows}) != expected:
        raise E6B1AnalysisError(f"{provider}: projected B1 plan count drift")
    _validate_b1_rows(rows, context=f"{provider} projected plan")
    return rows


def _validate_b1_rows(rows: Sequence[Mapping[str, Any]], *, context: str) -> None:
    for row in rows:
        if row.get("study_id") != STUDY_ID:
            raise E6B1AnalysisError(f"{context}: study identity drift")
        if row.get("replicate_window") != BLOCK_ID:
            raise E6B1AnalysisError(f"{context}: W1/W2 or non-B1 row rejected")
        if row.get("execution_block_id") != BLOCK_ID:
            raise E6B1AnalysisError(f"{context}: execution block identity drift")
        if row.get("temporal_replication_claim") is not False:
            raise E6B1AnalysisError(f"{context}: temporal=true or missing boundary rejected")
        if row.get("execution_block_role") != BLOCK_ROLE:
            raise E6B1AnalysisError(f"{context}: execution block role identity drift")
        provider = str(row.get("provider_id", ""))
        if provider not in EXPECTED_MODELS:
            raise E6B1AnalysisError(f"{context}: provider identity drift")
        if row.get("run_id") != f"e6-v2-{provider}-{BLOCK_ID}":
            raise E6B1AnalysisError(f"{context}: run identity drift")
        if row.get("execution_identity") != _execution_identity(provider):
            raise E6B1AnalysisError(f"{context}: execution identity drift")
        if row.get("model_id") != EXPECTED_MODELS[provider]:
            raise E6B1AnalysisError(f"{context}: model identity drift")
        if not row.get("source_v1_work_key"):
            raise E6B1AnalysisError(f"{context}: source work key is missing")


def _has_response_evidence(row: Mapping[str, Any]) -> bool:
    if row.get("response_obtained") is True:
        return True
    requests = row.get("provider_requests")
    return isinstance(requests, list) and any(
        isinstance(request, Mapping)
        and bool(request.get("provider_response_id") or request.get("response_id"))
        for request in requests
    )


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_sha256_hex(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _is_administrative_closure(row: Mapping[str, Any]) -> bool:
    return row.get("record_kind") == "block_closure"


def _latest_attempts(
    raw_rows: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    _validate_b1_rows(raw_rows, context="raw records")
    latest: dict[str, dict[str, Any]] = {}
    histories: dict[str, list[dict[str, Any]]] = defaultdict(list)
    physical_attempt_rows = 0
    administrative_closure_rows = 0
    identity_fields = (
        "run_id",
        "execution_identity",
        "provider_id",
        "model_id",
        "configured_model",
        "underlying_task_id",
        "case_id",
        "benchmark",
        "condition_id",
        "replicate_window",
        "execution_block_id",
        "execution_block_role",
        "source_v1_work_key",
        "source_replicate_window",
    )
    for raw in raw_rows:
        row = copy.deepcopy(dict(raw))
        if row.get("schema_version") != RAW_SCHEMA_VERSION:
            raise E6B1AnalysisError("raw record schema identity drift")
        key = str(row.get("work_key", ""))
        attempt = row.get("attempt")
        if row.get("record_kind") not in {"execution", "block_closure"}:
            raise E6B1AnalysisError(f"{key or 'unknown'}: raw record kind drift")
        administrative = _is_administrative_closure(row)
        allowed_attempts = {0, 1, 2} if administrative else {1, 2}
        if not key or isinstance(attempt, bool) or attempt not in allowed_attempts:
            raise E6B1AnalysisError("invalid B1 work key or outer attempt")
        history = histories[key]
        if administrative:
            administrative_closure_rows += 1
            if history:
                previous = history[-1]
                if _is_administrative_closure(previous):
                    raise E6B1AnalysisError(f"{key}: duplicate administrative closure")
                if int(attempt) != int(previous["attempt"]):
                    raise E6B1AnalysisError(
                        f"{key}: administrative closure changed outer attempt"
                    )
                if any(row.get(field) != previous.get(field) for field in identity_fields):
                    raise E6B1AnalysisError(f"{key}: closure identity drift")
            elif int(attempt) != 0:
                raise E6B1AnalysisError(
                    f"{key}: untouched administrative closure must use attempt 0"
                )
            if row.get("closure_is_model_outcome") is not False:
                raise E6B1AnalysisError(
                    f"{key}: administrative closure must disclaim model outcome"
                )
            if row.get("terminal_status") is not True:
                raise E6B1AnalysisError(f"{key}: administrative closure must be terminal")
        elif history:
            previous = history[-1]
            if _is_administrative_closure(previous):
                raise E6B1AnalysisError(f"{key}: execution appended after block closure")
            if int(attempt) <= int(previous["attempt"]):
                raise E6B1AnalysisError(f"{key}: attempts are not append-only")
            if any(row.get(field) != previous.get(field) for field in identity_fields):
                raise E6B1AnalysisError(f"{key}: attempt identity drift")
            if int(attempt) != 2 or len(history) != 1:
                raise E6B1AnalysisError(f"{key}: unsupported recovery history")
            if _has_response_evidence(previous):
                raise E6B1AnalysisError(f"{key}: response-bearing attempt was replayed")
            if previous.get("retry_eligible") is not True:
                raise E6B1AnalysisError(f"{key}: attempt 1 was not retry eligible")
            if row.get("terminal_status") is not True:
                raise E6B1AnalysisError(f"{key}: attempt 2 must be terminal")
        elif int(attempt) != 1:
            raise E6B1AnalysisError(f"{key}: attempt 2 has no attempt 1")
        if not administrative:
            physical_attempt_rows += 1
        history.append(row)
        latest[key] = row
    return latest, {
        "raw_append_rows": len(raw_rows),
        "physical_attempt_rows": physical_attempt_rows,
        "administrative_closure_rows": administrative_closure_rows,
        "latest_work_items": len(latest),
        "superseded_attempt_rows": len(raw_rows) - len(latest),
        "recovered_work_items": sum(
            {int(row["attempt"]) for row in history if not _is_administrative_closure(row)}
            == {1, 2}
            for history in histories.values()
        ),
    }


def merge_plan_and_raw(
    plan_rows: Sequence[Mapping[str, Any]],
    raw_rows: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    _validate_b1_rows(plan_rows, context="B1 plan")
    plan = {str(row.get("work_key", "")): copy.deepcopy(dict(row)) for row in plan_rows}
    if "" in plan or len(plan) != len(plan_rows):
        raise E6B1AnalysisError("B1 plan contains missing or duplicate work keys")
    latest, attempt_audit = _latest_attempts(raw_rows)
    extra = set(latest) - set(plan)
    if extra:
        raise E6B1AnalysisError(f"raw work keys absent from B1 plan: {sorted(extra)[:3]}")
    identity_fields = (
        "run_id",
        "execution_identity",
        "provider_id",
        "model_id",
        "underlying_task_id",
        "case_id",
        "benchmark",
        "condition_id",
        "replicate_window",
        "execution_block_id",
        "execution_block_role",
        "source_v1_work_key",
        "source_replicate_window",
    )
    merged: list[dict[str, Any]] = []
    for key, planned in plan.items():
        observed = latest.get(key)
        if observed is None:
            merged.append(
                {
                    **planned,
                    "_observed": False,
                    "_terminal": False,
                    "_scientific_terminal": False,
                    "_administrative_closure": False,
                    "_response_bearing": False,
                    "attempt": None,
                    "operational_status": "not_started",
                    "unsafe_effect": False,
                }
            )
            continue
        for field in identity_fields:
            if planned.get(field) != observed.get(field):
                raise E6B1AnalysisError(f"{key}: {field} identity drift")
        expected_model = planned.get("model_id")
        configured = observed.get("configured_model", observed.get("model_id"))
        if configured != expected_model:
            raise E6B1AnalysisError(f"{key}: configured model identity drift")
        merged.append(
            {
                **planned,
                **observed,
                "_observed": True,
                "_terminal": observed.get("terminal_status") is True,
                "_scientific_terminal": observed.get("terminal_status") is True
                and not _is_administrative_closure(observed),
                "_administrative_closure": _is_administrative_closure(observed),
                "_response_bearing": _has_response_evidence(observed),
            }
        )
    merged.sort(key=lambda row: (int(row.get("sequence", 0)), str(row["work_key"])))
    return merged, {
        **attempt_audit,
        "planned_work_items": len(plan_rows),
        "observed_latest_work_items": sum(bool(row["_observed"]) for row in merged),
        "terminal_latest_work_items": sum(bool(row["_terminal"]) for row in merged),
        "scientific_terminal_latest_work_items": sum(
            bool(row["_scientific_terminal"]) for row in merged
        ),
        "administrative_closure_work_items": sum(
            bool(row["_administrative_closure"]) for row in merged
        ),
        "response_bearing_latest_work_items": sum(
            bool(row["_response_bearing"]) for row in merged
        ),
        "unresolved_or_unstarted_work_items": sum(
            not bool(row["_scientific_terminal"]) for row in merged
        ),
        "nonterminal_or_unstarted_work_items": sum(
            not bool(row["_terminal"]) for row in merged
        ),
        "missing_work_items": sum(not bool(row["_observed"]) for row in merged),
    }


def _is_failure(row: Mapping[str, Any]) -> bool:
    return bool(row.get("_terminal")) and row.get("operational_status") != SUCCESS_STATUS


def _endpoint(row: Mapping[str, Any], endpoint: str) -> bool:
    if endpoint == "unsafe_effect":
        return bool(row.get("unsafe_effect"))
    if endpoint == "unsafe_or_failure":
        return bool(row.get("unsafe_effect")) or _is_failure(row)
    raise E6B1AnalysisError(f"unsupported endpoint: {endpoint}")


def _newcombe_paired(
    baseline: Sequence[bool], treatment: Sequence[bool]
) -> dict[str, Any]:
    if len(baseline) != len(treatment):
        raise E6B1AnalysisError("paired samples differ in length")
    total = len(baseline)
    if total == 0:
        return {
            "method": "newcombe_paired_hybrid_score",
            "pairs": 0,
            "estimate": None,
            "ci_low": None,
            "ci_high": None,
        }
    n00 = n01 = n10 = n11 = 0
    for left, right in zip(baseline, treatment, strict=True):
        if left and right:
            n11 += 1
        elif left:
            n10 += 1
        elif right:
            n01 += 1
        else:
            n00 += 1
    p_left = (n10 + n11) / total
    p_right = (n01 + n11) / total
    left_low, left_high = wilson_interval(n10 + n11, total)
    right_low, right_high = wilson_interval(n01 + n11, total)
    assert None not in (left_low, left_high, right_low, right_high)
    denominator = math.sqrt(
        p_left * (1.0 - p_left) * p_right * (1.0 - p_right)
    )
    correlation = (
        ((n11 / total) - p_left * p_right) / denominator
        if denominator > 0.0
        else 0.0
    )
    correlation = max(-1.0, min(1.0, correlation))
    estimate = p_right - p_left
    lower_margin = math.sqrt(
        max(
            0.0,
            (p_right - float(right_low)) ** 2
            + (float(left_high) - p_left) ** 2
            - 2.0
            * correlation
            * (p_right - float(right_low))
            * (float(left_high) - p_left),
        )
    )
    upper_margin = math.sqrt(
        max(
            0.0,
            (float(right_high) - p_right) ** 2
            + (p_left - float(left_low)) ** 2
            - 2.0
            * correlation
            * (float(right_high) - p_right)
            * (p_left - float(left_low)),
        )
    )
    return {
        "method": "newcombe_paired_hybrid_score",
        "pairs": total,
        "n00": n00,
        "n01_treatment_only": n01,
        "n10_baseline_only": n10,
        "n11": n11,
        "estimate": estimate,
        "ci_low": max(-1.0, estimate - lower_margin),
        "ci_high": min(1.0, estimate + upper_margin),
    }


def _complete_condition_pairs(
    rows: Sequence[Mapping[str, Any]], baseline: str, treatment: str
) -> dict[str, dict[str, Mapping[str, Any]]]:
    grouped: dict[str, dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for row in rows:
        condition = str(row.get("condition_id", ""))
        if bool(row.get("_scientific_terminal")) and condition in {baseline, treatment}:
            task = str(row["underlying_task_id"])
            if condition in grouped[task]:
                raise E6B1AnalysisError(f"duplicate B1 task/condition: {task}:{condition}")
            grouped[task][condition] = row
    return {
        task: values
        for task, values in grouped.items()
        if set(values) == {baseline, treatment}
    }


def _paired_family(
    rows: Sequence[Mapping[str, Any]],
    *,
    endpoint: str,
    expected_tasks: int,
    replicates: int,
) -> dict[str, Any]:
    comparisons: list[dict[str, Any]] = []
    for name, baseline, treatment in PRIMARY_COMPARISONS:
        blocks = _complete_condition_pairs(rows, baseline, treatment)
        left = [_endpoint(values[baseline], endpoint) for values in blocks.values()]
        right = [_endpoint(values[treatment], endpoint) for values in blocks.values()]
        task_values: dict[str, tuple[str, float]] = {}
        for task, values in blocks.items():
            left_benchmark = str(values[baseline].get("benchmark", ""))
            right_benchmark = str(values[treatment].get("benchmark", ""))
            if left_benchmark != right_benchmark:
                raise E6B1AnalysisError(
                    f"{task}: paired comparison benchmark identity drift"
                )
            task_values[task] = (
                left_benchmark,
                float(_endpoint(values[treatment], endpoint))
                - float(_endpoint(values[baseline], endpoint)),
            )
        exact = mcnemar_exact(left, right)
        comparisons.append(
            {
                "comparison_id": name,
                "endpoint": endpoint,
                "effect_direction": "treatment_minus_baseline",
                "baseline": baseline,
                "treatment": treatment,
                "expected_pairs": expected_tasks,
                "complete_pairs": len(blocks),
                "pair_coverage": len(blocks) / expected_tasks if expected_tasks else None,
                "baseline_rate": proportion_result(sum(left), len(left)),
                "treatment_rate": proportion_result(sum(right), len(right)),
                "newcombe_95": _newcombe_paired(left, right),
                "paired_task_bootstrap_95": _task_bootstrap(
                    task_values,
                    label=f"paired:{endpoint}:{name}",
                    replicates=replicates,
                ),
                "mcnemar_exact": exact,
            }
        )
    adjusted = holm_adjust(
        [float(item["mcnemar_exact"]["p_value"]) for item in comparisons]
    )
    for item, value in zip(comparisons, adjusted, strict=True):
        item["holm_adjusted_p"] = value
    return {
        "endpoint": endpoint,
        "multiplicity": "Holm across four within-provider B1 comparisons",
        "comparisons": {item["comparison_id"]: item for item in comparisons},
    }


def _bootstrap_seed(label: str) -> int:
    digest = hashlib.sha256(f"{BOOTSTRAP_SEED}\0{label}".encode()).digest()
    return int.from_bytes(digest[:8], "big")


def _task_bootstrap(
    task_values: Mapping[str, tuple[str, float]],
    *,
    label: str,
    replicates: int,
) -> dict[str, Any]:
    if replicates <= 0:
        raise E6B1AnalysisError("bootstrap replicates must be positive")
    strata: dict[str, list[float]] = defaultdict(list)
    for benchmark, value in task_values.values():
        number = float(value)
        if not math.isfinite(number):
            raise E6B1AnalysisError("bootstrap values must be finite")
        strata[str(benchmark)].append(number)
    if not strata:
        return {
            "method": "benchmark_stratified_task_bootstrap",
            "replicates": replicates,
            "tasks": 0,
            "estimate": None,
            "ci_low": None,
            "ci_high": None,
            "degenerate": False,
        }
    observed = [value for values in strata.values() for value in values]
    degenerate = len(set(observed)) == 1
    if degenerate:
        return {
            "method": "benchmark_stratified_task_bootstrap",
            "replicates": replicates,
            "tasks": len(observed),
            "estimate": mean(observed),
            "ci_low": None,
            "ci_high": None,
            "degenerate": True,
            "note": "empirical bootstrap degenerated; no zero-width certainty claimed",
        }
    rng = random.Random(_bootstrap_seed(label))
    distribution: list[float] = []
    for _ in range(replicates):
        sample = [
            rng.choice(values)
            for _, values in sorted(strata.items())
            for _ in range(len(values))
        ]
        distribution.append(mean(sample))
    return {
        "method": "benchmark_stratified_task_bootstrap",
        "replicates": replicates,
        "tasks": len(observed),
        "stratum_tasks": {
            benchmark: len(values) for benchmark, values in sorted(strata.items())
        },
        "estimate": mean(observed),
        "ci_low": percentile(distribution, 0.025),
        "ci_high": percentile(distribution, 0.975),
        "degenerate": False,
    }


def _factorial_2x2(
    rows: Sequence[Mapping[str, Any]], *, endpoint: str, replicates: int
) -> dict[str, Any]:
    grouped: dict[str, dict[str, Mapping[str, Any]]] = defaultdict(dict)
    cells = set(FACTOR_CELLS.values())
    for row in rows:
        condition = str(row.get("condition_id", ""))
        if bool(row.get("_scientific_terminal")) and condition in cells:
            task = str(row["underlying_task_id"])
            if condition in grouped[task]:
                raise E6B1AnalysisError(f"duplicate factorial cell: {task}:{condition}")
            grouped[task][condition] = row
    complete = {task: values for task, values in grouped.items() if set(values) == cells}
    effects: dict[str, dict[str, tuple[str, float]]] = {
        "module": {},
        "prompt": {},
        "module_x_prompt": {},
    }
    for task, values in complete.items():
        p0 = float(_endpoint(values[FACTOR_CELLS["policy_normal"]], endpoint))
        p1 = float(_endpoint(values[FACTOR_CELLS["policy_safe"]], endpoint))
        f0 = float(_endpoint(values[FACTOR_CELLS["full_normal"]], endpoint))
        f1 = float(_endpoint(values[FACTOR_CELLS["full_safe"]], endpoint))
        benchmark = str(values[FACTOR_CELLS["policy_normal"]]["benchmark"])
        effects["module"][task] = (benchmark, (f0 + f1 - p0 - p1) / 2.0)
        effects["prompt"][task] = (benchmark, (p1 + f1 - p0 - f0) / 2.0)
        effects["module_x_prompt"][task] = (benchmark, (f1 - f0) - (p1 - p0))
    return {
        "endpoint": endpoint,
        "complete_tasks": len(complete),
        "effects": {
            name: _task_bootstrap(
                values,
                label=f"factor:{endpoint}:{name}",
                replicates=replicates,
            )
            for name, values in effects.items()
        },
        "claim_boundary": "single-block paired diagnostic; not temporal repeatability",
    }


def _summarize_values(values: Iterable[float]) -> dict[str, Any]:
    sample = [float(value) for value in values]
    if any(not math.isfinite(value) or value < 0.0 for value in sample):
        raise E6B1AnalysisError("burden values must be finite and non-negative")
    return {
        "count": len(sample),
        "sum": sum(sample),
        "p50": percentile(sample, 0.50),
        "p95": percentile(sample, 0.95),
    }


def _number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    number = float(value)
    if not math.isfinite(number) or number < 0.0:
        raise E6B1AnalysisError("resource value must be finite and non-negative")
    return number


def _resource_summary(raw_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    raw_rows = [row for row in raw_rows if not _is_administrative_closure(row)]
    by_condition: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in raw_rows:
        by_condition[str(row.get("condition_id", ""))].append(row)

    def summarize(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        latency_total: list[float] = []
        latency_model: list[float] = []
        provider_calls: list[float] = []
        token_totals = {"input": 0.0, "output": 0.0, "total": 0.0}
        cost_by_currency: dict[str, float] = defaultdict(float)
        for row in rows:
            latency = row.get("latency_ms")
            if isinstance(latency, Mapping):
                if latency.get("total") is not None:
                    latency_total.append(_number(latency.get("total")))
                if latency.get("model") is not None:
                    latency_model.append(_number(latency.get("model")))
            if row.get("provider_call_count") is not None:
                provider_calls.append(_number(row.get("provider_call_count")))
            usage = row.get("token_usage")
            if isinstance(usage, Mapping):
                for field in token_totals:
                    token_totals[field] += _number(usage.get(field))
            cost = row.get("cost")
            if isinstance(cost, Mapping) and cost.get("currency"):
                cost_by_currency[str(cost["currency"])] += _number(cost.get("amount"))
        return {
            "physical_attempt_rows": len(rows),
            "latency_total_ms": _summarize_values(latency_total),
            "latency_model_ms": _summarize_values(latency_model),
            "provider_calls": _summarize_values(provider_calls),
            "tokens": {key: round(value, 6) for key, value in token_totals.items()},
            "cost_by_currency": {
                key: round(value, 10) for key, value in sorted(cost_by_currency.items())
            },
        }

    return {
        "accounting_scope": "all physical attempts, including superseded response-less attempts",
        "overall": summarize(raw_rows),
        "by_condition": {
            condition: summarize(by_condition.get(condition, [])) for condition in CONDITIONS
        },
    }


def _cell_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for benchmark in ("all", "agentdojo-v1", "m3-v2"):
        scoped = rows if benchmark == "all" else [
            row for row in rows if row.get("benchmark") == benchmark
        ]
        for condition in CONDITIONS:
            values = [row for row in scoped if row.get("condition_id") == condition]
            terminal = [row for row in values if bool(row.get("_terminal"))]
            scientific_terminal = [
                row for row in values if bool(row.get("_scientific_terminal"))
            ]
            observed = [row for row in values if bool(row.get("_observed"))]
            administrative = [
                row for row in values if bool(row.get("_administrative_closure"))
            ]
            unsafe = sum(
                bool(row.get("unsafe_effect")) for row in scientific_terminal
            )
            failures = sum(_is_failure(row) for row in scientific_terminal)
            unsafe_or_failure = sum(
                bool(row.get("unsafe_effect")) or _is_failure(row)
                for row in scientific_terminal
            )
            unresolved = len(values) - len(scientific_terminal)
            nonterminal = len(values) - len(terminal)
            key = f"{benchmark}|{condition}"
            result[key] = {
                "benchmark": benchmark,
                "condition_id": condition,
                "planned": len(values),
                "observed_latest": len(observed),
                "terminal_latest": len(terminal),
                "scientific_terminal_latest": len(scientific_terminal),
                "administrative_closure_latest": len(administrative),
                "response_bearing_latest": sum(
                    bool(row.get("_response_bearing")) for row in values
                ),
                "unresolved_or_unstarted": unresolved,
                "nonterminal_or_unstarted": nonterminal,
                "unsafe_count": unsafe,
                "operational_failure_count": failures,
                "unsafe_or_failure_count": unsafe_or_failure,
                "unsafe_terminal": proportion_result(
                    unsafe, len(scientific_terminal)
                ),
                "unsafe_itt_observed_lower": proportion_result(unsafe, len(values)),
                "unsafe_or_failure_terminal": proportion_result(
                    unsafe_or_failure, len(scientific_terminal)
                ),
                "unsafe_or_failure_or_unresolved_upper": proportion_result(
                    unsafe_or_failure + unresolved, len(values)
                ),
                "ask_events": sum(
                    int(row.get("ask_count", 0) or 0) for row in scientific_terminal
                ),
                "deny_events": sum(
                    int(row.get("deny_count", 0) or 0) for row in scientific_terminal
                ),
                "records_with_ask": sum(
                    int(row.get("ask_count", 0) or 0) > 0
                    for row in scientific_terminal
                ),
                "records_with_deny": sum(
                    int(row.get("deny_count", 0) or 0) > 0
                    for row in scientific_terminal
                ),
                "operational_statuses": dict(
                    sorted(
                        Counter(
                            str(row.get("operational_status", "unknown"))
                            for row in observed
                        ).items()
                    )
                ),
            }
    return result


def _request_iter(rows: Sequence[Mapping[str, Any]]) -> Iterable[Mapping[str, Any]]:
    for row in rows:
        requests = row.get("provider_requests")
        if isinstance(requests, list):
            for request in requests:
                if isinstance(request, Mapping):
                    yield request


def _systemic_failure_key(row: Mapping[str, Any]) -> str | None:
    status = str(row.get("operational_status", ""))
    if status == "provider_failure":
        diagnostic = row.get("runtime_failure_diagnostic")
        failure_class = (
            str(diagnostic.get("failure_class", "unknown"))
            if isinstance(diagnostic, Mapping)
            else str(row.get("error_type", "unknown"))
        )
        return f"provider_failure:{failure_class}"
    if status in {
        "runner_failure",
        "post_response_runner_failure",
        "contract_failure",
        "pre_response_transport_failure",
    }:
        return f"{status}:{row.get('error_type') or 'unknown'}"
    return None


def _technical_audit(
    provider: str,
    merged: Sequence[Mapping[str, Any]],
    raw_rows: Sequence[Mapping[str, Any]],
    gate: Mapping[str, Any] | None,
) -> dict[str, Any]:
    expected_model = EXPECTED_MODELS[provider]
    observed = [row for row in merged if bool(row.get("_observed"))]
    physical_rows = [row for row in raw_rows if not _is_administrative_closure(row)]
    response_bearing_attempts = [
        row for row in physical_rows if _has_response_evidence(row)
    ]
    observed_records_present = bool(observed)
    physical_attempts_present = bool(physical_rows)
    response_evidence_present = bool(response_bearing_attempts)
    exact_model = all(
        row.get("returned_models") == [expected_model]
        and row.get("returned_model_id") == expected_model
        for row in response_bearing_attempts
    )
    complete_chain = all(
        isinstance(row.get("provider_requests"), list)
        and bool(row["provider_requests"])
        and all(
            isinstance(request, Mapping)
            and _nonempty_string(request.get("local_request_id"))
            and _is_sha256_hex(request.get("payload_sha256"))
            and _nonempty_string(request.get("provider_response_id"))
            and request.get("returned_model") == expected_model
            for request in row["provider_requests"]
        )
        for row in response_bearing_attempts
    )
    response_ids = [
        str(request["provider_response_id"])
        for request in _request_iter(physical_rows)
        if request.get("provider_response_id")
    ]
    unique_response_ids = len(response_ids) == len(set(response_ids))
    local_request_ids = [
        str(request["local_request_id"])
        for request in _request_iter(physical_rows)
        if request.get("local_request_id")
    ]
    unique_local_request_ids = len(local_request_ids) == len(
        set(local_request_ids)
    )
    provider_call_counts_match = all(
        isinstance(row.get("provider_requests"), list)
        and int(row.get("provider_call_count", -1))
        == len(row["provider_requests"])
        for row in physical_rows
    )
    visible_field_digests_complete = all(
        _is_sha256_hex(row.get("online_visible_field_digest_sha256"))
        for row in physical_rows
    )
    field_isolation = all(
        row.get("online_forbidden_fields_present") is False for row in physical_rows
    )
    no_tools_effects = all(
        row.get("provider_tools_enabled") is False
        and row.get("external_effects_enabled") is False
        for row in physical_rows
    )
    call_caps = all(
        int(row.get("provider_call_count", 0) or 0)
        <= (16 if row.get("condition_id") == CONDITIONS[1] else 8)
        for row in physical_rows
    )
    free_tier = provider != "gemini" or all(
        row.get("free_tier_attestation")
        == {
            "billing_tier": "free",
            "cost_usd": 0.0,
            "paid_fallback_enabled": False,
        }
        and row.get("cost")
        == {"currency": "USD", "amount": 0.0, "billing_tier": "free"}
        for row in physical_rows
    )
    failure_counts = Counter(
        (str(row.get("condition_id")), key)
        for row in observed
        if (key := _systemic_failure_key(row)) is not None
    )
    systemic = {
        "|".join(key): count for key, count in sorted(failure_counts.items()) if count >= 2
    }
    gate_bound = gate is not None and (
        gate.get("schema_version") == "m3-paper-v2-e6-window-gate-2.0"
        and gate.get("study_id") == STUDY_ID
        and gate.get("provider_id") == provider
        and gate.get("replicate_window") == BLOCK_ID
        and gate.get("execution_block_id") == BLOCK_ID
        and gate.get("execution_block_role") == BLOCK_ROLE
        and gate.get("temporal_replication_claim") is False
        and gate.get("scientific_outcomes_inspected") is False
    )
    return {
        "observed_latest": len(observed),
        "observed_records_present": observed_records_present,
        "physical_attempts_present": physical_attempts_present,
        "response_evidence_present": response_evidence_present,
        "physical_attempt_rows": len(physical_rows),
        "administrative_closure_rows": len(raw_rows) - len(physical_rows),
        "response_bearing_physical_attempts": len(response_bearing_attempts),
        "all_plan_rows_terminal": len(merged) > 0
        and all(bool(row.get("_terminal")) for row in merged),
        "exact_returned_model": exact_model,
        "complete_official_request_chain": complete_chain,
        "unique_official_response_ids": unique_response_ids,
        "unique_local_request_ids": unique_local_request_ids,
        "provider_call_counts_match_request_chain": provider_call_counts_match,
        "online_visible_field_digests_complete": visible_field_digests_complete,
        "online_field_isolation": field_isolation,
        "provider_tools_and_real_effects_disabled": no_tools_effects,
        "provider_call_caps_respected": call_caps,
        "gemini_free_tier_usd_zero": free_tier,
        "gate_identity_bound": gate_bound,
        "systemic_failure_counts": systemic,
        "no_repeated_systemic_failure": not systemic,
        "passed_for_observed_records": all(
            (
                observed_records_present,
                physical_attempts_present,
                response_evidence_present,
                exact_model,
                complete_chain,
                unique_response_ids,
                unique_local_request_ids,
                provider_call_counts_match,
                visible_field_digests_complete,
                field_isolation,
                no_tools_effects,
                call_caps,
                free_tier,
                gate_bound,
                not systemic,
            )
        ),
    }


def _parse_time(value: Any, *, field: str) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError as exc:
        raise E6B1AnalysisError(f"invalid {field} timestamp") from exc
    if parsed.tzinfo is None:
        raise E6B1AnalysisError(f"{field} timestamp must be timezone-aware")
    return parsed


def _first_time(values: Iterable[Any], *, field: str) -> datetime | None:
    parsed = [value for item in values if (value := _parse_time(item, field=field))]
    return min(parsed) if parsed else None


def _last_time(values: Iterable[Any], *, field: str) -> datetime | None:
    parsed = [value for item in values if (value := _parse_time(item, field=field))]
    return max(parsed) if parsed else None


def _timing_summary(
    raw_rows: Sequence[Mapping[str, Any]],
    state: Mapping[str, Any] | None,
    close: Mapping[str, Any] | None,
) -> dict[str, Any]:
    physical_rows = [row for row in raw_rows if not _is_administrative_closure(row)]
    start = _first_time(
        [
            state.get("window_started_at") if state else None,
            state.get("execution_block_started_at") if state else None,
            close.get("execution_block_started_at") if close else None,
            *(row.get("window_started_at") for row in physical_rows),
        ],
        field="block start",
    )
    last_observed = _last_time(
        (row.get("recorded_at") for row in physical_rows), field="last observed"
    )
    sealed = _last_time(
        [
            close.get("sealed_at") if close else None,
            close.get("ended_at") if close else None,
            close.get("window_completed_at") if close else None,
            close.get("execution_block_completed_at") if close else None,
        ],
        field="block seal",
    )
    for name, value in (("last_observed_at", last_observed), ("sealed_at", sealed)):
        if start is not None and value is not None and value < start:
            raise E6B1AnalysisError(f"{name} precedes block start")
    return {
        "block_started_at": start.isoformat() if start else None,
        "last_observed_at": last_observed.isoformat() if last_observed else None,
        "sealed_at": sealed.isoformat() if sealed else None,
        "observed_span_seconds": (
            (last_observed - start).total_seconds()
            if start is not None and last_observed is not None
            else None
        ),
        "sealed_span_seconds": (
            (sealed - start).total_seconds()
            if start is not None and sealed is not None
            else None
        ),
        "seal_status": "sealed" if sealed is not None else "not_sealed",
        "administrative_closure_rows_excluded_from_observation_time": sum(
            _is_administrative_closure(row) for row in raw_rows
        ),
        "timing_claim_boundary": "execution span only; not a temporal replicate",
    }


def _validate_support_artifacts(
    provider: str,
    *,
    state: Mapping[str, Any] | None,
    close: Mapping[str, Any] | None,
) -> None:
    if state is not None and (
        state.get("study_id") != STUDY_ID
        or state.get("provider_id") != provider
        or state.get("execution_block_id") != BLOCK_ID
        or state.get("temporal_replication_claim") is not False
    ):
        raise E6B1AnalysisError(f"{provider}: B1 state identity drift")
    if close is not None and (
        close.get("schema_version") != "m3-paper-v2-e6-block-seal-2.0"
        or close.get("study_id") != STUDY_ID
        or close.get("provider_id") != provider
        or close.get("execution_block_id") != BLOCK_ID
        or close.get("execution_block_role") != BLOCK_ROLE
        or close.get("temporal_replication_claim") is not False
        or close.get("status") != "sealed"
        or close.get("closure_mode")
        not in {
            "all_rows_terminal",
            "technical_gate_not_extended",
            "provider_unavailable",
            "fatal_stop",
        }
        or close.get("provider_tools_enabled") is not False
        or close.get("external_effects_enabled") is not False
    ):
        raise E6B1AnalysisError(f"{provider}: B1 seal identity drift")


def _validate_seal_against_evidence(
    provider: str,
    close: Mapping[str, Any] | None,
    gate: Mapping[str, Any] | None,
    plan_rows: Sequence[Mapping[str, Any]],
    merged: Sequence[Mapping[str, Any]],
    audit: Mapping[str, Any],
) -> None:
    if close is None:
        return
    expected_scalars = {
        "planned_rows": len(plan_rows),
        "terminal_rows": int(audit["terminal_latest_work_items"]),
        "response_bearing_rows": int(audit["response_bearing_latest_work_items"]),
        "administrative_closure_rows": int(
            audit["administrative_closure_work_items"]
        ),
        "gate_status": gate.get("status") if gate is not None else "not_available",
    }
    if any(close.get(field) != value for field, value in expected_scalars.items()):
        raise E6B1AnalysisError(f"{provider}: B1 seal counts do not bind raw evidence")
    expected_conditions: dict[str, dict[str, int]] = {}
    for condition in CONDITIONS:
        values = [row for row in merged if row.get("condition_id") == condition]
        expected_conditions[condition] = {
            "planned": len(values),
            "response_bearing": sum(
                bool(row.get("_response_bearing")) for row in values
            ),
            "administrative_closure": sum(
                bool(row.get("_administrative_closure")) for row in values
            ),
        }
    if close.get("condition_counts") != expected_conditions:
        raise E6B1AnalysisError(
            f"{provider}: B1 seal condition counts do not bind raw evidence"
        )


def analyze_provider_block(
    provider: str,
    *,
    plan_rows: Sequence[Mapping[str, Any]],
    raw_rows: Sequence[Mapping[str, Any]],
    gate: Mapping[str, Any] | None = None,
    state: Mapping[str, Any] | None = None,
    close: Mapping[str, Any] | None = None,
    bootstrap_replicates: int = BOOTSTRAP_REPLICATES,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if provider not in EXPECTED_MODELS:
        raise E6B1AnalysisError(f"unsupported provider: {provider}")
    if any(row.get("provider_id") != provider for row in plan_rows):
        raise E6B1AnalysisError(f"{provider}: plan mixes providers")
    if any(row.get("provider_id") != provider for row in raw_rows):
        raise E6B1AnalysisError(f"{provider}: raw evidence mixes providers")
    _validate_support_artifacts(provider, state=state, close=close)
    merged, audit = merge_plan_and_raw(plan_rows, raw_rows)
    _validate_seal_against_evidence(
        provider, close, gate, plan_rows, merged, audit
    )
    tasks = {str(row["underlying_task_id"]) for row in plan_rows}
    technical = _technical_audit(provider, merged, raw_rows, gate)
    cells = _cell_summary(merged)
    no_defense = cells["all|no_defense"]
    timing = _timing_summary(raw_rows, state, close)
    block_closed = timing["seal_status"] == "sealed"
    all_terminal = audit["terminal_latest_work_items"] == len(plan_rows)
    no_administrative_closure = audit["administrative_closure_work_items"] == 0
    technical_passed = technical["passed_for_observed_records"] is True
    if not technical_passed:
        status = "ANALYZED_TECHNICAL_AUDIT_FAILED_DIAGNOSTIC"
    elif block_closed and all_terminal and no_administrative_closure:
        status = "ANALYZED_COMPLETE_DIAGNOSTIC"
    elif block_closed and all_terminal:
        status = "ANALYZED_CLOSED_ADMINISTRATIVELY_INCOMPLETE_DIAGNOSTIC"
    elif block_closed:
        status = "ANALYZED_CLOSED_INCOMPLETE_DIAGNOSTIC"
    else:
        status = "ANALYZED_OPEN_OR_UNSEALED_DIAGNOSTIC"
    result = {
        "provider": provider,
        "model_id": EXPECTED_MODELS[provider],
        "analysis_status": status,
        "expected_tasks": len(tasks),
        "expected_plan_rows": len(plan_rows),
        "audit": audit,
        "technical_audit": technical,
        "gate": copy.deepcopy(dict(gate)) if gate is not None else None,
        "block_close": copy.deepcopy(dict(close)) if close is not None else None,
        "timing": timing,
        "cell_summary": cells,
        "no_defense_activity": {
            "risk_enriched_single_block": True,
            "terminal_rate": no_defense["unsafe_terminal"],
            "itt_observed_lower": no_defense["unsafe_itt_observed_lower"],
            "conservative_upper": no_defense[
                "unsafe_or_failure_or_unresolved_upper"
            ],
            "claim_boundary": "calibration-set activity during B1; not deployment prevalence",
        },
        "paired_comparisons": {
            endpoint: _paired_family(
                merged,
                endpoint=endpoint,
                expected_tasks=len(tasks),
                replicates=bootstrap_replicates,
            )
            for endpoint in ("unsafe_effect", "unsafe_or_failure")
        },
        "factorial_2x2": {
            endpoint: _factorial_2x2(
                merged, endpoint=endpoint, replicates=bootstrap_replicates
            )
            for endpoint in ("unsafe_effect", "unsafe_or_failure")
        },
        "burden": _resource_summary(raw_rows),
        "claim_eligibility": {
            "single_block_diagnostic": True,
            "temporal_repeatability": False,
            "deployment_prevalence": False,
            "formal_cross_provider_generalization": False,
            "benign_utility_or_tcr": False,
        },
    }
    return result, merged


def _nested_provider_diagnostic(
    deepseek_result: Mapping[str, Any],
    gemini_result: Mapping[str, Any],
    deepseek_rows: Sequence[Mapping[str, Any]],
    gemini_rows: Sequence[Mapping[str, Any]],
    *,
    bootstrap_replicates: int,
) -> dict[str, Any]:
    gm_tasks = {str(row["underlying_task_id"]) for row in gemini_rows}
    ds_tasks = {str(row["underlying_task_id"]) for row in deepseek_rows}
    nested = gm_tasks.issubset(ds_tasks)
    ds_payloads = {
        (str(row["underlying_task_id"]), str(row["condition_id"])): str(
            row.get("analysis_payload_digest_sha256", "")
        )
        for row in deepseek_rows
    }
    gm_payloads = {
        (str(row["underlying_task_id"]), str(row["condition_id"])): str(
            row.get("analysis_payload_digest_sha256", "")
        )
        for row in gemini_rows
    }
    payloads_match = all(ds_payloads.get(key) == digest for key, digest in gm_payloads.items())
    effects: dict[str, Any] = {}
    if nested and payloads_match:
        for endpoint in ("unsafe_effect", "unsafe_or_failure"):
            endpoint_effects: dict[str, Any] = {}
            for name, baseline, treatment in PRIMARY_COMPARISONS:
                ds_pairs = _complete_condition_pairs(deepseek_rows, baseline, treatment)
                gm_pairs = _complete_condition_pairs(gemini_rows, baseline, treatment)
                values: dict[str, tuple[str, float]] = {}
                for task in sorted(gm_tasks & set(ds_pairs) & set(gm_pairs)):
                    ds = float(_endpoint(ds_pairs[task][treatment], endpoint)) - float(
                        _endpoint(ds_pairs[task][baseline], endpoint)
                    )
                    gm = float(_endpoint(gm_pairs[task][treatment], endpoint)) - float(
                        _endpoint(gm_pairs[task][baseline], endpoint)
                    )
                    values[task] = (str(gm_pairs[task][baseline]["benchmark"]), gm - ds)
                endpoint_effects[name] = _task_bootstrap(
                    values,
                    label=f"nested:{endpoint}:{name}",
                    replicates=bootstrap_replicates,
                )
            effects[endpoint] = endpoint_effects
    return {
        "role": "nested_single_block_directional_diagnostic",
        "cross_provider_claim_eligible": False,
        "gemini_permanently_diagnostic": True,
        "nested_tasks": len(gm_tasks) if nested else 0,
        "gemini_tasks_nested_in_deepseek": nested,
        "analysis_payload_digests_match": payloads_match,
        "effect_direction": "gemini_risk_difference_minus_deepseek_risk_difference",
        "effect_differences": effects if nested and payloads_match else None,
        "claim_boundary": (
            "descriptive nested-task calibration only; no provider ranking or "
            "formal cross-provider generalization"
        ),
        "provider_statuses": {
            "deepseek": deepseek_result["analysis_status"],
            "gemini": gemini_result["analysis_status"],
        },
    }


def analyze_all(
    *,
    deepseek_plan: Sequence[Mapping[str, Any]],
    deepseek_raw: Sequence[Mapping[str, Any]],
    gemini_plan: Sequence[Mapping[str, Any]],
    gemini_raw: Sequence[Mapping[str, Any]],
    deepseek_gate: Mapping[str, Any] | None = None,
    gemini_gate: Mapping[str, Any] | None = None,
    deepseek_state: Mapping[str, Any] | None = None,
    gemini_state: Mapping[str, Any] | None = None,
    deepseek_close: Mapping[str, Any] | None = None,
    gemini_close: Mapping[str, Any] | None = None,
    bootstrap_replicates: int = BOOTSTRAP_REPLICATES,
) -> dict[str, Any]:
    deepseek, ds_rows = analyze_provider_block(
        "deepseek",
        plan_rows=deepseek_plan,
        raw_rows=deepseek_raw,
        gate=deepseek_gate,
        state=deepseek_state,
        close=deepseek_close,
        bootstrap_replicates=bootstrap_replicates,
    )
    gemini, gm_rows = analyze_provider_block(
        "gemini",
        plan_rows=gemini_plan,
        raw_rows=gemini_raw,
        gate=gemini_gate,
        state=gemini_state,
        close=gemini_close,
        bootstrap_replicates=bootstrap_replicates,
    )
    technical_green = all(
        value["technical_audit"]["passed_for_observed_records"] is True
        for value in (deepseek, gemini)
    )
    return {
        "schema_version": ANALYSIS_SCHEMA_VERSION,
        "study_id": STUDY_ID,
        "verification_status": (
            "ANALYZED_TECHNICAL_AUDIT_PASSED"
            if technical_green
            else "ANALYZED_TECHNICAL_AUDIT_FAILED"
        ),
        "material_passport": {
            "origin_skill": "academic-research-suite / experiment-agent",
            "mode": "validate",
            "analysis_role": "single B1 diagnostic execution block",
        },
        "analysis_boundaries": {
            "b1_only": True,
            "temporal_replication_claim": False,
            "v1_outcomes_read": False,
            "missing_rows_counted_safe": False,
            "latest_attempt_for_scientific_endpoints": True,
            "all_physical_attempts_for_resources": True,
            "gemini_diagnostic_only": True,
            "cross_provider_claim_eligible": False,
            "provider_clients_imported": False,
        },
        "providers": {"deepseek": deepseek, "gemini": gemini},
        "nested_provider_diagnostic": _nested_provider_diagnostic(
            deepseek,
            gemini,
            ds_rows,
            gm_rows,
            bootstrap_replicates=bootstrap_replicates,
        ),
    }


def _fmt_rate(value: Mapping[str, Any]) -> str:
    numerator = value.get("numerator")
    denominator = value.get("denominator")
    estimate = value.get("value")
    if estimate is None:
        return f"{numerator}/{denominator} (NA)"
    low = value.get("ci_low")
    high = value.get("ci_high")
    interval = "" if low is None or high is None else f", 95% CI {low:.3f}–{high:.3f}"
    return f"{numerator}/{denominator} ({estimate:.3f}{interval})"


def _fmt_number(value: Any, digits: int = 3) -> str:
    return "NA" if value is None else f"{float(value):.{digits}f}"


def render_markdown_report(analysis: Mapping[str, Any]) -> str:
    providers = analysis["providers"]
    lines = [
        "# E6-v2 B1 同期攻击活性诊断报告",
        "",
        "## Material Passport",
        "",
        "- Origin Skill：`academic-research-suite / experiment-agent`",
        "- Mode：`validate`",
        f"- Study ID：`{analysis['study_id']}`",
        f"- Verification Status：`{analysis['verification_status']}`",
        "- Evidence Role：`single diagnostic execution block`",
        "",
        "## 结论边界",
        "",
        "B1 是一次风险富集攻击校准块，只描述其实际执行跨度内的结果。它不构成跨日期重复性证据，不能与 E6-v1 W1/W2 合并，也不支持正式跨厂商泛化、部署流行率或良性任务效用结论。Gemini 始终为 diagnostic-only。",
        "",
        "## 执行与终态覆盖",
        "",
        "| Provider | Analysis status | Gate | Closure mode | Planned | Scientific terminal | Admin closure | Response-bearing | Unresolved | Sealed at |",
        "|---|---|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for provider in ("deepseek", "gemini"):
        value = providers[provider]
        audit = value["audit"]
        timing = value["timing"]
        gate = value.get("gate") or {}
        close = value.get("block_close") or {}
        lines.append(
            f"| {provider} | {value['analysis_status']} | {gate.get('status', 'NOT AVAILABLE')} | "
            f"{close.get('closure_mode', 'NOT SEALED')} | {audit['planned_work_items']} | "
            f"{audit['scientific_terminal_latest_work_items']} | "
            f"{audit['administrative_closure_work_items']} | "
            f"{audit['response_bearing_latest_work_items']} | "
            f"{audit['unresolved_or_unstarted_work_items']} | "
            f"{timing['sealed_at'] or 'NOT SEALED'} |"
        )

    lines.extend(
        [
            "",
            "## 技术审计",
            "",
            "| Provider | Returned model | Request chain | Local IDs unique | Visible digest | Field isolation | Tools/effects off | Call count/cap | Free tier | Overall |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
    )
    for provider in ("deepseek", "gemini"):
        audit = providers[provider]["technical_audit"]
        lines.append(
            f"| {provider} | {audit['exact_returned_model']} | "
            f"{audit['complete_official_request_chain']} | "
            f"{audit['unique_local_request_ids']} | "
            f"{audit['online_visible_field_digests_complete']} | "
            f"{audit['online_field_isolation']} | "
            f"{audit['provider_tools_and_real_effects_disabled']} | "
            f"{audit['provider_call_counts_match_request_chain'] and audit['provider_call_caps_respected']} | "
            f"{audit['gemini_free_tier_usd_zero']} | "
            f"{audit['passed_for_observed_records']} |"
        )
    lines.extend(
        [
            "",
            "## No-defense 活性",
            "",
            "| Provider | Terminal rate | ITT observed lower | Conservative upper |",
            "|---|---|---|---|",
        ]
    )
    for provider in ("deepseek", "gemini"):
        activity = providers[provider]["no_defense_activity"]
        lines.append(
            f"| {provider} | {_fmt_rate(activity['terminal_rate'])} | "
            f"{_fmt_rate(activity['itt_observed_lower'])} | "
            f"{_fmt_rate(activity['conservative_upper'])} |"
        )
    lines.extend(
        [
            "",
            "## 六条件结果",
            "",
        "| Provider | Condition | Planned | Scientific terminal | Administrative | Unsafe | Failure | Upper bound | ASK events | DENY events |",
        "|---|---|---:|---:|---:|---:|---:|---|---:|---:|",
        ]
    )
    for provider in ("deepseek", "gemini"):
        for condition in CONDITIONS:
            cell = providers[provider]["cell_summary"][f"all|{condition}"]
            lines.append(
                f"| {provider} | {CONDITION_LABELS[condition]} | {cell['planned']} | "
                f"{cell['scientific_terminal_latest']} | "
                f"{cell['administrative_closure_latest']} | {cell['unsafe_count']} | "
                f"{cell['operational_failure_count']} | "
                f"{_fmt_rate(cell['unsafe_or_failure_or_unresolved_upper'])} | "
                f"{cell['ask_events']} | {cell['deny_events']} |"
            )
    lines.extend(
        [
            "",
            "## 同块配对比较（unsafe effect）",
            "",
            "| Provider | Comparison | Complete/expected | Risk difference | Newcombe 95% CI | Stratified bootstrap 95% CI | McNemar p | Holm p |",
            "|---|---|---:|---:|---|---|---:|---:|",
        ]
    )
    for provider in ("deepseek", "gemini"):
        comparisons = providers[provider]["paired_comparisons"]["unsafe_effect"][
            "comparisons"
        ]
        for name, _, _ in PRIMARY_COMPARISONS:
            item = comparisons[name]
            interval = item["newcombe_95"]
            bootstrap = item["paired_task_bootstrap_95"]
            bootstrap_interval = (
                "DEGENERATE / no zero-width claim"
                if bootstrap["degenerate"]
                else f"[{_fmt_number(bootstrap['ci_low'])}, {_fmt_number(bootstrap['ci_high'])}]"
            )
            lines.append(
                f"| {provider} | {name} | {item['complete_pairs']}/{item['expected_pairs']} | "
                f"{_fmt_number(interval['estimate'])} | "
                f"[{_fmt_number(interval['ci_low'])}, {_fmt_number(interval['ci_high'])}] | "
                f"{bootstrap_interval} | "
                f"{_fmt_number(item['mcnemar_exact']['p_value'])} | "
                f"{_fmt_number(item['holm_adjusted_p'])} |"
            )
    lines.extend(
        [
            "",
            "## 2×2 因子诊断",
            "",
            "| Provider | Endpoint | Effect | Tasks | Estimate | Bootstrap 95% CI |",
            "|---|---|---|---:|---:|---|",
        ]
    )
    for provider in ("deepseek", "gemini"):
        for endpoint, factorial in providers[provider]["factorial_2x2"].items():
            for effect, value in factorial["effects"].items():
                interval = (
                    "DEGENERATE / no zero-width claim"
                    if value["degenerate"]
                    else f"[{_fmt_number(value['ci_low'])}, {_fmt_number(value['ci_high'])}]"
                )
                lines.append(
                    f"| {provider} | {endpoint} | {effect} | {value['tasks']} | "
                    f"{_fmt_number(value['estimate'])} | {interval} |"
                )
    lines.extend(
        [
            "",
            "## 运行负担（所有物理 attempts）",
            "",
            "| Provider | Physical rows | Provider calls | Tokens | Cost | Latency p50/p95 ms |",
            "|---|---:|---:|---:|---|---|",
        ]
    )
    for provider in ("deepseek", "gemini"):
        burden = providers[provider]["burden"]["overall"]
        calls = burden["provider_calls"]
        latency = burden["latency_total_ms"]
        cost = ", ".join(
            f"{currency} {amount:.6f}"
            for currency, amount in burden["cost_by_currency"].items()
        ) or "NA"
        lines.append(
            f"| {provider} | {burden['physical_attempt_rows']} | "
            f"{_fmt_number(calls['sum'], 0)} | {_fmt_number(burden['tokens']['total'], 0)} | "
            f"{cost} | {_fmt_number(latency['p50'])}/{_fmt_number(latency['p95'])} |"
        )
    nested = analysis["nested_provider_diagnostic"]
    lines.extend(
        [
            "",
            "## 跨 provider 边界",
            "",
            f"- Gemini tasks nested in DeepSeek：`{nested['gemini_tasks_nested_in_deepseek']}`",
            f"- Payload digests matched：`{nested['analysis_payload_digests_match']}`",
            "- Cross-provider claim eligible：`false`（固定）",
            "- 仅允许报告同一 30 个任务上的方向性诊断差，不进行 provider 排名。",
            "",
            "## 时间信息",
            "",
            "| Provider | Started | Last observed | Sealed | Observed span (s) | Sealed span (s) |",
            "|---|---|---|---|---:|---:|",
        ]
    )
    for provider in ("deepseek", "gemini"):
        timing = providers[provider]["timing"]
        lines.append(
            f"| {provider} | {timing['block_started_at'] or 'NA'} | "
            f"{timing['last_observed_at'] or 'NA'} | {timing['sealed_at'] or 'NOT SEALED'} | "
            f"{_fmt_number(timing['observed_span_seconds'], 1)} | "
            f"{_fmt_number(timing['sealed_span_seconds'], 1)} |"
        )
    lines.extend(
        [
            "",
            "## 解释限制",
            "",
            "- 样本由历史 unsafe control 结果富集，比例不是自然部署 ASR。",
            "- 缺失、未启动和未终态行没有被当作安全；报告同时给出 ITT 观测下界与保守上界。",
            "- 科学终点使用最新合法 attempt；token、调用、成本和延迟使用所有物理 attempts。",
            "- B1 不包含良性任务，因此不能增加 TCR 或效用证据。",
            "",
        ]
    )
    return "\n".join(lines)


def _write_csv(path: Path, fieldnames: Sequence[str], rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_tables(analysis: Mapping[str, Any], root: Path) -> None:
    cell_rows: list[dict[str, Any]] = []
    paired_rows: list[dict[str, Any]] = []
    burden_rows: list[dict[str, Any]] = []
    for provider, value in analysis["providers"].items():
        for cell in value["cell_summary"].values():
            cell_rows.append(
                {
                    "provider": provider,
                    "benchmark": cell["benchmark"],
                    "condition_id": cell["condition_id"],
                    "planned": cell["planned"],
                    "terminal": cell["terminal_latest"],
                    "scientific_terminal": cell["scientific_terminal_latest"],
                    "administrative_closure": cell[
                        "administrative_closure_latest"
                    ],
                    "unsafe": cell["unsafe_count"],
                    "operational_failure": cell["operational_failure_count"],
                    "unresolved": cell["unresolved_or_unstarted"],
                    "itt_lower": cell["unsafe_itt_observed_lower"]["value"],
                    "conservative_upper": cell[
                        "unsafe_or_failure_or_unresolved_upper"
                    ]["value"],
                }
            )
        for endpoint, family in value["paired_comparisons"].items():
            for item in family["comparisons"].values():
                paired_rows.append(
                    {
                        "provider": provider,
                        "endpoint": endpoint,
                        "comparison_id": item["comparison_id"],
                        "complete_pairs": item["complete_pairs"],
                        "expected_pairs": item["expected_pairs"],
                        "risk_difference": item["newcombe_95"]["estimate"],
                        "ci_low": item["newcombe_95"]["ci_low"],
                        "ci_high": item["newcombe_95"]["ci_high"],
                        "bootstrap_ci_low": item["paired_task_bootstrap_95"][
                            "ci_low"
                        ],
                        "bootstrap_ci_high": item["paired_task_bootstrap_95"][
                            "ci_high"
                        ],
                        "bootstrap_degenerate": item[
                            "paired_task_bootstrap_95"
                        ]["degenerate"],
                        "mcnemar_p": item["mcnemar_exact"]["p_value"],
                        "holm_p": item["holm_adjusted_p"],
                    }
                )
        for condition, burden in value["burden"]["by_condition"].items():
            burden_rows.append(
                {
                    "provider": provider,
                    "condition_id": condition,
                    "physical_attempt_rows": burden["physical_attempt_rows"],
                    "provider_calls": burden["provider_calls"]["sum"],
                    "tokens_total": burden["tokens"]["total"],
                    "latency_p50_ms": burden["latency_total_ms"]["p50"],
                    "latency_p95_ms": burden["latency_total_ms"]["p95"],
                    "cost_json": json.dumps(
                        burden["cost_by_currency"], sort_keys=True, separators=(",", ":")
                    ),
                }
            )
    _write_csv(
        root / "cell_summary_v2.csv",
        (
            "provider",
            "benchmark",
            "condition_id",
            "planned",
            "terminal",
            "scientific_terminal",
            "administrative_closure",
            "unsafe",
            "operational_failure",
            "unresolved",
            "itt_lower",
            "conservative_upper",
        ),
        cell_rows,
    )
    _write_csv(
        root / "paired_effects_v2.csv",
        (
            "provider",
            "endpoint",
            "comparison_id",
            "complete_pairs",
            "expected_pairs",
            "risk_difference",
            "ci_low",
            "ci_high",
            "bootstrap_ci_low",
            "bootstrap_ci_high",
            "bootstrap_degenerate",
            "mcnemar_p",
            "holm_p",
        ),
        paired_rows,
    )
    _write_csv(
        root / "burden_v2.csv",
        (
            "provider",
            "condition_id",
            "physical_attempt_rows",
            "provider_calls",
            "tokens_total",
            "latency_p50_ms",
            "latency_p95_ms",
            "cost_json",
        ),
        burden_rows,
    )


def _svg_document(title: str, body: str, *, width: int = 960, height: int = 540) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title">\n'
        f'<title id="title">{html.escape(title)}</title>\n'
        '<rect width="100%" height="100%" fill="#ffffff"/>\n'
        f"{body}\n</svg>\n"
    )


def _write_figures(analysis: Mapping[str, Any], root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    colors = {"deepseek": "#2f6f9f", "gemini": "#d47b29"}
    body = [
        '<text x="40" y="38" font-family="sans-serif" font-size="22" font-weight="bold">B1 unsafe-effect rates</text>',
        '<text x="40" y="62" font-family="sans-serif" font-size="13" fill="#555">Risk-enriched single-block diagnostic; unresolved rows shown separately in tables.</text>',
    ]
    bar_width = 46
    start_x = 80
    max_height = 330
    for provider_index, provider in enumerate(("deepseek", "gemini")):
        for index, condition in enumerate(CONDITIONS):
            cell = analysis["providers"][provider]["cell_summary"][f"all|{condition}"]
            rate = cell["unsafe_terminal"]["value"] or 0.0
            x = start_x + index * 140 + provider_index * (bar_width + 6)
            height = rate * max_height
            y = 430 - height
            body.append(
                f'<rect x="{x}" y="{y:.2f}" width="{bar_width}" height="{height:.2f}" fill="{colors[provider]}"/>'
            )
            body.append(
                f'<text x="{x + bar_width / 2:.1f}" y="{max(88, y - 5):.1f}" text-anchor="middle" font-family="sans-serif" font-size="11">{cell["unsafe_count"]}/{cell["scientific_terminal_latest"]}</text>'
            )
            if provider_index == 0:
                label = CONDITION_LABELS[condition].replace(" / ", "/")
                body.append(
                    f'<text x="{x + bar_width + 3}" y="462" text-anchor="middle" font-family="sans-serif" font-size="10" transform="rotate(-28 {x + bar_width + 3} 462)">{html.escape(label)}</text>'
                )
    body.extend(
        [
            '<line x1="55" y1="430" x2="930" y2="430" stroke="#333"/>',
            f'<rect x="690" y="30" width="14" height="14" fill="{colors["deepseek"]}"/><text x="710" y="42" font-family="sans-serif" font-size="12">DeepSeek</text>',
            f'<rect x="790" y="30" width="14" height="14" fill="{colors["gemini"]}"/><text x="810" y="42" font-family="sans-serif" font-size="12">Gemini</text>',
        ]
    )
    (root / "activity_conditions_v2.svg").write_text(
        _svg_document("B1 unsafe-effect condition rates", "\n".join(body)),
        encoding="utf-8",
    )

    nested = analysis["nested_provider_diagnostic"]
    body = [
        '<text x="40" y="38" font-family="sans-serif" font-size="22" font-weight="bold">Nested provider directional diagnostic</text>',
        '<text x="40" y="62" font-family="sans-serif" font-size="13" fill="#555">Gemini risk difference minus DeepSeek risk difference; no provider ranking.</text>',
        '<line x1="480" y1="90" x2="480" y2="480" stroke="#777" stroke-dasharray="5 4"/>',
    ]
    effects = nested.get("effect_differences") or {}
    unsafe = effects.get("unsafe_effect", {}) if isinstance(effects, Mapping) else {}
    for index, (name, _, _) in enumerate(PRIMARY_COMPARISONS):
        value = unsafe.get(name, {}) if isinstance(unsafe, Mapping) else {}
        estimate = value.get("estimate")
        y = 130 + index * 82
        body.append(
            f'<text x="40" y="{y + 5}" font-family="sans-serif" font-size="13">{html.escape(name)}</text>'
        )
        if estimate is None:
            body.append(
                f'<text x="520" y="{y + 5}" font-family="sans-serif" font-size="13" fill="#777">NA / incomplete pairs</text>'
            )
        else:
            x = 480 + float(estimate) * 320
            body.append(
                f'<circle cx="{x:.2f}" cy="{y}" r="7" fill="#5a3d8e"/>'
            )
            body.append(
                f'<text x="{x + 12:.2f}" y="{y + 5}" font-family="sans-serif" font-size="12">{float(estimate):.3f}</text>'
            )
    body.extend(
        [
            '<text x="160" y="510" font-family="sans-serif" font-size="12">−1</text>',
            '<text x="475" y="510" font-family="sans-serif" font-size="12">0</text>',
            '<text x="796" y="510" font-family="sans-serif" font-size="12">+1</text>',
        ]
    )
    (root / "nested_provider_diagnostic_v2.svg").write_text(
        _svg_document("Nested provider diagnostic effect differences", "\n".join(body)),
        encoding="utf-8",
    )


def write_outputs(analysis: Mapping[str, Any], *, output_root: Path = OUTPUT_ROOT) -> dict[str, str]:
    output_root.mkdir(parents=True, exist_ok=True)
    analysis_path = output_root / "analysis_v2.json"
    report_path = output_root / "report_v2.md"
    analysis_path.write_text(
        json.dumps(analysis, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    # The reader-facing artifacts are deliberately rendered from the persisted
    # JSON, not from a parallel in-memory calculation.
    persisted = json.loads(analysis_path.read_text(encoding="utf-8"))
    report_path.write_text(render_markdown_report(persisted), encoding="utf-8")
    _write_tables(persisted, output_root / "tables")
    _write_figures(persisted, output_root / "figures")
    return {
        "analysis": str(analysis_path),
        "report": str(report_path),
        "cell_table": str(output_root / "tables/cell_summary_v2.csv"),
        "paired_table": str(output_root / "tables/paired_effects_v2.csv"),
        "burden_table": str(output_root / "tables/burden_v2.csv"),
        "activity_figure": str(output_root / "figures/activity_conditions_v2.svg"),
        "nested_figure": str(
            output_root / "figures/nested_provider_diagnostic_v2.svg"
        ),
    }


def _load_current_analysis(*, bootstrap_replicates: int) -> dict[str, Any]:
    inputs: dict[str, Any] = {}
    for provider in ("deepseek", "gemini"):
        inputs[f"{provider}_plan"] = load_projected_plan(provider)
        inputs[f"{provider}_raw"] = _read_jsonl(RAW_PATHS[provider], missing_ok=True)
        inputs[f"{provider}_gate"] = _read_json(GATE_PATHS[provider], missing_ok=True)
        inputs[f"{provider}_state"] = _read_json(STATE_PATHS[provider], missing_ok=True)
        inputs[f"{provider}_close"] = _read_json(CLOSE_PATHS[provider], missing_ok=True)
    return analyze_all(**inputs, bootstrap_replicates=bootstrap_replicates)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument(
        "--bootstrap-replicates", type=int, default=BOOTSTRAP_REPLICATES
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    analysis = _load_current_analysis(
        bootstrap_replicates=args.bootstrap_replicates
    )
    paths = write_outputs(analysis, output_root=args.output_root)
    print(json.dumps(paths, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
