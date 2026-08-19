from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import experiments.paper_v1.benchmarks.plan_q2_formal_execution as planner
from experiments.paper_v1.benchmarks.plan_q2_formal_execution import (
    EXTERNAL_BASELINES,
    _external_qualification_command,
    build_execution_plan,
)
from experiments.paper_v1.benchmarks.common import portable_path


def _write(path: Path, value: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _inputs(tmp_path: Path, *, live: bool, completed: bool = False) -> dict[str, Path]:
    health = "completed_formal_admitted" if completed else "running_progressing"
    monitor = _write(
        tmp_path / "tool.json",
        {
            "health_status": health,
            "pid": 123,
            "pid_alive": live,
            "counts": {"completed_cases": 400, "failed_cases": 0, "expected_cases": 726},
        },
    )
    adaptive = _write(
        tmp_path / "adaptive.json",
        {"health_status": "missing_manifest", "pid_alive": False},
    )
    cell_manifest = _write(tmp_path / "cell" / "manifest.json", {"status": "pending"})
    public = _write(
        tmp_path / "public.json",
        {
            "expected_cell_count": 1,
            "expected_case_runs": 726,
            "cells": [
                {
                    "cell_id": "agentdojo__qwen__m3_full__r1",
                    "benchmark": "agentdojo",
                    "model": "qwen",
                    "condition_id": "m3_full",
                    "manifest_path": str(cell_manifest),
                }
            ],
        },
    )
    q2 = _write(
        tmp_path / "q2.json",
        {"raw_score": 63.5, "capped_score": 60.0, "goal_90_met": False},
    )
    admission = _write(
        tmp_path / "tool_admission.json",
        {"status": "blocked_not_formally_admitted"},
    )
    admissions = tmp_path / "admissions"
    for name in EXTERNAL_BASELINES:
        _write(admissions / f"{name}_formal_admission_v1.json", {"status": "blocked"})
    return {
        "tool_filter_monitor_path": monitor,
        "tool_filter_admission_path": admission,
        "adaptive_monitor_path": adaptive,
        "public_plan_path": public,
        "q2_audit_path": q2,
        "external_admission_dir": admissions,
    }


def _isolate_external_specs(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    specs = {}
    for name, spec in planner.EXTERNAL_QUALIFICATION_SPECS.items():
        specs[name] = {
            **spec,
            "freeze": str(tmp_path / "freezes" / f"{name}.json"),
            "output": str(tmp_path / "qualifications" / name),
            "output_p3": str(tmp_path / "qualifications" / f"{name}_p3"),
            "output_p4": str(tmp_path / "qualifications" / f"{name}_p4"),
            "output_p5": str(tmp_path / "qualifications" / f"{name}_p5"),
            "analysis_p3": str(tmp_path / "analysis" / f"{name}_p3"),
            "analysis_p4": str(tmp_path / "analysis" / f"{name}_p4"),
            "analysis_p5": str(tmp_path / "analysis" / f"{name}_p5"),
            "formal_output": str(tmp_path / "formal" / name),
        }
    monkeypatch.setattr(planner, "EXTERNAL_QUALIFICATION_SPECS", specs)


def _retire_taskshield(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    task_spec = planner.EXTERNAL_QUALIFICATION_SPECS["task_shield"]
    formal_root = Path(task_spec["formal_output"])
    seal = _write(tmp_path / "seal.json", {"status": "sealed_failed_formal_root"})
    v15_analysis = _write(
        tmp_path / "v15-analysis.json",
        {
            "status": "completed_failed_qualification_analysis",
            "result_eligible_for_formal_tables": False,
            "operational_result": {
                "qualification_passed": False,
                "completed_cases": 11,
                "failed_cases": 1,
            },
        },
    )
    v16_g3 = _write(
        tmp_path / "g3.json",
        {
            "name": "G3_v16_expanded",
            "status": "failed",
            "result_eligible_for_formal_tables": False,
        },
    )
    v16_summary = _write(
        tmp_path / "v16-summary.json",
        {
            "status": "completed_negative_qualification_evidence",
            "result_eligible_for_formal_tables": False,
        },
    )
    monkeypatch.setattr(planner, "DEFAULT_TASKSHIELD_V14_ROOT", formal_root)
    monkeypatch.setattr(planner, "DEFAULT_TASKSHIELD_V14_SEAL", seal)
    monkeypatch.setattr(planner, "DEFAULT_TASKSHIELD_V15_ANALYSIS", v15_analysis)
    monkeypatch.setattr(planner, "DEFAULT_TASKSHIELD_V16_G3", v16_g3)
    monkeypatch.setattr(planner, "DEFAULT_TASKSHIELD_V16_SUMMARY", v16_summary)


def test_live_workload_forces_read_only_monitor_action(tmp_path: Path, monkeypatch) -> None:
    _isolate_external_specs(tmp_path, monkeypatch)
    plan = build_execution_plan(**_inputs(tmp_path, live=True))

    assert plan["resource_gate"] == "busy"
    assert plan["next_safe_action"]["action_id"] == "monitor_active_formal_workload"
    assert plan["next_safe_action"]["resource_kind"] == "none"
    assert plan["active_workloads"][0]["completed"] == 400


def test_completed_tool_filter_requires_analysis_before_admission(tmp_path: Path, monkeypatch) -> None:
    _isolate_external_specs(tmp_path, monkeypatch)
    plan = build_execution_plan(**_inputs(tmp_path, live=False, completed=True))

    assert plan["resource_gate"] == "free"
    assert plan["next_safe_action"]["action_id"] == "analyze_tool_filter"
    assert "analyze_agentdojo_official_tool_filter_formal" in plan["next_safe_action"]["command"]


def test_admitted_tool_filter_moves_to_first_external_qualification(tmp_path: Path, monkeypatch) -> None:
    _isolate_external_specs(tmp_path, monkeypatch)
    paths = _inputs(tmp_path, live=False, completed=True)
    _write(paths["tool_filter_admission_path"], {"status": "admitted"})

    plan = build_execution_plan(**paths)

    assert plan["next_safe_action"]["action_id"] == "qualify_task_shield"
    assert plan["next_safe_action"]["resource_kind"] == "ollama_gpu"
    command = plan["next_safe_action"]["command"]
    assert "run_taskshield_paper_formal" in command
    assert command.count("--case-id") == 2
    assert "--no-resume" in command
    assert "--admit-formal" not in command
    assert str(tmp_path / "qualifications" / "task_shield") in command


def test_registry_updated_tool_filter_counts_as_admitted(tmp_path: Path, monkeypatch) -> None:
    _isolate_external_specs(tmp_path, monkeypatch)
    paths = _inputs(tmp_path, live=False, completed=True)
    _write(paths["tool_filter_admission_path"], {"status": "admitted_registry_updated"})

    plan = build_execution_plan(**paths)

    assert plan["next_safe_action"]["action_id"] == "qualify_task_shield"


def test_completed_qualification_moves_to_full_formal_run(tmp_path: Path, monkeypatch) -> None:
    _isolate_external_specs(tmp_path, monkeypatch)
    paths = _inputs(tmp_path, live=False, completed=True)
    _write(paths["tool_filter_admission_path"], {"status": "admitted_registry_updated"})
    task_spec = planner.EXTERNAL_QUALIFICATION_SPECS["task_shield"]
    _write(
        Path(task_spec["output"]) / "run_manifest.json",
        {
            "status": "completed_diagnostic_partial",
            "result_eligible_for_formal_tables": False,
            "summary": {"expected_cases": 2, "completed_cases": 2, "failed_cases": 0},
        },
    )

    plan = build_execution_plan(**paths)

    assert plan["next_safe_action"]["action_id"] == "run_task_shield_formal"
    assert "--admit-formal" in plan["next_safe_action"]["command"]


def test_running_external_formal_workload_blocks_competing_model_job(tmp_path: Path, monkeypatch) -> None:
    _isolate_external_specs(tmp_path, monkeypatch)
    paths = _inputs(tmp_path, live=False, completed=True)
    _write(paths["tool_filter_admission_path"], {"status": "admitted_registry_updated"})
    task_spec = planner.EXTERNAL_QUALIFICATION_SPECS["task_shield"]
    _write(
        Path(task_spec["formal_output"]) / "run_manifest.json",
        {
            "status": "running",
            "pid": os.getpid(),
            "summary": {"expected_cases": 726, "completed_cases": 3, "failed_cases": 0},
        },
    )

    plan = build_execution_plan(**paths)

    assert plan["resource_gate"] == "busy"
    assert plan["next_safe_action"]["action_id"] == "monitor_active_formal_workload"
    assert "task_shield_formal_v14" in plan["next_safe_action"]["command"]
    assert plan["active_workloads"][0]["workload"] == "task_shield_formal"


def test_planner_distinguishes_live_and_exited_processes() -> None:
    assert planner._pid_alive(os.getpid()) is True
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait(timeout=10)
    assert planner._pid_alive(child.pid) is False


def test_running_external_formal_with_failed_case_requires_manual_review(
    tmp_path: Path, monkeypatch
) -> None:
    _isolate_external_specs(tmp_path, monkeypatch)
    paths = _inputs(tmp_path, live=False, completed=True)
    _write(paths["tool_filter_admission_path"], {"status": "admitted_registry_updated"})
    task_spec = planner.EXTERNAL_QUALIFICATION_SPECS["task_shield"]
    _write(
        Path(task_spec["formal_output"]) / "run_manifest.json",
        {
            "status": "running",
            "pid": os.getpid(),
            "summary": {"expected_cases": 726, "completed_cases": 26, "failed_cases": 1},
        },
    )

    plan = build_execution_plan(**paths)

    assert plan["resource_gate"] == "busy"
    assert plan["next_safe_action"]["action_id"] == "review_failed_formal_workload"
    assert plan["next_safe_action"]["status"] == "ready_read_only_recovery_package"
    assert plan["next_safe_action"]["resource_kind"] == "cpu_read_only"
    assert "prepare_taskshield_v14_recovery_package" in plan["next_safe_action"]["command"]
    assert "monitor_agentdojo_official_formal_run" in plan["next_safe_action"][
        "supporting_monitor_command"
    ]
    assert "retry" in plan["next_safe_action"]["reason"]
    assert plan["active_workloads"][0]["failed"] == 1
    assert (
        plan["active_workloads"][0]["health_status"]
        == "running_with_failures_requires_attention"
    )


def test_sealed_v14_and_failed_v15_block_resume_and_require_new_revision(
    tmp_path: Path, monkeypatch
) -> None:
    _isolate_external_specs(tmp_path, monkeypatch)
    paths = _inputs(tmp_path, live=False, completed=True)
    _write(paths["tool_filter_admission_path"], {"status": "admitted_registry_updated"})
    task_spec = planner.EXTERNAL_QUALIFICATION_SPECS["task_shield"]
    formal_root = Path(task_spec["formal_output"])
    _write(
        formal_root / "run_manifest.json",
        {
            "status": "running",
            "pid": 9804,
            "summary": {"expected_cases": 726, "completed_cases": 24, "failed_cases": 2},
        },
    )
    seal = _write(
        tmp_path / "seal.json",
        {"status": "sealed_failed_formal_root"},
    )
    analysis = _write(
        tmp_path / "analysis.json",
        {
            "status": "completed_failed_qualification_analysis",
            "result_eligible_for_formal_tables": False,
            "operational_result": {
                "qualification_passed": False,
                "completed_cases": 11,
                "failed_cases": 1,
            },
        },
    )
    monkeypatch.setattr(planner, "DEFAULT_TASKSHIELD_V14_ROOT", formal_root)
    monkeypatch.setattr(planner, "DEFAULT_TASKSHIELD_V14_SEAL", seal)
    monkeypatch.setattr(planner, "DEFAULT_TASKSHIELD_V15_ANALYSIS", analysis)
    monkeypatch.setattr(planner, "DEFAULT_TASKSHIELD_V16_G3", tmp_path / "missing-g3.json")
    monkeypatch.setattr(
        planner,
        "DEFAULT_TASKSHIELD_V16_SUMMARY",
        tmp_path / "missing-v16-summary.json",
    )

    plan = build_execution_plan(**paths)

    assert plan["resource_gate"] == "free"
    assert plan["external_states"]["task_shield"]["formal_status"] == "sealed_failed_formal_root"
    assert plan["external_states"]["task_shield"]["recovery_revision_required"] is True
    assert plan["next_safe_action"]["action_id"] == "review_task_shield_v15_failed_qualification"
    assert plan["next_safe_action"]["status"] == "blocked_explicit_revision_decision"
    assert "run_taskshield_paper_formal_v14" not in plan["next_safe_action"]["command"]
    assert "v1.6" in plan["next_safe_action"]["reason"]


def test_failed_v16_g3_retires_taskshield_and_routes_to_progent(
    tmp_path: Path, monkeypatch
) -> None:
    _isolate_external_specs(tmp_path, monkeypatch)
    paths = _inputs(tmp_path, live=False, completed=True)
    _write(paths["tool_filter_admission_path"], {"status": "admitted_registry_updated"})
    task_spec = planner.EXTERNAL_QUALIFICATION_SPECS["task_shield"]
    formal_root = Path(task_spec["formal_output"])
    seal = _write(tmp_path / "seal.json", {"status": "sealed_failed_formal_root"})
    v15_analysis = _write(
        tmp_path / "v15-analysis.json",
        {
            "status": "completed_failed_qualification_analysis",
            "result_eligible_for_formal_tables": False,
            "operational_result": {
                "qualification_passed": False,
                "completed_cases": 11,
                "failed_cases": 1,
            },
        },
    )
    v16_g3 = _write(
        tmp_path / "g3.json",
        {
            "name": "G3_v16_expanded",
            "status": "failed",
            "result_eligible_for_formal_tables": False,
        },
    )
    v16_summary = _write(
        tmp_path / "v16-summary.json",
        {
            "status": "completed_negative_qualification_evidence",
            "result_eligible_for_formal_tables": False,
        },
    )
    monkeypatch.setattr(planner, "DEFAULT_TASKSHIELD_V14_ROOT", formal_root)
    monkeypatch.setattr(planner, "DEFAULT_TASKSHIELD_V14_SEAL", seal)
    monkeypatch.setattr(planner, "DEFAULT_TASKSHIELD_V15_ANALYSIS", v15_analysis)
    monkeypatch.setattr(planner, "DEFAULT_TASKSHIELD_V16_G3", v16_g3)
    monkeypatch.setattr(planner, "DEFAULT_TASKSHIELD_V16_SUMMARY", v16_summary)

    plan = build_execution_plan(**paths)

    task_state = plan["external_states"]["task_shield"]
    assert task_state["route_retired"] is True
    assert task_state["terminal_route_status"] == (
        "failed_qualification_preserved_negative_evidence"
    )
    assert plan["next_safe_action"]["action_id"] == "build_progent_v14_freeze"
    assert "build_progent_source_backed_formal_freeze_v14" in plan["next_safe_action"]["command"]


def test_progent_v14_g1_pass_routes_to_p3_selection(tmp_path: Path, monkeypatch) -> None:
    _isolate_external_specs(tmp_path, monkeypatch)
    paths = _inputs(tmp_path, live=False, completed=True)
    _write(paths["tool_filter_admission_path"], {"status": "admitted_registry_updated"})
    _retire_taskshield(tmp_path, monkeypatch)
    spec = planner.EXTERNAL_QUALIFICATION_SPECS["progent"]
    _write(Path(spec["freeze"]), {"status": "completed_frozen_formal_protocol"})
    g1 = _write(tmp_path / "g1.json", {"status": "passed"})
    monkeypatch.setattr(planner, "DEFAULT_PROGENT_V14_G1", g1)

    plan = build_execution_plan(**paths)

    assert plan["next_safe_action"]["action_id"] == "run_progent_v14_p3"
    assert "--selection p3" in plan["next_safe_action"]["command"]
    assert "--case-id" not in plan["next_safe_action"]["command"]


def test_progent_v14_terminal_p3_requires_gate_analysis(tmp_path: Path, monkeypatch) -> None:
    _isolate_external_specs(tmp_path, monkeypatch)
    paths = _inputs(tmp_path, live=False, completed=True)
    _write(paths["tool_filter_admission_path"], {"status": "admitted_registry_updated"})
    _retire_taskshield(tmp_path, monkeypatch)
    spec = planner.EXTERNAL_QUALIFICATION_SPECS["progent"]
    _write(Path(spec["freeze"]), {"status": "completed_frozen_formal_protocol"})
    g1 = _write(tmp_path / "g1.json", {"status": "passed"})
    monkeypatch.setattr(planner, "DEFAULT_PROGENT_V14_G1", g1)
    _write(
        Path(spec["output_p3"]) / "run_manifest.json",
        {
            "status": "completed_qualification",
            "exact_selected_coverage": True,
            "zero_unresolved": True,
            "summary": {"expected_cases": 8, "completed_cases": 8, "failed_cases": 0},
        },
    )

    plan = build_execution_plan(**paths)

    assert plan["next_safe_action"]["action_id"] == "analyze_progent_v14_p3"
    assert "--phase p3" in plan["next_safe_action"]["command"]


def test_progent_v14_p3_gate_pass_routes_to_p4(tmp_path: Path, monkeypatch) -> None:
    _isolate_external_specs(tmp_path, monkeypatch)
    paths = _inputs(tmp_path, live=False, completed=True)
    _write(paths["tool_filter_admission_path"], {"status": "admitted_registry_updated"})
    _retire_taskshield(tmp_path, monkeypatch)
    spec = planner.EXTERNAL_QUALIFICATION_SPECS["progent"]
    _write(Path(spec["freeze"]), {"status": "completed_frozen_formal_protocol"})
    g1 = _write(tmp_path / "g1.json", {"status": "passed"})
    monkeypatch.setattr(planner, "DEFAULT_PROGENT_V14_G1", g1)
    _write(
        Path(spec["output_p3"]) / "run_manifest.json",
        {
            "status": "completed_qualification",
            "exact_selected_coverage": True,
            "zero_unresolved": True,
            "summary": {"expected_cases": 8, "completed_cases": 8, "failed_cases": 0},
        },
    )
    _write(Path(spec["analysis_p3"]) / "gate.json", {"status": "passed"})

    plan = build_execution_plan(**paths)

    assert plan["next_safe_action"]["action_id"] == "run_progent_v14_p4"
    assert "--selection p4" in plan["next_safe_action"]["command"]


def test_progent_v14_p3_gate_failure_routes_to_next_baseline(
    tmp_path: Path, monkeypatch
) -> None:
    _isolate_external_specs(tmp_path, monkeypatch)
    paths = _inputs(tmp_path, live=False, completed=True)
    _write(paths["tool_filter_admission_path"], {"status": "admitted_registry_updated"})
    _retire_taskshield(tmp_path, monkeypatch)
    spec = planner.EXTERNAL_QUALIFICATION_SPECS["progent"]
    _write(Path(spec["freeze"]), {"status": "completed_frozen_formal_protocol"})
    g1 = _write(tmp_path / "g1.json", {"status": "passed"})
    monkeypatch.setattr(planner, "DEFAULT_PROGENT_V14_G1", g1)
    _write(
        Path(spec["output_p3"]) / "run_manifest.json",
        {
            "status": "completed_qualification",
            "exact_selected_coverage": True,
            "zero_unresolved": True,
            "summary": {"expected_cases": 8, "completed_cases": 8, "failed_cases": 0},
        },
    )
    _write(Path(spec["analysis_p3"]) / "gate.json", {"status": "failed"})

    plan = build_execution_plan(**paths)

    assert plan["external_states"]["progent"]["route_retired"] is True
    assert plan["next_safe_action"]["action_id"] == "qualify_camel_or_fides"
    assert "run_camel_source_backed_formal" in plan["next_safe_action"]["command"]


def test_camel_v3_two_case_qualification_routes_to_p3_not_formal(
    tmp_path: Path, monkeypatch
) -> None:
    _isolate_external_specs(tmp_path, monkeypatch)
    monkeypatch.setattr(
        planner,
        "CAMEL_V3_P3_OUTPUT",
        str(tmp_path / "qualifications" / "camel_v3_p3_8case"),
    )
    paths = _inputs(tmp_path, live=False, completed=True)
    _write(paths["tool_filter_admission_path"], {"status": "admitted_registry_updated"})
    _retire_taskshield(tmp_path, monkeypatch)
    progent = planner.EXTERNAL_QUALIFICATION_SPECS["progent"]
    _write(Path(progent["freeze"]), {"status": "completed_frozen_formal_protocol"})
    g1 = _write(tmp_path / "g1.json", {"status": "passed"})
    monkeypatch.setattr(planner, "DEFAULT_PROGENT_V14_G1", g1)
    _write(
        Path(progent["output_p3"]) / "run_manifest.json",
        {
            "status": "completed_qualification",
            "exact_selected_coverage": True,
            "zero_unresolved": True,
            "summary": {"expected_cases": 8, "completed_cases": 8, "failed_cases": 0},
        },
    )
    _write(Path(progent["analysis_p3"]) / "gate.json", {"status": "failed"})
    camel = planner.EXTERNAL_QUALIFICATION_SPECS["camel_or_fides"]
    _write(
        Path(camel["output"]) / "run_manifest.json",
        {
            "status": "completed_diagnostic_partial",
            "result_eligible_for_formal_tables": False,
            "summary": {"expected_cases": 2, "completed_cases": 2, "failed_cases": 0},
        },
    )

    plan = build_execution_plan(**paths)

    assert plan["next_safe_action"]["action_id"] == "run_camel_or_fides_v3_p3_8case"
    assert "--admit-formal" not in plan["next_safe_action"]["command"]
    assert "camel_v3_p3_8case" in plan["next_safe_action"]["command"]


def test_progent_v14_p5_gate_pass_blocks_for_p6_authorization(
    tmp_path: Path, monkeypatch
) -> None:
    _isolate_external_specs(tmp_path, monkeypatch)
    paths = _inputs(tmp_path, live=False, completed=True)
    _write(paths["tool_filter_admission_path"], {"status": "admitted_registry_updated"})
    _retire_taskshield(tmp_path, monkeypatch)
    spec = planner.EXTERNAL_QUALIFICATION_SPECS["progent"]
    _write(Path(spec["freeze"]), {"status": "completed_frozen_formal_protocol"})
    g1 = _write(tmp_path / "g1.json", {"status": "passed"})
    monkeypatch.setattr(planner, "DEFAULT_PROGENT_V14_G1", g1)
    for phase, count in (("p3", 8), ("p4", 16), ("p5", 32)):
        _write(
            Path(spec[f"output_{phase}"]) / "run_manifest.json",
            {
                "status": "completed_qualification",
                "exact_selected_coverage": True,
                "zero_unresolved": True,
                "summary": {
                    "expected_cases": count,
                    "completed_cases": count,
                    "failed_cases": 0,
                },
            },
        )
        _write(Path(spec[f"analysis_{phase}"]) / "gate.json", {"status": "passed"})

    plan = build_execution_plan(**paths)

    assert plan["next_safe_action"]["action_id"] == "request_progent_v14_p6_authorization"
    assert plan["next_safe_action"]["status"] == "blocked_explicit_formal_authorization"
    assert plan["next_safe_action"]["resource_kind"] == "none"


def test_ipiguard_retry_uses_a_fresh_output_root() -> None:
    command = _external_qualification_command("ipiguard")

    assert "ipiguard_source_backed_qualification_v2" in command
    assert "ipiguard_source_backed_qualification_v1" not in command
    assert command.count("--case-id") == 2
    assert "--no-resume" in command


def test_all_external_admitted_selects_first_pending_public_cell(tmp_path: Path, monkeypatch) -> None:
    _isolate_external_specs(tmp_path, monkeypatch)
    paths = _inputs(tmp_path, live=False, completed=True)
    _write(paths["tool_filter_admission_path"], {"status": "admitted"})
    for name in EXTERNAL_BASELINES:
        _write(
            paths["external_admission_dir"] / f"{name}_formal_admission_v1.json",
            {"status": "admitted_formal_result"},
        )

    plan = build_execution_plan(**paths)

    assert plan["next_safe_action"]["action_id"] == "run_next_public_benchmark_cell"
    assert "run_agentdojo_formal_cell" in plan["next_safe_action"]["command"]
    assert plan["public_matrix"]["status_counts"] == {"pending": 1}


def test_q2_execution_plan_uses_relative_paths_inside_repo() -> None:
    root = Path("E:/portable") / ("M3_PI_" + "Guard_test")

    assert (
        portable_path(root / "protocols" / "monitor.json", root=root)
        == "protocols/monitor.json"
    )
    assert portable_path(Path("D:/external/model"), root=root) == str(
        Path("D:/external/model").resolve()
    )

