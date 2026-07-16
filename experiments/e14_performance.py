"""E14 real-model latency, throughput, token, and GPU benchmark runner.

The shared core remains sequential by design.  E14 obtains concurrency by
launching independent, disjoint ``m3_core.run_matrix`` lanes, each with its own
recoverable output directory.  Unit tests inject a lane executor and never
start Ollama or a model.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import Future, ThreadPoolExecutor, wait
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

import experiments.manifest as manifest_helpers
from experiments.catalog import (
    ALL_MODELS,
    CONTEXT_LENGTHS,
    CORE_MODELS,
    PERFORMANCE_CONCURRENCY,
)
from experiments.manifest import (
    fail_manifest,
    finish_manifest,
    new_manifest,
    record_event,
    register_artifact,
    save_manifest,
    sha256_file,
    utc_now,
)
from experiments.model_manager import gpu_snapshot, installed_models, stop_model
from m3_core.tool_sandbox import SANDBOX_RUNTIME_VERSION
from m3_eval.figure_manifest import FIGURE_MANIFEST_FILENAME, write_figure_manifest
from m3_eval.statistics import (
    clustered_paired_bootstrap,
    holm_adjust,
    latency_summary,
    percentile,
    proportion_result,
    wilcoxon_signed_rank,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = ROOT / "experiments" / "fixtures" / "smoke_cases.jsonl"
DEFAULT_OUT_DIR = ROOT / "outputs" / "experiments" / "E14"
E14_IMPLEMENTATION_FILES = (
    "experiments/catalog.py",
    "experiments/e14_performance.py",
    "experiments/manifest.py",
    "experiments/model_manager.py",
    "m3_eval/figure_manifest.py",
    "m3_eval/statistics.py",
)
E14_IMPLEMENTATION_ROOTS = ("m3_core", "m3_guard", "schemas")
E14_RESUME_IDENTITY_FIELDS = (
    "sandbox_runtime_version",
    "implementation_sha256",
)
CONDITIONS = (
    {"id": "off", "prompt_profile": "normal", "guard_mode": "off"},
    {"id": "full_guard", "prompt_profile": "normal", "guard_mode": "full_guard"},
)
SUCCESS_TERMINAL = {
    "completed",
    "blocked",
    "needs_confirmation",
    "max_steps_reached",
}
PERFORMANCE_FIELDS = (
    "job_id",
    "model",
    "num_ctx",
    "concurrency",
    "condition",
    "prompt_profile",
    "guard_mode",
    "job_status",
    "expected_case_runs",
    "observed_case_runs",
    "successful_case_runs",
    "missing_case_runs",
    "error_case_runs",
    "timeout_case_runs",
    "error_rate",
    "error_rate_ci_low",
    "error_rate_ci_high",
    "timeout_rate",
    "timeout_rate_ci_low",
    "timeout_rate_ci_high",
    "wall_seconds",
    "throughput_case_runs_per_s",
    "model_latency_count",
    "model_latency_median_ms",
    "model_latency_p95_ms",
    "guard_latency_count",
    "guard_latency_median_ms",
    "guard_latency_p95_ms",
    "total_latency_count",
    "total_latency_median_ms",
    "total_latency_p95_ms",
    "prompt_token_count",
    "prompt_tokens_median",
    "completion_token_count",
    "completion_tokens_median",
    "total_token_count",
    "total_tokens_median",
    "gpu_sample_count",
    "gpu_peak_memory_mib",
    "gpu_memory_delta_mib",
)


def _json_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def _safe_name(value: Any) -> str:
    text = "".join(character if character.isalnum() else "_" for character in str(value))
    return text.strip("_") or "item"


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temp, path)


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    with temp.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    os.replace(temp, path)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8-sig") as stream:
        for line_number, line in enumerate(stream, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON") from exc
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{line_number}: row must be an object")
            rows.append(row)
    return rows


def _write_csv(path: Path, rows: Sequence[dict[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def load_representative_cases(path: str | Path = DEFAULT_CASES) -> list[dict[str, Any]]:
    rows = _read_jsonl(Path(path))
    if not rows:
        raise ValueError("E14 representative case set is empty")
    case_ids = [str(row.get("case_id", "")).strip() for row in rows]
    if any(not case_id for case_id in case_ids):
        raise ValueError("every E14 representative case needs a case_id")
    duplicates = sorted(key for key, count in Counter(case_ids).items() if count > 1)
    if duplicates:
        raise ValueError(f"duplicate representative case_id values: {duplicates}")
    return rows


def _validate_grid(
    models: Sequence[str], contexts: Sequence[int], concurrencies: Sequence[int]
) -> None:
    if not models:
        raise ValueError("at least one model is required")
    unsupported_models = sorted(set(models) - set(ALL_MODELS))
    if unsupported_models:
        raise ValueError(f"models outside the approved catalogue: {unsupported_models}")
    unsupported_contexts = sorted(set(contexts) - set(CONTEXT_LENGTHS))
    if unsupported_contexts:
        raise ValueError(f"unsupported num_ctx values: {unsupported_contexts}")
    unsupported_concurrency = sorted(set(concurrencies) - set(PERFORMANCE_CONCURRENCY))
    if unsupported_concurrency:
        raise ValueError(f"unsupported concurrency values: {unsupported_concurrency}")


def build_execution_plan(
    cases: Sequence[dict[str, Any]],
    *,
    models: Sequence[str] = (CORE_MODELS[0],),
    contexts: Sequence[int] = CONTEXT_LENGTHS,
    concurrencies: Sequence[int] = PERFORMANCE_CONCURRENCY,
    repeats: int = 1,
    warmup: bool = True,
) -> dict[str, Any]:
    """Create a deterministic, counterbalanced E14 job plan."""

    models = tuple(dict.fromkeys(str(model) for model in models))
    contexts = tuple(dict.fromkeys(int(value) for value in contexts))
    concurrencies = tuple(dict.fromkeys(int(value) for value in concurrencies))
    _validate_grid(models, contexts, concurrencies)
    if repeats < 1:
        raise ValueError("repeats must be at least 1")
    case_ids = [str(case["case_id"]) for case in cases]
    if max(concurrencies) > len(case_ids):
        raise ValueError("representative case count must be at least the maximum concurrency")

    jobs: list[dict[str, Any]] = []
    cell_index = 0
    for model in models:
        model_key = _safe_name(model)
        for num_ctx in contexts:
            if warmup:
                for condition in CONDITIONS:
                    jobs.append(
                        {
                            "id": (
                                f"warmup__{model_key}__ctx{num_ctx}"
                                f"__{condition['id']}"
                            ),
                            "job_type": "warmup",
                            "model": model,
                            "num_ctx": num_ctx,
                            "concurrency": 1,
                            "condition": condition["id"],
                            "prompt_profile": condition["prompt_profile"],
                            "guard_mode": condition["guard_mode"],
                            "case_ids": list(case_ids),
                            "repeats": 1,
                            "expected_case_runs": len(case_ids),
                            "excluded_from_metrics": True,
                        }
                    )
            for concurrency in concurrencies:
                # Alternate condition order to avoid a universal time-order bias.
                ordered_conditions = CONDITIONS if cell_index % 2 == 0 else tuple(reversed(CONDITIONS))
                for condition in ordered_conditions:
                    jobs.append(
                        {
                            "id": (
                                f"perf__{model_key}__ctx{num_ctx}__c{concurrency}"
                                f"__{condition['id']}"
                            ),
                            "job_type": "performance",
                            "model": model,
                            "num_ctx": num_ctx,
                            "concurrency": concurrency,
                            "condition": condition["id"],
                            "prompt_profile": condition["prompt_profile"],
                            "guard_mode": condition["guard_mode"],
                            "case_ids": list(case_ids),
                            "repeats": int(repeats),
                            "expected_case_runs": len(case_ids) * int(repeats),
                            "excluded_from_metrics": False,
                        }
                    )
                cell_index += 1
    return {
        "schema_version": "1.0",
        "experiment_id": "E14",
        "backend": "ollama",
        "scope": "dedicated_representative_performance",
        "models": list(models),
        "num_ctx_values": list(contexts),
        "concurrency_values": list(concurrencies),
        "conditions": [dict(item) for item in CONDITIONS],
        "case_ids": case_ids,
        "repeats": int(repeats),
        "warmup_enabled": bool(warmup),
        "warmup_conditions": (
            [str(condition["id"]) for condition in CONDITIONS] if warmup else []
        ),
        "warmup_case_run_count": sum(
            int(job["expected_case_runs"])
            for job in jobs
            if job["job_type"] == "warmup"
        ),
        "performance_job_count": sum(job["job_type"] == "performance" for job in jobs),
        "warmup_job_count": sum(job["job_type"] == "warmup" for job in jobs),
        "jobs": jobs,
    }


def _partition_case_ids(case_ids: Sequence[str], concurrency: int) -> list[list[str]]:
    lanes = [[] for _ in range(int(concurrency))]
    for index, case_id in enumerate(case_ids):
        lanes[index % concurrency].append(case_id)
    return [lane for lane in lanes if lane]


def _lane_specs(
    job: dict[str, Any],
    *,
    output_dir: Path,
    cases_path: Path,
    resume: bool,
    seed: int,
    temperature: float,
    max_tokens: int,
    max_steps: int,
    request_timeout_seconds: float,
    lane_timeout_seconds: float,
    ask_threshold: float,
    deny_threshold: float,
) -> list[dict[str, Any]]:
    job_dir = output_dir / "work" / str(job["id"])
    lane_groups = _partition_case_ids(job["case_ids"], int(job["concurrency"]))
    specs: list[dict[str, Any]] = []
    condition_id = (
        f"e14_warmup_{job['condition']}"
        if job["job_type"] == "warmup"
        else f"e14_{job['condition']}"
    )
    for lane_id, lane_case_ids in enumerate(lane_groups):
        lane_dir = job_dir / f"lane_{lane_id}"
        lane_dir.mkdir(parents=True, exist_ok=True)
        run_prefix = f"{_safe_name(job['id'])}_lane{lane_id}"
        raw_path = lane_dir / f"{run_prefix}_{condition_id}.jsonl"
        command = [
            sys.executable,
            "-m",
            "m3_core.run_matrix",
            "--cases",
            str(cases_path),
            "--backend",
            "ollama",
            "--model",
            str(job["model"]),
            "--conditions",
            f"{condition_id}={job['prompt_profile']}:{job['guard_mode']}",
            "--ask-threshold",
            str(float(ask_threshold)),
            "--deny-threshold",
            str(float(deny_threshold)),
            "--case-ids",
            ",".join(lane_case_ids),
            "--out-dir",
            str(lane_dir),
            "--max-steps",
            str(int(max_steps)),
            "--run-prefix",
            run_prefix,
            "--run-group",
            "E14",
            "--seed",
            str(int(seed)),
            "--selection-seed",
            str(int(seed)),
            "--generation-seed",
            str(int(seed)),
            "--repeats",
            str(int(job["repeats"])),
            "--temperature",
            str(float(temperature)),
            "--max-tokens",
            str(int(max_tokens)),
            "--num-ctx",
            str(int(job["num_ctx"])),
            "--timeout",
            str(float(request_timeout_seconds)),
            "--notes",
            (
                "E14 real-model warmup lane; excluded from metrics"
                if job["job_type"] == "warmup"
                else "E14 real-model performance lane"
            ),
        ]
        if resume:
            command.append("--resume")
        specs.append(
            {
                "job_id": job["id"],
                "lane_id": lane_id,
                "case_ids": lane_case_ids,
                "command": command,
                "cwd": ROOT,
                "stdout_path": lane_dir / "stdout.log",
                "stderr_path": lane_dir / "stderr.log",
                "raw_path": raw_path,
                "timeout_seconds": float(lane_timeout_seconds),
            }
        )
    return specs


def _tail(path: Path, lines: int = 50) -> list[str]:
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:]


def subprocess_lane_executor(spec: dict[str, Any]) -> dict[str, Any]:
    """Run one recoverable lane with process-alive and hard-timeout monitoring."""

    started = time.perf_counter()
    timed_out = False
    terminated = False
    with (
        Path(spec["stdout_path"]).open("w", encoding="utf-8") as stdout,
        Path(spec["stderr_path"]).open("w", encoding="utf-8") as stderr,
    ):
        process = subprocess.Popen(
            list(spec["command"]),
            cwd=Path(spec["cwd"]),
            stdout=stdout,
            stderr=stderr,
            text=True,
        )
        try:
            return_code = process.wait(timeout=float(spec["timeout_seconds"]))
        except subprocess.TimeoutExpired:
            timed_out = True
            process.terminate()
            terminated = True
            try:
                return_code = process.wait(timeout=10.0)
            except subprocess.TimeoutExpired:
                process.kill()
                return_code = process.wait(timeout=10.0)
    return {
        "lane_id": spec["lane_id"],
        "case_ids": list(spec["case_ids"]),
        "command": list(spec["command"]),
        "exit_code": int(return_code),
        "timed_out": timed_out,
        "terminated": terminated,
        "process_alive_checked": True,
        "duration_seconds": time.perf_counter() - started,
        "stdout_path": str(spec["stdout_path"]),
        "stderr_path": str(spec["stderr_path"]),
        "stderr_tail": _tail(Path(spec["stderr_path"])),
        "raw_path": str(spec["raw_path"]),
        "raw_exists": Path(spec["raw_path"]).exists(),
    }


def _capture_gpu(
    provider: Callable[[], dict[str, Any]], job_id: str, phase: str
) -> dict[str, Any]:
    try:
        snapshot = dict(provider())
    except Exception as exc:  # GPU telemetry must not erase model measurements.
        snapshot = {
            "captured_at": utc_now(),
            "available": False,
            "reason": f"{type(exc).__name__}: {exc}",
        }
    snapshot["job_id"] = job_id
    snapshot["phase"] = phase
    return snapshot


def _gpu_peak(samples: Sequence[dict[str, Any]]) -> float | None:
    values = [
        float(sample["memory_used_mib"])
        for sample in samples
        if sample.get("available") and sample.get("memory_used_mib") is not None
    ]
    return max(values) if values else None


def execute_job(
    job: dict[str, Any],
    *,
    output_dir: Path,
    cases_path: Path,
    resume: bool,
    seed: int,
    temperature: float,
    max_tokens: int,
    max_steps: int,
    request_timeout_seconds: float,
    lane_timeout_seconds: float,
    gpu_poll_seconds: float,
    ask_threshold: float,
    deny_threshold: float,
    lane_executor: Callable[[dict[str, Any]], dict[str, Any]] = subprocess_lane_executor,
    gpu_provider: Callable[[], dict[str, Any]] = gpu_snapshot,
) -> dict[str, Any]:
    """Execute all lanes for one condition/context/concurrency cell."""

    specs = _lane_specs(
        job,
        output_dir=output_dir,
        cases_path=cases_path,
        resume=resume,
        seed=seed,
        temperature=temperature,
        max_tokens=max_tokens,
        max_steps=max_steps,
        request_timeout_seconds=request_timeout_seconds,
        lane_timeout_seconds=lane_timeout_seconds,
        ask_threshold=ask_threshold,
        deny_threshold=deny_threshold,
    )
    started_at = utc_now()
    samples = [_capture_gpu(gpu_provider, str(job["id"]), "before")]
    started = time.perf_counter()
    lane_results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=len(specs)) as executor:
        futures: dict[Future[dict[str, Any]], dict[str, Any]] = {
            executor.submit(lane_executor, spec): spec for spec in specs
        }
        pending = set(futures)
        while pending:
            done, pending = wait(pending, timeout=max(0.01, float(gpu_poll_seconds)))
            if pending:
                samples.append(_capture_gpu(gpu_provider, str(job["id"]), "running"))
            for future in done:
                spec = futures[future]
                try:
                    result = dict(future.result())
                except Exception as exc:
                    result = {
                        "lane_id": spec["lane_id"],
                        "case_ids": list(spec["case_ids"]),
                        "command": list(spec["command"]),
                        "exit_code": None,
                        "timed_out": isinstance(exc, TimeoutError),
                        "terminated": False,
                        "process_alive_checked": True,
                        "duration_seconds": None,
                        "stdout_path": str(spec["stdout_path"]),
                        "stderr_path": str(spec["stderr_path"]),
                        "stderr_tail": [f"{type(exc).__name__}: {exc}"],
                        "raw_path": str(spec["raw_path"]),
                        "raw_exists": Path(spec["raw_path"]).exists(),
                    }
                lane_results.append(result)
    wall_seconds = time.perf_counter() - started
    samples.append(_capture_gpu(gpu_provider, str(job["id"]), "after"))
    lane_results.sort(key=lambda item: int(item["lane_id"]))
    complete = all(
        result.get("exit_code") == 0
        and not result.get("timed_out")
        and result.get("raw_exists")
        for result in lane_results
    )
    raw_rows: list[dict[str, Any]] = []
    for result in lane_results:
        lane_id = int(result["lane_id"])
        for row in _read_jsonl(Path(result["raw_path"])):
            raw_rows.append(
                {
                    **row,
                    "performance_job_id": job["id"],
                    "performance_job_type": job["job_type"],
                    "performance_model": job["model"],
                    "performance_num_ctx": job["num_ctx"],
                    "performance_concurrency": job["concurrency"],
                    "performance_condition": job["condition"],
                    "performance_lane_id": lane_id,
                    "performance_wall_seconds": wall_seconds,
                }
            )
    before_memory = samples[0].get("memory_used_mib") if samples[0].get("available") else None
    peak_memory = _gpu_peak(samples)
    record = {
        "schema_version": "1.0",
        **{key: value for key, value in job.items() if key != "case_ids"},
        "case_ids": list(job["case_ids"]),
        "status": "completed" if complete else "failed",
        "started_at": started_at,
        "completed_at": utc_now(),
        "wall_seconds": wall_seconds,
        "lane_count": len(specs),
        "lanes": lane_results,
        "raw_row_count": len(raw_rows),
        "gpu_sample_count": len(samples),
        "gpu_peak_memory_mib": peak_memory,
        "gpu_memory_delta_mib": (
            peak_memory - float(before_memory)
            if peak_memory is not None and before_memory is not None
            else None
        ),
        "timed_out": any(bool(result.get("timed_out")) for result in lane_results),
        "error_count": sum(
            result.get("exit_code") != 0
            or result.get("timed_out")
            or not result.get("raw_exists")
            for result in lane_results
        ),
    }
    job_dir = output_dir / "work" / str(job["id"])
    _write_json(job_dir / "job_record.json", record)
    _write_jsonl(job_dir / "raw_runs.jsonl", raw_rows)
    _write_jsonl(job_dir / "gpu_snapshots.jsonl", samples)
    return {"record": record, "raw_rows": raw_rows, "gpu_samples": samples}


def _job_evidence(output_dir: Path, job: dict[str, Any]) -> tuple[dict[str, Any] | None, list[dict[str, Any]], list[dict[str, Any]]]:
    job_dir = output_dir / "work" / str(job["id"])
    record_path = job_dir / "job_record.json"
    record = json.loads(record_path.read_text(encoding="utf-8")) if record_path.exists() else None
    return (
        record,
        _read_jsonl(job_dir / "raw_runs.jsonl"),
        _read_jsonl(job_dir / "gpu_snapshots.jsonl"),
    )


def collect_evidence(
    output_dir: Path, plan: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    raw_rows: list[dict[str, Any]] = []
    gpu_rows: list[dict[str, Any]] = []
    for job in plan["jobs"]:
        record, rows, samples = _job_evidence(output_dir, job)
        if record is not None:
            records.append(record)
        raw_rows.extend(rows)
        gpu_rows.extend(samples)
    return records, raw_rows, gpu_rows


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def build_case_run_records(raw_rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in raw_rows:
        if row.get("performance_job_type") != "performance":
            continue
        run_key = str(row.get("run_key") or "")
        if not run_key:
            run_key = "|".join(
                str(row.get(field, ""))
                for field in ("case_id", "replicate_id", "seed", "condition_id")
            )
        grouped[(str(row.get("performance_job_id")), run_key)].append(row)

    records: list[dict[str, Any]] = []
    for (job_id, run_key), rows in sorted(grouped.items()):
        rows = sorted(rows, key=lambda row: int(row.get("step") or 0))
        first, last = rows[0], rows[-1]
        model_values = [_number(row.get("model_latency_ms")) for row in rows]
        guard_values = [_number(row.get("guard_latency_ms")) for row in rows]
        step_total_values = [_number(row.get("total_latency_ms")) for row in rows]
        case_values = [_number(row.get("case_latency_ms")) for row in rows]
        case_values = [value for value in case_values if value is not None]

        def complete_sum(values: Sequence[float | None]) -> float | None:
            observed = [value for value in values if value is not None]
            return sum(observed) if observed else None

        def complete_tokens(name: str) -> float | None:
            values = [_number(row.get(name)) for row in rows]
            return sum(value for value in values if value is not None) if values and all(
                value is not None for value in values
            ) else None

        timed_out = any(bool(row.get("timed_out")) for row in rows)
        error = any(
            str(row.get("final_status")) == "error"
            or str(row.get("guard_decision")) == "error"
            for row in rows
        )
        terminal = str(last.get("final_status", "")) in SUCCESS_TERMINAL
        records.append(
            {
                "job_id": job_id,
                "run_key": run_key,
                "case_id": str(first.get("case_id", "")),
                "replicate_id": int(first.get("replicate_id") or 0),
                "seed": first.get("seed"),
                "model": first.get("performance_model") or first.get("model"),
                "num_ctx": int(first.get("performance_num_ctx")),
                "concurrency": int(first.get("performance_concurrency")),
                "condition": str(first.get("performance_condition")),
                "model_latency_ms": complete_sum(model_values),
                "guard_latency_ms": complete_sum(guard_values),
                "total_latency_ms": max(case_values) if case_values else complete_sum(step_total_values),
                "prompt_tokens": complete_tokens("prompt_tokens"),
                "completion_tokens": complete_tokens("completion_tokens"),
                "total_tokens": complete_tokens("total_tokens"),
                "timed_out": timed_out,
                "error": error,
                "terminal": terminal,
                "successful": terminal and not error and not timed_out,
                "final_status": last.get("final_status"),
            }
        )
    return records


def _summary_fields(prefix: str, values: Sequence[float]) -> dict[str, Any]:
    summary = latency_summary(values)
    return {
        f"{prefix}_count": summary["count"],
        f"{prefix}_median_ms": summary["median"],
        f"{prefix}_p95_ms": summary["p95"],
    }


def _token_fields(prefix: str, values: Sequence[float]) -> dict[str, Any]:
    summary = latency_summary(values)
    return {
        f"{prefix}_count": summary["count"],
        f"{prefix}s_median": summary["median"],
    }


def build_performance_metrics(
    plan: dict[str, Any],
    job_records: Sequence[dict[str, Any]],
    case_records: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    record_by_job = {str(record["id"]): record for record in job_records}
    cases_by_job: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in case_records:
        cases_by_job[str(record["job_id"])].append(record)
    metrics: list[dict[str, Any]] = []
    for job in plan["jobs"]:
        if job["job_type"] != "performance":
            continue
        records = cases_by_job.get(str(job["id"]), [])
        job_record = record_by_job.get(str(job["id"]))
        expected = int(job["expected_case_runs"])
        observed = len(records)
        successful = [record for record in records if record["successful"]]
        errors = sum(bool(record["error"]) for record in records)
        timeouts = sum(bool(record["timed_out"]) for record in records)
        error_result = proportion_result(errors, observed)
        timeout_result = proportion_result(timeouts, observed)
        wall = _number(job_record.get("wall_seconds")) if job_record else None
        job_status = str(job_record.get("status")) if job_record else "missing"
        fully_observed = job_status == "completed" and observed == expected
        throughput = (
            len(successful) / wall
            if fully_observed and wall is not None and wall > 0.0 and successful
            else None
        )

        def values(name: str) -> list[float]:
            return [
                float(record[name])
                for record in successful
                if record.get(name) is not None
            ]

        gpu_peak = _number(job_record.get("gpu_peak_memory_mib")) if job_record else None
        gpu_delta = _number(job_record.get("gpu_memory_delta_mib")) if job_record else None
        row = {
            "job_id": job["id"],
            "model": job["model"],
            "num_ctx": job["num_ctx"],
            "concurrency": job["concurrency"],
            "condition": job["condition"],
            "prompt_profile": job["prompt_profile"],
            "guard_mode": job["guard_mode"],
            "job_status": (
                "completed"
                if fully_observed
                else "partial"
                if job_status == "completed"
                else job_status
            ),
            "expected_case_runs": expected,
            "observed_case_runs": observed,
            "successful_case_runs": len(successful),
            "missing_case_runs": max(0, expected - observed),
            "error_case_runs": errors,
            "timeout_case_runs": timeouts,
            "error_rate": error_result["value"],
            "error_rate_ci_low": error_result["ci_low"],
            "error_rate_ci_high": error_result["ci_high"],
            "timeout_rate": timeout_result["value"],
            "timeout_rate_ci_low": timeout_result["ci_low"],
            "timeout_rate_ci_high": timeout_result["ci_high"],
            "wall_seconds": wall,
            "throughput_case_runs_per_s": throughput,
            **_summary_fields("model_latency", values("model_latency_ms")),
            **_summary_fields("guard_latency", values("guard_latency_ms")),
            **_summary_fields("total_latency", values("total_latency_ms")),
            **_token_fields("prompt_token", values("prompt_tokens")),
            **_token_fields("completion_token", values("completion_tokens")),
            **_token_fields("total_token", values("total_tokens")),
            "gpu_sample_count": int(job_record.get("gpu_sample_count", 0)) if job_record else 0,
            "gpu_peak_memory_mib": gpu_peak,
            "gpu_memory_delta_mib": gpu_delta,
        }
        metrics.append(row)
    return metrics


def _na_wilcoxon(pair_count: int = 0) -> dict[str, Any]:
    return {
        "method": "wilcoxon_signed_rank",
        "pairs": pair_count,
        "nonzero_pairs": None,
        "zero_pairs": None,
        "w_plus": None,
        "w_minus": None,
        "statistic": None,
        "p_value": None,
        "rank_biserial": None,
        "median_difference": None,
        "status": "NA_insufficient_pairs",
    }


def _signed_summary(values: Iterable[float]) -> dict[str, Any]:
    """Summarize a finite signed effect sample without clipping improvements.

    End-to-end overhead is a signed effect: negative values mean the guarded
    run happened to be faster than its paired baseline.  Reusing
    ``latency_summary`` here incorrectly rejects those legitimate observations.
    """

    sample = [float(value) for value in values]
    if any(not math.isfinite(value) for value in sample):
        raise ValueError("signed effect samples must be finite")
    return {
        "count": len(sample),
        "median": percentile(sample, 0.50),
        "p95": percentile(sample, 0.95),
    }


def build_statistics(
    plan: dict[str, Any],
    case_records: Sequence[dict[str, Any]],
    metrics: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    records_by_cell: dict[tuple[str, int, int, str], list[dict[str, Any]]] = defaultdict(list)
    for record in case_records:
        records_by_cell[
            (
                str(record["model"]),
                int(record["num_ctx"]),
                int(record["concurrency"]),
                str(record["condition"]),
            )
        ].append(record)
    metric_by_cell = {
        (str(row["model"]), int(row["num_ctx"]), int(row["concurrency"]), str(row["condition"])): row
        for row in metrics
    }
    comparisons: list[dict[str, Any]] = []
    p_value_positions: list[int] = []
    p_values: list[float] = []
    for model in plan["models"]:
        for num_ctx in plan["num_ctx_values"]:
            for concurrency in plan["concurrency_values"]:
                base_rows = records_by_cell.get((model, num_ctx, concurrency, "off"), [])
                guard_rows = records_by_cell.get((model, num_ctx, concurrency, "full_guard"), [])

                def pair_key(row: dict[str, Any]) -> tuple[Any, ...]:
                    return (row["case_id"], row["replicate_id"], row.get("seed"))

                base_map = {pair_key(row): row for row in base_rows if row["successful"]}
                guard_map = {pair_key(row): row for row in guard_rows if row["successful"]}
                common = sorted(set(base_map) & set(guard_map), key=str)
                common = [
                    key
                    for key in common
                    if base_map[key].get("total_latency_ms") is not None
                    and guard_map[key].get("total_latency_ms") is not None
                ]
                baseline = [float(base_map[key]["total_latency_ms"]) for key in common]
                guarded = [float(guard_map[key]["total_latency_ms"]) for key in common]
                wilcoxon = wilcoxon_signed_rank(baseline, guarded) if common else _na_wilcoxon()
                bootstrap_pairs = [
                    (str(key[0]), float(base_map[key]["total_latency_ms"]), float(guard_map[key]["total_latency_ms"]))
                    for key in common
                ]
                bootstrap = clustered_paired_bootstrap(
                    bootstrap_pairs, iterations=10_000, seed=42
                )
                overhead_percent = [
                    100.0 * (right - left) / left
                    for left, right in zip(baseline, guarded)
                    if left > 0.0
                ]
                overhead_summary = _signed_summary(overhead_percent)
                guard_latencies = [
                    float(guard_map[key]["guard_latency_ms"])
                    for key in common
                    if guard_map[key].get("guard_latency_ms") is not None
                ]
                guard_summary = latency_summary(guard_latencies)
                base_metric = metric_by_cell.get((model, num_ctx, concurrency, "off"), {})
                guard_metric = metric_by_cell.get((model, num_ctx, concurrency, "full_guard"), {})
                base_throughput = _number(base_metric.get("throughput_case_runs_per_s"))
                guard_throughput = _number(guard_metric.get("throughput_case_runs_per_s"))
                throughput_change = (
                    100.0 * (guard_throughput - base_throughput) / base_throughput
                    if base_throughput is not None
                    and base_throughput > 0.0
                    and guard_throughput is not None
                    else None
                )
                comparison = {
                    "model": model,
                    "num_ctx": num_ctx,
                    "concurrency": concurrency,
                    "paired_case_runs": len(common),
                    "expected_paired_case_runs": len(plan["case_ids"]) * int(plan["repeats"]),
                    "total_latency_wilcoxon": wilcoxon,
                    "total_latency_bootstrap_guard_minus_off_ms": bootstrap,
                    "total_latency_overhead_percent": {
                        "count": overhead_summary["count"],
                        "median": overhead_summary["median"],
                        "p95": overhead_summary["p95"],
                    },
                    "guard_latency_ms": {
                        "count": guard_summary["count"],
                        "median": guard_summary["median"],
                        "p95": guard_summary["p95"],
                    },
                    "throughput_change_percent": throughput_change,
                    "target_checks": {
                        "guard_p95_below_10ms": (
                            None if guard_summary["p95"] is None else guard_summary["p95"] < 10.0
                        ),
                        "median_end_to_end_overhead_below_10pct": (
                            None
                            if overhead_summary["median"] is None
                            else overhead_summary["median"] < 10.0
                        ),
                    },
                    "status": (
                        "complete"
                        if len(common) == len(plan["case_ids"]) * int(plan["repeats"])
                        else "partial_or_NA"
                    ),
                }
                p_value = wilcoxon.get("p_value")
                if p_value is not None:
                    p_value_positions.append(len(comparisons))
                    p_values.append(float(p_value))
                comparisons.append(comparison)
    if p_values:
        adjusted = holm_adjust(p_values)
        for index, value in zip(p_value_positions, adjusted):
            comparisons[index]["total_latency_wilcoxon"]["holm_adjusted_p"] = value
    return {
        "schema_version": "1.0",
        "experiment_id": "E14",
        "status": "completed" if all(item["status"] == "complete" for item in comparisons) else "partial",
        "methods": {
            "latency": "case-run median and p95; failed/timeout/missing runs retained as counts",
            "paired_test": "two-sided paired Wilcoxon signed-rank",
            "effect_size": "matched-pairs rank-biserial correlation",
            "confidence_interval": "case-clustered paired bootstrap, 10,000 iterations, seed 42",
            "multiple_comparisons": "Holm family-wise correction",
            "undefined_policy": "missing and zero-denominator values remain null/NA",
        },
        "comparisons": comparisons,
    }


LATENCY_CHART_FIELDS = (
    "model",
    "num_ctx",
    "concurrency",
    "condition",
    "expected_case_runs",
    "observed_case_runs",
    "successful_case_runs",
    "missing_case_runs",
    "error_case_runs",
    "timeout_case_runs",
    "total_latency_count",
    "median_total_latency_ms",
    "p95_total_latency_ms",
    "value_status",
)
THROUGHPUT_CHART_FIELDS = (
    "model",
    "num_ctx",
    "concurrency",
    "condition",
    "expected_case_runs",
    "observed_case_runs",
    "successful_case_runs",
    "missing_case_runs",
    "error_case_runs",
    "timeout_case_runs",
    "wall_seconds",
    "throughput_case_runs_per_s",
    "value_status",
)
GPU_MEMORY_CHART_FIELDS = (
    "job_id",
    "model",
    "num_ctx",
    "concurrency",
    "condition",
    "prompt_profile",
    "guard_mode",
    "job_status",
    "gpu_peak_memory_mib",
    "gpu_memory_delta_mib",
    "gpu_sample_count",
    "peak_status",
    "delta_status",
)


def build_chart_data(metrics: Sequence[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    latency_rows: list[dict[str, Any]] = []
    throughput_rows: list[dict[str, Any]] = []
    for row in metrics:
        median_latency = row.get("total_latency_median_ms")
        p95_latency = row.get("total_latency_p95_ms")
        latency_rows.append(
            {
                "model": row["model"],
                "num_ctx": row["num_ctx"],
                "concurrency": row["concurrency"],
                "condition": row["condition"],
                "expected_case_runs": row.get("expected_case_runs"),
                "observed_case_runs": row.get("observed_case_runs"),
                "successful_case_runs": row.get("successful_case_runs"),
                "missing_case_runs": row.get("missing_case_runs"),
                "error_case_runs": row.get("error_case_runs"),
                "timeout_case_runs": row.get("timeout_case_runs"),
                "total_latency_count": row.get("total_latency_count"),
                "median_total_latency_ms": median_latency,
                "p95_total_latency_ms": p95_latency,
                "value_status": (
                    "observed"
                    if median_latency is not None and p95_latency is not None
                    else "NA_missing_or_failed"
                ),
            }
        )
        throughput = row.get("throughput_case_runs_per_s")
        throughput_rows.append(
            {
                "model": row["model"],
                "num_ctx": row["num_ctx"],
                "concurrency": row["concurrency"],
                "condition": row["condition"],
                "expected_case_runs": row.get("expected_case_runs"),
                "observed_case_runs": row.get("observed_case_runs"),
                "successful_case_runs": row.get("successful_case_runs"),
                "missing_case_runs": row.get("missing_case_runs"),
                "error_case_runs": row.get("error_case_runs"),
                "timeout_case_runs": row.get("timeout_case_runs"),
                "wall_seconds": row.get("wall_seconds"),
                "throughput_case_runs_per_s": throughput,
                "value_status": "observed" if throughput is not None else "NA_missing_or_failed",
            }
        )
    return latency_rows, throughput_rows


def build_gpu_chart_data(metrics: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build the adjacent, NA-preserving data surface for GPU memory figures."""

    rows: list[dict[str, Any]] = []
    for row in metrics:
        peak = row.get("gpu_peak_memory_mib")
        delta = row.get("gpu_memory_delta_mib")
        rows.append(
            {
                "job_id": row["job_id"],
                "model": row["model"],
                "num_ctx": row["num_ctx"],
                "concurrency": row["concurrency"],
                "condition": row["condition"],
                "prompt_profile": row["prompt_profile"],
                "guard_mode": row["guard_mode"],
                "job_status": row["job_status"],
                "gpu_peak_memory_mib": peak,
                "gpu_memory_delta_mib": delta,
                "gpu_sample_count": row.get("gpu_sample_count", 0),
                "peak_status": "observed" if peak is not None else "NA_telemetry_unavailable",
                "delta_status": "observed" if delta is not None else "NA_telemetry_unavailable",
            }
        )
    return rows


