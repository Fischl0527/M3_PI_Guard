"""恢复终止的 Gemini v4 分段证据（严禁捏造或修补未观察数据）。

提取断点前已完成的合法结果并打上恢复标记归档。
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from experiments.paper_v2.contracts import canonical_json_bytes, sha256_canonical_json


PROJECT_ROOT = Path(__file__).resolve().parents[2]
WRAPPER_PATH = (
    PROJECT_ROOT / "outputs/verification/run_gemini_public_v4_segment_guarded.ps1"
)
WRAPPER_RUN_ROOT = (
    PROJECT_ROOT
    / "outputs/verification/gemini_public_v4_s0_2026-08-02_guarded"
)
MISSING_RECEIPT_PATH = WRAPPER_RUN_ROOT / "receipt.json"
SEGMENT_ROOT = (
    PROJECT_ROOT
    / "outputs/paper_upgrade_v2/formal_public/gemini/"
    "public-v4-canary-s0-ab5ec080f3b268d77f1dbe41db03601a49281cfc1bc602bcbce0395bdda530c5"
)
V4_REVIEW_PATH = SEGMENT_ROOT / "technical_segment_review_v4.json"
V5_REVIEW_PATH = SEGMENT_ROOT / "technical_segment_review_v5.json"
RECOVERY_PATH = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/gemini_public_v4_s0_wrapper_recovery_v1.json"
)
RECOVERY_TEST_PATH = (
    PROJECT_ROOT
    / "tests/unit/test_paper_v2_gemini_public_v4_wrapper_recovery_v1.py"
)

SCHEMA_VERSION = "m3-paper-v2-gemini-public-wrapper-recovery-1.0"
RECOVERED_AT = "2026-08-03T12:50:00+08:00"
EXPECTED_WRAPPER_FILES = (
    "01_harness_gate.stderr.log",
    "01_harness_gate.stdout.log",
    "02_admission.stderr.log",
    "02_admission.stdout.log",
    "03_execute.stderr.log",
    "03_execute.stdout.log",
    "04_technical_review.stderr.log",
    "04_technical_review.stdout.log",
)
EXPECTED_HISTORICAL_SHA256 = {
    "outputs/verification/run_gemini_public_v4_segment_guarded.ps1": (
        "ee25e91919e7c4fa492ce5ad472fb4e0e025ef87b2696e3edfa0bac2555f5a82"
    ),
    (
        "outputs/verification/gemini_public_v4_s0_2026-08-02_guarded/"
        "01_harness_gate.stdout.log"
    ): "35fd3ca658113f7166b9c75885b174c106887f6a356bdcd103fdffc57cec7fff",
    (
        "outputs/verification/gemini_public_v4_s0_2026-08-02_guarded/"
        "01_harness_gate.stderr.log"
    ): "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    (
        "outputs/verification/gemini_public_v4_s0_2026-08-02_guarded/"
        "02_admission.stdout.log"
    ): "d82d2baa0f34890ddac67476e3684a9cbfddd1ee4db2258e62bf4b18f302bb2c",
    (
        "outputs/verification/gemini_public_v4_s0_2026-08-02_guarded/"
        "02_admission.stderr.log"
    ): "17dcbfb9360680e0268cf8f6f0a878f733f67ef8070f3f010e4651c36e822c1c",
    (
        "outputs/verification/gemini_public_v4_s0_2026-08-02_guarded/"
        "03_execute.stdout.log"
    ): "7645a48f7760cc24aae48b2313cf7ede4f706a0cd1970c67902bac4f6bb7ad72",
    (
        "outputs/verification/gemini_public_v4_s0_2026-08-02_guarded/"
        "03_execute.stderr.log"
    ): "1f6aab76f26cff9ed23f3942cb7b06be7e5f2d040f4ca164709544ed7af9d282",
    (
        "outputs/verification/gemini_public_v4_s0_2026-08-02_guarded/"
        "04_technical_review.stdout.log"
    ): "264e76639348366b8fbd311719627fafb7f054b871ff33bec603297740acc3dd",
    (
        "outputs/verification/gemini_public_v4_s0_2026-08-02_guarded/"
        "04_technical_review.stderr.log"
    ): "7bb9b07c137153e43a954f3a9d013fa35e6812ec1647b4b122ff49c09c5a7e76",
    (
        "outputs/paper_upgrade_v2/formal_public/gemini/"
        "public-v4-canary-s0-ab5ec080f3b268d77f1dbe41db03601a49281cfc1bc602bcbce0395bdda530c5/"
        "technical_segment_review_v4.json"
    ): "3a69e0ad6e28787c1e650cf8165d8d817896e7b89cb8ff3e375e5a4ceccfe54a",
    (
        "outputs/paper_upgrade_v2/formal_public/gemini/"
        "public-v4-canary-s0-ab5ec080f3b268d77f1dbe41db03601a49281cfc1bc602bcbce0395bdda530c5/"
        "technical_segment_review_v5.json"
    ): "c07b9713b7350255e63c2fe8ecd3129f57bd2f6d8951780e7b4cfaacae1994ec",
}
EXPECTED_AUDITOR_BLOCKS = {
    "01_harness_gate.stderr.log": 0,
    "02_admission.stderr.log": 15,
    "03_execute.stderr.log": 30,
    "04_technical_review.stderr.log": 45,
}
AUDITOR_LINE = "[RuntimeAuditor] Blocked tool call: delete_record"


class GeminiPublicV4WrapperRecoveryV1Error(ValueError):
    """当不可变的终端分段论据无法恢复时抛出的异常。"""


def _display_path(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _lock(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise GeminiPublicV4WrapperRecoveryV1Error(f"missing recovery source: {path}")
    return {
        "path": _display_path(path),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GeminiPublicV4WrapperRecoveryV1Error(
            f"invalid recovery JSON: {path}"
        ) from exc
    if not isinstance(value, dict):
        raise GeminiPublicV4WrapperRecoveryV1Error(
            f"recovery JSON must be an object: {path}"
        )
    return value


def _read_single_json_line(path: Path) -> dict[str, Any]:
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line]
    if len(lines) != 1:
        raise GeminiPublicV4WrapperRecoveryV1Error(
            f"expected exactly one JSON stdout line: {path}"
        )
    try:
        value = json.loads(lines[0])
    except json.JSONDecodeError as exc:
        raise GeminiPublicV4WrapperRecoveryV1Error(
            f"invalid JSON stdout line: {path}"
        ) from exc
    if not isinstance(value, dict):
        raise GeminiPublicV4WrapperRecoveryV1Error(
            f"stdout JSON must be an object: {path}"
        )
    return value


def _verify_self_manifest(value: Mapping[str, Any], *, label: str) -> None:
    manifest = value.get("manifest_sha256")
    core = {key: item for key, item in value.items() if key != "manifest_sha256"}
    if manifest != sha256_canonical_json(core):
        raise GeminiPublicV4WrapperRecoveryV1Error(f"{label} manifest drift")


def _assert_historical_hashes(locks: list[Mapping[str, Any]]) -> None:
    observed = {str(lock["path"]): str(lock["sha256"]) for lock in locks}
    if observed != EXPECTED_HISTORICAL_SHA256:
        raise GeminiPublicV4WrapperRecoveryV1Error(
            "Gemini v4 wrapper historical source-lock drift"
        )


def _verify_wrapper_logs() -> dict[str, Any]:
    if MISSING_RECEIPT_PATH.exists():
        raise GeminiPublicV4WrapperRecoveryV1Error(
            "original wrapper receipt unexpectedly exists; recovery is invalid"
        )
    actual_files = tuple(sorted(path.name for path in WRAPPER_RUN_ROOT.iterdir()))
    if actual_files != EXPECTED_WRAPPER_FILES:
        raise GeminiPublicV4WrapperRecoveryV1Error(
            "Gemini wrapper run-root file closure drift"
        )

    block_counts: dict[str, int] = {}
    for name, expected_count in EXPECTED_AUDITOR_BLOCKS.items():
        path = WRAPPER_RUN_ROOT / name
        nonempty = [
            line for line in path.read_text(encoding="utf-8").splitlines() if line
        ]
        if any(line != AUDITOR_LINE for line in nonempty):
            raise GeminiPublicV4WrapperRecoveryV1Error(
                f"unexpected stderr content in {name}"
            )
        if len(nonempty) != expected_count:
            raise GeminiPublicV4WrapperRecoveryV1Error(
                f"RuntimeAuditor block count drift in {name}"
            )
        block_counts[name] = len(nonempty)
    return {
        "exact_eight_step_logs": True,
        "missing_original_receipt_confirmed": True,
        "stderr_contains_only_expected_runtime_auditor_blocks": True,
        "runtime_auditor_block_counts": block_counts,
    }


def build_recovery() -> dict[str, Any]:
    historical_paths = [PROJECT_ROOT / path for path in EXPECTED_HISTORICAL_SHA256]
    historical_locks = [_lock(path) for path in historical_paths]
    _assert_historical_hashes(historical_locks)
    wrapper_observations = _verify_wrapper_logs()

    execute = _read_single_json_line(WRAPPER_RUN_ROOT / "03_execute.stdout.log")
    expected_execute = {
        "status": "gemini_public_v4_segment_complete_unadmitted",
        "segment_index": 0,
        "quota_day": "2026-08-02",
        "record_count": 1,
        "remaining_records": 0,
        "completed_this_process": 1,
        "provider_calls_completed": 0,
        "automatic_retries": 0,
        "billing_tier": "free",
        "charged_usd": 0.0,
        "paid_ceiling_usd": 0.0,
        "provider_tools_enabled": False,
        "external_effects_enabled": False,
        "result_admission_authorized": False,
        "quota_reservation_sha256": (
            "b3303408f0eb664d586707487d605eb4c617144ab49631d0631db07626128c0a"
        ),
    }
    if execute != expected_execute:
        raise GeminiPublicV4WrapperRecoveryV1Error("execute stdout signature drift")

    v4_review = _read_json(V4_REVIEW_PATH)
    v4_stdout = _read_single_json_line(
        WRAPPER_RUN_ROOT / "04_technical_review.stdout.log"
    )
    if v4_stdout != v4_review:
        raise GeminiPublicV4WrapperRecoveryV1Error(
            "captured v4 review does not match persisted review"
        )
    _verify_self_manifest(v4_review, label="v4 review")
    false_v4_checks = sorted(
        key for key, passed in v4_review.get("checks", {}).items() if not passed
    )
    if (
        v4_review.get("status") != "gemini_public_v4_segment_technical_gate_fail"
        or v4_review.get("technical_gate_passed") is not False
        or false_v4_checks != ["call_ledger_matches_trace_bundles"]
        or v4_review.get("scientific_outcomes_accessed") is not False
        or v4_review.get("result_admission_authorized") is not False
    ):
        raise GeminiPublicV4WrapperRecoveryV1Error("v4 failure signature drift")

    v5_review = _read_json(V5_REVIEW_PATH)
    _verify_self_manifest(v5_review, label="v5 review")
    reconciliation = v5_review.get("reconciliation", {})
    reconciled_calls = reconciliation.get("reconciled_calls", [])
    if (
        v5_review.get("status") != "gemini_public_v5_segment_technical_gate_pass"
        or v5_review.get("technical_gate_passed") is not True
        or v5_review.get("matrix_continuation_eligible") is not True
        or v5_review.get("observed_records") != 1
        or v5_review.get("provider_call_attempts") != 1
        or v5_review.get("provider_transport_completions") != 1
        or v5_review.get("runtime_runner_failures_retained_in_itt") != 1
        or not all(v5_review.get("checks", {}).values())
        or v5_review.get("scientific_outcomes_accessed") is not False
        or v5_review.get("result_admission_authorized") is not False
        or reconciliation.get("reconciled_post_response_failure_count") != 1
        or len(reconciled_calls) != 1
        or reconciled_calls[0].get("runtime_error_type")
        != "VigilLiveDependencyError"
    ):
        raise GeminiPublicV4WrapperRecoveryV1Error("v5 reconciliation drift")

    core = {
        "schema_version": SCHEMA_VERSION,
        "artifact_role": "non_fabricating_wrapper_recovery_and_segment_reconciliation",
        "recovered_at": RECOVERED_AT,
        "status": "gemini_segment_terminal_reconciled_wrapper_exit_unknown",
        "provider_id": "gemini",
        "model_id": "gemini-3.6-flash",
        "run_id": v5_review["run_id"],
        "execution_identity": v5_review["execution_identity"],
        "segment_index": 0,
        "quota_day": "2026-08-02",
        "source_locks": [
            *historical_locks,
            _lock(Path(__file__)),
            _lock(RECOVERY_TEST_PATH),
        ],
        "wrapper_observations": wrapper_observations,
        "original_v4_failure": {
            "review_manifest_sha256": v4_review["manifest_sha256"],
            "technical_gate_passed": False,
            "sole_failed_check": "call_ledger_matches_trace_bundles",
        },
        "failure_aware_v5_reconciliation": {
            "review_manifest_sha256": v5_review["manifest_sha256"],
            "technical_gate_passed": True,
            "provider_call_attempts": 1,
            "provider_transport_completions": 1,
            "runner_failures_retained_in_itt": 1,
            "runtime_error_type": "VigilLiveDependencyError",
            "matrix_continuation_eligible": True,
        },
        "verdict": {
            "segment_evidence_terminal": True,
            "segment_zero_retry_preserved": True,
            "segment_can_be_counted_in_itt": True,
            "future_matrix_continuation_eligible": True,
            "same_segment_retry_authorized": False,
            "wrapper_operating_system_exit_known": False,
            "original_wrapper_receipt_fabricated": False,
            "scientific_result_admission_authorized": False,
        },
        "evidence_boundary": {
            "credentials_read_by_recovery": False,
            "new_provider_calls_made": 0,
            "provider_execution_authorized": False,
            "scientific_outcomes_accessed": False,
            "historical_logs_mutated": False,
            "paid_billing_enabled": False,
            "provider_tools_enabled": False,
            "external_effects_enabled": False,
        },
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def write_recovery() -> dict[str, Any]:
    value = build_recovery()
    RECOVERY_PATH.parent.mkdir(parents=True, exist_ok=True)
    RECOVERY_PATH.write_bytes(canonical_json_bytes(value) + b"\n")
    return value


def validate_recovery(value: Mapping[str, Any]) -> dict[str, Any]:
    expected = build_recovery()
    if dict(value) != expected:
        raise GeminiPublicV4WrapperRecoveryV1Error("wrapper recovery artifact drift")
    return dict(value)


def verify_recovery() -> dict[str, Any]:
    if not RECOVERY_PATH.is_file():
        raise GeminiPublicV4WrapperRecoveryV1Error("wrapper recovery artifact missing")
    return validate_recovery(_read_json(RECOVERY_PATH))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write-recovery", action="store_true")
    action.add_argument("--verify-recovery", action="store_true")
    args = parser.parse_args()
    value = write_recovery() if args.write_recovery else verify_recovery()
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
