"""为前瞻性 v2 实验激活获批的 DeepSeek 请求追踪机制。

开启调用链路全程跟踪，支持精确的因果溯源与中间状态复现。
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator, FormatChecker

from experiments.paper_v2.provider_request_trace_candidate import (
    validate_policy_candidate,
    validate_qualification,
    validate_trace_attestation,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_ROOT = PROJECT_ROOT / "protocols/paper_upgrade_v2"
DEFAULT_CANDIDATE_POLICY = (
    PROTOCOL_ROOT / "provider_request_trace_policy_v2_candidate.json"
)
DEFAULT_CANDIDATE_QUALIFICATION = (
    PROTOCOL_ROOT / "provider_request_trace_v2_qualification.json"
)
DEFAULT_SCHEMA = (
    PROJECT_ROOT
    / "schemas/paper_v2/provider_trace_attestation_v2.schema.json"
)
DEFAULT_OUTPUT = (
    PROTOCOL_ROOT / "provider_request_trace_activation_v2.json"
)
SCHEMA_VERSION = "m3-paper-v2-provider-trace-activation-2.0"
ATTESTATION_SCHEMA_VERSION = (
    "m3-paper-v2-provider-trace-attestation-2.1"
)
APPROVED_AT = "2026-07-24T01:03:51.9003883+08:00"
APPROVAL_SOURCE = "direct_project_owner_message_with_quota_screenshot"
APPROVED_PROVIDER_IDS = ("deepseek",)


class ProviderRequestTraceActivationError(ValueError):
    """当批准的 v2 请求追踪边界发生漂移时抛出的异常。"""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ProviderRequestTraceActivationError(
            f"{path}: expected a JSON object"
        )
    return value


def _approval_design() -> list[str]:
    return [
        "local request ID frozen before transport",
        "canonical request payload SHA-256",
        "official provider response ID",
        "exact returned model identity",
        "append-only hash-chained log with flush and fsync",
    ]


def _validate_schema(path: Path = DEFAULT_SCHEMA) -> dict[str, Any]:
    schema = _load_object(path)
    Draft202012Validator.check_schema(schema)
    if (
        schema.get("$id")
        != "https://m3-pi-guard.local/schemas/paper_v2/"
        "provider_trace_attestation_v2.schema.json"
    ):
        raise ProviderRequestTraceActivationError(
            "provider trace attestation schema identity drift"
        )
    return schema


def build_activation(
    *,
    candidate_policy_path: Path = DEFAULT_CANDIDATE_POLICY,
    candidate_qualification_path: Path = DEFAULT_CANDIDATE_QUALIFICATION,
    schema_path: Path = DEFAULT_SCHEMA,
) -> dict[str, Any]:
    validate_policy_candidate(_load_object(candidate_policy_path))
    qualification = validate_qualification(
        _load_object(candidate_qualification_path)
    )
    _validate_schema(schema_path)
    if (
        qualification["append_flush_fsync"] is not True
        or qualification["payload_commitment_before_transport"] is not True
        or qualification["negative_cases_rejected"]
        != qualification["negative_cases_expected"]
    ):
        raise ProviderRequestTraceActivationError(
            "candidate trace qualification is incomplete"
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "approved_for_prospective_v2_trace",
        "approved_at": APPROVED_AT,
        "approval_source": APPROVAL_SOURCE,
        "approval_scope": {
            "provider_ids": list(APPROVED_PROVIDER_IDS),
            "accepted_complete_request_chain": _approval_design(),
        },
        "bound_inputs": {
            "candidate_policy": {
                "path": candidate_policy_path.relative_to(
                    PROJECT_ROOT
                ).as_posix(),
                "sha256": _sha256_file(candidate_policy_path),
            },
            "candidate_qualification": {
                "path": candidate_qualification_path.relative_to(
                    PROJECT_ROOT
                ).as_posix(),
                "sha256": _sha256_file(candidate_qualification_path),
            },
            "attestation_schema": {
                "path": schema_path.relative_to(PROJECT_ROOT).as_posix(),
                "sha256": _sha256_file(schema_path),
            },
        },
        "request_trace_protocol_activated": True,
        "fresh_prospective_requests_only": True,
        "v1_contract_unchanged": True,
        "historical_artifacts_retroactively_eligible": False,
        "formal_matrix_authorized": False,
        "formal_matrix_remaining_requirements": [
            "fresh live DeepSeek trace qualification under activated schema",
            "experiment-record v2 and record-store v2 integration",
            "provider execution preflight pass",
        ],
        "provider_tools_declared": False,
        "external_effects_enabled": False,
        "prompt_or_response_content_stored": False,
        "credentials_stored": False,
        "network_calls_made": 0,
        "formal_results_created": 0,
    }


def validate_activation(
    value: Any,
    *,
    candidate_policy_path: Path = DEFAULT_CANDIDATE_POLICY,
    candidate_qualification_path: Path = DEFAULT_CANDIDATE_QUALIFICATION,
    schema_path: Path = DEFAULT_SCHEMA,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ProviderRequestTraceActivationError(
            "trace activation must be an object"
        )
    expected = build_activation(
        candidate_policy_path=candidate_policy_path,
        candidate_qualification_path=candidate_qualification_path,
        schema_path=schema_path,
    )
    if dict(value) != expected:
        raise ProviderRequestTraceActivationError(
            "provider trace activation drift"
        )
    return dict(value)


def activate_trace_attestation(
    candidate: Mapping[str, Any],
    *,
    activation_path: Path = DEFAULT_OUTPUT,
    schema_path: Path = DEFAULT_SCHEMA,
) -> dict[str, Any]:
    candidate = validate_trace_attestation(candidate)
    activation = validate_activation(_load_object(activation_path))
    provider_id = str(candidate["provider_id"])
    if provider_id not in activation["approval_scope"]["provider_ids"]:
        raise ProviderRequestTraceActivationError(
            f"{provider_id}: provider is outside the approved trace scope"
        )
    value = {
        "schema_version": ATTESTATION_SCHEMA_VERSION,
        "evidence_level": "prospective_formal_trace_eligible_v2",
        "trace_mode": candidate["trace_mode"],
        "client_request_id": candidate["client_request_id"],
        "provider_request_id": candidate["provider_request_id"],
        "provider_response_id": candidate["provider_response_id"],
        "provider_id": provider_id,
        "model_id": candidate["model_id"],
        "payload_sha256": candidate["payload_sha256"],
        "commitment_sha256": candidate["commitment_sha256"],
        "started_event_sha256": candidate["started_event_sha256"],
        "activation_manifest_sha256": _sha256_file(activation_path),
        "official_network": True,
        "exact_model_identity": True,
        "prompt_rewrite_declaration": "none_declared",
        "request_started_before_transport": True,
        "append_flush_fsync": True,
        "prompt_or_response_content_stored": False,
        "v1_contract_unchanged": True,
        "v2_trace_eligible": True,
        "retroactive_upgrade_allowed": False,
    }
    validate_activated_attestation(value, schema_path=schema_path)
    return value


def validate_activated_attestation(
    value: Any,
    *,
    schema_path: Path = DEFAULT_SCHEMA,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ProviderRequestTraceActivationError(
            "activated attestation must be an object"
        )
    schema = _validate_schema(schema_path)
    Draft202012Validator(
        schema,
        format_checker=FormatChecker(),
    ).validate(dict(value))
    if (
        value.get("provider_request_id") is None
        and value.get("trace_mode")
        != "precommitted_local_plus_provider_response"
    ):
        raise ProviderRequestTraceActivationError(
            "missing provider request ID requires the local-precommit mode"
        )
    if (
        value.get("provider_request_id") is not None
        and value.get("trace_mode")
        != "provider_dual_id_plus_precommitted_local"
    ):
        raise ProviderRequestTraceActivationError(
            "provider request ID requires the dual-ID trace mode"
        )
    return dict(value)


def write_activation(path: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    value = build_activation()
    validate_activation(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return value


def verify_activation(path: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    return validate_activation(_load_object(path))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    output = (
        args.output
        if args.output.is_absolute()
        else PROJECT_ROOT / args.output
    )
    value = verify_activation(output) if args.verify_only else write_activation(
        output
    )
    print(
        json.dumps(
            {
                "status": value["status"],
                "approved_provider_ids": value["approval_scope"][
                    "provider_ids"
                ],
                "request_trace_protocol_activated": True,
                "formal_matrix_authorized": False,
                "network_calls_made": 0,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
