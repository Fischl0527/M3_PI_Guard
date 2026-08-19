"""Prospective experiment-record v2 contract for approved provider traces."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from experiments.paper_v2.contracts import (
    PaperV2ContractError,
    _validate_decision_semantics,
    _validate_digest_semantics,
    _validate_outcome_semantics,
    compute_online_visible_field_digest,
)
from experiments.paper_v2.provider_request_trace_activation import (
    DEFAULT_OUTPUT as DEFAULT_ACTIVATION,
)
from experiments.paper_v2.provider_safety import validate_safety_receipt
from experiments.paper_v2.provider_trace_bundle import (
    DEFAULT_SCHEMA as PROVIDER_TRACE_BUNDLE_SCHEMA,
    validate_provider_trace_bundle,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_RECORD_SCHEMA = (
    PROJECT_ROOT / "schemas/paper_v2/experiment_record_v2.schema.json"
)
EXPERIMENT_RECORD_V1_SCHEMA = (
    PROJECT_ROOT / "schemas/paper_v2/experiment_record_v1.schema.json"
)
PROVIDER_TRACE_SCHEMA = (
    PROJECT_ROOT
    / "schemas/paper_v2/provider_trace_attestation_v2.schema.json"
)
PROVIDER_SAFETY_RECEIPT_SCHEMA = (
    PROJECT_ROOT
    / "schemas/paper_v2/provider_safety_receipt_v1.schema.json"
)
EXPERIMENT_RECORD_SCHEMA_VERSION = "m3-paper-v2-experiment-record-2.2"


def _load_schema(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not isinstance(value.get("$id"), str):
        raise PaperV2ContractError(f"{path}: invalid JSON schema")
    return value


def _schema_registry() -> tuple[dict[str, Any], Registry]:
    schemas = [
        _load_schema(EXPERIMENT_RECORD_SCHEMA),
        _load_schema(EXPERIMENT_RECORD_V1_SCHEMA),
        _load_schema(PROVIDER_TRACE_SCHEMA),
        _load_schema(PROVIDER_TRACE_BUNDLE_SCHEMA),
        _load_schema(PROVIDER_SAFETY_RECEIPT_SCHEMA),
    ]
    registry = Registry().with_resources(
        [
            (schema["$id"], Resource.from_contents(schema))
            for schema in schemas
        ]
    )
    return schemas[0], registry


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_provider_semantics(
    record: Mapping[str, Any],
    *,
    activation_path: Path,
) -> None:
    bundle = validate_provider_trace_bundle(
        record["provider_trace_bundle"],
        activation_path=activation_path,
    )
    result_tier = record["result_tier"]
    if result_tier == "diagnostic":
        if (
            bundle["result_tier_ceiling"] != "diagnostic"
            or record["operational_status"] != "provider_failure"
        ):
            raise PaperV2ContractError(
                "diagnostic provider record requires an incomplete failed bundle"
            )
    elif (
        result_tier not in {"formal_candidate", "formal_admitted"}
        or bundle["result_tier_ceiling"] != "formal_candidate"
    ):
        raise PaperV2ContractError(
            "formal experiment-record v2 requires a complete provider bundle"
        )
    if (
        result_tier == "formal_admitted"
        and not record.get("admission_manifest_sha256")
    ):
        raise PaperV2ContractError(
            "formal admission requires an admission manifest digest"
        )
    safety_receipt = record["provider_safety_receipt"]
    validate_safety_receipt(safety_receipt)
    safety = safety_receipt["evidence"]
    if safety["provider_id"] != bundle["provider_id"]:
        raise PaperV2ContractError(
            "provider safety receipt does not bind the trace provider"
        )


def validate_experiment_record_v2(
    record: Mapping[str, Any],
    *,
    online_projection: Mapping[str, Any] | None = None,
    activation_path: Path = DEFAULT_ACTIVATION,
) -> None:
    """Validate schema, outcome semantics and the activated request chain."""

    schema, registry = _schema_registry()
    Draft202012Validator(
        schema,
        registry=registry,
        format_checker=FormatChecker(),
    ).validate(dict(record))
    _validate_digest_semantics(record["online_visible_field_digest"])
    _validate_decision_semantics(record)
    _validate_outcome_semantics(record)
    _validate_provider_semantics(
        record,
        activation_path=activation_path,
    )
    if online_projection is not None:
        expected = compute_online_visible_field_digest(online_projection)
        if expected != record["online_visible_field_digest"]:
            raise PaperV2ContractError(
                "online projection does not match online_visible_field_digest"
            )
