"""固化直接观察到的全新 Harness v10 状态转移失败证据。

深度捕获状态迁移异常堆栈，支持根本原因分析。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

from experiments.paper_v2 import (
    adaptive_formal_pro_200_host_timeout_review_v1 as host_review,
)
from experiments.paper_v2.contracts import (
    canonical_json_bytes,
    sha256_canonical_json,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUN_ROOT = PROJECT_ROOT / (
    "outputs/verification/experiment_closeout_fresh_harness_v10_20260807"
)
LAUNCH_PATH = RUN_ROOT / "launch.json"
RUNNING_PATH = RUN_ROOT / "running.json"
STDOUT_PATH = RUN_ROOT / "stdout.log"
STDERR_PATH = RUN_ROOT / "stderr.log"
RECEIPT_PATH = RUN_ROOT / "receipt.json"
HELPER_PATH = PROJECT_ROOT / "harness/scripts/verify_with_receipt_v3.ps1"
LAUNCHER_PATH = (
    PROJECT_ROOT
    / "outputs/verification/start_experiment_closeout_fresh_harness_v10.ps1"
)
GATE_V6_SOURCE_PATH = (
    PROJECT_ROOT / "experiments/paper_v2/experiment_closeout_harness_gate_v6.py"
)
GATE_V6_ARTIFACT_PATH = (
    PROJECT_ROOT / "protocols/paper_upgrade_v2/experiment_closeout_harness_gate_v6.json"
)
PRO_200_CANDIDATE_PATH = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/adaptive_formal_pro_200_candidate_v2.json"
)
REVIEW_PATH = PROJECT_ROOT / (
    "protocols/paper_upgrade_v2/"
    "experiment_closeout_fresh_harness_failure_review_v10.json"
)
TEST_PATH = PROJECT_ROOT / (
    "tests/unit/test_paper_v2_experiment_closeout_fresh_harness_failure_review_v10.py"
)

SCHEMA_VERSION = "m3-paper-v2-experiment-closeout-fresh-harness-failure-review-10.0"
REVIEWED_AT = "2026-08-07T19:10:00+08:00"
EXPECTED_VERIFY_SHA256 = (
    "147b5133a99333e9c87abbd423b594b6abfd165b1fc4100ab23a4ee5d1bc0e58"
)
EXPECTED_HELPER_SHA256 = (
    "4a5cc0d67d80e039ec8c749437dc0442e3d0487b4444d830bf2a7352716c6cbe"
)
EXPECTED_LAUNCHER_SHA256 = (
    "3247d6228c0aad1ebb2fa98f70c5de7174307967632f1c8b55b4d31fb412add7"
)
EXPECTED_RUNNING_SHA256 = (
    "8c380072ae3894cc1aa59c6bd6face328de18885c3b31dd171fe543cb850d0ad"
)
EXPECTED_STDOUT_SHA256 = (
    "ccfefdd4059dfd0eb21114de82d042c004ea66e4828af74f2d984d4150bc4452"
)
EXPECTED_STDERR_SHA256 = (
    "838453873e5a866e6970f399422e7dab51d5ee5791dbeb47e7ee506d22df197c"
)
EXPECTED_GATE_V6_MANIFEST = (
    "73a57abbd955d6b5099f3fdd1fbb0503017576e3d4758c29d7d760e3f3363a5d"
)
EXPECTED_HOST_REVIEW_MANIFEST = (
    "f927367ffb658139cfe02e0309a9030930478508df0100abc4b7e52abce108fc"
)
EXPECTED_PRO_200_CANDIDATE_MANIFEST = (
    "101f711fb58f55983d5ba97231d75a8185a325a3dea8b917d7de3d3a0e359695"
)
EXPECTED_PASS_NAMES = (
    "Harness files",
    "Harness and project source boundary",
    "Project layout and naming conventions",
    "JSON contracts",
    "PowerShell syntax",
    "Shell syntax",
    "Python compile",
    "Experiment registry structure",
    "Paper-v2 source-audit evidence",
    "Paper-v2 frozen study assets",
    "Historical evidence and current V2 freeze",
)
EXPECTED_FAIL_NAMES = (
    "Unit and integration tests",
    "Paper-v2 experiment closeout prospective evidence",
)
FAILED_TEST = (
    "tests/unit/test_paper_v2_experiment_closeout_harness_gate_v6.py::"
    "test_gate_reproduces_completed_prefix_and_pro_200_candidate"
)
FAILED_REPLAY_COMMAND = (
    "F:\\robot\\Anaconda3\\python.exe -m "
    "experiments.paper_v2.experiment_closeout_harness_gate_v6 --verify-gate"
)
PYTEST_SUMMARY = re.compile(
    r"(?P<failed>\d+) failed, (?P<passed>\d+) passed, "
    r"(?P<skipped>\d+) skipped, (?P<warnings>\d+) warnings in "
    r"(?P<duration>[^\r\n]+)"
)
SECRET_PATTERNS = (
    re.compile(rb"(?i)\bBearer\s+[A-Za-z0-9._~+/-]{12,}"),
    re.compile(rb"\bsk-[A-Za-z0-9_-]{12,}"),
    re.compile(rb"\bAQ\.[A-Za-z0-9._-]{12,}"),
)


class ExperimentCloseoutFreshHarnessFailureReviewV10Error(ValueError):
    """当不可变的 Fresh Harness v10 论据发生漂移时抛出的异常。"""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError as exc:
        raise ExperimentCloseoutFreshHarnessFailureReviewV10Error(
            f"review evidence escapes project root: {path}"
        ) from exc


def _lock(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ExperimentCloseoutFreshHarnessFailureReviewV10Error(
            f"missing Fresh Harness v10 evidence: {path}"
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
        raise ExperimentCloseoutFreshHarnessFailureReviewV10Error(
            f"{path}: invalid JSON"
        ) from exc
    if not isinstance(value, dict):
        raise ExperimentCloseoutFreshHarnessFailureReviewV10Error(
            f"{path}: expected object"
        )
    return value


def _count_bytes(raw: bytes, marker: str) -> int:
    return raw.count(marker.encode("utf-8")) + raw.count(marker.encode("utf-16-le"))


def analyze_transcript(stdout_bytes: bytes, stderr_bytes: bytes) -> dict[str, Any]:
    stdout = stdout_bytes.decode("utf-8", errors="replace")
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
        raise ExperimentCloseoutFreshHarnessFailureReviewV10Error(
            "Fresh Harness v10 pytest summary is missing or ambiguous"
        )
    summary = summaries[0].groupdict()
    secret_hits = sum(
        len(pattern.findall(stdout_bytes)) + len(pattern.findall(stderr_bytes))
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
        "pytest_failed": int(summary["failed"]),
        "pytest_passed": int(summary["passed"]),
        "pytest_skipped": int(summary["skipped"]),
        "pytest_warnings": int(summary["warnings"]),
        "pytest_duration": summary["duration"],
        "failed_test_count": stdout.count(f"FAILED {FAILED_TEST}"),
        "failed_replay_command_count": stdout.count(
            f"Command failed with exit code 1: {FAILED_REPLAY_COMMAND}"
        ),
        "prospective_drift_marker_count": _count_bytes(
            stdout_bytes, "prospective Adaptive Pro-200 path drift"
        )
        + _count_bytes(stderr_bytes, "prospective Adaptive Pro-200 path drift"),
        "python_traceback_count": _count_bytes(
            stdout_bytes, "Traceback (most recent call last)"
        )
        + _count_bytes(stderr_bytes, "Traceback (most recent call last)"),
        "runtime_auditor_blocks_stdout": _count_bytes(
            stdout_bytes, "[RuntimeAuditor] Blocked tool call:"
        ),
        "runtime_auditor_blocks_stderr": _count_bytes(
            stderr_bytes, "[RuntimeAuditor] Blocked tool call:"
        ),
        "secret_pattern_hits": secret_hits,
    }
    if (
        pass_names != list(EXPECTED_PASS_NAMES)
        or fail_names != list(EXPECTED_FAIL_NAMES)
        or observations["terminal_failure_marker_count"] != 1
        or not observations["terminal_failure_marker_is_last_nonempty_line"]
        or observations["pytest_failed"] != 1
        or observations["pytest_passed"] != 1627
        or observations["pytest_skipped"] != 1
        or observations["pytest_warnings"] != 3
        or observations["pytest_duration"] != "5274.64s (1:27:54)"
        or observations["failed_test_count"] != 1
        or observations["failed_replay_command_count"] != 1
        or observations["prospective_drift_marker_count"] != 4
        or observations["python_traceback_count"] != 1
        or observations["runtime_auditor_blocks_stdout"] != 60
        or observations["runtime_auditor_blocks_stderr"] != 363
        or observations["secret_pattern_hits"] != 0
    ):
        raise ExperimentCloseoutFreshHarnessFailureReviewV10Error(
            "Fresh Harness v10 failure transcript signature drift"
        )
    return observations


def _validate_receipt_chain(
    receipt: Mapping[str, Any],
    running: Mapping[str, Any],
    launch: Mapping[str, Any],
) -> None:
    checks = receipt.get("checks")
    if (
        receipt.get("schema_version") != "m3-harness-detached-receipt-3.0"
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
        or checks.get("process_scoped_git_qualification_passed") is not True
        or checks.get("global_git_config_mutated_false") is not True
        or checks.get("repository_git_config_mutated_false") is not True
        or checks.get("exactly_one_aggregate_marker") is not True
        or checks.get("exactly_one_zero_marker") is not False
        or checks.get("aggregate_marker_is_terminal") is not False
        or checks.get("no_failed_harness_stage") is not False
        or checks.get("network_or_provider_call_authorized_false") is not True
        or receipt.get("verify_script_sha256_before") != EXPECTED_VERIFY_SHA256
        or receipt.get("verify_script_sha256_after") != EXPECTED_VERIFY_SHA256
        or receipt.get("helper_script_sha256_before") != EXPECTED_HELPER_SHA256
        or receipt.get("helper_script_sha256_after") != EXPECTED_HELPER_SHA256
        or receipt.get("running_sha256") != EXPECTED_RUNNING_SHA256
        or receipt.get("stdout_sha256") != EXPECTED_STDOUT_SHA256
        or receipt.get("stderr_sha256") != EXPECTED_STDERR_SHA256
        or receipt.get("running_sha256") != _sha256_file(RUNNING_PATH)
        or receipt.get("stdout_sha256") != _sha256_file(STDOUT_PATH)
        or receipt.get("stderr_sha256") != _sha256_file(STDERR_PATH)
        or receipt.get("stdout_bytes") != STDOUT_PATH.stat().st_size
        or receipt.get("stderr_bytes") != STDERR_PATH.stat().st_size
        or receipt.get("aggregate_marker_count") != 1
        or receipt.get("zero_marker_count") != 0
        or receipt.get("failed_harness_stage_count") != 2
        or running.get("schema_version") != "m3-harness-detached-running-3.0"
        or running.get("status") != "running"
        or running.get("verify_script_sha256") != EXPECTED_VERIFY_SHA256
        or running.get("helper_script_sha256") != EXPECTED_HELPER_SHA256
        or running.get("network_or_provider_call_authorized") is not False
        or running.get("automatic_restart") is not False
        or launch.get("schema_version") != "m3-harness-detached-launch-3.0"
        or launch.get("status") != "launched_detached"
        or launch.get("automatic_restart") is not False
        or launch.get("network_or_provider_call_authorized") is not False
        or launch.get("verify_script_sha256") != EXPECTED_VERIFY_SHA256
        or launch.get("helper_script_sha256") != EXPECTED_HELPER_SHA256
        or launch.get("launcher_script_sha256") != EXPECTED_LAUNCHER_SHA256
        or _sha256_file(HELPER_PATH) != EXPECTED_HELPER_SHA256
        or _sha256_file(LAUNCHER_PATH) != EXPECTED_LAUNCHER_SHA256
    ):
        raise ExperimentCloseoutFreshHarnessFailureReviewV10Error(
            "Fresh Harness v10 receipt or immutable source lock drift"
        )


def _validate_state_transition() -> dict[str, Any]:
    gate = _read_json(GATE_V6_ARTIFACT_PATH)
    gate_core = {key: value for key, value in gate.items() if key != "manifest_sha256"}
    candidate = _read_json(PRO_200_CANDIDATE_PATH)
    candidate_core = {
        key: value for key, value in candidate.items() if key != "manifest_sha256"
    }
    gate_source = GATE_V6_SOURCE_PATH.read_text(encoding="utf-8")
    scope = candidate.get("scope")
    if not isinstance(scope, Mapping):
        raise ExperimentCloseoutFreshHarnessFailureReviewV10Error(
            "Pro-200 candidate scope is missing"
        )
    output_root = PROJECT_ROOT / str(scope.get("output_root"))
    if (
        gate.get("schema_version") != "m3-paper-v2-experiment-closeout-harness-gate-6.0"
        or gate.get("status") != "fresh_v8_and_completed_prefix_prerequisites_satisfied"
        or gate.get("manifest_sha256") != EXPECTED_GATE_V6_MANIFEST
        or sha256_canonical_json(gate_core) != EXPECTED_GATE_V6_MANIFEST
        or candidate.get("manifest_sha256") != EXPECTED_PRO_200_CANDIDATE_MANIFEST
        or sha256_canonical_json(candidate_core) != EXPECTED_PRO_200_CANDIDATE_MANIFEST
        or scope.get("stage") != "pro_200"
        or scope.get("target_budget") != 200
        or scope.get("authorized_task_count") != 39
        or not output_root.is_dir()
        or "or output_root.exists()" not in gate_source
        or '"prospective Adaptive Pro-200 path drift"' not in gate_source
    ):
        raise ExperimentCloseoutFreshHarnessFailureReviewV10Error(
            "Fresh Harness v10 prospective-to-completed transition drift"
        )
    return {
        "frozen_gate_manifest_sha256": gate["manifest_sha256"],
        "pro_200_candidate_manifest_sha256": candidate["manifest_sha256"],
        "pro_200_output_root": _display_path(output_root),
        "pro_200_output_root_now_exists": True,
        "gate_source_requires_output_root_absent": True,
    }


def build_review() -> dict[str, Any]:
    receipt = _read_json(RECEIPT_PATH)
    running = _read_json(RUNNING_PATH)
    launch = _read_json(LAUNCH_PATH)
    observations = analyze_transcript(
        STDOUT_PATH.read_bytes(), STDERR_PATH.read_bytes()
    )
    _validate_receipt_chain(receipt, running, launch)
    transition = _validate_state_transition()
    host = host_review.verify_review()
    if (
        host.get("manifest_sha256") != EXPECTED_HOST_REVIEW_MANIFEST
        or host.get("status")
        != "host_timeout_frozen_technical_gate_verified_wrapper_exit_unproven"
    ):
        raise ExperimentCloseoutFreshHarnessFailureReviewV10Error(
            "Pro-200 host-timeout closure drift"
        )

    core = {
        "schema_version": SCHEMA_VERSION,
        "artifact_role": "immutable_review_of_direct_exit_one_fresh_harness_v10",
        "reviewed_at": REVIEWED_AT,
        "status": "failed_harness_state_transition_frozen_no_provider_execution",
        "source_locks": [
            _lock(LAUNCH_PATH),
            _lock(RUNNING_PATH),
            _lock(STDOUT_PATH),
            _lock(STDERR_PATH),
            _lock(RECEIPT_PATH),
            _lock(HELPER_PATH),
            _lock(LAUNCHER_PATH),
            _lock(GATE_V6_SOURCE_PATH),
            _lock(GATE_V6_ARTIFACT_PATH),
            _lock(PRO_200_CANDIDATE_PATH),
            _lock(host_review.REVIEW_PATH),
            _lock(Path(host_review.__file__)),
            _lock(Path(__file__)),
            _lock(TEST_PATH),
        ],
        "observations": observations,
        "state_transition": transition,
        "root_cause": {
            "classification": (
                "expired_prospective_gate_replayed_after_authorized_pro200_completion"
            ),
            "failed_unit_test": FAILED_TEST,
            "failed_replay_command": FAILED_REPLAY_COMMAND,
            "pro_200_host_review_manifest_sha256": host["manifest_sha256"],
            "provider_failure": False,
            "scientific_result_failure": False,
            "historical_gate_corruption": False,
        },
        "remediation_boundary": {
            "preserve_frozen_gate_v6_artifact": True,
            "preserve_completed_pro_200_output": True,
            "replace_dynamic_prospective_replay_with_immutable_completion_review": True,
            "fresh_full_harness_run_required": True,
            "automatic_retry_or_restart": False,
            "modify_experimental_conditions": False,
        },
        "evidence_boundary": {
            "credentials_read_by_review": False,
            "provider_calls_made_by_review": 0,
            "provider_calls_made_by_failed_harness": 0,
            "network_calls_made_by_review": 0,
            "scientific_outcomes_accessed": False,
            "blind_labels_accessed": False,
            "historical_files_mutated": False,
            "provider_execution_authorized": False,
            "pro_500_execution_authorized": False,
            "result_access_authorized": False,
        },
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def write_review() -> dict[str, Any]:
    if REVIEW_PATH.exists():
        raise ExperimentCloseoutFreshHarnessFailureReviewV10Error(
            "Fresh Harness v10 failure review already exists; overwrite is forbidden"
        )
    value = build_review()
    REVIEW_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = REVIEW_PATH.with_suffix(".json.tmp")
    temporary.write_bytes(canonical_json_bytes(value) + b"\n")
    temporary.replace(REVIEW_PATH)
    return value


def validate_review(value: Mapping[str, Any]) -> dict[str, Any]:
    expected = build_review()
    if dict(value) != expected:
        raise ExperimentCloseoutFreshHarnessFailureReviewV10Error(
            "Fresh Harness v10 failure review artifact drift"
        )
    return dict(value)


def verify_review() -> dict[str, Any]:
    if not REVIEW_PATH.is_file():
        raise ExperimentCloseoutFreshHarnessFailureReviewV10Error(
            "Fresh Harness v10 failure review artifact missing"
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
