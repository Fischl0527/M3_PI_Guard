"""Freeze the content-free abort review for the Public-v1 primary canary."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from experiments.paper_v2 import formal_matrix_controller_v1 as medium_v1
from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.public_live_controller_v1 import (
    _canary_rows,
    validate_canary_admission,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ADMISSION = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/admissions/"
    "deepseek_public_primary_canary_admission_v1.json"
)
FIRST_STDERR = (
    PROJECT_ROOT
    / "outputs/paper_v2/verification/public_v1_primary_canary_live/"
    "canary_20260728_081451.stderr.log"
)
FIRST_EXIT = FIRST_STDERR.with_name("canary_20260728_081451.exit.txt")
SECOND_STDERR = (
    PROJECT_ROOT
    / "outputs/paper_v2/verification/public_v1_primary_canary_live/"
    "canary_20260728_081841.stderr.log"
)
SECOND_EXIT = SECOND_STDERR.with_name("canary_20260728_081841.exit.txt")
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/public_primary_canary_abort_review_v1.json"
)
GENERATED_AT = "2026-07-28T08:30:00+08:00"


class PublicAbortReviewError(ValueError):
    """Raised when the frozen Public-v1 abort evidence drifts."""


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PublicAbortReviewError(f"{path}: expected an object")
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _lock(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise PublicAbortReviewError(f"missing abort evidence: {path}")
    return {
        "path": path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def build_abort_review() -> dict[str, Any]:
    admission = validate_canary_admission(
        _load_json(ADMISSION),
        model_role="primary",
    )
    root = PROJECT_ROOT / str(admission["scope"]["output_root"])
    attempt_path = root / "attempt_events.jsonl"
    events = medium_v1._load_jsonl(attempt_path)
    status = medium_v1.validate_attempt_events(
        events,
        run_id=str(admission["scope"]["run_id"]),
        execution_identity=str(admission["scope"]["execution_identity"]),
        known_work_keys={
            str(item["work_key"]) for item in _canary_rows("primary")
        },
    )
    first_error = FIRST_STDERR.read_text(encoding="utf-8")
    second_error = SECOND_STDERR.read_text(encoding="utf-8")
    if (
        FIRST_EXIT.read_text(encoding="ascii").strip() != "1"
        or SECOND_EXIT.read_text(encoding="ascii").strip() != "1"
        or "dedicated PromptGuard environment is required" not in first_error
        or "unknown paper-v2 work key" not in second_error
    ):
        raise PublicAbortReviewError("public abort classification drift")
    trace_root = root / "traces"
    trace_files = (
        list(trace_root.glob("*.jsonl")) if trace_root.is_dir() else []
    )
    absent = {
        "record_ledger": not (root / "records.jsonl").exists(),
        "budget_ledger": not (root / "budget_events.jsonl").exists(),
        "provider_traces": not trace_files,
    }
    if (
        status["event_count"] != 1
        or len(status["open_work_keys"]) != 1
        or status["terminal_by_work_key"]
        or not all(absent.values())
    ):
        raise PublicAbortReviewError(
            "Public-v1 did not remain a zero-request open attempt"
        )
    core: dict[str, Any] = {
        "schema_version": "m3-paper-v2-public-canary-abort-review-1.0",
        "generated_at": GENERATED_AT,
        "status": "aborted_before_first_provider_request",
        "run_id": admission["scope"]["run_id"],
        "execution_identity": admission["scope"]["execution_identity"],
        "admission_manifest_sha256": admission["manifest_sha256"],
        "attempt_status": {
            "event_count": status["event_count"],
            "open_attempt_count": len(status["open_work_keys"]),
            "terminal_attempt_count": len(status["terminal_by_work_key"]),
            "tail_sha256": status["tail_sha256"],
        },
        "failure_classification": [
            "missing_local_promptguard_dependencies_pre_attempt",
            "public_agentdojo_work_key_not_in_medium_resolver",
        ],
        "artifact_locks": [
            _lock(path)
            for path in (
                ADMISSION,
                FIRST_STDERR,
                FIRST_EXIT,
                SECOND_STDERR,
                SECOND_EXIT,
                attempt_path,
            )
        ],
        "evidence": {
            **absent,
            "provider_requests": 0,
            "api_cost_cny": 0.0,
            "automatic_retries": 0,
            "scientific_outcomes_accessed": False,
            "formal_results_created": 0,
            "run_resumable": False,
        },
    }
    return {
        **core,
        "manifest_sha256": sha256_canonical_json(core),
    }


def write_abort_review(path: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    value = build_abort_review()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return value


def verify_abort_review(path: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    observed = _load_json(path)
    expected = build_abort_review()
    if observed != expected:
        raise PublicAbortReviewError("public abort review drift")
    return expected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--verify", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    value = (
        write_abort_review(args.output)
        if args.write
        else verify_abort_review(args.output)
    )
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
