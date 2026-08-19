"""Separate scientific-result admission for the adaptive eight-task canary."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import experiments.paper_v2.adaptive_canary_analysis_v1 as analysis_v1
import experiments.paper_v2.adaptive_cost_canary_controller_v2 as canary_v2
import experiments.paper_v2.adaptive_recovery_technical_review_v1 as typed_review
from experiments.paper_v2.contracts import (
    canonical_json_bytes,
    sha256_canonical_json,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_ROOT = PROJECT_ROOT / "protocols/paper_upgrade_v2"
CANDIDATE_PATH = (
    PROTOCOL_ROOT / "adaptive_canary_result_candidate_v1.json"
)
ADMISSION_PATH = (
    PROTOCOL_ROOT / "admissions/adaptive_canary_result_admission_v1.json"
)
SCHEMA_VERSION = "m3-paper-v2-adaptive-result-candidate-1.0"
ADMISSION_SCHEMA_VERSION = "m3-paper-v2-adaptive-result-admission-1.0"
GENERATED_AT = "2026-07-30T03:07:00+08:00"


class AdaptiveCanaryResultAdmissionError(ValueError):
    """Raised when adaptive scientific access is not exactly admitted."""


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AdaptiveCanaryResultAdmissionError(
            f"{path}: expected an object"
        )
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value) + b"\n")


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
        raise AdaptiveCanaryResultAdmissionError(
            f"missing adaptive result artifact: {path}"
        )
    return {
        "path": _display_path(path),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def _verify_lock(lock: Mapping[str, Any]) -> None:
    path = (PROJECT_ROOT / str(lock["path"])).resolve()
    try:
        path.relative_to(PROJECT_ROOT.resolve())
    except ValueError as exc:
        raise AdaptiveCanaryResultAdmissionError(
            "adaptive result lock escapes project"
        ) from exc
    if (
        not path.is_file()
        or path.stat().st_size != lock["bytes"]
        or _sha256_file(path) != lock["sha256"]
    ):
        raise AdaptiveCanaryResultAdmissionError(
            f"adaptive result lock drift: {lock['path']}"
        )


def _manifest_sha(value: Mapping[str, Any]) -> str:
    return sha256_canonical_json(
        {
            key: child
            for key, child in value.items()
            if key != "manifest_sha256"
        }
    )


def build_candidate() -> dict[str, Any]:
    technical = typed_review.verify_review()
    permit = canary_v2.authorize_canary(
        admission_path=canary_v2.ADMISSION_PATH
    )
    if analysis_v1.DEFAULT_OUTPUT.exists():
        raise AdaptiveCanaryResultAdmissionError(
            "adaptive analysis output already exists"
        )
    paths = [
        Path(__file__),
        Path(analysis_v1.__file__),
        typed_review.DEFAULT_OUTPUT,
        permit.query_ledger_path,
        permit.budget_ledger_path,
        permit.output_root / "continuation_task_events_v3.jsonl",
    ]
    paths.extend(sorted(permit.checkpoint_root.glob("*.json")))
    scope = {
        "run_id": permit.run_id,
        "execution_identity": permit.execution_identity,
        "model_id": "deepseek-v4-pro",
        "condition_id": "m3_full",
        "authorization_regime": "auto_compiled",
        "task_count": technical["expected_task_count"],
        "terminal_query_count": technical["terminal_query_count"],
        "diagnostic_query_count": technical["diagnostic_query_count"],
        "technical_review_manifest_sha256": technical[
            "manifest_sha256"
        ],
        "analysis_output_root": _display_path(analysis_v1.DEFAULT_OUTPUT),
        "claim_boundary": {
            "exploratory_cost_canary_only": True,
            "full_adaptive_panel": False,
            "second_model_adaptive_panel": False,
            "sota_claim_authorized": False,
        },
    }
    core = {
        "schema_version": SCHEMA_VERSION,
        "artifact_role": "adaptive_scientific_result_access_candidate",
        "generated_at": GENERATED_AT,
        "status": "technical_gate_passed_result_access_not_authorized",
        "scope": scope,
        "scope_sha256": sha256_canonical_json(scope),
        "artifact_locks": [_lock(path) for path in paths],
        "authorization": {
            "candidate_only": True,
            "scientific_outcome_access_authorized": False,
            "new_provider_execution_authorized": False,
            "formal_adaptive_continuation_authorized": False,
        },
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def validate_candidate(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise AdaptiveCanaryResultAdmissionError(
            "adaptive result candidate must be an object"
        )
    scope = value.get("scope")
    if (
        not isinstance(scope, Mapping)
        or value.get("schema_version") != SCHEMA_VERSION
        or value.get("manifest_sha256") != _manifest_sha(value)
        or value.get("scope_sha256") != sha256_canonical_json(scope)
        or value.get("authorization", {}).get(
            "scientific_outcome_access_authorized"
        )
        is not False
    ):
        raise AdaptiveCanaryResultAdmissionError(
            "adaptive result candidate drift"
        )
    for lock in value.get("artifact_locks", []):
        _verify_lock(lock)
    return copy.deepcopy(dict(value))


def write_candidate() -> dict[str, Any]:
    value = build_candidate()
    _write_json(CANDIDATE_PATH, value)
    return value


def verify_candidate() -> dict[str, Any]:
    return validate_candidate(_load_json(CANDIDATE_PATH))


def canonical_command() -> str:
    return (
        r"F:\robot\Anaconda3\python.exe -m "
        "experiments.paper_v2.adaptive_canary_analysis_v1 --analyze "
        "--admission protocols\\paper_upgrade_v2\\admissions\\"
        "adaptive_canary_result_admission_v1.json"
    )


def build_admission(
    *,
    owner_statement_sha256: str,
    approved_at: str,
) -> dict[str, Any]:
    candidate = verify_candidate()
    if (
        len(owner_statement_sha256) != 64
        or any(
            char not in "0123456789abcdef"
            for char in owner_statement_sha256
        )
    ):
        raise AdaptiveCanaryResultAdmissionError(
            "owner statement must be lowercase SHA-256"
        )
    command = canonical_command()
    core = {
        "schema_version": ADMISSION_SCHEMA_VERSION,
        "artifact_role": "adaptive_scientific_result_access_admission",
        "approved_at": approved_at,
        "status": "activated_for_exact_adaptive_canary_analysis",
        "authorization": {
            "owner_statement_sha256": owner_statement_sha256,
            "candidate_manifest_sha256": candidate["manifest_sha256"],
            "exact_command": command,
            "exact_command_sha256": hashlib.sha256(
                command.encode("utf-8")
            ).hexdigest(),
            "scientific_outcome_access_authorized": True,
            "new_provider_execution_authorized": False,
            "formal_adaptive_continuation_authorized": False,
            "provider_tools_enabled": False,
            "external_effects_enabled": False,
            "automatic_retries": 0,
            "claim_boundary": candidate["scope"]["claim_boundary"],
        },
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def validate_admission(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise AdaptiveCanaryResultAdmissionError(
            "adaptive result admission must be an object"
        )
    if value.get("manifest_sha256") != _manifest_sha(value):
        raise AdaptiveCanaryResultAdmissionError(
            "adaptive result admission manifest drift"
        )
    expected = build_admission(
        owner_statement_sha256=str(
            value.get("authorization", {}).get(
                "owner_statement_sha256",
                "",
            )
        ),
        approved_at=str(value.get("approved_at", "")),
    )
    if dict(value) != expected:
        raise AdaptiveCanaryResultAdmissionError(
            "adaptive result admission scope drift"
        )
    return copy.deepcopy(dict(value))


def write_admission(
    *,
    owner_statement_sha256: str,
    approved_at: str,
) -> dict[str, Any]:
    value = build_admission(
        owner_statement_sha256=owner_statement_sha256,
        approved_at=approved_at,
    )
    _write_json(ADMISSION_PATH, value)
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write-candidate", action="store_true")
    action.add_argument("--verify-candidate", action="store_true")
    action.add_argument("--write-admission", action="store_true")
    action.add_argument("--verify-admission", action="store_true")
    parser.add_argument("--owner-statement-sha256")
    parser.add_argument("--approved-at")
    args = parser.parse_args()
    if args.write_candidate:
        value = write_candidate()
    elif args.verify_candidate:
        value = verify_candidate()
    elif args.write_admission:
        if not args.owner_statement_sha256 or not args.approved_at:
            parser.error(
                "--write-admission requires --owner-statement-sha256 "
                "and --approved-at"
            )
        value = write_admission(
            owner_statement_sha256=args.owner_statement_sha256,
            approved_at=args.approved_at,
        )
    else:
        value = validate_admission(_load_json(ADMISSION_PATH))
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
