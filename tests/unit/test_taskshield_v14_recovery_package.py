from __future__ import annotations

import json
from pathlib import Path

from experiments.paper_v1.benchmarks.prepare_taskshield_v14_recovery_package import (
    build_recovery_package,
)
from experiments.paper_v1.benchmarks.validate_taskshield_v14_operator_decision import (
    build_operator_decision_validation,
)


def _write(path: Path, value: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_recovery_package_blocks_live_failed_v13_root(tmp_path: Path) -> None:
    monitor = _write(
        tmp_path / "monitor.json",
        {
            "health_status": "running_with_failures_requires_attention",
            "pid": 12345,
            "pid_alive": True,
            "formal_result_admitted_now": False,
            "counts": {
                "completed_cases": 35,
                "failed_cases": 1,
                "missing_cases": 690,
                "expected_cases": 726,
            },
        },
    )
    freeze = _write(
        tmp_path / "taskshield_paper_formal_freeze_v14.json",
        {
            "status": "completed_frozen_formal_protocol",
            "freeze_version": "m3-paper-v1-taskshield-reproduction-freeze-1.4",
            "passed_checks": 16,
            "total_checks": 16,
            "task_shield": {
                "timeout_retry_scope": "verifier_model_transport_timeout_only",
                "runtime_patch_version": "m3-paper-v1-taskshield-timeout-retry-1.4",
            },
        },
    )

    package = build_recovery_package(
        monitor_path=monitor,
        v13_run_dir=tmp_path / "taskshield_paper_formal_v13",
        v14_freeze_path=freeze,
        output_dir=tmp_path / "out",
        v14_qualification_root=tmp_path / "qualification",
        v14_formal_root=tmp_path / "formal",
    )

    assert package["status"] == "blocked_waiting_explicit_failed_root_decision"
    assert package["result_eligible_for_formal_tables"] is False
    assert package["q2_score_change"] == 0.0
    assert package["can_start_v14_qualification_now"] is False
    assert "v1_3_failed_root_pid_alive_requires_explicit_user_stop_or_wait" in package["blockers"]
    assert package["v1_3_root"]["failed_cases"] == 1
    assert package["v1_4_protocol"]["freeze_ready"] is True
    assert "do_not_retry_only_failed_case" in package["forbidden_actions"]
    assert "prepare_taskshield_v14_recovery_package" not in package["commands"][
        "v14_qualification_after_explicit_stop"
    ]
    assert "run_taskshield_paper_formal_v14" in package["commands"][
        "v14_qualification_after_explicit_stop"
    ]
    assert "--admit-formal" not in package["commands"]["v14_qualification_after_explicit_stop"]
    assert "--no-resume" in package["commands"]["v14_qualification_after_explicit_stop"]
    assert "--admit-formal" in package["commands"]["v14_full_formal_after_clean_qualification"]
    assert (tmp_path / "out" / "taskshield_v14_recovery_decision_v1.json").is_file()
    assert (tmp_path / "out" / "taskshield_v14_recovery_decision_v1.md").is_file()
    assert (tmp_path / "out" / "taskshield_v14_operator_decision_template.json").is_file()
    assert (tmp_path / "out" / "taskshield_v14_operator_decision_template.md").is_file()
    template = json.loads(
        (tmp_path / "out" / "taskshield_v14_operator_decision_template.json").read_text(
            encoding="utf-8"
        )
    )
    assert template["decision_status"] == "draft_unapproved"
    assert template["recovery_package_sha256"]
    assert template["acknowledgements"]["no_failed_row_exclusion"] is False


def test_operator_decision_validation_blocks_draft_and_live_root(tmp_path: Path) -> None:
    monitor = _write(
        tmp_path / "monitor.json",
        {
            "health_status": "running_with_failures_requires_attention",
            "pid": 12345,
            "pid_alive": True,
            "counts": {
                "completed_cases": 38,
                "failed_cases": 1,
                "missing_cases": 687,
                "expected_cases": 726,
            },
        },
    )
    freeze = _write(
        tmp_path / "taskshield_paper_formal_freeze_v14.json",
        {
            "status": "completed_frozen_formal_protocol",
            "freeze_version": "m3-paper-v1-taskshield-reproduction-freeze-1.4",
            "passed_checks": 16,
            "total_checks": 16,
            "task_shield": {},
        },
    )
    build_recovery_package(
        monitor_path=monitor,
        v13_run_dir=tmp_path / "taskshield_paper_formal_v13",
        v14_freeze_path=freeze,
        output_dir=tmp_path / "out",
        v14_qualification_root=tmp_path / "qualification",
        v14_formal_root=tmp_path / "formal",
    )

    audit = build_operator_decision_validation(
        package_path=tmp_path / "out" / "taskshield_v14_recovery_decision_v1.json",
        decision_path=tmp_path / "out" / "taskshield_v14_operator_decision_template.json",
        output_dir=tmp_path / "out",
    )

    assert audit["status"] == "blocked_not_approved_to_start_v14"
    assert audit["approved_to_start_v14_qualification"] is False
    assert "recovery_package_not_ready_for_v14_qualification" in audit["blockers"]
    assert "decision_status_not_approved" in audit["blockers"]
    assert "acknowledgement_missing:no_failed_row_exclusion" in audit["blockers"]
    assert audit["q2_score_change"] == 0.0
    assert (tmp_path / "out" / "taskshield_v14_operator_decision_validation_v1.json").is_file()


def test_operator_decision_validation_does_not_cascade_missing_decision(
    tmp_path: Path,
) -> None:
    package_path = tmp_path / "package.json"
    package_path.write_text(
        json.dumps(
            {
                "status": "blocked_waiting_explicit_failed_root_decision",
                "can_start_v14_qualification_now": False,
                "v1_3_root": {},
                "v1_4_protocol": {},
            }
        ),
        encoding="utf-8",
    )

    audit = build_operator_decision_validation(
        package_path=package_path,
        decision_path=tmp_path / "missing-approved-decision.json",
        output_dir=tmp_path / "validation",
    )

    assert audit["approved_to_start_v14_qualification"] is False
    assert audit["blockers"] == [
        "missing_operator_decision",
        "recovery_package_not_ready_for_v14_qualification",
        "recovery_package_status_not_ready",
    ]


def test_recovery_package_can_be_ready_after_failed_root_is_not_alive(tmp_path: Path) -> None:
    monitor = _write(
        tmp_path / "monitor.json",
        {
            "health_status": "stopped_without_terminal_manifest",
            "pid": 12345,
            "pid_alive": False,
            "formal_result_admitted_now": False,
            "counts": {
                "completed_cases": 35,
                "failed_cases": 1,
                "missing_cases": 690,
                "expected_cases": 726,
            },
        },
    )
    freeze = _write(
        tmp_path / "taskshield_paper_formal_freeze_v14.json",
        {
            "status": "completed_frozen_formal_protocol",
            "freeze_version": "m3-paper-v1-taskshield-reproduction-freeze-1.4",
            "passed_checks": 16,
            "total_checks": 16,
            "task_shield": {},
        },
    )

    package = build_recovery_package(
        monitor_path=monitor,
        v13_run_dir=tmp_path / "taskshield_paper_formal_v13",
        v14_freeze_path=freeze,
        output_dir=tmp_path / "out",
        v14_qualification_root=tmp_path / "qualification",
        v14_formal_root=tmp_path / "formal",
    )

    assert package["status"] == "ready_for_v14_qualification_after_explicit_decision"
    assert package["can_start_v14_qualification_now"] is True
    assert package["blockers"] == []


def test_operator_decision_validation_accepts_complete_ready_decision(tmp_path: Path) -> None:
    monitor = _write(
        tmp_path / "monitor.json",
        {
            "health_status": "stopped_without_terminal_manifest",
            "pid": 12345,
            "pid_alive": False,
            "counts": {
                "completed_cases": 38,
                "failed_cases": 1,
                "missing_cases": 687,
                "expected_cases": 726,
            },
        },
    )
    freeze = _write(
        tmp_path / "taskshield_paper_formal_freeze_v14.json",
        {
            "status": "completed_frozen_formal_protocol",
            "freeze_version": "m3-paper-v1-taskshield-reproduction-freeze-1.4",
            "passed_checks": 16,
            "total_checks": 16,
            "task_shield": {},
        },
    )
    build_recovery_package(
        monitor_path=monitor,
        v13_run_dir=tmp_path / "taskshield_paper_formal_v13",
        v14_freeze_path=freeze,
        output_dir=tmp_path / "out",
        v14_qualification_root=tmp_path / "qualification",
        v14_formal_root=tmp_path / "formal",
    )
    decision_path = tmp_path / "out" / "taskshield_v14_operator_decision.approved.json"
    decision = json.loads(
        (tmp_path / "out" / "taskshield_v14_operator_decision_template.json").read_text(
            encoding="utf-8"
        )
    )
    decision["decision_status"] = "approved"
    decision["approved_by"] = "operator"
    decision["approved_at_utc"] = "2026-07-22T10:20:00+00:00"
    decision["chosen_recovery_path"] = "preserve_v1_3_failed_root_start_fresh_v14"
    decision["acknowledgements"] = {
        key: True for key in decision["acknowledgements"]
    }
    _write(decision_path, decision)

    audit = build_operator_decision_validation(
        package_path=tmp_path / "out" / "taskshield_v14_recovery_decision_v1.json",
        decision_path=decision_path,
        output_dir=tmp_path / "out",
    )

    assert audit["status"] == "approved_to_start_v14_qualification"
    assert audit["approved_to_start_v14_qualification"] is True
    assert audit["blockers"] == []
    assert audit["result_eligible_for_formal_tables"] is False
    assert audit["q2_score_change"] == 0.0
