from __future__ import annotations

import json
from pathlib import Path

from experiments.paper_v1.benchmarks.audit_taskshield_v15_failure_modes import (
    QUALIFICATION_CASE_IDS,
    build_audit,
)


def _write_json(path: Path, value: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_v15_failure_audit_freezes_posthoc_scope_and_12_cases(tmp_path: Path) -> None:
    seal = _write_json(
        tmp_path / "seal.json",
        {
            "status": "sealed_failed_formal_root",
            "result_eligible_for_formal_tables": False,
            "counts": {
                "completed_cases": 24,
                "failed_cases": 2,
                "missing_cases": 700,
                "expected_cases": 726,
            },
        },
    )
    diagnostic = _write_json(
        tmp_path / "diagnostic.json",
        {
            "counts": {"failed_rows": 2},
            "failures": [
                {"classification": "model_output_or_parse"},
                {"classification": "model_output_or_parse"},
            ],
        },
    )
    freeze = _write_json(
        tmp_path / "freeze.json",
        {
            "case_rows": [
                {
                    "benchmark_case_id": case_id,
                    "case_kind": "security" if ":injection_task_" in case_id else "utility",
                }
                for case_id in QUALIFICATION_CASE_IDS
            ]
        },
    )
    failure_template = {
        "status": "failed",
        "error": "verifier returned invalid JSON",
        "traceback": (
            'check_content(content=content, source="assistant")\n'
            "self.extract(content=content, source=source)\nself._request(...)"
        ),
    }
    outcomes = tmp_path / "outcomes.jsonl"
    outcomes.write_text(
        "\n".join(
            json.dumps(failure_template | {"benchmark_case_id": case_id})
            for case_id in (
                "agentdojo:v1:banking:user_task_1",
                "agentdojo:v1:banking:user_task_6",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    runtime = tmp_path / "runtime.py"
    runtime.write_text(
        "value = _strict_json_array(raw)\nself.trace.model_requests.append({})\n",
        encoding="utf-8",
    )
    decision = _write_json(
        tmp_path / "decision.json",
        {
            "decision_status": "approved",
            "chosen_recovery_path": (
                "preserve_v1_4_failed_root_start_v1_5_failure_audit_and_expanded_qualification"
            ),
        },
    )

    audit = build_audit(
        v14_seal_path=seal,
        v14_diagnostic_path=diagnostic,
        v14_freeze_path=freeze,
        v14_outcomes_path=outcomes,
        v14_runtime_path=runtime,
        decision_path=decision,
        output_dir=tmp_path / "audit",
    )

    assert audit["status"] == "completed_failure_mode_audit"
    assert audit["ready_to_build_v15"] is True
    assert audit["result_eligible_for_formal_tables"] is False
    assert audit["q2_readiness_score_change"] == 0
    assert len(audit["qualification_case_rows"]) == 12
    assert audit["v15_change_contract"]["full_726_case_run_authorized"] is False
    assert (tmp_path / "audit" / "taskshield_v15_failure_mode_audit_v1.json").is_file()


def test_v15_failure_audit_blocks_if_failed_raw_output_was_claimed_present(
    tmp_path: Path,
) -> None:
    seal = _write_json(
        tmp_path / "seal.json",
        {
            "status": "sealed_failed_formal_root",
            "result_eligible_for_formal_tables": False,
            "counts": {
                "completed_cases": 24,
                "failed_cases": 2,
                "missing_cases": 700,
                "expected_cases": 726,
            },
        },
    )
    diagnostic = _write_json(
        tmp_path / "diagnostic.json",
        {
            "counts": {"failed_rows": 2},
            "failures": [
                {"classification": "model_output_or_parse"},
                {"classification": "model_output_or_parse"},
            ],
        },
    )
    freeze = _write_json(
        tmp_path / "freeze.json",
        {
            "case_rows": [
                {
                    "benchmark_case_id": case_id,
                    "case_kind": "security" if ":injection_task_" in case_id else "utility",
                }
                for case_id in QUALIFICATION_CASE_IDS
            ]
        },
    )
    traceback_text = (
        'check_content(content=content, source="assistant")\n'
        "self.extract(content=content, source=source)\nself._request(...)"
    )
    outcomes = tmp_path / "outcomes.jsonl"
    outcomes.write_text(
        "\n".join(
            json.dumps(
                {
                    "status": "failed",
                    "benchmark_case_id": case_id,
                    "error": "verifier returned invalid JSON",
                    "traceback": traceback_text,
                    "taskshield_trace": {"model_requests": [{"raw_output": "bad"}]},
                }
            )
            for case_id in (
                "agentdojo:v1:banking:user_task_1",
                "agentdojo:v1:banking:user_task_6",
            )
        ),
        encoding="utf-8",
    )
    runtime = tmp_path / "runtime.py"
    runtime.write_text(
        "value = _strict_json_array(raw)\nself.trace.model_requests.append({})\n",
        encoding="utf-8",
    )
    decision = _write_json(
        tmp_path / "decision.json",
        {
            "decision_status": "approved",
            "chosen_recovery_path": (
                "preserve_v1_4_failed_root_start_v1_5_failure_audit_and_expanded_qualification"
            ),
        },
    )

    audit = build_audit(
        v14_seal_path=seal,
        v14_diagnostic_path=diagnostic,
        v14_freeze_path=freeze,
        v14_outcomes_path=outcomes,
        v14_runtime_path=runtime,
        decision_path=decision,
        output_dir=tmp_path / "audit",
    )

    assert audit["status"] == "blocked_failure_mode_audit"
    assert "failed_raw_verifier_output_was_not_retained" in audit["failed_checks"]