def _render_chart(
    rows: Sequence[dict[str, Any]],
    *,
    chart: str,
    png_path: Path,
    svg_path: Path,
) -> dict[str, Any]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    fig, axis = plt.subplots(figsize=(10.5, 6.2))
    observed = [row for row in rows if row["value_status"] == "observed"]
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    models = sorted({str(row["model"]) for row in rows})
    model_scope = (
        f"single-model ({models[0]})"
        if len(models) == 1
        else f"{len(models)} models ({', '.join(models)})"
        if models
        else "model unavailable"
    )
    condition_order = {"off": 0, "full_guard": 1}
    condition_styles = {
        "off": {"linestyle": "--", "marker": "s"},
        "full_guard": {"linestyle": "-", "marker": "o"},
    }

    def ordered_colors(values: Sequence[int]) -> dict[int, Any]:
        ordered = sorted(set(values))
        cmap = plt.get_cmap("viridis")
        if len(ordered) == 1:
            positions = [0.55]
        else:
            positions = [0.12 + 0.76 * index / (len(ordered) - 1) for index in range(len(ordered))]
        return {value: cmap(position) for value, position in zip(ordered, positions)}

    denominator_pairs = sorted(
        {
            (int(row["successful_case_runs"]), int(row["expected_case_runs"]))
            for row in observed
            if row.get("successful_case_runs") is not None
            and row.get("expected_case_runs") is not None
        }
    )
    if len(denominator_pairs) == 1:
        sample_note = f"n={denominator_pairs[0][0]}/{denominator_pairs[0][1]} successful case-runs per job."
    elif denominator_pairs:
        sample_note = "Successful/expected case-runs vary by plotted job: " + ", ".join(
            f"{successful}/{expected}" for successful, expected in denominator_pairs
        ) + "."
    else:
        sample_note = "Successful/expected case-run denominator unavailable."

    if chart == "latency":
        color_order = sorted({int(row["concurrency"]) for row in rows})
        colors = ordered_colors(color_order)
        for row in observed:
            grouped[(row["model"], row["concurrency"], row["condition"])].append(row)
        for key, group in sorted(
            grouped.items(),
            key=lambda item: (
                str(item[0][0]),
                int(item[0][1]),
                condition_order.get(str(item[0][2]), 99),
            ),
        ):
            group.sort(key=lambda row: int(row["num_ctx"]))
            style = condition_styles.get(str(key[2]), {"linestyle": ":", "marker": "^"})
            axis.plot(
                [int(row["num_ctx"]) for row in group],
                [float(row["median_total_latency_ms"]) for row in group],
                color=colors[int(key[1])],
                linestyle=style["linestyle"],
                marker=style["marker"],
                linewidth=1.8,
                markersize=5.5,
            )
        axis.set_xlabel("Context window (tokens)")
        axis.set_ylabel("Median end-to-end latency per successful case-run (ms)")
        axis.set_title(f"E14 {model_scope}: latency by context window")
        context_ticks = sorted({int(row["num_ctx"]) for row in rows})
        axis.set_xticks(context_ticks, [f"{value:,}" for value in context_ticks])
        color_legend_title = "Concurrency"
        color_labels = {value: f"c={value}" for value in color_order}
        footer = (
            f"{sample_note} Points are descriptive medians; p95 is retained in the adjacent CSV.\n"
            "No inferential interval is shown. Only observed rows are plotted; NA is not zero."
        )
        denominator_detail = {
            "successful_over_expected": [
                f"{successful}/{expected}" for successful, expected in denominator_pairs
            ],
            "total_latency_count_values": sorted(
                {
                    int(row["total_latency_count"])
                    for row in observed
                    if row.get("total_latency_count") is not None
                }
            ),
        }
    elif chart == "throughput":
        color_order = sorted({int(row["num_ctx"]) for row in rows})
        colors = ordered_colors(color_order)
        for row in observed:
            grouped[(row["model"], row["num_ctx"], row["condition"])].append(row)
        for key, group in sorted(
            grouped.items(),
            key=lambda item: (
                str(item[0][0]),
                int(item[0][1]),
                condition_order.get(str(item[0][2]), 99),
            ),
        ):
            group.sort(key=lambda row: int(row["concurrency"]))
            style = condition_styles.get(str(key[2]), {"linestyle": ":", "marker": "^"})
            axis.plot(
                [int(row["concurrency"]) for row in group],
                [float(row["throughput_case_runs_per_s"]) for row in group],
                color=colors[int(key[1])],
                linestyle=style["linestyle"],
                marker=style["marker"],
                linewidth=1.8,
                markersize=5.5,
            )
        axis.set_xlabel("Concurrent lanes")
        axis.set_ylabel("Successful case-runs / wall-clock second")
        axis.set_title(f"E14 {model_scope}: throughput by concurrency")
        axis.set_xticks(sorted({int(row["concurrency"]) for row in rows}))
        color_legend_title = "Context window"
        color_labels = {value: f"{value:,} tokens" for value in color_order}
        footer = (
            f"{sample_note} Throughput = successful case-runs / job wall-clock seconds.\n"
            "Each point is one descriptive complete-job estimate; no inferential interval is shown. "
            "Only observed rows are plotted; NA is not zero."
        )
        denominator_detail = {
            "successful_over_expected": [
                f"{successful}/{expected}" for successful, expected in denominator_pairs
            ],
            "wall_seconds_observed_count": sum(
                row.get("wall_seconds") is not None for row in observed
            ),
        }
    else:
        raise ValueError("chart must be latency or throughput")
    if observed:
        color_handles = [
            Line2D([0], [0], color=colors[value], linewidth=2.6, label=color_labels[value])
            for value in color_order
        ]
        color_legend = axis.legend(
            handles=color_handles,
            title=color_legend_title,
            frameon=True,
            facecolor="white",
            edgecolor="#CBD5E1",
            framealpha=0.96,
            fontsize=7.5,
            title_fontsize=8,
            loc="upper left",
        )
        axis.add_artist(color_legend)
        condition_handles = [
            Line2D(
                [0],
                [0],
                color="#334155",
                linestyle=condition_styles[condition]["linestyle"],
                marker=condition_styles[condition]["marker"],
                linewidth=1.8,
                markersize=5.5,
                label=condition,
            )
            for condition in ("off", "full_guard")
        ]
        axis.legend(
            handles=condition_handles,
            title="Condition",
            frameon=True,
            facecolor="white",
            edgecolor="#CBD5E1",
            framealpha=0.96,
            fontsize=7.5,
            title_fontsize=8,
            loc="upper right",
        )
    else:
        axis.text(
            0.5,
            0.5,
            "No complete observed values; NA was not converted to zero",
            transform=axis.transAxes,
            ha="center",
            va="center",
            color="#666666",
        )
    axis.grid(linestyle="--", alpha=0.25)
    fig.text(
        0.5,
        0.01,
        footer,
        ha="center",
        va="bottom",
        fontsize=8.0,
        color="#536372",
    )
    fig.tight_layout(rect=(0, 0.085, 1, 1))
    fig.savefig(png_path, dpi=180, bbox_inches="tight")
    fig.savefig(svg_path, format="svg", bbox_inches="tight")
    plt.close(fig)
    return {
        "row_count": len(rows),
        "plotted_point_count": len(observed),
        "na_point_count": len(rows) - len(observed),
        "na_policy": "NA rows remain blank in CSV and are not plotted",
        "models": models,
        "model_scope": model_scope,
        "title": axis.get_title(),
        "x_label": axis.get_xlabel(),
        "y_label": axis.get_ylabel(),
        "color_order": color_order,
        "encoding": {
            "color": "concurrency in numeric order" if chart == "latency" else "context tokens in numeric order",
            "linestyle": "condition",
            "marker": "condition",
            "condition_styles": condition_styles,
            "legend_background": "opaque_white_with_border",
        },
        "denominator_audit": denominator_detail,
        "footer": footer,
    }


