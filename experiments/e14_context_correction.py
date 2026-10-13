"""运行校准后的 E14 延迟、吞吐量与计算资源开销修正实验。

测量在不同长上下文规模下防护监视器带来的额外时间与内存开销。
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from m3_eval.figure_manifest import write_figure_manifest
from m3_eval.statistics import holm_adjust, percentile, wilcoxon_signed_rank

from .catalog import CONTEXT_LENGTHS, PERFORMANCE_CONCURRENCY
from .context_correction_runtime import (
    archive_invalid_job_attempt,
    effective_prompt_eval_count,
    execute_matrix_job,
    file_record,
    first_step_rows,
    prompt_token_validity,
    provider_incomplete_is_safely_retained,
    read_jsonl,
    reusable_job_evidence,
    semantic_failure_progress,
    stable_json_hash,
    utc_now,
    verify_freeze,
    write_json,
    write_jsonl,
)
from .context_workloads import (
    DEFAULT_E14_OUT,
    DEFAULT_PROMPT_VERIFICATION_OUT,
    EFFECTIVE_CONTEXT_BY_TARGET,
    MODEL_ALIAS_BY_TARGET,
    PROTOCOL_ID,
    WORKLOAD_REVISION,
    load_prompt_verification,
)
from .manifest import (
    fail_manifest,
    finish_manifest,
    new_manifest,
    record_event,
    register_artifact,
    save_manifest,
    sha256_file,
)
from .model_manager import stop_model


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "outputs" / "experiments" / "E14_context_correction_v2_r3"
DEFAULT_SMOKE_OUTPUT = (
    ROOT / "outputs" / "experiments" / "E14_context_correction_v2_r3_smoke"
)
DEFAULT_FREEZE = ROOT / "protocols" / "context_correction_v2" / "freeze_r3.json"
CONDITIONS = (
    ("e14_v2_off", "normal", "off"),
    ("e14_v2_full_guard", "normal", "full_guard"),
)
WARMUP_CONDITIONS = (
    ("e14_v2_warmup_off", "normal", "off"),
    ("e14_v2_warmup_full_guard", "normal", "full_guard"),
)
SEED = 419
TEMPERATURE = 0.0
MAX_TOKENS = 256
HEADROOM_GATE = 512
TOKEN_TOLERANCE = 0.05


def load_cases(path: str | Path = DEFAULT_E14_OUT) -> list[dict[str, Any]]:
    rows = read_jsonl(path)
    if len(rows) != 40:
        raise ValueError(f"E14 V2 fixture must contain 40 cases, got {len(rows)}")
    if len({str(row.get("case_id")) for row in rows}) != 40:
        raise ValueError("E14 V2 fixture has duplicate case IDs")
    if any(row.get("workload_revision") != WORKLOAD_REVISION for row in rows):
        raise ValueError(f"E14 fixture must use workload revision {WORKLOAD_REVISION}")
    matched = [
        row
        for row in rows
        if (row.get("attack_dimensions") or {}).get("workload_cohort")
        == "matched_benign_latency"
    ]
    if len(matched) != 16 or any(
        bool(row.get("requires_tool"))
        or int(row["attack_dimensions"]["injection_position_pct"]) != 100
        or int(row["attack_dimensions"]["suffix_filler_units"]) != 0
        for row in matched
    ):
        raise ValueError("E14 r2 matched controls must be 16 no-tool end-position cases")
    return rows


def _ids(
    cases: Sequence[Mapping[str, Any]], target: int, cohort: str
) -> list[str]:
    return sorted(
        str(row["case_id"])
        for row in cases
        if int(row["attack_dimensions"]["target_prompt_tokens"]) == target
        and row["attack_dimensions"]["workload_cohort"] == cohort
    )


def _job(
    *,
    job_id: str,
    job_type: str,
    target: int,
    cohort: str,
    concurrency: int,
    outer_replicate_id: int,
    condition: tuple[str, str, str],
    case_ids: Sequence[str],
) -> dict[str, Any]:
    condition_id, prompt_profile, guard_mode = condition
    return {
        "id": job_id,
        "protocol_id": PROTOCOL_ID,
        "workload_revision": WORKLOAD_REVISION,
        "job_type": job_type,
        "base_model": "qwen3:4b-instruct",
        "served_model": MODEL_ALIAS_BY_TARGET[target],
        "target_prompt_tokens": target,
        "effective_context_window_tokens": EFFECTIVE_CONTEXT_BY_TARGET[target],
        "workload_cohort": cohort,
        "concurrency": concurrency,
        "outer_replicate_id": outer_replicate_id,
        "condition_id": condition_id,
        "prompt_profile": prompt_profile,
        "guard_mode": guard_mode,
        "case_ids": list(case_ids),
        "expected_case_runs": len(case_ids),
        "run_group": f"{PROTOCOL_ID}_E14",
        "notes": (
            "E14 V2 warmup excluded from formal metrics"
            if job_type == "warmup"
            else f"E14 V2 formal {cohort}"
        ),
    }


def build_plan(
    cases: Sequence[Mapping[str, Any]], *, phase: str = "formal"
) -> dict[str, Any]:
    if phase not in {"smoke", "formal"}:
        raise ValueError("phase must be smoke or formal")
    jobs: list[dict[str, Any]] = []
    if phase == "smoke":
        for target in CONTEXT_LENGTHS:
            case_ids = _ids(cases, target, "matched_benign_latency") + _ids(
                cases, target, "mixed_throughput"
            )[:2]
            if len(case_ids) != 6:
                raise ValueError("E14 smoke requires four matched benign plus two mixed cases")
            for condition in CONDITIONS:
                jobs.append(
                    _job(
                        job_id=f"smoke__ctx{target}__{condition[0]}",
                        job_type="smoke",
                        target=target,
                        cohort="smoke_combined",
                        concurrency=1,
                        outer_replicate_id=0,
                        condition=condition,
                        case_ids=case_ids,
                    )
                )
        return {
            "schema_version": "2.0",
            "protocol_id": PROTOCOL_ID,
            "workload_revision": WORKLOAD_REVISION,
            "experiment_id": "E14",
            "phase": "smoke",
            "expected_warmup_case_runs": 0,
            "expected_formal_case_runs": 48,
            "jobs": jobs,
        }

    for target in CONTEXT_LENGTHS:
        mixed_ids = _ids(cases, target, "mixed_throughput")
        benign_ids = _ids(cases, target, "matched_benign_latency")
        if len(mixed_ids) != 6 or len(benign_ids) != 4:
            raise ValueError(f"E14 target={target} cohort size mismatch")
        for condition in WARMUP_CONDITIONS:
            jobs.append(
                _job(
                    job_id=f"warmup__ctx{target}__{condition[0]}",
                    job_type="warmup",
                    target=target,
                    cohort="mixed_throughput",
                    concurrency=1,
                    outer_replicate_id=0,
                    condition=condition,
                    case_ids=mixed_ids,
                )
            )
        for concurrency in PERFORMANCE_CONCURRENCY:
            for outer in range(3):
                order = CONDITIONS if (target + concurrency + outer) % 2 else tuple(reversed(CONDITIONS))
                for condition in order:
                    jobs.append(
                        _job(
                            job_id=(
                                f"matched__ctx{target}__c{concurrency}__r{outer}__{condition[0]}"
                            ),
                            job_type="formal",
                            target=target,
                            cohort="matched_benign_latency",
                            concurrency=concurrency,
                            outer_replicate_id=outer,
                            condition=condition,
                            case_ids=benign_ids,
                        )
                    )
            order = CONDITIONS if (target + concurrency) % 2 else tuple(reversed(CONDITIONS))
            for condition in order:
                jobs.append(
                    _job(
                        job_id=f"mixed__ctx{target}__c{concurrency}__{condition[0]}",
                        job_type="formal",
                        target=target,
                        cohort="mixed_throughput",
                        concurrency=concurrency,
                        outer_replicate_id=0,
                        condition=condition,
                        case_ids=mixed_ids,
                    )
                )
    warmup = sum(job["expected_case_runs"] for job in jobs if job["job_type"] == "warmup")
    matched = sum(
        job["expected_case_runs"]
        for job in jobs
        if job["job_type"] == "formal"
        and job["workload_cohort"] == "matched_benign_latency"
    )
    mixed = sum(
        job["expected_case_runs"]
        for job in jobs
        if job["job_type"] == "formal"
        and job["workload_cohort"] == "mixed_throughput"
    )
    if (warmup, matched, mixed) != (48, 288, 144):
        raise AssertionError(f"E14 V2 denominator mismatch: {(warmup, matched, mixed)}")
    return {
        "schema_version": "2.0",
        "protocol_id": PROTOCOL_ID,
        "workload_revision": WORKLOAD_REVISION,
        "experiment_id": "E14",
        "phase": "formal",
        "transport": "ollama_native",
        "dynamic_num_ctx": None,
        "seed_base": SEED,
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
        "expected_warmup_case_runs": warmup,
        "expected_matched_benign_case_runs": matched,
        "expected_mixed_throughput_case_runs": mixed,
        "expected_formal_case_runs": matched + mixed,
        "warmup_job_count": sum(job["job_type"] == "warmup" for job in jobs),
        "formal_job_count": sum(job["job_type"] == "formal" for job in jobs),
        "jobs": jobs,
    }


def _case_logs(rows: Sequence[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("run_key"))].append(dict(row))
    for value in grouped.values():
        value.sort(key=lambda row: int(row.get("step") or 0))
    return grouped


def _matched_path_check(
    rows: Sequence[Mapping[str, Any]],
    plan: Mapping[str, Any],
    cases: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    job_by_id = {str(job["id"]): job for job in plan["jobs"]}
    phase = str(plan.get("phase"))
    eligible_ids = {
        str(case["case_id"])
        for case in (cases or ())
        if bool(case.get("latency_overhead_eligible"))
    }
    if phase == "smoke" and not eligible_ids:
        eligible_ids = {
            str(row.get("case_id"))
            for row in rows
            if "matched_benign_latency" in str(row.get("case_id"))
        }
    matched_rows = [
        row
        for row in rows
        if (
            phase == "formal"
            and job_by_id[str(row.get("correction_job_id"))]["job_type"] == "formal"
            and row.get("workload_cohort") == "matched_benign_latency"
        )
        or (
            phase == "smoke"
            and job_by_id[str(row.get("correction_job_id"))]["job_type"] == "smoke"
            and str(row.get("case_id")) in eligible_ids
        )
    ]
    runs = _case_logs(matched_rows)
    pairs: dict[tuple[str, int, int, int], dict[str, list[dict[str, Any]]]] = defaultdict(dict)
    for logs in runs.values():
        first = logs[0]
        key = (
            str(first["case_id"]),
            int(first["target_prompt_tokens"]),
            int(first["offered_concurrency"]),
            int(first["outer_replicate_id"]),
        )
        pairs[key][str(first["condition_id"])] = logs
    failures: list[dict[str, Any]] = []
    valid_pair_count = 0
    for key, conditions in sorted(pairs.items()):
        reasons: list[str] = []
        if set(conditions) != {"e14_v2_off", "e14_v2_full_guard"}:
            reasons.append("missing_condition")
        else:
            off = conditions["e14_v2_off"]
            full = conditions["e14_v2_full_guard"]
            if len(off) != 1 or len(full) != 1:
                reasons.append("not_single_step")
            elif not (
                off[0].get("parse_ok")
                and full[0].get("parse_ok")
                and (off[0].get("parsed_tool_call") or {}).get("tool") == "final"
                and (full[0].get("parsed_tool_call") or {}).get("tool") == "final"
            ):
                reasons.append("not_parsed_final")
            if off and full and off[0].get("raw_model_output") != full[0].get("raw_model_output"):
                reasons.append("raw_output_mismatch")
            if off and full and off[0].get("parsed_tool_call") != full[0].get("parsed_tool_call"):
                reasons.append("tool_call_mismatch")
            if full and full[0].get("guard_decision") != "allow":
                reasons.append("full_guard_not_allow")
            if off and full and not (
                off[0].get("final_status") == "completed"
                and full[0].get("final_status") == "completed"
            ):
                reasons.append("terminal_path_mismatch")
        if reasons:
            failures.append({"pair": list(key), "reasons": reasons})
        else:
            valid_pair_count += 1
    expected_pairs = 144 if phase == "formal" else 16
    return {
        "status": "pass" if len(pairs) == expected_pairs and not failures else "fail",
        "expected_pairs": expected_pairs,
        "observed_pairs": len(pairs),
        "valid_pairs": valid_pair_count,
        "failure_count": len(failures),
        "failures": failures,
    }


def _telemetry_checks(
    plan: Mapping[str, Any], records: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    job_by_id = {str(job["id"]): job for job in plan["jobs"]}
    context_failures: list[str] = []
    case_run_overlap_failures: list[str] = []
    gpu_failures: list[str] = []
    for record in records:
        job_id = str(record["id"])
        job = job_by_id[job_id]
        telemetry = read_jsonl(record["telemetry_path"])
        alias = str(job["served_model"])
        expected_context = int(job["effective_context_window_tokens"])
        observed_contexts = {
            int(model["context_length"])
            for sample in telemetry
            for model in (sample.get("ollama_ps") or {}).get("models", [])
            if model.get("name") == alias and model.get("context_length") is not None
        }
        if expected_context not in observed_contexts:
            context_failures.append(job_id)
        gpu_available = any(bool((sample.get("gpu") or {}).get("available")) for sample in telemetry)
        if not gpu_available:
            gpu_failures.append(job_id)
        offered = int(job["concurrency"])
        if (
            job["job_type"] == "formal"
            and offered > 1
            and int(
                record.get(
                    "observed_case_run_overlap", record.get("observed_max_inflight", 0)
                )
                or 0
            )
            < offered
        ):
            case_run_overlap_failures.append(job_id)
    return {
        "status": "pass"
        if not context_failures and not case_run_overlap_failures and not gpu_failures
        else "fail",
        "alias_context_failures": context_failures,
        "case_run_overlap_failures": case_run_overlap_failures,
        "client_overlap_failures": case_run_overlap_failures,
        "gpu_telemetry_failures": gpu_failures,
    }


def _validate(
    plan: Mapping[str, Any],
    cases: Sequence[Mapping[str, Any]],
    rows: Sequence[Mapping[str, Any]],
    records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    job_by_id = {str(job["id"]): job for job in plan["jobs"]}
    first = first_step_rows(rows)
    formal_all = [
        row
        for row in rows
        if job_by_id[str(row.get("correction_job_id"))]["job_type"]
        in ({"smoke"} if plan["phase"] == "smoke" else {"formal"})
    ]
    formal = [
        row
        for row in first
        if job_by_id[str(row.get("correction_job_id"))]["job_type"]
        in ({"smoke"} if plan["phase"] == "smoke" else {"formal"})
    ]
    warmup = [
        row
        for row in first
        if job_by_id[str(row.get("correction_job_id"))]["job_type"] == "warmup"
    ]
    expected_formal = int(plan["expected_formal_case_runs"])
    expected_warmup = int(plan.get("expected_warmup_case_runs", 0))
    run_keys = [str(row.get("run_key", "")) for row in first]
    checks: dict[str, bool] = {
        "exact_formal_case_runs": len(formal) == expected_formal,
        "exact_warmup_case_runs": len(warmup) == expected_warmup,
        "no_duplicate_run_key": len(run_keys) == len(set(run_keys)) and all(run_keys),
        "all_jobs_completed": len(records) == len(plan["jobs"])
        and all(record.get("status") == "completed" for record in records),
        "native_usage_every_step": all(
            (
                row.get("usage_source") == "ollama_native_prompt_eval_count"
                and row.get("prompt_eval_count") is not None
            )
            or row.get("provider_done") is False
            for row in rows
        ),
        "first_step_workload_proof_complete": all(
            effective_prompt_eval_count(row) is not None for row in first
        ),
        "provider_incomplete_safely_retained": all(
            provider_incomplete_is_safely_retained(row) for row in rows
        ),
        "dynamic_num_ctx_absent": all(
            (row.get("model_config") or {}).get("num_ctx") in {None, ""}
            for row in rows
        ),
        "no_timeout_or_runtime_error": all(
            not bool(row.get("timed_out"))
            and (
                str(row.get("final_status")) != "error"
                or row.get("provider_done") is False
            )
            for row in rows
        ),
    }
    per_target: list[dict[str, Any]] = []
    for target in CONTEXT_LENGTHS:
        target_rows = [row for row in first if int(row.get("target_prompt_tokens")) == target]
        item = prompt_token_validity(target_rows, target=target, tolerance=TOKEN_TOLERANCE)
        item["served_alias_match"] = all(
            row.get("model") == MODEL_ALIAS_BY_TARGET[target]
            and row.get("served_model") == MODEL_ALIAS_BY_TARGET[target]
            for row in target_rows
        )
        item["headroom_pass"] = all(
            effective_prompt_eval_count(row) is not None
            and EFFECTIVE_CONTEXT_BY_TARGET[target]
            - int(effective_prompt_eval_count(row) or 0)
            >= HEADROOM_GATE
            for row in target_rows
        ) and len(target_rows) == int(item["expected_rows"])
        per_target.append(item)
    checks["every_run_within_target_tolerance"] = all(
        item["all_within_tolerance"] for item in per_target
    )
    checks["served_alias_matches"] = all(item["served_alias_match"] for item in per_target)
    checks["minimum_output_headroom"] = all(item["headroom_pass"] for item in per_target)
    target_medians: list[float | None] = []
    for target in CONTEXT_LENGTHS:
        values = [
            int(effective_prompt_eval_count(row) or 0)
            for row in first
            if int(row["target_prompt_tokens"]) == target
            and effective_prompt_eval_count(row) is not None
        ]
        target_medians.append(statistics.median(values) if values else None)
    checks["strict_monotonic_no_collapse"] = all(
        left is not None and right is not None and left < right
        for left, right in zip(target_medians, target_medians[1:])
    )
    telemetry = _telemetry_checks(plan, records)
    checks["resident_alias_context_and_telemetry"] = telemetry["status"] == "pass"
    matched = _matched_path_check(rows, plan, cases)
    checks["matched_benign_paths_identical"] = matched["status"] == "pass"
    if plan["phase"] == "formal":
        checks["formal_cohort_denominators"] = (
            sum(
                1
                for row in formal
                if row.get("workload_cohort") == "matched_benign_latency"
            )
            == 288
            and sum(
                1
                for row in formal
                if row.get("workload_cohort") == "mixed_throughput"
            )
            == 144
        )
    formal_run_rows: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in formal_all:
        formal_run_rows[str(row.get("run_key", ""))].append(row)
    incomplete_run_count = sum(
        any(step.get("provider_done") is False for step in steps)
        for steps in formal_run_rows.values()
    )
    return {
        "schema_version": "2.0",
        "protocol_id": PROTOCOL_ID,
        "experiment_id": "E14",
        "phase": plan["phase"],
        "status": "pass" if all(checks.values()) else "fail",
        "expected_formal_case_runs": expected_formal,
        "observed_formal_case_runs": len(formal),
        "expected_warmup_case_runs": expected_warmup,
        "observed_warmup_case_runs": len(warmup),
        "checks": checks,
        "per_target": per_target,
        "target_prompt_token_medians": dict(zip(map(str, CONTEXT_LENGTHS), target_medians)),
        "matched_path": matched,
        "telemetry": telemetry,
        "parse_failure_count": sum(not bool(row.get("parse_ok")) for row in formal),
        "provider_incomplete_case_runs": incomplete_run_count,
        "provider_incomplete_first_step_case_runs": sum(
            row.get("provider_done") is False for row in formal
        ),
        "provider_incomplete_later_step_case_runs": sum(
            any(
                int(step.get("step") or 0) > 1
                and step.get("provider_done") is False
                for step in steps
            )
            for steps in formal_run_rows.values()
        ),
        "formal_provider_counter_missing_case_runs": sum(
            row.get("prompt_eval_count") is None for row in formal
        ),
        "preflight_fallback_case_runs": sum(
            row.get("prompt_count_evidence") == "frozen_one_token_preflight"
            for row in formal
        ),
        "output_length_finish_count": sum(
            str(row.get("finish_reason")) == "length" for row in rows
        ),
    }


PERFORMANCE_FIELDS = (
    "job_id",
    "job_type",
    "workload_cohort",
    "target_prompt_tokens",
    "effective_context_window_tokens",
    "served_model",
    "concurrency",
    "outer_replicate_id",
    "condition_id",
    "condition",
    "num_ctx",
    "expected_case_runs",
    "observed_case_runs",
    "missing_case_runs",
    "successful_case_runs",
    "error_case_runs",
    "timeout_case_runs",
    "provider_incomplete_case_runs",
    "prompt_tokens_median",
    "total_latency_median_ms",
    "total_latency_p95_ms",
    "guard_latency_p95_ms",
    "wall_seconds",
    "attempted_case_runs_per_s",
    "successful_case_runs_per_s",
    "completed_steps_per_s",
    "prompt_tokens_per_s",
    "verified_first_turn_prompt_tokens_per_s",
    "completion_tokens_per_s",
    "raw_prompt_usage_rows",
    "raw_prompt_usage_expected_rows",
    "raw_completion_usage_rows",
    "raw_completion_usage_expected_rows",
    "throughput_case_runs_per_s",
    "gpu_peak_memory_mib",
    "gpu_memory_delta_mib",
    "observed_max_inflight",
    "observed_case_run_overlap",
    "observed_lane_process_overlap",
    "orchestration_wall_seconds",
)


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _performance_rows(
    plan: Mapping[str, Any], rows: Sequence[Mapping[str, Any]], records: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    by_job: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        by_job[str(row.get("correction_job_id"))].append(row)
    result: list[dict[str, Any]] = []
    for record in records:
        job_rows = by_job[str(record["id"])]
        runs = _case_logs(job_rows)
        first = [logs[0] for logs in runs.values()]
        last = [logs[-1] for logs in runs.values()]
        successful = sum(
            str(row.get("final_status")) in {"completed", "blocked", "needs_confirmation", "max_steps_reached"}
            and str(row.get("final_status")) != "error"
            and not bool(row.get("timed_out"))
            for row in last
        )
        latencies = [
            float(logs[-1]["case_latency_ms"])
            for logs in runs.values()
            if _finite(logs[-1].get("case_latency_ms")) is not None
        ]
        guard_values = [
            float(row["guard_latency_ms"])
            for row in job_rows
            if _finite(row.get("guard_latency_ms")) is not None
        ]
        wall = float(record["wall_seconds"])
        telemetry = read_jsonl(record["telemetry_path"])
        gpu_values = [
            float((sample.get("gpu") or {})["memory_used_mib"])
            for sample in telemetry
            if _finite((sample.get("gpu") or {}).get("memory_used_mib")) is not None
        ]
        gpu_before = gpu_values[0] if gpu_values else None
        gpu_peak = max(gpu_values) if gpu_values else None
        prompt_counts = [
            (
                effective_prompt_eval_count(row)
                if int(row.get("step") or 0) == 1
                else int(row["prompt_eval_count"])
                if row.get("prompt_eval_count") is not None
                else None
            )
            for row in job_rows
        ]
        raw_prompt_values = [
            int(row["prompt_eval_count"])
            for row in job_rows
            if row.get("prompt_eval_count") is not None
        ]
        raw_completion_values = [
            int(row["eval_count"])
            for row in job_rows
            if row.get("eval_count") is not None
        ]
        prompt_total = (
            sum(int(value) for value in prompt_counts if value is not None)
            if all(value is not None for value in prompt_counts)
            else None
        )
        completion_total = (
            sum(raw_completion_values)
            if len(raw_completion_values) == len(job_rows)
            else None
        )
        first_prompt_values = [effective_prompt_eval_count(row) for row in first]
        verified_first_total = (
            sum(int(value) for value in first_prompt_values if value is not None)
            if all(value is not None for value in first_prompt_values)
            else None
        )
        incomplete_runs = sum(
            any(step.get("provider_done") is False for step in logs)
            for logs in runs.values()
        )
        result.append(
            {
                "job_id": record["id"],
                "job_type": record["job_type"],
                "workload_cohort": record["workload_cohort"],
                "target_prompt_tokens": record["target_prompt_tokens"],
                "effective_context_window_tokens": record["effective_context_window_tokens"],
                "served_model": record["served_model"],
                "concurrency": record["concurrency"],
                "outer_replicate_id": record["outer_replicate_id"],
                "condition_id": record["condition_id"],
                "condition": record["condition_id"],
                "num_ctx": record["target_prompt_tokens"],
                "expected_case_runs": record["expected_case_runs"],
                "observed_case_runs": len(runs),
                "missing_case_runs": max(0, int(record["expected_case_runs"]) - len(runs)),
                "successful_case_runs": successful,
                "error_case_runs": sum(str(row.get("final_status")) == "error" for row in last),
                "timeout_case_runs": sum(bool(row.get("timed_out")) for row in last),
                "provider_incomplete_case_runs": incomplete_runs,
                "prompt_tokens_median": (
                    statistics.median(
                        int(value) for value in first_prompt_values if value is not None
                    )
                    if first_prompt_values
                    and all(value is not None for value in first_prompt_values)
                    else None
                ),
                "total_latency_median_ms": statistics.median(latencies) if latencies else None,
                "total_latency_p95_ms": percentile(latencies, 0.95),
                "guard_latency_p95_ms": percentile(guard_values, 0.95),
                "wall_seconds": wall,
                "attempted_case_runs_per_s": len(runs) / wall if wall else None,
                "successful_case_runs_per_s": successful / wall if wall else None,
                "completed_steps_per_s": len(job_rows) / wall if wall else None,
                "prompt_tokens_per_s": (
                    prompt_total / wall if wall and prompt_total is not None else None
                ),
                "verified_first_turn_prompt_tokens_per_s": (
                    verified_first_total / wall
                    if wall and verified_first_total is not None
                    else None
                ),
                "completion_tokens_per_s": (
                    completion_total / wall
                    if wall and completion_total is not None
                    else None
                ),
                "raw_prompt_usage_rows": len(raw_prompt_values),
                "raw_prompt_usage_expected_rows": len(job_rows),
                "raw_completion_usage_rows": len(raw_completion_values),
                "raw_completion_usage_expected_rows": len(job_rows),
                "throughput_case_runs_per_s": successful / wall if wall else None,
                "gpu_peak_memory_mib": gpu_peak,
                "gpu_memory_delta_mib": gpu_peak - gpu_before if gpu_peak is not None and gpu_before is not None else None,
                "observed_max_inflight": record["observed_max_inflight"],
                "observed_case_run_overlap": record.get("observed_case_run_overlap"),
                "observed_lane_process_overlap": record.get("observed_lane_process_overlap"),
                "orchestration_wall_seconds": record.get("orchestration_wall_seconds"),
            }
        )
    return result


def _aggregate_chart_rows(
    performance: Sequence[Mapping[str, Any]],
    rows: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    latency: list[dict[str, Any]] = []
    throughput: list[dict[str, Any]] = []
    gpu: list[dict[str, Any]] = []
    for target in CONTEXT_LENGTHS:
        for concurrency in PERFORMANCE_CONCURRENCY:
            for condition_id, _, _ in CONDITIONS:
                matched_jobs = [
                    row for row in performance
                    if row["job_type"] == "formal"
                    and row["workload_cohort"] == "matched_benign_latency"
                    and int(row["target_prompt_tokens"]) == target
                    and int(row["concurrency"]) == concurrency
                    and row["condition_id"] == condition_id
                ]
                matched_steps = [
                    row
                    for row in rows
                    if row.get("correction_job_type") == "formal"
                    and row.get("workload_cohort") == "matched_benign_latency"
                    and int(row.get("target_prompt_tokens")) == target
                    and int(row.get("offered_concurrency")) == concurrency
                    and row.get("condition_id") == condition_id
                ]
                matched_runs = _case_logs(matched_steps)
                case_latencies = [
                    float(logs[-1]["case_latency_ms"])
                    for logs in matched_runs.values()
                    if _finite(logs[-1].get("case_latency_ms")) is not None
                ]
                guard_latencies = [
                    float(row["guard_latency_ms"])
                    for row in matched_steps
                    if _finite(row.get("guard_latency_ms")) is not None
                ]
                latency.append(
                    {
                        "target_prompt_tokens": target,
                        "concurrency": concurrency,
                        "condition_id": condition_id,
                        "outer_job_count": len(matched_jobs),
                        "case_run_count": len(matched_runs),
                        "median_total_latency_ms": (
                            statistics.median(case_latencies) if case_latencies else None
                        ),
                        "p95_total_latency_ms": percentile(case_latencies, 0.95),
                        "guard_latency_p95_ms": percentile(guard_latencies, 0.95),
                    }
                )
                mixed = [
                    row for row in performance
                    if row["job_type"] == "formal"
                    and row["workload_cohort"] == "mixed_throughput"
                    and int(row["target_prompt_tokens"]) == target
                    and int(row["concurrency"]) == concurrency
                    and row["condition_id"] == condition_id
                ]
                item = mixed[0] if mixed else {}
                throughput.append(
                    {
                        "target_prompt_tokens": target,
                        "concurrency": concurrency,
                        "condition_id": condition_id,
                        "attempted_case_runs_per_s": item.get("attempted_case_runs_per_s"),
                        "successful_case_runs_per_s": item.get("successful_case_runs_per_s"),
                        "completed_steps_per_s": item.get("completed_steps_per_s"),
                        "prompt_tokens_per_s": item.get("prompt_tokens_per_s"),
                        "completion_tokens_per_s": item.get("completion_tokens_per_s"),
                    }
                )
                relevant = [*matched_jobs, *mixed]
                gpu.append(
                    {
                        "target_prompt_tokens": target,
                        "concurrency": concurrency,
                        "condition_id": condition_id,
                        "gpu_peak_memory_mib": max(
                            (float(row["gpu_peak_memory_mib"]) for row in relevant if row.get("gpu_peak_memory_mib") is not None),
                            default=None,
                        ),
                        "gpu_memory_delta_mib": max(
                            (float(row["gpu_memory_delta_mib"]) for row in relevant if row.get("gpu_memory_delta_mib") is not None),
                            default=None,
                        ),
                    }
                )
    return latency, throughput, gpu


def _bootstrap_median_ci(
    values: Sequence[float], *, iterations: int = 10_000, seed: int = 42
) -> dict[str, Any]:
    if not values:
        return {"median": None, "ci_low": None, "ci_high": None, "iterations": iterations}
    rng = random.Random(seed)
    samples = [
        statistics.median(rng.choice(values) for _ in range(len(values)))
        for _ in range(iterations)
    ]
    return {
        "median": statistics.median(values),
        "ci_low": percentile(samples, 0.025),
        "ci_high": percentile(samples, 0.975),
        "iterations": iterations,
    }


def _latency_map(rows: Sequence[Mapping[str, Any]]) -> dict[tuple[str, int, int, int], float]:
    result: dict[tuple[str, int, int, int], float] = {}
    for logs in _case_logs(rows).values():
        first = logs[0]
        key = (
            str(first["case_id"]),
            int(first["target_prompt_tokens"]),
            int(first["offered_concurrency"]),
            int(first["outer_replicate_id"]),
        )
        value = _finite(logs[-1].get("case_latency_ms"))
        if value is None or key in result:
            raise ValueError(f"missing or duplicate matched latency key: {key}")
        result[key] = value
    return result


def _paired_latency_summary(
    base: Sequence[Mapping[str, Any]],
    guard: Sequence[Mapping[str, Any]],
    *,
    seed: int = 42,
) -> dict[str, Any]:
    base_map = _latency_map(base)
    guard_map = _latency_map(guard)
    if set(base_map) != set(guard_map):
        return {
            "status": "unpaired",
            "paired_case_runs": 0,
            "baseline_only": [list(key) for key in sorted(set(base_map) - set(guard_map))],
            "guard_only": [list(key) for key in sorted(set(guard_map) - set(base_map))],
        }
    keys = sorted(base_map)
    baseline = [base_map[key] for key in keys]
    guarded = [guard_map[key] for key in keys]
    deltas = [right - left for left, right in zip(baseline, guarded)]
    percentages = [
        100.0 * (right - left) / left
        for left, right in zip(baseline, guarded)
        if left > 0.0
    ]
    return {
        "status": "paired",
        "paired_case_runs": len(keys),
        "baseline_median_ms": statistics.median(baseline) if baseline else None,
        "full_guard_median_ms": statistics.median(guarded) if guarded else None,
        "ratio_of_medians_overhead_percent": (
            100.0 * (statistics.median(guarded) - statistics.median(baseline))
            / statistics.median(baseline)
            if baseline and statistics.median(baseline) > 0.0
            else None
        ),
        "paired_delta_ms": _bootstrap_median_ci(deltas, seed=seed),
        "paired_overhead_percent": _bootstrap_median_ci(percentages, seed=seed + 1),
        "total_latency_wilcoxon": (
            wilcoxon_signed_rank(baseline, guarded)
            if baseline
            else {
                "method": "wilcoxon_signed_rank",
                "pairs": 0,
                "p_value": None,
                "rank_biserial": None,
            }
        ),
    }


def _statistics_payload(
    cases: Sequence[Mapping[str, Any]],
    rows: Sequence[Mapping[str, Any]],
    performance: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    comparisons: list[dict[str, Any]] = []
    tests: list[tuple[int, str, float]] = []
    for target in CONTEXT_LENGTHS:
        case_subset = [
            case for case in cases
            if int(case["attack_dimensions"]["target_prompt_tokens"]) == target
            and case["attack_dimensions"]["workload_cohort"] == "matched_benign_latency"
        ]
        ids = {str(case["case_id"]) for case in case_subset}
        for concurrency in PERFORMANCE_CONCURRENCY:
            base = [
                dict(row) for row in rows
                if row.get("correction_job_type") == "formal"
                and row.get("workload_cohort") == "matched_benign_latency"
                and str(row.get("case_id")) in ids
                and int(row.get("offered_concurrency")) == concurrency
                and row.get("condition_id") == "e14_v2_off"
            ]
            guard = [
                dict(row) for row in rows
                if row.get("correction_job_type") == "formal"
                and row.get("workload_cohort") == "matched_benign_latency"
                and str(row.get("case_id")) in ids
                and int(row.get("offered_concurrency")) == concurrency
                and row.get("condition_id") == "e14_v2_full_guard"
            ]
            comparison = _paired_latency_summary(base, guard, seed=42 + target + concurrency)
            guard_values = [
                float(row["guard_latency_ms"])
                for row in guard
                if _finite(row.get("guard_latency_ms")) is not None
            ]
            item = {
                "comparison_id": f"ctx{target}_c{concurrency}",
                "target_prompt_tokens": target,
                "concurrency": concurrency,
                **comparison,
                "guard_latency_p95_ms": percentile(guard_values, 0.95),
            }
            index = len(comparisons)
            comparisons.append(item)
            test = item.get("total_latency_wilcoxon") or {}
            if test.get("p_value") is not None:
                tests.append((index, "total_latency_wilcoxon", float(test["p_value"])))
    adjusted = holm_adjust([value for _, _, value in tests]) if tests else []
    for (index, name, _), value in zip(tests, adjusted):
        comparisons[index][name]["holm_adjusted_p"] = value
    all_base = [
        dict(row)
        for row in rows
        if row.get("correction_job_type") == "formal"
        and row.get("workload_cohort") == "matched_benign_latency"
        and row.get("condition_id") == "e14_v2_off"
    ]
    all_guard = [
        dict(row)
        for row in rows
        if row.get("correction_job_type") == "formal"
        and row.get("workload_cohort") == "matched_benign_latency"
        and row.get("condition_id") == "e14_v2_full_guard"
    ]
    overall = _paired_latency_summary(all_base, all_guard, seed=419)
    all_guard_latencies = [
        float(row["guard_latency_ms"])
        for row in all_guard
        if _finite(row.get("guard_latency_ms")) is not None
    ]
    overall_guard_p95 = percentile(all_guard_latencies, 0.95)
    throughput: list[dict[str, Any]] = []
    for target in CONTEXT_LENGTHS:
        for concurrency in PERFORMANCE_CONCURRENCY:
            cell = {
                str(row["condition_id"]): row
                for row in performance
                if row["job_type"] == "formal"
                and row["workload_cohort"] == "mixed_throughput"
                and int(row["target_prompt_tokens"]) == target
                and int(row["concurrency"]) == concurrency
            }
            base_rate = (cell.get("e14_v2_off") or {}).get("successful_case_runs_per_s")
            guard_rate = (cell.get("e14_v2_full_guard") or {}).get(
                "successful_case_runs_per_s"
            )
            throughput.append(
                {
                    "target_prompt_tokens": target,
                    "concurrency": concurrency,
                    "baseline_successful_case_runs_per_s": base_rate,
                    "full_guard_successful_case_runs_per_s": guard_rate,
                    "relative_change_percent": (
                        100.0 * (float(guard_rate) - float(base_rate)) / float(base_rate)
                        if base_rate not in {None, 0, 0.0} and guard_rate is not None
                        else None
                    ),
                }
            )
    overhead = overall.get("paired_overhead_percent") or {}
    target_checks = {
        "guard_p95_below_10ms": (
            overall_guard_p95 is not None and overall_guard_p95 < 10.0
        ),
        "median_end_to_end_overhead_below_10pct": (
            overhead.get("median") is not None and float(overhead["median"]) < 10.0
        ),
    }
    return {
        "schema_version": "2.0",
        "experiment_id": "E14",
        "protocol_id": PROTOCOL_ID,
        "workload_revision": WORKLOAD_REVISION,
        "evidence_tier": "formal_context_correction_v2",
        "formal_model_only": True,
        "status": "completed",
        "estimands": {
            "guard_overhead": "matched benign identical-path pairs only",
            "system_throughput": "mixed workload by strategy; not pure Guard overhead",
        },
        "latency_method": "raw matched case-runs: median/p95, paired Wilcoxon, rank-biserial, and 10000 paired bootstrap medians",
        "multiplicity": "Holm correction across target/concurrency latency tests",
        "comparisons": comparisons,
        "overall_matched_latency": overall,
        "guard_latency_p95_ms": overall_guard_p95,
        "total_latency_overhead_percent": overhead,
        "mixed_throughput_comparisons": throughput,
        "target_checks": target_checks,
    }


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _render_charts(
    output: Path,
    latency: Sequence[Mapping[str, Any]],
    throughput: Sequence[Mapping[str, Any]],
    gpu: Sequence[Mapping[str, Any]],
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    styles = {
        "e14_v2_off": ("--", "s", "No Guard"),
        "e14_v2_full_guard": ("-", "o", "Full Guard"),
    }
    colors = {1: "#4C78A8", 2: "#F58518", 4: "#54A24B"}
    fig, axis = plt.subplots(figsize=(9.2, 5.4))
    for concurrency in PERFORMANCE_CONCURRENCY:
        for condition, (line, marker, label) in styles.items():
            values = sorted(
                (row for row in latency if row["concurrency"] == concurrency and row["condition_id"] == condition),
                key=lambda row: row["target_prompt_tokens"],
            )
            axis.plot(
                [row["target_prompt_tokens"] for row in values],
                [row["median_total_latency_ms"] for row in values],
                linestyle=line,
                marker=marker,
                color=colors[concurrency],
                label=f"c={concurrency} {label}",
            )
    axis.set_xscale("log", base=2)
    axis.set_xticks(CONTEXT_LENGTHS, [f"{value // 1024}K" for value in CONTEXT_LENGTHS])
    axis.set_xlabel("Calibrated first-step prompt tokens")
    axis.set_ylabel("Matched benign end-to-end median latency (ms)")
    axis.set_title("E14 V2 matched-path latency")
    axis.grid(alpha=0.25)
    axis.legend(ncol=2, fontsize=8, facecolor="white")
    fig.tight_layout()
    fig.savefig(output / "latency_by_context.png", dpi=180)
    fig.savefig(output / "latency_by_context.svg")
    plt.close(fig)

    fig, axis = plt.subplots(figsize=(9.2, 5.4))
    target_colors = {2048: "#4C78A8", 4096: "#F58518", 8192: "#54A24B", 16384: "#E45756"}
    for target in CONTEXT_LENGTHS:
        for condition, (line, marker, label) in styles.items():
            values = sorted(
                (row for row in throughput if row["target_prompt_tokens"] == target and row["condition_id"] == condition),
                key=lambda row: row["concurrency"],
            )
            axis.plot(
                [row["concurrency"] for row in values],
                [row["successful_case_runs_per_s"] for row in values],
                linestyle=line,
                marker=marker,
                color=target_colors[target],
                label=f"{target // 1024}K {label}",
            )
    axis.set_xticks(PERFORMANCE_CONCURRENCY)
    axis.set_xlabel("Offered client concurrency")
    axis.set_ylabel("Successful mixed case-runs/s")
    axis.set_title("E14 V2 mixed-workload system throughput")
    axis.grid(alpha=0.25)
    axis.legend(ncol=2, fontsize=8, facecolor="white")
    fig.tight_layout()
    fig.savefig(output / "throughput_by_concurrency.png", dpi=180)
    fig.savefig(output / "throughput_by_concurrency.svg")
    plt.close(fig)

    matrix = np.full((len(PERFORMANCE_CONCURRENCY) * 2, len(CONTEXT_LENGTHS)), np.nan)
    labels: list[str] = []
    for row_index, (concurrency, condition) in enumerate(
        (c, cond) for c in PERFORMANCE_CONCURRENCY for cond in styles
    ):
        labels.append(f"c={concurrency} {styles[condition][2]}")
        for column, target in enumerate(CONTEXT_LENGTHS):
            item = next(
                row for row in gpu
                if row["concurrency"] == concurrency
                and row["condition_id"] == condition
                and row["target_prompt_tokens"] == target
            )
            if item["gpu_peak_memory_mib"] is not None:
                matrix[row_index, column] = item["gpu_peak_memory_mib"]
    fig, axis = plt.subplots(figsize=(8.5, 5.5))
    image = axis.imshow(matrix, aspect="auto", cmap="Blues")
    axis.set_xticks(range(len(CONTEXT_LENGTHS)), [f"{v // 1024}K" for v in CONTEXT_LENGTHS])
    axis.set_yticks(range(len(labels)), labels)
    for row in range(matrix.shape[0]):
        for column in range(matrix.shape[1]):
            if not np.isnan(matrix[row, column]):
                axis.text(column, row, f"{matrix[row, column]:.0f}", ha="center", va="center", fontsize=8)
    axis.set_xlabel("Calibrated first-step prompt tokens")
    axis.set_title("E14 V2 observed device-wide GPU memory peak (MiB)")
    fig.colorbar(image, ax=axis, label="MiB")
    fig.tight_layout()
    fig.savefig(output / "gpu_memory_by_context.png", dpi=180)
    fig.savefig(output / "gpu_memory_by_context.svg")
    plt.close(fig)


def _analysis_text(
    validity: Mapping[str, Any], statistics_payload: Mapping[str, Any]
) -> str:
    comparisons = statistics_payload["comparisons"]
    overhead_tests = [
        item for item in comparisons if item.get("total_latency_wilcoxon")
    ]
    return "\n".join(
        [
            "# E14 V2 calibrated performance analysis",
            "",
            f"- Semantic validity: **{validity['status']}**.",
            f"- Warmup: {validity['observed_warmup_case_runs']}/{validity['expected_warmup_case_runs']} case-runs (excluded).",
            f"- Formal: {validity['observed_formal_case_runs']}/{validity['expected_formal_case_runs']} case-runs.",
            f"- Matched benign identical paths: {validity['matched_path']['valid_pairs']}/{validity['matched_path']['expected_pairs']} pairs.",
            f"- Latency comparisons with paired tests: {len(overhead_tests)}.",
            f"- Provider-incomplete formal case-runs retained as unsuccessful, non-executable outcomes: {validity['provider_incomplete_case_runs']}.",
            f"- Full Guard own p95 latency: {statistics_payload.get('guard_latency_p95_ms')} ms; target pass={statistics_payload['target_checks']['guard_p95_below_10ms']}.",
            f"- Median paired end-to-end overhead: {(statistics_payload.get('total_latency_overhead_percent') or {}).get('median')}%; target pass={statistics_payload['target_checks']['median_end_to_end_overhead_below_10pct']}.",
            "- Guard overhead conclusions use only identical one-step benign paths; mixed attack/benign runs are system-throughput evidence only.",
            "- Concurrency is client-offered concurrency. Full case-run overlap is checked from durable timestamps, but Ollama/GPU may still serialize internally.",
            "- First-turn workload is bound to frozen one-token native proof; formal raw-provider token coverage is reported separately and missing token usage is never coerced to zero.",
            "- GPU values are device-wide polled observations; they are not Guard-exclusive allocation and may miss transient peaks.",
            "- Old V3 E14 is preserved as invalid context-axis diagnostic evidence and excluded from this denominator.",
            "",
        ]
    )


def _build_outputs(
    output: Path,
    plan: Mapping[str, Any],
    cases: Sequence[Mapping[str, Any]],
    rows: Sequence[Mapping[str, Any]],
    records: Sequence[Mapping[str, Any]],
    validity: Mapping[str, Any],
    cases_path: str | Path = DEFAULT_E14_OUT,
) -> list[tuple[Path, str]]:
    raw_path = output / "raw_runs.jsonl"
    records_path = output / "job_records.jsonl"
    telemetry_path = output / "telemetry.jsonl"
    validity_path = output / "validity_checks.json"
    write_jsonl(raw_path, rows)
    write_jsonl(records_path, records)
    telemetry = [
        {**sample, "job_id": record["id"]}
        for record in records
        for sample in read_jsonl(record["telemetry_path"])
    ]
    write_jsonl(telemetry_path, telemetry)
    write_json(validity_path, validity)
    outputs: list[tuple[Path, str]] = [
        (raw_path, "raw_log"),
        (records_path, "job_log"),
        (telemetry_path, "resource_log"),
        (validity_path, "semantic_validity"),
    ]
    if plan["phase"] != "formal" or validity["status"] != "pass":
        return outputs
    formal_rows = [
        row for row in rows if row.get("correction_job_type") == "formal"
    ]
    formal_raw_path = output / "formal_raw_runs.jsonl"
    write_jsonl(formal_raw_path, formal_rows)
    raw_index_path = output / "raw_run_index.json"
    write_json(
        raw_index_path,
        {
            "schema_version": "2.0",
            "experiment_id": "E14",
            "protocol_id": PROTOCOL_ID,
            "warmup_policy": "retained_in_raw_runs_but_excluded_from_formal_raw_index",
            "old_v3_policy": "excluded_invalid_context_axis_provenance",
            "records": [
                {
                    **file_record(cases_path, kind="case_dataset"),
                    "row_count": len(cases),
                    "distinct_case_count": len({str(case["case_id"]) for case in cases}),
                },
                {
                    **file_record(formal_raw_path, kind="formal_raw_log"),
                    "row_count": len(formal_rows),
                    "distinct_case_count": len(
                        {str(row["case_id"]) for row in formal_rows}
                    ),
                    "logical_case_runs": int(plan["expected_formal_case_runs"]),
                    "evidence_tier": "formal_context_correction_v2",
                },
            ],
        },
    )
    outputs.extend(
        [(formal_raw_path, "formal_raw_log"), (raw_index_path, "raw_run_index")]
    )
    performance = _performance_rows(plan, rows, records)
    latency, throughput, gpu = _aggregate_chart_rows(performance, rows)
    statistics_payload = _statistics_payload(cases, rows, performance)
    performance_path = output / "performance.csv"
    metrics_path = output / "metrics.csv"
    statistics_path = output / "statistics.json"
    analysis_path = output / "analysis.md"
    latency_path = output / "latency_by_context_data.csv"
    throughput_path = output / "throughput_by_concurrency_data.csv"
    gpu_path = output / "gpu_memory_by_context_data.csv"
    _write_csv(performance_path, performance, PERFORMANCE_FIELDS)
    _write_csv(metrics_path, performance, PERFORMANCE_FIELDS)
    _write_csv(latency_path, latency, tuple(latency[0]))
    _write_csv(throughput_path, throughput, tuple(throughput[0]))
    _write_csv(gpu_path, gpu, tuple(gpu[0]))
    write_json(statistics_path, statistics_payload)
    analysis_path.write_text(_analysis_text(validity, statistics_payload), encoding="utf-8")
    _render_charts(output, latency, throughput, gpu)
    figure_manifest = write_figure_manifest(
        output,
        experiment_id="E14",
        evidence_tier="formal_context_correction_v2",
        figures=[
            {
                "id": "latency_by_context",
                "title": "E14 V2 matched-path latency",
                "role": "primary",
                "order": 0,
                "chart_type": "multi_series_line",
                "caption": "Matched benign identical-path median latency by calibrated prompt target, offered concurrency and condition.",
                "files": {"data": latency_path.name, "png": "latency_by_context.png", "svg": "latency_by_context.svg"},
                "metrics": ["median_total_latency_ms", "p95_total_latency_ms"],
                "grain": ["target_prompt_tokens", "concurrency", "condition_id"],
                "uncertainty": [{"method": "paired Wilcoxon in statistics.json; p95 is descriptive"}],
                "warnings": ["Only identical one-step benign paths enter Guard overhead."],
            },
            {
                "id": "throughput_by_concurrency",
                "title": "E14 V2 mixed-workload system throughput",
                "role": "secondary",
                "order": 1,
                "chart_type": "multi_series_line",
                "caption": "Successful mixed case-runs per wall-clock second by calibrated prompt target and offered client concurrency.",
                "files": {"data": throughput_path.name, "png": "throughput_by_concurrency.png", "svg": "throughput_by_concurrency.svg"},
                "metrics": ["successful_case_runs_per_s"],
                "grain": ["target_prompt_tokens", "concurrency", "condition_id"],
                "uncertainty": [{"method": "none", "reason": "one wall-clock mixed job per cell"}],
                "warnings": ["System throughput by strategy is not pure Guard overhead."],
            },
            {
                "id": "gpu_memory_by_context",
                "title": "E14 V2 observed GPU memory peak",
                "role": "secondary",
                "order": 2,
                "chart_type": "annotated_heatmap",
                "caption": "Device-wide polled GPU memory peak by target, offered concurrency and condition.",
                "files": {"data": gpu_path.name, "png": "gpu_memory_by_context.png", "svg": "gpu_memory_by_context.svg"},
                "metrics": ["gpu_peak_memory_mib", "gpu_memory_delta_mib"],
                "grain": ["target_prompt_tokens", "concurrency", "condition_id"],
                "uncertainty": [{"method": "none", "reason": "polled device-wide telemetry"}],
                "warnings": ["Polling may miss transient peaks and is not Guard-exclusive."],
            },
        ],
    )
    outputs.extend(
        [
            (performance_path, "metrics"),
            (metrics_path, "metrics"),
            (statistics_path, "statistics"),
            (analysis_path, "analysis"),
            (latency_path, "figure_data"),
            (throughput_path, "figure_data"),
            (gpu_path, "figure_data"),
            (output / "latency_by_context.png", "figure"),
            (output / "latency_by_context.svg", "figure"),
            (output / "throughput_by_concurrency.png", "figure"),
            (output / "throughput_by_concurrency.svg", "figure"),
            (output / "gpu_memory_by_context.png", "figure"),
            (output / "gpu_memory_by_context.svg", "figure"),
            (figure_manifest, "figure_manifest"),
        ]
    )
    return outputs


def run(
    *,
    phase: str,
    cases_path: str | Path = DEFAULT_E14_OUT,
    output_dir: str | Path | None = None,
    freeze_path: str | Path = DEFAULT_FREEZE,
    prompt_verification_path: str | Path = DEFAULT_PROMPT_VERIFICATION_OUT,
    resume: bool = False,
) -> dict[str, Any]:
    cases_file = Path(cases_path)
    cases = load_cases(cases_file)
    prompt_verification_file = Path(prompt_verification_path)
    _, prompt_verification = load_prompt_verification(
        prompt_verification_file,
        required_cases=cases,
        experiment_id="E14",
        fixture_path=cases_file,
    )
    plan = build_plan(cases, phase=phase)
    output = Path(output_dir or (DEFAULT_SMOKE_OUTPUT if phase == "smoke" else DEFAULT_OUTPUT))
    output.mkdir(parents=True, exist_ok=True)
    plan_path = output / "execution_plan.json"
    write_json(plan_path, plan)
    freeze = verify_freeze(freeze_path) if phase == "formal" else None
    configuration = {
        "protocol_id": PROTOCOL_ID,
        "workload_revision": WORKLOAD_REVISION,
        "phase": phase,
        "plan_sha256": sha256_file(plan_path),
        "fixture_sha256": sha256_file(cases_file),
        "freeze_sha256": sha256_file(freeze_path) if freeze else None,
        "freeze_path": Path(freeze_path).resolve().relative_to(ROOT).as_posix(),
        "prompt_verification_sha256": sha256_file(prompt_verification_file),
        "transport": "ollama_native",
        "dynamic_num_ctx": None,
        "seed_base": SEED,
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
        "headroom_gate": HEADROOM_GATE,
        "token_tolerance": TOKEN_TOLERANCE,
    }
    manifest_path = output / "manifest.json"
    expected = int(plan["expected_formal_case_runs"])
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("configuration_hash") != stable_json_hash(configuration):
            raise RuntimeError("refusing E14 V2 resume: configuration changed")
        if not resume:
            raise FileExistsError("E14 V2 manifest exists; pass --resume")
        manifest["status"] = "running"
        record_event(manifest, "resumed", "explicit E14 V2 resume requested")
    else:
        manifest = new_manifest(
            "E14",
            dataset_paths=[cases_file, prompt_verification_file, plan_path],
            configuration=configuration,
            expected_runs=expected,
            models=[MODEL_ALIAS_BY_TARGET[target] for target in CONTEXT_LENGTHS],
            command=list(sys.argv),
        )
        manifest["protocol_id"] = PROTOCOL_ID
        manifest["workload_revision"] = WORKLOAD_REVISION
        manifest["configuration_hash"] = stable_json_hash(configuration)
        manifest["correction_of"] = "invalid V3 E14 context-axis evidence"
        manifest["denominator_policy"] = "V2_only_old_V3_excluded"
        manifest["warmup_expected_case_runs"] = int(plan.get("expected_warmup_case_runs", 0))
        manifest["jobs"] = [
            {**job, "status": "pending", "attempts": 0, "last_error": None}
            for job in plan["jobs"]
        ]
    register_artifact(manifest, plan_path, kind="execution_plan")
    register_artifact(
        manifest, prompt_verification_file, kind="prompt_workload_verification"
    )
    save_manifest(manifest, manifest_path)
    rows: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    try:
        for target in CONTEXT_LENGTHS:
            for job in (item for item in plan["jobs"] if item["target_prompt_tokens"] == target):
                entry = next(item for item in manifest["jobs"] if item["id"] == job["id"])
                job_dir = output / "work" / job["id"]
                record_path = output / "work" / job["id"] / "job_record.json"
                record = None
                if record_path.exists():
                    record = json.loads(record_path.read_text(encoding="utf-8"))
                    if reusable_job_evidence(
                        record, job, tolerance=TOKEN_TOLERANCE
                    ):
                        if entry.get("status") != "completed":
                            entry["status"] = "completed"
                            entry["last_error"] = None
                            entry["completed_at"] = record.get("completed_at") or utc_now()
                            record_event(
                                manifest,
                                "durable_job_recovered",
                                f"recovered complete evidence for {job['id']}",
                            )
                            save_manifest(manifest, manifest_path)
                    else:
                        archived = archive_invalid_job_attempt(
                            output,
                            job["id"],
                            attempt=max(1, int(entry.get("attempts", 0))),
                        )
                        record_event(
                            manifest,
                            "invalid_job_archived",
                            f"rerunning complete affected condition {job['id']}",
                            archive=str(archived) if archived else None,
                        )
                        entry["status"] = "pending"
                        entry["last_error"] = "semantic resume audit failed"
                        record = None
                elif job_dir.exists():
                    archived = archive_invalid_job_attempt(
                        output,
                        job["id"],
                        attempt=max(1, int(entry.get("attempts", 0))),
                    )
                    record_event(
                        manifest,
                        "partial_job_archived",
                        f"preserved incomplete condition before rerun {job['id']}",
                        archive=str(archived) if archived else None,
                    )
                    entry["status"] = "pending"
                    entry["last_error"] = "partial job evidence archived"
                if record is None:
                    entry["status"] = "running"
                    entry["attempts"] = int(entry.get("attempts", 0)) + 1
                    save_manifest(manifest, manifest_path)
                    record = execute_matrix_job(
                        job,
                        cases_path=cases_file,
                        output_dir=output,
                        resume=False,
                        max_steps=3,
                        max_tokens=MAX_TOKENS,
                        timeout_seconds=600.0,
                        lane_timeout_seconds=7200.0,
                        temperature=TEMPERATURE,
                        seed=SEED + int(job["outer_replicate_id"]),
                        capture_telemetry=True,
                        telemetry_poll_seconds=0.5,
                        prompt_verification=prompt_verification,
                    )
                    entry["status"] = record["status"]
                    entry["last_error"] = None if record["status"] == "completed" else "job completeness failure"
                    entry["completed_at"] = utc_now()
                    save_manifest(manifest, manifest_path)
                records.append(record)
                rows.extend(read_jsonl(record["raw_path"]))
            stop_model(MODEL_ALIAS_BY_TARGET[target])
            record_event(manifest, "model_stopped", MODEL_ALIAS_BY_TARGET[target])
            save_manifest(manifest, manifest_path)
        validity = _validate(plan, cases, rows, records)
        outputs = _build_outputs(
            output,
            plan,
            cases,
            rows,
            records,
            validity,
            cases_path=cases_file,
        )
        for path, kind in outputs:
            register_artifact(manifest, path, kind=kind)
        failed_jobs = sum(job.get("status") != "completed" for job in manifest["jobs"])
        manifest["validity_checks"] = validity
        unresolved_cases = int(validity["provider_incomplete_case_runs"])
        if validity["status"] != "pass" or failed_jobs:
            manifest["progress"] = semantic_failure_progress(
                expected_runs=expected,
                completed_runs=int(validity["observed_formal_case_runs"]),
                failed_jobs=failed_jobs,
                unresolved_cases=unresolved_cases,
            )
            fail_manifest(
                manifest,
                category="semantic_validity",
                message=f"semantic validity={validity['status']}, failed_jobs={failed_jobs}",
            )
        else:
            finish_manifest(
                manifest,
                completed_runs=expected,
                failed_jobs=0,
                unresolved_cases=unresolved_cases,
            )
        save_manifest(manifest, manifest_path)
        return manifest
    except Exception as exc:
        fail_manifest(manifest, category=type(exc).__name__, message=str(exc))
        save_manifest(manifest, manifest_path)
        raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=["plan", "smoke", "formal", "audit"], required=True)
    parser.add_argument("--cases", type=Path, default=DEFAULT_E14_OUT)
    parser.add_argument("--out-dir", type=Path)
    parser.add_argument("--freeze", type=Path, default=DEFAULT_FREEZE)
    parser.add_argument(
        "--prompt-verification",
        type=Path,
        default=DEFAULT_PROMPT_VERIFICATION_OUT,
    )
    parser.add_argument("--resume", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cases = load_cases(args.cases)
    if args.phase == "plan":
        print(json.dumps(build_plan(cases, phase="formal"), ensure_ascii=False, indent=2))
        return 0
    if args.phase == "audit":
        output = args.out_dir or DEFAULT_OUTPUT
        plan = json.loads((output / "execution_plan.json").read_text(encoding="utf-8"))
        rows = read_jsonl(output / "raw_runs.jsonl")
        records = read_jsonl(output / "job_records.jsonl")
        validity = _validate(plan, cases, rows, records)
        write_json(output / "validity_checks.json", validity)
        print(json.dumps(validity, ensure_ascii=False, indent=2))
        return 0 if validity["status"] == "pass" else 1
    manifest = run(
        phase=args.phase,
        cases_path=args.cases,
        output_dir=args.out_dir,
        freeze_path=args.freeze,
        prompt_verification_path=args.prompt_verification,
        resume=args.resume,
    )
    output = args.out_dir or (DEFAULT_SMOKE_OUTPUT if args.phase == "smoke" else DEFAULT_OUTPUT)
    print(json.dumps({"status": manifest["status"], "manifest": str(output / "manifest.json")}, ensure_ascii=False))
    return 0 if manifest["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
