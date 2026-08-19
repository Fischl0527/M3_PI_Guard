"""Bind Fresh Harness v8 and completed prefix evidence for Pro-200.

This gate is deliberately non-authorizing.  It verifies the immutable Fresh
Harness v8 receipt, the completed Adaptive Pro-50 and Gemini Public-v5 s1
technical chains, and the exact prospective Pro-200 candidate/admission.  A
provider call still requires the separate single-use wrapper and a later full
Harness that includes this gate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

from experiments.paper_v2 import adaptive_formal_pro_controller_v2 as adaptive
from experiments.paper_v2 import experiment_closeout_harness_gate_v5 as prior_gate
from experiments.paper_v2 import gemini_public_controller_v5 as gemini
from experiments.paper_v2.contracts import canonical_json_bytes, sha256_canonical_json


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUN_ROOT = (
    PROJECT_ROOT
    / "outputs/verification/experiment_closeout_fresh_harness_v8_20260806"
)
RUNNING_PATH = RUN_ROOT / "running.json"
STDOUT_PATH = RUN_ROOT / "stdout.log"
STDERR_PATH = RUN_ROOT / "stderr.log"
RECEIPT_PATH = RUN_ROOT / "receipt.json"
LAUNCH_PATH = RUN_ROOT / "launch.json"
HELPER_PATH = PROJECT_ROOT / "harness/scripts/verify_with_receipt_v3.ps1"
LAUNCHER_PATH = (
    PROJECT_ROOT
    / "outputs/verification/start_experiment_closeout_fresh_harness_v8.ps1"
)
PRIOR_GATE_PATH = prior_gate.GATE_PATH
GEMINI_WRAPPER_GATE_PATH = prior_gate.PRIOR_GATE_PATH

PRO_50_STAGE = "pro_50"
PRO_50_CANDIDATE_PATH = adaptive.candidate_path(PRO_50_STAGE)
PRO_50_ADMISSION_PATH = adaptive.admission_path(PRO_50_STAGE)
PRO_50_WRAPPER_PATH = (
    PROJECT_ROOT
    / "outputs/verification/run_adaptive_formal_pro_v2_guarded_v3.ps1"
)
PRO_50_WRAPPER_RECEIPT_PATH = (
    PROJECT_ROOT
    / "outputs/verification/adaptive_formal_pro_50_v2_guarded_v3_20260806"
    / "receipt.json"
)

GEMINI_SEGMENT_INDEX = 1
GEMINI_QUOTA_DAY = "2026-08-06"
GEMINI_ADMISSION_PATH = gemini.admission_path(
    GEMINI_SEGMENT_INDEX, GEMINI_QUOTA_DAY
)
GEMINI_REVIEW_PATH = (
    PROJECT_ROOT
    / "outputs/paper_upgrade_v2/formal_public/gemini"
    / "public-v5-canary-recovery-s1-"
    "b28e6af8206cc66283d10ce73b220c839f9ad1d48393a40de33c6d4be31384b4"
    / "technical_segment_review_v6.json"
)
GEMINI_WRAPPER_PATH = (
    PROJECT_ROOT
    / "outputs/verification/run_gemini_public_v5_recovery_segment_guarded_v2.ps1"
)
GEMINI_WRAPPER_RECEIPT_PATH = (
    PROJECT_ROOT
    / "outputs/verification/gemini_public_v5_recovery_s1_2026-08-06_guarded_v2"
    / "receipt.json"
)
GEMINI_QUOTA_LEDGER_PATH = (
    PROJECT_ROOT / "outputs/paper_upgrade_v2/gemini_project_quota_days_v1.jsonl"
)

PRO_200_STAGE = "pro_200"
PRO_200_CANDIDATE_PATH = adaptive.candidate_path(PRO_200_STAGE)
PRO_200_ADMISSION_PATH = adaptive.admission_path(PRO_200_STAGE)
PRO_200_WRAPPER_PATH = (
    PROJECT_ROOT
    / "outputs/verification/run_adaptive_formal_pro_v2_guarded_v4.ps1"
)
TEST_PATH = (
    PROJECT_ROOT / "tests/unit/test_paper_v2_experiment_closeout_harness_gate_v6.py"
)
WRAPPER_TEST_PATH = (
    PROJECT_ROOT / "tests/unit/test_paper_v2_adaptive_formal_pro_v2_wrapper_v4.py"
)
GATE_PATH = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/experiment_closeout_harness_gate_v6.json"
)

SCHEMA_VERSION = "m3-paper-v2-experiment-closeout-harness-gate-6.0"
EXPECTED_PYTEST_PASSED = 1568
EXPECTED_PYTEST_SKIPPED = 1
EXPECTED_PYTEST_WARNINGS = 3
EXPECTED_RUNTIME_AUDITOR_DELETE_BLOCKS = 303
EXPECTED_AGENTDOJO_COMMIT = "089ed468cf3ed0322acc66b0211f26d9d90dbf60"
EXPECTED_PRIOR_GATE_MANIFEST_SHA256 = (
    "ff76b53991b5b0f8f2ccdfc88aa246c9be6d7e12786bdf8c3c0d4d1b3c10e58e"
)
PYTEST_SUMMARY = re.compile(
    r"(?P<passed>\d+) passed, (?P<skipped>\d+) skipped, "
    r"(?P<warnings>\d+) warnings in (?P<duration>[^\r\n]+)"
)


class ExperimentCloseoutHarnessGateV6Error(ValueError):
    """Raised when v8 or a completed/prospective prefix artifact drifts."""


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
        raise ExperimentCloseoutHarnessGateV6Error(f"missing gate input: {path}")
    return {
        "path": _display_path(path),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ExperimentCloseoutHarnessGateV6Error(
            f"{path}: invalid JSON"
        ) from exc
    if not isinstance(value, dict):
        raise ExperimentCloseoutHarnessGateV6Error(f"{path}: expected object")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        values = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ExperimentCloseoutHarnessGateV6Error(
            f"{path}: invalid JSONL"
        ) from exc
    if any(not isinstance(value, dict) for value in values):
        raise ExperimentCloseoutHarnessGateV6Error(f"{path}: expected objects")
    return values


def _manifest_matches(value: Mapping[str, Any]) -> bool:
    core = {key: child for key, child in value.items() if key != "manifest_sha256"}
    return value.get("manifest_sha256") == sha256_canonical_json(core)


def _validate_prior_gate_snapshot() -> dict[str, Any]:
    value = _read_json(PRIOR_GATE_PATH)
    locks = value.get("source_locks")
    if (
        not _manifest_matches(value)
        or value.get("manifest_sha256") != EXPECTED_PRIOR_GATE_MANIFEST_SHA256
        or value.get("status")
        != "fresh_v7_full_harness_execution_prerequisite_satisfied"
        or value.get("verdict", {}).get("provider_execution_authorized_by_gate")
        is not False
        or value.get("verdict", {}).get("result_access_authorized_by_gate")
        is not False
        or not isinstance(locks, list)
        or not locks
    ):
        raise ExperimentCloseoutHarnessGateV6Error("v5 predecessor gate drift")
    for lock in locks:
        if not isinstance(lock, Mapping):
            raise ExperimentCloseoutHarnessGateV6Error(
                "v5 predecessor source lock drift"
            )
        path = PROJECT_ROOT / str(lock.get("path", ""))
        if (
            not path.is_file()
            or lock.get("bytes") != path.stat().st_size
            or lock.get("sha256") != _sha256_file(path)
        ):
            raise ExperimentCloseoutHarnessGateV6Error(
                "v5 predecessor source lock drift"
            )
    return value


def _secret_pattern_hit_count(*texts: str) -> int:
    return sum(
        len(pattern.findall(text))
        for pattern in prior_gate.SECRET_PATTERNS
        for text in texts
    )


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
        raise ExperimentCloseoutHarnessGateV6Error(
            "v8 Harness pytest summary is missing or ambiguous"
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
        pass_names != list(prior_gate.EXPECTED_PASS_NAMES)
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
        raise ExperimentCloseoutHarnessGateV6Error(
            "v8 Harness terminal evidence did not pass"
        )
    return observations


def _validate_v8_receipt(
    receipt: Mapping[str, Any],
    running: Mapping[str, Any],
    launch: Mapping[str, Any],
) -> None:
    checks = receipt.get("checks")
    verify_sha = receipt.get("verify_script_sha256_before")
    helper_sha = receipt.get("helper_script_sha256_before")
    if (
        receipt.get("schema_version") != "m3-harness-detached-receipt-3.0"
        or receipt.get("status") != "completed_exit_zero_evidence_pass"
        or receipt.get("operating_system_exit_code_directly_observed") is not True
        or receipt.get("child_exit_code") != 0
        or receipt.get("exit_code") != 0
        or receipt.get("evidence_gate_passed") is not True
        or not isinstance(checks, Mapping)
        or tuple(checks) != prior_gate.EXPECTED_RECEIPT_CHECKS
        or any(checks[name] is not True for name in prior_gate.EXPECTED_RECEIPT_CHECKS)
        or receipt.get("aggregate_marker_count") != 1
        or receipt.get("zero_marker_count") != 1
        or receipt.get("failed_harness_stage_count") != 0
        or receipt.get("network_or_provider_call_authorized") is not False
        or receipt.get("automatic_restart") is not False
        or receipt.get("api_environment_variables_scrubbed")
        != list(prior_gate.EXPECTED_API_ENVIRONMENT_VARIABLES)
        or running.get("schema_version") != "m3-harness-detached-running-3.0"
        or running.get("status") != "running"
        or running.get("network_or_provider_call_authorized") is not False
        or running.get("automatic_restart") is not False
        or launch.get("schema_version") != "m3-harness-detached-launch-3.0"
        or launch.get("status") != "launched_detached"
        or launch.get("network_or_provider_call_authorized") is not False
        or launch.get("automatic_restart") is not False
        or receipt.get("stdout_sha256") != _sha256_file(STDOUT_PATH)
        or receipt.get("stderr_sha256") != _sha256_file(STDERR_PATH)
        or receipt.get("running_sha256") != _sha256_file(RUNNING_PATH)
        or verify_sha != receipt.get("verify_script_sha256_after")
        or verify_sha != running.get("verify_script_sha256")
        or verify_sha != launch.get("verify_script_sha256")
        or helper_sha != receipt.get("helper_script_sha256_after")
        or helper_sha != running.get("helper_script_sha256")
        or helper_sha != launch.get("helper_script_sha256")
        or helper_sha != _sha256_file(HELPER_PATH)
        or launch.get("launcher_script_sha256") != _sha256_file(LAUNCHER_PATH)
        or receipt.get("expected_agentdojo_commit") != EXPECTED_AGENTDOJO_COMMIT
        or receipt.get("observed_agentdojo_commit") != EXPECTED_AGENTDOJO_COMMIT
        or receipt.get("git_safe_directory_scope") != "process_only"
        or receipt.get("global_git_config_mutated") is not False
        or receipt.get("repository_git_config_mutated") is not False
    ):
        raise ExperimentCloseoutHarnessGateV6Error(
            "v8 Harness receipt or source chain drift"
        )


def _resolve_logged_path(value: Any) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else PROJECT_ROOT / path


def _validate_wrapper_steps(
    receipt: Mapping[str, Any], step_names: tuple[str, ...]
) -> None:
    steps = receipt.get("steps")
    if not isinstance(steps, Mapping):
        raise ExperimentCloseoutHarnessGateV6Error("wrapper steps missing")
    logged_texts: list[str] = []
    for name in step_names:
        step = steps.get(name)
        if not isinstance(step, Mapping) or step.get("exit_code") != 0:
            raise ExperimentCloseoutHarnessGateV6Error("wrapper step drift")
        for stream in ("stdout", "stderr"):
            path = _resolve_logged_path(step.get(f"{stream}_path"))
            if (
                not path.is_file()
                or step.get(f"{stream}_sha256") != _sha256_file(path)
            ):
                raise ExperimentCloseoutHarnessGateV6Error(
                    "wrapper log chain drift"
                )
            logged_texts.append(path.read_text(encoding="utf-8", errors="replace"))
    if (
        steps.get("secret_scan", {}).get("status") != "pass"
        or steps.get("secret_scan", {}).get("secret_pattern_hit_count") != 0
        or _secret_pattern_hit_count(*logged_texts) != 0
    ):
        raise ExperimentCloseoutHarnessGateV6Error("wrapper secret scan drift")


def _validate_pro_50_completion() -> tuple[dict[str, Any], dict[str, Any]]:
    candidate = adaptive.verify_stage_candidate(PRO_50_STAGE)
    admission = adaptive.validate_stage_admission(
        _read_json(PRO_50_ADMISSION_PATH), stage=PRO_50_STAGE
    )
    review_path = adaptive.review_path(PRO_50_STAGE)
    review = _read_json(review_path)
    receipt = _read_json(PRO_50_WRAPPER_RECEIPT_PATH)
    _validate_wrapper_steps(
        receipt,
        (
            "01_harness_gate",
            "02_order_gate",
            "03_candidate",
            "04_admission",
            "05_execute",
            "06_technical_review",
        ),
    )
    checks = review.get("checks")
    if (
        candidate.get("scope", {}).get("authorized_task_count") != 32
        or admission.get("candidate_manifest_sha256")
        != candidate.get("manifest_sha256")
        or not _manifest_matches(review)
        or review.get("status") != "adaptive_formal_stage_technical_gate_pass"
        or review.get("technical_gate_passed") is not True
        or review.get("result_admission_authorized") is not False
        or review.get("stage") != PRO_50_STAGE
        or review.get("authorized_task_count") != 32
        or review.get("terminal_task_count") != 32
        or review.get("completed_provider_call_count") != 1968
        or review.get("stage_cost_cny", 11.0) > 10.0
        or not isinstance(checks, Mapping)
        or not checks
        or any(value is not True for value in checks.values())
        or receipt.get("schema_version")
        != "m3-paper-v2-adaptive-formal-pro-process-receipt-3.0"
        or receipt.get("status") != "completed_technical_gate_pass"
        or receipt.get("final_exit_code") != 0
        or receipt.get("stage") != PRO_50_STAGE
        or receipt.get("authorized_task_count") != 32
        or receipt.get("automatic_retries") != 0
        or receipt.get("provider_tools_enabled") is not False
        or receipt.get("external_effects_enabled") is not False
        or receipt.get("scientific_outcomes_accessed_by_wrapper") is not False
        or receipt.get("wrapper_sha256") != _sha256_file(PRO_50_WRAPPER_PATH)
        or receipt.get("harness_gate_sha256") != _sha256_file(PRIOR_GATE_PATH)
        or receipt.get("candidate_sha256") != _sha256_file(PRO_50_CANDIDATE_PATH)
        or receipt.get("admission_sha256") != _sha256_file(PRO_50_ADMISSION_PATH)
        or receipt.get("technical_review", {}).get("review_sha256")
        != _sha256_file(review_path)
    ):
        raise ExperimentCloseoutHarnessGateV6Error(
            "completed Adaptive Pro-50 evidence drift"
        )
    return review, receipt


def _validate_gemini_s1_completion() -> tuple[dict[str, Any], dict[str, Any]]:
    candidate = gemini.verify_candidate()
    admission = gemini.validate_segment_admission(
        _read_json(GEMINI_ADMISSION_PATH),
        segment_index=GEMINI_SEGMENT_INDEX,
        quota_day=GEMINI_QUOTA_DAY,
    )
    review = _read_json(GEMINI_REVIEW_PATH)
    receipt = _read_json(GEMINI_WRAPPER_RECEIPT_PATH)
    _validate_wrapper_steps(
        receipt,
        ("01_harness_gate", "02_admission", "03_execute", "04_technical_review"),
    )
    checks = review.get("checks")
    quota_events = [
        event
        for event in _read_jsonl(GEMINI_QUOTA_LEDGER_PATH)
        if event.get("quota_day") == GEMINI_QUOTA_DAY
    ]
    if len(quota_events) != 1:
        raise ExperimentCloseoutHarnessGateV6Error("Gemini quota-day reuse drift")
    quota = quota_events[0]
    if (
        candidate.get("manifest_sha256")
        != review.get("candidate_manifest_sha256")
        or admission.get("manifest_sha256") is None
        or review.get("admission_file_sha256")
        != _sha256_file(GEMINI_ADMISSION_PATH)
        or not _manifest_matches(review)
        or review.get("status")
        != "gemini_public_v5_recovery_segment_gate_pass"
        or review.get("technical_gate_passed") is not True
        or review.get("matrix_continuation_eligible") is not True
        or review.get("scientific_outcomes_accessed") is not False
        or review.get("result_admission_authorized") is not False
        or review.get("expected_records") != 1
        or review.get("observed_records") != 1
        or review.get("provider_call_attempts") != 1
        or review.get("provider_transport_completions") != 1
        or review.get("runtime_runner_failures_retained_in_itt") != 1
        or not isinstance(checks, Mapping)
        or not checks
        or any(value is not True for value in checks.values())
        or receipt.get("status") != "completed_technical_gate_pass"
        or receipt.get("final_exit_code") != 0
        or receipt.get("provider_id") != "gemini"
        or receipt.get("model_id") != "gemini-3.6-flash"
        or receipt.get("quota_day") != GEMINI_QUOTA_DAY
        or receipt.get("expected_record_count") != 1
        or receipt.get("paid_ceiling_usd") != 0.0
        or receipt.get("automatic_retries") != 0
        or receipt.get("provider_tools_enabled") is not False
        or receipt.get("external_effects_enabled") is not False
        or receipt.get("scientific_outcomes_accessed_by_wrapper") is not False
        or receipt.get("wrapper_sha256") != _sha256_file(GEMINI_WRAPPER_PATH)
        or receipt.get("harness_gate_sha256")
        != _sha256_file(GEMINI_WRAPPER_GATE_PATH)
        or receipt.get("candidate_sha256") != _sha256_file(gemini.CANDIDATE_PATH)
        or receipt.get("admission_sha256") != _sha256_file(GEMINI_ADMISSION_PATH)
        or quota.get("event_type") != "formal_day_reserved"
        or quota.get("billing_tier") != "free"
        or quota.get("paid_ceiling_usd") != 0.0
        or quota.get("maximum_provider_requests") != 16
        or quota.get("reserved_provider_requests") != 2
        or quota.get("declared_other_project_requests") != 0
        or quota.get("automatic_retries") != 0
        or quota.get("provider_tools_enabled") is not False
        or quota.get("external_effects_enabled") is not False
        or quota.get("workload") != "public_canary_recovery_v5_segment_1"
        or quota.get("run_id") != admission.get("run_id")
        or quota.get("execution_identity") != admission.get("execution_identity")
        or quota.get("admission_file_sha256")
        != _sha256_file(GEMINI_ADMISSION_PATH)
    ):
        raise ExperimentCloseoutHarnessGateV6Error(
            "completed Gemini Public-v5 s1 evidence drift"
        )
    return review, receipt


def _validate_pro_200_path() -> tuple[dict[str, Any], dict[str, Any]]:
    candidate = adaptive.verify_stage_candidate(PRO_200_STAGE)
    admission = adaptive.validate_stage_admission(
        _read_json(PRO_200_ADMISSION_PATH), stage=PRO_200_STAGE
    )
    scope = candidate.get("scope", {})
    checkpoint_locks = candidate.get("source_checkpoint_locks")
    diagnostics = scope.get("cumulative_diagnostic_case_ids")
    output_root = PROJECT_ROOT / str(scope.get("output_root"))
    if (
        candidate.get("status") != "offline_qualified_execution_not_authorized"
        or scope.get("stage") != PRO_200_STAGE
        or scope.get("target_budget") != 200
        or scope.get("authorized_task_count") != 39
        or scope.get("source_checkpoint_count") != 39
        or scope.get("stage_hard_limit_cny") != 20.0
        or scope.get("projected_total_ceiling_cny") != 180.0
        or not isinstance(checkpoint_locks, list)
        or len(checkpoint_locks) != 39
        or any(lock.get("query_count") != 50 for lock in checkpoint_locks)
        or not isinstance(diagnostics, list)
        or len(diagnostics) != 1
        or candidate.get("authorization", {}).get("stage_execution_authorized")
        is not False
        or candidate.get("authorization", {}).get("result_admission_authorized")
        is not False
        or candidate.get("execution_controls", {}).get("automatic_retries") != 0
        or candidate.get("execution_controls", {}).get("provider_tools_enabled")
        is not False
        or candidate.get("execution_controls", {}).get("external_effects_enabled")
        is not False
        or candidate.get("evidence_boundary", {}).get("network_calls_made") != 0
        or candidate.get("evidence_boundary", {}).get("credentials_read") is not False
        or output_root.exists()
        or admission.get("status")
        != "activated_for_one_exact_order_bound_adaptive_stage"
        or admission.get("candidate_manifest_sha256")
        != candidate.get("manifest_sha256")
        or admission.get("run_id") != scope.get("run_id")
        or admission.get("execution_identity") != scope.get("execution_identity")
        or admission.get("authorization", {}).get("stage_execution_authorized")
        is not True
        or admission.get("authorization", {}).get("terminal_query_replay_authorized")
        is not False
        or admission.get("authorization", {}).get("result_admission_authorized")
        is not False
        or admission.get("authorization", {}).get("automatic_retries") != 0
        or admission.get("authorization", {}).get("provider_tools_enabled") is not False
        or admission.get("authorization", {}).get("external_effects_enabled") is not False
    ):
        raise ExperimentCloseoutHarnessGateV6Error(
            "prospective Adaptive Pro-200 path drift"
        )
    return candidate, admission


def build_gate() -> dict[str, Any]:
    with prior_gate._process_scoped_safe_directories():
        predecessor = _validate_prior_gate_snapshot()
        pro_50_review, pro_50_receipt = _validate_pro_50_completion()
        gemini_review, gemini_receipt = _validate_gemini_s1_completion()
        pro_200_candidate, pro_200_admission = _validate_pro_200_path()

    receipt = _read_json(RECEIPT_PATH)
    running = _read_json(RUNNING_PATH)
    launch = _read_json(LAUNCH_PATH)
    stdout = STDOUT_PATH.read_text(encoding="utf-8", errors="replace")
    stderr = STDERR_PATH.read_text(encoding="utf-8", errors="replace")
    observations = analyze_transcript(stdout, stderr)
    _validate_v8_receipt(receipt, running, launch)

    if (
        predecessor.get("status")
        != "fresh_v7_full_harness_execution_prerequisite_satisfied"
        or predecessor.get("verdict", {}).get("provider_execution_authorized_by_gate")
        is not False
    ):
        raise ExperimentCloseoutHarnessGateV6Error("v5 predecessor gate drift")

    core = {
        "schema_version": SCHEMA_VERSION,
        "artifact_role": "fresh_v8_completed_prefix_non_authorizing_closeout_gate",
        "status": "fresh_v8_and_completed_prefix_prerequisites_satisfied",
        "source_locks": [
            _lock(LAUNCH_PATH),
            _lock(RUNNING_PATH),
            _lock(STDOUT_PATH),
            _lock(STDERR_PATH),
            _lock(RECEIPT_PATH),
            _lock(HELPER_PATH),
            _lock(LAUNCHER_PATH),
            _lock(PRIOR_GATE_PATH),
            _lock(PRO_50_CANDIDATE_PATH),
            _lock(PRO_50_ADMISSION_PATH),
            _lock(adaptive.review_path(PRO_50_STAGE)),
            _lock(PRO_50_WRAPPER_PATH),
            _lock(PRO_50_WRAPPER_RECEIPT_PATH),
            _lock(gemini.CANDIDATE_PATH),
            _lock(GEMINI_ADMISSION_PATH),
            _lock(GEMINI_REVIEW_PATH),
            _lock(GEMINI_WRAPPER_PATH),
            _lock(GEMINI_WRAPPER_RECEIPT_PATH),
            _lock(GEMINI_WRAPPER_GATE_PATH),
            _lock(GEMINI_QUOTA_LEDGER_PATH),
            _lock(PRO_200_CANDIDATE_PATH),
            _lock(PRO_200_ADMISSION_PATH),
            _lock(PRO_200_WRAPPER_PATH),
            _lock(Path(__file__)),
            _lock(TEST_PATH),
            _lock(WRAPPER_TEST_PATH),
        ],
        "prerequisite_manifests": {
            "fresh_harness_v7_gate": predecessor["manifest_sha256"],
            "adaptive_pro_50_review": pro_50_review["manifest_sha256"],
            "gemini_public_v5_segment_1_review": gemini_review["manifest_sha256"],
            "adaptive_pro_200_candidate": pro_200_candidate["manifest_sha256"],
            "adaptive_pro_200_admission": pro_200_admission["manifest_sha256"],
        },
        "observations": observations,
        "technical_scope": {
            "fresh_harness_v8_receipt_sha256": _sha256_file(RECEIPT_PATH),
            "adaptive_pro_50_terminal_tasks": pro_50_review["terminal_task_count"],
            "adaptive_pro_50_cumulative_completed_provider_calls": pro_50_review[
                "completed_provider_call_count"
            ],
            "adaptive_pro_50_wrapper_exit_code": pro_50_receipt["final_exit_code"],
            "gemini_segment_1_records": gemini_review["observed_records"],
            "gemini_segment_1_provider_transports": gemini_review[
                "provider_transport_completions"
            ],
            "gemini_segment_1_runner_failures_retained_in_itt": gemini_review[
                "runtime_runner_failures_retained_in_itt"
            ],
            "gemini_segment_1_wrapper_exit_code": gemini_receipt["final_exit_code"],
            "adaptive_next_stage": PRO_200_STAGE,
            "adaptive_next_tasks": pro_200_candidate["scope"][
                "authorized_task_count"
            ],
            "adaptive_retained_prior_diagnostics": len(
                pro_200_candidate["scope"]["cumulative_diagnostic_case_ids"]
            ),
            "adaptive_next_target_budget": pro_200_candidate["scope"][
                "target_budget"
            ],
            "adaptive_next_execution_identity": pro_200_candidate["scope"][
                "execution_identity"
            ],
        },
        "verdict": {
            "operating_system_exit_code_directly_observed": True,
            "full_harness_v8_passed": True,
            "completed_prefix_evidence_passed": True,
            "exact_pro_200_candidate_and_admission_reproduced": True,
            "provider_execution_authorized_by_gate": False,
            "result_access_authorized_by_gate": False,
            "separate_single_use_wrapper_and_untouched_output_required": True,
            "post_integration_full_harness_required": True,
        },
        "evidence_boundary": {
            "credentials_read_by_gate": False,
            "new_provider_calls_made_by_gate": 0,
            "scientific_outcomes_accessed_by_gate": False,
            "blind_labels_accessed_by_gate": False,
            "logs_mutated_by_gate": False,
            "historical_frozen_assets_mutated_by_gate": False,
            "automatic_retries": 0,
            "provider_tools_enabled": False,
            "external_effects_enabled": False,
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
        raise ExperimentCloseoutHarnessGateV6Error("v8 Harness gate missing")
    observed = _read_json(GATE_PATH)
    expected = build_gate()
    if observed != expected:
        raise ExperimentCloseoutHarnessGateV6Error("v8 Harness gate drift")
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
