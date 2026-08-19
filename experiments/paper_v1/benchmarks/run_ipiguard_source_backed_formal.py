"""Run the frozen source-backed IPIGuard AgentDojo condition.

The runner loads IPIGuard's pinned construct/traverse/DAG classes without
editing the external checkout.  It isolates an unused Vertex provider import,
uses the frozen local OpenAI-compatible transport, retains every case failure,
and admits a result only after exact 726-case coverage.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
import types
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from .common import rows_sha256, sha256_file
from .run_agentdojo_official_detector_formal import (
    _append_jsonl,
    _case_manifest_path,
    _load_existing_case,
    _ollama_probe,
    _read_json,
    _write_json,
    _write_jsonl,
    parse_agentdojo_case_id,
)


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_FREEZE = (
    ROOT / "protocols" / "paper_upgrade_v1" / "ipiguard_source_backed_formal_freeze_v1.json"
)
DEFAULT_OUTPUT = (
    ROOT / "outputs" / "paper_upgrade_v1" / "baselines" / "ipiguard_source_backed_formal_v1"
)
RUNNER_VERSION = "m3-paper-v1-ipiguard-source-backed-runner-1.1"
EXPECTED_FREEZE_STATUS = "completed_frozen_formal_protocol"
EXPECTED_CONDITION_ID = "ipiguard_source_backed"
FORMAL_CASE_STATUS = "ipiguard_source_backed_formal_case"
DIAGNOSTIC_CASE_STATUS = "ipiguard_source_backed_diagnostic_case"


def _validate_local_adapter_freeze(freeze: Mapping[str, Any]) -> None:
    adapter = freeze.get("local_adapter", {})
    files = adapter.get("files", {}) if isinstance(adapter, Mapping) else {}
    hashes = adapter.get("sha256", {}) if isinstance(adapter, Mapping) else {}
    if not isinstance(files, Mapping) or not isinstance(hashes, Mapping) or not files:
        raise ValueError("freeze is missing hash-bound local adapter files")
    mismatches: list[str] = []
    for name, raw_path in files.items():
        path = Path(str(raw_path))
        expected = str(hashes.get(name, ""))
        observed = sha256_file(path) if path.exists() else ""
        if not expected or observed != expected:
            mismatches.append(str(name))
    if mismatches:
        raise ValueError("local adapter freeze hash mismatch: " + ", ".join(sorted(mismatches)))


def _validate_resume_identity(
    *,
    output_dir: Path,
    freeze_path: Path,
    freeze: Mapping[str, Any],
    selected: Sequence[Mapping[str, Any]],
) -> None:
    manifest_path = output_dir / "run_manifest.json"
    if not manifest_path.exists():
        return
    manifest = _read_json(manifest_path)
    expected = {
        "freeze_sha256": sha256_file(freeze_path),
        "runner_version": RUNNER_VERSION,
        "model_id": str(freeze.get("model_id", "")),
        "condition_id": EXPECTED_CONDITION_ID,
        "selected_cases": len(selected),
        "case_rows_sha256": rows_sha256(selected),
    }
    mismatches = [
        name
        for name, value in expected.items()
        if manifest.get(name) != value
    ]
    if mismatches:
        raise ValueError(
            "resume root identity mismatch; use a new output directory: "
            + ", ".join(sorted(mismatches))
        )


def _module_is_within(module: Any, source_root: Path) -> bool:
    path = getattr(module, "__file__", None)
    if not path:
        return True
    try:
        Path(path).resolve().relative_to(source_root.resolve())
        return True
    except ValueError:
        return False


def _install_optional_import_isolation(source_root: Path, empty_function_name: str) -> None:
    """Avoid importing unused Vertex provider code from the pinned fork.

    ``tool_execution.py`` imports one constant from ``google_llm.py`` even for
    the OpenAI/IPIGuard path.  The freeze pins the exact constant and source
    hash.  This function supplies only that constant and does not replace any
    construct, traverse, DAG, tool, attack, suite, or checker implementation.
    """

    for name, module in list(sys.modules.items()):
        if name == "agentdojo" or name.startswith("agentdojo."):
            if not _module_is_within(module, source_root):
                raise RuntimeError(
                    "a different AgentDojo checkout is already imported; use a fresh process: " + name
                )
    source_text = str(source_root.resolve())
    if source_text not in sys.path:
        sys.path.insert(0, source_text)
    package_name = "agentdojo.agent_pipeline"
    if package_name not in sys.modules:
        package = types.ModuleType(package_name)
        package.__path__ = [str(source_root / "agentdojo" / "agent_pipeline")]
        package.__package__ = package_name
        sys.modules[package_name] = package
    stub_name = "agentdojo.agent_pipeline.llms.google_llm"
    if stub_name not in sys.modules:
        stub = types.ModuleType(stub_name)
        stub.EMPTY_FUNCTION_NAME = empty_function_name
        stub.__m3_optional_provider_import_isolation__ = True
        sys.modules[stub_name] = stub


def _system_message(source_root: Path) -> str:
    import yaml

    path = source_root / "agentdojo" / "data" / "system_messages.yaml"
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping) or not isinstance(value.get("default"), str):
        raise ValueError("pinned IPIGuard AgentDojo default system message is missing")
    return str(value["default"])


def _pipeline_name(model_id: str) -> str:
    safe = model_id.replace(":", "-").replace("/", "-").replace("\\", "-")
    return safe + "-ipiguard-source-backed"


def _build_pipeline(freeze: Mapping[str, Any]):
    import openai

    checkout = Path(str(freeze["ipiguard"]["checkout"]))
    source_root = checkout / "agentdojo" / "src"
    isolation = freeze["optional_provider_import_isolation"]
    _install_optional_import_isolation(source_root, str(isolation["stubbed_value"]))

    from agentdojo.agent_pipeline.basic_elements import InitQuery, SystemMessage
    from agentdojo.agent_pipeline.llms.ipiguard_llm import (
        OpenAIConstructLLM,
        OpenAITraverseLLM,
    )
    from agentdojo.agent_pipeline.tool_execution import DagToolsExecutionLoop, DagToolsExecutor
    from agentdojo.logging import Logger

    class CapturingOpenAIConstructLLM(OpenAIConstructLLM):
        """Retain the raw DAG JSON while delegating parsing unchanged upstream."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            self.m3_last_construct_dag_raw: str | None = None

        def construct_dag(self, dag_str):  # noqa: ANN001, ANN201
            self.m3_last_construct_dag_raw = str(dag_str)
            return super().construct_dag(dag_str)

    client = openai.OpenAI(
        api_key="ollama-local",
        base_url=str(freeze["transport"]["base_url"]),
        timeout=180.0,
    )
    model_id = str(freeze["model_id"])
    temperature = float(freeze.get("temperature", 0.0))
    construct_llm = CapturingOpenAIConstructLLM(client, model_id, temperature)
    traverse_llm = OpenAITraverseLLM(client, model_id, temperature)
    tools_loop = DagToolsExecutionLoop(DagToolsExecutor(traverse_llm))
    elements = [
        SystemMessage(_system_message(source_root)),
        InitQuery(),
        construct_llm,
        tools_loop,
    ]

    class SourceBackedIPIGuardPipeline:
        name = _pipeline_name(model_id)

        def reset_construct_capture(self) -> None:
            construct_llm.m3_last_construct_dag_raw = None

        def construct_capture(self) -> str | None:
            return construct_llm.m3_last_construct_dag_raw

        def query(
            self,
            query: str,
            runtime: Any,
            env: Any,
            messages: Sequence[Any] = (),
            extra_args: dict[str, Any] | None = None,
        ):
            current_messages: Sequence[Any] = list(messages)
            current_extra = dict(extra_args or {})
            current_extra.setdefault("input_tokens", 0)
            current_extra.setdefault("output_tokens", 0)
            for element in elements:
                query, runtime, env, current_messages, current_extra = element.query(
                    query,
                    runtime,
                    env,
                    current_messages,
                    current_extra,
                )
                Logger().get().log(current_messages)
            return query, runtime, env, current_messages, current_extra

    return SourceBackedIPIGuardPipeline(), source_root


