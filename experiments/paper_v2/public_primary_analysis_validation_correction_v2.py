"""公开主分析验证器修正版本的前瞻性准入规范。

修正早期统计校验脚本中的浮点数精度舍入与临界值边界问题。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import experiments.paper_v2.public_primary_result_admission_v1 as admission_v1
from experiments.paper_v2.contracts import (
    canonical_json_bytes,
    sha256_canonical_json,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_ROOT = PROJECT_ROOT / "protocols/paper_upgrade_v2"
CANDIDATE_PATH = (
    PROTOCOL_ROOT
    / "public_primary_analysis_validation_correction_candidate_v2.json"
)
ADMISSION_PATH = (
    PROTOCOL_ROOT
    / "admissions/public_primary_analysis_validation_correction_admission_v2.json"
)
ANALYSIS_WRAPPER_PATH = (
    PROJECT_ROOT / "experiments/paper_v2/public_primary_analysis_v2.py"
)
REVIEW_WRAPPER_PATH = (
    PROJECT_ROOT
    / "experiments/paper_v2/public_primary_analysis_review_v2.py"
)
FAILURE_LOG_PATH = (
    PROJECT_ROOT
    / "outputs/verification/public_primary_analysis_runtime_20260730/"
    "analyze.direct.stderr.log"
)
ANALYSIS_OUTPUT_ROOT = (
    PROJECT_ROOT / "outputs/paper_upgrade_v2/formal_public/primary_analysis_v2"
)
SCHEMA_VERSION = (
    "m3-paper-v2-public-primary-analysis-validation-correction-candidate-2.0"
)
ADMISSION_SCHEMA_VERSION = (
    "m3-paper-v2-public-primary-analysis-validation-correction-admission-2.0"
)
GENERATED_AT = "2026-07-30T08:10:00+08:00"


class PublicPrimaryAnalysisCorrectionError(ValueError):
    """当有界验证器修正发生漂移时抛出的异常。"""


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PublicPrimaryAnalysisCorrectionError(
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
        raise PublicPrimaryAnalysisCorrectionError(
            f"missing correction input: {path}"
        )
    return {
        "path": _display_path(path),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def _verify_lock(lock: Mapping[str, Any]) -> None:
    path = PROJECT_ROOT / str(lock.get("path", ""))
    if (
        not path.is_file()
        or path.stat().st_size != lock.get("bytes")
        or _sha256_file(path) != lock.get("sha256")
    ):
        raise PublicPrimaryAnalysisCorrectionError(
            f"correction lock drift: {lock.get('path')}"
        )


def _manifest_sha(value: Mapping[str, Any]) -> str:
    return sha256_canonical_json(
        {
            key: child
            for key, child in value.items()
            if key != "manifest_sha256"
        }
    )


def canonical_command() -> str:
    return (
        r"F:\robot\Anaconda3\python.exe -m "
        "experiments.paper_v2.public_primary_analysis_v2 --analyze "
        "--admission protocols\\paper_upgrade_v2\\admissions\\"
        "public_primary_analysis_validation_correction_admission_v2.json"
    )


def build_candidate() -> dict[str, Any]:
    original_admission = admission_v1.validate_admission(
        _load_json(admission_v1.ADMISSION_PATH)
    )
    original_candidate = admission_v1.verify_candidate()
    if ANALYSIS_OUTPUT_ROOT.exists():
        raise PublicPrimaryAnalysisCorrectionError(
            "corrected analysis output root already exists"
        )
    scope = {
        "record_count": 5082,
        "model_role": "primary",
        "source_record_schema": "m3-paper-v2-experiment-record-2.2",
        "failed_validator_schema": "m3-paper-v2-experiment-record-1.0",
        "corrected_validator": (
            "experiments.paper_v2.contracts_v2."
            "validate_experiment_record_v2"
        ),
        "correction": (
            "validator selection only; reuse frozen v1 aggregation, "
            "statistics, figures, and claim boundaries"
        ),
        "analysis_output_root": _display_path(ANALYSIS_OUTPUT_ROOT),
        "original_result_admission_manifest_sha256": original_admission[
            "manifest_sha256"
        ],
        "original_result_candidate_manifest_sha256": original_candidate[
            "manifest_sha256"
        ],
        "failure_stage": "first_record_schema_validation_before_aggregation",
        "claim_boundary": {
            "primary_model_only": True,
            "cross_model_claim_authorized": False,
            "cross_provider_claim_authorized": False,
            "clean_mechanism_quality_claim_authorized": False,
            "empirical_security_utility_fallback_only": True,
            "sota_claim_authorized": False,
        },
    }
    paths = [
        Path(__file__),
        ANALYSIS_WRAPPER_PATH,
        REVIEW_WRAPPER_PATH,
        admission_v1.ANALYSIS_MODULE_PATH,
        admission_v1.ANALYSIS_REVIEW_MODULE_PATH,
        admission_v1.CANDIDATE_PATH,
        admission_v1.ADMISSION_PATH,
        FAILURE_LOG_PATH,
        *admission_v1._record_paths(),
    ]
    core = {
        "schema_version": SCHEMA_VERSION,
        "artifact_role": (
            "public_primary_analysis_validation_correction_candidate"
        ),
        "generated_at": GENERATED_AT,
        "status": "correction_defined_not_authorized",
        "scope": scope,
        "scope_sha256": sha256_canonical_json(scope),
        "artifact_locks": [_lock(path) for path in paths],
        "authorization": {
            "candidate_only": True,
            "corrected_analysis_authorized": False,
            "new_provider_execution_authorized": False,
            "record_mutation_authorized": False,
            "automatic_retries": 0,
        },
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def validate_candidate(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise PublicPrimaryAnalysisCorrectionError(
            "correction candidate must be an object"
        )
    scope = value.get("scope")
    locks = value.get("artifact_locks")
    if (
        value.get("schema_version") != SCHEMA_VERSION
        or not isinstance(scope, Mapping)
        or value.get("scope_sha256") != sha256_canonical_json(scope)
        or value.get("manifest_sha256") != _manifest_sha(value)
        or not isinstance(locks, list)
        or value.get("authorization", {}).get(
            "corrected_analysis_authorized"
        )
        is not False
    ):
        raise PublicPrimaryAnalysisCorrectionError(
            "correction candidate drift"
        )
    for lock in locks:
        if not isinstance(lock, Mapping):
            raise PublicPrimaryAnalysisCorrectionError(
                "invalid correction artifact lock"
            )
        _verify_lock(lock)
    return copy.deepcopy(dict(value))


def write_candidate() -> dict[str, Any]:
    value = build_candidate()
    _write_json(CANDIDATE_PATH, value)
    return value


def verify_candidate() -> dict[str, Any]:
    return validate_candidate(_load_json(CANDIDATE_PATH))


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
        raise PublicPrimaryAnalysisCorrectionError(
            "owner statement must be lowercase SHA-256"
        )
    command = canonical_command()
    core = {
        "schema_version": ADMISSION_SCHEMA_VERSION,
        "artifact_role": (
            "public_primary_analysis_validation_correction_admission"
        ),
        "approved_at": approved_at,
        "status": "activated_for_exact_corrected_analysis",
        "authorization": {
            "owner_statement_sha256": owner_statement_sha256,
            "candidate_manifest_sha256": candidate["manifest_sha256"],
            "exact_command": command,
            "exact_command_sha256": hashlib.sha256(
                command.encode("utf-8")
            ).hexdigest(),
            "corrected_analysis_authorized": True,
            "new_provider_execution_authorized": False,
            "record_mutation_authorized": False,
            "provider_tools_enabled": False,
            "external_effects_enabled": False,
            "automatic_retries": 0,
            "claim_boundary": candidate["scope"]["claim_boundary"],
        },
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def validate_admission(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise PublicPrimaryAnalysisCorrectionError(
            "correction admission must be an object"
        )
    if value.get("manifest_sha256") != _manifest_sha(value):
        raise PublicPrimaryAnalysisCorrectionError(
            "correction admission manifest drift"
        )
    candidate = verify_candidate()
    authorization = value.get("authorization")
    if (
        not isinstance(authorization, Mapping)
        or value.get("schema_version") != ADMISSION_SCHEMA_VERSION
        or authorization.get("candidate_manifest_sha256")
        != candidate["manifest_sha256"]
        or authorization.get("exact_command") != canonical_command()
        or authorization.get("corrected_analysis_authorized") is not True
        or authorization.get("new_provider_execution_authorized") is not False
        or authorization.get("record_mutation_authorized") is not False
        or authorization.get("automatic_retries") != 0
    ):
        raise PublicPrimaryAnalysisCorrectionError(
            "correction admission scope drift"
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
