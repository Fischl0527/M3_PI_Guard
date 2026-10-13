"""绑定全新 Harness v7 与当前收官证据（不执行新的模型请求）。

验证阶段交付物的自包含性与不可变性。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping

from experiments.paper_v2 import adaptive_formal_pro_controller_v2 as adaptive
from experiments.paper_v2 import experiment_closeout_freeze_v1 as closeout
from experiments.paper_v2 import experiment_closeout_harness_gate_v4 as prior_gate
from experiments.paper_v2 import gemini_public_controller_v5 as gemini
from experiments.paper_v2.contracts import canonical_json_bytes, sha256_canonical_json


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUN_ROOT = (
    PROJECT_ROOT
    / "outputs/verification/experiment_closeout_fresh_harness_v7_20260806"
)
RUNNING_PATH = RUN_ROOT / "running.json"
STDOUT_PATH = RUN_ROOT / "stdout.log"
STDERR_PATH = RUN_ROOT / "stderr.log"
RECEIPT_PATH = RUN_ROOT / "receipt.json"
LAUNCH_PATH = RUN_ROOT / "launch.json"
HELPER_PATH = PROJECT_ROOT / "harness/scripts/verify_with_receipt_v3.ps1"
LAUNCHER_PATH = (
    PROJECT_ROOT
    / "outputs/verification/start_experiment_closeout_fresh_harness_v7.ps1"
)
PRIOR_GATE_PATH = prior_gate.GATE_PATH
V7_AUDIT_PATH = closeout.V7_IMMUTABLE_AUDIT
GEMINI_SEGMENT_INDEX = 0
GEMINI_QUOTA_DAY = "2026-08-05"
GEMINI_REVIEW_PATH = (
    PROJECT_ROOT
    / "outputs/paper_upgrade_v2/formal_public/gemini"
    / "public-v5-canary-recovery-s0-885cf3a88684ca7427a29a5c0b65e0a6f97746133279fb59341bae557c4b48b2"
    / "technical_segment_review_v6.json"
)
GEMINI_ADMISSION_PATH = gemini.admission_path(
    GEMINI_SEGMENT_INDEX, GEMINI_QUOTA_DAY
)
GEMINI_WRAPPER_PATH = (
    PROJECT_ROOT
    / "outputs/verification/run_gemini_public_v5_recovery_segment_guarded_v2.ps1"
)
GEMINI_WRAPPER_RECEIPT_PATH = (
    PROJECT_ROOT
    / "outputs/verification/gemini_public_v5_recovery_s0_2026-08-05_guarded_v2/receipt.json"
)
ADAPTIVE_STAGE = "pro_50"
ADAPTIVE_CANDIDATE_PATH = adaptive.candidate_path(ADAPTIVE_STAGE)
ADAPTIVE_ADMISSION_PATH = adaptive.admission_path(ADAPTIVE_STAGE)
ADAPTIVE_WRAPPER_PATH = (
    PROJECT_ROOT
    / "outputs/verification/run_adaptive_formal_pro_v2_guarded_v3.ps1"
)
TEST_PATH = (
    PROJECT_ROOT / "tests/unit/test_paper_v2_experiment_closeout_harness_gate_v5.py"
)
WRAPPER_TEST_PATH = (
    PROJECT_ROOT / "tests/unit/test_paper_v2_adaptive_formal_pro_v2_wrapper_v3.py"
)
GATE_PATH = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/experiment_closeout_harness_gate_v5.json"
)

SCHEMA_VERSION = "m3-paper-v2-experiment-closeout-harness-gate-5.0"
EXPECTED_PYTEST_PASSED = 1552
EXPECTED_PYTEST_SKIPPED = 1
EXPECTED_PYTEST_WARNINGS = 3
EXPECTED_RUNTIME_AUDITOR_DELETE_BLOCKS = 213
EXPECTED_AGENTDOJO_COMMIT = "089ed468cf3ed0322acc66b0211f26d9d90dbf60"
EXPECTED_RECEIPT_CHECKS = prior_gate.EXPECTED_RECEIPT_CHECKS
EXPECTED_PASS_NAMES = prior_gate.EXPECTED_PASS_NAMES
EXPECTED_API_ENVIRONMENT_VARIABLES = (
    "ANTHROPIC_API_KEY",
    "DEEPSEEK_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "M3_CANARY_SECRET_API_KEY",
    "M3_FRONTIER_API_CONSENT",
    "OPENAI_API_KEY",
    "OPENAI_COMPATIBLE_API_KEY",
)
PYTEST_SUMMARY = re.compile(
    r"(?P<passed>\d+) passed, (?P<skipped>\d+) skipped, "
    r"(?P<warnings>\d+) warnings in (?P<duration>[^\r\n]+)"
)
SECRET_PATTERNS = prior_gate.SECRET_PATTERNS
SAFE_GIT_CHECKOUTS = tuple(
    PROJECT_ROOT / relative
    for relative in (
        "external/benchmarks/agentdojo",
        "external/benchmarks/injecagent",
        "external/paper_v2_audits/vigil",
        "external/paper_v2_audits/drift",
        "external/paper_v2_audits/asb",
        "external/paper_v2_audits/bipia",
        "external/paper_v2_audits/piarena",
        "external/paper_v2_audits/struq",
        "external/paper_v2_audits/toolsafe",
        "external/paper_v2_audits/wasp-http1",
        "external/baselines/camel-prompt-injection",
        "external/baselines/fides",
        "external/baselines/ipiguard",
        "external/baselines/progent",
        "external/baselines/PurpleLlama",
    )
)


class ExperimentCloseoutHarnessGateV5Error(ValueError):
    """当 Fresh Harness v7 或绑定的前置条件发生漂移时抛出的异常。"""


@contextmanager
def _process_scoped_safe_directories() -> Iterator[None]:
    """追加精确的仅限当前进程的 Git safe.directory 条目并在此后恢复。"""

    count_key = "GIT_CONFIG_COUNT"
    previous_count = os.environ.get(count_key)
    try:
        count = int(previous_count or "0")
    except ValueError as exc:
        raise ExperimentCloseoutHarnessGateV5Error(
            "invalid inherited GIT_CONFIG_COUNT"
        ) from exc
    previous_entries: list[tuple[str, str | None]] = []
    for offset, checkout in enumerate(SAFE_GIT_CHECKOUTS):
        if not (checkout / ".git").exists():
            raise ExperimentCloseoutHarnessGateV5Error(
                f"missing safe-directory checkout: {checkout}"
            )
        index = count + offset
        key_name = f"GIT_CONFIG_KEY_{index}"
        value_name = f"GIT_CONFIG_VALUE_{index}"
        previous_entries.extend(
            (
                (key_name, os.environ.get(key_name)),
                (value_name, os.environ.get(value_name)),
            )
        )
        os.environ[key_name] = "safe.directory"
        os.environ[value_name] = checkout.resolve().as_posix()
    os.environ[count_key] = str(count + len(SAFE_GIT_CHECKOUTS))
    try:
        yield
    finally:
        for name, previous in [(count_key, previous_count), *previous_entries]:
            if previous is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = previous


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
        raise ExperimentCloseoutHarnessGateV5Error(f"missing gate input: {path}")
    return {
        "path": _display_path(path),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ExperimentCloseoutHarnessGateV5Error(
            f"{path}: invalid JSON"
        ) from exc
    if not isinstance(value, dict):
        raise ExperimentCloseoutHarnessGateV5Error(f"{path}: expected object")
    return value


def _manifest_matches(value: Mapping[str, Any]) -> bool:
    core = {key: child for key, child in value.items() if key != "manifest_sha256"}
    return value.get("manifest_sha256") == sha256_canonical_json(core)


def _secret_pattern_hit_count(*texts: str) -> int:
    return sum(
        len(pattern.findall(text))
        for pattern in SECRET_PATTERNS
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
        raise ExperimentCloseoutHarnessGateV5Error(
            "v7 Harness pytest summary is missing or ambiguous"
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
        raise ExperimentCloseoutHarnessGateV5Error(
            "v7 Harness terminal evidence did not pass"
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
        or receipt.get("api_environment_variables_scrubbed")
        != list(EXPECTED_API_ENVIRONMENT_VARIABLES)
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
        or historical_verify_sha != receipt.get("verify_script_sha256_after")
        or historical_verify_sha != running.get("verify_script_sha256")
        or historical_verify_sha != launch.get("verify_script_sha256")
        or historical_helper_sha != receipt.get("helper_script_sha256_after")
        or historical_helper_sha != running.get("helper_script_sha256")
        or historical_helper_sha != launch.get("helper_script_sha256")
        or historical_helper_sha != _sha256_file(HELPER_PATH)
        or launch.get("launcher_script_sha256") != _sha256_file(LAUNCHER_PATH)
        or receipt.get("expected_agentdojo_commit") != EXPECTED_AGENTDOJO_COMMIT
        or receipt.get("observed_agentdojo_commit") != EXPECTED_AGENTDOJO_COMMIT
        or receipt.get("git_safe_directory_scope") != "process_only"
        or receipt.get("global_git_config_mutated") is not False
        or receipt.get("repository_git_config_mutated") is not False
    ):
        raise ExperimentCloseoutHarnessGateV5Error(
            "v7 Harness receipt or historical source chain drift"
        )


def _resolve_logged_path(value: Any) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else PROJECT_ROOT / path


def _validate_gemini_segment() -> tuple[dict[str, Any], dict[str, Any]]:
    candidate = gemini.verify_candidate()
    admission = gemini.validate_segment_admission(
        _read_json(GEMINI_ADMISSION_PATH),
        segment_index=GEMINI_SEGMENT_INDEX,
        quota_day=GEMINI_QUOTA_DAY,
    )
    review = _read_json(GEMINI_REVIEW_PATH)
    receipt = _read_json(GEMINI_WRAPPER_RECEIPT_PATH)
    checks = review.get("checks")
    step_names = (
        "01_harness_gate",
        "02_admission",
        "03_execute",
        "04_technical_review",
    )
    steps = receipt.get("steps")
    if not isinstance(steps, Mapping):
        raise ExperimentCloseoutHarnessGateV5Error(
            "Gemini wrapper receipt steps missing"
        )
    logged_texts: list[str] = []
    for name in step_names:
        step = steps.get(name)
        if not isinstance(step, Mapping) or step.get("exit_code") != 0:
            raise ExperimentCloseoutHarnessGateV5Error(
                "Gemini wrapper step drift"
            )
        for key in ("stdout", "stderr"):
            path = _resolve_logged_path(step.get(f"{key}_path"))
            if (
                not path.is_file()
                or step.get(f"{key}_sha256") != _sha256_file(path)
            ):
                raise ExperimentCloseoutHarnessGateV5Error(
                    "Gemini wrapper log chain drift"
                )
            logged_texts.append(path.read_text(encoding="utf-8", errors="replace"))
    if (
        candidate.get("manifest_sha256")
        != review.get("candidate_manifest_sha256")
        or admission.get("manifest_sha256") is None
        or _sha256_file(GEMINI_ADMISSION_PATH)
        != review.get("admission_file_sha256")
        or not _manifest_matches(review)
        or review.get("status")
        != "gemini_public_v5_recovery_segment_gate_pass"
        or review.get("technical_gate_passed") is not True
        or review.get("matrix_continuation_eligible") is not True
        or review.get("scientific_outcomes_accessed") is not False
        or review.get("result_admission_authorized") is not False
        or review.get("expected_records") != 1
        or review.get("observed_records") != 1
        or not isinstance(checks, Mapping)
        or len(checks) != 16
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
        or steps.get("secret_scan", {}).get("secret_pattern_hit_count") != 0
        or receipt.get("wrapper_sha256") != _sha256_file(GEMINI_WRAPPER_PATH)
        or receipt.get("harness_gate_sha256") != _sha256_file(PRIOR_GATE_PATH)
        or receipt.get("candidate_sha256") != _sha256_file(gemini.CANDIDATE_PATH)
        or receipt.get("admission_sha256") != _sha256_file(GEMINI_ADMISSION_PATH)
        or _secret_pattern_hit_count(*logged_texts) != 0
    ):
        raise ExperimentCloseoutHarnessGateV5Error(
            "Gemini Public-v5 segment-0 evidence drift"
        )
    return review, receipt


def _validate_adaptive_path() -> tuple[dict[str, Any], dict[str, Any]]:
    candidate = adaptive.verify_stage_candidate(ADAPTIVE_STAGE)
    admission = adaptive.validate_stage_admission(
        _read_json(ADAPTIVE_ADMISSION_PATH), stage=ADAPTIVE_STAGE
    )
    if (
        candidate.get("status") != "offline_qualified_execution_not_authorized"
        or candidate.get("scope", {}).get("authorized_task_count") != 32
        or candidate.get("authorization", {}).get("stage_execution_authorized")
        is not False
        or candidate.get("authorization", {}).get("result_admission_authorized")
        is not False
        or candidate.get("execution_controls", {}).get("automatic_retries") != 0
        or candidate.get("execution_controls", {}).get("provider_tools_enabled")
        is not False
        or candidate.get("execution_controls", {}).get("external_effects_enabled")
        is not False
        or admission.get("status")
        != "activated_for_one_exact_order_bound_adaptive_stage"
        or admission.get("candidate_manifest_sha256")
        != candidate.get("manifest_sha256")
        or admission.get("run_id") != candidate.get("scope", {}).get("run_id")
        or admission.get("execution_identity")
        != candidate.get("scope", {}).get("execution_identity")
        or admission.get("authorization", {}).get("stage_execution_authorized")
        is not True
        or admission.get("authorization", {}).get("result_admission_authorized")
        is not False
        or admission.get("authorization", {}).get("automatic_retries") != 0
        or admission.get("authorization", {}).get("provider_tools_enabled")
        is not False
        or admission.get("authorization", {}).get("external_effects_enabled")
        is not False
    ):
        raise ExperimentCloseoutHarnessGateV5Error(
            "Adaptive Pro-50 candidate/admission drift"
        )
    return candidate, admission


def build_gate() -> dict[str, Any]:
    with _process_scoped_safe_directories():
        predecessor = prior_gate.verify_gate()
        closeout_status = closeout.verify_bundle()
        v7_audit = _read_json(V7_AUDIT_PATH)
        gemini_review, gemini_receipt = _validate_gemini_segment()
        adaptive_candidate, adaptive_admission = _validate_adaptive_path()
    receipt = _read_json(RECEIPT_PATH)
    running = _read_json(RUNNING_PATH)
    launch = _read_json(LAUNCH_PATH)
    stdout = STDOUT_PATH.read_text(encoding="utf-8", errors="replace")
    stderr = STDERR_PATH.read_text(encoding="utf-8", errors="replace")
    observations = analyze_transcript(stdout, stderr)
    _validate_receipt_chain(receipt, running, launch)

    if (
        predecessor.get("status")
        != "fresh_v6_full_harness_closeout_prerequisite_satisfied"
        or predecessor.get("verdict", {}).get("provider_execution_authorized_by_gate")
        is not False
        or closeout_status.get("status") != "experiment_closeout_freeze_verified"
        or v7_audit.get("status")
        != "verified_historical_failure_closed_nonresumable"
        or v7_audit.get("record_count") != 0
        or v7_audit.get("open_attempt_count") != 1
        or v7_audit.get("prior_run_resumable") is not False
        or v7_audit.get("rerun_authorized") is not False
    ):
        raise ExperimentCloseoutHarnessGateV5Error(
            "closeout predecessor or historical v7 boundary drift"
        )

    core = {
        "schema_version": SCHEMA_VERSION,
        "artifact_role": "fresh_v7_direct_exit_non_authorizing_closeout_gate",
        "status": "fresh_v7_full_harness_execution_prerequisite_satisfied",
        "source_locks": [
            _lock(LAUNCH_PATH),
            _lock(RUNNING_PATH),
            _lock(STDOUT_PATH),
            _lock(STDERR_PATH),
            _lock(RECEIPT_PATH),
            _lock(HELPER_PATH),
            _lock(LAUNCHER_PATH),
            _lock(PRIOR_GATE_PATH),
            _lock(V7_AUDIT_PATH),
            _lock(gemini.CANDIDATE_PATH),
            _lock(GEMINI_ADMISSION_PATH),
            _lock(GEMINI_REVIEW_PATH),
            _lock(GEMINI_WRAPPER_PATH),
            _lock(GEMINI_WRAPPER_RECEIPT_PATH),
            _lock(ADAPTIVE_CANDIDATE_PATH),
            _lock(ADAPTIVE_ADMISSION_PATH),
            _lock(ADAPTIVE_WRAPPER_PATH),
            _lock(Path(__file__)),
            _lock(TEST_PATH),
            _lock(WRAPPER_TEST_PATH),
        ],
        "prerequisite_manifests": {
            "fresh_harness_v6_gate": predecessor["manifest_sha256"],
            "historical_medium_v7_immutable_audit": v7_audit["manifest_sha256"],
            "gemini_public_v5_segment_0_review": gemini_review["manifest_sha256"],
            "adaptive_pro_50_candidate": adaptive_candidate["manifest_sha256"],
            "adaptive_pro_50_admission": adaptive_admission["manifest_sha256"],
        },
        "observations": observations,
        "technical_scope": {
            "gemini_segment_0_records": gemini_review["observed_records"],
            "gemini_segment_0_provider_transports": gemini_review[
                "provider_transport_completions"
            ],
            "gemini_segment_0_wrapper_exit_code": gemini_receipt[
                "final_exit_code"
            ],
            "adaptive_stage": ADAPTIVE_STAGE,
            "adaptive_pending_tasks": adaptive_candidate["scope"][
                "authorized_task_count"
            ],
            "adaptive_execution_identity": adaptive_candidate["scope"][
                "execution_identity"
            ],
        },
        "verdict": {
            "operating_system_exit_code_directly_observed": True,
            "full_harness_passed": True,
            "closeout_harness_prerequisite_satisfied": True,
            "exact_adaptive_candidate_and_admission_reproduced": True,
            "provider_execution_authorized_by_gate": False,
            "result_access_authorized_by_gate": False,
            "separate_single_use_wrapper_and_untouched_output_required": True,
        },
        "evidence_boundary": {
            "credentials_read": False,
            "provider_calls_made": 0,
            "scientific_outcomes_accessed": False,
            "blind_labels_accessed": False,
            "logs_mutated": False,
            "historical_frozen_assets_mutated": False,
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
        raise ExperimentCloseoutHarnessGateV5Error("v7 Harness gate missing")
    observed = _read_json(GATE_PATH)
    expected = build_gate()
    if observed != expected:
        raise ExperimentCloseoutHarnessGateV5Error("v7 Harness gate drift")
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