def _persist_construct_capture(
    *,
    pipeline: Any,
    capture_root: Path,
    case_manifest_path: Path,
) -> dict[str, Any]:
    raw = pipeline.construct_capture() if hasattr(pipeline, "construct_capture") else None
    if raw is None:
        return {
            "construct_output_present": False,
            "construct_output_json_valid": False,
            "construct_output_tool_call_count": 0,
        }
    capture_root.mkdir(parents=True, exist_ok=True)
    path = capture_root / (case_manifest_path.stem + ".txt")
    path.write_text(raw, encoding="utf-8")
    parsed: Any = None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        pass
    tool_calls = parsed.get("tool_calls", []) if isinstance(parsed, Mapping) else []
    if not isinstance(tool_calls, list):
        tool_calls = []
    return {
        "construct_output_present": True,
        "construct_output_json_valid": isinstance(parsed, Mapping),
        "construct_output_tool_call_count": len(tool_calls),
        "construct_output_tool_call_key_sets": [
            sorted(str(key) for key in item)
            for item in tool_calls
            if isinstance(item, Mapping)
        ],
        "construct_output_path": str(path.resolve()),
        "construct_output_sha256": sha256_file(path),
        "construct_output_bytes": path.stat().st_size,
    }


def _dag_snapshot(value: Any) -> dict[str, Any]:
    if value is None:
        return {"present": False, "nodes": [], "edges": []}
    try:
        nodes = []
        for node_id, data in value.nodes(data=True):
            call = data.get("function_call")
            nodes.append(
                {
                    "id": str(node_id),
                    "function": str(getattr(call, "function", "")),
                    "args": dict(getattr(call, "args", {}) or {}),
                    "depends_on": [str(item) for item in data.get("depends_on", [])],
                }
            )
        edges = [[str(left), str(right)] for left, right in value.edges()]
        return {"present": True, "nodes": nodes, "edges": edges}
    except Exception as exc:  # evidence serialization must not hide a malformed DAG
        return {
            "present": True,
            "serialization_error": type(exc).__name__ + ": " + str(exc),
            "nodes": [],
            "edges": [],
        }


