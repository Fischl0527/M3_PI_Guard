"""Bind the fresh v6 Harness evidence without authorizing provider execution.

This gate is deliberately non-authorizing.  It proves that the latest complete
Harness run ended with a directly observed zero exit and that the current
closeout prerequisites still reproduce.  A provider run additionally needs a
separate exact prospective admission, an untouched output root, and its own
budget/quota-day reservation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

from experiments.paper_v2 import adaptive_execution_order_gate_v2 as order_gate
from experiments.paper_v2 import gemini_public_controller_v5 as gemini_v5
from experiments.paper_v2 import independent_blind_day1_acceptance_v1 as day1
from experiments.paper_v2 import public_second_evidence_merge_v1 as flash_merge
from experiments.paper_v2 import sandbox_git_safe_directory_qualification_v1 as git_gate
from experiments.paper_v2 import (
    experiment_closeout_fresh_harness_failure_review_v5 as failure_review,
)
from experiments.paper_v2.contracts import canonical_json_bytes, sha256_canonical_json


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUN_ROOT = (
    PROJECT_ROOT
    / "outputs/verification/experiment_closeout_fresh_harness_v6_20260805"
)
RUNNING_PATH = RUN_ROOT / "running.json"
STDOUT_PATH = RUN_ROOT / "stdout.log"
STDERR_PATH = RUN_ROOT / "stderr.log"
RECEIPT_PATH = RUN_ROOT / "receipt.json"
LAUNCH_PATH = RUN_ROOT / "launch.json"
HELPER_PATH = PROJECT_ROOT / "harness/scripts/verify_with_receipt_v3.ps1"
LAUNCHER_PATH = (
    PROJECT_ROOT
    / "outputs/verification/start_experiment_closeout_fresh_harness_v6.ps1"
)
TEST_PATH = (
    PROJECT_ROOT / "tests/unit/test_paper_v2_experiment_closeout_harness_gate_v4.py"
)
GATE_PATH = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/experiment_closeout_harness_gate_v4.json"
)

SCHEMA_VERSION = "m3-paper-v2-experiment-closeout-harness-gate-4.0"
EXPECTED_PYTEST_PASSED = 1538
EXPECTED_PYTEST_SKIPPED = 1
EXPECTED_PYTEST_WARNINGS = 3
EXPECTED_RUNTIME_AUDITOR_DELETE_BLOCKS = 183
EXPECTED_AGENTDOJO_COMMIT = "089ed468cf3ed0322acc66b0211f26d9d90dbf60"
EXPECTED_RECEIPT_CHECKS = (
    "child_exit_code_zero",
    "verifier_source_stable",
    "helper_source_stable",
    "process_scoped_git_qualification_passed",
    "global_git_config_mutated_false",
    "repository_git_config_mutated_false",
    "exactly_one_aggregate_marker",
    "exactly_one_zero_marker",
    "aggregate_marker_is_terminal",
    "no_failed_harness_stage",
    "network_or_provider_call_authorized_false",
)
EXPECTED_PASS_NAMES = (
    "Harness files",
    "Harness and project source boundary",
    "Project layout and naming conventions",
    "JSON contracts",
    "PowerShell syntax",
    "Shell syntax",
    "Python compile",
    "Unit and integration tests",
    "Experiment registry structure",
    "Paper-v2 source-audit evidence",
    "Paper-v2 frozen study assets",
    "Paper-v2 experiment closeout prospective evidence",
    "Historical evidence and current V2 freeze",
)
PYTEST_SUMMARY = re.compile(
    r"(?P<passed>\d+) passed, (?P<skipped>\d+) skipped, "
    r"(?P<warnings>\d+) warnings in (?P<duration>[^\r\n]+)"
)
SECRET_PATTERNS = (
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]{12,}"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"\bAQ\.[A-Za-z0-9._-]{12,}"),
)


class ExperimentCloseoutHarnessGateV4Error(ValueError):
    """Raised when v6 Harness evidence or a closeout prerequisite drifts."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _display_path(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()


