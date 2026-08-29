"""Qualify a prospective v2 request trace without activating it.

The paper-v2 v1 experiment contract requires both a provider request header ID
and a provider response ID.  Some official endpoints do not document or return
the former.  This module evaluates a prospective alternative: fsync a
content-free local request commitment before transport, then bind it to the
official response ID, exact model identity, payload hash and safe provider
receipt.

The candidate is deliberately not an experiment-record admission path.  It
cannot retroactively upgrade an earlier smoke and requires an explicit future
protocol/schema decision before formal execution.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Mapping, Sequence

from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.official_provider_executor import (
    DEFAULT_BUDGET_POLICY,
    HTTPResponseEnvelope,
    OfficialProviderClient,
    ProviderBudgetState,
    validate_messages,
    validate_provider_receipt,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_ROOT = PROJECT_ROOT / "protocols/paper_upgrade_v2"
DEFAULT_POLICY_OUTPUT = (
    PROTOCOL_ROOT / "provider_request_trace_policy_v2_candidate.json"
)
DEFAULT_QUALIFICATION_OUTPUT = (
    PROTOCOL_ROOT / "provider_request_trace_v2_qualification.json"
)
POLICY_SCHEMA_VERSION = "m3-paper-v2-provider-trace-policy-2.0-candidate"
COMMITMENT_SCHEMA_VERSION = "m3-paper-v2-provider-request-commitment-2.0"
EVENT_SCHEMA_VERSION = "m3-paper-v2-provider-trace-event-2.0"
ATTESTATION_SCHEMA_VERSION = "m3-paper-v2-provider-trace-attestation-2.0"
QUALIFICATION_SCHEMA_VERSION = (
    "m3-paper-v2-provider-trace-qualification-2.0"
)
QUALIFICATION_RECORDED_AT = "2026-07-24T01:10:00+08:00"
FIXED_MESSAGES = [
    {
        "role": "system",
        "content": "Return exactly SAFE. No tools are available.",
    },
    {
        "role": "user",
        "content": "Synthetic public provider-trace qualification.",
    },
]


class ProviderRequestTraceError(ValueError):
    """Raised when a prospective request trace is incomplete or drifts."""


def _write_fsynced_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(
        dict(row),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(encoded + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def _load_trace_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                if not line.strip():
                    raise ProviderRequestTraceError(
                        f"{path}:{line_number}: blank trace row"
                    )
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ProviderRequestTraceError(
                        f"{path}:{line_number}: trace row must be an object"
                    )
                rows.append(value)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProviderRequestTraceError(
            f"{path}: trace ledger is not valid UTF-8 JSONL"
        ) from exc
    validate_trace_rows(rows)
    return rows


def load_trace_rows(path: Path) -> list[dict[str, Any]]:
    """Load and validate a provider trace without exposing mutable internals."""

    return _load_trace_rows(path)


def _row_core(
    *,
    sequence: int,
    previous_event_sha256: str | None,
    event: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": EVENT_SCHEMA_VERSION,
        "sequence": sequence,
        "previous_event_sha256": previous_event_sha256,
        "event": dict(event),
    }


def validate_trace_rows(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    previous: str | None = None
    open_requests: dict[str, Mapping[str, Any]] = {}
    terminal_requests: set[str] = set()
    for sequence, row in enumerate(rows, start=1):
        if row.get("schema_version") != EVENT_SCHEMA_VERSION:
            raise ProviderRequestTraceError("unsupported trace event schema")
        if row.get("sequence") != sequence:
            raise ProviderRequestTraceError("trace sequence drift")
        if row.get("previous_event_sha256") != previous:
            raise ProviderRequestTraceError("trace hash-chain drift")
        event = row.get("event")
        if not isinstance(event, Mapping):
            raise ProviderRequestTraceError("trace event is missing")
        core = _row_core(
            sequence=sequence,
            previous_event_sha256=previous,
            event=event,
        )
        digest = sha256_canonical_json(core)
        if row.get("event_sha256") != digest:
            raise ProviderRequestTraceError("trace event digest drift")
        client_request_id = event.get("client_request_id")
        if not isinstance(client_request_id, str) or not client_request_id:
            raise ProviderRequestTraceError("client request ID is required")
        event_type = event.get("event_type")
        if event_type == "started":
            if (
                client_request_id in open_requests
                or client_request_id in terminal_requests
            ):
                raise ProviderRequestTraceError(
                    "duplicate client request trace"
                )
            commitment = event.get("commitment")
            validate_request_commitment(commitment)
            if event.get("commitment_sha256") != sha256_canonical_json(
                commitment
            ):
                raise ProviderRequestTraceError(
                    "started commitment digest drift"
                )
            open_requests[client_request_id] = commitment
        elif event_type == "completed":
            if client_request_id not in open_requests:
                raise ProviderRequestTraceError(
                    "completed trace has no precommitted start"
                )
            attestation = event.get("attestation")
            validate_trace_attestation(attestation)
            if (
                attestation["client_request_id"] != client_request_id
                or attestation["commitment_sha256"]
                != sha256_canonical_json(
                    open_requests.pop(client_request_id)
                )
            ):
                raise ProviderRequestTraceError(
                    "terminal trace does not bind its precommitment"
                )
            terminal_requests.add(client_request_id)
        else:
            raise ProviderRequestTraceError(
                "trace event must be started or completed"
            )
        previous = digest
    return {
        "event_count": len(rows),
        "completed_requests": len(terminal_requests),
        "open_requests": len(open_requests),
        "tail_sha256": previous,
    }


def _request_payload(
    client: OfficialProviderClient,
    messages: Sequence[Mapping[str, str]],
) -> dict[str, Any]:
    normalized = validate_messages(
        messages,
        content_class=client.content_class,
        policy=client.policy,
        allow_pinned_synthetic_credential_labels=(
            client.allow_pinned_synthetic_credential_labels
        ),
        active_api_key=client.api_key,
    )
    return {
        "model": client.model,
        "messages": normalized,
        "temperature": float(client.temperature),
        "max_tokens": int(client.max_tokens),
        "stream": False,
    }


def build_request_commitment(
    client: OfficialProviderClient,
    messages: Sequence[Mapping[str, str]],
    *,
    execution_identity: str,
    work_key: str,
    call_index: int,
    attempt_id: str,
    precommitted_at: str,
) -> dict[str, Any]:
    if not execution_identity or not work_key or not attempt_id:
        raise ProviderRequestTraceError(
            "execution, work and attempt identities are required"
        )
    if (
        isinstance(call_index, bool)
        or not isinstance(call_index, int)
        or call_index < 1
    ):
        raise ProviderRequestTraceError("call index must be positive")
    payload_sha256 = sha256_canonical_json(
        _request_payload(client, messages)
    )
    identity = {
        "execution_identity": execution_identity,
        "work_key": work_key,
        "call_index": call_index,
        "attempt_id": attempt_id,
        "provider_id": client.provider_id,
        "model_id": client.model,
        "payload_sha256": payload_sha256,
    }
    client_request_id = "m3req-" + sha256_canonical_json(identity)[:32]
    commitment = {
        "schema_version": COMMITMENT_SCHEMA_VERSION,
        **identity,
        "client_request_id": client_request_id,
        "precommitted_at": precommitted_at,
        "content_class": client.content_class,
        "provider_tools_declared": False,
        "external_effects_enabled": False,
        "prompt_or_response_content_stored": False,
    }
    validate_request_commitment(commitment)
    return commitment


def validate_request_commitment(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ProviderRequestTraceError("request commitment must be an object")
    if value.get("schema_version") != COMMITMENT_SCHEMA_VERSION:
        raise ProviderRequestTraceError("unsupported request commitment")
    for field in (
        "execution_identity",
        "work_key",
        "attempt_id",
        "provider_id",
        "model_id",
        "payload_sha256",
        "client_request_id",
        "precommitted_at",
        "content_class",
    ):
        if not isinstance(value.get(field), str) or not value[field]:
            raise ProviderRequestTraceError(
                f"request commitment requires {field}"
            )
    if not str(value["payload_sha256"]).isalnum() or len(
        str(value["payload_sha256"])
    ) != 64:
        raise ProviderRequestTraceError("payload digest is invalid")
    if (
        value.get("provider_tools_declared") is not False
        or value.get("external_effects_enabled") is not False
        or value.get("prompt_or_response_content_stored") is not False
    ):
        raise ProviderRequestTraceError(
            "request commitment safety boundary drift"
        )
    return dict(value)


def append_started_trace(
    path: Path,
    commitment: Mapping[str, Any],
) -> dict[str, Any]:
    commitment = validate_request_commitment(commitment)
    rows = _load_trace_rows(path)
    client_request_id = commitment["client_request_id"]
    if any(
        row["event"]["client_request_id"] == client_request_id
        for row in rows
    ):
        raise ProviderRequestTraceError("request trace already exists")
    event = {
        "event_type": "started",
        "client_request_id": client_request_id,
        "commitment": commitment,
        "commitment_sha256": sha256_canonical_json(commitment),
        "automatic_retry": False,
        "transport_started_after_precommit": True,
    }
    previous = rows[-1]["event_sha256"] if rows else None
    core = _row_core(
        sequence=len(rows) + 1,
        previous_event_sha256=previous,
        event=event,
    )
    row = {**core, "event_sha256": sha256_canonical_json(core)}
    _write_fsynced_jsonl(path, row)
    _load_trace_rows(path)
    return row


def _official_receipt_evidence(
    receipt: Mapping[str, Any],
) -> Mapping[str, Any]:
    validate_provider_receipt(receipt)
    evidence = receipt["evidence"]
    if evidence.get("transport_kind") != "official_network":
        raise ProviderRequestTraceError(
            "formal trace candidate requires an official network receipt"
        )
    if (
        evidence.get("model_identity_exact_match") is not True
        or evidence.get("configured_model") != evidence.get("returned_model")
        or evidence.get("identity_verified") is not True
    ):
        raise ProviderRequestTraceError(
            "formal trace candidate requires exact model identity"
        )
    if not evidence.get("response_id"):
        raise ProviderRequestTraceError(
            "formal trace candidate requires a provider response ID"
        )
    if evidence.get("prompt_rewrite_declaration") != "none_declared":
        raise ProviderRequestTraceError(
            "formal trace candidate requires no prompt rewrite"
        )
    return evidence


def bind_trace_attestation(
    commitment: Mapping[str, Any],
    receipt: Mapping[str, Any],
    *,
    started_event_sha256: str,
) -> dict[str, Any]:
    commitment = validate_request_commitment(commitment)
    evidence = _official_receipt_evidence(receipt)
    comparisons = {
        "provider_id": evidence.get("provider_id"),
        "model_id": evidence.get("returned_model"),
        "payload_sha256": evidence.get("payload_sha256"),
    }
    expected = {
        "provider_id": commitment["provider_id"],
        "model_id": commitment["model_id"],
        "payload_sha256": commitment["payload_sha256"],
    }
    if comparisons != expected:
        raise ProviderRequestTraceError(
            "provider receipt drifted from the precommitted request"
        )
    provider_request_id = evidence.get("request_id")
    trace_mode = (
        "provider_dual_id_plus_precommitted_local"
        if provider_request_id
        else "precommitted_local_plus_provider_response"
    )
    attestation = {
        "schema_version": ATTESTATION_SCHEMA_VERSION,
        "evidence_level": "formal_trace_candidate_v2",
        "trace_mode": trace_mode,
        "client_request_id": commitment["client_request_id"],
        "provider_request_id": provider_request_id,
        "provider_response_id": evidence["response_id"],
        "provider_id": commitment["provider_id"],
        "model_id": commitment["model_id"],
        "payload_sha256": commitment["payload_sha256"],
        "commitment_sha256": sha256_canonical_json(commitment),
        "started_event_sha256": started_event_sha256,
        "official_network": True,
        "exact_model_identity": True,
        "prompt_rewrite_declaration": "none_declared",
        "v1_formal_candidate": False,
        "v2_schema_activation_required": True,
        "retroactive_upgrade_allowed": False,
    }
    validate_trace_attestation(attestation)
    return attestation


def validate_trace_attestation(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ProviderRequestTraceError("trace attestation must be an object")
    if value.get("schema_version") != ATTESTATION_SCHEMA_VERSION:
        raise ProviderRequestTraceError("unsupported trace attestation")
    if value.get("evidence_level") != "formal_trace_candidate_v2":
        raise ProviderRequestTraceError("trace evidence level drift")
    if value.get("trace_mode") not in {
        "provider_dual_id_plus_precommitted_local",
        "precommitted_local_plus_provider_response",
    }:
        raise ProviderRequestTraceError("unsupported trace mode")
    for field in (
        "client_request_id",
        "provider_response_id",
        "provider_id",
        "model_id",
        "payload_sha256",
        "commitment_sha256",
        "started_event_sha256",
    ):
        if not isinstance(value.get(field), str) or not value[field]:
            raise ProviderRequestTraceError(
                f"trace attestation requires {field}"
            )
    if (
        value.get("official_network") is not True
        or value.get("exact_model_identity") is not True
        or value.get("prompt_rewrite_declaration") != "none_declared"
        or value.get("v1_formal_candidate") is not False
        or value.get("v2_schema_activation_required") is not True
        or value.get("retroactive_upgrade_allowed") is not False
    ):
        raise ProviderRequestTraceError(
            "trace attestation activation boundary drift"
        )
    return dict(value)


def append_completed_trace(
    path: Path,
    *,
    client_request_id: str,
    receipt: Mapping[str, Any],
) -> dict[str, Any]:
    rows = _load_trace_rows(path)
    matching = [
        row
        for row in rows
        if row["event"]["event_type"] == "started"
        and row["event"]["client_request_id"] == client_request_id
    ]
    if len(matching) != 1:
        raise ProviderRequestTraceError(
            "completed trace requires exactly one persisted precommitment"
        )
    if any(
        row["event"]["event_type"] == "completed"
        and row["event"]["client_request_id"] == client_request_id
        for row in rows
    ):
        raise ProviderRequestTraceError("request trace is already terminal")
    started = matching[0]
    commitment = started["event"]["commitment"]
    attestation = bind_trace_attestation(
        commitment,
        receipt,
        started_event_sha256=started["event_sha256"],
    )
    event = {
        "event_type": "completed",
        "client_request_id": client_request_id,
        "attestation": attestation,
        "provider_receipt_sha256": sha256_canonical_json(receipt),
        "automatic_retry": False,
    }
    previous = rows[-1]["event_sha256"]
    core = _row_core(
        sequence=len(rows) + 1,
        previous_event_sha256=previous,
        event=event,
    )
    row = {**core, "event_sha256": sha256_canonical_json(core)}
    _write_fsynced_jsonl(path, row)
    status = _load_trace_rows(path)
    if status[-1] != row:
        raise ProviderRequestTraceError("terminal trace persistence failed")
    return row


def build_policy_candidate() -> dict[str, Any]:
    return {
        "schema_version": POLICY_SCHEMA_VERSION,
        "status": "qualified_candidate_not_activated",
        "purpose": (
            "Prospective request trace for official APIs that return a "
            "provider response ID but no documented request-ID header."
        ),
        "v1_contract_unchanged": True,
        "v1_artifacts_retroactively_eligible": False,
        "formal_execution_authorized": False,
        "activation_requires_explicit_user_confirmation": True,
        "activation_requires_new_experiment_record_schema": True,
        "required_order": [
            "build content-free payload commitment",
            "append and fsync started event",
            "perform exactly one official transport attempt",
            "validate exact returned model and provider response ID",
            "append and fsync terminal event",
        ],
        "required_bindings": [
            "execution_identity",
            "work_key",
            "call_index",
            "attempt_id",
            "provider_id",
            "model_id",
            "payload_sha256",
            "client_request_id",
            "started_event_sha256",
            "provider_response_id",
        ],
        "provider_request_header_id": "stored_when_available_not_required",
        "provider_response_id": "required",
        "automatic_retry": False,
        "cross_provider_fallback": False,
        "provider_managed_tools": False,
        "external_effects": False,
        "prompt_or_response_content_stored": False,
        "official_sources": [
            "https://api-docs.deepseek.com/zh-cn/api/create-chat-completion/",
            "https://ai.google.dev/gemini-api/docs/openai",
        ],
    }


def _fixture_client(
    provider_id: str,
    *,
    include_request_id: bool,
) -> OfficialProviderClient:
    policy = json.loads(DEFAULT_BUDGET_POLICY.read_text(encoding="utf-8"))
    model = str(policy[provider_id]["model_id"])

    def transport(*_):
        usage: dict[str, int] = {
            "prompt_tokens": 20,
            "completion_tokens": 2,
            "total_tokens": 22,
        }
        if provider_id == "deepseek":
            usage.update(
                {
                    "prompt_cache_hit_tokens": 16,
                    "prompt_cache_miss_tokens": 4,
                }
            )
        headers = (
            {"x-request-id": f"fixture-{provider_id}-request"}
            if include_request_id
            else {}
        )
        return HTTPResponseEnvelope(
            status_code=200,
            headers=headers,
            body={
                "id": f"fixture-{provider_id}-response",
                "model": model,
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "SAFE"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": usage,
            },
        )

    return OfficialProviderClient(
        provider_id=provider_id,
        api_key=f"fixture-key-{provider_id}",
        content_class="fixed_non_sensitive_runtime_instruction",
        budget_state=ProviderBudgetState(
            provider_id=provider_id,
            policy=policy,
        ),
        policy=policy,
        transport=transport,
        temperature=0.0,
        max_tokens=16,
    )


def _as_official_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    value = copy.deepcopy(dict(receipt))
    value["evidence"]["transport_kind"] = "official_network"
    value["evidence_sha256"] = sha256_canonical_json(value["evidence"])
    return value


def build_qualification() -> dict[str, Any]:
    modes: dict[str, str] = {}
    negative_cases_rejected = 0
    with TemporaryDirectory(prefix="m3-provider-trace-v2-") as directory:
        root = Path(directory)
        for provider_id, include_request_id in (
            ("deepseek", False),
            ("gemini", True),
        ):
            client = _fixture_client(
                provider_id,
                include_request_id=include_request_id,
            )
            commitment = build_request_commitment(
                client,
                FIXED_MESSAGES,
                execution_identity="qualification-execution",
                work_key=f"qualification-{provider_id}",
                call_index=1,
                attempt_id=f"qualification-attempt-{provider_id}",
                precommitted_at=QUALIFICATION_RECORDED_AT,
            )
            path = root / f"{provider_id}.jsonl"
            append_started_trace(path, commitment)
            completion = client.complete(FIXED_MESSAGES, step=1)
            terminal = append_completed_trace(
                path,
                client_request_id=commitment["client_request_id"],
                receipt=_as_official_receipt(completion.receipt),
            )
            modes[provider_id] = terminal["event"]["attestation"][
                "trace_mode"
            ]
            status = validate_trace_rows(_load_trace_rows(path))
            if status["completed_requests"] != 1:
                raise ProviderRequestTraceError(
                    "qualification trace did not terminate"
                )

        receipt = _as_official_receipt(
            _fixture_client(
                "deepseek", include_request_id=False
            ).complete(FIXED_MESSAGES, step=1).receipt
        )
        try:
            append_completed_trace(
                root / "missing-start.jsonl",
                client_request_id="m3req-missing",
                receipt=receipt,
            )
        except ProviderRequestTraceError:
            negative_cases_rejected += 1

        client = _fixture_client("deepseek", include_request_id=False)
        commitment = build_request_commitment(
            client,
            FIXED_MESSAGES,
            execution_identity="negative-execution",
            work_key="negative-work",
            call_index=1,
            attempt_id="negative-attempt",
            precommitted_at=QUALIFICATION_RECORDED_AT,
        )
        path = root / "payload-drift.jsonl"
        append_started_trace(path, commitment)
        drifted = copy.deepcopy(receipt)
        drifted["evidence"]["payload_sha256"] = "0" * 64
        drifted["evidence_sha256"] = sha256_canonical_json(
            drifted["evidence"]
        )
        try:
            append_completed_trace(
                path,
                client_request_id=commitment["client_request_id"],
                receipt=drifted,
            )
        except ProviderRequestTraceError:
            negative_cases_rejected += 1

        tampered = copy.deepcopy(_load_trace_rows(path))
        tampered[0]["event"]["commitment"]["work_key"] = "tampered"
        try:
            validate_trace_rows(tampered)
        except ProviderRequestTraceError:
            negative_cases_rejected += 1

    return {
        "schema_version": QUALIFICATION_SCHEMA_VERSION,
        "status": "qualified_candidate_not_activated",
        "recorded_at": QUALIFICATION_RECORDED_AT,
        "qualified_trace_modes": modes,
        "qualified_provider_count": len(modes),
        "negative_cases_rejected": negative_cases_rejected,
        "negative_cases_expected": 3,
        "append_flush_fsync": True,
        "payload_commitment_before_transport": True,
        "old_smoke_retroactive_upgrade": False,
        "v1_contract_modified": False,
        "v2_schema_activated": False,
        "user_confirmation_recorded": False,
        "network_calls_made": 0,
        "provider_tools_declared": False,
        "external_effects": False,
        "formal_results_created": 0,
        "qualification_evidence_only": True,
    }


def validate_policy_candidate(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ProviderRequestTraceError("trace policy must be an object")
    if value != build_policy_candidate():
        raise ProviderRequestTraceError("trace policy candidate drift")
    return dict(value)


def validate_qualification(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ProviderRequestTraceError(
            "trace qualification must be an object"
        )
    if value != build_qualification():
        raise ProviderRequestTraceError("trace qualification drift")
    return dict(value)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument(
        "--policy-output",
        type=Path,
        default=DEFAULT_POLICY_OUTPUT,
    )
    parser.add_argument(
        "--qualification-output",
        type=Path,
        default=DEFAULT_QUALIFICATION_OUTPUT,
    )
    args = parser.parse_args()
    policy_path = (
        args.policy_output
        if args.policy_output.is_absolute()
        else PROJECT_ROOT / args.policy_output
    )
    qualification_path = (
        args.qualification_output
        if args.qualification_output.is_absolute()
        else PROJECT_ROOT / args.qualification_output
    )
    policy = build_policy_candidate()
    qualification = build_qualification()
    if args.verify_only:
        validate_policy_candidate(
            json.loads(policy_path.read_text(encoding="utf-8"))
        )
        validate_qualification(
            json.loads(qualification_path.read_text(encoding="utf-8"))
        )
        print(
            json.dumps(
                {
                    "status": "verified_candidate_not_activated",
                    "network_calls_made": 0,
                    "formal_results_created": 0,
                },
                sort_keys=True,
            )
        )
        return 0
    policy_path.parent.mkdir(parents=True, exist_ok=True)
    policy_path.write_text(
        json.dumps(policy, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    qualification_path.write_text(
        json.dumps(
            qualification,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "policy": policy_path.relative_to(PROJECT_ROOT).as_posix(),
                "qualification": qualification_path.relative_to(
                    PROJECT_ROOT
                ).as_posix(),
                "status": qualification["status"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
