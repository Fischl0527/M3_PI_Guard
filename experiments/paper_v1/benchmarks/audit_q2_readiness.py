"""Compute an evidence-backed Q2-readiness score for the paper-v1 upgrade.

This audit is intentionally conservative.  It rewards completed local
engineering evidence, but it caps the total score when Q2-critical evidence is
missing: independent confirmatory blind data, public-benchmark formal results,
strong source-backed baselines, API-model coverage, and adaptive query-budget
attacks.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .common import (
    portable_path,
    portable_value,
    resolve_artifact_path,
    rows_sha256,
    sha256_file,
)


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = ROOT / "protocols" / "paper_upgrade_v1"
DEFAULT_FINAL_MANIFEST = ROOT / "outputs" / "experiments" / "final_analysis" / "manifest.json"
DEFAULT_STAT_VALIDATION = (
    ROOT / "outputs" / "experiments" / "final_analysis" / "statistical_validation.json"
)
DEFAULT_REPORT_VERIFICATION = (
    ROOT / "outputs" / "experiments" / "final_analysis" / "report" / "verification.json"
)
DEFAULT_BASELINE_REGISTRY_AUDIT = (
    ROOT / "protocols" / "paper_upgrade_v1" / "baseline_registry_audit_v1.json"
)
DEFAULT_STRONG_BASELINE_AUDIT = (
    ROOT / "protocols" / "paper_upgrade_v1" / "strong_baseline_formal_readiness_audit_v1.json"
)
DEFAULT_PUBLIC_COMPLETENESS = (
    ROOT / "protocols" / "paper_upgrade_v1" / "public_benchmark_result_completeness_audit_v2.json"
)
DEFAULT_PUBLIC_FREEZE = ROOT / "protocols" / "paper_upgrade_v1" / "public_benchmark_formal_freeze_v2.json"
DEFAULT_MODEL_REGISTRY = ROOT / "protocols" / "paper_upgrade_v1" / "model_registry_v2.json"
DEFAULT_TOOL_FILTER_FREEZE = (
    ROOT / "protocols" / "paper_upgrade_v1" / "agentdojo_tool_filter_formal_freeze_v1.json"
)
DEFAULT_CONFIRMATORY_PREREGISTRATION = (
    ROOT
    / "protocols"
    / "paper_upgrade_v1"
    / "paper_v1_confirmatory_preregistration_freeze_v1.json"
)
DEFAULT_INDEPENDENT_BLIND_AUDIT = (
    ROOT
    / "protocols"
    / "paper_upgrade_v1"
    / "m3_v2_independent_blind_admission_audit_v2.json"
)
DEFAULT_PAPER_EVIDENCE_INDEX = (
    ROOT / "protocols" / "paper_upgrade_v1" / "paper_v1_evidence_index_v1.json"
)
DEFAULT_FORMAL_RUN_MONITOR = (
    ROOT
    / "protocols"
    / "paper_upgrade_v1"
    / "agentdojo_official_formal_run_monitor_v1.json"
)
DEFAULT_TRANSFORMERS_RUN_MONITOR = (
    ROOT
    / "protocols"
    / "paper_upgrade_v1"
    / "monitors"
    / "transformers_pi_detector_formal_v2"
    / "agentdojo_official_formal_run_monitor_v1.json"
)
DEFAULT_TOOL_FILTER_RUN_MONITOR = (
    ROOT
    / "protocols"
    / "paper_upgrade_v1"
    / "monitors"
    / "tool_filter_formal_v1"
    / "agentdojo_official_formal_run_monitor_v1.json"
)
DEFAULT_FRONTIER_API_AUDIT = (
    ROOT
    / "protocols"
    / "paper_upgrade_v1"
    / "frontier_api_model_slot_admission_audit_v1.json"
)
DEFAULT_TRANSFORMERS_RUN = (
    ROOT
    / "outputs"
    / "paper_upgrade_v1"
    / "baselines"
    / "agentdojo_transformers_pi_detector_official_formal_v2_cpu_detector"
    / "run_manifest.json"
)
DEFAULT_TRANSFORMERS_RECOVERY_RUN = (
    ROOT
    / "outputs"
    / "paper_upgrade_v1"
    / "baselines"
    / "agentdojo_transformers_pi_detector_official_resource_isolated_formal_v1"
    / "run_manifest.json"
)

AUDIT_STEM = "q2_readiness_audit_v1"
AUDIT_VERSION = "m3-paper-v1-q2-readiness-audit-1.0"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def _source(path: Path) -> dict[str, Any]:
    return {
        "path": portable_value(str(path), root=ROOT),
        "exists": path.exists(),
        "sha256": sha256_file(path) if path.exists() else "",
    }


def _resolve_json_reference(reference: Any, *, root: Path = ROOT) -> dict[str, Any]:
    if isinstance(reference, Mapping):
        return {
            "reference_kind": "embedded",
            "path": "",
            "exists": True,
            "sha256": "",
            "manifest": dict(reference),
        }
    if isinstance(reference, str) and reference.strip():
        path = resolve_artifact_path(reference, root=root)
        return {
            "reference_kind": "path",
            "path": portable_path(path, root=root),
            "exists": path.exists(),
            "sha256": sha256_file(path) if path.exists() else "",
            "manifest": _read_json(path),
        }
    return {
        "reference_kind": "missing",
        "path": "",
        "exists": False,
        "sha256": "",
        "manifest": {},
    }


def _first_present_string(*values: Any) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _nested_mapping(value: Any, key: str) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        child = value.get(key, {})
        if isinstance(child, Mapping):
            return child
    return {}


def _extract_confirmatory_blind_candidate_sha(manifest: Mapping[str, Any]) -> str:
    sources = _nested_mapping(manifest, "sources")
    candidate_source = _nested_mapping(sources, "independent_blind_candidate")
    dataset_source = _nested_mapping(sources, "dataset")
    candidate = _nested_mapping(manifest, "candidate")
    dataset = _nested_mapping(manifest, "dataset")
    return _first_present_string(
        manifest.get("independent_blind_candidate_sha256"),
        manifest.get("candidate_sha256"),
        manifest.get("dataset_sha256"),
        candidate_source.get("sha256"),
        dataset_source.get("sha256"),
        candidate.get("sha256"),
        dataset.get("sha256"),
    )


def _extract_confirmatory_blind_case_count(manifest: Mapping[str, Any]) -> int:
    summary = _nested_mapping(manifest, "summary")
    counts = _nested_mapping(manifest, "counts")
    dataset = _nested_mapping(manifest, "dataset")
    candidates = (
        manifest.get("selected_cases"),
        manifest.get("case_count"),
        manifest.get("total_cases"),
        summary.get("selected_cases"),
        summary.get("case_count"),
        summary.get("total_cases"),
        counts.get("selected_cases"),
        counts.get("case_count"),
        counts.get("total_cases"),
        counts.get("total"),
        dataset.get("case_count"),
        dataset.get("total_cases"),
    )
    for value in candidates:
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return 0


def _confirmatory_blind_manifest_gate(
    blind_reference: Any,
    independent_blind_audit: Mapping[str, Any],
) -> dict[str, Any]:
    resolved = _resolve_json_reference(blind_reference)
    manifest = resolved["manifest"]
    status = str(manifest.get("status", ""))
    evidence_status = str(manifest.get("evidence_status", ""))
    evidence_level = str(manifest.get("evidence_level", ""))
    split = str(manifest.get("split", manifest.get("dataset_split", "")))
    candidate_admitted = (
        independent_blind_audit.get("status") == "admitted_independent_blind"
        and independent_blind_audit.get("result_eligible_for_confirmatory_q2_tables") is True
    )
    expected_candidate_sha = str(independent_blind_audit.get("candidate_sha256", ""))
    observed_candidate_sha = _extract_confirmatory_blind_candidate_sha(manifest)
    case_count = _extract_confirmatory_blind_case_count(manifest)
    formal_status = status in {"completed_formal", "completed_formal_analysis"}
    result_eligible = (
        manifest.get("result_eligible_for_confirmatory_q2_tables") is True
        or manifest.get("result_eligible_for_formal_tables") is True
    )
    independent_scope = (
        split == "independent_blind"
        or evidence_level == "independent_blind"
        or evidence_status in {"formal_independent_blind", "formal_confirmatory_blind"}
    )
    boundary = _nested_mapping(manifest, "evidence_boundary")
    posthoc_flag = bool(boundary.get("posthoc") or manifest.get("posthoc"))

    checks = [
        ("blind_manifest_reference_present", bool(blind_reference), resolved["reference_kind"]),
        ("blind_manifest_resolved", resolved["exists"] and bool(manifest), resolved["path"]),
        ("candidate_audit_admitted", candidate_admitted, independent_blind_audit.get("status", "")),
        ("manifest_status_formal", formal_status, status),
        ("manifest_result_eligible", result_eligible, result_eligible),
        ("manifest_case_count_600", case_count == 600, case_count),
        (
            "manifest_candidate_sha_matches_admission",
            bool(expected_candidate_sha)
            and bool(observed_candidate_sha)
            and observed_candidate_sha == expected_candidate_sha,
            {"expected": expected_candidate_sha, "observed": observed_candidate_sha},
        ),
        ("manifest_scope_independent_blind", independent_scope, {"split": split, "evidence_status": evidence_status, "evidence_level": evidence_level}),
        ("manifest_not_posthoc", not posthoc_flag, posthoc_flag),
    ]
    blockers = [name for name, passed, _detail in checks if not passed]
    return {
        "accepted": not blockers,
        "reference_kind": resolved["reference_kind"],
        "path": resolved["path"],
        "exists": resolved["exists"],
        "sha256": resolved["sha256"],
        "status": status,
        "evidence_status": evidence_status,
        "evidence_level": evidence_level,
        "split": split,
        "case_count": case_count,
        "candidate_sha256": observed_candidate_sha,
        "expected_candidate_sha256": expected_candidate_sha,
        "checks": [
            {"name": name, "status": "pass" if passed else "fail", "detail": detail}
            for name, passed, detail in checks
        ],
        "blockers": blockers,
    }


def _select_transformers_run(
    primary_path: Path,
    recovery_path: Path,
) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    primary = _read_json(primary_path)
    recovery = _read_json(recovery_path)
    primary_status = primary.get("status", "")
    recovery_status = recovery.get("status", "")
    if recovery:
        selected_path = recovery_path
        selected = recovery
        reason = "recovery_manifest_present"
    else:
        selected_path = primary_path
        selected = primary
        reason = "recovery_manifest_missing_use_primary"
    return selected_path, selected, {
        "selected_path": str(selected_path),
        "selection_reason": reason,
        "primary_path": str(primary_path),
        "primary_status": primary_status,
        "recovery_path": str(recovery_path),
        "recovery_status": recovery_status,
    }


def _monitor_matches_run(monitor: Mapping[str, Any], run_manifest_path: Path) -> bool:
    """Return true only when a monitor snapshot belongs to the selected run.

    Historical monitor files can outlive the formal root they originally
    described.  The Q2 scorecard must not treat a generic AgentDojo monitor that
    currently points at another baseline, such as ``tool_filter``, as evidence
    that a stale ``transformers_pi_detector`` manifest is still progressing.
    """

    monitored_path = str(monitor.get("run_manifest_path", "")).strip()
    if not monitored_path:
        return False
    try:
        return Path(monitored_path).resolve() == run_manifest_path.resolve()
    except (OSError, RuntimeError, ValueError):
        return False


def _select_matching_monitor(
    selected_run_path: Path,
    *,
    generic_monitor_path: Path,
    selected_monitor_path: Path,
) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    generic = _read_json(generic_monitor_path)
    selected = _read_json(selected_monitor_path)
    candidates = [
        ("selected_run_monitor", selected_monitor_path, selected),
        ("generic_monitor", generic_monitor_path, generic),
    ]
    for name, path, monitor in candidates:
        if monitor and _monitor_matches_run(monitor, selected_run_path):
            return path, monitor, {
                "selected_monitor_path": str(path),
                "selection_reason": f"{name}_matches_selected_run",
                "generic_monitor_path": str(generic_monitor_path),
                "generic_monitor_matches_selected_run": _monitor_matches_run(
                    generic,
                    selected_run_path,
                ),
                "selected_run_monitor_path": str(selected_monitor_path),
                "selected_run_monitor_matches_selected_run": _monitor_matches_run(
                    selected,
                    selected_run_path,
                ),
            }
    fallback_path = generic_monitor_path if generic else selected_monitor_path
    fallback_monitor = generic if generic else selected
    return fallback_path, fallback_monitor, {
        "selected_monitor_path": str(fallback_path),
        "selection_reason": "no_monitor_matches_selected_run_fallback_used",
        "generic_monitor_path": str(generic_monitor_path),
        "generic_monitor_matches_selected_run": _monitor_matches_run(
            generic,
            selected_run_path,
        ),
        "selected_run_monitor_path": str(selected_monitor_path),
        "selected_run_monitor_matches_selected_run": _monitor_matches_run(
            selected,
            selected_run_path,
        ),
    }


def _criterion(
    criterion_id: str,
    title: str,
    weight: float,
    earned: float,
    status: str,
    evidence: Mapping[str, Any],
    blockers: list[str],
) -> dict[str, Any]:
    earned = round(max(0.0, min(float(weight), float(earned))), 3)
    return {
        "id": criterion_id,
        "title": title,
        "weight": weight,
        "earned": earned,
        "status": status,
        "evidence": dict(evidence),
        "blockers": blockers,
    }


def _historical_evidence(
    final_manifest: Mapping[str, Any],
    stat_validation: Mapping[str, Any],
    report_verification: Mapping[str, Any],
) -> dict[str, Any]:
    checks = {
        "final_manifest_completed": final_manifest.get("status") == "completed",
        "e0_e17_registry_declared": len(final_manifest.get("registry_experiments", [])) >= 18,
        "charts_declared": int(final_manifest.get("chart_count", 0)) >= 10,
        "large_input_ledger_declared": int(final_manifest.get("input_artifact_count", 0)) >= 1000,
        "statistical_validation_passed": stat_validation.get("verification_status", {}).get("label") == "PASS",
        "portable_report_validated": report_verification.get("validation") == "passed",
    }
    earned = 12.0 * sum(checks.values()) / len(checks)
    blockers = [name for name, passed in checks.items() if not passed]
    return _criterion(
        "historical_e0_e17_evidence",
        "Historical E0-E17 engineering evidence",
        12.0,
        earned,
        "complete" if not blockers else "partial",
        checks,
        blockers,
    )


def _mechanism_evidence(root: Path) -> dict[str, Any]:
    required_files = [
        root / "m3_guard" / "runtime_monitor.py",
        root / "m3_guard" / "task_policy.py",
        root / "m3_guard" / "provenance.py",
        root / "m3_core" / "policy_compiler.py",
        root / "m3_core" / "policy_regimes.py",
    ]
    present = [path for path in required_files if path.exists()]
    formal_proof = (root / "protocols" / "paper_upgrade_v1" / "formal_security_properties_v1.md").exists()
    no_leakage_tests = (root / "tests" / "unit" / "test_paper_v1_runtime.py").exists()
    earned = 6.0 * len(present) / len(required_files)
    if no_leakage_tests:
        earned += 2.0
    if formal_proof:
        earned += 2.0
    blockers: list[str] = []
    if len(present) != len(required_files):
        blockers.append("runtime policy/provenance source files are incomplete")
    if not formal_proof:
        blockers.append("formal security-property statement/proof is not recorded")
    return _criterion(
        "mechanism_no_label_leakage",
        "Non-oracle runtime mechanism and formalization",
        10.0,
        earned,
        "partial" if blockers else "complete",
        {
            "required_files_present": len(present),
            "required_files_total": len(required_files),
            "no_leakage_test_file_present": no_leakage_tests,
            "formal_security_properties_present": formal_proof,
        },
        blockers,
    )


def _confirmatory_blind(
    final_manifest: Mapping[str, Any],
    independent_blind_audit: Mapping[str, Any],
    paper_evidence_index: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    policy = final_manifest.get("formal_evidence_policy", {})
    has_historical_human_review = "E17" in policy
    evidence_index = (
        final_manifest if paper_evidence_index is None else paper_evidence_index
    )
    blind_manifest_gate = _confirmatory_blind_manifest_gate(
        evidence_index.get("m3_v2_independent_blind_manifest"),
        independent_blind_audit,
    )
    has_new_blind = bool(blind_manifest_gate["accepted"])
    candidate_admitted = (
        independent_blind_audit.get("status") == "admitted_independent_blind"
        and independent_blind_audit.get("result_eligible_for_confirmatory_q2_tables") is True
    )
    earned = 15.0 if has_new_blind else (2.0 if has_historical_human_review else 0.0)
    blockers = [] if has_new_blind else [
        "new independent M3-v2 blind split is not admitted, frozen and run",
        "independent blind admission audit has not admitted a candidate dataset"
        if not candidate_admitted
        else "independent blind candidate is admitted but downstream blind runs are not complete",
        "post-hoc/historical blind evidence cannot serve as confirmatory Q2 evidence",
        *[
            blocker if blocker.startswith("blind_manifest_") else f"blind_manifest_{blocker}"
            for blocker in blind_manifest_gate["blockers"]
        ],
    ]
    return _criterion(
        "confirmatory_new_blind",
        "Independent confirmatory blind evidence",
        15.0,
        earned,
        "complete" if has_new_blind else "blocked",
        {
            "historical_e17_policy": policy.get("E17", ""),
            "new_blind_manifest_declared": has_new_blind,
            "independent_blind_admission_status": independent_blind_audit.get("status", ""),
            "independent_blind_candidate_admitted": candidate_admitted,
            "independent_blind_candidate_path": independent_blind_audit.get("candidate_path", ""),
            "independent_blind_manifest_gate": blind_manifest_gate,
        },
        blockers,
    )


def _public_benchmark(
    public_freeze: Mapping[str, Any],
    public_completeness: Mapping[str, Any],
    transformers_run: Mapping[str, Any],
    transformers_run_path: Path,
    formal_run_monitor: Mapping[str, Any],
    tool_filter_run_monitor: Mapping[str, Any],
) -> dict[str, Any]:
    freeze_done = public_freeze.get("status") == "completed"
    expected = int(public_completeness.get("expected_case_runs", 0) or 0)
    complete = int(public_completeness.get("complete_case_runs", 0) or 0)
    matrix_fraction = complete / expected if expected else 0.0
    monitor_health = formal_run_monitor.get("health_status", "")
    monitor_matches_transformers = _monitor_matches_run(formal_run_monitor, transformers_run_path)
    formal_detector_running = (
        transformers_run.get("status") == "running"
        and monitor_health == "running_progressing"
        and monitor_matches_transformers
        and bool(formal_run_monitor.get("pid_alive"))
        and int(formal_run_monitor.get("counts", {}).get("failed_cases", 0) or 0) == 0
    )
    tool_filter_status = tool_filter_run_monitor.get("manifest_status", "")
    tool_filter_running = (
        tool_filter_status == "running"
        and tool_filter_run_monitor.get("health_status") == "running_progressing"
    )
    tool_filter_formal = tool_filter_status == "completed_formal"
    earned = (3.0 if freeze_done else 0.0) + 10.0 * matrix_fraction
    if transformers_run.get("status") == "completed_formal":
        earned += 2.0
    elif formal_detector_running:
        earned += 0.5
    elif tool_filter_running:
        earned += 0.5
    scored_status = (
        "completed_formal"
        if transformers_run.get("status") == "completed_formal"
        else "running_progressing"
        if formal_detector_running
        else "not_admitted_or_not_progressing"
    )
    blockers = []
    if public_completeness.get("result_completeness_gate") != "satisfied":
        blockers.append("public benchmark formal matrix is not complete")
    if transformers_run.get("status") != "completed_formal":
        blockers.append("AgentDojo official transformers_pi_detector full cell is not admitted")
    if not tool_filter_formal:
        blockers.append("AgentDojo official tool_filter full cell is not admitted")
    return _criterion(
        "public_benchmark_formal_results",
        "AgentDojo/InjecAgent public benchmark formal results",
        15.0,
        earned,
        "complete" if not blockers else "blocked",
        {
            "freeze_status": public_freeze.get("status", ""),
            "expected_case_runs": expected,
            "complete_case_runs": complete,
            "matrix_fraction": round(matrix_fraction, 6),
            "result_gate": public_completeness.get("result_completeness_gate", ""),
            "transformers_detector_manifest_status": transformers_run.get("status", ""),
            "transformers_detector_scored_status": scored_status,
            "transformers_detector_monitor_health": formal_run_monitor.get("health_status", ""),
            "transformers_detector_monitor_matches_selected_run": monitor_matches_transformers,
            "transformers_detector_monitor_pid_alive": bool(formal_run_monitor.get("pid_alive")),
            "transformers_detector_monitor_completed": formal_run_monitor.get("counts", {}).get("completed_cases", 0),
            "transformers_detector_monitor_failed": formal_run_monitor.get("counts", {}).get("failed_cases", 0),
            "transformers_detector_monitor_missing": formal_run_monitor.get("counts", {}).get("missing_cases", 0),
            "tool_filter_manifest_status": tool_filter_status,
            "tool_filter_monitor_health": tool_filter_run_monitor.get("health_status", ""),
            "tool_filter_monitor_completed": tool_filter_run_monitor.get("counts", {}).get("completed_cases", 0),
            "tool_filter_monitor_failed": tool_filter_run_monitor.get("counts", {}).get("failed_cases", 0),
            "tool_filter_monitor_missing": tool_filter_run_monitor.get("counts", {}).get("missing_cases", 0),
            "tool_filter_formal_result_admitted_now": bool(tool_filter_run_monitor.get("formal_result_admitted_now")),
        },
        blockers,
    )


def _strong_baselines(strong_audit: Mapping[str, Any], baseline_audit: Mapping[str, Any]) -> dict[str, Any]:
    ready = strong_audit.get("formal_ready_strong_baselines", [])
    ready_count = len(ready) if isinstance(ready, list) else 0
    minimum = 5
    earned = 15.0 * min(ready_count, minimum) / minimum
    pending = [
        key
        for key, row in strong_audit.get("readiness_rows", {}).items()
        if isinstance(row, Mapping) and row.get("formal_admission_status") != "formal_ready"
    ]
    blockers = []
    if ready_count < minimum:
        blockers.append("fewer than five source-backed strong baselines are formal-ready")
    return _criterion(
        "source_backed_strong_baselines",
        "Source-backed strong baselines",
        15.0,
        earned,
        "complete" if ready_count >= minimum else "blocked",
        {
            "formal_ready_count": ready_count,
            "formal_ready": ready,
            "minimum": minimum,
            "pending": pending,
            "registry_audit_status": baseline_audit.get("status", ""),
        },
        blockers,
    )


def _model_coverage(
    model_registry: Mapping[str, Any],
    frontier_api_audit: Mapping[str, Any],
) -> dict[str, Any]:
    summary = model_registry.get("summary", {})
    local_small = int(summary.get("local_model_slots", 0) or 0)
    modern = int(summary.get("modern_open_7b_14b_slots", 0) or 0)
    api = max(
        int(summary.get("frontier_api_vendor_slots", 0) or 0),
        int(frontier_api_audit.get("registered_frontier_api_vendor_count", 0) or 0),
    )
    earned = 0.0
    earned += 3.0 * min(local_small, 2) / 2
    earned += 3.0 * min(modern, 2) / 2
    earned += 4.0 * min(api, 2) / 2
    blockers = []
    if api < 2:
        blockers.append("two frontier API vendor model slots are still missing")
    if frontier_api_audit and frontier_api_audit.get("status") not in {
        "configured_pending_network_smoke",
        "registry_satisfied_pending_formal_runs",
    }:
        blockers.append("frontier API local configuration is not ready for explicit network smoke")
    return _criterion(
        "model_coverage",
        "Model coverage",
        10.0,
        earned,
        "complete" if not blockers else "partial",
        {
            "local_model_slots": local_small,
            "modern_open_7b_14b_slots": modern,
            "frontier_api_vendor_slots": api,
            "q2_model_gate": model_registry.get("q2_model_gate", summary.get("q2_model_gate", "")),
            "frontier_api_admission_status": frontier_api_audit.get("status", ""),
            "frontier_api_configured_vendor_count": frontier_api_audit.get("configured_vendor_count", 0),
            "frontier_api_registered_vendor_count": frontier_api_audit.get(
                "registered_frontier_api_vendor_count", 0
            ),
            "frontier_api_selected_model_registry_path": frontier_api_audit.get(
                "selected_model_registry_path", ""
            ),
            "frontier_api_model_registry_selection": frontier_api_audit.get(
                "model_registry_selection", {}
            ),
            "frontier_api_network_calls_performed": frontier_api_audit.get(
                "network_calls_performed", False
            ),
            "frontier_api_explicit_network_smoke_consent": frontier_api_audit.get(
                "explicit_network_smoke_consent", False
            ),
        },
        blockers,
    )


def _adaptive_attack(root: Path, final_manifest: Mapping[str, Any]) -> dict[str, Any]:
    historical_e16 = "E16" in final_manifest.get("registry_experiments", [])
    query_budget_freeze_manifest = (
        root / "protocols" / "paper_upgrade_v1" / "adaptive_mcts_budget_freeze_v1.json"
    )
    query_budget_freeze = _read_json(query_budget_freeze_manifest)
    complete_freeze = query_budget_freeze.get("status") == "completed_frozen_protocol"
    query_budget_manifest = root / "outputs" / "paper_upgrade_v1" / "adaptive_mcts_budget_v1" / "manifest.json"
    query_budget = _read_json(query_budget_manifest)
    complete_query_budget = query_budget.get("status") == "completed_formal"
    runner_preflight_manifest = (
        root
        / "outputs"
        / "paper_upgrade_v1"
        / "adaptive_mcts_budget_runner_stub_preflight_v1"
        / "manifest.json"
    )
    runner_preflight_analysis_manifest = (
        runner_preflight_manifest.parent / "analysis" / "analysis_manifest.json"
    )
    runner_preflight = _read_json(runner_preflight_manifest)
    runner_preflight_analysis = _read_json(runner_preflight_analysis_manifest)
    runner_preflight_complete = (
        runner_preflight.get("status") == "completed_qualification_only"
        and runner_preflight.get("result_eligible_for_formal_tables") is False
        and runner_preflight_analysis.get("status") == "completed_diagnostic_analysis"
        and runner_preflight_analysis.get("result_eligible_for_formal_tables") is False
    )
    earned = 10.0 if complete_query_budget else (2.0 if historical_e16 else 0.0)
    if complete_freeze and not complete_query_budget:
        earned += 1.0
    if runner_preflight_complete and not complete_query_budget:
        earned += 1.0
    blockers = [] if complete_query_budget else [
        "80-task adaptive query-budget attack is not complete",
        "MCTS/black-box budget curves are still missing as formal evidence",
    ]
    return _criterion(
        "adaptive_query_budget_attacks",
        "Adaptive query-budget attacks",
        10.0,
        earned,
        "complete" if complete_query_budget else "blocked",
        {
            "historical_e16_present": historical_e16,
            "query_budget_freeze_manifest": str(query_budget_freeze_manifest),
            "query_budget_freeze_status": query_budget_freeze.get("status", ""),
            "query_budget_freeze_case_count": query_budget_freeze.get("case_count", 0),
            "query_budget_manifest": str(query_budget_manifest),
            "query_budget_status": query_budget.get("status", ""),
            "runner_preflight_manifest": str(runner_preflight_manifest),
            "runner_preflight_status": runner_preflight.get("status", ""),
            "runner_preflight_analysis_manifest": str(
                runner_preflight_analysis_manifest
            ),
            "runner_preflight_analysis_status": runner_preflight_analysis.get(
                "status", ""
            ),
            "runner_preflight_formal_result_eligible": runner_preflight.get(
                "result_eligible_for_formal_tables"
            ),
        },
        blockers,
    )


def _statistics_human_review(
    final_manifest: Mapping[str, Any],
    stat_validation: Mapping[str, Any],
    report_verification: Mapping[str, Any],
) -> dict[str, Any]:
    checks = {
        "statistical_validation_passed": stat_validation.get("verification_status", {}).get("label") == "PASS",
        "human_review_policy_declared": "E17" in final_manifest.get("formal_evidence_policy", {}),
        "chart_count_at_least_ten": int(final_manifest.get("chart_count", 0) or 0) >= 10,
        "portable_report_validation_passed": report_verification.get("validation") == "passed",
    }
    earned = 8.0 * sum(checks.values()) / len(checks)
    blockers = [name for name, passed in checks.items() if not passed]
    return _criterion(
        "statistics_review_and_figures",
        "Statistics, human review, and figures",
        8.0,
        earned,
        "complete" if not blockers else "partial",
        checks,
        blockers,
    )


def _reproducibility(
    public_freeze: Mapping[str, Any],
    baseline_audit: Mapping[str, Any],
    strong_audit: Mapping[str, Any],
    tool_filter_freeze: Mapping[str, Any],
    confirmatory_preregistration: Mapping[str, Any],
) -> dict[str, Any]:
    checks = {
        "public_freeze_completed": public_freeze.get("status") == "completed",
        "baseline_registry_audit_completed": baseline_audit.get("status") == "completed",
        "strong_baseline_audit_completed": strong_audit.get("status") == "completed",
        "tool_filter_freeze_completed": tool_filter_freeze.get("status") == "completed_frozen_formal_protocol",
        "confirmatory_preregistration_frozen": (
            confirmatory_preregistration.get("status")
            == "completed_frozen_preregistration"
            and bool(confirmatory_preregistration.get("preregistration_sha256"))
            and confirmatory_preregistration.get("passed_checks")
            == confirmatory_preregistration.get("total_checks")
        ),
    }
    earned = 8.0 * sum(checks.values()) / len(checks)
    blockers = [name for name, passed in checks.items() if not passed]
    return _criterion(
        "reproducibility_and_freezes",
        "Reproducibility, freezes, and exclusion gates",
        8.0,
        earned,
        "complete" if not blockers else "partial",
        checks,
        blockers,
    )


def _manuscript_package(root: Path) -> dict[str, Any]:
    figures = list((root / "outputs" / "experiments" / "final_analysis").glob("*.png"))
    paper_outline = root / "protocols" / "paper_upgrade_v1" / "paper_storyline_v1.md"
    q2_status = root / "protocols" / "paper_upgrade_v1" / "implementation_status.md"
    earned = 0.0
    if len(figures) >= 10:
        earned += 2.0
    if q2_status.exists():
        earned += 2.0
    if paper_outline.exists():
        earned += 3.0
    blockers = []
    if not paper_outline.exists():
        blockers.append("paper storyline/manuscript scaffold is not frozen")
    return _criterion(
        "manuscript_package",
        "Manuscript package and paper narrative",
        7.0,
        earned,
        "complete" if not blockers else "partial",
        {
            "final_analysis_png_count": len(figures),
            "implementation_status_present": q2_status.exists(),
            "paper_storyline_present": paper_outline.exists(),
        },
        blockers,
    )


def _cap(total: float, name: str, value: float, active: bool, reason: str) -> dict[str, Any]:
    return {
        "name": name,
        "cap": value,
        "gate_missing": active,
        "score_limited": active and total > value,
        "reason": reason,
    }


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_markdown(path: Path, audit: Mapping[str, Any]) -> None:
    lines = [
        "# Q2 readiness audit v1",
        "",
        f"Generated: {audit['created_at']}",
        "",
        "## Result",
        "",
        f"- Raw score: {audit['raw_score']:.1f}/100",
        f"- Capped score: {audit['capped_score']:.1f}/100",
        f"- Readiness band: `{audit['readiness_band']}`",
        f"- Goal met (>=90): `{audit['goal_90_met']}`",
        "",
        "## Criteria",
        "",
        "| Criterion | Earned | Status | Main blockers |",
        "|---|---:|---|---|",
    ]
    for row in audit["criteria"]:
        blockers = "; ".join(row["blockers"]) or "none"
        blockers = blockers.replace("|", "\\|")
        lines.append(
            f"| {row['title']} | {row['earned']:.1f}/{row['weight']:.1f} | "
            f"`{row['status']}` | {blockers} |"
        )
    lines.extend(["", "## Active Caps", ""])
    active_caps = [cap for cap in audit["caps"] if cap["gate_missing"]]
    if active_caps:
        for cap in active_caps:
            suffix = "score currently below this cap" if not cap["score_limited"] else "score limited"
            lines.append(f"- {cap['name']}: cap {cap['cap']:.1f}; {cap['reason']} ({suffix})")
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            audit["boundary"],
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def build_q2_readiness_audit(
    *,
    output_dir: Path = DEFAULT_OUTPUT,
    final_manifest_path: Path = DEFAULT_FINAL_MANIFEST,
    stat_validation_path: Path = DEFAULT_STAT_VALIDATION,
    report_verification_path: Path = DEFAULT_REPORT_VERIFICATION,
    baseline_registry_audit_path: Path = DEFAULT_BASELINE_REGISTRY_AUDIT,
    strong_baseline_audit_path: Path = DEFAULT_STRONG_BASELINE_AUDIT,
    public_completeness_path: Path = DEFAULT_PUBLIC_COMPLETENESS,
    public_freeze_path: Path = DEFAULT_PUBLIC_FREEZE,
    model_registry_path: Path = DEFAULT_MODEL_REGISTRY,
    tool_filter_freeze_path: Path = DEFAULT_TOOL_FILTER_FREEZE,
    confirmatory_preregistration_path: Path = DEFAULT_CONFIRMATORY_PREREGISTRATION,
    independent_blind_audit_path: Path = DEFAULT_INDEPENDENT_BLIND_AUDIT,
    paper_evidence_index_path: Path = DEFAULT_PAPER_EVIDENCE_INDEX,
    formal_run_monitor_path: Path = DEFAULT_FORMAL_RUN_MONITOR,
    transformers_run_monitor_path: Path = DEFAULT_TRANSFORMERS_RUN_MONITOR,
    tool_filter_run_monitor_path: Path = DEFAULT_TOOL_FILTER_RUN_MONITOR,
    frontier_api_audit_path: Path = DEFAULT_FRONTIER_API_AUDIT,
    transformers_run_path: Path = DEFAULT_TRANSFORMERS_RUN,
    transformers_recovery_run_path: Path = DEFAULT_TRANSFORMERS_RECOVERY_RUN,
) -> dict[str, Any]:
    final_manifest = _read_json(final_manifest_path)
    stat_validation = _read_json(stat_validation_path)
    report_verification = _read_json(report_verification_path)
    baseline_audit = _read_json(baseline_registry_audit_path)
    strong_audit = _read_json(strong_baseline_audit_path)
    public_completeness = _read_json(public_completeness_path)
    public_freeze = _read_json(public_freeze_path)
    model_registry = _read_json(model_registry_path)
    tool_filter_freeze = _read_json(tool_filter_freeze_path)
    confirmatory_preregistration = _read_json(confirmatory_preregistration_path)
    independent_blind_audit = _read_json(independent_blind_audit_path)
    paper_evidence_index = _read_json(paper_evidence_index_path)
    tool_filter_run_monitor = _read_json(tool_filter_run_monitor_path)
    frontier_api_audit = _read_json(frontier_api_audit_path)
    selected_transformers_run_path, transformers_run, transformers_selection = _select_transformers_run(
        transformers_run_path,
        transformers_recovery_run_path,
    )
    selected_formal_monitor_path, formal_run_monitor, formal_monitor_selection = (
        _select_matching_monitor(
            selected_transformers_run_path,
            generic_monitor_path=formal_run_monitor_path,
            selected_monitor_path=transformers_run_monitor_path,
        )
    )

    criteria = portable_value([
        _historical_evidence(final_manifest, stat_validation, report_verification),
        _mechanism_evidence(ROOT),
        _confirmatory_blind(
            final_manifest,
            independent_blind_audit,
            paper_evidence_index,
        ),
        _public_benchmark(
            public_freeze,
            public_completeness,
            transformers_run,
            selected_transformers_run_path,
            formal_run_monitor,
            tool_filter_run_monitor,
        ),
        _strong_baselines(strong_audit, baseline_audit),
        _model_coverage(model_registry, frontier_api_audit),
        _adaptive_attack(ROOT, final_manifest),
        _statistics_human_review(final_manifest, stat_validation, report_verification),
        _reproducibility(
            public_freeze,
            baseline_audit,
            strong_audit,
            tool_filter_freeze,
            confirmatory_preregistration,
        ),
        _manuscript_package(ROOT),
    ], root=ROOT)
    raw_score = round(sum(float(row["earned"]) for row in criteria), 3)

    ready_baselines = len(strong_audit.get("formal_ready_strong_baselines", []))
    public_gate_satisfied = public_completeness.get("result_completeness_gate") == "satisfied"
    confirmatory_blind = next(
        row for row in criteria if row["id"] == "confirmatory_new_blind"
    )
    has_new_blind = confirmatory_blind["status"] == "complete"
    api_vendors = max(
        int(model_registry.get("summary", {}).get("frontier_api_vendor_slots", 0) or 0),
        int(frontier_api_audit.get("registered_frontier_api_vendor_count", 0) or 0),
    )
    adaptive_formal = (
        ROOT / "outputs" / "paper_upgrade_v1" / "adaptive_mcts_budget_v1" / "manifest.json"
    )
    has_adaptive_query_budget = _read_json(adaptive_formal).get("status") == "completed_formal"
    caps = [
        _cap(raw_score, "public_benchmark_gate", 75.0, not public_gate_satisfied, "formal public-benchmark matrix is incomplete"),
        _cap(raw_score, "strong_baseline_gate", 70.0, ready_baselines < 5, "fewer than five strong baselines are formal-ready"),
        _cap(raw_score, "independent_blind_gate", 65.0, not has_new_blind, "new independent confirmatory blind evidence is missing"),
        _cap(raw_score, "frontier_api_model_gate", 60.0, api_vendors < 2, "two frontier API vendor slots are missing"),
        _cap(raw_score, "adaptive_budget_gate", 60.0, not has_adaptive_query_budget, "formal adaptive query-budget evidence is missing"),
    ]
    active_cap_values = [float(cap["cap"]) for cap in caps if cap["score_limited"]]
    capped_score = round(min([raw_score, *active_cap_values]) if active_cap_values else raw_score, 3)
    readiness_band = (
        "q2_target_met"
        if capped_score >= 90.0
        else "substantial_but_not_q2_ready"
        if capped_score >= 70.0
        else "paper_upgrade_in_progress"
    )
    sources = portable_value({
        "final_manifest": _source(final_manifest_path),
        "stat_validation": _source(stat_validation_path),
        "report_verification": _source(report_verification_path),
        "baseline_registry_audit": _source(baseline_registry_audit_path),
        "strong_baseline_audit": _source(strong_baseline_audit_path),
        "public_completeness": _source(public_completeness_path),
        "public_freeze": _source(public_freeze_path),
        "model_registry": _source(model_registry_path),
        "tool_filter_freeze": _source(tool_filter_freeze_path),
        "confirmatory_preregistration": _source(confirmatory_preregistration_path),
        "independent_blind_audit": _source(independent_blind_audit_path),
        "paper_evidence_index": _source(paper_evidence_index_path),
        "formal_run_monitor": _source(selected_formal_monitor_path),
        "formal_run_monitor_generic": _source(formal_run_monitor_path),
        "formal_run_monitor_selected": _source(transformers_run_monitor_path),
        "tool_filter_run_monitor": _source(tool_filter_run_monitor_path),
        "frontier_api_audit": _source(frontier_api_audit_path),
        "transformers_run": _source(selected_transformers_run_path),
        "transformers_run_primary": _source(transformers_run_path),
        "transformers_run_recovery": _source(transformers_recovery_run_path),
    }, root=ROOT)
    audit = {
        "schema_version": "paper-q2-readiness-audit-1.0",
        "audit_version": AUDIT_VERSION,
        "status": "completed",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "raw_score": raw_score,
        "capped_score": capped_score,
        "goal_80_met": capped_score >= 80.0,
        "goal_90_met": capped_score >= 90.0,
        "readiness_band": readiness_band,
        "criteria": criteria,
        "criteria_sha256": rows_sha256(criteria),
        "caps": caps,
        "sources": sources,
        "sources_sha256": rows_sha256(sources.values()),
        "transformers_run_selection": portable_value(transformers_selection, root=ROOT),
        "transformers_monitor_selection": portable_value(formal_monitor_selection, root=ROOT),
        "boundary": (
            "Readiness audit only.  It is not a manuscript acceptance predictor "
            "and cannot turn partial, diagnostic, smoke, or running results into "
            "formal paper evidence.  Scores should move upward only when the "
            "underlying frozen artifacts and formal manifests are actually present."
        ),
    }
    json_path = output_dir / f"{AUDIT_STEM}.json"
    md_path = output_dir / f"{AUDIT_STEM}.md"
    _write_json(json_path, audit)
    _write_markdown(md_path, audit)
    audit["json_path"] = portable_path(json_path, root=ROOT)
    audit["markdown_path"] = portable_path(md_path, root=ROOT)
    return audit


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    audit = build_q2_readiness_audit(output_dir=args.output_dir)
    print(json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
