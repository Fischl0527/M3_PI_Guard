"""在允许模型调用前绑定直接观察到的第 2 日全量 Harness 退出码门禁。

前置阻断未通过测试时的后续昂贵实验调用。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from experiments.paper_v2.contracts import canonical_json_bytes, sha256_canonical_json


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUN_ROOT = (
    PROJECT_ROOT
    / "outputs/verification/experiment_closeout_day2_harness_v1_20260802"
)
RUNNING_PATH = RUN_ROOT / "running.json"
STDOUT_PATH = RUN_ROOT / "stdout.log"
STDERR_PATH = RUN_ROOT / "stderr.log"
RECEIPT_PATH = RUN_ROOT / "receipt.json"
LAUNCH_PATH = RUN_ROOT / "launch.json"
HELPER_PATH = PROJECT_ROOT / "harness/scripts/verify_with_receipt_v1.ps1"
LAUNCHER_PATH = (
    PROJECT_ROOT
    / "outputs/verification/start_experiment_closeout_day2_harness_v1.ps1"
)
VERIFY_SCRIPT_PATH = PROJECT_ROOT / "harness/scripts/verify.ps1"
TEST_PATH = (
    PROJECT_ROOT
    / "tests/unit/test_paper_v2_experiment_closeout_day2_harness_gate_v1.py"
)
GATE_PATH = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/experiment_closeout_day2_harness_gate_v1.json"
)

SCHEMA_VERSION = "m3-paper-v2-experiment-closeout-day2-harness-gate-1.0"
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


class ExperimentCloseoutDay2HarnessGateV1Error(ValueError):
    """当 Day-2 Harness 论据不完整或发生漂移时抛出的异常。"""


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
        raise ExperimentCloseoutDay2HarnessGateV1Error(
            f"missing Day-2 Harness artifact: {path}"
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
        raise ExperimentCloseoutDay2HarnessGateV1Error(
            f"{path}: invalid JSON"
        ) from exc
    if not isinstance(value, dict):
        raise ExperimentCloseoutDay2HarnessGateV1Error(
            f"{path}: expected object"
        )
    return value


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
        raise ExperimentCloseoutDay2HarnessGateV1Error(
            "Day-2 Harness pytest summary is missing or ambiguous"
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
    }
    if (
        pass_names != list(EXPECTED_PASS_NAMES)
        or observations["fail_line_count"] != 0
        or terminal_count != 1
        or not observations["terminal_zero_marker_is_last_nonempty_line"]
        or observations["pytest_passed"] < 1365
        or observations["pytest_skipped"] != 1
        or observations["python_traceback_observed"]
    ):
        raise ExperimentCloseoutDay2HarnessGateV1Error(
            "Day-2 Harness terminal evidence did not pass"
        )
    return observations


def build_gate() -> dict[str, Any]:
    receipt = _read_json(RECEIPT_PATH)
    running = _read_json(RUNNING_PATH)
    launch = _read_json(LAUNCH_PATH)
    stdout = STDOUT_PATH.read_text(encoding="utf-8", errors="replace")
    stderr = STDERR_PATH.read_text(encoding="utf-8", errors="replace")
    observations = analyze_transcript(stdout, stderr)
    if (
        receipt.get("schema_version") != "m3-harness-detached-receipt-1.0"
        or receipt.get("status") != "completed_exit_zero"
        or receipt.get("operating_system_exit_code_directly_observed") is not True
        or receipt.get("exit_code") != 0
        or receipt.get("network_or_provider_call_authorized") is not False
        or running.get("status") != "running"
        or running.get("network_or_provider_call_authorized") is not False
        or launch.get("status") != "launched_detached"
        or launch.get("automatic_restart") is not False
        or launch.get("network_or_provider_call_authorized") is not False
        or receipt.get("stdout_sha256") != _sha256_file(STDOUT_PATH)
        or receipt.get("stderr_sha256") != _sha256_file(STDERR_PATH)
        or receipt.get("running_sha256") != _sha256_file(RUNNING_PATH)
        or receipt.get("verify_script_sha256") != _sha256_file(VERIFY_SCRIPT_PATH)
        or receipt.get("helper_script_sha256") != _sha256_file(HELPER_PATH)
        or launch.get("helper_script_sha256") != _sha256_file(HELPER_PATH)
        or launch.get("launcher_script_sha256") != _sha256_file(LAUNCHER_PATH)
    ):
        raise ExperimentCloseoutDay2HarnessGateV1Error(
            "Day-2 Harness receipt or source lock drift"
        )
    core = {
        "schema_version": SCHEMA_VERSION,
        "artifact_role": "direct_os_exit_full_harness_provider_canary_gate",
        "status": "full_harness_exit_zero_provider_canary_prerequisite_satisfied",
        "source_locks": [
            _lock(LAUNCH_PATH),
            _lock(RUNNING_PATH),
            _lock(STDOUT_PATH),
            _lock(STDERR_PATH),
            _lock(RECEIPT_PATH),
            _lock(HELPER_PATH),
            _lock(LAUNCHER_PATH),
            _lock(VERIFY_SCRIPT_PATH),
            _lock(Path(__file__)),
            _lock(TEST_PATH),
        ],
        "observations": observations,
        "verdict": {
            "operating_system_exit_code_directly_observed": True,
            "full_harness_passed": True,
            "provider_canary_harness_prerequisite_satisfied": True,
            "provider_execution_authorized_by_gate": False,
            "separate_candidate_admission_and_budget_or_quota_required": True,
        },
        "evidence_boundary": {
            "credentials_read": False,
            "provider_calls_made": 0,
            "scientific_outcomes_accessed": False,
            "logs_mutated": False,
            "automatic_restart": False,
        },
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def write_gate() -> dict[str, Any]:
    value = build_gate()
    GATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    GATE_PATH.write_bytes(canonical_json_bytes(value) + b"\n")
    return value


def verify_gate() -> dict[str, Any]:
    observed = _read_json(GATE_PATH)
    expected = build_gate()
    if observed != expected:
        raise ExperimentCloseoutDay2HarnessGateV1Error(
            "Day-2 Harness gate artifact drift"
        )
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
