from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_conventions_audit():
    script = REPO_ROOT / "scripts" / "audit_project_conventions.py"
    spec = importlib.util.spec_from_file_location("audit_project_conventions", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_harness_engineering_is_separate_from_project_source() -> None:
    harness_paths = (
        "harness/README.md",
        "harness/项目上下文.md",
        "harness/config/permissions.yaml",
        "harness/config/policies.md",
        "harness/config/workflow.md",
        "harness/state/current-task.md",
        "harness/state/progress.md",
        "harness/state/session-handoff.md",
        "harness/specs/product-spec.md",
        "harness/features/feature_list.json",
        "harness/tasks/task.md",
        "harness/scripts/verify.ps1",
        "harness/scripts/test.ps1",
        "harness/workspaces/runpro/10_analysis/approval-gate.md",
    )
    assert all((REPO_ROOT / relative).is_file() for relative in harness_paths)

    project_directories = (
        "m3_core",
        "m3_guard",
        "m3_eval",
        "m3_attacks",
        "experiments",
        "protocols",
        "schemas",
        "fixtures",
        "tests",
        "scripts",
    )
    assert all((REPO_ROOT / relative).is_dir() for relative in project_directories)

    legacy_harness_paths = (
        "README_AGENT.md",
        ".agent",
        "features",
        "specs",
        "tasks",
        "runpro_workspace",
        "agent/current-task.md",
        "agent/failure-log.md",
        "agent/memory.md",
        "agent/progress.md",
        "agent/session-handoff.md",
        "agent/task-history.md",
    )
    assert all(not (REPO_ROOT / relative).exists() for relative in legacy_harness_paths)

    feature_list = json.loads(
        (REPO_ROOT / "harness/features/feature_list.json").read_text(encoding="utf-8")
    )
    assert feature_list["schemaVersion"] == "1.0"
    assert (REPO_ROOT / "AGENTS.md").is_file()
    assert (REPO_ROOT / "agent/README.md").is_file()


def test_approved_document_renames_use_exact_canonical_names() -> None:
    expected = {
        REPO_ROOT / "docs": {
            "项目移交报告.md",
            "项目完整综述.md",
            "系统架构.md",
            "运行手册.md",
            "数据集说明.md",
            "伦理与适用范围.md",
            "证据索引.md",
            "移交与论文检查清单.md",
            "README.md",
        },
        REPO_ROOT / "docs" / "presentation": {"ppt_result_notes.md"},
        REPO_ROOT / "docs" / "archive": {"README.md", "report_v0_3.md"},
        REPO_ROOT / "experiments": {"e17_source_index.md"},
        REPO_ROOT / "harness" / "tasks": {"m3-expansion-001.md"},
    }
    forbidden = {
        REPO_ROOT / "docs": {
            "PROJECT_HANDOFF.md",
            "PROJECT_OVERVIEW.md",
            "SYSTEM_ARCHITECTURE.md",
            "RUNBOOK.md",
            "DATASET_CARD.md",
            "ETHICS_AND_SCOPE.md",
            "SUBMISSION_EVIDENCE_INDEX.md",
            "RELEASE_CHECKLIST.md",
            "PPT_result_notes.md",
            "report_v0.3.md",
        },
        REPO_ROOT / "experiments": {"E17_SOURCE_INDEX.md"},
        REPO_ROOT / "harness" / "tasks": {"M3-EXPANSION-001.md"},
    }
    for directory, required_names in expected.items():
        observed = {path.name for path in directory.iterdir()}
        assert required_names <= observed
    for directory, forbidden_names in forbidden.items():
        observed = {path.name for path in directory.iterdir()}
        assert not (forbidden_names & observed)


def test_superseded_documents_are_archived_without_breaking_current_entries() -> None:
    current_entries = (
        "docs/数据集说明.md",
        "docs/移交与论文检查清单.md",
        "docs/证据索引.md",
        "docs/report_sections/README.md",
        "docs/research/progent_v13_failure_analysis.md",
        "docs/research/taskshield_v15_failure_analysis.md",
        "docs/research/taskshield_v16_execution_plan.md",
        "docs/research/taskshield_v16_feasibility_plan.md",
    )
    archived_entries = (
        "docs/archive/legacy_competition/dataset_card_legacy_69.md",
        "docs/archive/legacy_competition/release_checklist_legacy_v1.md",
        "docs/archive/legacy_competition/submission_evidence_index_legacy_v1.md",
        "docs/archive/legacy_competition/report_sections/03_attack_scenarios.md",
        "docs/archive/research/progent_v13_failure_analysis.md",
        "docs/archive/research/taskshield_v15_failure_analysis.md",
        "docs/archive/research/taskshield_v16_execution_plan.md",
        "docs/archive/research/taskshield_v16_feasibility_plan.md",
    )
    assert all((REPO_ROOT / relative).is_file() for relative in current_entries)
    assert all((REPO_ROOT / relative).is_file() for relative in archived_entries)


def test_project_conventions_audit_passes() -> None:
    audit = _load_conventions_audit()
    report = audit.run_audit()
    assert report["status"] == "pass", report
    assert report["passed_checks"] == report["total_checks"]


def test_checkout_specific_absolute_paths_are_rejected() -> None:
    audit = _load_conventions_audit()
    checkout_name = "M3_PI_" + "Guard_test"
    assert audit.CHECKOUT_SPECIFIC_ABSOLUTE_PATH.search(
        "E:\\" + checkout_name + r"\docs\项目完整综述.md"
    )
    assert audit.CHECKOUT_SPECIFIC_ABSOLUTE_PATH.search(
        "D:/work/" + checkout_name + "/scripts/run.py"
    )
    assert not audit.CHECKOUT_SPECIFIC_ABSOLUTE_PATH.search(
        "docs/项目完整综述.md"
    )
    assert not audit.CHECKOUT_SPECIFIC_ABSOLUTE_PATH.search(
        r"E:\Ollama\models"
    )


def test_portability_scan_excludes_frozen_sources() -> None:
    audit = _load_conventions_audit()
    scanned = {path.relative_to(REPO_ROOT).as_posix() for path in audit._portability_files()}
    assert "m3_core/run_matrix.py" not in scanned
    assert "docs/项目完整综述.md" in scanned
    assert "protocols/paper_upgrade_v1/q2_readiness_audit_v1.json" in scanned
    assert (
        "protocols/paper_upgrade_v1/execution/q2_formal_execution_plan_v1.json"
        in scanned
    )
    assert (
        "protocols/paper_upgrade_v1/agentdojo_tool_filter_formal_admission_v1.json"
        in scanned
    )


def test_portability_scan_excludes_hash_bound_formal_adapter_code() -> None:
    audit = _load_conventions_audit()
    hash_bound = audit._hash_bound_file_paths()
    scanned = {path.relative_to(REPO_ROOT).as_posix() for path in audit._portability_files()}

    expected = {
        "experiments/paper_v1/benchmarks/analyze_taskshield_paper_formal.py",
        "experiments/paper_v1/benchmarks/analyze_progent_source_backed_formal.py",
        "experiments/paper_v1/benchmarks/analyze_camel_source_backed_formal.py",
        "experiments/paper_v1/benchmarks/analyze_ipiguard_source_backed_formal.py",
    }
    assert expected <= hash_bound
    assert not (expected & scanned)


def test_hash_bound_formal_adapter_identities_match_freezes() -> None:
    audit = _load_conventions_audit()
    result = audit.check_hash_bound_file_identity()

    assert result.passed, result.details
    assert result.name == "hash_bound_file_identity"
    hash_bound = audit._hash_bound_file_paths()
    assert len(hash_bound) == 70
    assert {
        "schemas/paper_v1/agentdojo_official_outcome_v2.schema.json",
        "experiments/paper_v1/benchmarks/agentdojo_official_metrics_v2.py",
        "experiments/paper_v1/benchmarks/analyze_progent_source_backed_formal_v12.py",
        "experiments/paper_v1/benchmarks/analyze_progent_source_backed_formal_v13.py",
        "experiments/paper_v1/benchmarks/audit_progent_v12_correctness.py",
        "experiments/paper_v1/benchmarks/audit_progent_v13_correctness.py",
        "experiments/paper_v1/benchmarks/build_progent_source_backed_formal_freeze_v12.py",
        "experiments/paper_v1/benchmarks/build_progent_source_backed_formal_freeze_v13.py",
        "experiments/paper_v1/benchmarks/progent_source_backed_runtime_v12.py",
        "experiments/paper_v1/benchmarks/progent_source_backed_runtime_v13.py",
        "experiments/paper_v1/benchmarks/progent_v12_case_worker.py",
        "experiments/paper_v1/benchmarks/progent_v13_case_worker.py",
        "experiments/paper_v1/benchmarks/run_progent_source_backed_formal_v12.py",
        "experiments/paper_v1/benchmarks/run_progent_source_backed_formal_v13.py",
        "experiments/paper_v1/benchmarks/run_taskshield_paper_formal_v13.py",
        "experiments/paper_v1/benchmarks/taskshield_paper_runtime_v13.py",
        "experiments/paper_v1/benchmarks/build_taskshield_paper_formal_freeze_v14.py",
        "experiments/paper_v1/benchmarks/run_taskshield_paper_formal_v14.py",
        "experiments/paper_v1/benchmarks/taskshield_paper_runtime_v14.py",
        "experiments/paper_v1/benchmarks/build_taskshield_paper_formal_freeze_v15.py",
        "experiments/paper_v1/benchmarks/run_taskshield_paper_formal_v15.py",
        "experiments/paper_v1/benchmarks/taskshield_paper_runtime_v15.py",
        "experiments/paper_v1/benchmarks/build_taskshield_paper_formal_freeze_v16.py",
        "experiments/paper_v1/benchmarks/run_taskshield_paper_formal_v16.py",
        "experiments/paper_v1/benchmarks/taskshield_paper_runtime_v16.py",
        "experiments/paper_v1/benchmarks/analyze_taskshield_v16_qualification.py",
        "protocols/paper_upgrade_v1/execution/progent_v12_p0_metric_semantics_v1/gate_g0.json",
        "protocols/paper_upgrade_v1/execution/progent_v12_p3_failure_review_v1.md",
        "protocols/paper_upgrade_v1/progent_source_backed_formal_protocol_v12.md",
        "protocols/paper_upgrade_v1/progent_source_backed_formal_protocol_v13.md",
        "schemas/paper_v1/progent_source_backed_outcome_v12.schema.json",
        "schemas/paper_v1/progent_source_backed_outcome_v13.schema.json",
        "protocols/paper_upgrade_v1/execution/taskshield_v15_failure_audit_v1/taskshield_v15_failure_mode_audit_v1.json",
        "protocols/paper_upgrade_v1/execution/taskshield_v16_p0_metric_semantics_v1/gate_g0.json",
        "experiments/paper_v1/benchmarks/run_camel_source_backed_formal_v3.py",
        "experiments/paper_v1/benchmarks/analyze_camel_source_backed_formal_v3.py",
        "experiments/paper_v1/benchmarks/strong_baseline_metric_semantics_v2.py",
        "protocols/paper_upgrade_v1/camel_source_backed_formal_protocol_v3.md",
    } <= hash_bound


def test_preregistration_blind_audit_snapshot_is_not_reused_for_postfreeze_admission() -> None:
    audit = _load_conventions_audit()
    preregistration = json.loads(
        (
            REPO_ROOT
            / "protocols"
            / "paper_upgrade_v1"
            / "paper_v1_confirmatory_preregistration_freeze_v1.json"
        ).read_text(encoding="utf-8")
    )
    frozen = preregistration["reference_artifacts"]["independent_blind_admission_audit"]
    frozen_path = audit._resolve_hash_bound_candidate(frozen["path"])
    assert hashlib.sha256(frozen_path.read_bytes()).hexdigest() == frozen["sha256"]
    assert frozen_path.name == "m3_v2_independent_blind_admission_audit_v1.json"
    assert (
        REPO_ROOT
        / "experiments"
        / "paper_v1"
        / "benchmarks"
        / "audit_q2_readiness.py"
    ).read_text(encoding="utf-8").find(
        "m3_v2_independent_blind_admission_audit_v2.json"
    ) >= 0


def test_stable_public_security_interfaces_keep_their_names() -> None:
    from m3_guard.guard_engine import evaluate_guard, guard_decide
    from m3_guard.provenance import ProvenanceEvent
    from m3_guard.runtime_monitor import ActionProposal, GuardDecision
    from m3_guard.task_policy import TaskPolicyManifest

    assert guard_decide.__name__ == "guard_decide"
    assert evaluate_guard.__name__ == "evaluate_guard"
    assert TaskPolicyManifest.__name__ == "TaskPolicyManifest"
    assert ActionProposal.__name__ == "ActionProposal"
    assert GuardDecision.__name__ == "GuardDecision"
    assert ProvenanceEvent.__name__ == "ProvenanceEvent"