def _trace_path(log_root: Path, pipeline_name: str, parsed: Mapping[str, Any]) -> Path:
    attack_type = "direct" if parsed["case_kind"] == "security" else "none"
    injection_id = str(parsed["injection_task_id"] or "none")
    return (
        log_root
        / pipeline_name.replace("/", "_")
        / str(parsed["suite"])
        / str(parsed["user_task_id"])
        / attack_type
        / f"{injection_id}.json"
    )


def _execute_case(
    *,
    freeze: Mapping[str, Any],
    pipeline: Any,
    parsed: Mapping[str, Any],
    log_root: Path,
) -> dict[str, Any]:
    from agentdojo.attacks.attack_registry import load_attack
    from agentdojo.logging import TraceLogger
    from agentdojo.task_suite.load_suites import get_suite

    class FileOnlyDelegate:
        def __init__(self, target: Path) -> None:
            self.logdir = str(target.resolve())
            self.messages: list[Any] = []

        def log(self, messages, **kwargs) -> None:  # noqa: ANN001, ARG002
            self.messages = list(messages)

        def log_error(self, message: str) -> None:  # noqa: ARG002
            return None

    suite = get_suite(str(parsed["benchmark_version"]), str(parsed["suite"]))
    user_task = suite.get_user_task_by_id(str(parsed["user_task_id"]))
    injection_task = None
    injections: dict[str, str] = {}
    if parsed["case_kind"] == "security":
        injection_task = suite.get_injection_task_by_id(str(parsed["injection_task_id"]))
        attack = load_attack(str(freeze["attack_name"]), suite, pipeline)
        injections = dict(attack.attack(user_task, injection_task))
    attack_type = str(freeze["attack_name"]) if injection_task is not None else "none"
    logger = TraceLogger(
        FileOnlyDelegate(log_root),
        suite_name=str(parsed["suite"]),
        pipeline_name=str(pipeline.name),
        user_task_id=str(parsed["user_task_id"]),
        injection_task_id=str(parsed["injection_task_id"] or "none"),
        injections=injections,
        attack_type=attack_type,
        source_backed_ipiguard=True,
    )
    started = time.perf_counter()
    with logger:
        utility, security, _messages, extra = suite.run_task_with_pipeline_msg(
            pipeline,
            user_task,
            injection_task=injection_task,
            injections=injections,
            extra_args={"input_tokens": 0, "output_tokens": 0},
        )
        logger.set_contextarg("input_tokens", int(extra.get("input_tokens", 0)))
        logger.set_contextarg("output_tokens", int(extra.get("output_tokens", 0)))
        logger.set_contextarg("dag", _dag_snapshot(extra.get("dag")))
    trace_path = _trace_path(log_root, str(pipeline.name), parsed)
    if not trace_path.exists():
        raise FileNotFoundError("IPIGuard source trace was not written: " + str(trace_path))
    dag = _dag_snapshot(extra.get("dag"))
    if not dag.get("present") or dag.get("serialization_error"):
        raise ValueError("IPIGuard DAG evidence is missing or unserializable")
    return {
        "utility_success": bool(utility),
        "security_success": bool(security),
        "attack_success": bool(not security) if parsed["case_kind"] == "security" else False,
        "elapsed_ms": round((time.perf_counter() - started) * 1000.0, 6),
        "input_tokens": int(extra.get("input_tokens", 0)),
        "output_tokens": int(extra.get("output_tokens", 0)),
        "dag_node_count": len(dag["nodes"]),
        "dag_edge_count": len(dag["edges"]),
        "source_trace_path": str(trace_path.resolve()),
        "source_trace_sha256": sha256_file(trace_path),
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
        "cases_with_dag": sum(int(row.get("dag_node_count", 0)) > 0 for row in completed),
        "input_tokens": sum(int(row.get("input_tokens", 0)) for row in completed),
        "output_tokens": sum(int(row.get("output_tokens", 0)) for row in completed),
        "status_counts": dict(sorted(Counter(str(row.get("status", "")) for row in rows).items())),
    }


