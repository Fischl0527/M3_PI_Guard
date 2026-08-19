"""Build a fail-closed next-action plan for the Q2 formal campaign.

The planner is intentionally read-only.  It never starts a model, retries a
case, runs an analyzer, or writes a registry.  It converts the current monitor
and admission artifacts into one deterministic next action so that long GPU
runs are not overlapped and completed rows are not silently promoted.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .common import portable_path


ROOT = Path(__file__).resolve().parents[3]
PROTOCOL_ROOT = ROOT / "protocols" / "paper_upgrade_v1"
DEFAULT_OUTPUT_DIR = PROTOCOL_ROOT / "execution"
DEFAULT_TOOL_FILTER_MONITOR = (
    PROTOCOL_ROOT
    / "monitors"
    / "tool_filter_formal_v1"
    / "agentdojo_official_formal_run_monitor_v1.json"
)
DEFAULT_TOOL_FILTER_ADMISSION = PROTOCOL_ROOT / "agentdojo_tool_filter_formal_admission_v1.json"
DEFAULT_ADAPTIVE_MONITOR = (
    PROTOCOL_ROOT
    / "monitors"
    / "adaptive_mcts_budget_v1"
    / "adaptive_mcts_budget_formal_monitor_v1.json"
)
DEFAULT_PUBLIC_PLAN = PROTOCOL_ROOT / "public_benchmark_formal_run_plan_v2.json"
DEFAULT_Q2_AUDIT = PROTOCOL_ROOT / "q2_readiness_audit_v1.json"
DEFAULT_TASKSHIELD_V14_ROOT = (
    ROOT / "outputs" / "paper_upgrade_v1" / "baselines" / "taskshield_paper_formal_v14"
)
DEFAULT_TASKSHIELD_V14_SEAL = (
    PROTOCOL_ROOT
    / "execution"
    / "taskshield_v14_failed_root_seal_v1"
    / "taskshield_v14_failed_root_seal_v1.json"
)
DEFAULT_TASKSHIELD_V15_ANALYSIS = (
    PROTOCOL_ROOT
    / "execution"
    / "taskshield_v15_expanded_qualification_v1"
    / "qualification_analysis.json"
)
DEFAULT_TASKSHIELD_V16_G3 = (
    PROTOCOL_ROOT
    / "execution"
    / "taskshield_v16_p4_expanded_v1"
    / "gate_g3.json"
)
DEFAULT_TASKSHIELD_V16_SUMMARY = (
    ROOT
    / "outputs"
    / "paper_upgrade_v1"
    / "analysis_v2"
    / "taskshield_v16_qualification"
    / "summary.json"
)
DEFAULT_PROGENT_V14_G1 = (
    PROTOCOL_ROOT
    / "execution"
    / "progent_v14_p2_correctness_v1"
    / "gate_g1.json"
)
EXTERNAL_BASELINES = ("task_shield", "progent", "camel_or_fides", "ipiguard")
ADMITTED_STATUSES = {"admitted", "admitted_registry_updated"}
EXTERNAL_ADMITTED_STATUSES = {"admitted_formal_result"}
EXTERNAL_READY_STATUSES = {"ready_for_registry_admission"}
QUALIFICATION_CASE_IDS = (
    "agentdojo:v1:banking:user_task_0",
    "agentdojo:v1:banking:user_task_0:injection_task_0",
)
CAMEL_V3_P3_CASE_IDS = (
    "agentdojo:v1:banking:user_task_0",
    "agentdojo:v1:banking:user_task_0:injection_task_0",
    "agentdojo:v1:slack:user_task_18",
    "agentdojo:v1:slack:user_task_18:injection_task_1",
    "agentdojo:v1:workspace:user_task_0",
    "agentdojo:v1:workspace:user_task_0:injection_task_0",
    "agentdojo:v1:travel:user_task_0",
    "agentdojo:v1:travel:user_task_0:injection_task_0",
)
CAMEL_V3_P3_OUTPUT = (
    "outputs/paper_upgrade_v1/baselines/camel_source_backed_qualification_v3_p3_8case"
)
EXTERNAL_QUALIFICATION_SPECS = {
    "task_shield": {
        "python": "python",
        "module": "experiments.paper_v1.benchmarks.run_taskshield_paper_formal_v14",
        "analyzer": "experiments.paper_v1.benchmarks.analyze_taskshield_paper_formal",
        "freeze": "protocols/paper_upgrade_v1/taskshield_paper_formal_freeze_v14.json",
        "output": "outputs/paper_upgrade_v1/baselines/taskshield_paper_qualification_v14",
        "formal_output": "outputs/paper_upgrade_v1/baselines/taskshield_paper_formal_v14",
        "monitor_output": "protocols/paper_upgrade_v1/monitors/task_shield_formal_v14",
    },
    "progent": {
        "python": "python",
        "builder": "experiments.paper_v1.benchmarks.build_progent_source_backed_formal_freeze_v14",
        "g1_audit": "experiments.paper_v1.benchmarks.audit_progent_v14_correctness",
        "module": "experiments.paper_v1.benchmarks.run_progent_source_backed_formal_v14",
        "analyzer": "experiments.paper_v1.benchmarks.analyze_progent_source_backed_formal_v14",
        "freeze": "protocols/paper_upgrade_v1/progent_source_backed_formal_freeze_v14.json",
        "output": "outputs/paper_upgrade_v1/baselines/progent_source_backed_qualification_v14_p3",
        "output_p3": "outputs/paper_upgrade_v1/baselines/progent_source_backed_qualification_v14_p3",
        "output_p4": "outputs/paper_upgrade_v1/baselines/progent_source_backed_qualification_v14_p4",
        "output_p5": "outputs/paper_upgrade_v1/baselines/progent_source_backed_qualification_v14_p5",
        "analysis_p3": "outputs/paper_upgrade_v1/analysis_v2/progent_source_backed_v14_p3",
        "analysis_p4": "outputs/paper_upgrade_v1/analysis_v2/progent_source_backed_v14_p4",
        "analysis_p5": "outputs/paper_upgrade_v1/analysis_v2/progent_source_backed_v14_p5",
        "formal_output": "outputs/paper_upgrade_v1/baselines/progent_source_backed_formal_v14",
    },
    "camel_or_fides": {
        "python": "& E:\\M3_PI_Guard_runtime\\camel\\.venv\\Scripts\\python.exe",
        "module": "experiments.paper_v1.benchmarks.run_camel_source_backed_formal_v3",
        "analyzer": "experiments.paper_v1.benchmarks.analyze_camel_source_backed_formal_v3",
        "freeze": "protocols/paper_upgrade_v1/camel_source_backed_formal_freeze_v3.json",
        "output": "outputs/paper_upgrade_v1/baselines/camel_source_backed_qualification_v3",
        "formal_output": "outputs/paper_upgrade_v1/baselines/camel_source_backed_formal_v3",
    },
    "ipiguard": {
        "python": "python",
        "module": "experiments.paper_v1.benchmarks.run_ipiguard_source_backed_formal",
        "analyzer": "experiments.paper_v1.benchmarks.analyze_ipiguard_source_backed_formal",
        "freeze": "protocols/paper_upgrade_v1/ipiguard_source_backed_formal_freeze_v1.json",
        "output": "outputs/paper_upgrade_v1/baselines/ipiguard_source_backed_qualification_v2",
        "formal_output": "outputs/paper_upgrade_v1/baselines/ipiguard_source_backed_formal_v1",
    },
}
RUNNING_HEALTH = {
    "running_progressing",
    "running_stall_suspected",
    "running_with_failures_requires_attention",
}
PLAN_VERSION = "m3-paper-v1-q2-formal-execution-plan-1.0"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _is_live_monitor(monitor: Mapping[str, Any]) -> bool:
    return (
        str(monitor.get("health_status", "")) in RUNNING_HEALTH
        and monitor.get("pid_alive") is True
    )


def _pid_alive(pid: Any) -> bool | None:
    try:
        pid_int = int(pid)
    except (TypeError, ValueError):
        return None
    if pid_int <= 0:
        return None
    if os.name == "nt":
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        process_query_limited_information = 0x1000
        still_active = 259
        kernel32.OpenProcess.argtypes = [
            ctypes.c_uint32,
            ctypes.c_int,
            ctypes.c_uint32,
        ]
        kernel32.OpenProcess.restype = ctypes.c_void_p
        kernel32.GetExitCodeProcess.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_uint32),
        ]
        kernel32.GetExitCodeProcess.restype = ctypes.c_int
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel32.CloseHandle.restype = ctypes.c_int
        handle = kernel32.OpenProcess(process_query_limited_information, False, pid_int)
        if handle:
            exit_code = ctypes.c_uint32()
            try:
                if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                    return None
                return exit_code.value == still_active
            finally:
                kernel32.CloseHandle(handle)
        return kernel32.GetLastError() == 5
    try:
        os.kill(pid_int, 0)
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _public_cell_summary(plan: Mapping[str, Any]) -> dict[str, Any]:
    rows = plan.get("cells", [])
    if not isinstance(rows, list):
        rows = []
    statuses: Counter[str] = Counter()
    first_pending: dict[str, Any] | None = None
    for raw in rows:
        if not isinstance(raw, Mapping):
            continue
        manifest_path = Path(str(raw.get("manifest_path", "")))
        manifest = _read_json(manifest_path) if str(manifest_path) not in {"", "."} else {}
        status = str(manifest.get("status") or raw.get("status_after_initialization") or "missing")
        statuses[status] += 1
        if first_pending is None and status == "pending":
            first_pending = {
                "cell_id": str(raw.get("cell_id", "")),
                "benchmark": str(raw.get("benchmark", "")),
                "model": str(raw.get("model", "")),
                "condition_id": str(raw.get("condition_id", "")),
            }
    return {
        "expected_cell_count": int(plan.get("expected_cell_count", len(rows)) or 0),
        "expected_case_runs": int(plan.get("expected_case_runs", 0) or 0),
        "status_counts": dict(sorted(statuses.items())),
        "first_pending": first_pending,
    }


def _external_admission_summary(admission_dir: Path) -> dict[str, str]:
    return {
        baseline: str(
            _read_json(admission_dir / f"{baseline}_formal_admission_v1.json").get(
                "status", "missing"
            )
        )
        for baseline in EXTERNAL_BASELINES
    }


def _public_command(first_pending: Mapping[str, Any] | None) -> str:
    if not first_pending:
        return ""
    cell_id = str(first_pending.get("cell_id", ""))
    benchmark = str(first_pending.get("benchmark", ""))
    if benchmark == "agentdojo":
        module = "experiments.paper_v1.benchmarks.run_agentdojo_formal_cell"
        admission_flag = "--admit-formal-source"
    elif benchmark == "injecagent":
        module = "experiments.paper_v1.benchmarks.run_injecagent_formal_cell"
        admission_flag = "--formal-source-admission"
    else:
        return ""
    return (
        f"python -m {module} --cell-id {cell_id} --execute {admission_flag} "
        "--ingest --materialize"
    )


def _external_qualification_command(baseline: str) -> str:
    spec = EXTERNAL_QUALIFICATION_SPECS.get(baseline)
    if not spec:
        return ""
    if baseline == "progent":
        return _progent_v14_run_command(spec, "p3")
    case_args = " ".join(f"--case-id {case_id}" for case_id in QUALIFICATION_CASE_IDS)
    return (
        f"{spec['python']} -m {spec['module']} --freeze {spec['freeze']} "
        f"--output-dir {spec['output']} {case_args} --no-resume"
    )


def _camel_v3_p3_command() -> str:
    spec = EXTERNAL_QUALIFICATION_SPECS["camel_or_fides"]
    case_args = " ".join(f"--case-id {case_id}" for case_id in CAMEL_V3_P3_CASE_IDS)
    return (
        f"{spec['python']} -m {spec['module']} --freeze {spec['freeze']} "
        f"--output-dir {CAMEL_V3_P3_OUTPUT} {case_args} --no-resume"
    )


def _external_formal_command(baseline: str) -> str:
    spec = EXTERNAL_QUALIFICATION_SPECS.get(baseline)
    if not spec:
        return ""
    return (
        f"{spec['python']} -m {spec['module']} --freeze {spec['freeze']} "
        f"--output-dir {spec['formal_output']} --admit-formal"
    )


def _external_analysis_command(baseline: str) -> str:
    spec = EXTERNAL_QUALIFICATION_SPECS.get(baseline)
    if not spec:
        return ""
    return (
        f"python -m {spec['analyzer']} --run-dir {spec['formal_output']} "
        f"--output-dir {spec['formal_output']}/analysis"
    )


def _external_admission_command(baseline: str) -> str:
    spec = EXTERNAL_QUALIFICATION_SPECS.get(baseline)
    if not spec:
        return ""
    return (
        "python -m experiments.paper_v1.benchmarks."
        "admit_external_strong_baseline_formal_result "
        f"--condition-id {baseline} --run-dir {spec['formal_output']} "
        f"--analysis-manifest {spec['formal_output']}/analysis/analysis_manifest.json"
    )


def _spec_path(value: str) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else ROOT / path


def _progent_v14_phase_output(spec: Mapping[str, Any], phase: str) -> Path:
    raw = spec.get(f"output_{phase}")
    if raw:
        return _spec_path(str(raw))
    base = _spec_path(str(spec["output"]))
    return base if phase == "p3" else base.with_name(base.name + f"_{phase}")


def _progent_v14_phase_analysis(spec: Mapping[str, Any], phase: str) -> Path:
    raw = spec.get(f"analysis_{phase}")
    if raw:
        return _spec_path(str(raw))
    return _progent_v14_phase_output(spec, phase) / "analysis"


def _progent_v14_run_command(spec: Mapping[str, Any], phase: str) -> str:
    return (
        f"{spec['python']} -m {spec['module']} --freeze {spec['freeze']} "
        f"--output-dir {spec.get(f'output_{phase}', spec['output'])} "
        f"--selection {phase} --no-resume"
    )


def _progent_v14_analysis_command(spec: Mapping[str, Any], phase: str) -> str:
    return (
        f"python -m {spec['analyzer']} --run-dir "
        f"{spec.get(f'output_{phase}', spec['output'])} --output-dir "
        f"{spec.get(f'analysis_{phase}', str(_progent_v14_phase_analysis(spec, phase)))} "
        f"--phase {phase}"
    )


def _progent_v14_state(admission_status: str) -> dict[str, Any]:
    spec = EXTERNAL_QUALIFICATION_SPECS["progent"]
    freeze_path = _spec_path(str(spec["freeze"]))
    freeze = _read_json(freeze_path)
    g1 = _read_json(DEFAULT_PROGENT_V14_G1)
    phase_states: dict[str, Any] = {}
    running_phase = ""
    running_manifest: Mapping[str, Any] = {}
    for phase in ("p3", "p4", "p5"):
        run_dir = _progent_v14_phase_output(spec, phase)
        analysis_dir = _progent_v14_phase_analysis(spec, phase)
        manifest = _read_json(run_dir / "run_manifest.json")
        gate = _read_json(analysis_dir / "gate.json")
        summary = manifest.get("summary", {}) if isinstance(manifest, Mapping) else {}
        completed = bool(
            manifest.get("status") == "completed_qualification"
            and manifest.get("exact_selected_coverage") is True
            and manifest.get("zero_unresolved") is True
        )
        failed = bool(
            manifest
            and (
                manifest.get("status") == "completed_qualification_with_failures"
                or manifest.get("zero_unresolved") is False
            )
        )
        if manifest.get("status") == "running":
            running_phase = phase
            running_manifest = manifest
        phase_states[phase] = {
            "run_dir": portable_path(run_dir, root=ROOT),
            "run_status": manifest.get("status", "missing"),
            "run_completed": completed,
            "run_failed": failed,
            "completed_cases": summary.get("completed_cases", 0),
            "failed_cases": summary.get("failed_cases", 0),
            "expected_cases": summary.get("expected_cases", 0),
            "gate_path": portable_path(analysis_dir / "gate.json", root=ROOT),
            "gate_status": gate.get("status", "missing"),
            "gate_passed": gate.get("status") == "passed",
            "gate_failed": gate.get("status") == "failed",
        }
    failed_gate_phase = next(
        (
            phase
            for phase in ("p3", "p4", "p5")
            if phase_states[phase].get("gate_failed")
        ),
        "",
    )
    p5_passed = bool(phase_states["p5"]["gate_passed"])
    formal_manifest = _read_json(_spec_path(str(spec["formal_output"])) / "run_manifest.json")
    formal_summary = formal_manifest.get("summary", {}) if isinstance(formal_manifest, Mapping) else {}
    formal_pid_alive = _pid_alive(formal_manifest.get("pid"))
    state = {
        "admission_status": admission_status,
        "freeze_path": portable_path(freeze_path, root=ROOT),
        "freeze_status": freeze.get("status", "missing"),
        "g1_path": portable_path(DEFAULT_PROGENT_V14_G1, root=ROOT),
        "g1_status": g1.get("status", "missing"),
        "g1_passed": g1.get("status") == "passed",
        "phase_states": phase_states,
        "qualification_completed": p5_passed,
        "route_retired": bool(failed_gate_phase),
        "terminal_route_status": (
            f"failed_{failed_gate_phase}_qualification_gate_preserved_negative_evidence"
            if failed_gate_phase
            else ""
        ),
        "retirement_reason": (
            "Progent v1.4 qualification gate failed; preserve evidence and route "
            "the Q2-80 strong-baseline campaign to the next baseline instead of "
            "retrying or expanding this revision."
            if failed_gate_phase
            else ""
        ),
        "formal_manifest": portable_path(
            _spec_path(str(spec["formal_output"])) / "run_manifest.json", root=ROOT
        ),
        "formal_status": formal_manifest.get("status", "missing"),
        "formal_pid": formal_manifest.get("pid"),
        "formal_pid_alive": formal_pid_alive,
        "formal_completed_cases": formal_summary.get("completed_cases", 0),
        "formal_failed_cases": formal_summary.get("failed_cases", 0),
        "formal_expected_cases": formal_summary.get("expected_cases", 0),
        "formal_completed": bool(
            formal_manifest.get("status") == "completed_formal"
            and formal_manifest.get("result_eligible_for_formal_tables") is True
            and formal_summary.get("expected_cases") == 726
            and formal_summary.get("completed_cases") == 726
            and formal_summary.get("failed_cases") == 0
        ),
        "analysis_completed": False,
        "p6_authorization_required": p5_passed,
    }
    if running_phase:
        state.update(
            {
                "formal_status": "running",
                "formal_pid": running_manifest.get("pid"),
                "formal_pid_alive": _pid_alive(running_manifest.get("pid")),
                "formal_completed_cases": running_manifest.get("summary", {}).get(
                    "completed_cases", 0
                ),
                "formal_failed_cases": running_manifest.get("summary", {}).get(
                    "failed_cases", 0
                ),
                "formal_expected_cases": running_manifest.get("summary", {}).get(
                    "expected_cases", 0
                ),
                "running_phase": running_phase,
                "monitor_command": (
                    "python -m experiments.paper_v1.benchmarks."
                    f"analyze_progent_source_backed_formal_v14 --run-dir "
                    f"{spec.get(f'output_{running_phase}', spec['output'])} "
                    f"--output-dir {spec.get(f'analysis_{running_phase}', str(_progent_v14_phase_analysis(spec, running_phase)))} "
                    f"--phase {running_phase}"
                ),
            }
        )
    return state


def _progent_v14_next_action(state: Mapping[str, Any]) -> dict[str, str]:
    spec = EXTERNAL_QUALIFICATION_SPECS["progent"]
    if state.get("freeze_status") != "completed_frozen_formal_protocol":
        return {
            "action_id": "build_progent_v14_freeze",
            "status": "ready_requires_explicit_execution",
            "resource_kind": "cpu",
            "command": f"python -m {spec['builder']}",
            "reason": "Progent v1.4 freeze is missing or invalid; build the zero-model staged freeze before any qualification case.",
        }
    if state.get("g1_passed") is not True:
        return {
            "action_id": "audit_progent_v14_g1",
            "status": "ready_requires_explicit_execution",
            "resource_kind": "cpu",
            "command": f"python -m {spec['g1_audit']}",
            "reason": "Progent v1.4 must pass the zero-model correctness gate before P3 can start.",
        }
    for phase in ("p3", "p4", "p5"):
        phase_state = state.get("phase_states", {}).get(phase, {})
        if phase_state.get("run_failed"):
            return {
                "action_id": f"review_progent_v14_{phase}_failed_root",
                "status": "blocked_failed_root_preserved",
                "resource_kind": "cpu_read_only",
                "command": "",
                "reason": f"Progent v1.4 {phase.upper()} has unresolved or failed cases; preserve the root and do not retry rows in place.",
            }
        if not phase_state.get("run_completed"):
            return {
                "action_id": f"run_progent_v14_{phase}",
                "status": "ready_requires_explicit_execution",
                "resource_kind": "ollama_gpu",
                "command": _progent_v14_run_command(spec, phase),
                "reason": f"Run fresh Progent v1.4 {phase.upper()} qualification with per-case watchdog and no failed-row retry.",
            }
        if not phase_state.get("gate_passed"):
            if phase_state.get("gate_failed"):
                return {
                    "action_id": f"review_progent_v14_{phase}_gate_failure",
                    "status": "blocked_failed_gate_preserved",
                    "resource_kind": "cpu_read_only",
                    "command": "",
                    "reason": f"Progent v1.4 {phase.upper()} gate failed; preserve the evidence and move only through a new revision.",
                }
            return {
                "action_id": f"analyze_progent_v14_{phase}",
                "status": "ready_requires_explicit_execution",
                "resource_kind": "cpu",
                "command": _progent_v14_analysis_command(spec, phase),
                "reason": f"Progent v1.4 {phase.upper()} run is terminal; analyze the gate before any larger panel.",
            }
    return {
        "action_id": "request_progent_v14_p6_authorization",
        "status": "blocked_explicit_formal_authorization",
        "resource_kind": "none",
        "command": "",
        "reason": "P5 has passed; the 726-case Progent P6 formal run requires a separate explicit authorization and an authorized freeze.",
    }


def _external_run_state(baseline: str, admission_status: str) -> dict[str, Any]:
    spec = EXTERNAL_QUALIFICATION_SPECS.get(baseline)
    if not spec:
        return {"admission_status": admission_status, "qualification_status": "missing_spec"}
    if baseline == "progent":
        return _progent_v14_state(admission_status)
    qualification_manifest = _spec_path(str(spec["output"])) / "run_manifest.json"
    formal_manifest = _spec_path(str(spec["formal_output"])) / "run_manifest.json"
    analysis_manifest = _spec_path(str(spec["formal_output"])) / "analysis" / "analysis_manifest.json"
    qualification = _read_json(qualification_manifest)
    formal = _read_json(formal_manifest)
    analysis = _read_json(analysis_manifest)
    expanded_qualification_manifest = _read_json(_spec_path(CAMEL_V3_P3_OUTPUT) / "run_manifest.json")
    q_summary = qualification.get("summary", {}) if isinstance(qualification, Mapping) else {}
    expanded_summary = (
        expanded_qualification_manifest.get("summary", {})
        if isinstance(expanded_qualification_manifest, Mapping)
        else {}
    )
    f_summary = formal.get("summary", {}) if isinstance(formal, Mapping) else {}
    formal_pid_alive = _pid_alive(formal.get("pid"))
    qualification_completed = bool(
        qualification.get("status") == "completed_diagnostic_partial"
        and qualification.get("result_eligible_for_formal_tables") is False
        and q_summary.get("expected_cases") == 2
        and q_summary.get("completed_cases") == 2
        and q_summary.get("failed_cases") == 0
    )
    expanded_qualification_completed = bool(
        baseline == "camel_or_fides"
        and expanded_qualification_manifest.get("status") == "completed_diagnostic_partial"
        and expanded_qualification_manifest.get("result_eligible_for_formal_tables") is False
        and expanded_summary.get("expected_cases") == len(CAMEL_V3_P3_CASE_IDS)
        and expanded_summary.get("completed_cases") == len(CAMEL_V3_P3_CASE_IDS)
        and expanded_summary.get("failed_cases") == 0
        and expanded_summary.get("unresolved_security_cases", 0) == 0
    )
    formal_completed = bool(
        formal.get("status") == "completed_formal"
        and formal.get("result_eligible_for_formal_tables") is True
        and formal.get("exact_frozen_coverage") is True
        and f_summary.get("expected_cases") == 726
        and f_summary.get("completed_cases") == 726
        and f_summary.get("failed_cases") == 0
    )
    analysis_completed = bool(
        analysis.get("status") == "completed_formal_analysis"
        and analysis.get("result_eligible_for_formal_tables") is True
    )
    return {
        "admission_status": admission_status,
        "qualification_manifest": portable_path(qualification_manifest, root=ROOT),
        "qualification_status": qualification.get("status", "missing"),
        "qualification_completed": qualification_completed,
        "expanded_qualification_manifest": portable_path(
            _spec_path(CAMEL_V3_P3_OUTPUT) / "run_manifest.json",
            root=ROOT,
        )
        if baseline == "camel_or_fides"
        else None,
        "expanded_qualification_status": expanded_qualification_manifest.get("status", "missing")
        if baseline == "camel_or_fides"
        else None,
        "expanded_qualification_completed": expanded_qualification_completed
        if baseline == "camel_or_fides"
        else None,
        "expanded_qualification_expected_cases": expanded_summary.get("expected_cases", 0)
        if baseline == "camel_or_fides"
        else None,
        "expanded_qualification_completed_cases": expanded_summary.get("completed_cases", 0)
        if baseline == "camel_or_fides"
        else None,
        "expanded_qualification_failed_cases": expanded_summary.get("failed_cases", 0)
        if baseline == "camel_or_fides"
        else None,
        "formal_manifest": portable_path(formal_manifest, root=ROOT),
        "formal_status": formal.get("status", "missing"),
        "formal_pid": formal.get("pid"),
        "formal_pid_alive": formal_pid_alive,
        "formal_completed_cases": f_summary.get("completed_cases", 0),
        "formal_failed_cases": f_summary.get("failed_cases", 0),
        "formal_expected_cases": f_summary.get("expected_cases", 0),
        "formal_completed": formal_completed,
        "analysis_manifest": portable_path(analysis_manifest, root=ROOT),
        "analysis_status": analysis.get("status", "missing"),
        "analysis_completed": analysis_completed,
    }


def _apply_taskshield_recovery_state(state: dict[str, Any]) -> dict[str, Any]:
    """Overlay the latest sealed/failed revision without mutating old manifests."""

    spec = EXTERNAL_QUALIFICATION_SPECS["task_shield"]
    formal_root = _spec_path(str(spec["formal_output"])).resolve()
    if formal_root != DEFAULT_TASKSHIELD_V14_ROOT.resolve():
        return state
    seal = _read_json(DEFAULT_TASKSHIELD_V14_SEAL)
    analysis = _read_json(DEFAULT_TASKSHIELD_V15_ANALYSIS)
    v16_gate = _read_json(DEFAULT_TASKSHIELD_V16_G3)
    v16_summary = _read_json(DEFAULT_TASKSHIELD_V16_SUMMARY)
    sealed = seal.get("status") == "sealed_failed_formal_root"
    v15_failed = bool(
        analysis.get("status") == "completed_failed_qualification_analysis"
        and analysis.get("operational_result", {}).get("qualification_passed") is False
        and analysis.get("result_eligible_for_formal_tables") is False
    )
    if not sealed and not v15_failed:
        return state
    v16_failed = bool(
        v16_gate.get("name") == "G3_v16_expanded"
        and v16_gate.get("status") == "failed"
        and v16_gate.get("result_eligible_for_formal_tables") is False
        and v16_summary.get("status") == "completed_negative_qualification_evidence"
        and v16_summary.get("result_eligible_for_formal_tables") is False
    )
    return {
        **state,
        "formal_manifest_status": state.get("formal_status", "missing"),
        "formal_status": "sealed_failed_formal_root" if sealed else state.get("formal_status"),
        "formal_pid_alive": False if sealed else state.get("formal_pid_alive"),
        "qualification_completed": False if v15_failed else state.get("qualification_completed"),
        "latest_qualification_status": analysis.get("status", "missing"),
        "latest_qualification_passed": analysis.get("operational_result", {}).get(
            "qualification_passed"
        ),
        "latest_qualification_completed_cases": analysis.get(
            "operational_result", {}
        ).get("completed_cases", 0),
        "latest_qualification_failed_cases": analysis.get(
            "operational_result", {}
        ).get("failed_cases", 0),
        "latest_qualification_analysis": portable_path(
            DEFAULT_TASKSHIELD_V15_ANALYSIS,
            root=ROOT,
        ),
        "v14_failed_root_seal": portable_path(DEFAULT_TASKSHIELD_V14_SEAL, root=ROOT),
        "recovery_revision_required": bool(sealed and v15_failed and not v16_failed),
        "recovery_revision": "v1.6",
        "recovery_requires_explicit_decision": not v16_failed,
        "v16_gate_status": v16_gate.get("status", "missing"),
        "v16_gate": portable_path(DEFAULT_TASKSHIELD_V16_G3, root=ROOT),
        "v16_negative_evidence": portable_path(
            DEFAULT_TASKSHIELD_V16_SUMMARY,
            root=ROOT,
        ),
        "route_retired": v16_failed,
        "terminal_route_status": (
            "failed_qualification_preserved_negative_evidence"
            if v16_failed
            else "recovery_revision_pending"
        ),
    }


def build_execution_plan(
    *,
    tool_filter_monitor_path: Path = DEFAULT_TOOL_FILTER_MONITOR,
    tool_filter_admission_path: Path = DEFAULT_TOOL_FILTER_ADMISSION,
    adaptive_monitor_path: Path = DEFAULT_ADAPTIVE_MONITOR,
    public_plan_path: Path = DEFAULT_PUBLIC_PLAN,
    q2_audit_path: Path = DEFAULT_Q2_AUDIT,
    external_admission_dir: Path = PROTOCOL_ROOT / "admissions",
) -> dict[str, Any]:
    tool_monitor = _read_json(tool_filter_monitor_path)
    tool_admission = _read_json(tool_filter_admission_path)
    adaptive_monitor = _read_json(adaptive_monitor_path)
    public_plan = _read_json(public_plan_path)
    q2_audit = _read_json(q2_audit_path)
    external = _external_admission_summary(external_admission_dir)
    external_states = {
        baseline: _external_run_state(baseline, external.get(baseline, "missing"))
        for baseline in EXTERNAL_BASELINES
    }
    external_states["task_shield"] = _apply_taskshield_recovery_state(
        external_states["task_shield"]
    )
    public = _public_cell_summary(public_plan)

    active_workloads: list[dict[str, Any]] = []
    if _is_live_monitor(tool_monitor):
        active_workloads.append(
            {
                "workload": "agentdojo_tool_filter",
                "pid": tool_monitor.get("pid"),
                "completed": tool_monitor.get("counts", {}).get("completed_cases", 0),
                "failed": tool_monitor.get("counts", {}).get("failed_cases", 0),
                "expected": tool_monitor.get("counts", {}).get("expected_cases", 0),
                "health_status": tool_monitor.get("health_status"),
            }
        )
    if _is_live_monitor(adaptive_monitor):
        active_workloads.append(
            {
                "workload": "adaptive_mcts_budget",
                "pid": adaptive_monitor.get("pid"),
                "health_status": adaptive_monitor.get("health_status"),
            }
        )
    for name, state in external_states.items():
        if state.get("formal_status") == "running" and state.get("formal_pid_alive") is not False:
            spec = EXTERNAL_QUALIFICATION_SPECS[name]
            failed = int(state.get("formal_failed_cases", 0) or 0)
            health_status = (
                "running_with_failures_requires_attention"
                if failed
                else "running_progressing"
            )
            active_workloads.append(
                {
                    "workload": f"{name}_formal",
                    "pid": state.get("formal_pid"),
                    "completed": state.get("formal_completed_cases", 0),
                    "failed": failed,
                    "expected": state.get("formal_expected_cases", 0),
                    "health_status": health_status,
                    "monitor_command": (
                        state.get("monitor_command")
                        or (
                            "python -m experiments.paper_v1.benchmarks."
                            "monitor_agentdojo_official_formal_run "
                            f"--run-dir {spec['formal_output']} "
                            f"--output-dir {spec.get('monitor_output', f'protocols/paper_upgrade_v1/monitors/{name}_formal_v1')}"
                        )
                    ),
                }
            )

    resource_gate = "busy" if active_workloads else "free"
    tool_health = str(tool_monitor.get("health_status", "missing_manifest"))
    tool_admission_status = str(tool_admission.get("status", "missing"))

    if active_workloads:
        monitor_command = str(active_workloads[0].get("monitor_command", ""))
        if not monitor_command:
            monitor_command = (
                "python -m experiments.paper_v1.benchmarks."
                "monitor_agentdojo_official_formal_run "
                "--run-dir outputs/paper_upgrade_v1/baselines/"
                "agentdojo_tool_filter_official_formal_v1 "
                "--output-dir protocols/paper_upgrade_v1/monitors/tool_filter_formal_v1"
            )
        failed_active = [
            row
            for row in active_workloads
            if int(row.get("failed", 0) or 0) > 0
            or row.get("health_status") == "running_with_failures_requires_attention"
        ]
        if failed_active:
            next_action = {
                "action_id": "review_failed_formal_workload",
                "status": "ready_read_only_recovery_package",
                "resource_kind": "cpu_read_only",
                "command": (
                    "python -m experiments.paper_v1.benchmarks."
                    "prepare_taskshield_v14_recovery_package"
                ),
                "supporting_monitor_command": monitor_command,
                "reason": (
                    "A live formal workload already has failed cases, so formal "
                    "admission is blocked unless a new explicit failure-recovery "
                    "revision is created. Generate a read-only recovery package; "
                    "do not start competing model jobs, retry cases, exclude rows, "
                    "or promote partial evidence automatically."
                ),
            }
        else:
            next_action = {
                "action_id": "monitor_active_formal_workload",
                "status": "ready_read_only",
                "resource_kind": "none",
                "command": monitor_command,
                "reason": "A live formal workload owns Ollama/GPU; no competing model job is safe.",
            }
    elif tool_health == "completed_formal_admitted" and tool_admission_status not in ADMITTED_STATUSES:
        next_action = {
            "action_id": "analyze_tool_filter",
            "status": "ready_requires_explicit_execution",
            "resource_kind": "cpu",
            "command": (
                "python -m experiments.paper_v1.benchmarks."
                "analyze_agentdojo_official_tool_filter_formal "
                "--run-dir outputs/paper_upgrade_v1/baselines/"
                "agentdojo_tool_filter_official_formal_v1"
            ),
            "reason": "The exact formal run is complete; analysis must precede registry admission.",
        }
    elif tool_admission_status in ADMITTED_STATUSES:
        pending_external = next(
            (
                name
                for name in EXTERNAL_BASELINES
                if external.get(name) not in EXTERNAL_ADMITTED_STATUSES
                and not external_states[name].get("route_retired", False)
            ),
            None,
        )
        if pending_external:
            state = external_states[pending_external]
            if pending_external == "task_shield" and state.get(
                "recovery_revision_required"
            ):
                action_id = "review_task_shield_v15_failed_qualification"
                command = (
                    "python -m experiments.paper_v1.benchmarks."
                    "analyze_taskshield_v15_expanded_qualification"
                )
                reason = (
                    "Task Shield v1.4 is sealed and v1.5 failed its fresh 12-case "
                    "qualification (11 completed, 1 timeout failure). Review the "
                    "diagnostic analysis and require an explicit v1.6 decision; never "
                    "resume v1.4, edit v1.5, or selectively retry the failed row."
                )
                resource_kind = "cpu_read_only"
                action_status = "blocked_explicit_revision_decision"
            elif pending_external == "progent":
                next_action = _progent_v14_next_action(state)
                return {
                    "schema_version": "paper-q2-formal-execution-plan-1.0",
                    "plan_version": PLAN_VERSION,
                    "status": "completed_read_only_plan",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "resource_gate": resource_gate,
                    "active_workloads": active_workloads,
                    "next_safe_action": next_action,
                    "tool_filter": {
                        "health_status": tool_health,
                        "admission_status": tool_admission_status,
                        "monitor_path": portable_path(tool_filter_monitor_path, root=ROOT),
                    },
                    "external_admissions": external,
                    "external_states": external_states,
                    "adaptive": {
                        "health_status": str(adaptive_monitor.get("health_status", "missing_manifest")),
                        "monitor_path": portable_path(adaptive_monitor_path, root=ROOT),
                    },
                    "public_matrix": public,
                    "q2_readiness": {
                        "raw_score": q2_audit.get("raw_score"),
                        "capped_score": q2_audit.get("capped_score"),
                        "goal_80_met": q2_audit.get("goal_80_met"),
                        "goal_90_met": q2_audit.get("goal_90_met"),
                    },
                    "boundary": (
                        "Read-only execution planning only. This artifact never starts, retries, analyzes, "
                        "admits or excludes a formal case and cannot change Q2 readiness by itself."
                    ),
                }
            elif state["admission_status"] in EXTERNAL_READY_STATUSES:
                action_id = f"write_{pending_external}_admission"
                command = _external_admission_command(pending_external) + " --write-registries"
                reason = (
                    f"{pending_external} has a clean dry-run admission; write both registries "
                    "so the source-backed baseline becomes formal-ready."
                )
                resource_kind = "cpu"
                action_status = "ready_requires_explicit_execution"
            elif not state["qualification_completed"]:
                action_id = f"qualify_{pending_external}"
                command = _external_qualification_command(pending_external)
                reason = (
                    f"{pending_external} is the next frozen strong-baseline qualification; "
                    "run one utility and one security case in a fresh qualification-only root, "
                    "retain all failures, and do not request formal admission."
                )
                resource_kind = "ollama_gpu"
                action_status = "ready_requires_explicit_execution"
            elif (
                pending_external == "camel_or_fides"
                and not state.get("expanded_qualification_completed")
            ):
                action_id = "run_camel_or_fides_v3_p3_8case"
                command = _camel_v3_p3_command()
                reason = (
                    "CaMeL v3 two-case qualification is only a smoke gate. Run the "
                    "fresh 8-case P3 panel across banking/slack/workspace/travel "
                    "before considering any 726-case formal workload."
                )
                resource_kind = "ollama_gpu"
                action_status = "ready_requires_explicit_execution"
            elif pending_external == "camel_or_fides":
                action_id = "review_camel_or_fides_v3_p3_before_p4"
                command = (
                    "python -m experiments.paper_v1.benchmarks."
                    "analyze_camel_source_backed_formal_v3 "
                    f"--run-dir {CAMEL_V3_P3_OUTPUT} "
                    f"--output-dir {CAMEL_V3_P3_OUTPUT}/analysis --allow-diagnostic"
                )
                reason = (
                    "CaMeL v3 P3 is complete. Do not start the 726-case formal "
                    "run yet; review P3 utility/latency first and define the P4/P5 "
                    "expanded qualification gates in a fresh protocol revision."
                )
                resource_kind = "cpu_read_only"
                action_status = "blocked_staged_qualification_required"
            elif not state["formal_completed"]:
                action_id = f"run_{pending_external}_formal"
                command = _external_formal_command(pending_external)
                reason = (
                    f"{pending_external} qualification is complete; run the exact 726-case "
                    "formal workload with explicit formal admission and resume support."
                )
                resource_kind = "ollama_gpu"
                action_status = "ready_requires_explicit_execution"
            elif not state["analysis_completed"]:
                action_id = f"analyze_{pending_external}_formal"
                command = _external_analysis_command(pending_external)
                reason = (
                    f"{pending_external} formal run is complete; produce the hash-linked "
                    "formal analysis before registry admission."
                )
                resource_kind = "cpu"
                action_status = "ready_requires_explicit_execution"
            else:
                action_id = f"admit_{pending_external}_formal"
                command = _external_admission_command(pending_external)
                reason = (
                    f"{pending_external} formal run and analysis are complete; run a "
                    "fail-closed admission dry-run before registry writes."
                )
                resource_kind = "cpu"
                action_status = "ready_requires_explicit_execution"
            next_action = {
                "action_id": action_id,
                "status": action_status,
                "resource_kind": resource_kind,
                "command": command,
                "reason": reason,
            }
        else:
            command = _public_command(public.get("first_pending"))
            next_action = {
                "action_id": "run_next_public_benchmark_cell",
                "status": "ready_requires_explicit_execution" if command else "blocked_no_pending_cell",
                "resource_kind": "ollama_gpu",
                "command": command,
                "reason": "All external admissions are complete; continue the frozen public matrix.",
            }
    else:
        next_action = {
            "action_id": "review_tool_filter_terminal_state",
            "status": "blocked_manual_review",
            "resource_kind": "none",
            "command": "",
            "reason": (
                f"ToolFilter health is {tool_health!r} and admission is "
                f"{tool_admission_status!r}; do not retry or promote automatically."
            ),
        }

    return {
        "schema_version": "paper-q2-formal-execution-plan-1.0",
        "plan_version": PLAN_VERSION,
        "status": "completed_read_only_plan",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "resource_gate": resource_gate,
        "active_workloads": active_workloads,
        "next_safe_action": next_action,
        "tool_filter": {
            "health_status": tool_health,
            "admission_status": tool_admission_status,
            "monitor_path": portable_path(tool_filter_monitor_path, root=ROOT),
        },
        "external_admissions": external,
        "external_states": external_states,
        "adaptive": {
            "health_status": str(adaptive_monitor.get("health_status", "missing_manifest")),
            "monitor_path": portable_path(adaptive_monitor_path, root=ROOT),
        },
        "public_matrix": public,
        "q2_readiness": {
            "raw_score": q2_audit.get("raw_score"),
            "capped_score": q2_audit.get("capped_score"),
            "goal_80_met": q2_audit.get("goal_80_met"),
            "goal_90_met": q2_audit.get("goal_90_met"),
        },
        "boundary": (
            "Read-only execution planning only. This artifact never starts, retries, analyzes, "
            "admits or excludes a formal case and cannot change Q2 readiness by itself."
        ),
    }


def _write_markdown(path: Path, plan: Mapping[str, Any]) -> None:
    action = plan["next_safe_action"]
    lines = [
        "# Q2 formal execution plan",
        "",
        f"- Status: `{plan['status']}`",
        f"- Resource gate: `{plan['resource_gate']}`",
        f"- Next action: `{action['action_id']}`",
        f"- Action status: `{action['status']}`",
        f"- Reason: {action['reason']}",
        f"- Command: `{action['command'] or 'none; manual review required'}`",
        "",
        "## Active workloads",
        "",
    ]
    if plan["active_workloads"]:
        for row in plan["active_workloads"]:
            lines.append(
                f"- `{row['workload']}`: health `{row['health_status']}`, PID `{row.get('pid')}`"
            )
    else:
        lines.append("- None.")
    lines.extend(["", "## Evidence boundary", "", str(plan["boundary"]), ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    plan = build_execution_plan()
    if not args.no_write:
        output_dir = args.output_dir.resolve()
        _write_json(output_dir / "q2_formal_execution_plan_v1.json", plan)
        _write_markdown(output_dir / "q2_formal_execution_plan_v1.md", plan)
    print(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

