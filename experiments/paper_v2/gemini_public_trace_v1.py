"""Prospective, append-only request trace for official Gemini public runs."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import experiments.paper_v2.provider_request_trace_candidate as trace
from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.official_provider_executor import (
    OfficialProviderClient,
    OfficialProviderCompletion,
    ProviderPausedError,
    validate_provider_receipt,
)


PROVIDER_ID = "gemini"
BUNDLE_SCHEMA_VERSION = "m3-paper-v2-gemini-provider-trace-bundle-1.0"
ACTIVATED_SCHEMA_VERSION = (
    "m3-paper-v2-gemini-provider-trace-attestation-1.0"
)
USAGE_SCHEMA_VERSION = "m3-paper-v2-gemini-free-usage-evidence-1.0"


class GeminiPublicTraceV1Error(ValueError):
    """Raised when the prospective Gemini evidence chain is incomplete."""


def _usage_totals(items: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return {
        "requests": len(items),
        "prompt_tokens": sum(int(item["prompt_tokens"]) for item in items),
        "completion_tokens": sum(
            int(item["completion_tokens"]) for item in items
        ),
        "total_tokens": sum(int(item["total_tokens"]) for item in items),
    }


def build_usage_evidence(
    receipt: Mapping[str, Any],
    commitment: Mapping[str, Any],
    *,
    prior_items: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    validate_provider_receipt(receipt)
    evidence = receipt["evidence"]
    if (
        evidence.get("provider_id") != PROVIDER_ID
        or evidence.get("returned_model") != commitment["model_id"]
        or evidence.get("payload_sha256") != commitment["payload_sha256"]
        or not evidence.get("response_id")
        or evidence.get("transport_kind") != "official_network"
        or evidence.get("identity_verified") is not True
    ):
        raise GeminiPublicTraceV1Error(
            "Gemini receipt does not bind the pretransport commitment"
        )
    raw = evidence.get("usage")
    budget = evidence.get("budget")
    if not isinstance(raw, Mapping) or not isinstance(budget, Mapping):
        raise GeminiPublicTraceV1Error("Gemini usage or budget evidence missing")
    prompt = int(raw.get("prompt_tokens", -1))
    completion = int(raw.get("completion_tokens", -1))
    total = int(raw.get("total_tokens", -1))
    if prompt < 0 or completion < 0 or total < prompt + completion:
        raise GeminiPublicTraceV1Error("Gemini token usage is inconsistent")
    cumulative = _usage_totals(
        [
            *prior_items,
            {
                "prompt_tokens": prompt,
                "completion_tokens": completion,
                "total_tokens": total,
            },
        ]
    )
    observed = budget.get("cumulative_usage")
    if not isinstance(observed, Mapping) or any(
        int(observed.get(field, -1)) != cumulative[field]
        for field in ("requests", "prompt_tokens", "completion_tokens")
    ):
        raise GeminiPublicTraceV1Error(
            "Gemini cumulative usage drifted from prior requests"
        )
    if budget.get("charged_usd") != 0.0 or budget.get("status") != "continue":
        raise GeminiPublicTraceV1Error(
            "Gemini receipt is not compatible with the free-only gate"
        )
    return {
        "schema_version": USAGE_SCHEMA_VERSION,
        "call_index": int(commitment["call_index"]),
        "client_request_id": str(commitment["client_request_id"]),
        "provider_response_id": str(evidence["response_id"]),
        "provider_receipt_sha256": sha256_canonical_json(receipt),
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": total,
        "cumulative_usage": cumulative,
        "billing_tier": "free",
        "charged_usd": 0.0,
        "paid_ceiling_usd": 0.0,
        "free_tier_attestation_source": (
            "frozen_local_policy_plus_provider_usage_receipt"
        ),
        "budget_status_after_request": "continue",
    }


def activate_attestation(
    candidate: Mapping[str, Any],
    *,
    admission_manifest_sha256: str,
) -> dict[str, Any]:
    trace.validate_trace_attestation(candidate)
    if len(admission_manifest_sha256) != 64:
        raise GeminiPublicTraceV1Error(
            "Gemini trace activation requires an admission SHA-256"
        )
    value = {
        **copy.deepcopy(dict(candidate)),
        "schema_version": ACTIVATED_SCHEMA_VERSION,
        "evidence_level": "prospective_formal_gemini_trace_eligible_v1",
        "admission_manifest_sha256": admission_manifest_sha256,
        "request_started_before_transport": True,
        "append_flush_fsync": True,
        "prompt_or_response_content_stored": False,
    }
    return validate_activated_attestation(value)


def validate_activated_attestation(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise GeminiPublicTraceV1Error("Gemini attestation must be an object")
    required_strings = (
        "client_request_id",
        "provider_response_id",
        "provider_id",
        "model_id",
        "payload_sha256",
        "commitment_sha256",
        "started_event_sha256",
        "admission_manifest_sha256",
    )
    if (
        value.get("schema_version") != ACTIVATED_SCHEMA_VERSION
        or value.get("evidence_level")
        != "prospective_formal_gemini_trace_eligible_v1"
        or value.get("provider_id") != PROVIDER_ID
        or any(not isinstance(value.get(field), str) or not value[field] for field in required_strings)
        or any(
            len(str(value[field])) != 64
            for field in (
                "payload_sha256",
                "commitment_sha256",
                "started_event_sha256",
                "admission_manifest_sha256",
            )
        )
        or value.get("official_network") is not True
        or value.get("exact_model_identity") is not True
        or value.get("prompt_rewrite_declaration") != "none_declared"
        or value.get("request_started_before_transport") is not True
        or value.get("append_flush_fsync") is not True
        or value.get("prompt_or_response_content_stored") is not False
        or value.get("retroactive_upgrade_allowed") is not False
    ):
        raise GeminiPublicTraceV1Error("Gemini activated attestation drift")
    return copy.deepcopy(dict(value))


def _started_commitments(
    rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    return [
        copy.deepcopy(dict(row["event"]["commitment"]))
        for row in rows
        if row["event"]["event_type"] == "started"
    ]


def _terminal_candidates(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    return {
        str(row["event"]["client_request_id"]): copy.deepcopy(
            dict(row["event"]["attestation"])
        )
        for row in rows
        if row["event"]["event_type"] == "completed"
    }


def build_trace_bundle(
    *,
    trace_path: Path,
    execution_identity: str,
    work_key: str,
    model_id: str,
    admission_manifest_sha256: str,
    activated_attestations: Mapping[str, Mapping[str, Any]],
    usage_evidence: Mapping[str, Mapping[str, Any]],
    failures: Mapping[str, Mapping[str, str]],
) -> dict[str, Any]:
    rows = trace.load_trace_rows(trace_path)
    status = trace.validate_trace_rows(rows)
    commitments = _started_commitments(rows)
    ordered_activated = [
        copy.deepcopy(dict(activated_attestations[item["client_request_id"]]))
        for item in commitments
        if item["client_request_id"] in activated_attestations
    ]
    ordered_usage = [
        copy.deepcopy(dict(usage_evidence[item["client_request_id"]]))
        for item in commitments
        if item["client_request_id"] in usage_evidence
    ]
    ordered_failures = [
        copy.deepcopy(dict(failures[item["client_request_id"]]))
        for item in commitments
        if item["client_request_id"] in failures
    ]
    bundle_status = "completed" if not ordered_failures else {
        "provider_failure": "incomplete_provider_failure",
        "paused": "incomplete_paused",
        "evidence_failure": "incomplete_evidence_failure",
    }[ordered_failures[0]["status"]]
    tier = "formal_candidate" if bundle_status == "completed" else "diagnostic"
    core = {
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "execution_identity": execution_identity,
        "work_key": work_key,
        "provider_id": PROVIDER_ID,
        "model_id": model_id,
        "admission_manifest_sha256": admission_manifest_sha256,
        "bundle_status": bundle_status,
        "result_tier_ceiling": tier,
        "request_count": len(commitments),
        "completed_request_count": status["completed_requests"],
        "open_request_count": status["open_requests"],
        "trace_event_count": status["event_count"],
        "trace_tail_sha256": status["tail_sha256"],
        "trace_rows_sha256": sha256_canonical_json(rows),
        "trace_rows": rows,
        "activated_attestations": ordered_activated,
        "usage_evidence": ordered_usage,
        "usage_summary": {
            **_usage_totals(ordered_usage),
            "billing_tier": "free",
            "charged_usd": 0.0,
            "paid_ceiling_usd": 0.0,
        },
        "failures": ordered_failures,
        "append_flush_fsync": True,
        "automatic_retry": False,
        "provider_tools_declared": False,
        "external_effects_enabled": False,
        "prompt_or_response_content_stored": False,
    }
    value = {**core, "bundle_sha256": sha256_canonical_json(core)}
    return validate_trace_bundle(value)


def validate_trace_bundle(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise GeminiPublicTraceV1Error("Gemini trace bundle must be an object")
    core = {key: item for key, item in value.items() if key != "bundle_sha256"}
    if (
        value.get("schema_version") != BUNDLE_SCHEMA_VERSION
        or value.get("provider_id") != PROVIDER_ID
        or value.get("bundle_sha256") != sha256_canonical_json(core)
        or value.get("automatic_retry") is not False
        or value.get("provider_tools_declared") is not False
        or value.get("external_effects_enabled") is not False
        or value.get("prompt_or_response_content_stored") is not False
    ):
        raise GeminiPublicTraceV1Error("Gemini trace bundle envelope drift")
    rows = value.get("trace_rows")
    if not isinstance(rows, list):
        raise GeminiPublicTraceV1Error("Gemini trace rows missing")
    status = trace.validate_trace_rows(rows)
    commitments = _started_commitments(rows)
    if (
        value.get("request_count") != len(commitments)
        or value.get("completed_request_count") != status["completed_requests"]
        or value.get("open_request_count") != status["open_requests"]
        or value.get("trace_event_count") != status["event_count"]
        or value.get("trace_tail_sha256") != status["tail_sha256"]
        or value.get("trace_rows_sha256") != sha256_canonical_json(rows)
    ):
        raise GeminiPublicTraceV1Error("Gemini trace summary drift")
    if [item["call_index"] for item in commitments] != list(
        range(1, len(commitments) + 1)
    ):
        raise GeminiPublicTraceV1Error("Gemini call indices are not contiguous")
    for item in commitments:
        if (
            item["execution_identity"] != value["execution_identity"]
            or item["work_key"] != value["work_key"]
            or item["provider_id"] != PROVIDER_ID
            or item["model_id"] != value["model_id"]
        ):
            raise GeminiPublicTraceV1Error("Gemini commitment identity drift")
    candidates = _terminal_candidates(rows)
    activated = [
        validate_activated_attestation(item)
        for item in value.get("activated_attestations", [])
    ]
    usage = value.get("usage_evidence")
    failures = value.get("failures")
    if not isinstance(usage, list) or not isinstance(failures, list):
        raise GeminiPublicTraceV1Error("Gemini trace evidence arrays missing")
    completed_ids = [
        item["client_request_id"]
        for item in commitments
        if item["client_request_id"] in candidates
    ]
    if (
        [item["client_request_id"] for item in activated] != completed_ids
        or [item["client_request_id"] for item in usage] != completed_ids
        or any(
            item["admission_manifest_sha256"]
            != value["admission_manifest_sha256"]
            for item in activated
        )
    ):
        raise GeminiPublicTraceV1Error("Gemini terminal evidence ordering drift")
    for item in activated:
        candidate = candidates[item["client_request_id"]]
        for field in (
            "trace_mode",
            "client_request_id",
            "provider_request_id",
            "provider_response_id",
            "provider_id",
            "model_id",
            "payload_sha256",
            "commitment_sha256",
            "started_event_sha256",
        ):
            if item[field] != candidate[field]:
                raise GeminiPublicTraceV1Error(
                    "Gemini activated attestation does not bind terminal trace"
                )
    response_ids = [item["provider_response_id"] for item in activated]
    if len(response_ids) != len(set(response_ids)):
        raise GeminiPublicTraceV1Error("Gemini response IDs are not unique")
    expected_summary = {
        **_usage_totals(usage),
        "billing_tier": "free",
        "charged_usd": 0.0,
        "paid_ceiling_usd": 0.0,
    }
    if value.get("usage_summary") != expected_summary or any(
        item.get("billing_tier") != "free"
        or item.get("charged_usd") != 0.0
        or item.get("paid_ceiling_usd") != 0.0
        for item in usage
    ):
        raise GeminiPublicTraceV1Error("Gemini free-tier usage summary drift")
    open_ids = {
        item["client_request_id"]
        for item in commitments
        if item["client_request_id"] not in candidates
    }
    if {item.get("client_request_id") for item in failures} != open_ids:
        raise GeminiPublicTraceV1Error("Gemini failures do not match open requests")
    expected_status = "completed"
    expected_tier = "formal_candidate"
    if failures:
        expected_status = {
            "provider_failure": "incomplete_provider_failure",
            "paused": "incomplete_paused",
            "evidence_failure": "incomplete_evidence_failure",
        }[failures[0]["status"]]
        expected_tier = "diagnostic"
    if (
        value.get("bundle_status") != expected_status
        or value.get("result_tier_ceiling") != expected_tier
    ):
        raise GeminiPublicTraceV1Error("Gemini bundle status drift")
    return copy.deepcopy(dict(value))


class GeminiPublicTracedProviderClient:
    """Wrap one official client and precommit each exact payload to disk."""

    def __init__(
        self,
        client: OfficialProviderClient,
        *,
        execution_identity: str,
        work_key: str,
        trace_path: Path,
        admission_manifest_sha256: str,
        recorded_at: Callable[[], str],
        receipt_adapter: (
            Callable[[Mapping[str, Any]], Mapping[str, Any]] | None
        ) = None,
    ) -> None:
        if client.provider_id != PROVIDER_ID:
            raise GeminiPublicTraceV1Error("Gemini trace received another provider")
        if trace_path.exists() and trace_path.stat().st_size:
            raise GeminiPublicTraceV1Error(
                "existing Gemini trace cannot be automatically resumed"
            )
        self._client = client
        self.execution_identity = execution_identity
        self.work_key = work_key
        self.trace_path = trace_path
        self.admission_manifest_sha256 = admission_manifest_sha256
        self.recorded_at = recorded_at
        self.receipt_adapter = receipt_adapter
        self._activated: dict[str, dict[str, Any]] = {}
        self._usage: dict[str, dict[str, Any]] = {}
        self._failures: dict[str, dict[str, str]] = {}

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        case: dict[str, Any] | None = None,
        step: int = 1,
        observations: list[Any] | None = None,
    ) -> OfficialProviderCompletion:
        attempt_id = "attempt-" + sha256_canonical_json(
            {
                "execution_identity": self.execution_identity,
                "work_key": self.work_key,
                "call_index": step,
            }
        )[:24]
        commitment = trace.build_request_commitment(
            self._client,
            messages,
            execution_identity=self.execution_identity,
            work_key=self.work_key,
            call_index=step,
            attempt_id=attempt_id,
            precommitted_at=self.recorded_at(),
        )
        started = trace.append_started_trace(self.trace_path, commitment)
        phase = "provider_transport"
        try:
            completion = self._client.complete(
                messages,
                case=case,
                step=step,
                observations=observations,
            )
            phase = "evidence_completion"
            receipt = (
                dict(self.receipt_adapter(completion.receipt))
                if self.receipt_adapter is not None
                else dict(completion.receipt)
            )
            candidate = trace.bind_trace_attestation(
                commitment,
                receipt,
                started_event_sha256=started["event_sha256"],
            )
            activated = activate_attestation(
                candidate,
                admission_manifest_sha256=self.admission_manifest_sha256,
            )
            usage = build_usage_evidence(
                receipt,
                commitment,
                prior_items=list(self._usage.values()),
            )
            terminal = trace.append_completed_trace(
                self.trace_path,
                client_request_id=commitment["client_request_id"],
                receipt=receipt,
            )
            if terminal["event"]["attestation"] != candidate:
                raise GeminiPublicTraceV1Error("Gemini terminal trace drift")
            self._activated[commitment["client_request_id"]] = activated
            self._usage[commitment["client_request_id"]] = usage
            return completion
        except Exception as exc:
            self._failures[commitment["client_request_id"]] = {
                "client_request_id": commitment["client_request_id"],
                "status": (
                    "paused"
                    if isinstance(exc, ProviderPausedError)
                    else (
                        "evidence_failure"
                        if phase == "evidence_completion"
                        else "provider_failure"
                    )
                ),
                "error_type": type(exc).__name__,
            }
            raise

    def build_bundle(self) -> dict[str, Any]:
        return build_trace_bundle(
            trace_path=self.trace_path,
            execution_identity=self.execution_identity,
            work_key=self.work_key,
            model_id=self.model,
            admission_manifest_sha256=self.admission_manifest_sha256,
            activated_attestations=self._activated,
            usage_evidence=self._usage,
            failures=self._failures,
        )