def _render_gpu_memory_chart(
    rows: Sequence[dict[str, Any]],
    *,
    png_path: Path,
    svg_path: Path,
) -> dict[str, Any]:
    """Render device-wide VRAM peak and peak-minus-before delta as two heatmaps."""

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    contexts = sorted({int(row["num_ctx"]) for row in rows})
    models = sorted({str(row["model"]) for row in rows})
    model_scope = (
        f"single-model ({models[0]})"
        if len(models) == 1
        else f"{len(models)} models ({', '.join(models)})"
        if models
        else "model unavailable"
    )
    condition_order = {"off": 0, "full_guard": 1}
    row_keys = sorted(
        {
            (str(row["model"]), int(row["concurrency"]), str(row["condition"]))
            for row in rows
        },
        key=lambda key: (key[0], key[1], condition_order.get(key[2], 99)),
    )
    labels = [f"{model} | c={concurrency} | {condition}" for model, concurrency, condition in row_keys]
    row_index = {key: index for index, key in enumerate(row_keys)}
    column_index = {context: index for index, context in enumerate(contexts)}
    figure_height = max(5.8, 2.6 + 0.34 * len(row_keys))
    fig, axes = plt.subplots(1, 2, figsize=(15.2, figure_height), sharex=False, sharey=True)
    panels = (
        (
            axes[0],
            "gpu_peak_memory_mib",
            "peak_status",
            "Observed device VRAM peak",
            "Blues",
        ),
        (
            axes[1],
            "gpu_memory_delta_mib",
            "delta_status",
            "Peak minus pre-job snapshot",
            "Oranges",
        ),
    )
    gpu_sample_counts = [
        int(row["gpu_sample_count"])
        for row in rows
        if int(row.get("gpu_sample_count") or 0) > 0
        and (row["peak_status"] == "observed" or row["delta_status"] == "observed")
    ]
    if gpu_sample_counts:
        sample_count_min = min(gpu_sample_counts)
        sample_count_max = max(gpu_sample_counts)
        sample_count_note = (
            f"snapshot n={sample_count_min} per cell"
            if sample_count_min == sample_count_max
            else f"snapshot n={sample_count_min}–{sample_count_max} per cell"
        )
    else:
        sample_count_min = None
        sample_count_max = None
        sample_count_note = "snapshot n unavailable"
    footer = (
        f"Device-wide polling ({sample_count_note} in this bundle); transient peaks between snapshots may be missed.\n"
        "Delta = observed job peak − before-job snapshot; neither panel attributes memory causally to Guard."
    )
    integrity: dict[str, Any] = {
        "row_count": len(rows),
        "peak_plotted_point_count": 0,
        "delta_plotted_point_count": 0,
        "peak_na_point_count": 0,
        "delta_na_point_count": 0,
        "na_policy": "NA telemetry remains blank in CSV and is not plotted",
        "measurement_scope": "device-wide nvidia-smi snapshots",
        "models": models,
        "model_scope": model_scope,
        "x_label": "Context window (tokens)",
        "gpu_sample_count_min": sample_count_min,
        "gpu_sample_count_max": sample_count_max,
        "transient_peak_limit": "polling may miss peaks between snapshots",
        "footer": footer,
    }
    for panel_index, (axis, metric, status_field, title, cmap_name) in enumerate(panels):
        observed = [row for row in rows if row[status_field] == "observed"]
        matrix = np.full((len(row_keys), len(contexts)), np.nan, dtype=float)
        for row in observed:
            key = (str(row["model"]), int(row["concurrency"]), str(row["condition"]))
            matrix[row_index[key], column_index[int(row["num_ctx"])]] = float(row[metric])
        axis.set_title(title, loc="left", fontsize=11, fontweight="semibold")
        axis.set_xlabel("Context window (tokens)")
        axis.set_ylabel("Model | concurrency | condition" if panel_index == 0 else "")
        axis.set_xticks(range(len(contexts)), [str(context) for context in contexts])
        axis.set_yticks(range(len(labels)), labels, fontsize=7)
        if observed:
            cmap = plt.get_cmap(cmap_name).copy()
            cmap.set_bad("#EEF1F4")
            vmax = max(1.0, max(float(row[metric]) for row in observed))
            image = axis.imshow(
                np.ma.masked_invalid(matrix),
                aspect="auto",
                interpolation="nearest",
                cmap=cmap,
                vmin=0.0,
                vmax=vmax,
            )
            colorbar = fig.colorbar(image, ax=axis, fraction=0.046, pad=0.03)
            colorbar.set_label("MiB", fontsize=8)
            colorbar.ax.tick_params(labelsize=7)
            for row_number in range(len(row_keys)):
                for column_number in range(len(contexts)):
                    value = matrix[row_number, column_number]
                    text = "NA" if np.isnan(value) else f"{value:,.0f}"
                    text_color = (
                        "#536372"
                        if np.isnan(value)
                        else "#FFFFFF"
                        if float(value) / vmax >= 0.58
                        else "#24313D"
                    )
                    axis.text(
                        column_number,
                        row_number,
                        text,
                        ha="center",
                        va="center",
                        fontsize=6.5,
                        color=text_color,
                    )
        else:
            axis.text(
                0.5,
                0.5,
                "GPU telemetry unavailable\nNA was not converted to zero",
                transform=axis.transAxes,
                ha="center",
                va="center",
                color="#666666",
            )
        prefix = "peak" if panel_index == 0 else "delta"
        integrity[f"{prefix}_plotted_point_count"] = len(observed)
        integrity[f"{prefix}_na_point_count"] = len(rows) - len(observed)
    fig.suptitle(
        f"E14 {model_scope}: observed GPU memory envelope",
        x=0.08,
        ha="left",
        fontsize=15,
    )
    fig.text(
        0.08,
        0.01,
        footer,
        ha="left",
        va="bottom",
        fontsize=8.5,
        color="#536372",
    )
    fig.tight_layout(rect=(0, 0.07, 1, 0.94))
    fig.savefig(png_path, dpi=180, bbox_inches="tight")
    fig.savefig(svg_path, format="svg", bbox_inches="tight")
    plt.close(fig)
    return integrity


