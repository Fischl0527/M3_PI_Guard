"""Run the frozen official AgentDojo transformers PI-detector condition.

The runner uses AgentDojo's upstream ``AgentPipeline.from_config`` path with
the official ``transformers_pi_detector`` defense.  It adds only experiment
orchestration: frozen-case selection, file-only logging, failure retention,
resume support, optional resource isolation frozen in the protocol, and
admission checks.  Resource isolation unloads the local Ollama model before a
CPU detector call; it never truncates or changes detector input or scores.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import traceback
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .common import rows_sha256, sha256_file


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_FREEZE = (
    ROOT
    / "protocols"
    / "paper_upgrade_v1"
    / "agentdojo_transformers_pi_detector_resource_isolated_freeze_v1.json"
)
DEFAULT_OUTPUT = (
    ROOT
    / "outputs"
    / "paper_upgrade_v1"
    / "baselines"
    / "agentdojo_transformers_pi_detector_official_resource_isolated_formal_v1"
)
RUNNER_VERSION = "m3-paper-v1-agentdojo-official-transformers-detector-runner-1.3"
EXPECTED_FREEZE_STATUS = "completed_frozen_formal_protocol"
FORMAL_CASE_STATUS = "agentdojo_official_transformers_detector_formal_case"
DIAGNOSTIC_CASE_STATUS = "agentdojo_official_transformers_detector_diagnostic_case"
OMITTED_MARKER = "<Data omitted because a prompt injection was detected>"
DETECTOR_DEVICE_POLICIES = {"auto", "cpu"}
CPU_CUDA_VISIBLE_DEVICES = "-1"
RESOURCE_POLICIES = {"none", "unload_ollama_before_detector"}


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(str(path) + " must contain a JSON object")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, rows: list[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="") as handle:
        handle.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")


def parse_agentdojo_case_id(case_id: str) -> dict[str, str | None]:
    parts = str(case_id).split(":")
    if len(parts) not in {4, 5} or parts[0] != "agentdojo":
        raise ValueError("invalid AgentDojo case id: " + str(case_id))
    return {
        "benchmark": parts[0],
        "benchmark_version": parts[1],
        "suite": parts[2],
        "user_task_id": parts[3],
        "injection_task_id": parts[4] if len(parts) == 5 else None,
        "case_kind": "security" if len(parts) == 5 else "utility",
    }


def _safe_case_stem(index: int, case_id: str) -> str:
    import hashlib

    digest = hashlib.sha256(case_id.encode("utf-8")).hexdigest()[:12]
    return f"case_{index:04d}_{digest}"


def _ollama_probe(base_url: str, model_id: str) -> dict[str, Any]:
    root = re.sub(r"/v1/?$", "", base_url.rstrip("/"))
    with urllib.request.urlopen(root + "/api/version", timeout=10) as response:
        version_payload = json.load(response)
    with urllib.request.urlopen(root + "/api/tags", timeout=30) as response:
        tags_payload = json.load(response)
    names = [str(row.get("name", "")) for row in tags_payload.get("models", [])]
    return {
        "base_url": base_url,
        "ollama_version": version_payload.get("version", ""),
        "model_count": len(names),
        "model_present": model_id in names,
        "target_model": model_id,
    }


def _ollama_unload(base_url: str, model_id: str, *, timeout: float = 60.0) -> dict[str, Any]:
    root = re.sub(r"/v1/?$", "", base_url.rstrip("/"))
    payload = json.dumps(
        {"model": model_id, "prompt": "", "stream": False, "keep_alive": 0}
    ).encode("utf-8")
    request = urllib.request.Request(
        root + "/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=timeout) as response:
        response_payload = json.load(response)
        status_code = int(getattr(response, "status", 200))
    if status_code != 200:
        raise RuntimeError(f"Ollama unload returned HTTP {status_code}")
    return {
        "status": "unloaded_before_detector",
        "http_status": status_code,
        "model": model_id,
        "elapsed_ms": round((time.perf_counter() - started) * 1000.0, 6),
        "done": bool(response_payload.get("done", False)),
    }


def _find_transformers_detector(pipeline: Any) -> Any:
    queue = [pipeline]
    seen: set[int] = set()
    while queue:
        current = queue.pop(0)
        if id(current) in seen:
            continue
        seen.add(id(current))
        if current.__class__.__name__ == "TransformersBasedPIDetector":
            return current
        elements = getattr(current, "elements", None)
        if isinstance(elements, (list, tuple)):
            queue.extend(elements)
    raise RuntimeError("official TransformersBasedPIDetector not found in pipeline")


def _install_resource_policy(
    pipeline: Any,
    *,
    policy: str,
    base_url: str,
    model_id: str,
    unload_fn: Any = _ollama_unload,
) -> dict[str, Any]:
    if policy not in RESOURCE_POLICIES:
        raise ValueError("unknown detector resource policy: " + str(policy))
    info = {
        "policy": policy,
        "detector_input_changed": False,
        "detector_threshold_changed": False,
        "ollama_unload_count": 0,
        "last_unload": {},
        "boundary": (
            "Resource scheduling only. The detector receives the original complete "
            "tool-output string with the pinned official model, threshold and source."
        ),
    }
    if policy == "none":
        pipeline.m3_resource_policy = info
        return info
    detector = _find_transformers_detector(pipeline)
    original_detect = detector.detect

    def detect_with_unload(tool_output: str):
        unload = unload_fn(base_url, model_id)
        info["ollama_unload_count"] = int(info["ollama_unload_count"]) + 1
        info["last_unload"] = unload
        return original_detect(tool_output)

    detector.detect = detect_with_unload
    pipeline.m3_resource_policy = info
    return info


def _apply_detector_device_policy(policy: str) -> dict[str, Any]:
    if policy not in DETECTOR_DEVICE_POLICIES:
        raise ValueError("unknown detector device policy: " + str(policy))
    before = os.environ.get("CUDA_VISIBLE_DEVICES")
    if policy == "cpu":
        os.environ["CUDA_VISIBLE_DEVICES"] = CPU_CUDA_VISIBLE_DEVICES
    return {
        "detector_device_policy": policy,
        "cuda_visible_devices_before": before if before is not None else "",
        "cuda_visible_devices_after": os.environ.get("CUDA_VISIBLE_DEVICES", ""),
        "device_boundary": (
            "The official AgentDojo detector class is unchanged. The runner only "
            "controls CUDA visibility before importing torch/transformers so the "
            "ProtectAI detector can be isolated from the Ollama GPU model. On this "
            "Windows PyTorch runtime, the CPU policy uses CUDA_VISIBLE_DEVICES=-1 "
            "instead of an empty value because an empty value can still leave "
            "torch.cuda.is_available() true with zero visible devices."
        ),
    }


def _trace_path(log_root: Path, pipeline_name: str, parsed: Mapping[str, Any]) -> Path:
    attack_name = "direct" if parsed["case_kind"] == "security" else "none"
    injection_id = str(parsed["injection_task_id"] or "none")
    safe_pipeline = pipeline_name.replace("/", "_")
    return (
        log_root
        / safe_pipeline
        / str(parsed["suite"])
        / str(parsed["user_task_id"])
        / attack_name
        / f"{injection_id}.json"
    )


def _marker_count(path: Path) -> int:
    return path.read_text(encoding="utf-8").count(OMITTED_MARKER) if path.exists() else 0


def _case_manifest_path(case_root: Path, index: int, case_id: str) -> Path:
    return case_root / (_safe_case_stem(index, case_id) + ".json")


def _load_existing_case(
    *,
    case_root: Path,
    index: int,
    case_id: str,
    retry_failed: bool,
) -> dict[str, Any] | None:
    path = _case_manifest_path(case_root, index, case_id)
    if not path.exists():
        return None
    row = _read_json(path)
    if str(row.get("benchmark_case_id", "")) != case_id:
        raise ValueError("case manifest identity mismatch: " + str(path))
    if str(row.get("status", "")) == "failed" and retry_failed:
        return None
    return row


def _build_pipeline(freeze: Mapping[str, Any], log_root: Path):
    checkout = Path(str(freeze["agentdojo"]["checkout"]))
    source = str((checkout / "src").resolve())
    if source not in sys.path:
        sys.path.insert(0, source)

    import agentdojo.attacks.baseline_attacks  # noqa: F401
    from agentdojo.agent_pipeline.agent_pipeline import AgentPipeline, PipelineConfig
    from agentdojo.logging import Logger
    from agentdojo.models import ModelsEnum

    class FileOnlyLogger(Logger):
        def __init__(self, target: Path) -> None:
            self.logdir = str(target.resolve())
            self.messages: list[Any] = []

        def log(self, messages, **kwargs) -> None:  # noqa: ANN001
            self.messages = list(messages)

        def log_error(self, message: str) -> None:
            return None

    config = PipelineConfig(
        llm=ModelsEnum.OPENAI_COMPATIBLE,
        model_id=str(freeze["model_id"]),
        defense="transformers_pi_detector",
        tool_delimiter="tool",
        system_message_name=None,
        system_message=None,
        tool_output_format=str(freeze.get("tool_output_format", "yaml")),
    )
    pipeline = AgentPipeline.from_config(config)
    resource_policy = str(freeze.get("runtime", {}).get("resource_policy", "none"))
    _install_resource_policy(
        pipeline,
        policy=resource_policy,
        base_url=str(freeze["transport"]["base_url"]),
        model_id=str(freeze["model_id"]),
    )
    return pipeline, FileOnlyLogger(log_root)


def _execute_case(
    *,
    freeze: Mapping[str, Any],
    pipeline: Any,
    file_logger: Any,
    parsed: Mapping[str, Any],
    log_root: Path,
) -> dict[str, Any]:
    from agentdojo.attacks.attack_registry import load_attack
    from agentdojo.benchmark import run_task_with_injection_tasks, run_task_without_injection_tasks
    from agentdojo.logging import OutputLogger
    from agentdojo.task_suite.load_suites import get_suite

    # The import is intentional: it documents that the file-only delegate has
    # the same TraceLogger contract as the upstream OutputLogger without using
    # Rich console rendering on Windows.
    assert not isinstance(file_logger, OutputLogger)
    suite = get_suite(str(parsed["benchmark_version"]), str(parsed["suite"]))
    user_task = suite.get_user_task_by_id(str(parsed["user_task_id"]))
    resource_info = getattr(pipeline, "m3_resource_policy", {})
    unload_before = int(resource_info.get("ollama_unload_count", 0))
    started = time.perf_counter()
    with file_logger:
        if parsed["case_kind"] == "utility":
            utility, security = run_task_without_injection_tasks(
                suite,
                pipeline,
                user_task,
                logdir=log_root,
                force_rerun=True,
                benchmark_version=str(parsed["benchmark_version"]),
            )
        else:
            injection_id = str(parsed["injection_task_id"])
            attack = load_attack(str(freeze["attack_name"]), suite, pipeline)
            utility_rows, security_rows = run_task_with_injection_tasks(
                suite,
                pipeline,
                user_task,
                attack,
                logdir=log_root,
                force_rerun=True,
                injection_tasks=[injection_id],
                benchmark_version=str(parsed["benchmark_version"]),
            )
            key = (str(parsed["user_task_id"]), injection_id)
            utility = bool(utility_rows[key])
            security = bool(security_rows[key])
    trace_path = _trace_path(log_root, str(pipeline.name), parsed)
    if not trace_path.exists():
        raise FileNotFoundError("official AgentDojo trace was not written: " + str(trace_path))
    unload_after = int(resource_info.get("ollama_unload_count", 0))
    return {
        "utility_success": bool(utility),
        "security_success": bool(security),
        "attack_success": bool(not security) if parsed["case_kind"] == "security" else False,
        "elapsed_ms": round((time.perf_counter() - started) * 1000.0, 6),
        "official_trace_path": str(trace_path.resolve()),
        "official_trace_sha256": sha256_file(trace_path),
        "detector_redaction_marker_count": _marker_count(trace_path),
        "detector_resource_policy": resource_info.get("policy", "none"),
        "ollama_unloads_before_detector": unload_after - unload_before,
        "detector_input_changed_by_resource_policy": bool(
            resource_info.get("detector_input_changed", False)
        ),
    }


def _aggregate_cases(case_root: Path, cases: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, frozen in enumerate(cases, 1):
        path = _case_manifest_path(case_root, index, str(frozen["benchmark_case_id"]))
        if path.exists():
            rows.append(_read_json(path))
    return rows


def _summary(rows: list[Mapping[str, Any]], total: int) -> dict[str, Any]:
    completed = [row for row in rows if row.get("status") == "completed"]
    failed = [row for row in rows if row.get("status") == "failed"]
    utility = [row for row in rows if row.get("case_kind") == "utility"]
    security = [row for row in rows if row.get("case_kind") == "security"]
    return {
        "expected_cases": total,
        "case_manifests": len(rows),
        "completed_cases": len(completed),
        "failed_cases": len(failed),
        "missing_cases": total - len(rows),
        "utility_cases": len(utility),
        "security_cases": len(security),
        "utility_successes": sum(bool(row.get("utility_success")) for row in utility),
        "attack_successes": sum(bool(row.get("attack_success")) for row in security),
        "detector_redacted_cases": sum(int(row.get("detector_redaction_marker_count", 0)) > 0 for row in completed),
        "status_counts": dict(sorted(Counter(str(row.get("status", "")) for row in rows).items())),
    }


def run(
    *,
    freeze_path: Path,
    output_dir: Path,
    case_limit: int | None,
    case_ids: list[str] | None,
    admit_formal: bool,
    resume: bool,
    retry_failed: bool,
    detector_device_policy: str,
) -> dict[str, Any]:
    freeze = _read_json(freeze_path)
    if freeze.get("status") != EXPECTED_FREEZE_STATUS:
        raise ValueError("freeze is not completed: " + str(freeze.get("status")))
    cases = list(freeze.get("case_rows", []))
    if rows_sha256(cases) != freeze.get("case_rows_sha256"):
        raise ValueError("freeze case_rows hash mismatch")
    if len(cases) != int(freeze.get("case_counts", {}).get("total", 0)):
        raise ValueError("freeze case count mismatch")
    if case_ids:
        requested = set(case_ids)
        selected = [row for row in cases if str(row["benchmark_case_id"]) in requested]
        missing_requested = requested - {
            str(row["benchmark_case_id"]) for row in selected
        }
        if missing_requested:
            raise ValueError(
                "requested case IDs are not in the freeze: "
                + ", ".join(sorted(missing_requested))
            )
        if len(selected) != len(requested):
            raise ValueError("requested case IDs are not unique")
    else:
        selected = cases[:case_limit] if case_limit is not None else cases
    full_requested = len(selected) == len(cases)
    if admit_formal and not full_requested:
        raise ValueError("formal admission cannot be requested for a partial run")

    transport = freeze["transport"]
    base_url = str(transport["base_url"])
    os.environ["OPENAI_COMPATIBLE_BASE_URL"] = base_url
    os.environ["OPENAI_COMPATIBLE_API_KEY"] = "ollama-local"
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ.setdefault("HF_HOME", r"E:\AI_Cache\huggingface")
    os.environ.setdefault("HF_HUB_CACHE", r"E:\AI_Cache\huggingface\hub")
    os.environ.setdefault("OLLAMA_MODELS", str(transport["ollama_models"]))
    service = _ollama_probe(base_url, str(freeze["model_id"]))
    if not service["model_present"]:
        raise ValueError("frozen model is not visible in Ollama: " + str(freeze["model_id"]))

    output_dir.mkdir(parents=True, exist_ok=True)
    case_root = output_dir / "case_manifests"
    log_root = output_dir / "official_logs"
    progress_path = output_dir / "progress.jsonl"
    if not resume and progress_path.exists():
        raise ValueError("--no-resume requires a fresh output directory")
    started_at = datetime.now(timezone.utc).isoformat()
    device_policy = _apply_detector_device_policy(detector_device_policy)
    pipeline, file_logger = _build_pipeline(freeze, log_root)

    for index, frozen in enumerate(selected, 1):
        case_id = str(frozen["benchmark_case_id"])
        existing = (
            _load_existing_case(
                case_root=case_root,
                index=index,
                case_id=case_id,
                retry_failed=retry_failed,
            )
            if resume
            else None
        )
        if existing is not None:
            _append_jsonl(
                progress_path,
                {
                    "index": index,
                    "selected_cases": len(selected),
                    "benchmark_case_id": case_id,
                    "status": "resumed_" + str(existing.get("status", "unknown")),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            continue
        parsed = parse_agentdojo_case_id(case_id)
        if parsed["case_kind"] != frozen.get("case_kind"):
            raise ValueError("case kind mismatch in freeze: " + case_id)
        progress = {
            "index": index,
            "selected_cases": len(selected),
            "benchmark_case_id": case_id,
            "case_kind": parsed["case_kind"],
            "suite": parsed["suite"],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        _append_jsonl(progress_path, {**progress, "status": "running"})
        try:
            outcome = _execute_case(
                freeze=freeze,
                pipeline=pipeline,
                file_logger=file_logger,
                parsed=parsed,
                log_root=log_root,
            )
            row = {
                "schema_version": "paper-agentdojo-official-detector-case-1.0",
                "runner_version": RUNNER_VERSION,
                "status": "completed",
                "evidence_status": FORMAL_CASE_STATUS if admit_formal else DIAGNOSTIC_CASE_STATUS,
                "result_eligible_for_formal_tables": bool(admit_formal),
                "case_index": index,
                "benchmark_case_id": case_id,
                "case_kind": parsed["case_kind"],
                "suite": parsed["suite"],
                "user_task_id": parsed["user_task_id"],
                "injection_task_id": parsed["injection_task_id"],
                **outcome,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            _write_json(_case_manifest_path(case_root, index, case_id), row)
            _append_jsonl(progress_path, {**progress, "status": "completed"})
        except Exception as exc:
            row = {
                "schema_version": "paper-agentdojo-official-detector-case-1.0",
                "runner_version": RUNNER_VERSION,
                "status": "failed",
                "evidence_status": DIAGNOSTIC_CASE_STATUS,
                "result_eligible_for_formal_tables": False,
                "case_index": index,
                "benchmark_case_id": case_id,
                "case_kind": parsed["case_kind"],
                "suite": parsed["suite"],
                "user_task_id": parsed["user_task_id"],
                "injection_task_id": parsed["injection_task_id"],
                "utility_success": False,
                "security_success": False if parsed["case_kind"] == "security" else None,
                "attack_success": parsed["case_kind"] == "security",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            _write_json(_case_manifest_path(case_root, index, case_id), row)
            _append_jsonl(
                progress_path,
                {**progress, "status": "failed", "error_type": type(exc).__name__, "error": str(exc)},
            )

        current_rows = _aggregate_cases(case_root, selected)
        _write_jsonl(output_dir / "outcomes.jsonl", current_rows)
        _write_json(
            output_dir / "run_manifest.json",
            {
                "schema_version": "paper-agentdojo-official-detector-run-manifest-1.0",
                "runner_version": RUNNER_VERSION,
                "status": "running",
                "started_at": started_at,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "pid": os.getpid(),
                "freeze_path": str(freeze_path.resolve()),
                "freeze_sha256": sha256_file(freeze_path),
                "output_dir": str(output_dir.resolve()),
                "service": service,
                "model_id": freeze["model_id"],
                "condition_id": freeze["condition_id"],
                "case_limit": case_limit,
                "requested_case_ids": list(case_ids or []),
                "formal_admission_requested": admit_formal,
                "resume": resume,
                "retry_failed": retry_failed,
                "device_policy": device_policy,
                "resource_policy": dict(getattr(pipeline, "m3_resource_policy", {})),
                "summary": _summary(current_rows, len(selected)),
                "result_eligible_for_formal_tables": False,
            },
        )

    rows = _aggregate_cases(case_root, selected)
    _write_jsonl(output_dir / "outcomes.jsonl", rows)
    summary = _summary(rows, len(selected))
    unique_ids = len({str(row.get("benchmark_case_id", "")) for row in rows}) == len(rows)
    exact_coverage = full_requested and len(rows) == len(cases) and unique_ids
    no_failures = summary["failed_cases"] == 0
    formally_admitted = bool(admit_formal and exact_coverage and no_failures)
    if formally_admitted:
        status = "completed_formal"
    elif full_requested and no_failures:
        status = "completed_full_not_admitted"
    elif full_requested:
        status = "completed_full_with_failures"
    else:
        status = "completed_diagnostic_partial"
    manifest = {
        "schema_version": "paper-agentdojo-official-detector-run-manifest-1.0",
        "runner_version": RUNNER_VERSION,
        "status": status,
        "started_at": started_at,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "pid": os.getpid(),
        "freeze_path": str(freeze_path.resolve()),
        "freeze_sha256": sha256_file(freeze_path),
        "output_dir": str(output_dir.resolve()),
        "service": service,
        "model_id": freeze["model_id"],
        "condition_id": freeze["condition_id"],
        "attack_name": freeze["attack_name"],
        "detector": freeze["detector"],
        "agentdojo": freeze["agentdojo"],
        "case_limit": case_limit,
        "requested_case_ids": list(case_ids or []),
        "formal_admission_requested": admit_formal,
        "resume": resume,
        "retry_failed": retry_failed,
        "device_policy": device_policy,
        "resource_policy": dict(getattr(pipeline, "m3_resource_policy", {})),
        "summary": summary,
        "case_rows_sha256": rows_sha256(rows),
        "outcomes_path": str((output_dir / "outcomes.jsonl").resolve()),
        "outcomes_sha256": sha256_file(output_dir / "outcomes.jsonl"),
        "progress_path": str(progress_path.resolve()),
        "progress_sha256": sha256_file(progress_path),
        "exact_frozen_coverage": exact_coverage,
        "result_eligible_for_formal_tables": formally_admitted,
        "formal_admission_blockers": [
            blocker
            for blocker, present in [
                ("formal_admission_not_requested", not admit_formal),
                ("partial_or_inexact_case_coverage", not exact_coverage),
                ("failed_cases_present", not no_failures),
            ]
            if present
        ],
        "boundary": (
            "Formal eligibility requires explicit admission, exact coverage of all "
            "726 frozen cases, unique case IDs, complete official traces and zero "
            "unexplained failures. Partial/qualification runs remain diagnostic."
        ),
    }
    _write_json(output_dir / "run_manifest.json", manifest)
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", type=Path, default=DEFAULT_FREEZE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--case-limit", type=int, default=None)
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--admit-formal", action="store_true")
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument(
        "--detector-device",
        choices=sorted(DETECTOR_DEVICE_POLICIES),
        default=os.environ.get("M3_AGENTDOJO_DETECTOR_DEVICE", "auto"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run(
        freeze_path=args.freeze.resolve(),
        output_dir=args.output_dir.resolve(),
        case_limit=args.case_limit,
        case_ids=list(args.case_id),
        admit_formal=args.admit_formal,
        resume=not args.no_resume,
        retry_failed=args.retry_failed,
        detector_device_policy=args.detector_device,
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "summary": result["summary"],
                "result_eligible": result["result_eligible_for_formal_tables"],
                "manifest": str((args.output_dir / "run_manifest.json").resolve()),
            },
            ensure_ascii=False,
        )
    )
    return 0 if result["status"] in {"completed_formal", "completed_diagnostic_partial"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
