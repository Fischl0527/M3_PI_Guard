"""固化直接观察到的非零全新 Harness v5 失败结果。

记录并在历史中冻结该轮次的异常诊断记录。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

from experiments.paper_v2 import sandbox_git_safe_directory_qualification_v1 as git_gate
from experiments.paper_v2.contracts import canonical_json_bytes, sha256_canonical_json


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUN_ROOT = PROJECT_ROOT / "outputs/verification/experiment_closeout_fresh_harness_v5_20260804"
LAUNCH_PATH = RUN_ROOT / "launch.json"
RUNNING_PATH = RUN_ROOT / "running.json"
STDOUT_PATH = RUN_ROOT / "stdout.log"
STDERR_PATH = RUN_ROOT / "stderr.log"
RECEIPT_PATH = RUN_ROOT / "receipt.json"
HELPER_PATH = PROJECT_ROOT / "harness/scripts/verify_with_receipt_v2.ps1"
LAUNCHER_PATH = (
    PROJECT_ROOT
    / "outputs/verification/start_experiment_closeout_fresh_harness_v5.ps1"
)
REVIEW_PATH = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/experiment_closeout_fresh_harness_failure_review_v5.json"
)
TEST_PATH = (
    PROJECT_ROOT
    / "tests/unit/test_paper_v2_experiment_closeout_fresh_harness_failure_review_v5.py"
)

SCHEMA_VERSION = "m3-paper-v2-experiment-closeout-fresh-harness-failure-review-5.0"
REVIEWED_AT = "2026-08-05T00:20:00+08:00"
EXPECTED_VERIFY_SHA256 = "5f86bc984c0a4f57816b078b09b7484c53e614b3ed751f6e8e225a965fd59e5e"
EXPECTED_HELPER_SHA256 = "92200da1b1e0557a464c8263dc485750f25e3fcf36f90ae88d2420ff474ba232"
EXPECTED_LAUNCHER_SHA256 = "9d21fae65992a227336fea51c2977f58832a91b612bc00f8d189177fb9764a0a"
EXPECTED_STDOUT_SHA256 = "389486c8c307315252b2a74cbad74948d6cab3edf0369b2400576fafacd48b90"
EXPECTED_STDERR_SHA256 = "1268ce510cc0b0742fc5b79822a8f708e6e3f262d2108567a7717e0b5bb2bbb2"
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
)
EXPECTED_FAIL_NAMES = (
    "Paper-v2 frozen study assets",
    "Paper-v2 experiment closeout prospective evidence",
    "Historical evidence and current V2 freeze",
)
FIRST_FAILED_COMMAND = (
    "F:\\robot\\Anaconda3\\python.exe -m "
    "experiments.paper_v2.formal_matrix_controller_v8 --verify-canary-admission"
)
PYTEST_SUMMARY = re.compile(
    r"(?P<passed>\d+) passed, (?P<skipped>\d+) skipped, "
    r"(?P<warnings>\d+) warnings in (?P<duration>[^\r\n]+)"
)
SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"AQ\.[A-Za-z0-9_-]{12,}"),
    re.compile(r"AIza[A-Za-z0-9_-]{12,}"),
)


class ExperimentCloseoutFreshHarnessFailureReviewV5Error(ValueError):
    """当不可变的 Fresh Harness v5 论据发生漂移时抛出的异常。"""


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
        raise ExperimentCloseoutFreshHarnessFailureReviewV5Error(
            f"missing fresh Harness v5 evidence: {path}"
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
        raise ExperimentCloseoutFreshHarnessFailureReviewV5Error(
            f"{path}: invalid JSON"
        ) from exc
    if not isinstance(value, dict):
        raise ExperimentCloseoutFreshHarnessFailureReviewV5Error(
            f"{path}: expected object"
        )
    return value


def analyze_transcript(stdout: str, stderr_bytes: bytes) -> dict[str, Any]:
    stderr = stderr_bytes.decode("utf-8", errors="replace")
    pass_names = [
        line.removeprefix("PASS: ")
        for line in stdout.splitlines()
        if line.startswith("PASS: ")
    ]
    fail_names = [
        line.removeprefix("FAIL: ")
        for line in stdout.splitlines()
        if line.startswith("FAIL: ")
    ]
    summaries = list(PYTEST_SUMMARY.finditer(stdout))
    if len(summaries) != 1:
        raise ExperimentCloseoutFreshHarnessFailureReviewV5Error(
            "fresh Harness v5 pytest summary is missing or ambiguous"
        )
    summary = summaries[0].groupdict()
    secret_pattern_hits = sum(
        len(pattern.findall(stdout)) + len(pattern.findall(stderr))
        for pattern in SECRET_PATTERNS
    )
    observations = {
        "pass_names": pass_names,
        "fail_names": fail_names,
        "terminal_failure_marker_count": sum(
            line == "Verification failed=1" for line in stdout.splitlines()
        ),
        "terminal_failure_marker_is_last_nonempty_line": stdout.rstrip().endswith(
            "Verification failed=1"
        ),
        "pytest_passed": int(summary["passed"]),
        "pytest_skipped": int(summary["skipped"]),
        "pytest_warnings": int(summary["warnings"]),
        "pytest_duration": summary["duration"],
        "first_failed_command_observed": (
            f"Command failed with exit code 1: {FIRST_FAILED_COMMAND}" in stdout
        ),
        "downstream_process_exit_3221226091_count": stdout.count(
            "Command failed with exit code -1073741205:"
        ),
        "python_traceback_count": stderr.count("Traceback (most recent call last)"),
        "runtime_auditor_delete_blocks": stderr.count(
            "[RuntimeAuditor] Blocked tool call: delete_record"
        ),
        "git_rev_parse_mentions": stderr.count("rev-parse"),
        "git_exit_3221226091_observed": "exit status 3221226091" in stderr,
        "secret_pattern_hits": secret_pattern_hits,
    }
    if (
        pass_names != list(EXPECTED_PASS_NAMES)
        or fail_names != list(EXPECTED_FAIL_NAMES)
        or observations["terminal_failure_marker_count"] != 1
        or not observations["terminal_failure_marker_is_last_nonempty_line"]
        or observations["pytest_passed"] != 1531
        or observations["pytest_skipped"] != 1
        or observations["pytest_warnings"] != 3
        or observations["pytest_duration"] != "28907.43s (8:01:47)"
        or not observations["first_failed_command_observed"]
        or observations["downstream_process_exit_3221226091_count"] != 2
        or observations["python_traceback_count"] != 1
        or observations["runtime_auditor_delete_blocks"] != 1
        or observations["git_rev_parse_mentions"] != 2
        or not observations["git_exit_3221226091_observed"]
        or observations["secret_pattern_hits"] != 0
    ):
        raise ExperimentCloseoutFreshHarnessFailureReviewV5Error(
            "fresh Harness v5 failure transcript signature drift"
        )
    return observations


def _validate_receipt_chain(
    receipt: Mapping[str, Any],
    running: Mapping[str, Any],
    launch: Mapping[str, Any],
) -> None:
    checks = receipt.get("checks")
    if (
        receipt.get("schema_version") != "m3-harness-detached-receipt-2.0"
        or receipt.get("status") != "completed_child_nonzero"
        or receipt.get("operating_system_exit_code_directly_observed") is not True
        or receipt.get("child_exit_code") != 1
        or receipt.get("exit_code") != 1
        or receipt.get("evidence_gate_passed") is not False
        or receipt.get("network_or_provider_call_authorized") is not False
        or receipt.get("automatic_restart") is not False
        or not isinstance(checks, Mapping)
        or checks.get("child_exit_code_zero") is not False
        or checks.get("verifier_source_stable") is not True
        or checks.get("helper_source_stable") is not True
        or checks.get("exactly_one_aggregate_marker") is not True
        or checks.get("exactly_one_zero_marker") is not False
        or checks.get("no_failed_harness_stage") is not False
        or receipt.get("verify_script_sha256_before") != EXPECTED_VERIFY_SHA256
        or receipt.get("verify_script_sha256_after") != EXPECTED_VERIFY_SHA256
        or receipt.get("helper_script_sha256_before") != EXPECTED_HELPER_SHA256
        or receipt.get("helper_script_sha256_after") != EXPECTED_HELPER_SHA256
        or receipt.get("stdout_sha256") != EXPECTED_STDOUT_SHA256
        or receipt.get("stderr_sha256") != EXPECTED_STDERR_SHA256
        or receipt.get("stdout_sha256") != _sha256_file(STDOUT_PATH)
        or receipt.get("stderr_sha256") != _sha256_file(STDERR_PATH)
        or receipt.get("running_sha256") != _sha256_file(RUNNING_PATH)
        or receipt.get("stdout_bytes") != STDOUT_PATH.stat().st_size
        or receipt.get("stderr_bytes") != STDERR_PATH.stat().st_size
        or receipt.get("aggregate_marker_count") != 1
        or receipt.get("zero_marker_count") != 0
        or receipt.get("failed_harness_stage_count") != 3
        or running.get("schema_version") != "m3-harness-detached-running-2.0"
        or running.get("verify_script_sha256") != EXPECTED_VERIFY_SHA256
        or running.get("helper_script_sha256") != EXPECTED_HELPER_SHA256
        or running.get("network_or_provider_call_authorized") is not False
        or launch.get("schema_version") != "m3-harness-detached-launch-2.0"
        or launch.get("status") != "launched_detached"
        or launch.get("automatic_restart") is not False
        or launch.get("network_or_provider_call_authorized") is not False
        or launch.get("verify_script_sha256") != EXPECTED_VERIFY_SHA256
        or launch.get("helper_script_sha256") != EXPECTED_HELPER_SHA256
        or launch.get("launcher_script_sha256") != EXPECTED_LAUNCHER_SHA256
        or _sha256_file(HELPER_PATH) != EXPECTED_HELPER_SHA256
        or _sha256_file(LAUNCHER_PATH) != EXPECTED_LAUNCHER_SHA256
    ):
        raise ExperimentCloseoutFreshHarnessFailureReviewV5Error(
            "fresh Harness v5 receipt or immutable source lock drift"
        )


def build_review() -> dict[str, Any]:
    receipt = _read_json(RECEIPT_PATH)
    running = _read_json(RUNNING_PATH)
    launch = _read_json(LAUNCH_PATH)
    stdout = STDOUT_PATH.read_text(encoding="utf-8", errors="replace")
    stderr_bytes = STDERR_PATH.read_bytes()
    observations = analyze_transcript(stdout, stderr_bytes)
    _validate_receipt_chain(receipt, running, launch)
    qualification = git_gate.verify_qualification()

    core = {
        "schema_version": SCHEMA_VERSION,
        "artifact_role": "immutable_review_of_direct_exit_one_fresh_harness_v5",
        "reviewed_at": REVIEWED_AT,
        "status": "failed_harness_frozen_no_provider_execution",
        "source_locks": [
            _lock(LAUNCH_PATH),
            _lock(RUNNING_PATH),
            _lock(STDOUT_PATH),
            _lock(STDERR_PATH),
            _lock(RECEIPT_PATH),
            _lock(HELPER_PATH),
            _lock(LAUNCHER_PATH),
            _lock(git_gate.QUALIFICATION_PATH),
            _lock(Path(__file__)),
            _lock(TEST_PATH),
        ],
        "failed_verify_script_sha256": EXPECTED_VERIFY_SHA256,
        "observations": observations,
        "root_cause": {
            "classification": "sandbox_git_safe_directory_rejection_at_external_checkout",
            "first_failed_check": EXPECTED_FAIL_NAMES[0],
            "first_failed_command": FIRST_FAILED_COMMAND,
            "failed_git_operation": "git -C <agentdojo-checkout> rev-parse HEAD",
            "frozen_agentdojo_commit": git_gate.EXPECTED_COMMIT,
            "sanitized_qualification_manifest_sha256": qualification[
                "manifest_sha256"
            ],
            "process_scoped_remediation_qualified": True,
            "experiment_test_failure": False,
            "provider_failure": False,
        },
        "remediation_boundary": {
            "use_exact_process_scoped_safe_directory": True,
            "inherit_only_into_fresh_harness_child": True,
            "mutate_global_git_config": False,
            "mutate_repository_git_config": False,
            "modify_v5_run_or_historical_evidence": False,
            "fresh_full_harness_run_required": True,
        },
        "evidence_boundary": {
            "credentials_read_by_review": False,
            "provider_calls_made_by_review": 0,
            "provider_calls_made_by_failed_harness": 0,
            "network_calls_made_by_review": 0,
            "scientific_outcomes_modified": False,
            "historical_files_mutated": False,
            "provider_execution_authorized": False,
            "result_access_authorized": False,
        },
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def write_review() -> dict[str, Any]:
    value = build_review()
    REVIEW_PATH.parent.mkdir(parents=True, exist_ok=True)
    REVIEW_PATH.write_bytes(canonical_json_bytes(value) + b"\n")
    return value


def validate_review(value: Mapping[str, Any]) -> dict[str, Any]:
    expected = build_review()
    if dict(value) != expected:
        raise ExperimentCloseoutFreshHarnessFailureReviewV5Error(
            "fresh Harness v5 failure review artifact drift"
        )
    return dict(value)


def verify_review() -> dict[str, Any]:
    if not REVIEW_PATH.is_file():
        raise ExperimentCloseoutFreshHarnessFailureReviewV5Error(
            "fresh Harness v5 failure review artifact missing"
        )
    return validate_review(_read_json(REVIEW_PATH))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write-review", action="store_true")
    action.add_argument("--verify-review", action="store_true")
    args = parser.parse_args()
    value = write_review() if args.write_review else verify_review()
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
