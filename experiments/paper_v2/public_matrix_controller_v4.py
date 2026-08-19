"""Freeze and qualify the execution-identity-aware public candidate v4.

Public-v4 supersedes the permanently aborted Public-v3 run.  It binds the
Public-v3 abort review and the evaluator-level v4 M3 qualification into fresh
run and execution identities.  This module is offline-only.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator, FormatChecker

from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.public_abort_review_v3 import (
    DEFAULT_OUTPUT as DEFAULT_V3_ABORT_REVIEW,
    verify_abort_review as verify_v3_abort_review,
)
from experiments.paper_v2.public_m3_live_dependency_v4 import (
    DEFAULT_OUTPUT as DEFAULT_M3_QUALIFICATION,
    verify_public_m3_resolver_qualification,
)
from experiments.paper_v2.public_matrix_plan_v1 import (
    DEFAULT_MANIFEST,
    DEFAULT_PLAN,
    verify_public_execution_plan,
)
from experiments.paper_v2.public_provider_budget_v1 import (
    PublicBudgetPolicyError,
    load_public_policy,
    validate_public_policy,
)
import experiments.paper_v2.public_matrix_controller_v3 as v3


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_ROOT = PROJECT_ROOT / "protocols/paper_upgrade_v2"
DEFAULT_SCHEMA = (
    PROJECT_ROOT / "schemas/paper_v2/public_matrix_candidate_v4.schema.json"
)
DEFAULT_ADMISSION_SCHEMA = (
    PROJECT_ROOT / "schemas/paper_v2/public_matrix_admission_v4.schema.json"
)
DEFAULT_QUALIFICATION = (
    PROTOCOL_ROOT / "public_matrix_controller_qualification_v4.json"
)
DEFAULT_CANDIDATE = PROTOCOL_ROOT / "public_matrix_candidate_v4.json"
QUALIFIED_AT = "2026-07-29T02:00:00+08:00"
CANDIDATE_AT = "2026-07-29T02:00:00+08:00"
SCHEMA_VERSION = "m3-paper-v2-public-matrix-candidate-4.0"
CANDIDATE_STATUS = "candidate_pending_exact_command_canary_approval"


class PublicMatrixControllerV4Error(ValueError):
    """Raised when the Public-v4 candidate cannot fail closed."""


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PublicMatrixControllerV4Error(f"{path}: expected an object")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _display_path(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()


def _artifact_lock(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise PublicMatrixControllerV4Error(
            f"missing Public-v4 artifact: {path}"
        )
    return {
        "path": _display_path(path),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def _manifest_sha(value: Mapping[str, Any]) -> str:
    return sha256_canonical_json(
        {key: child for key, child in value.items() if key != "manifest_sha256"}
    )


def _source_candidate() -> dict[str, Any]:
    return v3.validate_candidate(_load_json(v3.DEFAULT_CANDIDATE))


def build_controller_qualification() -> dict[str, Any]:
    manifest = verify_public_execution_plan()
    source_candidate = _source_candidate()
    public_m3 = verify_public_m3_resolver_qualification()
    abort_review = verify_v3_abort_review()
    rows = v3.v2._load_jsonl(DEFAULT_PLAN)
    if len(rows) != 6873:
        raise PublicMatrixControllerV4Error(
            "public plan record count drift"
        )
    expanded = copy.deepcopy(load_public_policy())
    expanded["deepseek"]["incremental_hard_limit_cny"] = 30.0
    expanded_budget_rejected = False
    try:
        validate_public_policy(expanded)
    except PublicBudgetPolicyError:
        expanded_budget_rejected = True
    if not expanded_budget_rejected:
        raise PublicMatrixControllerV4Error(
            "expanded public budget was not rejected"
        )
    probes = public_m3["qualification_probes"]
    if (
        len(probes) != 4
        or not all(
            probe["binding_digest_matches_material"]
            and probe["evaluator_completed"]
            for probe in probes
        )
    ):
        raise PublicMatrixControllerV4Error(
            "Public-v4 evaluator qualification drift"
        )
    return {
        "schema_version": (
            "m3-paper-v2-public-matrix-controller-qualification-4.0"
        ),
        "generated_at": QUALIFIED_AT,
        "status": "public_v4_controller_qualified_offline",
        "plan": {
            "records": len(rows),
            "sha256": _sha256_file(DEFAULT_PLAN),
            "manifest_sha256": _sha256_file(DEFAULT_MANIFEST),
            "primary_records": manifest["counts"]["by_model_role"][
                "primary"
            ],
            "second_records": manifest["counts"]["by_model_role"]["second"],
        },
        "condition_shells": v3.v2._condition_qualification(rows),
        "public_m3_evaluator": {
            "qualification_sha256": _sha256_file(
                DEFAULT_M3_QUALIFICATION
            ),
            "qualification_probes": len(probes),
            "all_binding_digests_match": True,
            "all_evaluator_probes_completed": True,
            "public_work_items": public_m3["public_m3_work_items"],
            "private_selection_bindings": public_m3[
                "private_selection_bindings"
            ],
            "network_calls_made": 0,
        },
        "public_v3_abort": {
            "review_sha256": abort_review["manifest_sha256"],
            "record_count": abort_review["operational_summary"][
                "record_count"
            ],
            "provider_calls_completed": abort_review[
                "operational_summary"
            ]["provider_calls_completed"],
            "run_resumable": abort_review["evidence_boundary"][
                "run_resumable"
            ],
            "result_admission_authorized": abort_review[
                "evidence_boundary"
            ]["result_admission_authorized"],
            "binding_digest_matches_active_material": abort_review[
                "root_cause"
            ]["binding_digest_matches_active_material"],
        },
        "source_candidate": {
            "manifest_sha256": source_candidate["manifest_sha256"],
            "execution_authorized": source_candidate["authorization"][
                "canary_execution_authorized"
            ],
        },
        "provider_trace": v3.v2._provider_trace_qualification(),
        "negative_coverage": {
            "expanded_budget_rejected": expanded_budget_rejected,
            "existing_trace_path_rejected": True,
            "model_identity_mismatch_rejected_by_client": True,
            "forbidden_online_evaluator_fields_rejected": True,
            "v3_active_identity_mismatch_reproduced": True,
            "v4_active_identity_evaluator_completed": True,
            "automatic_retry": 0,
        },
        "evidence_boundary": {
            "credentials_read": False,
            "network_calls_made": 0,
            "model_calls_made": 0,
            "experiment_records_persisted": 0,
            "formal_results_created": 0,
            "scientific_outcomes_accessed": False,
        },
    }


def write_controller_qualification(
    path: Path = DEFAULT_QUALIFICATION,
) -> dict[str, Any]:
    value = build_controller_qualification()
    _write_json(path, value)
    return value


def verify_controller_qualification(
    path: Path = DEFAULT_QUALIFICATION,
) -> dict[str, Any]:
    observed = _load_json(path)
    expected = build_controller_qualification()
    if observed != expected:
        raise PublicMatrixControllerV4Error(
            "Public-v4 controller qualification drift"
        )
    return observed


def _candidate_artifacts() -> list[Path]:
    return [
        Path(__file__),
        PROJECT_ROOT / "experiments/paper_v2/public_live_controller_v4.py",
        PROJECT_ROOT
        / "experiments/paper_v2/public_m3_live_dependency_v4.py",
        PROJECT_ROOT / "experiments/paper_v2/public_abort_review_v3.py",
        DEFAULT_SCHEMA,
        DEFAULT_ADMISSION_SCHEMA,
        DEFAULT_QUALIFICATION,
        v3.DEFAULT_CANDIDATE,
        DEFAULT_V3_ABORT_REVIEW,
        DEFAULT_M3_QUALIFICATION,
        DEFAULT_PLAN,
        DEFAULT_MANIFEST,
    ]


def build_candidate() -> dict[str, Any]:
    qualification = verify_controller_qualification()
    source_candidate = _source_candidate()
    manifest = verify_public_execution_plan()
    policy = load_public_policy()
    abort_review = verify_v3_abort_review()
    m3_qualification_sha256 = _sha256_file(DEFAULT_M3_QUALIFICATION)
    model_roles = copy.deepcopy(source_candidate["scope"]["model_roles"])
    for role in ("primary", "second"):
        source_identity = model_roles[role]["execution_identity"]
        model_roles[role]["public_v3_execution_identity"] = source_identity
        model_roles[role]["source_execution_identity"] = source_identity
        model_roles[role]["execution_identity"] = sha256_canonical_json(
            {
                "schema_version": (
                    "m3-paper-v2-public-execution-identity-4.0"
                ),
                "model_role": role,
                "source_candidate_manifest_sha256": source_candidate[
                    "manifest_sha256"
                ],
                "source_execution_identity": source_identity,
                "public_m3_evaluator_qualification_sha256": (
                    m3_qualification_sha256
                ),
                "public_v3_abort_review_sha256": abort_review[
                    "manifest_sha256"
                ],
            }
        )
    scope = {
        "records": 6873,
        "model_roles": model_roles,
        "canary": {
            **manifest["canary"],
            "selection_is_outcome_blind": True,
            "records_remain_in_formal_matrix": True,
        },
        "budget": {
            "incremental_hard_limit_cny": policy["deepseek"][
                "incremental_hard_limit_cny"
            ],
            "untouched_reserve_cny": policy["deepseek"][
                "untouched_reserve_cny"
            ],
            "role_hard_limits_cny": {
                role: policy["deepseek"]["roles"][role][
                    "role_hard_limit_cny"
                ]
                for role in ("primary", "second")
            },
            "automatic_retries": 0,
            "cost_ledger": "append_only_cache_aware_actual_usage",
        },
        "execution_order": [
            "primary_canary",
            "primary_matrix",
            "second_canary",
            "second_matrix",
        ],
        "provider": {
            "max_tokens": 512,
            "timeout_seconds": 120.0,
            "execution_concurrency": 1,
            "provider_managed_tools_enabled": False,
            "external_effects_enabled": False,
        },
        "runs": {
            role: {
                "run_id": f"paper-v2-public-v4-{role}-20260729",
                "output_root": (
                    "outputs/paper_upgrade_v2/formal_public/deepseek/"
                    f"public-v4-{role}-"
                    f"{model_roles[role]['execution_identity']}"
                ),
            }
            for role in ("primary", "second")
        },
        "remediation": {
            "source_candidate_manifest_sha256": source_candidate[
                "manifest_sha256"
            ],
            "source_run_resumable": False,
            "source_abort_review_sha256": abort_review["manifest_sha256"],
            "public_m3_evaluator_qualification_sha256": (
                m3_qualification_sha256
            ),
            "active_execution_identity_injected_into_resolver": True,
            "actual_evaluator_path_qualified": True,
            "fresh_execution_identity_required": True,
            "source_work_keys_retained_under_fresh_run_identity": True,
        },
        "failure_policy": {
            "first_http_429": "pause",
            "first_identity_mismatch": "pause",
            "first_unknown_runner_failure": "pause",
            "budget_ceiling": "pause_before_next_request",
            "completed_terminal_items_retried": False,
            "pending_only_resume_requires_new_identity": True,
            "all_failures_remain_in_intention_to_treat": True,
        },
        "qualification": {
            "path": _display_path(DEFAULT_QUALIFICATION),
            "sha256": _sha256_file(DEFAULT_QUALIFICATION),
            "qualified_pairs": qualification["condition_shells"][
                "qualified_pairs"
            ],
            "public_m3_evaluator_probes": qualification[
                "public_m3_evaluator"
            ]["qualification_probes"],
        },
        "scientific_boundary": {
            "canary_review_is_outcome_blind": True,
            "result_admission_is_separate": True,
            "flash_claim": "cross_model_not_cross_provider",
            "partial_v3_records_admissible": False,
        },
    }
    core = {
        "schema_version": SCHEMA_VERSION,
        "artifact_role": "owner_review_candidate",
        "generated_at": CANDIDATE_AT,
        "status": CANDIDATE_STATUS,
        "scope": scope,
        "artifact_locks": [
            _artifact_lock(path)
            for path in sorted(
                set(_candidate_artifacts()),
                key=lambda item: _display_path(item),
            )
        ],
        "authorization": {
            "candidate_only": True,
            "canary_execution_authorized": False,
            "matrix_continuation_authorized": False,
            "result_admission_authorized": False,
            "active_admission_present": False,
        },
        "evidence_boundary": {
            "credentials_read_while_building": False,
            "network_calls_while_building": 0,
            "model_calls_while_building": 0,
            "formal_results_created": 0,
            "candidate_is_executable": False,
            "scientific_outcomes_accessed": False,
        },
        "scope_sha256": sha256_canonical_json(scope),
    }
    candidate = {**core, "manifest_sha256": sha256_canonical_json(core)}
    return validate_candidate(candidate)


def validate_candidate(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise PublicMatrixControllerV4Error(
            "Public-v4 candidate must be an object"
        )
    Draft202012Validator(
        _load_json(DEFAULT_SCHEMA),
        format_checker=FormatChecker(),
    ).validate(dict(value))
    if (
        value["scope_sha256"] != sha256_canonical_json(value["scope"])
        or value["manifest_sha256"] != _manifest_sha(value)
    ):
        raise PublicMatrixControllerV4Error(
            "Public-v4 candidate digest drift"
        )
    locks = value["artifact_locks"]
    if len({item["path"] for item in locks}) != len(locks):
        raise PublicMatrixControllerV4Error(
            "duplicate Public-v4 artifact lock"
        )
    for item in locks:
        path = (PROJECT_ROOT / item["path"]).resolve()
        try:
            path.relative_to(PROJECT_ROOT.resolve())
        except ValueError as exc:
            raise PublicMatrixControllerV4Error(
                "Public-v4 artifact lock escapes the project root"
            ) from exc
        if (
            not path.is_file()
            or path.stat().st_size != item["bytes"]
            or _sha256_file(path) != item["sha256"]
        ):
            raise PublicMatrixControllerV4Error(
                f"Public-v4 artifact lock drift: {item['path']}"
            )
    return copy.deepcopy(dict(value))


def write_candidate(path: Path = DEFAULT_CANDIDATE) -> dict[str, Any]:
    value = build_candidate()
    _write_json(path, value)
    return value


def verify_candidate(path: Path = DEFAULT_CANDIDATE) -> dict[str, Any]:
    observed = validate_candidate(_load_json(path))
    expected = build_candidate()
    if observed != expected:
        raise PublicMatrixControllerV4Error(
            "Public-v4 candidate drift"
        )
    return observed


def verify_stage_a() -> dict[str, Any]:
    qualification = verify_controller_qualification()
    candidate = verify_candidate()
    return {
        "status": "public_v4_stage_a_offline_qualified_candidate_frozen",
        "records": candidate["scope"]["records"],
        "qualified_pairs": qualification["condition_shells"][
            "qualified_pairs"
        ],
        "public_m3_evaluator_probes": qualification[
            "public_m3_evaluator"
        ]["qualification_probes"],
        "model_roles": sorted(qualification["provider_trace"]),
        "candidate_sha256": candidate["manifest_sha256"],
        "execution_authorized": False,
        "network_calls_made": 0,
        "formal_results_created": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write-qualification", action="store_true")
    action.add_argument("--verify-qualification", action="store_true")
    action.add_argument("--write-candidate", action="store_true")
    action.add_argument("--verify-candidate", action="store_true")
    action.add_argument("--verify-stage-a", action="store_true")
    args = parser.parse_args()
    if args.write_qualification:
        value = write_controller_qualification()
    elif args.verify_qualification:
        value = verify_controller_qualification()
    elif args.write_candidate:
        value = write_candidate()
    elif args.verify_candidate:
        value = verify_candidate()
    else:
        value = verify_stage_a()
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
