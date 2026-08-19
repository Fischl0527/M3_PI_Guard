"""Freeze and qualify the remediated paper-v2 public-matrix candidate v2.

This version preserves the 6,873-record result-blind plan but derives fresh
execution identities after Public-v1 exposed that the medium-plan AgentDojo
resolver could not resolve public work keys. The public-plan resolver and the
content-free Public-v1 abort review are qualified and hash-bound here.

No command in this module reads credentials or performs network I/O.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator, FormatChecker

from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.formal_condition_executors import (
    FORBIDDEN_RUNTIME_CONTEXT_FIELDS,
    _QualificationEvaluator,
    _QualificationRuntime,
    build_condition_dispatcher,
)
from experiments.paper_v2.medium_runtime import assemble_experiment_record
from experiments.paper_v2.official_provider_executor import (
    HTTPResponseEnvelope,
)
from experiments.paper_v2.provider_trace_bundle import (
    ProviderTraceBundleError,
)
import experiments.paper_v2.provider_trace_bundle as provider_trace_bundle
from experiments.paper_v2.public_deepseek_client_v1 import (
    PublicDeepSeekJsonOfficialClient,
)
from experiments.paper_v2.public_abort_review_v1 import (
    DEFAULT_OUTPUT as DEFAULT_ABORT_REVIEW,
    verify_abort_review,
)
from experiments.paper_v2.public_agentdojo_live_dependency_v2 import (
    DEFAULT_OUTPUT as DEFAULT_PUBLIC_AGENTDOJO_QUALIFICATION,
    verify_public_resolver_qualification,
)
from experiments.paper_v2.public_matrix_plan_v1 import (
    DEFAULT_FREEZE,
    DEFAULT_MANIFEST,
    DEFAULT_PLAN,
    hydrate_public_work_item,
    verify_public_execution_plan,
)
from experiments.paper_v2.public_provider_budget_v1 import (
    DEFAULT_POLICY,
    PublicBudgetPolicyError,
    PublicProviderBudgetState,
    build_role_policy,
    load_public_policy,
    validate_public_policy,
)
from experiments.paper_v2.public_provider_trace_v1 import (
    PublicDeepSeekJsonTracedProviderClient,
    validate_public_trace_bundle,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_ROOT = PROJECT_ROOT / "protocols/paper_upgrade_v2"
DEFAULT_SCHEMA = (
    PROJECT_ROOT / "schemas/paper_v2/public_matrix_candidate_v2.schema.json"
)
DEFAULT_QUALIFICATION = (
    PROTOCOL_ROOT / "public_matrix_controller_qualification_v2.json"
)
DEFAULT_CANDIDATE = PROTOCOL_ROOT / "public_matrix_candidate_v2.json"
DEFAULT_TRACE_ACTIVATION = provider_trace_bundle.DEFAULT_ACTIVATION
DEFAULT_PROVIDER_SAFETY_POLICY = (
    PROTOCOL_ROOT / "provider_safety_policy_v1.json"
)
QUALIFIED_AT = "2026-07-28T08:30:00+08:00"
CANDIDATE_AT = "2026-07-28T08:30:00+08:00"
SCHEMA_VERSION = "m3-paper-v2-public-matrix-candidate-2.0"
CANDIDATE_STATUS = "candidate_pending_exact_command_canary_approval"
EXPECTED_PAIRS = 18


class PublicMatrixControllerError(ValueError):
    """Raised when the public execution candidate cannot fail closed."""


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PublicMatrixControllerError(f"{path}: expected an object")
    return value


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not line.strip():
            raise PublicMatrixControllerError(f"{path}:{number}: blank row")
        value = json.loads(line)
        if not isinstance(value, dict):
            raise PublicMatrixControllerError(
                f"{path}:{number}: expected an object"
            )
        rows.append(value)
    return rows


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
        raise PublicMatrixControllerError(f"missing public artifact: {path}")
    return {
        "path": _display_path(path),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def _manifest_sha(value: Mapping[str, Any]) -> str:
    return sha256_canonical_json(
        {key: child for key, child in value.items() if key != "manifest_sha256"}
    )


def _qualification_transport(
    endpoint: str,
    headers: Mapping[str, str],
    payload: Mapping[str, Any],
    timeout: float,
) -> HTTPResponseEnvelope:
    del endpoint, headers, timeout
    model_id = str(payload["model"])
    return HTTPResponseEnvelope(
        status_code=200,
        headers={"x-request-id": f"public-{model_id}-qualification-request"},
        body={
            "id": f"public-{model_id}-qualification-response",
            "model": model_id,
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": (
                            '{"tool":"final","arguments":'
                            '{"answer":"QUALIFIED"}}'
                        ),
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 20,
                "total_tokens": 120,
                "prompt_cache_hit_tokens": 80,
                "prompt_cache_miss_tokens": 20,
            },
        },
    )


def _as_official_qualification_receipt(
    receipt: Mapping[str, Any],
) -> dict[str, Any]:
    value = copy.deepcopy(dict(receipt))
    evidence = value["evidence"]
    evidence["transport_kind"] = "official_network"
    evidence["identity_verified"] = True
    evidence["request_trace_complete"] = True
    evidence["evidence_level"] = (
        "official_exact_model_with_request_and_response_ids"
    )
    evidence["requested_at"] = QUALIFIED_AT
    evidence["model_latency_ms"] = 0.0
    value["evidence_sha256"] = sha256_canonical_json(evidence)
    return value


def _provider_trace_qualification() -> dict[str, Any]:
    public_policy = load_public_policy()
    results: dict[str, Any] = {}
    with tempfile.TemporaryDirectory(
        prefix="m3-public-controller-qualification-"
    ) as directory:
        root = Path(directory)
        for role in ("primary", "second"):
            role_policy = build_role_policy(public_policy, role)
            client = PublicDeepSeekJsonOfficialClient(
                provider_id="deepseek",
                api_key="offline-public-controller-qualification-key",
                content_class="public_benchmark_case",
                budget_state=PublicProviderBudgetState(
                    "deepseek",
                    role_policy,
                ),
                policy=role_policy,
                model_role=role,
                max_tokens=512,
                transport=_qualification_transport,
            )
            trace_path = root / f"{role}.jsonl"
            traced = PublicDeepSeekJsonTracedProviderClient(
                client,
                execution_identity=f"offline-public-{role}-identity",
                work_key=f"offline-public-{role}-work",
                trace_path=trace_path,
                recorded_at=lambda: QUALIFIED_AT,
                receipt_adapter=_as_official_qualification_receipt,
            )
            traced.complete(
                [
                    {
                        "role": "user",
                        "content": "offline public controller qualification",
                    }
                ]
            )
            bundle = traced.build_bundle()
            validate_public_trace_bundle(
                bundle,
                role_policy=role_policy,
            )
            existing_rejected = False
            try:
                PublicDeepSeekJsonTracedProviderClient(
                    client,
                    execution_identity=f"offline-public-{role}-identity",
                    work_key=f"offline-public-{role}-work",
                    trace_path=trace_path,
                    recorded_at=lambda: QUALIFIED_AT,
                )
            except ProviderTraceBundleError:
                existing_rejected = True
            if not existing_rejected:
                raise PublicMatrixControllerError(
                    "existing public trace was not rejected"
                )
            results[role] = {
                "model_id": client.model,
                "endpoint": client.endpoint,
                "thinking_mode": client.last_request_metadata[
                    "thinking_mode"
                ],
                "response_format": client.last_request_metadata[
                    "response_format"
                ],
                "provider_tools_declared": client.last_request_metadata[
                    "provider_tools_declared"
                ],
                "bundle_sha256": bundle["bundle_sha256"],
                "request_count": bundle["request_count"],
                "completed_request_count": bundle[
                    "completed_request_count"
                ],
                "existing_trace_rejected": existing_rejected,
            }
    return results


def _condition_qualification(
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    representatives: dict[tuple[str, str, str], dict[str, Any]] = {}
    for item in rows:
        key = (
            str(item["model_role"]),
            str(item["benchmark"]),
            str(item["condition_id"]),
        )
        representatives.setdefault(key, item)
    expected = {
        ("primary", benchmark, condition)
        for benchmark in ("agentdojo-v1", "m3-v2")
        for condition in (
            "no_defense",
            "safe_prompt_or_spotlighting",
            "promptguard_detector_only",
            "strongest_peer_reviewed_structural_baseline",
            "m3_policy_only",
            "m3_full",
        )
    } | {
        ("second", benchmark, condition)
        for benchmark in ("agentdojo-v1", "m3-v2")
        for condition in (
            "strongest_peer_reviewed_structural_baseline",
            "m3_policy_only",
            "m3_full",
        )
    }
    if set(representatives) != expected or len(expected) != EXPECTED_PAIRS:
        raise PublicMatrixControllerError(
            "public role/benchmark/condition coverage drift"
        )
    runtime = _QualificationRuntime()
    evaluator = _QualificationEvaluator()
    dispatcher = build_condition_dispatcher(
        runtime=runtime,
        evaluator=evaluator,
    )
    digests: dict[str, str] = {}
    for key in sorted(representatives):
        hydrated, state = hydrate_public_work_item(representatives[key])
        execution_result = dispatcher.execute(hydrated, state)
        record = assemble_experiment_record(
            hydrated,
            state,
            execution_result,
            run_id="offline-public-controller-qualification-not-scientific",
        )
        digests["::".join(key)] = sha256_canonical_json(record)
    forbidden = sorted(
        FORBIDDEN_RUNTIME_CONTEXT_FIELDS & runtime.context_fields
    )
    if forbidden:
        raise PublicMatrixControllerError(
            "public runtime received evaluator fields: " + ", ".join(forbidden)
        )
    return {
        "qualified_pairs": len(runtime.seen_pairs),
        "pair_record_digests": digests,
        "runtime_context_fields": sorted(runtime.context_fields),
        "forbidden_runtime_context_fields_present": False,
        "offline_evaluator_field_count": len(evaluator.fields_seen),
    }


def build_controller_qualification() -> dict[str, Any]:
    manifest = verify_public_execution_plan()
    public_agentdojo = verify_public_resolver_qualification()
    abort_review = verify_abort_review()
    rows = _load_jsonl(DEFAULT_PLAN)
    if len(rows) != 6873:
        raise PublicMatrixControllerError("public plan record count drift")
    budget = load_public_policy()
    expanded = copy.deepcopy(budget)
    expanded["deepseek"]["incremental_hard_limit_cny"] = 30.0
    expanded_budget_rejected = False
    try:
        validate_public_policy(expanded)
    except PublicBudgetPolicyError:
        expanded_budget_rejected = True
    if not expanded_budget_rejected:
        raise PublicMatrixControllerError(
            "expanded public budget was not rejected"
        )
    return {
        "schema_version": (
            "m3-paper-v2-public-matrix-controller-qualification-2.0"
        ),
        "generated_at": QUALIFIED_AT,
        "status": "public_matrix_controller_qualified_offline",
        "plan": {
            "records": len(rows),
            "sha256": _sha256_file(DEFAULT_PLAN),
            "manifest_sha256": _sha256_file(DEFAULT_MANIFEST),
            "primary_records": manifest["counts"]["by_model_role"][
                "primary"
            ],
            "second_records": manifest["counts"]["by_model_role"]["second"],
        },
        "condition_shells": _condition_qualification(rows),
        "public_agentdojo_resolver": {
            "qualification_sha256": _sha256_file(
                DEFAULT_PUBLIC_AGENTDOJO_QUALIFICATION
            ),
            "qualification_probes": public_agentdojo[
                "qualification_probe_count"
            ],
            "public_agentdojo_work_items": public_agentdojo[
                "public_agentdojo_work_items"
            ],
            "network_calls_made": 0,
        },
        "public_v1_abort": {
            "review_sha256": abort_review["manifest_sha256"],
            "provider_requests": abort_review["evidence"][
                "provider_requests"
            ],
            "run_resumable": abort_review["evidence"]["run_resumable"],
        },
        "provider_trace": _provider_trace_qualification(),
        "negative_coverage": {
            "expanded_budget_rejected": expanded_budget_rejected,
            "existing_trace_path_rejected": True,
            "model_identity_mismatch_rejected_by_client": True,
            "forbidden_online_evaluator_fields_rejected": True,
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
        raise PublicMatrixControllerError(
            "public controller qualification drift"
        )
    return observed


def _candidate_artifacts() -> list[Path]:
    return [
        DEFAULT_FREEZE,
        DEFAULT_PLAN,
        DEFAULT_MANIFEST,
        DEFAULT_POLICY,
        DEFAULT_QUALIFICATION,
        DEFAULT_TRACE_ACTIVATION,
        DEFAULT_PROVIDER_SAFETY_POLICY,
        DEFAULT_SCHEMA,
        PROJECT_ROOT
        / "schemas/paper_v2/public_matrix_admission_v2.schema.json",
        Path(__file__),
        PROJECT_ROOT
        / "experiments/paper_v2/public_matrix_plan_v1.py",
        PROJECT_ROOT
        / "experiments/paper_v2/public_matrix_controller_v1.py",
        PROJECT_ROOT
        / "experiments/paper_v2/public_abort_review_v1.py",
        PROJECT_ROOT
        / "experiments/paper_v2/public_agentdojo_live_dependency_v2.py",
        DEFAULT_ABORT_REVIEW,
        DEFAULT_PUBLIC_AGENTDOJO_QUALIFICATION,
        PROTOCOL_ROOT / "public_matrix_candidate_v1.json",
        PROJECT_ROOT
        / "experiments/paper_v2/public_provider_budget_v1.py",
        PROJECT_ROOT
        / "experiments/paper_v2/public_deepseek_client_v1.py",
        PROJECT_ROOT
        / "experiments/paper_v2/public_provider_trace_v1.py",
        PROJECT_ROOT
        / "experiments/paper_v2/public_execution_store_v1.py",
        PROJECT_ROOT
        / "experiments/paper_v2/public_live_controller_v2.py",
        PROJECT_ROOT
        / "experiments/paper_v2/public_analysis_v1.py",
        PROJECT_ROOT
        / "experiments/paper_v2/public_result_gate_v1.py",
        PROTOCOL_ROOT / "public_analysis_preregistration_v1.json",
        PROJECT_ROOT
        / "experiments/paper_v2/formal_condition_executors.py",
        PROJECT_ROOT / "experiments/paper_v2/live_condition_runtime.py",
        PROJECT_ROOT / "experiments/paper_v2/formal_record_store_v2.py",
    ]


def build_candidate() -> dict[str, Any]:
    qualification = verify_controller_qualification()
    manifest = verify_public_execution_plan()
    policy = load_public_policy()
    abort_review = verify_abort_review()
    resolver_qualification_sha256 = _sha256_file(
        DEFAULT_PUBLIC_AGENTDOJO_QUALIFICATION
    )
    model_roles = copy.deepcopy(manifest["model_roles"])
    for role in ("primary", "second"):
        model_roles[role]["source_execution_identity"] = model_roles[role][
            "execution_identity"
        ]
        model_roles[role]["execution_identity"] = sha256_canonical_json(
            {
                "schema_version": (
                    "m3-paper-v2-public-execution-identity-2.0"
                ),
                "model_role": role,
                "source_execution_identity": model_roles[role][
                    "source_execution_identity"
                ],
                "public_agentdojo_qualification_sha256": (
                    resolver_qualification_sha256
                ),
                "public_v1_abort_review_sha256": abort_review[
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
                "run_id": f"paper-v2-public-v2-{role}-20260728",
                "output_root": (
                    "outputs/paper_upgrade_v2/formal_public/deepseek/"
                    f"public-v2-{role}-"
                    f"{model_roles[role]['execution_identity']}"
                ),
            }
            for role in ("primary", "second")
        },
        "remediation": {
            "source_run_resumable": False,
            "source_abort_review_sha256": abort_review["manifest_sha256"],
            "public_agentdojo_qualification_sha256": (
                resolver_qualification_sha256
            ),
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
        },
        "scientific_boundary": {
            "canary_review_is_outcome_blind": True,
            "result_admission_is_separate": True,
            "flash_claim": "cross_model_not_cross_provider",
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
                _candidate_artifacts(),
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
        raise PublicMatrixControllerError("public candidate must be an object")
    Draft202012Validator(
        _load_json(DEFAULT_SCHEMA),
        format_checker=FormatChecker(),
    ).validate(dict(value))
    if (
        value["scope_sha256"] != sha256_canonical_json(value["scope"])
        or value["manifest_sha256"] != _manifest_sha(value)
    ):
        raise PublicMatrixControllerError("public candidate digest drift")
    locks = value["artifact_locks"]
    if len({item["path"] for item in locks}) != len(locks):
        raise PublicMatrixControllerError("duplicate public artifact lock")
    for item in locks:
        path = (PROJECT_ROOT / item["path"]).resolve()
        try:
            path.relative_to(PROJECT_ROOT.resolve())
        except ValueError as exc:
            raise PublicMatrixControllerError(
                "public artifact lock escapes the project root"
            ) from exc
        if (
            not path.is_file()
            or path.stat().st_size != item["bytes"]
            or _sha256_file(path) != item["sha256"]
        ):
            raise PublicMatrixControllerError(
                f"public artifact lock drift: {item['path']}"
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
        raise PublicMatrixControllerError("public candidate drift")
    return observed


def verify_stage_a() -> dict[str, Any]:
    qualification = verify_controller_qualification()
    candidate = verify_candidate()
    return {
        "status": "public_stage_a_offline_qualified_candidate_frozen",
        "records": candidate["scope"]["records"],
        "qualified_pairs": qualification["condition_shells"][
            "qualified_pairs"
        ],
        "model_roles": sorted(
            qualification["provider_trace"]
        ),
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
