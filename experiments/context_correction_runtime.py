"""Shared execution primitives for context-correction experiment runners."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .manifest import sha256_file
from .model_manager import gpu_snapshot, ollama_ps_snapshot


ROOT = Path(__file__).resolve().parents[1]

EXPECTED_FREEZE_PATHS = (
    "protocols/context_correction_v2/protocol.md",
    "protocols/context_correction_v2/protocol.json",
    "protocols/context_correction_v2/calibration_r2.json",
    "protocols/context_correction_v2/prompt_verification_r2.json",
    "protocols/context_correction_v2/fixtures/e9_cases.jsonl",
    "protocols/context_correction_v2/fixtures/e14_cases_r2.jsonl",
    "agent/audits/context_experiment_validity.json",
    "experiments/catalog.py",
    "experiments/manifest.py",
    "experiments/model_manager.py",
    "experiments/context_workloads.py",
    "experiments/context_correction_runtime.py",
    "experiments/e9_context_correction.py",
    "experiments/e14_context_correction.py",
    "experiments/modelfiles/Qwen3-4B-Ctx4K.Modelfile",
    "experiments/modelfiles/Qwen3-4B-Ctx8K.Modelfile",
    "experiments/modelfiles/Qwen3-4B-Ctx16K.Modelfile",
    "experiments/modelfiles/Qwen3-4B-Ctx32K.Modelfile",
    "m3_core/agent_runner.py",
    "m3_core/case_views.py",
    "m3_core/llm_client.py",
    "m3_core/run_batch.py",
    "m3_core/run_matrix.py",
    "m3_core/tool_sandbox.py",
    "m3_eval/figure_manifest.py",
    "m3_eval/metrics.py",
    "m3_eval/statistics.py",
    "m3_guard/__init__.py",
    "m3_guard/config.py",
    "m3_guard/dataflow.py",
    "m3_guard/detector.py",
    "m3_guard/guard_engine.py",
    "m3_guard/normalizer.py",
    "m3_guard/policy_engine.py",
    "schemas/attack_case.schema.json",
    "schemas/run_log.schema.json",
    "schemas/tool_call.schema.json",
    "tests/unit/test_context_workloads.py",
    "tests/unit/test_context_correction_runtime.py",
    "tests/unit/test_e9_context_correction.py",
    "tests/unit/test_e14_context_correction.py",
    "tests/unit/test_core_runtime.py",
    "tests/unit/test_core_batch.py",
    "tests/unit/test_run_sandbox_isolation.py",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    source = Path(path)
    if not source.exists():
        return rows
    with source.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            stripped = line.strip()
            if not stripped:
                continue
            value = json.loads(stripped)
            if not isinstance(value, dict):
                raise ValueError(f"expected object at {source}:{line_number}")
            rows.append(value)
    return rows


def write_json(path: str | Path, value: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: str | Path, rows: Iterable[Mapping[str, Any]]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "".join(
            json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def file_record(path: str | Path, *, kind: str) -> dict[str, Any]:
    target = Path(path)
    return {
        "path": str(target),
        "kind": kind,
        "bytes": target.stat().st_size,
        "sha256": sha256_file(target),
    }


def stable_json_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def semantic_failure_progress(
    *,
    expected_runs: int,
    completed_runs: int,
    failed_jobs: int,
    unresolved_cases: int,
) -> dict[str, Any]:
    """Represent a semantic-gate failure without inventing a failed job."""

    return {
        "expected_runs": int(expected_runs),
        "completed_runs": int(completed_runs),
        "failed_jobs": int(failed_jobs),
        "unresolved_cases": int(unresolved_cases),
        "semantic_status": "fail",
    }


def partition_case_ids(case_ids: Sequence[str], concurrency: int) -> list[list[str]]:
    if concurrency < 1:
        raise ValueError("concurrency must be positive")
    lanes = [[] for _ in range(concurrency)]
    for index, case_id in enumerate(case_ids):
        lanes[index % concurrency].append(str(case_id))
    return [lane for lane in lanes if lane]


def max_interval_overlap(intervals: Sequence[tuple[float, float]]) -> int:
    events: list[tuple[float, int]] = []
    for started, ended in intervals:
        events.append((started, 1))
        events.append((ended, -1))
    # Starts sort before ends at the same timestamp so immediate handoff does
    # not understate offered overlap.
    events.sort(key=lambda item: (item[0], -item[1]))
    active = peak = 0
    for _, delta in events:
        active += delta
        peak = max(peak, active)
    return peak


def _case_run_overlap(rows: Sequence[Mapping[str, Any]]) -> int:
    """Measure overlap of complete case-run intervals from durable timestamps."""

    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row.get("run_key", "")), []).append(row)
    intervals: list[tuple[float, float]] = []
    for run_key, run_rows in grouped.items():
        if not run_key:
            continue
        try:
            start = min(
                datetime.fromisoformat(str(row["started_at"])).timestamp()
                for row in run_rows
                if row.get("started_at")
            )
            end = max(
                datetime.fromisoformat(str(row["completed_at"])).timestamp()
                for row in run_rows
                if row.get("completed_at")
            )
        except (ValueError, TypeError):
            continue
        if end >= start:
            intervals.append((start, end))
    return max_interval_overlap(intervals)


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in "-_" else "_" for char in value)


def _run_lane(
    *,
    job: Mapping[str, Any],
    lane_id: int,
    case_ids: Sequence[str],
    cases_path: Path,
    job_dir: Path,
    resume: bool,
    max_steps: int,
    max_tokens: int,
    timeout_seconds: float,
    lane_timeout_seconds: float,
    temperature: float,
    seed: int,
    ask_threshold: float,
    deny_threshold: float,
) -> dict[str, Any]:
    lane_dir = job_dir / f"lane_{lane_id}"
    lane_dir.mkdir(parents=True, exist_ok=True)
    condition_id = str(job["condition_id"])
    run_prefix = f"{_safe_name(str(job['id']))}_lane{lane_id}"
    command = [
        sys.executable,
        "-m",
        "m3_core.run_matrix",
        "--cases",
        str(cases_path),
        "--backend",
        "ollama",
        "--model",
        str(job["served_model"]),
        "--ollama-transport",
        "native",
        "--conditions",
        f"{condition_id}={job['prompt_profile']}:{job['guard_mode']}",
        "--case-ids",
        ",".join(case_ids),
        "--out-dir",
        str(lane_dir),
        "--max-steps",
        str(int(max_steps)),
        "--run-prefix",
        run_prefix,
        "--run-group",
        str(job.get("run_group") or "CONTEXT_CORRECTION_V2"),
        "--seed",
        str(int(seed)),
        "--selection-seed",
        str(int(seed)),
        "--generation-seed",
        str(int(seed)),
        "--repeats",
        "1",
        "--temperature",
        str(float(temperature)),
        "--max-tokens",
        str(int(max_tokens)),
        "--timeout",
        str(float(timeout_seconds)),
        "--ask-threshold",
        str(float(ask_threshold)),
        "--deny-threshold",
        str(float(deny_threshold)),
        "--notes",
        str(job.get("notes") or "context correction formal lane"),
    ]
    if resume and (lane_dir / "manifest.json").exists():
        command.append("--resume")
    stdout_path = lane_dir / "stdout.log"
    stderr_path = lane_dir / "stderr.log"
    started_wall = utc_now()
    started = time.perf_counter()
    timed_out = False
    exit_code: int | None
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=float(lane_timeout_seconds),
            check=False,
        )
        exit_code = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        exit_code = None
        stdout = str(exc.stdout or "")
        stderr = str(exc.stderr or "") + "\nLANE_TIMEOUT"
    ended = time.perf_counter()
    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")
    manifest_path = lane_dir / "manifest.json"
    matrix_manifest = (
        json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest_path.exists()
        else {}
    )
    raw_paths: list[Path] = []
    for result in matrix_manifest.get("results", []):
        value = Path(str(result.get("jsonl", "")))
        raw_paths.append(value if value.is_absolute() else ROOT / value)
    raw_rows = [row for path in raw_paths for row in read_jsonl(path)]
    status = "completed" if (
        exit_code == 0
        and not timed_out
        and matrix_manifest.get("status") == "completed"
        and raw_paths
        and all(path.exists() for path in raw_paths)
    ) else "failed"
    return {
        "lane_id": lane_id,
        "case_ids": list(case_ids),
        "status": status,
        "started_at": started_wall,
        "completed_at": utc_now(),
        "started_perf": started,
        "completed_perf": ended,
        "wall_seconds": ended - started,
        "exit_code": exit_code,
        "timed_out": timed_out,
        "command": command,
        "manifest_path": str(manifest_path),
        "manifest_status": matrix_manifest.get("status"),
        "raw_paths": [str(path) for path in raw_paths],
        "raw_rows": raw_rows,
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "stderr_tail": stderr.splitlines()[-50:],
    }


def execute_matrix_job(
    job: Mapping[str, Any],
    *,
    cases_path: str | Path,
    output_dir: str | Path,
    resume: bool = False,
    max_steps: int = 3,
    max_tokens: int = 256,
    timeout_seconds: float = 600.0,
    lane_timeout_seconds: float = 3600.0,
    temperature: float = 0.2,
    seed: int = 419,
    ask_threshold: float = 0.35,
    deny_threshold: float = 0.65,
    capture_telemetry: bool = False,
    telemetry_poll_seconds: float = 0.5,
    prompt_verification: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    """Run one condition/cell with independently offered client lanes."""

    job_dir = Path(output_dir) / "work" / str(job["id"])
    job_dir.mkdir(parents=True, exist_ok=True)
    groups = partition_case_ids(job["case_ids"], int(job.get("concurrency", 1)))
    started_at = utc_now()
    job_started = time.perf_counter()
    lane_results: list[dict[str, Any]] = []
    telemetry: list[dict[str, Any]] = []
    if capture_telemetry:
        telemetry.append(
            {
                "phase": "before",
                "gpu": gpu_snapshot(),
                "ollama_ps": ollama_ps_snapshot(),
            }
        )
    with ThreadPoolExecutor(max_workers=len(groups)) as executor:
        futures = {
            executor.submit(
                _run_lane,
                job=job,
                lane_id=lane_id,
                case_ids=case_ids,
                cases_path=Path(cases_path),
                job_dir=job_dir,
                resume=resume,
                max_steps=max_steps,
                max_tokens=max_tokens,
                timeout_seconds=timeout_seconds,
                lane_timeout_seconds=lane_timeout_seconds,
                temperature=temperature,
                seed=seed,
                ask_threshold=ask_threshold,
                deny_threshold=deny_threshold,
            ): lane_id
            for lane_id, case_ids in enumerate(groups)
        }
        pending = set(futures)
        while pending:
            done, pending = wait(
                pending,
                timeout=max(0.05, float(telemetry_poll_seconds)),
                return_when=FIRST_COMPLETED,
            )
            if capture_telemetry:
                telemetry.append(
                    {
                        "phase": "running" if pending else "after",
                        "gpu": gpu_snapshot(),
                        "ollama_ps": ollama_ps_snapshot(),
                    }
                )
            for future in done:
                lane_results.append(future.result())
    lane_results.sort(key=lambda item: int(item["lane_id"]))
    intervals = [
        (float(lane["started_perf"]), float(lane["completed_perf"]))
        for lane in lane_results
    ]
    lane_process_overlap = max_interval_overlap(intervals)
    lane_envelope_seconds = (
        max(end for _, end in intervals) - min(start for start, _ in intervals)
        if intervals
        else 0.0
    )
    raw_rows: list[dict[str, Any]] = []
    for lane in lane_results:
        for row in lane.pop("raw_rows"):
            is_first_step = int(row.get("step") or 0) == 1
            verified_prompt_count = (
                int(prompt_verification[str(row.get("case_id"))])
                if is_first_step
                and prompt_verification is not None
                and str(row.get("case_id")) in prompt_verification
                else None
            )
            raw_rows.append(
                {
                    **row,
                    "correction_protocol_id": job.get("protocol_id"),
                    "correction_workload_revision": job.get("workload_revision"),
                    "correction_job_id": job["id"],
                    "correction_job_type": job.get("job_type"),
                    "workload_cohort": job.get("workload_cohort"),
                    "condition_id": job.get("condition_id"),
                    "prompt_profile": job.get("prompt_profile"),
                    "guard_mode": job.get("guard_mode"),
                    "target_prompt_tokens": int(job["target_prompt_tokens"]),
                    "served_model": job["served_model"],
                    "base_model": job.get("base_model", "qwen3:4b-instruct"),
                    "effective_context_window_tokens": int(
                        job["effective_context_window_tokens"]
                    ),
                    "offered_concurrency": int(job.get("concurrency", 1)),
                    "observed_lane_process_overlap": lane_process_overlap,
                    "outer_replicate_id": int(job.get("outer_replicate_id", 0)),
                    "calibrated_prompt_eval_count": verified_prompt_count,
                    "prompt_count_evidence": (
                        "formal_provider"
                        if row.get("prompt_eval_count") is not None
                        else "frozen_one_token_preflight"
                        if verified_prompt_count is not None
                        else "missing"
                    ),
                    "job_wall_seconds": lane_envelope_seconds,
                }
            )
    observed_case_run_overlap = _case_run_overlap(raw_rows)
    for row in raw_rows:
        row["observed_case_run_overlap"] = observed_case_run_overlap
    expected = int(job["expected_case_runs"])
    first_step = [row for row in raw_rows if int(row.get("step") or 0) == 1]
    run_keys = [str(row.get("run_key", "")) for row in first_step]
    complete = (
        all(lane["status"] == "completed" for lane in lane_results)
        and len(first_step) == expected
        and len(set(run_keys)) == expected
        and all(run_keys)
    )
    raw_path = job_dir / "raw_runs.jsonl"
    telemetry_path = job_dir / "telemetry.jsonl"
    write_jsonl(raw_path, raw_rows)
    write_jsonl(telemetry_path, telemetry)
    record = {
        **dict(job),
        "status": "completed" if complete else "failed",
        "started_at": started_at,
        "completed_at": utc_now(),
        "wall_seconds": lane_envelope_seconds,
        "orchestration_wall_seconds": time.perf_counter() - job_started,
        "observed_case_runs": len(first_step),
        "duplicate_run_keys": len(run_keys) - len(set(run_keys)),
        "observed_max_inflight": observed_case_run_overlap,
        "observed_case_run_overlap": observed_case_run_overlap,
        "observed_lane_process_overlap": lane_process_overlap,
        "lane_count": len(lane_results),
        "lanes": lane_results,
        "raw_path": str(raw_path),
        "raw_sha256": sha256_file(raw_path),
        "telemetry_path": str(telemetry_path),
        "telemetry_sha256": sha256_file(telemetry_path),
        "telemetry_sample_count": len(telemetry),
    }
    write_json(job_dir / "job_record.json", record)
    return record


def first_step_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows if int(row.get("step") or 0) == 1]


def effective_prompt_eval_count(row: Mapping[str, Any]) -> int | None:
    """Return raw usage, or the frozen proof for an exact first-turn only."""

    raw = row.get("prompt_eval_count")
    if raw is not None:
        return int(raw)
    if int(row.get("step") or 0) == 1:
        calibrated = row.get("calibrated_prompt_eval_count")
        if calibrated is not None:
            return int(calibrated)
    return None


def provider_incomplete_is_safely_retained(row: Mapping[str, Any]) -> bool:
    """Verify that a partial native response remained a non-executable outcome."""

    if row.get("provider_done") is not False:
        return True
    parsed = row.get("parsed_tool_call") or {}
    arguments = parsed.get("arguments") if isinstance(parsed, Mapping) else {}
    return bool(
        row.get("parse_ok") is False
        and "provider_incomplete_response" in str(row.get("parse_error", ""))
        and str(row.get("final_status")) == "error"
        and str(row.get("guard_decision")) == "error"
        and row.get("tool_execution_attempted") is False
        and float(row.get("guard_latency_ms") or 0.0) == 0.0
        and isinstance(parsed, Mapping)
        and parsed.get("tool") == "final"
        and str(row.get("observation"))
        == "PROVIDER_INCOMPLETE_RESPONSE_NOT_EXECUTED"
        and isinstance(arguments, Mapping)
        and arguments.get("answer") == "PROVIDER_INCOMPLETE_RESPONSE_NOT_EXECUTED"
    )


def prompt_token_validity(
    rows: Sequence[Mapping[str, Any]],
    *,
    target: int,
    tolerance: float = 0.05,
) -> dict[str, Any]:
    values = [value for row in rows if (value := effective_prompt_eval_count(row)) is not None]
    lower = target * (1.0 - tolerance)
    upper = target * (1.0 + tolerance)
    return {
        "target_prompt_tokens": target,
        "expected_rows": len(rows),
        "usage_rows": len(values),
        "min": min(values) if values else None,
        "max": max(values) if values else None,
        "all_within_tolerance": len(values) == len(rows)
        and all(lower <= value <= upper for value in values),
        "tolerance_fraction": tolerance,
    }


def reusable_job_evidence(
    record: Mapping[str, Any],
    job: Mapping[str, Any],
    *,
    tolerance: float = 0.05,
) -> bool:
    """Return true only for complete, semantically valid durable job evidence."""

    raw_path = Path(str(record.get("raw_path", "")))
    if record.get("status") != "completed" or not raw_path.exists():
        return False
    rows = read_jsonl(raw_path)
    first = first_step_rows(rows)
    expected = int(job["expected_case_runs"])
    run_keys = [str(row.get("run_key", "")) for row in first]
    target = int(job["target_prompt_tokens"])
    effective_counts = [
        {
            **row,
            "prompt_eval_count": effective_prompt_eval_count(row),
        }
        for row in first
    ]
    token_check = prompt_token_validity(
        effective_counts, target=target, tolerance=tolerance
    )
    return bool(
        record.get("raw_sha256") == sha256_file(raw_path)
        and len(first) == expected
        and {str(row.get("case_id")) for row in first}
        == {str(value) for value in job.get("case_ids", [])}
        and len(set(run_keys)) == expected
        and all(run_keys)
        and token_check["all_within_tolerance"]
        and all(
            (
                (
                    row.get("usage_source") == "ollama_native_prompt_eval_count"
                    and row.get("prompt_eval_count") is not None
                )
                or (
                    int(row.get("step") or 0) == 1
                    and row.get("prompt_count_evidence")
                    == "frozen_one_token_preflight"
                    and row.get("calibrated_prompt_eval_count") is not None
                )
                or row.get("provider_done") is False
            )
            and row.get("model") == job.get("served_model")
            and row.get("served_model") == job.get("served_model")
            and row.get("correction_protocol_id") == job.get("protocol_id")
            and row.get("correction_job_id") == job.get("id")
            and row.get("condition_id") == job.get("condition_id")
            and int(row.get("target_prompt_tokens") or -1)
            == int(job.get("target_prompt_tokens") or -2)
            and (row.get("model_config") or {}).get("ollama_transport") == "native"
            and int(row.get("provider_attempts") or 0) == 1
            and (row.get("model_config") or {}).get("num_ctx") in {None, ""}
            and not bool(row.get("timed_out"))
            and (
                str(row.get("final_status")) != "error"
                or row.get("provider_done") is False
            )
            and provider_incomplete_is_safely_retained(row)
            for row in rows
        )
    )


def archive_invalid_job_attempt(
    output_dir: str | Path,
    job_id: str,
    *,
    attempt: int,
) -> Path | None:
    """Preserve an invalid attempt before rerunning the whole affected job."""

    source = Path(output_dir) / "work" / str(job_id)
    if not source.exists():
        return None
    archive_root = Path(output_dir) / "work" / "failed_attempts"
    archive_root.mkdir(parents=True, exist_ok=True)
    target = archive_root / f"{job_id}__attempt{attempt}"
    suffix = 1
    while target.exists():
        suffix += 1
        target = archive_root / f"{job_id}__attempt{attempt}_{suffix}"
    shutil.move(str(source), str(target))
    return target


def verify_freeze(freeze_path: str | Path) -> dict[str, Any]:
    """Verify every frozen file before formal execution or resume."""

    path = Path(freeze_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    problems: list[str] = []
    if payload.get("protocol_id") != "CONTEXT_CORRECTION_V2":
        problems.append("protocol_id")
    if payload.get("workload_revision") != "r2":
        problems.append("workload_revision")
    if payload.get("status") != "pass" or payload.get("freeze_complete") is not True:
        problems.append("status")
    files = payload.get("files")
    if not isinstance(files, list) or not files:
        files = []
        problems.append("files_empty")
    paths = [str(record.get("path", "")).replace("\\", "/") for record in files]
    if len(paths) != len(set(paths)):
        problems.append("duplicate_paths")
    if set(paths) != set(EXPECTED_FREEZE_PATHS):
        problems.append("freeze_allowlist")
    for record in files:
        value = Path(str(record.get("path", "")))
        target = value if value.is_absolute() else ROOT / value
        if not target.exists():
            problems.append(f"missing:{record.get('path')}")
        elif sha256_file(target) != record.get("sha256"):
            problems.append(f"sha256:{record.get('path')}")
        elif int(target.stat().st_size) != int(record.get("bytes", -1)):
            problems.append(f"bytes:{record.get('path')}")
    prompt_record = payload.get("prompt_verification") or {}
    prompt_path = (
        ROOT
        / "protocols"
        / "context_correction_v2"
        / "prompt_verification_r2.json"
    )
    if (
        prompt_record.get("status") != "pass"
        or prompt_record.get("workload_revision") != "r2"
        or prompt_record.get("sha256") != sha256_file(prompt_path)
        or int(prompt_record.get("case_count", -1)) != 100
    ):
        problems.append("prompt_verification")
    smoke = payload.get("smoke_evidence") or {}
    for experiment_id in ("E9", "E14"):
        record = smoke.get(experiment_id) or {}
        manifest_path = Path(str(record.get("manifest_path", "")))
        target = manifest_path if manifest_path.is_absolute() else ROOT / manifest_path
        if not target.exists():
            problems.append(f"smoke_missing:{experiment_id}")
            continue
        manifest = json.loads(target.read_text(encoding="utf-8"))
        if (
            record.get("sha256") != sha256_file(target)
            or manifest.get("status") != "completed"
            or (manifest.get("validity_checks") or {}).get("status") != "pass"
        ):
            problems.append(f"smoke_invalid:{experiment_id}")
    profiles = payload.get("model_profiles") or {}
    expected_profiles = {
        "2048": ("m3-qwen3-4b-ctx4k:latest", "0ce262040abb", 4096),
        "4096": ("m3-qwen3-4b-ctx8k:latest", "81f2e7df722a", 8192),
        "8192": ("m3-qwen3-4b-ctx16k:latest", "b7c705adc68a", 16384),
        "16384": ("m3-qwen3-4b-ctx32k:latest", "ef6929a22b37", 32768),
    }
    for target, (alias, alias_id, context) in expected_profiles.items():
        record = profiles.get(target) or {}
        if not (
            record.get("served_model") == alias
            and str(record.get("alias_id", "")).lower().startswith(alias_id)
            and int(record.get("effective_context_window_tokens", -1)) == context
        ):
            problems.append(f"model_profile:{target}")
    tests = payload.get("test_gate") or {}
    if tests.get("status") != "pass" or int(tests.get("passed", 0)) < 1:
        problems.append("test_gate")
    if problems:
        raise RuntimeError("context correction freeze drift: " + ", ".join(problems))
    return payload