def _lock(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ExperimentCloseoutHarnessGateV4Error(
            f"missing v6 Harness artifact: {path}"
        )
    return {
        "path": _display_path(path),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ExperimentCloseoutHarnessGateV4Error(f"{path}: invalid JSON") from exc
    if not isinstance(value, dict):
        raise ExperimentCloseoutHarnessGateV4Error(f"{path}: expected object")
    return value


def _secret_pattern_hit_count(*texts: str) -> int:
    return sum(len(pattern.findall(text)) for pattern in SECRET_PATTERNS for text in texts)


def analyze_transcript(stdout: str, stderr: str) -> dict[str, Any]:
    pass_names = [
        line.removeprefix("PASS: ")
        for line in stdout.splitlines()
        if line.startswith("PASS: ")
    ]
    fail_lines = [line for line in stdout.splitlines() if line.startswith("FAIL: ")]
    terminal_count = sum(
        line == "Verification failed=0" for line in stdout.splitlines()
    )
    summaries = list(PYTEST_SUMMARY.finditer(stdout))
    if len(summaries) != 1:
        raise ExperimentCloseoutHarnessGateV4Error(
            "v6 Harness pytest summary is missing or ambiguous"
        )
    summary = summaries[0].groupdict()
    observations = {
        "pass_names": pass_names,
        "fail_line_count": len(fail_lines),
        "terminal_zero_marker_count": terminal_count,
        "terminal_zero_marker_is_last_nonempty_line": stdout.rstrip().endswith(
            "Verification failed=0"
        ),
        "pytest_passed": int(summary["passed"]),
        "pytest_skipped": int(summary["skipped"]),
        "pytest_warnings": int(summary["warnings"]),
        "pytest_duration": summary["duration"],
        "python_traceback_observed": "Traceback (most recent call last)" in stderr,
        "runtime_auditor_delete_blocks": stderr.count(
            "[RuntimeAuditor] Blocked tool call: delete_record"
        ),
        "secret_pattern_hit_count": _secret_pattern_hit_count(stdout, stderr),
    }
    if (
        pass_names != list(EXPECTED_PASS_NAMES)
        or observations["fail_line_count"] != 0
        or terminal_count != 1
        or not observations["terminal_zero_marker_is_last_nonempty_line"]
        or observations["pytest_passed"] != EXPECTED_PYTEST_PASSED
        or observations["pytest_skipped"] != EXPECTED_PYTEST_SKIPPED
        or observations["pytest_warnings"] != EXPECTED_PYTEST_WARNINGS
        or observations["python_traceback_observed"]
        or observations["runtime_auditor_delete_blocks"]
        != EXPECTED_RUNTIME_AUDITOR_DELETE_BLOCKS
        or observations["secret_pattern_hit_count"] != 0
    ):
        raise ExperimentCloseoutHarnessGateV4Error(
            "v6 Harness terminal evidence did not pass"
        )
    return observations


def _validate_receipt_chain(
    receipt: Mapping[str, Any],
    running: Mapping[str, Any],
    launch: Mapping[str, Any],
) -> None:
    checks = receipt.get("checks")
    historical_verify_sha = receipt.get("verify_script_sha256_before")
    historical_helper_sha = receipt.get("helper_script_sha256_before")
    if (
        receipt.get("schema_version") != "m3-harness-detached-receipt-3.0"
        or receipt.get("status") != "completed_exit_zero_evidence_pass"
        or receipt.get("operating_system_exit_code_directly_observed") is not True
        or receipt.get("child_exit_code") != 0
        or receipt.get("exit_code") != 0
        or receipt.get("evidence_gate_passed") is not True
        or not isinstance(checks, Mapping)
        or tuple(checks) != EXPECTED_RECEIPT_CHECKS
        or any(checks[name] is not True for name in EXPECTED_RECEIPT_CHECKS)
        or receipt.get("aggregate_marker_count") != 1
        or receipt.get("zero_marker_count") != 1
        or receipt.get("failed_harness_stage_count") != 0
        or receipt.get("network_or_provider_call_authorized") is not False
        or receipt.get("automatic_restart") is not False
        or running.get("schema_version") != "m3-harness-detached-running-3.0"
        or running.get("status") != "running"
        or running.get("network_or_provider_call_authorized") is not False
        or running.get("automatic_restart") is not False
        or launch.get("schema_version") != "m3-harness-detached-launch-3.0"
        or launch.get("status") != "launched_detached"
        or launch.get("automatic_restart") is not False
        or launch.get("network_or_provider_call_authorized") is not False
        or receipt.get("stdout_sha256") != _sha256_file(STDOUT_PATH)
        or receipt.get("stderr_sha256") != _sha256_file(STDERR_PATH)
        or receipt.get("running_sha256") != _sha256_file(RUNNING_PATH)
        or historical_verify_sha != receipt.get("verify_script_sha256_after")
        or historical_verify_sha != running.get("verify_script_sha256")
        or historical_verify_sha != launch.get("verify_script_sha256")
        or historical_helper_sha != receipt.get("helper_script_sha256_after")
        or historical_helper_sha != running.get("helper_script_sha256")
        or historical_helper_sha != launch.get("helper_script_sha256")
        or historical_helper_sha != _sha256_file(HELPER_PATH)
        or launch.get("helper_script_sha256") != _sha256_file(HELPER_PATH)
        or launch.get("launcher_script_sha256") != _sha256_file(LAUNCHER_PATH)
        or receipt.get("expected_agentdojo_commit") != EXPECTED_AGENTDOJO_COMMIT
        or receipt.get("observed_agentdojo_commit") != EXPECTED_AGENTDOJO_COMMIT
        or receipt.get("git_safe_directory_scope") != "process_only"
        or receipt.get("global_git_config_mutated") is not False
        or receipt.get("repository_git_config_mutated") is not False
    ):
        raise ExperimentCloseoutHarnessGateV4Error(
            "v6 Harness receipt or historical source chain drift"
        )


def build_gate() -> dict[str, Any]:
    failure = failure_review.verify_review()
    git_qualification = git_gate.verify_qualification()
    order = order_gate.verify_supersession_order_review()
    registration = day1.verify_acceptance()
    flash = flash_merge.verify_merge()
    gemini = gemini_v5.verify_candidate()
    receipt = _read_json(RECEIPT_PATH)
    running = _read_json(RUNNING_PATH)
    launch = _read_json(LAUNCH_PATH)
    stdout = STDOUT_PATH.read_text(encoding="utf-8", errors="replace")
    stderr = STDERR_PATH.read_text(encoding="utf-8", errors="replace")
    observations = analyze_transcript(stdout, stderr)
    _validate_receipt_chain(receipt, running, launch)

    if (
        failure.get("status") != "failed_harness_frozen_no_provider_execution"
        or git_qualification.get("status")
        != "qualified_process_scoped_safe_directory"
        or order.get("status")
        != "v1_stages_superseded_before_execution_order_v2_frozen"
        or registration.get("status")
        != "independent_custodian_day1_registration_accepted"
        or registration.get("evidence_boundary", {}).get("execution_authorized")
        is not False
        or flash.get("status")
        != "second_evidence_merge_pass_result_access_still_sealed"
        or flash.get("coverage", {}).get("role_records") != 1791
        or flash.get("authorization", {}).get(
            "scientific_outcome_access_authorized"
        )
        is not False
        or gemini.get("status")
        != "candidate_pending_fresh_harness_and_daily_admissions"
        or gemini.get("scope", {}).get("pending_records") != 10
        or gemini.get("scope", {}).get("segment_count") != 7
        or gemini.get("authorization", {}).get("segment_execution_authorized")
        is not False
        or gemini.get("authorization", {}).get("result_admission_authorized")
        is not False
    ):
        raise ExperimentCloseoutHarnessGateV4Error(
            "closeout prerequisite safety boundary drift"
        )

    core = {
        "schema_version": SCHEMA_VERSION,
        "artifact_role": "fresh_v6_direct_exit_non_authorizing_closeout_gate",
        "status": "fresh_v6_full_harness_closeout_prerequisite_satisfied",
        "source_locks": [
            _lock(LAUNCH_PATH),
            _lock(RUNNING_PATH),
            _lock(STDOUT_PATH),
            _lock(STDERR_PATH),
            _lock(RECEIPT_PATH),
            _lock(HELPER_PATH),
            _lock(LAUNCHER_PATH),
            _lock(failure_review.REVIEW_PATH),
            _lock(git_gate.QUALIFICATION_PATH),
            _lock(order_gate.REVIEW_PATH),
            _lock(day1.ACCEPTANCE_PATH),
            _lock(flash_merge.DEFAULT_OUTPUT),
            _lock(gemini_v5.CANDIDATE_PATH),
            _lock(Path(__file__)),
            _lock(TEST_PATH),
        ],
        "prerequisite_manifests": {
            "fresh_harness_v5_failure_review": failure["manifest_sha256"],
            "process_scoped_git_qualification": git_qualification[
                "manifest_sha256"
            ],
            "adaptive_supersession_order": order["manifest_sha256"],
            "day1_custodian_acceptance": registration["manifest_sha256"],
            "flash_second_evidence_merge": flash["manifest_sha256"],
            "gemini_v5_recovery_candidate": gemini["manifest_sha256"],
        },
        "observations": observations,
        "verdict": {
            "operating_system_exit_code_directly_observed": True,
            "full_harness_passed": True,
            "closeout_harness_prerequisite_satisfied": True,
            "provider_execution_authorized_by_gate": False,
            "result_access_authorized_by_gate": False,
            "separate_exact_admission_budget_and_quota_day_required": True,
        },
        "evidence_boundary": {
            "credentials_read": False,
            "provider_calls_made": 0,
            "scientific_outcomes_accessed": False,
            "blind_labels_accessed": False,
            "logs_mutated": False,
            "automatic_restart": False,
            "historical_frozen_assets_mutated": False,
        },
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def write_gate() -> dict[str, Any]:
    value = build_gate()
    GATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    GATE_PATH.write_bytes(canonical_json_bytes(value) + b"\n")
    return value


def verify_gate() -> dict[str, Any]:
    if not GATE_PATH.is_file():
        raise ExperimentCloseoutHarnessGateV4Error("v6 Harness gate artifact missing")
    observed = _read_json(GATE_PATH)
    expected = build_gate()
    if observed != expected:
        raise ExperimentCloseoutHarnessGateV4Error("v6 Harness gate artifact drift")
    return observed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write-gate", action="store_true")
    action.add_argument("--verify-gate", action="store_true")
    args = parser.parse_args()
    value = write_gate() if args.write_gate else verify_gate()
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
