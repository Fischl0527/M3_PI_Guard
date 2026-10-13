"""固化直接观察到的非零第 2 日 Harness 失败结果。

忠实记录失败原因与追踪日志，绝不掩盖测试未通过状态。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

from experiments.paper_v2 import adaptive_execution_order_gate_v2 as order_gate
from experiments.paper_v2.contracts import canonical_json_bytes, sha256_canonical_json


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUN_ROOT = (
    PROJECT_ROOT
    / "outputs/verification/experiment_closeout_day2_harness_v1_20260802"
)
LAUNCH_PATH = RUN_ROOT / "launch.json"
RUNNING_PATH = RUN_ROOT / "running.json"
STDOUT_PATH = RUN_ROOT / "stdout.log"
STDERR_PATH = RUN_ROOT / "stderr.log"
RECEIPT_PATH = RUN_ROOT / "receipt.json"
HELPER_PATH = PROJECT_ROOT / "harness/scripts/verify_with_receipt_v1.ps1"
LAUNCHER_PATH = (
    PROJECT_ROOT
    / "outputs/verification/start_experiment_closeout_day2_harness_v1.ps1"
)
REVIEW_PATH = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/experiment_closeout_day2_harness_failure_review_v1.json"
)
TEST_PATH = (
    PROJECT_ROOT
    / "tests/unit/test_paper_v2_experiment_closeout_day2_harness_failure_review_v1.py"
)

SCHEMA_VERSION = "m3-paper-v2-experiment-closeout-day2-harness-failure-review-1.0"
REVIEWED_AT = "2026-08-03T01:22:00+08:00"
FAILED_CHECK = "Paper-v2 experiment closeout prospective evidence"
FAILED_COMMAND = (
    "F:\\robot\\Anaconda3\\python.exe -m "
    "experiments.paper_v2.adaptive_formal_pro_controller_v1 "
    "--verify-admission --stage pro_50"
)
EXPECTED_PRIOR_VERIFY_SHA256 = (
    "715a6bc995ac5b7275aa13def3bb58eeb21f719ed11f8fc19e6dd3fca2863007"
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
    "Historical evidence and current V2 freeze",
)
PYTEST_SUMMARY = re.compile(
    r"(?P<passed>\d+) passed, (?P<skipped>\d+) skipped, "
    r"(?P<warnings>\d+) warnings in (?P<duration>[^\r\n]+)"
)


class ExperimentCloseoutDay2HarnessFailureReviewV1Error(ValueError):
    """当失败的 Day-2 Harness 论据无法再复现时抛出的异常。"""


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
        raise ExperimentCloseoutDay2HarnessFailureReviewV1Error(
            f"missing Day-2 failure evidence: {path}"
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
        raise ExperimentCloseoutDay2HarnessFailureReviewV1Error(
            f"{path}: invalid JSON"
        ) from exc
    if not isinstance(value, dict):
        raise ExperimentCloseoutDay2HarnessFailureReviewV1Error(
            f"{path}: expected object"
        )
    return value


def _analyze_transcript(stdout: str, stderr: str) -> dict[str, Any]:
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
        raise ExperimentCloseoutDay2HarnessFailureReviewV1Error(
            "Day-2 failure pytest summary is missing or ambiguous"
        )
    summary = summaries[0].groupdict()
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
        "failed_command_observed": (
            f"Command failed with exit code 1: {FAILED_COMMAND}" in stdout
        ),
        "stage_admission_drift_observed": (
            "AdaptiveFormalProControllerV1Error: stage admission drift" in stderr
        ),
        "python_traceback_count": stderr.count("Traceback (most recent call last)"),
        "runtime_auditor_delete_blocks": stderr.count(
            "[RuntimeAuditor] Blocked tool call: delete_record"
        ),
    }
    if (
        pass_names != list(EXPECTED_PASS_NAMES)
        or fail_names != [FAILED_CHECK]
        or observations["terminal_failure_marker_count"] != 1
        or not observations["terminal_failure_marker_is_last_nonempty_line"]
        or observations["pytest_passed"] != 1438
        or observations["pytest_skipped"] != 1
        or observations["pytest_warnings"] != 3
        or not observations["failed_command_observed"]
        or not observations["stage_admission_drift_observed"]
        or observations["python_traceback_count"] != 1
    ):
        raise ExperimentCloseoutDay2HarnessFailureReviewV1Error(
            "Day-2 failure transcript signature drift"
        )
    return observations


def build_review() -> dict[str, Any]:
    receipt = _read_json(RECEIPT_PATH)
    launch = _read_json(LAUNCH_PATH)
    running = _read_json(RUNNING_PATH)
    stdout = STDOUT_PATH.read_text(encoding="utf-8", errors="replace")
    stderr = STDERR_PATH.read_text(encoding="utf-8", errors="replace")
    observations = _analyze_transcript(stdout, stderr)
    if (
        receipt.get("schema_version") != "m3-harness-detached-receipt-1.0"
        or receipt.get("status") != "completed_nonzero"
        or receipt.get("exit_code") != 1
        or receipt.get("operating_system_exit_code_directly_observed") is not True
        or receipt.get("network_or_provider_call_authorized") is not False
        or receipt.get("verify_script_sha256") != EXPECTED_PRIOR_VERIFY_SHA256
        or receipt.get("stdout_sha256") != _sha256_file(STDOUT_PATH)
        or receipt.get("stderr_sha256") != _sha256_file(STDERR_PATH)
        or receipt.get("running_sha256") != _sha256_file(RUNNING_PATH)
        or receipt.get("helper_script_sha256") != _sha256_file(HELPER_PATH)
        or launch.get("status") != "launched_detached"
        or launch.get("automatic_restart") is not False
        or launch.get("network_or_provider_call_authorized") is not False
        or launch.get("helper_script_sha256") != _sha256_file(HELPER_PATH)
        or launch.get("launcher_script_sha256") != _sha256_file(LAUNCHER_PATH)
        or running.get("status") != "running"
        or running.get("verify_script_sha256") != EXPECTED_PRIOR_VERIFY_SHA256
        or running.get("network_or_provider_call_authorized") is not False
    ):
        raise ExperimentCloseoutDay2HarnessFailureReviewV1Error(
            "Day-2 failure receipt or immutable source lock drift"
        )

    supersession = order_gate.verify_supersession_order_review()
    seals = {row["stage"]: row for row in supersession["v1_seals"]}
    if (
        set(seals) != {"pro_50", "flash_50"}
        or any(row["candidate_admission_binding_matches"] for row in seals.values())
        or any(row["v1_execution_authorized"] for row in seals.values())
        or any(row["nonempty_output_files"] != 0 for row in seals.values())
    ):
        raise ExperimentCloseoutDay2HarnessFailureReviewV1Error(
            "adaptive v1 supersession evidence drift"
        )

    core = {
        "schema_version": SCHEMA_VERSION,
        "artifact_role": "immutable_review_of_direct_exit_one_day2_harness",
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
            _lock(order_gate.REVIEW_PATH),
            _lock(Path(__file__)),
            _lock(TEST_PATH),
        ],
        "observations": observations,
        "root_cause": {
            "classification": "stale_current_harness_command",
            "failed_check": FAILED_CHECK,
            "failed_command": FAILED_COMMAND,
            "historical_admission_drift_is_expected_and_fail_closed": True,
            "supersession_manifest_sha256": supersession["manifest_sha256"],
            "superseded_stages": ["pro_50", "flash_50"],
        },
        "remediation_boundary": {
            "replace_obsolete_current_harness_admission_checks": True,
            "verify_supersession_order_review_instead": True,
            "modify_v1_candidates_or_admissions": False,
            "resume_or_retry_v1_execution": False,
            "fresh_full_harness_run_required": True,
        },
        "evidence_boundary": {
            "credentials_read_by_review": False,
            "provider_calls_made_by_review": 0,
            "provider_calls_made_by_failed_harness": 0,
            "network_calls_made_by_review": 0,
            "scientific_outcomes_accessed": False,
            "historical_files_mutated": False,
            "provider_canary_authorized": False,
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
        raise ExperimentCloseoutDay2HarnessFailureReviewV1Error(
            "Day-2 failure review artifact drift"
        )
    return dict(value)


def verify_review() -> dict[str, Any]:
    if not REVIEW_PATH.is_file():
        raise ExperimentCloseoutDay2HarnessFailureReviewV1Error(
            "Day-2 failure review artifact missing"
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
