"""Freeze the failed Gemini fallback v1 canary as permanently ineligible.

The review is content-free.  It binds the prospective candidate, active
admission, one open work-item attempt, and the closed started/failed call event
pair left by the VIGIL compatibility failure.  It never reads prompts,
responses, credentials, or scientific outcome fields.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

import experiments.paper_v2.gemini_fallback_controller_v1 as controller
from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.official_provider_executor import (
    load_call_events,
    validate_call_events,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_ROOT = PROJECT_ROOT / "protocols/paper_upgrade_v2"
DEFAULT_OUTPUT = (
    PROTOCOL_ROOT / "gemini_fallback_abort_review_v1.json"
)
SCHEMA_VERSION = "m3-paper-v2-gemini-fallback-abort-review-1.0"
GENERATED_AT = "2026-07-27T01:25:00+08:00"


class GeminiFallbackAbortReviewError(ValueError):
    """Raised when the failed v1 trace no longer matches the frozen review."""


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise GeminiFallbackAbortReviewError(
            f"{path}: expected a JSON object"
        )
    return value


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                raise GeminiFallbackAbortReviewError(
                    f"{path}:{line_number}: blank row"
                )
            value = json.loads(line)
            if not isinstance(value, dict):
                raise GeminiFallbackAbortReviewError(
                    f"{path}:{line_number}: expected an object"
                )
            rows.append(value)
    return rows


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _display_path(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT).as_posix()


def _file_lock(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise GeminiFallbackAbortReviewError(
            f"required v1 evidence is missing: {path}"
        )
    return {
        "path": _display_path(path),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def _without_manifest(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: item
        for key, item in value.items()
        if key != "manifest_sha256"
    }


def build_review() -> dict[str, Any]:
    candidate = controller.verify_candidate()
    admission = controller.validate_manifest(
        _load_json(controller.DEFAULT_CANARY_ADMISSION),
        expected_role="three_condition_canary_authorization",
    )
    outputs = candidate["scope"]["outputs"]
    root = PROJECT_ROOT / outputs["root"]
    attempt_path = PROJECT_ROOT / outputs["attempt_ledger_path"]
    call_path = PROJECT_ROOT / outputs["call_ledger_path"]
    record_path = PROJECT_ROOT / outputs["record_ledger_path"]
    evidence_path = PROJECT_ROOT / outputs["evidence_ledger_path"]

    attempts = _load_jsonl(attempt_path)
    calls = load_call_events(call_path)
    records = _load_jsonl(record_path)
    evidence = _load_jsonl(evidence_path)
    call_status = validate_call_events(
        calls,
        execution_identity=candidate["scope"]["execution_identity"],
        provider_id=controller.PROVIDER_ID,
        model_id=controller.MODEL_ID,
    )

    checks = {
        "candidate_bound": (
            admission["authorization"]["candidate_manifest_sha256"]
            == candidate["manifest_sha256"]
        ),
        "one_started_attempt": (
            len(attempts) == 1
            and attempts[0].get("event_type") == "started"
        ),
        "single_closed_failed_call": (
            len(calls) == 2
            and [row.get("event_type") for row in calls]
            == ["started", "failed"]
            and calls[-1].get("error_type")
            == "VigilLiveDependencyError"
            and call_status["open_attempts"] == 0
            and call_status["completed_calls"] == 0
            and call_status["failed_calls"] == 1
        ),
        "no_formal_record": not records,
        "no_evidence_sidecar": not evidence,
        "same_work_key": (
            bool(attempts)
            and bool(calls)
            and attempts[0].get("work_key") == calls[0].get("work_key")
        ),
        "no_automatic_retry": all(
            row.get("automatic_retry") is False for row in calls
        ),
    }
    if not all(checks.values()):
        failed = sorted(
            name for name, passed in checks.items() if not passed
        )
        raise GeminiFallbackAbortReviewError(
            f"failed Gemini v1 abort checks: {failed}"
        )

    locked = [
        _file_lock(controller.DEFAULT_CANDIDATE),
        _file_lock(controller.DEFAULT_CANARY_ADMISSION),
        _file_lock(attempt_path),
        _file_lock(call_path),
        _file_lock(Path(__file__)),
    ]
    core = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": GENERATED_AT,
        "status": "aborted_result_ineligible_new_version_required",
        "run_id": candidate["scope"]["run_id"],
        "matrix_identity": candidate["scope"]["matrix_identity"],
        "candidate_manifest_sha256": candidate["manifest_sha256"],
        "canary_admission_manifest_sha256": admission["manifest_sha256"],
        "stop_reason": "vigil_gemini_constraint_generation_fell_back",
        "technical_checks": checks,
        "trace_summary": {
            "attempt_events": len(attempts),
            "open_work_item_attempts": 1,
            "provider_call_events": len(calls),
            "provider_calls_completed": 0,
            "provider_calls_failed": 1,
            "official_response_identity_archived": False,
            "experiment_records": 0,
            "evidence_sidecar_entries": 0,
            "network_attempt_upper_bound": 1,
        },
        "evidence_boundary": {
            "prompts_read": 0,
            "response_text_read": 0,
            "credentials_read": False,
            "scientific_outcomes_read": 0,
            "external_effects_enabled": False,
            "provider_tools_enabled": False,
        },
        "disposition": {
            "run_resumable": False,
            "result_eligible": False,
            "orphan_call_promotable": False,
            "new_run_and_matrix_identity_required": True,
            "structural_condition_reclassified_as_diagnostic_only": True,
        },
        "locked_evidence": locked,
        "output_root": _display_path(root),
    }
    return {
        **core,
        "manifest_sha256": sha256_canonical_json(core),
    }


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(
            value,
            stream,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def write_review(path: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    value = build_review()
    _write_json(path, value)
    return value


def verify_review(path: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    observed = _load_json(path)
    if (
        observed.get("manifest_sha256")
        != sha256_canonical_json(_without_manifest(observed))
        or observed != build_review()
    ):
        raise GeminiFallbackAbortReviewError(
            "Gemini fallback v1 abort review drift"
        )
    return observed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    value = write_review() if args.write else verify_review()
    print(
        json.dumps(
            {
                "status": value["status"],
                "run_id": value["run_id"],
                "result_eligible": value["disposition"]["result_eligible"],
                "provider_calls_failed": value["trace_summary"][
                    "provider_calls_failed"
                ],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
