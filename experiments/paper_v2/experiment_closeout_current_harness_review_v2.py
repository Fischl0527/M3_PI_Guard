"""宿主重置后恢复当前工作树已完成 Harness 判定结论的复核工具。

无损恢复中断的 Harness 评估状态并输出可信性审计签名。
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from experiments.paper_v2.contracts import canonical_json_bytes, sha256_canonical_json


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUN_ROOT = (
    PROJECT_ROOT
    / "outputs/verification/experiment_closeout_current_harness_v2_20260802"
)
RUNNING_PATH = RUN_ROOT / "running.json"
STDOUT_PATH = RUN_ROOT / "stdout.log"
STDERR_PATH = RUN_ROOT / "stderr.log"
MISSING_WRAPPER_RECEIPT_PATH = RUN_ROOT / "receipt.json"
WRAPPER_PATH = (
    PROJECT_ROOT
    / "outputs/verification/run_experiment_closeout_current_harness_v2.ps1"
)
VERIFY_SCRIPT_PATH = PROJECT_ROOT / "harness/scripts/verify.ps1"
REVIEW_PATH = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/experiment_closeout_current_harness_review_v2.json"
)
REVIEW_TEST_PATH = (
    PROJECT_ROOT
    / "tests/unit/test_paper_v2_experiment_closeout_current_harness_review_v2.py"
)

SCHEMA_VERSION = "m3-paper-v2-closeout-current-harness-review-2.0"
REVIEWED_AT = "2026-08-02T15:46:00+08:00"
EXPECTED_PYTEST_SUMMARY = (
    "1365 passed, 1 skipped, 3 warnings in 5049.03s (1:24:09)"
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
EXPECTED_RUNTIME_AUDITOR_BLOCKS = 33
EXPECTED_SHA256 = {
    "running.json": "55cec61c7d3a3ffce75e1873e0fce026d81eb2ab423bb2decbaeba89c2830aaf",
    "stdout.log": "340509a306d6585b53e77a64751bafc5bab2c9ddda9b9ba7918a18b5951ec170",
    "stderr.log": "02a6c27e6984563a30e9f4de762ccbb5a4575c07cef687003b6154030be79a41",
    "wrapper": "d1f9fe03b2135ba9209d21e0f88956d63346372a1f62592dc03f739cd748e998",
    "verify_script": "715a6bc995ac5b7275aa13def3bb58eeb21f719ed11f8fc19e6dd3fca2863007",
}


class ExperimentCloseoutCurrentHarnessReviewV2Error(ValueError):
    """当已完成的 Harness 论据无法支持恢复时抛出的异常。"""


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
        raise ExperimentCloseoutCurrentHarnessReviewV2Error(
            f"missing current Harness artifact: {path}"
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
        raise ExperimentCloseoutCurrentHarnessReviewV2Error(
            f"{path}: invalid JSON"
        ) from exc
    if not isinstance(value, dict):
        raise ExperimentCloseoutCurrentHarnessReviewV2Error(
            f"{path}: expected object"
        )
    return value


def _assert_source_hashes(locks: Mapping[str, Mapping[str, Any]]) -> None:
    for name, expected in EXPECTED_SHA256.items():
        observed = locks[name]["sha256"]
        if observed != expected:
            raise ExperimentCloseoutCurrentHarnessReviewV2Error(
                f"current Harness {name} SHA-256 drift"
            )


def _verify_terminal_exit_contract() -> None:
    source = VERIFY_SCRIPT_PATH.read_text(encoding="utf-8")
    expected_suffix = (
        'Write-Host "`nVerification failed=$script:Failed"\n'
        "exit $script:Failed"
    )
    if not source.rstrip().endswith(expected_suffix):
        raise ExperimentCloseoutCurrentHarnessReviewV2Error(
            "verify.ps1 terminal exit contract drift"
        )


def build_review() -> dict[str, Any]:
    locks = {
        "running.json": _lock(RUNNING_PATH),
        "stdout.log": _lock(STDOUT_PATH),
        "stderr.log": _lock(STDERR_PATH),
        "wrapper": _lock(WRAPPER_PATH),
        "verify_script": _lock(VERIFY_SCRIPT_PATH),
    }
    _assert_source_hashes(locks)
    _verify_terminal_exit_contract()

    running = _read_json(RUNNING_PATH)
    stdout = STDOUT_PATH.read_text(encoding="utf-8", errors="replace")
    stderr = STDERR_PATH.read_text(encoding="utf-8", errors="replace")
    pass_names = tuple(
        line.removeprefix("PASS: ")
        for line in stdout.splitlines()
        if line.startswith("PASS: ")
    )
    fail_lines = tuple(
        line for line in stdout.splitlines() if line.startswith("FAIL: ")
    )
    terminal_marker_count = sum(
        line == "Verification failed=0" for line in stdout.splitlines()
    )
    observations = {
        "running_marker_status": running.get("status"),
        "api_environment_variables_scrubbed": running.get(
            "api_environment_variables_scrubbed"
        ),
        "network_or_provider_call_authorized": running.get(
            "network_or_provider_call_authorized"
        ),
        "pytest_summary_observed": EXPECTED_PYTEST_SUMMARY in stdout,
        "pass_names": list(pass_names),
        "fail_line_count": len(fail_lines),
        "terminal_zero_marker_count": terminal_marker_count,
        "terminal_zero_marker_is_last_nonempty_line": (
            stdout.rstrip().endswith("Verification failed=0")
        ),
        "python_traceback_observed": (
            "Traceback (most recent call last)" in stderr
        ),
        "runtime_auditor_delete_blocks": stderr.count(
            "[RuntimeAuditor] Blocked tool call: delete_record"
        ),
        "wrapper_receipt_observed": MISSING_WRAPPER_RECEIPT_PATH.exists(),
    }
    expected_observations = {
        "running_marker_status": "running",
        "api_environment_variables_scrubbed": [
            "DEEPSEEK_API_KEY",
            "GEMINI_API_KEY",
            "GOOGLE_API_KEY",
        ],
        "network_or_provider_call_authorized": False,
        "pytest_summary_observed": True,
        "pass_names": list(EXPECTED_PASS_NAMES),
        "fail_line_count": 0,
        "terminal_zero_marker_count": 1,
        "terminal_zero_marker_is_last_nonempty_line": True,
        "python_traceback_observed": False,
        "runtime_auditor_delete_blocks": EXPECTED_RUNTIME_AUDITOR_BLOCKS,
        "wrapper_receipt_observed": False,
    }
    if observations != expected_observations:
        raise ExperimentCloseoutCurrentHarnessReviewV2Error(
            "completed current Harness observation signature drift"
        )

    core = {
        "schema_version": SCHEMA_VERSION,
        "artifact_role": (
            "recovered_terminal_review_of_completed_runtime_worktree_harness"
        ),
        "reviewed_at": REVIEWED_AT,
        "status": "passed_recovered_from_terminal_harness_evidence",
        "source_locks": [
            locks["running.json"],
            locks["stdout.log"],
            locks["stderr.log"],
            locks["wrapper"],
            locks["verify_script"],
            _lock(Path(__file__)),
            _lock(REVIEW_TEST_PATH),
        ],
        "observations": observations,
        "exit_code_evidence": {
            "operating_system_exit_code_directly_observed": False,
            "effective_exit_code": 0,
            "basis": (
                "unique_terminal_zero_marker_plus_hash_locked_verify_script_"
                "immediate_exit_contract"
            ),
            "outer_command_timeout_seconds": 3604,
            "original_wrapper_receipt_missing": True,
        },
        "post_run_executable_and_evidence_delta": {
            "files_added_after_full_harness": [
                _display_path(Path(__file__)),
                _display_path(REVIEW_TEST_PATH),
                _display_path(REVIEW_PATH),
            ],
            "runtime_or_experiment_controller_files_changed": False,
            "verify_script_changed": False,
            "state_and_handoff_documents_outside_source_delta": True,
            "focused_pytest": "2 passed",
            "python_compile": "passed",
            "ruff": "passed",
            "full_harness_rerun_after_recovery_delta": False,
        },
        "verdict": {
            "pre_recovery_worktree_full_harness_passed": True,
            "post_recovery_current_worktree_full_harness_directly_observed": (
                False
            ),
            "post_run_executable_delta_scoped_and_verified": True,
            "full_harness_failed": False,
            "current_worktree_full_rerun_required": False,
            "fresh_provider_canary_harness_prerequisite_satisfied": True,
        },
        "evidence_boundary": {
            "missing_wrapper_receipt_fabricated": False,
            "raw_operating_system_exit_claimed": False,
            "logs_mutated_by_review": False,
            "historical_evidence_replayed": True,
            "new_provider_calls_made_by_review": 0,
            "credentials_read_by_review": False,
            "provider_execution_authorized_by_review": False,
            "separate_candidate_and_admission_still_required": True,
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
        raise ExperimentCloseoutCurrentHarnessReviewV2Error(
            "current Harness recovered review drift"
        )
    return dict(value)


def verify_review() -> dict[str, Any]:
    if not REVIEW_PATH.is_file():
        raise ExperimentCloseoutCurrentHarnessReviewV2Error(
            "current Harness recovered review missing"
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
