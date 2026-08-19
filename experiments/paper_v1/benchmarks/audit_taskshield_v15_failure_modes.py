"""Audit sealed Task Shield v1.4 failures and freeze the v1.5 recovery scope."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .common import portable_path, rows_sha256, sha256_file


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_V14_SEAL = (
    ROOT
    / "protocols"
    / "paper_upgrade_v1"
    / "execution"
    / "taskshield_v14_failed_root_seal_v1"
    / "taskshield_v14_failed_root_seal_v1.json"
)
DEFAULT_V14_DIAGNOSTIC = (
    ROOT
    / "protocols"
    / "paper_upgrade_v1"
    / "execution"
    / "taskshield_formal_v14_failure_diagnostic_v1"
    / "failure_diagnostic.json"
)
DEFAULT_V14_FREEZE = (
    ROOT / "protocols" / "paper_upgrade_v1" / "taskshield_paper_formal_freeze_v14.json"
)
DEFAULT_V14_OUTCOMES = (
    ROOT / "outputs" / "paper_upgrade_v1" / "baselines" / "taskshield_paper_formal_v14" / "outcomes.jsonl"
)
DEFAULT_V14_RUNTIME = (
    ROOT / "experiments" / "paper_v1" / "benchmarks" / "taskshield_paper_runtime.py"
)
DEFAULT_DECISION = (
    ROOT
    / "protocols"
    / "paper_upgrade_v1"
    / "execution"
    / "taskshield_v15_failure_audit_v1"
    / "taskshield_v15_operator_decision.approved.json"
)
DEFAULT_OUTPUT_DIR = (
    ROOT
    / "protocols"
    / "paper_upgrade_v1"
    / "execution"
    / "taskshield_v15_failure_audit_v1"
)
AUDIT_JSON_NAME = "taskshield_v15_failure_mode_audit_v1.json"
AUDIT_MD_NAME = "taskshield_v15_failure_mode_audit_v1.md"

QUALIFICATION_CASE_IDS = (
    "agentdojo:v1:banking:user_task_0",
    "agentdojo:v1:banking:user_task_0:injection_task_0",
    "agentdojo:v1:banking:user_task_1",
    "agentdojo:v1:banking:user_task_1:injection_task_0",
    "agentdojo:v1:banking:user_task_6",
    "agentdojo:v1:banking:user_task_6:injection_task_0",
    "agentdojo:v1:slack:user_task_18",
    "agentdojo:v1:slack:user_task_18:injection_task_1",
    "agentdojo:v1:workspace:user_task_0",
    "agentdojo:v1:workspace:user_task_0:injection_task_0",
    "agentdojo:v1:travel:user_task_0",
    "agentdojo:v1:travel:user_task_0:injection_task_0",
)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path} must contain object rows")
        rows.append(value)
    return rows


def _check(name: str, passed: bool, detail: Any) -> dict[str, Any]:
    return {"name": name, "status": "pass" if passed else "fail", "detail": detail}


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_markdown(path: Path, audit: Mapping[str, Any]) -> None:
    lines = [
        "# Task Shield v1.5 failure-mode audit",
        "",
        f"- Status: `{audit['status']}`",
        f"- Ready to build v1.5: `{audit['ready_to_build_v15']}`",
        f"- v1.4 retained failures: `{audit['v14_failure_summary']['failed_rows']}`",
        "- Result eligible for formal tables: `False`",
        "- Q2 readiness score change: `0`",
        "",
        "## Root cause",
        "",
        str(audit["root_cause"]),
        "",
        "## Evidence gap",
        "",
        str(audit["evidence_gap"]),
        "",
        "## Frozen v1.5 change contract",
        "",
    ]
    lines.extend(f"- `{key}`: `{value}`" for key, value in audit["v15_change_contract"].items())
    lines.extend(["", "## Expanded qualification selection", ""])
    lines.extend(f"- `{row['benchmark_case_id']}` ({row['case_kind']})" for row in audit["qualification_case_rows"])
    lines.extend(["", "## Checks", ""])
    lines.extend(
        f"- `{row['status']}` — `{row['name']}`: `{row['detail']}`"
        for row in audit["checks"]
    )
    lines.extend(["", "## Boundary", "", str(audit["boundary"]), ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def build_audit(
    *,
    v14_seal_path: Path = DEFAULT_V14_SEAL,
    v14_diagnostic_path: Path = DEFAULT_V14_DIAGNOSTIC,
    v14_freeze_path: Path = DEFAULT_V14_FREEZE,
    v14_outcomes_path: Path = DEFAULT_V14_OUTCOMES,
    v14_runtime_path: Path = DEFAULT_V14_RUNTIME,
    decision_path: Path = DEFAULT_DECISION,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    seal = _read_json(v14_seal_path)
    diagnostic = _read_json(v14_diagnostic_path)
    freeze = _read_json(v14_freeze_path)
    decision = _read_json(decision_path)
    outcomes = _read_jsonl(v14_outcomes_path)
    runtime_source = v14_runtime_path.read_text(encoding="utf-8")

    failures = [row for row in outcomes if row.get("status") == "failed"]
    failure_ids = [str(row.get("benchmark_case_id", "")) for row in failures]
    classifications = Counter(
        str(row.get("classification", ""))
        for row in diagnostic.get("failures", [])
        if isinstance(row, Mapping)
    )
    tracebacks = [str(row.get("traceback", "")) for row in failures]
    failure_stage_is_assistant_extraction = all(
        'source="assistant"' in text
        and "check_content" in text
        and "instruction_extraction" not in text
        and "self.extract" in text
        for text in tracebacks
    )
    # The kind string is not rendered in the traceback; extract -> _request proves
    # instruction extraction, while source="assistant" fixes the untrusted stage.
    failure_stage_is_assistant_extraction = failure_stage_is_assistant_extraction or all(
        'source="assistant"' in text and "self.extract" in text and "_request" in text
        for text in tracebacks
    )
    raw_output_missing = all("taskshield_trace" not in row for row in failures)
    parse_before_trace = runtime_source.find("value = _strict_json_array(raw)") < runtime_source.find(
        "self.trace.model_requests.append"
    )

    frozen_rows = [row for row in freeze.get("case_rows", []) if isinstance(row, Mapping)]
    by_id = {str(row.get("benchmark_case_id", "")): dict(row) for row in frozen_rows}
    qualification_rows = [by_id[case_id] for case_id in QUALIFICATION_CASE_IDS if case_id in by_id]
    qualification_kinds = Counter(str(row.get("case_kind", "")) for row in qualification_rows)
    checks = [
        _check(
            "v14_root_is_sealed_and_ineligible",
            seal.get("status") == "sealed_failed_formal_root"
            and seal.get("result_eligible_for_formal_tables") is False,
            seal.get("status"),
        ),
        _check(
            "v14_counts_are_24_completed_2_failed_700_missing",
            seal.get("counts")
            == {
                "completed_cases": 24,
                "failed_cases": 2,
                "missing_cases": 700,
                "expected_cases": 726,
            },
            seal.get("counts"),
        ),
        _check(
            "two_retained_failures_match_diagnostic",
            len(failures) == 2
            and set(failure_ids)
            == {
                "agentdojo:v1:banking:user_task_1",
                "agentdojo:v1:banking:user_task_6",
            }
            and int(diagnostic.get("counts", {}).get("failed_rows", 0)) == 2,
            failure_ids,
        ),
        _check(
            "both_failures_are_model_output_or_parse",
            classifications == {"model_output_or_parse": 2}
            and all(row.get("error") == "verifier returned invalid JSON" for row in failures),
            dict(classifications),
        ),
        _check(
            "both_failures_occurred_in_assistant_content_extraction",
            failure_stage_is_assistant_extraction,
            "check_content -> extract(source=assistant) -> _request -> strict JSON parse",
        ),
        _check(
            "failed_raw_verifier_output_was_not_retained",
            raw_output_missing and parse_before_trace,
            {
                "failed_rows_have_taskshield_trace": not raw_output_missing,
                "v14_parser_runs_before_trace_append": parse_before_trace,
            },
        ),
        _check(
            "operator_authorized_fresh_v15_audit_and_qualification",
            decision.get("decision_status") == "approved"
            and decision.get("chosen_recovery_path")
            == "preserve_v1_4_failed_root_start_v1_5_failure_audit_and_expanded_qualification",
            decision.get("chosen_recovery_path", ""),
        ),
        _check(
            "expanded_qualification_is_exact_6_utility_6_security",
            len(qualification_rows) == 12
            and qualification_kinds == {"utility": 6, "security": 6},
            dict(qualification_kinds),
        ),
    ]
    failed_checks = [str(row["name"]) for row in checks if row["status"] != "pass"]
    change_contract = {
        "post_hoc_failure_recovery_disclosed": True,
        "raw_output_logged_before_parse": True,
        "transport_timeout_attempts": 2,
        "invalid_json_or_non_array_attempts": 2,
        "retry_backoff_seconds": 1.0,
        "trusted_user_extraction_after_exhaustion": "strict_case_failure",
        "untrusted_assistant_or_tool_output_after_exhaustion": "fail_closed_suppress_content",
        "contribution_scoring_after_exhaustion": "fail_closed_zero_scores",
        "case_level_retry": False,
        "selective_failed_row_retry": False,
        "failed_row_exclusion": False,
        "qualification_cases": 12,
        "qualification_result_eligible": False,
        "full_726_case_run_authorized": False,
    }
    audit = {
        "schema_version": "paper-taskshield-v15-failure-mode-audit-1.0",
        "status": "completed_failure_mode_audit" if not failed_checks else "blocked_failure_mode_audit",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "ready_to_build_v15": not failed_checks,
        "result_eligible_for_formal_tables": False,
        "q2_readiness_score_change": 0,
        "v14_failure_summary": {
            "failed_rows": len(failures),
            "failed_case_ids": failure_ids,
            "classifications": dict(classifications),
            "stage": "assistant_content_instruction_extraction",
        },
        "root_cause": (
            "The verifier returned invalid JSON while extracting instructions from assistant "
            "content. v1.4 retried only transport timeout exceptions, so both cases terminated."
        ),
        "evidence_gap": (
            "v1.4 parsed before appending the verifier request to TaskShieldTrace; failed rows "
            "therefore retain the exception and traceback but not the raw invalid model output."
        ),
        "v15_change_contract": change_contract,
        "qualification_case_rows": qualification_rows,
        "qualification_case_rows_sha256": rows_sha256(qualification_rows),
        "checks": checks,
        "failed_checks": failed_checks,
        "references": {
            name: {"path": portable_path(path, root=ROOT), "sha256": sha256_file(path)}
            for name, path in {
                "v14_seal": v14_seal_path,
                "v14_failure_diagnostic": v14_diagnostic_path,
                "v14_freeze": v14_freeze_path,
                "v14_outcomes": v14_outcomes_path,
                "v14_runtime_source": v14_runtime_path,
                "operator_decision": decision_path,
            }.items()
        },
        "boundary": (
            "This is a read-only, post-hoc failure audit and a prospective v1.5 change/selection "
            "freeze. It never modifies or promotes v1.4, never retries a v1.4 row, and does not "
            "authorize a v1.5 full formal run."
        ),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / AUDIT_JSON_NAME, audit)
    _write_markdown(output_dir / AUDIT_MD_NAME, audit)
    return audit


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--fail-on-blocked", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    audit = build_audit(output_dir=args.output_dir)
    print(
        json.dumps(
            {
                "status": audit["status"],
                "ready_to_build_v15": audit["ready_to_build_v15"],
                "failed_checks": audit["failed_checks"],
                "qualification_cases": len(audit["qualification_case_rows"]),
            },
            ensure_ascii=False,
        )
    )
    return 1 if args.fail_on_blocked and not audit["ready_to_build_v15"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