def _select_cases(
    cases: list[Mapping[str, Any]],
    case_limit: int | None,
    case_ids: list[str] | None,
) -> list[Mapping[str, Any]]:
    if case_ids:
        requested = set(case_ids)
        selected = [row for row in cases if str(row["benchmark_case_id"]) in requested]
        missing = requested - {str(row["benchmark_case_id"]) for row in selected}
        if missing:
            raise ValueError("requested case IDs are not in the freeze: " + ", ".join(sorted(missing)))
        if len(selected) != len(requested):
            raise ValueError("requested case IDs are not unique")
        return selected
    return cases[:case_limit] if case_limit is not None else cases


def run(
    *,
    freeze_path: Path,
    output_dir: Path,
    case_limit: int | None,
    case_ids: list[str] | None,
    admit_formal: bool,
    resume: bool,
    retry_failed: bool,
) -> dict[str, Any]:
    freeze = _read_json(freeze_path)
    if freeze.get("status") != EXPECTED_FREEZE_STATUS:
        raise ValueError("freeze is not completed: " + str(freeze.get("status")))
    if freeze.get("condition_id") != EXPECTED_CONDITION_ID:
        raise ValueError("unexpected freeze condition: " + str(freeze.get("condition_id")))
    _validate_local_adapter_freeze(freeze)
    cases = list(freeze.get("case_rows", []))
    if rows_sha256(cases) != freeze.get("case_rows_sha256"):
        raise ValueError("freeze case_rows hash mismatch")
    if len(cases) != int(freeze.get("case_counts", {}).get("total", 0)):
        raise ValueError("freeze case count mismatch")
    selected = _select_cases(cases, case_limit, case_ids)
    full_requested = len(selected) == len(cases)
    if admit_formal and not full_requested:
        raise ValueError("formal admission cannot be requested for a partial run")

    _validate_resume_identity(
        output_dir=output_dir,
        freeze_path=freeze_path,
        freeze=freeze,
        selected=selected,
    )

    transport = freeze["transport"]
    base_url = str(transport["base_url"])
    os.environ.setdefault("OLLAMA_MODELS", str(transport["ollama_models"]))
    service = _ollama_probe(base_url, str(freeze["model_id"]))
    if not service["model_present"]:
        raise ValueError("frozen model is not visible in Ollama: " + str(freeze["model_id"]))

    output_dir.mkdir(parents=True, exist_ok=True)
    case_root = output_dir / "case_manifests"
    log_root = output_dir / "source_logs"
    construct_capture_root = output_dir / "construct_outputs"
    progress_path = output_dir / "progress.jsonl"
    if not resume and progress_path.exists():
        raise ValueError("--no-resume requires a fresh output directory")
    started_at = datetime.now(timezone.utc).isoformat()
    pipeline, source_root = _build_pipeline(freeze)

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
        if hasattr(pipeline, "reset_construct_capture"):
            pipeline.reset_construct_capture()
        try:
            outcome = _execute_case(
                freeze=freeze,
                pipeline=pipeline,
                parsed=parsed,
                log_root=log_root,
            )
            row = {
                "schema_version": "paper-ipiguard-source-backed-case-1.0",
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
        except Exception as exc:
            row = {
                "schema_version": "paper-ipiguard-source-backed-case-1.0",
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
        row.update(
            _persist_construct_capture(
                pipeline=pipeline,
                capture_root=construct_capture_root,
                case_manifest_path=_case_manifest_path(case_root, index, case_id),
            )
        )
        _write_json(_case_manifest_path(case_root, index, case_id), row)
        _append_jsonl(
            progress_path,
            {
                **progress,
                "status": str(row["status"]),
                "error_type": row.get("error_type", ""),
                "error": row.get("error", ""),
            },
        )
        current = _aggregate_cases(case_root, selected)
        _write_jsonl(output_dir / "outcomes.jsonl", current)
        _write_json(
            output_dir / "run_manifest.json",
            {
                "schema_version": "paper-ipiguard-source-backed-run-manifest-1.0",
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
                "source_root": str(source_root.resolve()),
                "selected_cases": len(selected),
                "formal_admission_requested": admit_formal,
                "summary": _summary(current, len(selected)),
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
        "schema_version": "paper-ipiguard-source-backed-run-manifest-1.0",
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
        "ipiguard": freeze["ipiguard"],
        "optional_provider_import_isolation": freeze["optional_provider_import_isolation"],
        "case_limit": case_limit,
        "selected_cases": len(selected),
        "requested_case_ids": list(case_ids or []),
        "formal_admission_requested": admit_formal,
        "resume": resume,
        "retry_failed": retry_failed,
        "summary": summary,
        "case_rows_sha256": rows_sha256(rows),
        "status_counts": dict(sorted(Counter(str(row.get("status", "")) for row in rows).items())),
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
            "Formal eligibility requires explicit admission, exact unique coverage of all "
            "726 frozen cases, source traces with DAG evidence, and zero unexplained failures. "
            "This is a disclosed source-backed adapter, not the upstream CLI byte-for-byte."
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
