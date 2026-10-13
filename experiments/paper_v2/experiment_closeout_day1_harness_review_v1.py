"""中断的第 1 日收官 Harness 运行的纯内容复核模块。

分析第 1 日执行产物，排查环境依赖与外部接口问题。
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
    / "outputs/verification/experiment_closeout_day1_harness_20260801"
)
WRAPPER_PATH = (
    PROJECT_ROOT / "outputs/verification/run_experiment_closeout_day1_harness.ps1"
)
REVIEW_PATH = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/experiment_closeout_day1_harness_review_v1.json"
)
GENERATED_AT = "2026-08-02T10:14:40+08:00"
SCHEMA_VERSION = "m3-paper-v2-closeout-day1-harness-review-1.0"
EXPECTED_SHA256 = {
    "stdout.log": "d50286eb7ebc19725b57e6a1f93b8277aa3efb5eaadb88608d81c466fbe72113",
    "stderr.log": "73d513bdfe4e03e4e733563a57266a893a4e8a675c053c216fb230dd98f1b0ea",
}


class ExperimentCloseoutDay1HarnessReviewV1Error(ValueError):
    """当中断运行论据不再匹配其审查结果时抛出的异常。"""


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
        raise ExperimentCloseoutDay1HarnessReviewV1Error(
            f"missing interrupted-run artifact: {path}"
        )
    return {
        "path": _display_path(path),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise ExperimentCloseoutDay1HarnessReviewV1Error(
            f"cannot read interrupted-run artifact: {path}"
        ) from exc


def build_review() -> dict[str, Any]:
    stdout_path = RUN_ROOT / "stdout.log"
    stderr_path = RUN_ROOT / "stderr.log"
    receipt_path = RUN_ROOT / "receipt.json"
    stdout = _read_text(stdout_path)
    stderr = _read_text(stderr_path)
    stdout_lock = _lock(stdout_path)
    stderr_lock = _lock(stderr_path)
    if (
        stdout_lock["sha256"] != EXPECTED_SHA256["stdout.log"]
        or stderr_lock["sha256"] != EXPECTED_SHA256["stderr.log"]
    ):
        raise ExperimentCloseoutDay1HarnessReviewV1Error(
            "Day-1 Harness logs changed after interruption observation"
        )
    observations = {
        "pytest_summary_observed": (
            "1266 passed, 1 skipped, 3 warnings in 5108.35s (1:25:08)"
            in stdout
        ),
        "public_primary_v5_admission_observed": (
            '"status": "activated_for_exact_projected_analysis"' in stdout
        ),
        "aggregate_completion_marker_observed": "Verification failed=" in stdout,
        "wrapper_receipt_observed": receipt_path.exists(),
        "python_traceback_observed": "Traceback (most recent call last)" in stderr,
    }
    if (
        observations["pytest_summary_observed"] is not True
        or observations["public_primary_v5_admission_observed"] is not True
        or observations["aggregate_completion_marker_observed"] is not False
        or observations["wrapper_receipt_observed"] is not False
        or observations["python_traceback_observed"] is not False
    ):
        raise ExperimentCloseoutDay1HarnessReviewV1Error(
            "Day-1 Harness interruption signature drift"
        )
    core = {
        "schema_version": SCHEMA_VERSION,
        "artifact_role": "content_only_review_of_interrupted_full_harness",
        "reviewed_at": GENERATED_AT,
        "status": "inconclusive_host_interruption_full_rerun_required",
        "source_locks": [stdout_lock, stderr_lock, _lock(WRAPPER_PATH)],
        "observations": observations,
        "verdict": {
            "full_harness_passed": False,
            "full_harness_failed": False,
            "partial_pytest_subrun_passed": True,
            "current_worktree_full_rerun_required": True,
        },
        "evidence_boundary": {
            "historical_logs_mutated": False,
            "historical_process_resumed": False,
            "provider_execution_authorized": False,
            "network_calls_made_by_review": 0,
            "credentials_read": False,
            "scientific_outcomes_accessed": False,
        },
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ExperimentCloseoutDay1HarnessReviewV1Error(
            f"{path}: invalid JSON"
        ) from exc
    if not isinstance(value, dict):
        raise ExperimentCloseoutDay1HarnessReviewV1Error(
            f"{path}: expected object"
        )
    return value


def write_review() -> dict[str, Any]:
    value = build_review()
    REVIEW_PATH.parent.mkdir(parents=True, exist_ok=True)
    REVIEW_PATH.write_bytes(canonical_json_bytes(value) + b"\n")
    return value


def validate_review(value: Mapping[str, Any]) -> dict[str, Any]:
    expected = build_review()
    if dict(value) != expected:
        raise ExperimentCloseoutDay1HarnessReviewV1Error(
            "Day-1 Harness interruption review drift"
        )
    return dict(value)


def verify_review() -> dict[str, Any]:
    if not REVIEW_PATH.is_file():
        raise ExperimentCloseoutDay1HarnessReviewV1Error(
            "Day-1 Harness interruption review missing"
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
