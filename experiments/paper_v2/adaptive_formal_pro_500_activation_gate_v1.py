"""Activate the Pro-500 wrapper only after a new complete Harness run.

The source for this gate, the guarded runner, and both detached launchers is
present before Fresh Harness v11.  After that Harness finishes with a directly
observed exit zero, this module can freeze one non-result activation artifact.
The artifact never replaces the separate project-owner stage admission.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

from experiments.paper_v2 import adaptive_formal_pro_controller_v2 as controller
from experiments.paper_v2 import experiment_closeout_harness_gate_v7 as gate_v7
from experiments.paper_v2 import (
    experiment_closeout_fresh_harness_failure_review_v10 as failure_review_v10,
)
from experiments.paper_v2.contracts import canonical_json_bytes


PROJECT_ROOT = Path(__file__).resolve().parents[2]
HARNESS_ROOT = (
    PROJECT_ROOT / "outputs/verification/experiment_closeout_fresh_harness_v12_20260819"
)
HARNESS_LAUNCH_PATH = HARNESS_ROOT / "launch.json"
HARNESS_RUNNING_PATH = HARNESS_ROOT / "running.json"
HARNESS_STDOUT_PATH = HARNESS_ROOT / "stdout.log"
HARNESS_STDERR_PATH = HARNESS_ROOT / "stderr.log"
HARNESS_RECEIPT_PATH = HARNESS_ROOT / "receipt.json"
VERIFY_SCRIPT_PATH = PROJECT_ROOT / "harness/scripts/verify.ps1"
HARNESS_HELPER_PATH = PROJECT_ROOT / "harness/scripts/verify_with_receipt_v3.ps1"
HARNESS_LAUNCHER_PATH = (
    PROJECT_ROOT
    / "outputs/verification/start_experiment_closeout_fresh_harness_v12.ps1"
)
GUARDED_RUNNER_PATH = (
    PROJECT_ROOT / "experiments/paper_v2/adaptive_formal_pro_500_guarded_runner_v1.py"
)
GUARDED_RUNNER_TEST_PATH = (
    PROJECT_ROOT
    / "tests/unit/test_paper_v2_adaptive_formal_pro_500_guarded_runner_v1.py"
)
GUARDED_LAUNCHER_PATH = (
    PROJECT_ROOT / "outputs/verification/start_adaptive_formal_pro_500_guarded_v1.ps1"
)
HARNESS_LAUNCHER_TEST_PATH = (
    PROJECT_ROOT / "tests/unit/test_paper_v2_fresh_harness_v12_launcher.py"
)
PREINTEGRATION_GATE_PATH = gate_v7.GATE_PATH
PRO_500_CANDIDATE_PATH = controller.candidate_path("pro_500")
PRO_500_ADMISSION_PATH = controller.admission_path("pro_500")
GATE_PATH = (
    PROJECT_ROOT
    / "outputs/verification/adaptive_formal_pro_500_activation_gate_v1_20260807.json"
)
TEST_PATH = (
    PROJECT_ROOT
    / "tests/unit/test_paper_v2_adaptive_formal_pro_500_activation_gate_v1.py"
)

SCHEMA_VERSION = "m3-paper-v2-adaptive-formal-pro-500-activation-gate-1.0"
EXPECTED_PASS_NAMES = gate_v7.EXPECTED_PASS_NAMES
REQUIRED_VERIFY_SOURCE_MARKERS = (
    "experiment_closeout_harness_gate_v7",
    "experiment_closeout_fresh_harness_failure_review_v10",
    "adaptive_formal_pro_500_activation_gate_v1.py",
    "adaptive_formal_pro_500_guarded_runner_v1.py",
    "start_adaptive_formal_pro_500_guarded_v1.ps1",
    "start_experiment_closeout_fresh_harness_v12.ps1",
)
SECRET_PATTERNS = (
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]{12,}"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"\bAQ\.[A-Za-z0-9._-]{12,}"),
)


class AdaptiveFormalPro500ActivationGateV1Error(ValueError):
    """Raised when the post-integration activation evidence fails closed."""


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
        raise AdaptiveFormalPro500ActivationGateV1Error(
            f"activation evidence escapes project root: {path}"
        ) from exc


def _lock(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise AdaptiveFormalPro500ActivationGateV1Error(
            f"missing Pro-500 activation evidence: {path}"
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
        raise AdaptiveFormalPro500ActivationGateV1Error(
            f"{path}: invalid JSON"
        ) from exc
    if not isinstance(value, dict):
        raise AdaptiveFormalPro500ActivationGateV1Error(f"{path}: expected object")
    return value


def validate_receipt_contract(
    *,
    launch: Mapping[str, Any],
    running: Mapping[str, Any],
    receipt: Mapping[str, Any],
    verify_sha256: str,
    helper_sha256: str,
    launcher_sha256: str,
    running_sha256: str,
    stdout_sha256: str,
    stderr_sha256: str,
) -> None:
    checks = receipt.get("checks")
    if (
        not isinstance(checks, Mapping)
        or not checks
        or any(value is not True for value in checks.values())
        or launch.get("schema_version") != "m3-harness-detached-launch-3.0"
        or launch.get("status") != "launched_detached"
        or launch.get("verify_script_sha256") != verify_sha256
        or launch.get("helper_script_sha256") != helper_sha256
        or launch.get("launcher_script_sha256") != launcher_sha256
        or launch.get("network_or_provider_call_authorized") is not False
        or launch.get("automatic_restart") is not False
        or running.get("schema_version") != "m3-harness-detached-running-3.0"
        or running.get("verify_script_sha256") != verify_sha256
        or running.get("helper_script_sha256") != helper_sha256
        or running.get("network_or_provider_call_authorized") is not False
        or running.get("automatic_restart") is not False
        or receipt.get("schema_version") != "m3-harness-detached-receipt-3.0"
        or receipt.get("status") != "completed_exit_zero_evidence_pass"
        or receipt.get("operating_system_exit_code_directly_observed") is not True
        or receipt.get("child_exit_code") != 0
        or receipt.get("exit_code") != 0
        or receipt.get("evidence_gate_passed") is not True
        or receipt.get("verify_script_sha256_before") != verify_sha256
        or receipt.get("verify_script_sha256_after") != verify_sha256
        or receipt.get("helper_script_sha256_before") != helper_sha256
        or receipt.get("helper_script_sha256_after") != helper_sha256
        or receipt.get("running_sha256") != running_sha256
        or receipt.get("stdout_sha256") != stdout_sha256
        or receipt.get("stderr_sha256") != stderr_sha256
        or receipt.get("aggregate_marker_count") != 1
        or receipt.get("zero_marker_count") != 1
        or receipt.get("failed_harness_stage_count") != 0
        or receipt.get("network_or_provider_call_authorized") is not False
        or receipt.get("automatic_restart") is not False
    ):
        raise AdaptiveFormalPro500ActivationGateV1Error(
            "Fresh Harness v12 receipt contract drift"
        )


def validate_harness_logs(stdout: str, stderr: str) -> dict[str, Any]:
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
    match = re.search(
        r"(?P<passed>\d+) passed, (?P<skipped>\d+) skipped, "
        r"(?P<warnings>\d+) warnings in (?P<seconds>[\d.]+)s",
        stdout,
    )
    secret_hits = sum(
        len(pattern.findall(stdout)) + len(pattern.findall(stderr))
        for pattern in SECRET_PATTERNS
    )
    if (
        pass_names != EXPECTED_PASS_NAMES
        or fail_lines
        or terminal_zero_count != 1
        or not stdout.rstrip().endswith("Verification failed=0")
        or match is None
        or int(match.group("skipped")) != 1
        or int(match.group("warnings")) != 3
        or "Traceback (most recent call last)" in stderr
        or secret_hits != 0
    ):
        raise AdaptiveFormalPro500ActivationGateV1Error(
            "Fresh Harness v12 terminal log contract drift"
        )
    return {
        "pass_names": list(pass_names),
        "failed_stage_count": 0,
        "terminal_zero_marker_count": 1,
        "pytest_passed": int(match.group("passed")),
        "pytest_skipped": int(match.group("skipped")),
        "pytest_warnings": int(match.group("warnings")),
        "pytest_seconds": float(match.group("seconds")),
        "secret_pattern_hit_count": 0,
    }


def _validate_verify_source() -> str:
    source = VERIFY_SCRIPT_PATH.read_text(encoding="utf-8")
    if any(marker not in source for marker in REQUIRED_VERIFY_SOURCE_MARKERS):
        raise AdaptiveFormalPro500ActivationGateV1Error(
            "Fresh Harness v12 verify source marker drift"
        )
    return _sha256_file(VERIFY_SCRIPT_PATH)


def build_gate() -> dict[str, Any]:
    preintegration = gate_v7.verify_gate()
    v10_failure = failure_review_v10.verify_review()
    candidate = controller.verify_stage_candidate("pro_500")
    admission = controller.validate_stage_admission(
        _read_json(PRO_500_ADMISSION_PATH),
        stage="pro_500",
    )
    launch = _read_json(HARNESS_LAUNCH_PATH)
    running = _read_json(HARNESS_RUNNING_PATH)
    receipt = _read_json(HARNESS_RECEIPT_PATH)
    stdout = HARNESS_STDOUT_PATH.read_text(encoding="utf-8", errors="replace")
    stderr = HARNESS_STDERR_PATH.read_text(encoding="utf-8", errors="replace")
    verify_sha256 = _validate_verify_source()
    helper_sha256 = _sha256_file(HARNESS_HELPER_PATH)
    launcher_sha256 = _sha256_file(HARNESS_LAUNCHER_PATH)
    validate_receipt_contract(
        launch=launch,
        running=running,
        receipt=receipt,
        verify_sha256=verify_sha256,
        helper_sha256=helper_sha256,
        launcher_sha256=launcher_sha256,
        running_sha256=_sha256_file(HARNESS_RUNNING_PATH),
        stdout_sha256=_sha256_file(HARNESS_STDOUT_PATH),
        stderr_sha256=_sha256_file(HARNESS_STDERR_PATH),
    )
    log_status = validate_harness_logs(stdout, stderr)
    if (
        preintegration.get("verdict", {}).get("post_integration_full_harness_required")
        is not True
        or preintegration.get("verdict", {}).get(
            "provider_execution_authorized_by_gate"
        )
        is not False
        or candidate.get("manifest_sha256")
        != gate_v7.EXPECTED_PRO_500_CANDIDATE_MANIFEST
        or admission.get("manifest_sha256")
        != gate_v7.EXPECTED_PRO_500_ADMISSION_MANIFEST
        or v10_failure.get("root_cause", {}).get("classification")
        != "expired_prospective_gate_replayed_after_authorized_pro200_completion"
        or v10_failure.get("evidence_boundary", {}).get("pro_500_execution_authorized")
        is not False
    ):
        raise AdaptiveFormalPro500ActivationGateV1Error(
            "Pro-500 pre-integration identity drift"
        )
    core = {
        "schema_version": SCHEMA_VERSION,
        "artifact_role": "post_fresh_harness_pro_500_wrapper_activation_gate",
        "status": "fresh_harness_passed_exact_pro_500_wrapper_eligible",
        "source_locks": [
            _lock(HARNESS_LAUNCH_PATH),
            _lock(HARNESS_RUNNING_PATH),
            _lock(HARNESS_STDOUT_PATH),
            _lock(HARNESS_STDERR_PATH),
            _lock(HARNESS_RECEIPT_PATH),
            _lock(VERIFY_SCRIPT_PATH),
            _lock(HARNESS_HELPER_PATH),
            _lock(HARNESS_LAUNCHER_PATH),
            _lock(failure_review_v10.REVIEW_PATH),
            _lock(Path(failure_review_v10.__file__)),
            _lock(failure_review_v10.TEST_PATH),
            _lock(PREINTEGRATION_GATE_PATH),
            _lock(Path(gate_v7.__file__)),
            _lock(PRO_500_CANDIDATE_PATH),
            _lock(PRO_500_ADMISSION_PATH),
            _lock(GUARDED_RUNNER_PATH),
            _lock(GUARDED_RUNNER_TEST_PATH),
            _lock(GUARDED_LAUNCHER_PATH),
            _lock(HARNESS_LAUNCHER_TEST_PATH),
            _lock(Path(__file__)),
            _lock(TEST_PATH),
        ],
        "fresh_harness_v12": {
            **log_status,
            "receipt_sha256": _sha256_file(HARNESS_RECEIPT_PATH),
            "verify_script_sha256": verify_sha256,
            "operating_system_exit_code_directly_observed": True,
            "exit_code": 0,
            "evidence_gate_passed": True,
            "network_or_provider_call_authorized": False,
        },
        "fresh_harness_v10_failure_transition": {
            "review_manifest_sha256": v10_failure["manifest_sha256"],
            "classification": v10_failure["root_cause"]["classification"],
            "provider_failure": False,
            "scientific_result_failure": False,
        },
        "pro_500_identity": {
            "preintegration_gate_manifest_sha256": preintegration["manifest_sha256"],
            "candidate_manifest_sha256": candidate["manifest_sha256"],
            "admission_manifest_sha256": admission["manifest_sha256"],
            "run_id": candidate["scope"]["run_id"],
            "execution_identity": candidate["scope"]["execution_identity"],
            "authorized_tasks": 36,
            "target_budget": 500,
            "stage_hard_limit_cny": 35.0,
        },
        "evidence_boundary": {
            "credentials_read": False,
            "provider_calls_made": 0,
            "network_calls_made": 0,
            "scientific_outcomes_accessed": False,
            "blind_labels_accessed": False,
            "provider_tools_enabled": False,
            "external_effects_enabled": False,
            "automatic_retries": 0,
            "result_access_authorized": False,
        },
        "verdict": {
            "current_integrated_source_full_harness_passed": True,
            "exact_pro_500_guarded_runner_eligible": True,
            "separate_owner_admission_still_required": True,
            "provider_execution_authorized_by_gate_alone": False,
            "result_access_authorized_by_gate": False,
            "single_use_untouched_output_required": True,
        },
    }
    return {**core, "manifest_sha256": _canonical_sha256(core)}


def write_gate() -> dict[str, Any]:
    if GATE_PATH.exists():
        raise AdaptiveFormalPro500ActivationGateV1Error(
            "Pro-500 activation gate already exists; overwrite is forbidden"
        )
    value = build_gate()
    temporary = GATE_PATH.with_suffix(".json.tmp")
    temporary.write_bytes(canonical_json_bytes(value) + b"\n")
    temporary.replace(GATE_PATH)
    return value


def validate_gate(value: Mapping[str, Any]) -> dict[str, Any]:
    expected = build_gate()
    if dict(value) != expected:
        raise AdaptiveFormalPro500ActivationGateV1Error(
            "Pro-500 activation gate artifact drift"
        )
    return dict(value)


def verify_gate() -> dict[str, Any]:
    if not GATE_PATH.is_file():
        raise AdaptiveFormalPro500ActivationGateV1Error(
            "Pro-500 activation gate is missing"
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
