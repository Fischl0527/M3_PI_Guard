"""Prepare a read-only Task Shield v1.4 recovery decision package.

This helper exists because a failed formal root must not be silently retried,
repaired, excluded, admitted, or overlapped by a competing model job.  It turns
the current v1.3 failed-root monitor plus the frozen v1.4 protocol into an
auditable handoff package for a later explicit user decision.

It never stops processes, starts Ollama/model work, retries cases, analyzes
formal results, or writes registries.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .common import portable_path


ROOT = Path(__file__).resolve().parents[3]
PROTOCOL_ROOT = ROOT / "protocols" / "paper_upgrade_v1"
DEFAULT_MONITOR = (
    PROTOCOL_ROOT
    / "monitors"
    / "task_shield_formal_v13"
    / "agentdojo_official_formal_run_monitor_v1.json"
)
DEFAULT_V13_RUN_DIR = ROOT / "outputs" / "paper_upgrade_v1" / "baselines" / "taskshield_paper_formal_v13"
DEFAULT_V14_FREEZE = PROTOCOL_ROOT / "taskshield_paper_formal_freeze_v14.json"
DEFAULT_OUTPUT_DIR = PROTOCOL_ROOT / "execution" / "taskshield_v14_recovery_decision_v1"
PACKAGE_JSON_NAME = "taskshield_v14_recovery_decision_v1.json"
PACKAGE_MD_NAME = "taskshield_v14_recovery_decision_v1.md"
DECISION_TEMPLATE_JSON_NAME = "taskshield_v14_operator_decision_template.json"
DECISION_TEMPLATE_MD_NAME = "taskshield_v14_operator_decision_template.md"
DECISION_APPROVED_JSON_NAME = "taskshield_v14_operator_decision.approved.json"
V14_QUALIFICATION_ROOT = "outputs/paper_upgrade_v1/baselines/taskshield_paper_qualification_v14"
V14_FORMAL_ROOT = "outputs/paper_upgrade_v1/baselines/taskshield_paper_formal_v14"
QUALIFICATION_CASE_IDS = (
    "agentdojo:v1:banking:user_task_0",
    "agentdojo:v1:banking:user_task_0:injection_task_0",
)
PACKAGE_VERSION = "m3-paper-v1-taskshield-v14-recovery-decision-package-1.0"


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


def _sha256(path: Path) -> str:
    if not path.exists():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _case_args() -> str:
    return " ".join(f"--case-id {case_id}" for case_id in QUALIFICATION_CASE_IDS)


def _freshness(path: Path) -> dict[str, Any]:
    return {
        "path": portable_path(path, root=ROOT),
        "exists": path.exists(),
        "has_run_manifest": (path / "run_manifest.json").exists(),
    }


def _commands() -> dict[str, str]:
    freeze = "protocols/paper_upgrade_v1/taskshield_paper_formal_freeze_v14.json"
    return {
        "refresh_v13_monitor": (
            "python -m experiments.paper_v1.benchmarks.monitor_agentdojo_official_formal_run "
            "--run-dir outputs/paper_upgrade_v1/baselines/taskshield_paper_formal_v13 "
            "--output-dir protocols/paper_upgrade_v1/monitors/task_shield_formal_v13"
        ),
        "refresh_q2_plan": "python -m experiments.paper_v1.benchmarks.plan_q2_formal_execution",
        "v14_qualification_after_explicit_stop": (
            "python -m experiments.paper_v1.benchmarks.run_taskshield_paper_formal_v14 "
            f"--freeze {freeze} --output-dir {V14_QUALIFICATION_ROOT} "
            f"{_case_args()} --no-resume"
        ),
        "v14_full_formal_after_clean_qualification": (
            "python -m experiments.paper_v1.benchmarks.run_taskshield_paper_formal_v14 "
            f"--freeze {freeze} --output-dir {V14_FORMAL_ROOT} "
            "--admit-formal --no-resume"
        ),
        "v14_analyze_after_complete_formal": (
            "python -m experiments.paper_v1.benchmarks.analyze_taskshield_paper_formal "
            f"--run-dir {V14_FORMAL_ROOT} --output-dir {V14_FORMAL_ROOT}/analysis"
        ),
        "v14_admission_dry_run_after_analysis": (
            "python -m experiments.paper_v1.benchmarks."
            "admit_external_strong_baseline_formal_result "
            f"--condition-id task_shield --run-dir {V14_FORMAL_ROOT} "
            f"--analysis-manifest {V14_FORMAL_ROOT}/analysis/analysis_manifest.json"
        ),
        "v14_admission_write_after_clean_dry_run": (
            "python -m experiments.paper_v1.benchmarks."
            "admit_external_strong_baseline_formal_result "
            f"--condition-id task_shield --run-dir {V14_FORMAL_ROOT} "
            f"--analysis-manifest {V14_FORMAL_ROOT}/analysis/analysis_manifest.json "
            "--write-registries"
        ),
    }


def build_recovery_package(
    *,
    monitor_path: Path = DEFAULT_MONITOR,
    v13_run_dir: Path = DEFAULT_V13_RUN_DIR,
    v14_freeze_path: Path = DEFAULT_V14_FREEZE,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    v14_qualification_root: Path | None = None,
    v14_formal_root: Path | None = None,
) -> dict[str, Any]:
    monitor = _read_json(monitor_path)
    freeze = _read_json(v14_freeze_path)
    counts = monitor.get("counts", {}) if isinstance(monitor.get("counts"), Mapping) else {}
    failed_cases = int(counts.get("failed_cases", 0) or 0)
    completed_cases = int(counts.get("completed_cases", 0) or 0)
    expected_cases = int(counts.get("expected_cases", 0) or 0)
    missing_cases = int(counts.get("missing_cases", 0) or 0)
    pid_alive = monitor.get("pid_alive") is True
    health_status = str(monitor.get("health_status", "missing_monitor"))
    has_failed_live_root = pid_alive and (
        failed_cases > 0 or health_status == "running_with_failures_requires_attention"
    )
    qualification_root = (
        v14_qualification_root
        if v14_qualification_root is not None
        else ROOT / V14_QUALIFICATION_ROOT
    )
    formal_root = (
        v14_formal_root
        if v14_formal_root is not None
        else ROOT / V14_FORMAL_ROOT
    )
    v14_freeze_ready = bool(
        freeze.get("status") == "completed_frozen_formal_protocol"
        and freeze.get("freeze_version") == "m3-paper-v1-taskshield-reproduction-freeze-1.4"
        and freeze.get("passed_checks") == freeze.get("total_checks") == 16
    )
    blockers: list[str] = []
    if has_failed_live_root:
        blockers.append("v1_3_failed_root_pid_alive_requires_explicit_user_stop_or_wait")
    if not v14_freeze_ready:
        blockers.append("v1_4_freeze_not_ready")
    if qualification_root.exists():
        blockers.append("v1_4_qualification_root_already_exists_review_before_reuse")
    if formal_root.exists():
        blockers.append("v1_4_formal_root_already_exists_review_before_reuse")

    can_start_v14_qualification = not blockers
    status = (
        "ready_for_v14_qualification_after_explicit_decision"
        if can_start_v14_qualification
        else "blocked_waiting_explicit_failed_root_decision"
    )
    package = {
        "schema_version": "paper-taskshield-v14-recovery-decision-package-1.0",
        "package_version": PACKAGE_VERSION,
        "status": status,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "result_eligible_for_formal_tables": False,
        "q2_score_change": 0.0,
        "can_start_v14_qualification_now": can_start_v14_qualification,
        "blockers": blockers,
        "v1_3_root": {
            "run_dir": portable_path(v13_run_dir, root=ROOT),
            "monitor_path": portable_path(monitor_path, root=ROOT),
            "monitor_sha256": _sha256(monitor_path),
            "health_status": health_status,
            "pid": monitor.get("pid"),
            "pid_alive": pid_alive,
            "completed_cases": completed_cases,
            "failed_cases": failed_cases,
            "missing_cases": missing_cases,
            "expected_cases": expected_cases,
            "formal_result_admitted_now": monitor.get("formal_result_admitted_now", False),
            "failed_root_policy": (
                "preserve; do not selectively retry, exclude, patch/admit, or pool "
                "partial rows"
            ),
        },
        "v1_4_protocol": {
            "freeze_path": portable_path(v14_freeze_path, root=ROOT),
            "freeze_sha256": _sha256(v14_freeze_path),
            "freeze_ready": v14_freeze_ready,
            "timeout_retry_scope": freeze.get("task_shield", {}).get(
                "timeout_retry_scope", ""
            ),
            "runtime_patch_version": freeze.get("task_shield", {}).get(
                "runtime_patch_version", ""
            ),
            "qualification_root": _freshness(qualification_root),
            "formal_root": _freshness(formal_root),
        },
        "forbidden_actions": [
            "do_not_retry_only_failed_case",
            "do_not_exclude_failed_row",
            "do_not_admit_v1_3_partial_root",
            "do_not_start_v1_4_while_v1_3_pid_is_alive",
            "do_not_write_registries_before_clean_dry_run_admission",
        ],
        "required_gates": [
            "explicit_user_decision_to_stop_or_wait_for_v1_3",
            "v1_3_failed_root_preserved",
            "fresh_v1_4_two_case_qualification_2_of_2_zero_failed",
            "fresh_v1_4_726_case_full_root_exact_coverage_zero_unexplained_failures",
            "v1_4_formal_analysis_hash_linked_to_run",
            "external_baseline_admission_dry_run_clean",
            "explicit_write_registries_only_after_clean_dry_run",
        ],
        "commands": _commands(),
        "operator_decision": {
            "template_json_path": portable_path(
                output_dir / DECISION_TEMPLATE_JSON_NAME, root=ROOT
            ),
            "template_md_path": portable_path(output_dir / DECISION_TEMPLATE_MD_NAME, root=ROOT),
            "approved_decision_path": portable_path(
                output_dir / DECISION_APPROVED_JSON_NAME, root=ROOT
            ),
            "validation_command": (
                "python -m experiments.paper_v1.benchmarks."
                "validate_taskshield_v14_operator_decision "
                f"--package {portable_path(output_dir / PACKAGE_JSON_NAME, root=ROOT)} "
                f"--decision {portable_path(output_dir / DECISION_APPROVED_JSON_NAME, root=ROOT)} "
                f"--output-dir {portable_path(output_dir, root=ROOT)}"
            ),
        },
        "boundary": (
            "Read-only recovery decision package. It does not stop processes, start "
            "model work, retry cases, analyze results, admit baselines, write "
            "registries or change Q2 readiness."
        ),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    package_json_path = output_dir / PACKAGE_JSON_NAME
    _write_json(package_json_path, package)
    _write_markdown(output_dir / PACKAGE_MD_NAME, package)
    _write_operator_decision_template(
        output_dir / DECISION_TEMPLATE_JSON_NAME,
        output_dir / DECISION_TEMPLATE_MD_NAME,
        package=package,
        package_sha256=_sha256(package_json_path),
    )
    return package


def _write_markdown(path: Path, package: Mapping[str, Any]) -> None:
    commands = package["commands"]
    v13 = package["v1_3_root"]
    lines = [
        "# Task Shield v1.4 recovery decision package",
        "",
        f"- Status: `{package['status']}`",
        f"- Result eligible: `{package['result_eligible_for_formal_tables']}`",
        f"- Q2 score change: `{package['q2_score_change']}`",
        f"- Can start v1.4 qualification now: `{package['can_start_v14_qualification_now']}`",
        "",
        "## v1.3 failed-root snapshot",
        "",
        f"- Run dir: `{v13['run_dir']}`",
        f"- Health: `{v13['health_status']}`",
        f"- PID: `{v13['pid']}`, alive: `{v13['pid_alive']}`",
        f"- Counts: {v13['completed_cases']}/{v13['expected_cases']} completed, "
        f"{v13['failed_cases']} failed, {v13['missing_cases']} missing",
        "",
        "## Required gates",
        "",
    ]
    lines.extend(f"- `{gate}`" for gate in package["required_gates"])
    lines.extend(
        [
            "",
            "## Commands",
            "",
            f"- Refresh v1.3 monitor: `{commands['refresh_v13_monitor']}`",
            f"- Refresh Q2 plan: `{commands['refresh_q2_plan']}`",
            f"- v1.4 qualification after explicit stop/wait decision: "
            f"`{commands['v14_qualification_after_explicit_stop']}`",
            f"- v1.4 full formal after clean qualification: "
            f"`{commands['v14_full_formal_after_clean_qualification']}`",
            f"- v1.4 analysis after complete formal: "
            f"`{commands['v14_analyze_after_complete_formal']}`",
            f"- v1.4 admission dry run: "
            f"`{commands['v14_admission_dry_run_after_analysis']}`",
            "",
            "## Operator decision artifact",
            "",
            "- Draft template: "
            f"`{package['operator_decision']['template_json_path']}`",
            "- Approved decision target: "
            f"`{package['operator_decision']['approved_decision_path']}`",
            "- Validation command: "
            f"`{package['operator_decision']['validation_command']}`",
            "",
            "The template is intentionally `draft_unapproved`. A future v1.4 "
            "qualification remains blocked until the approved decision validates "
            "against a fresh recovery package whose v1.3 PID is no longer live.",
            "",
            "## Boundary",
            "",
            str(package["boundary"]),
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_operator_decision_template(
    json_path: Path,
    md_path: Path,
    *,
    package: Mapping[str, Any],
    package_sha256: str,
) -> None:
    v13 = package["v1_3_root"]
    v14 = package["v1_4_protocol"]
    template = {
        "schema_version": "paper-taskshield-v14-operator-decision-1.0",
        "decision_status": "draft_unapproved",
        "approved_by": "",
        "approved_at_utc": "",
        "chosen_recovery_path": "",
        "allowed_recovery_paths": [
            "wait_for_v1_3_to_finish_without_starting_v14",
            "preserve_v1_3_failed_root_start_fresh_v14",
            "abandon_task_shield_baseline_for_current_q2_cycle",
        ],
        "recovery_package_path": portable_path(
            json_path.parent / PACKAGE_JSON_NAME, root=ROOT
        ),
        "recovery_package_sha256": package_sha256,
        "expected_v1_3_run_dir": v13["run_dir"],
        "expected_v1_3_monitor_sha256": v13["monitor_sha256"],
        "expected_v14_qualification_root": v14["qualification_root"]["path"],
        "expected_v14_formal_root": v14["formal_root"]["path"],
        "acknowledgements": {
            "v1_3_failed_root_is_preserved_and_ineligible": False,
            "no_selective_failed_case_retry": False,
            "no_failed_row_exclusion": False,
            "no_v1_3_partial_admission": False,
            "v14_must_start_from_fresh_roots": False,
            "q2_score_does_not_change_until_clean_admission": False,
            "validator_does_not_stop_or_start_processes": False,
        },
        "operator_notes": "",
    }
    _write_json(json_path, template)
    lines = [
        "# Task Shield v1.4 operator decision template",
        "",
        "This is a draft template. Copy the JSON file to "
        f"`{DECISION_APPROVED_JSON_NAME}`, fill the operator fields, choose one "
        "allowed recovery path and set every acknowledgement to `true` only after "
        "the team has explicitly decided how to handle the live/failed v1.3 root.",
        "",
        "Validation command:",
        "",
        f"`{package['operator_decision']['validation_command']}`",
        "",
        "Fail-closed behavior:",
        "",
        "- `draft_unapproved` is never sufficient.",
        "- A package with a live v1.3 PID is never sufficient to start v1.4.",
        "- The validator does not stop processes, start v1.4 or write registries.",
        "- Approval changes no Q2 score until qualification, full run, analysis and admission all pass.",
        "",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--monitor", type=Path, default=DEFAULT_MONITOR)
    parser.add_argument("--v13-run-dir", type=Path, default=DEFAULT_V13_RUN_DIR)
    parser.add_argument("--v14-freeze", type=Path, default=DEFAULT_V14_FREEZE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    package = build_recovery_package(
        monitor_path=args.monitor,
        v13_run_dir=args.v13_run_dir,
        v14_freeze_path=args.v14_freeze,
        output_dir=args.output_dir,
    )
    print(json.dumps(package, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