def build_analysis(
    plan: dict[str, Any],
    job_records: Sequence[dict[str, Any]],
    metrics: Sequence[dict[str, Any]],
    statistics: dict[str, Any],
) -> str:
    performance_records = [record for record in job_records if record["job_type"] == "performance"]
    completed = sum(record["status"] == "completed" for record in performance_records)
    failed = [record for record in performance_records if record["status"] != "completed"]
    verification = "ANALYZED" if completed == plan["performance_job_count"] else "PARTIAL"
    warmup_enabled = bool(plan.get("warmup_enabled", False))
    warmup_conditions = [str(value) for value in plan.get("warmup_conditions", [])]
    warmup_job_count = int(plan.get("warmup_job_count", 0))
    warmup_case_run_count = int(plan.get("warmup_case_run_count", 0))
    if warmup_enabled:
        warmup_condition_label = "/".join(warmup_conditions)
        warmup_description = (
            f"- 暖机：每个 model×num_ctx 分别执行 {warmup_condition_label} 两个独立任务，"
            f"每个任务覆盖完整 {len(plan.get('case_ids', []))} 条代表案例；"
            f"共 {warmup_job_count} jobs / {warmup_case_run_count} case-runs，"
            "全部标记 excluded_from_metrics。"
        )
    else:
        warmup_description = "- 暖机：已通过 `--no-warmup` 禁用；没有暖机任务进入执行计划或指标。"
    lines = [
        "# E14 性能与资源实验",
        "",
        "## Material Passport",
        "",
        f"- Verification Status: `{verification}`",
        "- Source: local Ollama RunLog, E14 job records, and nvidia-smi snapshots",
        "- Evidence scope: dedicated representative performance matrix; not part of efficacy denominators",
        "- Backend: real-model `ollama` only",
        "",
        "## 执行完整性",
        "",
        f"- 计划性能 job：{plan['performance_job_count']}；完成：{completed}；失败/缺失：{len(failed)}。",
        f"- 网格：num_ctx={plan['num_ctx_values']}，并发={plan['concurrency_values']}，条件=off/full_guard。",
        warmup_description,
        "- 正式性能条件顺序交替，降低固定先后顺序偏差。",
        "- timeout、错误、缺失调用不会从计数中删除；无法定义的时延、吞吐、token 或显存保持 NA。",
        "",
        "## 分组指标",
        "",
        "| model | ctx | concurrency | condition | success/expected | median ms | p95 ms | throughput | Guard p95 ms | VRAM peak MiB | VRAM delta MiB |",
        "|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ]

    def show(value: Any, digits: int = 3) -> str:
        return "NA" if value is None else f"{float(value):.{digits}f}"

    for row in metrics:
        lines.append(
            "| {model} | {ctx} | {concurrency} | {condition} | {success}/{expected} | {median} | "
            "{p95} | {throughput} | {guard_p95} | {gpu} | {gpu_delta} |".format(
                model=row["model"],
                ctx=row["num_ctx"],
                concurrency=row["concurrency"],
                condition=row["condition"],
                success=row["successful_case_runs"],
                expected=row["expected_case_runs"],
                median=show(row["total_latency_median_ms"]),
                p95=show(row["total_latency_p95_ms"]),
                throughput=show(row["throughput_case_runs_per_s"], 5),
                guard_p95=show(row["guard_latency_p95_ms"]),
                gpu=show(row["gpu_peak_memory_mib"], 1),
                gpu_delta=show(row["gpu_memory_delta_mib"], 1),
            )
        )
    lines.extend(
        [
            "",
            "## 配对统计",
            "",
            "| model | ctx | concurrency | pairs | median overhead | p95 Guard ms | Wilcoxon p | Holm p | rank-biserial | targets |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for comparison in statistics["comparisons"]:
        test = comparison["total_latency_wilcoxon"]
        checks = comparison["target_checks"]
        lines.append(
            "| {model} | {ctx} | {concurrency} | {pairs} | {overhead}% | {guard_p95} | {p} | "
            "{holm} | {effect} | guard<10ms={guard_target}, total<10%={total_target} |".format(
                model=comparison["model"],
                ctx=comparison["num_ctx"],
                concurrency=comparison["concurrency"],
                pairs=comparison["paired_case_runs"],
                overhead=show(comparison["total_latency_overhead_percent"]["median"]),
                guard_p95=show(comparison["guard_latency_ms"]["p95"]),
                p=show(test.get("p_value"), 5),
                holm=show(test.get("holm_adjusted_p"), 5),
                effect=show(test.get("rank_biserial")),
                guard_target=checks["guard_p95_below_10ms"],
                total_target=checks["median_end_to_end_overhead_below_10pct"],
            )
        )
    lines.extend(
        [
            "",
            "统计检验同时报告效应量与区间；不以单个 p 值判定工程效果。跨 ctx/并发比较采用 Holm 校正。",
            "吞吐是完整 job 的成功 case-run/墙钟秒；job 不完整时为 NA，避免把崩溃误写成零吞吐。",
        ]
    )
    negative_overhead_cells = [
        comparison
        for comparison in statistics["comparisons"]
        if comparison["total_latency_overhead_percent"].get("median") is not None
        and float(comparison["total_latency_overhead_percent"]["median"]) < 0.0
    ]
    observed_prefix = (
        f"本次有 {len(negative_overhead_cells)} 个单元出现负的 median overhead；"
        if negative_overhead_cells
        else "方法解释："
    )
    lines.append(
        f"{observed_prefix}有符号端到端 overhead 比较的是 full_guard 与 off 的完整观测路径。"
        "负值可能包含分支、短路及其他路径差异，不是纯可加的 Guard overhead，"
        "也不能据此宣称 Guard 加速模型。"
    )

    anomaly = next(
        (
            comparison
            for comparison in statistics["comparisons"]
            if int(comparison["num_ctx"]) == 2048
            and int(comparison["concurrency"]) == 1
            and comparison["target_checks"].get("guard_p95_below_10ms") is False
        ),
        None,
    )
    if anomaly is not None:
        other_target_checks = [
            comparison["target_checks"].get("guard_p95_below_10ms")
            for comparison in statistics["comparisons"]
            if comparison is not anomaly
            and comparison["target_checks"].get("guard_p95_below_10ms") is not None
        ]
        passed_other_targets = sum(value is True for value in other_target_checks)
        guard_median = anomaly["guard_latency_ms"].get("median")
        guard_p95 = anomaly["guard_latency_ms"].get("p95")
        first_cell = (
            bool(plan.get("num_ctx_values"))
            and bool(plan.get("concurrency_values"))
            and int(plan["num_ctx_values"][0]) == 2048
            and int(plan["concurrency_values"][0]) == 1
        )
        cell_position = (
            "计划矩阵首个 ctx/c 单元（2048 tokens / c=1）"
            if first_cell
            else "2048 tokens / c=1 单元"
        )
        peer_evidence = (
            f"，其余 {passed_other_targets}/{len(other_target_checks)} 个可判定单元达到目标"
            if other_target_checks
            else ""
        )
        if warmup_enabled and "full_guard" in warmup_conditions:
            lines.append(
                f"Observed post-warmup tail anomaly：{cell_position}的 Guard p95={show(guard_p95)} ms"
                f"（median={show(guard_median)} ms）未达到 p95<10 ms 目标{peer_evidence}。"
                "该计划已在每个 model×num_ctx 上用完整代表集完成 Full Guard 独立暖机，"
                "因此不能仅依据执行位置把该尾部归因为冷启动；需要保留原始样本并单独复核。"
            )
        else:
            lines.append(
                f"Observed cold-start-like anomaly：{cell_position}的 Guard p95={show(guard_p95)} ms"
                f"（median={show(guard_median)} ms）未达到 p95<10 ms 目标{peer_evidence}。"
                "首单元尾部值远高于其中位数的孤立模式与冷启动样异常一致；"
                "这只是基于现有观测的模式推断，不能确认冷启动或任何具体机制造成该结果。"
            )
    lines.extend(["", "## 失败与限制", ""])
    if failed:
        for record in failed:
            tails = [line for lane in record.get("lanes", []) for line in lane.get("stderr_tail", [])]
            detail = tails[-1] if tails else "no stderr captured"
            lines.append(f"- `{record['id']}`: failed; `{detail}`")
    else:
        lines.append("- 没有失败的性能 job。")
    lines.extend(
        [
            "- 本实验测量本机当前 Ollama/GPU/驱动状态，不外推到其他硬件。",
            "- 并发 lane 共享同一 Ollama 服务与 GPU，结果反映系统级争用而非独立 GPU 性能。",
            "- VRAM peak 是 nvidia-smi 的设备级轮询峰值；delta 是峰值减去 job 前快照，不能归因为 Guard 的独占显存。",
            "- 图表只绘制相邻 CSV 中标为 observed 的值，NA 不替换成 0。",
            "",
        ]
    )
    return "\n".join(lines)


def _e14_implementation_sha256() -> str:
    """Hash the code paths that define E14 execution and post-processing."""

    paths = [ROOT / relative for relative in E14_IMPLEMENTATION_FILES]
    for relative in E14_IMPLEMENTATION_ROOTS:
        root = ROOT / relative
        if root.exists():
            paths.extend(
                path
                for path in root.rglob("*")
                if path.is_file()
                and "__pycache__" not in path.parts
                and path.suffix.lower() in {".py", ".json"}
            )
    digest = hashlib.sha256()
    for path in sorted(
        set(paths), key=lambda item: item.relative_to(ROOT).as_posix()
    ):
        if not path.is_file():
            raise FileNotFoundError(f"E14 implementation input missing: {path}")
        digest.update(path.relative_to(ROOT).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _configuration(
    *,
    cases_path: Path,
    plan: dict[str, Any],
    seed: int,
    temperature: float,
    max_tokens: int,
    max_steps: int,
    request_timeout_seconds: float,
    lane_timeout_seconds: float,
    gpu_poll_seconds: float,
    ask_threshold: float,
    deny_threshold: float,
) -> dict[str, Any]:
    stable = {
        "cases": str(cases_path.resolve()),
        "dataset_sha256": sha256_file(cases_path),
        "sandbox_runtime_version": SANDBOX_RUNTIME_VERSION,
        "implementation_sha256": _e14_implementation_sha256(),
        "plan": plan,
        "seed": int(seed),
        "temperature": float(temperature),
        "max_tokens": int(max_tokens),
        "max_steps": int(max_steps),
        "request_timeout_seconds": float(request_timeout_seconds),
        "lane_timeout_seconds": float(lane_timeout_seconds),
        "gpu_poll_seconds": float(gpu_poll_seconds),
        "ask_threshold": float(ask_threshold),
        "deny_threshold": float(deny_threshold),
    }
    return {**stable, "config_hash": _json_hash(stable)}


def _new_e14_manifest(
    cases_path: Path,
    plan: dict[str, Any],
    configuration: dict[str, Any],
    command: Sequence[str],
) -> dict[str, Any]:
    manifest = new_manifest(
        "E14",
        dataset_paths=[cases_path],
        configuration=configuration,
        expected_runs=int(plan["performance_job_count"]),
        models=plan["models"],
        command=list(command),
    )
    manifest["sandbox_runtime_version"] = configuration["sandbox_runtime_version"]
    manifest["implementation_sha256"] = configuration["implementation_sha256"]
    manifest["jobs"] = [
        {
            **job,
            "status": "pending",
            "attempts": 0,
            "last_error": None,
        }
        for job in plan["jobs"]
    ]
    return manifest


def _manifest_job(manifest: dict[str, Any], job_id: str) -> dict[str, Any]:
    return next(job for job in manifest["jobs"] if job["id"] == job_id)


def _register_outputs(manifest: dict[str, Any], outputs: Sequence[tuple[Path, str]]) -> None:
    for path, kind in outputs:
        register_artifact(manifest, path, kind=kind)


def _build_outputs(
    output_dir: Path,
    plan: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], list[tuple[Path, str]]]:
    job_records, raw_rows, gpu_rows = collect_evidence(output_dir, plan)
    case_records = build_case_run_records(raw_rows)
    metrics = build_performance_metrics(plan, job_records, case_records)
    statistics = build_statistics(plan, case_records, metrics)
    latency_rows, throughput_rows = build_chart_data(metrics)
    gpu_memory_rows = build_gpu_chart_data(metrics)

    raw_path = output_dir / "raw_runs.jsonl"
    gpu_path = output_dir / "gpu_snapshots.jsonl"
    jobs_path = output_dir / "job_records.jsonl"
    performance_path = output_dir / "performance.csv"
    metrics_csv_path = output_dir / "metrics.csv"
    metrics_json_path = output_dir / "metrics.json"
    statistics_path = output_dir / "statistics.json"
    analysis_path = output_dir / "analysis.md"
    latency_csv = output_dir / "latency_by_context_data.csv"
    latency_png = output_dir / "latency_by_context.png"
    latency_svg = output_dir / "latency_by_context.svg"
    throughput_csv = output_dir / "throughput_by_concurrency_data.csv"
    throughput_png = output_dir / "throughput_by_concurrency.png"
    throughput_svg = output_dir / "throughput_by_concurrency.svg"
    gpu_memory_csv = output_dir / "gpu_memory_by_context_data.csv"
    gpu_memory_png = output_dir / "gpu_memory_by_context.png"
    gpu_memory_svg = output_dir / "gpu_memory_by_context.svg"

    _write_jsonl(raw_path, raw_rows)
    _write_jsonl(gpu_path, gpu_rows)
    _write_jsonl(jobs_path, job_records)
    _write_csv(performance_path, metrics, PERFORMANCE_FIELDS)
    _write_csv(metrics_csv_path, metrics, PERFORMANCE_FIELDS)
    _write_json(
        metrics_json_path,
        {
            "schema_version": "1.0",
            "experiment_id": "E14",
            "undefined_policy": "missing values remain null/NA",
            "rows": metrics,
        },
    )
    _write_json(statistics_path, statistics)
    _write_csv(latency_csv, latency_rows, LATENCY_CHART_FIELDS)
    _write_csv(throughput_csv, throughput_rows, THROUGHPUT_CHART_FIELDS)
    _write_csv(gpu_memory_csv, gpu_memory_rows, GPU_MEMORY_CHART_FIELDS)
    latency_integrity = _render_chart(
        latency_rows, chart="latency", png_path=latency_png, svg_path=latency_svg
    )
    throughput_integrity = _render_chart(
        throughput_rows,
        chart="throughput",
        png_path=throughput_png,
        svg_path=throughput_svg,
    )
    gpu_memory_integrity = _render_gpu_memory_chart(
        gpu_memory_rows,
        png_path=gpu_memory_png,
        svg_path=gpu_memory_svg,
    )
    statistics["chart_integrity"] = {
        "latency": latency_integrity,
        "throughput": throughput_integrity,
        "gpu_memory": gpu_memory_integrity,
    }
    _write_json(statistics_path, statistics)
    analysis_path.write_text(
        build_analysis(plan, job_records, metrics, statistics), encoding="utf-8"
    )
    figure_manifest_path = write_figure_manifest(
        output_dir,
        experiment_id="E14",
        evidence_tier="formal_dedicated",
        figures=[
            {
                "id": "latency_by_context",
                "title": "E14 end-to-end latency by context window",
                "role": "primary",
                "order": 0,
                "chart_type": "multi_series_line",
                "caption": (
                    "Observed median end-to-end latency by context, concurrency, model, and "
                    "condition; adjacent data also retains p95 and NA status."
                ),
                "files": {
                    "data": latency_csv.name,
                    "png": latency_png.name,
                    "svg": latency_svg.name,
                },
                "metrics": ["median_total_latency_ms", "p95_total_latency_ms"],
                "grain": ["model", "num_ctx", "concurrency", "condition"],
                "uncertainty": [
                    {
                        "method": "descriptive median and p95",
                        "confidence_interval": False,
                        "note": "p95 is a tail summary, not a confidence interval",
                    }
                ],
                "warnings": [
                    "Only complete observed values are plotted; failed, timeout, and missing rows remain NA in the adjacent CSV.",
                    "Dedicated E14 performance matrix; do not combine with efficacy denominators.",
                ],
            },
            {
                "id": "throughput_by_concurrency",
                "title": "E14 successful throughput by concurrency",
                "role": "secondary",
                "order": 1,
                "chart_type": "multi_series_line",
                "caption": (
                    "Successful case-runs per wall-clock second for complete jobs across "
                    "concurrency settings."
                ),
                "files": {
                    "data": throughput_csv.name,
                    "png": throughput_png.name,
                    "svg": throughput_svg.name,
                },
                "metrics": ["throughput_case_runs_per_s"],
                "grain": ["model", "num_ctx", "concurrency", "condition"],
                "uncertainty": [
                    {
                        "method": "none",
                        "reason": "single complete-job wall-clock estimate; no inferential interval",
                    }
                ],
                "warnings": [
                    "Incomplete jobs remain NA rather than being represented as zero throughput.",
                    "Concurrent lanes share the same Ollama service and GPU.",
                ],
            },
            {
                "id": "gpu_vram_peak_delta",
                "title": "E14 observed GPU memory peak and delta",
                "role": "secondary",
                "order": 2,
                "chart_type": "two_panel_heatmap",
                "caption": (
                    "Device-wide VRAM peak and peak-minus-before delta by context, model, "
                    "concurrency, and condition."
                ),
                "files": {
                    "data": gpu_memory_csv.name,
                    "png": gpu_memory_png.name,
                    "svg": gpu_memory_svg.name,
                },
                "metrics": ["gpu_peak_memory_mib", "gpu_memory_delta_mib", "gpu_sample_count"],
                "grain": ["job_id", "model", "num_ctx", "concurrency", "condition"],
                "uncertainty": [
                    {
                        "method": "none",
                        "reason": "polled job-level telemetry summary; no inferential interval",
                        "sampling": "before, periodic while running, and after",
                    }
                ],
                "warnings": [
                    "nvidia-smi reports device-wide memory, not model- or Guard-exclusive allocation.",
                    "Polling can miss transient peaks between samples.",
                    "Delta is observed peak minus the pre-job snapshot and must not be interpreted as causal Guard overhead.",
                    "Unavailable telemetry remains NA and is not plotted.",
                ],
            },
        ],
    )
    outputs = [
        (raw_path, "raw_log"),
        (gpu_path, "resource_log"),
        (jobs_path, "job_log"),
        (performance_path, "metrics"),
        (metrics_csv_path, "metrics"),
        (metrics_json_path, "metrics"),
        (statistics_path, "statistics"),
        (analysis_path, "analysis"),
        (latency_csv, "figure_data"),
        (latency_png, "figure"),
        (latency_svg, "figure"),
        (throughput_csv, "figure_data"),
        (throughput_png, "figure"),
        (throughput_svg, "figure"),
        (gpu_memory_csv, "figure_data"),
        (gpu_memory_png, "figure"),
        (gpu_memory_svg, "figure"),
        (figure_manifest_path, "figure_manifest"),
    ]
    return job_records, metrics, statistics, outputs


def run_e14(
    output_dir: str | Path = DEFAULT_OUT_DIR,
    *,
    cases_path: str | Path = DEFAULT_CASES,
    models: Sequence[str] = (CORE_MODELS[0],),
    contexts: Sequence[int] = CONTEXT_LENGTHS,
    concurrencies: Sequence[int] = PERFORMANCE_CONCURRENCY,
    repeats: int = 1,
    warmup: bool = True,
    plan_only: bool = False,
    resume: bool = False,
    seed: int = 42,
    temperature: float = 0.0,
    max_tokens: int = 256,
    max_steps: int = 3,
    request_timeout_seconds: float = 120.0,
    lane_timeout_seconds: float = 1800.0,
    gpu_poll_seconds: float = 1.0,
    ask_threshold: float = 0.35,
    deny_threshold: float = 0.65,
    command: Sequence[str] = (),
    lane_executor: Callable[[dict[str, Any]], dict[str, Any]] = subprocess_lane_executor,
    gpu_provider: Callable[[], dict[str, Any]] = gpu_snapshot,
    inventory_provider: Callable[[], dict[str, dict[str, str]]] = installed_models,
    model_stopper: Callable[[str], None] = stop_model,
) -> dict[str, Any]:
    """Plan or execute E14. Formal execution always uses the Ollama backend."""

    if not 0.0 <= ask_threshold <= deny_threshold <= 1.0:
        raise ValueError("require 0 <= ask_threshold <= deny_threshold <= 1")
    if min(request_timeout_seconds, lane_timeout_seconds, gpu_poll_seconds) <= 0.0:
        raise ValueError("timeouts and GPU polling interval must be positive")
    out = Path(output_dir)
    cases_file = Path(cases_path)
    cases = load_representative_cases(cases_file)
    plan = build_execution_plan(
        cases,
        models=models,
        contexts=contexts,
        concurrencies=concurrencies,
        repeats=repeats,
        warmup=warmup,
    )
    configuration = _configuration(
        cases_path=cases_file,
        plan=plan,
        seed=seed,
        temperature=temperature,
        max_tokens=max_tokens,
        max_steps=max_steps,
        request_timeout_seconds=request_timeout_seconds,
        lane_timeout_seconds=lane_timeout_seconds,
        gpu_poll_seconds=gpu_poll_seconds,
        ask_threshold=ask_threshold,
        deny_threshold=deny_threshold,
    )
    out.mkdir(parents=True, exist_ok=True)
    manifest_path = out / "manifest.json"
    plan_path = out / "execution_plan.json"

    planned_transition = False
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        existing_configuration = manifest.get("configuration", {})
        for field in E14_RESUME_IDENTITY_FIELDS:
            if existing_configuration.get(field) != configuration.get(field):
                raise RuntimeError(f"Refusing E14 resume: {field} changed")
            if manifest.get(field) != existing_configuration.get(field):
                raise RuntimeError(
                    f"Refusing E14 resume: top-level {field} provenance mismatch"
                )
        existing_hash = existing_configuration.get("config_hash")
        if existing_hash != configuration["config_hash"]:
            raise RuntimeError("Refusing E14 resume: configuration hash changed")
        planned_transition = manifest.get("status") == "planned" and not plan_only
        if not resume and manifest.get("status") != "planned" and not plan_only:
            raise FileExistsError("E14 manifest exists; pass --resume to continue")
    else:
        manifest = _new_e14_manifest(cases_file, plan, configuration, command)

    # Validate an existing manifest before touching its durable plan.  A
    # rejected configuration drift must leave both artifacts byte-identical.
    _write_json(plan_path, plan)
    register_artifact(manifest, plan_path, kind="execution_plan")

    if plan_only:
        manifest["status"] = "planned"
        manifest["progress"] = {
            "expected_runs": plan["performance_job_count"],
            "completed_runs": sum(
                job.get("status") == "completed" and job.get("job_type") == "performance"
                for job in manifest["jobs"]
            ),
            "failed_jobs": sum(job.get("status") == "failed" for job in manifest["jobs"]),
            "unresolved_cases": 0,
        }
        record_event(manifest, "planned", "E14 plan-only manifest generated")
        save_manifest(manifest, manifest_path)
        return manifest

    # A plan-only manifest transitions directly to running. Other interrupted
    # manifests require the explicit resume flag checked above.
    if planned_transition:
        # The plan manifest captures planning provenance.  The first formal
        # transition must replace that with the actual execution invocation
        # and environment while preserving created_at, configuration and jobs.
        manifest["command"] = list(command)
        manifest["git"] = manifest_helpers.git_state()
        manifest["environment"] = manifest_helpers.environment_snapshot()
        record_event(
            manifest,
            "formal_started",
            "E14 formal execution started from planned manifest",
        )
    manifest["status"] = "running"
    manifest["failure"] = None
    if resume:
        record_event(manifest, "resumed", "explicit E14 resume requested")
    save_manifest(manifest, manifest_path)

    try:
        installed = inventory_provider()
        missing = [model for model in plan["models"] if model not in installed]
        if missing:
            raise RuntimeError(f"required E14 model(s) are not installed: {missing}")
    except Exception as exc:
        fail_manifest(manifest, category="preflight", message=str(exc))
        save_manifest(manifest, manifest_path)
        raise

    # A completed entry is trusted only while its durable job record exists.
    for job in plan["jobs"]:
        entry = _manifest_job(manifest, str(job["id"]))
        record_path = out / "work" / str(job["id"]) / "job_record.json"
        if entry.get("status") == "completed" and not record_path.exists():
            entry["status"] = "pending"
            entry["last_error"] = "completed job record missing during resume audit"

    lifecycle_errors: list[str] = []
    for model in plan["models"]:
        try:
            for job in (item for item in plan["jobs"] if item["model"] == model):
                entry = _manifest_job(manifest, str(job["id"]))
                if entry.get("status") == "completed":
                    continue
                if entry.get("status") == "failed" and not resume:
                    continue
                entry["status"] = "running"
                entry["attempts"] = int(entry.get("attempts", 0)) + 1
                entry["started_at"] = utc_now()
                entry["last_error"] = None
                save_manifest(manifest, manifest_path)
                try:
                    result = execute_job(
                        job,
                        output_dir=out,
                        cases_path=cases_file,
                        resume=resume or entry["attempts"] > 1,
                        seed=seed,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        max_steps=max_steps,
                        request_timeout_seconds=request_timeout_seconds,
                        lane_timeout_seconds=lane_timeout_seconds,
                        gpu_poll_seconds=gpu_poll_seconds,
                        ask_threshold=ask_threshold,
                        deny_threshold=deny_threshold,
                        lane_executor=lane_executor,
                        gpu_provider=gpu_provider,
                    )
                    record = result["record"]
                    entry["status"] = record["status"]
                    entry["completed_at"] = utc_now()
                    entry["wall_seconds"] = record["wall_seconds"]
                    entry["gpu_peak_memory_mib"] = record["gpu_peak_memory_mib"]
                    if record["status"] != "completed":
                        tails = [
                            line
                            for lane in record.get("lanes", [])
                            for line in lane.get("stderr_tail", [])
                        ]
                        entry["last_error"] = tails[-1] if tails else "lane failed without stderr"
                except Exception as exc:
                    entry["status"] = "failed"
                    entry["completed_at"] = utc_now()
                    entry["last_error"] = f"{type(exc).__name__}: {exc}"
                    job_dir = out / "work" / str(job["id"])
                    job_dir.mkdir(parents=True, exist_ok=True)
                    _write_json(
                        job_dir / "job_record.json",
                        {
                            "schema_version": "1.0",
                            **job,
                            "status": "failed",
                            "wall_seconds": None,
                            "lanes": [],
                            "gpu_sample_count": 0,
                            "gpu_peak_memory_mib": None,
                            "gpu_memory_delta_mib": None,
                            "timed_out": isinstance(exc, TimeoutError),
                            "error_count": 1,
                            "error": entry["last_error"],
                        },
                    )
                    _write_jsonl(job_dir / "raw_runs.jsonl", [])
                    _write_jsonl(job_dir / "gpu_snapshots.jsonl", [])
                save_manifest(manifest, manifest_path)
        finally:
            try:
                model_stopper(model)
                record_event(manifest, "model_stopped", f"released model {model}")
            except Exception as exc:
                message = f"{model}: {type(exc).__name__}: {exc}"
                lifecycle_errors.append(message)
                record_event(manifest, "model_stop_failed", message)
            save_manifest(manifest, manifest_path)

    try:
        job_records, metrics, statistics, outputs = _build_outputs(out, plan)
    except Exception as exc:
        # Model jobs are durable before aggregation starts.  Persist a distinct
        # post-processing failure so an explicit --resume can rebuild every
        # aggregate from the complete raw job set without rerunning or silently
        # dropping any condition.
        performance_entries = [
            job for job in manifest["jobs"] if job["job_type"] == "performance"
        ]
        completed_count = sum(
            job.get("status") == "completed" for job in performance_entries
        )
        manifest["progress"] = {
            "expected_runs": plan["performance_job_count"],
            "completed_runs": completed_count,
            "failed_jobs": 1,
            "unresolved_cases": 0,
        }
        message = f"{type(exc).__name__}: {exc}"
        fail_manifest(manifest, category="postprocessing_failure", message=message)
        record_event(
            manifest,
            "postprocessing_failed",
            message,
            completed_performance_jobs=completed_count,
        )
        save_manifest(manifest, manifest_path)
        raise
    _register_outputs(manifest, outputs)
    performance_entries = [
        job for job in manifest["jobs"] if job["job_type"] == "performance"
    ]
    failed_entries = [job for job in manifest["jobs"] if job.get("status") != "completed"]
    completed_count = sum(job.get("status") == "completed" for job in performance_entries)
    unresolved_cases = sum(int(row["missing_case_runs"]) for row in metrics)
    manifest["progress"] = {
        "expected_runs": plan["performance_job_count"],
        "completed_runs": completed_count,
        "failed_jobs": len(failed_entries) + len(lifecycle_errors),
        "unresolved_cases": unresolved_cases,
    }
    manifest["lifecycle_errors"] = lifecycle_errors
    if not failed_entries and not lifecycle_errors and completed_count == plan["performance_job_count"]:
        finish_manifest(
            manifest,
            completed_runs=completed_count,
            failed_jobs=0,
            unresolved_cases=unresolved_cases,
        )
    else:
        manifest["status"] = "failed"
        manifest["completed_at"] = utc_now()
        manifest["failure"] = {
            "category": "job_failure",
            "message": (
                f"{len(failed_entries)} jobs and {len(lifecycle_errors)} lifecycle actions failed; "
                "partial metrics retain NA values"
            ),
            "at": utc_now(),
        }
        record_event(manifest, "failed", manifest["failure"]["message"])
    save_manifest(manifest, manifest_path)
    return manifest


def _csv_values(value: str, cast: Callable[[str], Any] = str) -> list[Any]:
    return [cast(item.strip()) for item in str(value).split(",") if item.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--models", default=CORE_MODELS[0])
    parser.add_argument("--num-ctx", default=",".join(str(value) for value in CONTEXT_LENGTHS))
    parser.add_argument(
        "--concurrency", default=",".join(str(value) for value in PERFORMANCE_CONCURRENCY)
    )
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=256)
    parser.add_argument("--max-steps", type=int, default=3)
    parser.add_argument("--request-timeout", type=float, default=120.0)
    parser.add_argument("--lane-timeout", type=float, default=1800.0)
    parser.add_argument("--gpu-poll-seconds", type=float, default=1.0)
    parser.add_argument("--ask-threshold", type=float, default=0.35)
    parser.add_argument("--deny-threshold", type=float, default=0.65)
    parser.add_argument("--no-warmup", action="store_true")
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--resume", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    actual_argv = list(argv) if argv is not None else sys.argv[1:]
    command = [sys.executable, "-m", "experiments.e14_performance", *actual_argv]
    manifest = run_e14(
        args.out_dir,
        cases_path=args.cases,
        models=_csv_values(args.models),
        contexts=_csv_values(args.num_ctx, int),
        concurrencies=_csv_values(args.concurrency, int),
        repeats=args.repeats,
        warmup=not args.no_warmup,
        plan_only=args.plan_only,
        resume=args.resume,
        seed=args.seed,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        max_steps=args.max_steps,
        request_timeout_seconds=args.request_timeout,
        lane_timeout_seconds=args.lane_timeout,
        gpu_poll_seconds=args.gpu_poll_seconds,
        ask_threshold=args.ask_threshold,
        deny_threshold=args.deny_threshold,
        command=command,
    )
    print(
        json.dumps(
            {"manifest": str(args.out_dir / "manifest.json"), "status": manifest["status"]},
            ensure_ascii=False,
        )
    )
    return 0 if manifest["status"] in {"planned", "completed"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
