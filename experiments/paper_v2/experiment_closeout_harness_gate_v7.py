"""构建非授权性 Pro-500 集成前置 Harness 门禁。

在不提前触发大模型计费请求的前提下，完成所有本地测试集与数据契约审查。
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from experiments.paper_v2 import adaptive_formal_pro_controller_v2 as controller
from experiments.paper_v2 import (
    adaptive_formal_pro_200_host_timeout_review_v1 as host_timeout_review,
)
from experiments.paper_v2.contracts import canonical_json_bytes


PROJECT_ROOT = Path(__file__).resolve().parents[2]
HARNESS_ROOT = (
    PROJECT_ROOT
    / "outputs/verification/experiment_closeout_fresh_harness_v9_20260807"
)
HARNESS_LAUNCH_PATH = HARNESS_ROOT / "launch.json"
HARNESS_RUNNING_PATH = HARNESS_ROOT / "running.json"
HARNESS_STDOUT_PATH = HARNESS_ROOT / "stdout.log"
HARNESS_STDERR_PATH = HARNESS_ROOT / "stderr.log"
HARNESS_RECEIPT_PATH = HARNESS_ROOT / "receipt.json"
HARNESS_HELPER_PATH = PROJECT_ROOT / "harness/scripts/verify_with_receipt_v3.ps1"
HARNESS_LAUNCHER_PATH = (
    PROJECT_ROOT
    / "outputs/verification/start_experiment_closeout_fresh_harness_v9.ps1"
)
HOST_TIMEOUT_REVIEW_PATH = host_timeout_review.REVIEW_PATH
PRO_200_TECHNICAL_REVIEW_PATH = host_timeout_review.TECHNICAL_REVIEW_PATH
PRO_500_CANDIDATE_PATH = controller.candidate_path("pro_500")
PRO_500_ADMISSION_PATH = controller.admission_path("pro_500")
GATE_PATH = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/experiment_closeout_harness_gate_v7.json"
)
TEST_PATH = (
    PROJECT_ROOT
    / "tests/unit/test_paper_v2_experiment_closeout_harness_gate_v7.py"
)

SCHEMA_VERSION = "m3-paper-v2-experiment-closeout-harness-gate-7.0"
CREATED_AT = "2026-08-07T13:30:00+08:00"
EXPECTED_HARNESS_RECEIPT_SHA256 = (
    "14ef9b5ae618839798051a31ce4a4abc270f53f46e393e678e0f43b29f6f0e44"
)
EXPECTED_HARNESS_VERIFY_SHA256 = (
    "bbe29590775fbae2a43b442562a3bf094a1072c049a17cbca29f2ae678248d37"
)
EXPECTED_HOST_TIMEOUT_REVIEW_MANIFEST = (
    "f927367ffb658139cfe02e0309a9030930478508df0100abc4b7e52abce108fc"
)
EXPECTED_PRO_200_REVIEW_MANIFEST = (
    "1910ac58f6403850f9aa5ead1cca3c592dcc7cb9feee9486ef050e214a6ee349"
)
EXPECTED_PRO_500_CANDIDATE_MANIFEST = (
    "947cd58dbda621218f96f6520991a5c49b76d35eaff268002a12329c05b53214"
)
EXPECTED_PRO_500_ADMISSION_MANIFEST = (
    "ae60c0a8d21c7243b4ec7daf026f40b02b37a840dd84a5cca06229509efdd7d6"
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
EXPECTED_PYTEST_SUMMARY = "1584 passed, 1 skipped, 3 warnings in 5034.23s"
EXPECTED_RUNTIME_AUDITOR_BLOCKS = 363


class ExperimentCloseoutHarnessGateV7Error(ValueError):
    """当 Pro-500 集成前门禁无法复现时抛出的异常。"""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError as exc:
        raise ExperimentCloseoutHarnessGateV7Error(
            f"gate evidence escapes project root: {path}"
        ) from exc


def _lock(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ExperimentCloseoutHarnessGateV7Error(
            f"missing Pro-500 pre-integration evidence: {path}"
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
        raise ExperimentCloseoutHarnessGateV7Error(
            f"{path}: invalid JSON"
        ) from exc
    if not isinstance(value, dict):
        raise ExperimentCloseoutHarnessGateV7Error(
            f"{path}: expected object"
        )
    return value


def _validate_embedded_manifest(
    value: Mapping[str, Any], *, label: str
) -> str:
    observed = value.get("manifest_sha256")
    core = {key: child for key, child in value.items() if key != "manifest_sha256"}
    recomputed = _canonical_sha256(core)
    if not isinstance(observed, str) or observed != recomputed:
        raise ExperimentCloseoutHarnessGateV7Error(
            f"{label}: embedded manifest drift"
        )
    return observed


def _validate_harness_v9() -> dict[str, Any]:
    launch = _read_json(HARNESS_LAUNCH_PATH)
    running = _read_json(HARNESS_RUNNING_PATH)
    receipt = _read_json(HARNESS_RECEIPT_PATH)
    stdout = HARNESS_STDOUT_PATH.read_text(encoding="utf-8", errors="replace")
    stderr = HARNESS_STDERR_PATH.read_text(encoding="utf-8", errors="replace")
    pass_names = tuple(
        line.removeprefix("PASS: ")
        for line in stdout.splitlines()
        if line.startswith("PASS: ")
    )
    fail_lines = tuple(
        line for line in stdout.splitlines() if line.startswith("FAIL: ")
    )
    terminal_zero_count = sum(
        line == "Verification failed=0" for line in stdout.splitlines()
    )
    receipt_sha256 = _sha256_file(HARNESS_RECEIPT_PATH)
    stdout_sha256 = _sha256_file(HARNESS_STDOUT_PATH)
    stderr_sha256 = _sha256_file(HARNESS_STDERR_PATH)
    running_sha256 = _sha256_file(HARNESS_RUNNING_PATH)
    if (
        receipt_sha256 != EXPECTED_HARNESS_RECEIPT_SHA256
        or launch.get("schema_version") != "m3-harness-detached-launch-3.0"
        or launch.get("status") != "launched_detached"
        or launch.get("verify_script_sha256") != EXPECTED_HARNESS_VERIFY_SHA256
        or launch.get("network_or_provider_call_authorized") is not False
        or launch.get("automatic_restart") is not False
        or running.get("schema_version") != "m3-harness-detached-running-3.0"
        or running.get("verify_script_sha256") != EXPECTED_HARNESS_VERIFY_SHA256
        or running.get("network_or_provider_call_authorized") is not False
        or running.get("automatic_restart") is not False
        or receipt.get("schema_version") != "m3-harness-detached-receipt-3.0"
        or receipt.get("status") != "completed_exit_zero_evidence_pass"
        or receipt.get("operating_system_exit_code_directly_observed") is not True
        or receipt.get("child_exit_code") != 0
        or receipt.get("exit_code") != 0
        or receipt.get("evidence_gate_passed") is not True
        or receipt.get("verify_script_sha256_before")
        != EXPECTED_HARNESS_VERIFY_SHA256
        or receipt.get("verify_script_sha256_after")
        != EXPECTED_HARNESS_VERIFY_SHA256
        or receipt.get("running_sha256") != running_sha256
        or receipt.get("stdout_sha256") != stdout_sha256
        or receipt.get("stderr_sha256") != stderr_sha256
        or receipt.get("aggregate_marker_count") != 1
        or receipt.get("zero_marker_count") != 1
        or receipt.get("failed_harness_stage_count") != 0
        or receipt.get("network_or_provider_call_authorized") is not False
        or receipt.get("automatic_restart") is not False
        or pass_names != EXPECTED_PASS_NAMES
        or fail_lines
        or terminal_zero_count != 1
        or not stdout.rstrip().endswith("Verification failed=0")
        or EXPECTED_PYTEST_SUMMARY not in stdout
        or "Traceback (most recent call last)" in stderr
        or stderr.count("[RuntimeAuditor] Blocked tool call: delete_record")
        != EXPECTED_RUNTIME_AUDITOR_BLOCKS
    ):
        raise ExperimentCloseoutHarnessGateV7Error(
            "Fresh Harness v9 evidence drift"
        )
    return {
        "direct_os_exit_observed": True,
        "exit_code": 0,
        "evidence_gate_passed": True,
        "pass_names": list(pass_names),
        "failed_stage_count": 0,
        "pytest_passed": 1584,
        "pytest_skipped": 1,
        "pytest_warnings": 3,
        "runtime_auditor_delete_blocks": EXPECTED_RUNTIME_AUDITOR_BLOCKS,
        "historical_verify_script_sha256": EXPECTED_HARNESS_VERIFY_SHA256,
        "current_source_changed_after_v9": True,
        "post_integration_full_harness_required": True,
    }


def _validate_pro_200_closeout() -> dict[str, Any]:
    review = host_timeout_review.verify_review()
    technical = _read_json(PRO_200_TECHNICAL_REVIEW_PATH)
    if (
        review.get("manifest_sha256") != EXPECTED_HOST_TIMEOUT_REVIEW_MANIFEST
        or review.get("claim_boundary", {}).get(
            "original_wrapper_direct_exit_proven"
        )
        is not False
        or review.get("claim_boundary", {}).get(
            "execute_child_direct_exit_proven"
        )
        is not False
        or review.get("claim_boundary", {}).get(
            "technical_review_child_direct_exit_zero_proven"
        )
        is not True
        or review.get("evidence_boundary", {}).get("result_access_authorized")
        is not False
        or technical.get("manifest_sha256")
        != EXPECTED_PRO_200_REVIEW_MANIFEST
        or technical.get("status")
        != "adaptive_formal_stage_technical_gate_pass"
        or technical.get("technical_gate_passed") is not True
        or technical.get("result_admission_authorized") is not False
        or technical.get("terminal_task_count") != 39
        or technical.get("completed_provider_call_count") != 6925
        or technical.get("terminal_query_count_this_stage") != 5504
        or technical.get("stage_cost_cny") != 8.0544754
    ):
        raise ExperimentCloseoutHarnessGateV7Error(
            "Pro-200 host-timeout closeout drift"
        )
    return {
        "host_timeout_review_manifest_sha256": review["manifest_sha256"],
        "technical_review_manifest_sha256": technical["manifest_sha256"],
        "terminal_tasks": 39,
        "completed_provider_calls": 6925,
        "incremental_terminal_queries": 5504,
        "stage_cost_cny": 8.0544754,
        "original_wrapper_direct_exit_proven": False,
        "execute_child_direct_exit_proven": False,
        "technical_review_child_direct_exit_zero_proven": True,
        "result_admission_authorized": False,
    }


def _validate_pro_500() -> dict[str, Any]:
    candidate = controller.verify_stage_candidate("pro_500")
    admission = controller.validate_stage_admission(
        _read_json(PRO_500_ADMISSION_PATH),
        stage="pro_500",
    )
    scope = candidate.get("scope", {})
    controls = candidate.get("execution_controls", {})
    authorization = admission.get("authorization", {})
    locks = candidate.get("source_checkpoint_locks", [])
    if (
        candidate.get("manifest_sha256")
        != EXPECTED_PRO_500_CANDIDATE_MANIFEST
        or admission.get("manifest_sha256")
        != EXPECTED_PRO_500_ADMISSION_MANIFEST
        or scope.get("stage") != "pro_500"
        or scope.get("target_budget") != 500
        or scope.get("authorized_task_count") != 36
        or scope.get("source_checkpoint_count") != 36
        or len(scope.get("authorized_case_ids", [])) != 36
        or len(scope.get("cumulative_diagnostic_case_ids", [])) != 4
        or scope.get("stage_hard_limit_cny") != 35.0
        or any(lock.get("query_count") != 200 for lock in locks)
        or controls.get("automatic_retries") != 0
        or controls.get("provider_tools_enabled") is not False
        or controls.get("external_effects_enabled") is not False
        or authorization.get("stage_execution_authorized") is not True
        or authorization.get("terminal_query_replay_authorized") is not False
        or authorization.get("automatic_retries") != 0
        or authorization.get("provider_tools_enabled") is not False
        or authorization.get("external_effects_enabled") is not False
        or authorization.get("result_admission_authorized") is not False
    ):
        raise ExperimentCloseoutHarnessGateV7Error(
            "Pro-500 candidate/admission drift"
        )
    return {
        "candidate_manifest_sha256": candidate["manifest_sha256"],
        "admission_manifest_sha256": admission["manifest_sha256"],
        "execution_identity": scope["execution_identity"],
        "authorized_tasks": 36,
        "retained_cumulative_diagnostics": 4,
        "source_checkpoint_budget": 200,
        "target_budget": 500,
        "stage_hard_limit_cny": 35.0,
        "automatic_retries": 0,
        "provider_tools_enabled": False,
        "external_effects_enabled": False,
        "result_admission_authorized": False,
    }


def build_gate() -> dict[str, Any]:
    harness = _validate_harness_v9()
    pro_200 = _validate_pro_200_closeout()
    pro_500 = _validate_pro_500()
    core = {
        "schema_version": SCHEMA_VERSION,
        "artifact_role": "pro_500_preintegration_non_authorizing_harness_gate",
        "created_at": CREATED_AT,
        "status": "pro_500_prerequisites_satisfied_fresh_harness_required",
        "source_locks": [
            _lock(HARNESS_LAUNCH_PATH),
            _lock(HARNESS_RUNNING_PATH),
            _lock(HARNESS_STDOUT_PATH),
            _lock(HARNESS_STDERR_PATH),
            _lock(HARNESS_RECEIPT_PATH),
            _lock(HARNESS_HELPER_PATH),
            _lock(HARNESS_LAUNCHER_PATH),
            _lock(HOST_TIMEOUT_REVIEW_PATH),
            _lock(PRO_200_TECHNICAL_REVIEW_PATH),
            _lock(PRO_500_CANDIDATE_PATH),
            _lock(PRO_500_ADMISSION_PATH),
            _lock(Path(__file__)),
            _lock(TEST_PATH),
        ],
        "fresh_harness_v9": harness,
        "pro_200_closeout": pro_200,
        "pro_500": pro_500,
        "evidence_boundary": {
            "credentials_read": False,
            "provider_calls_made": 0,
            "network_calls_made": 0,
            "scientific_outcomes_accessed": False,
            "blind_labels_accessed": False,
            "historical_evidence_modified": False,
            "provider_tools_enabled": False,
            "external_effects_enabled": False,
            "automatic_retries": 0,
            "result_access_authorized": False,
        },
        "verdict": {
            "fresh_harness_v9_passed": True,
            "pro_200_technical_closeout_passed": True,
            "pro_500_candidate_and_admission_reproduced": True,
            "provider_execution_authorized_by_gate": False,
            "result_access_authorized_by_gate": False,
            "post_integration_full_harness_required": True,
            "detached_single_use_wrapper_required": True,
        },
    }
    return {**core, "manifest_sha256": _canonical_sha256(core)}


def write_gate() -> dict[str, Any]:
    value = build_gate()
    GATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    GATE_PATH.write_bytes(canonical_json_bytes(value) + b"\n")
    return value


def validate_gate(value: Mapping[str, Any]) -> dict[str, Any]:
    expected = build_gate()
    if dict(value) != expected:
        raise ExperimentCloseoutHarnessGateV7Error(
            "Pro-500 pre-integration gate artifact drift"
        )
    return dict(value)


def verify_gate() -> dict[str, Any]:
    if not GATE_PATH.is_file():
        raise ExperimentCloseoutHarnessGateV7Error(
            "Pro-500 pre-integration gate is missing"
        )
    return validate_gate(_read_json(GATE_PATH))


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
