"""面向公开 Pro/Flash 执行的提供商追踪包适配器。

将不同提供商的私有响应头统一适配为结构化 trace 证据。
"""

from __future__ import annotations

import copy
import hashlib
from pathlib import Path
from typing import Any, Mapping, Sequence

from jsonschema import Draft202012Validator, FormatChecker

import experiments.paper_v2.provider_trace_bundle as pt
from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.deepseek_json_client_v2 import (
    build_json_request_commitment,
)
from experiments.paper_v2.official_provider_executor import (
    OfficialProviderCompletion,
    ProviderPausedError,
    validate_provider_receipt,
)
from experiments.paper_v2.provider_budget import (
    BudgetPolicyError,
    validate_deepseek_usage,
)
from experiments.paper_v2.provider_request_trace_activation import (
    activate_trace_attestation,
    validate_activated_attestation,
)
from experiments.paper_v2.provider_request_trace_candidate import (
    append_completed_trace,
    append_started_trace,
    bind_trace_attestation,
    validate_trace_rows,
)
from experiments.paper_v2.public_provider_budget_v1 import role_cost_cny


class PublicProviderTraceError(ValueError):
    """当公开请求链不完整或不一致时抛出的异常。"""


def _usage_totals(
    items: Sequence[Mapping[str, Any]],
) -> dict[str, int]:
    fields = (
        "prompt_tokens",
        "prompt_cache_hit_tokens",
        "prompt_cache_miss_tokens",
        "completion_tokens",
        "total_tokens",
    )
    return {
        field: sum(int(item[field]) for item in items)
        for field in fields
    }


def build_public_usage_summary(
    items: Sequence[Mapping[str, Any]],
    *,
    role_policy: Mapping[str, Any],
) -> dict[str, Any]:
    totals = _usage_totals(items)
    cost = role_cost_cny(role_policy, totals)
    ceiling = float(role_policy["deepseek"]["abort_ceiling_cny"])
    return {
        "completed_call_count": len(items),
        **totals,
        "cache_accounting_complete": (
            totals["prompt_tokens"]
            == totals["prompt_cache_hit_tokens"]
            + totals["prompt_cache_miss_tokens"]
        ),
        "cumulative_cost_cny": cost,
        "abort_ceiling_cny": ceiling,
        "within_abort_ceiling": cost <= ceiling,
    }


def build_public_usage_evidence(
    receipt: Mapping[str, Any],
    commitment: Mapping[str, Any],
    *,
    prior_items: Sequence[Mapping[str, Any]],
    role_policy: Mapping[str, Any],
) -> dict[str, Any]:
    validate_provider_receipt(receipt)
    evidence = receipt["evidence"]
    if (
        evidence.get("provider_id") != "deepseek"
        or evidence.get("returned_model") != commitment["model_id"]
        or evidence.get("payload_sha256") != commitment["payload_sha256"]
        or not evidence.get("response_id")
    ):
        raise PublicProviderTraceError(
            "public usage receipt does not bind the request commitment"
        )
    usage_raw = evidence.get("usage")
    if not isinstance(usage_raw, Mapping):
        raise PublicProviderTraceError("public usage receipt is missing")
    try:
        usage = validate_deepseek_usage(dict(usage_raw))
    except BudgetPolicyError as exc:
        raise PublicProviderTraceError(str(exc)) from exc
    total_tokens = usage_raw.get("total_tokens")
    if (
        isinstance(total_tokens, bool)
        or not isinstance(total_tokens, int)
        or total_tokens
        < usage["prompt_tokens"] + usage["completion_tokens"]
    ):
        raise PublicProviderTraceError("public total-token accounting drift")
    before = _usage_totals(prior_items)
    cumulative = {
        "prompt_tokens": before["prompt_tokens"] + usage["prompt_tokens"],
        "prompt_cache_hit_tokens": before["prompt_cache_hit_tokens"]
        + usage["prompt_cache_hit_tokens"],
        "prompt_cache_miss_tokens": before["prompt_cache_miss_tokens"]
        + usage["prompt_cache_miss_tokens"],
        "completion_tokens": before["completion_tokens"]
        + usage["completion_tokens"],
    }
    budget = evidence.get("budget")
    budget_usage = (
        budget.get("cumulative_usage")
        if isinstance(budget, Mapping)
        else None
    )
    if (
        not isinstance(budget_usage, Mapping)
        or any(
            int(budget_usage.get(field, -1)) != expected
            for field, expected in cumulative.items()
        )
    ):
        raise PublicProviderTraceError(
            "public cumulative usage drifted from prior calls"
        )
    request_cost = role_cost_cny(
        role_policy,
        {
            **usage,
            "total_tokens": int(total_tokens),
        },
    )
    cumulative_cost = role_cost_cny(role_policy, cumulative)
    if round(float(budget.get("cumulative_cost_cny")), 12) != cumulative_cost:
        raise PublicProviderTraceError(
            "public cumulative cost drifted from frozen pricing"
        )
    ceiling = float(role_policy["deepseek"]["abort_ceiling_cny"])
    if cumulative_cost > ceiling:
        raise PublicProviderTraceError(
            "public completed call crossed the role ceiling"
        )
    status = str(budget.get("status", ""))
    if status not in {"continue", "pause_before_next_request"}:
        raise PublicProviderTraceError("public budget status is unsupported")
    return {
        "schema_version": "m3-paper-v2-deepseek-usage-evidence-1.0",
        "call_index": int(commitment["call_index"]),
        "client_request_id": str(commitment["client_request_id"]),
        "provider_response_id": str(evidence["response_id"]),
        "provider_receipt_sha256": sha256_canonical_json(receipt),
        "prompt_tokens": usage["prompt_tokens"],
        "prompt_cache_hit_tokens": usage["prompt_cache_hit_tokens"],
        "prompt_cache_miss_tokens": usage["prompt_cache_miss_tokens"],
        "completion_tokens": usage["completion_tokens"],
        "total_tokens": int(total_tokens),
        "cache_accounting_complete": True,
        "request_cost_cny": request_cost,
        "cumulative_cost_cny": cumulative_cost,
        "budget_status_after_request": status,
    }


def _validate_public_usage(
    value: Mapping[str, Any],
    *,
    commitments: Sequence[Mapping[str, Any]],
    terminal_rows: Mapping[str, Mapping[str, Any]],
    activated: Sequence[Mapping[str, Any]],
    role_policy: Mapping[str, Any],
) -> None:
    items = value["usage_evidence"]
    completed = [
        item
        for item in commitments
        if item["client_request_id"] in terminal_rows
    ]
    if len(items) != len(completed):
        raise PublicProviderTraceError(
            "each completed public request requires one usage row"
        )
    activated_by_id = {
        item["client_request_id"]: item for item in activated
    }
    prior: list[dict[str, Any]] = []
    for commitment, item in zip(completed, items, strict=True):
        request_id = commitment["client_request_id"]
        terminal = terminal_rows[request_id]["event"]
        attestation = activated_by_id.get(request_id)
        if (
            attestation is None
            or item["call_index"] != commitment["call_index"]
            or item["client_request_id"] != request_id
            or item["provider_response_id"]
            != attestation["provider_response_id"]
            or item["provider_receipt_sha256"]
            != terminal["provider_receipt_sha256"]
        ):
            raise PublicProviderTraceError(
                "public usage evidence drifted from the request chain"
            )
        try:
            usage = validate_deepseek_usage(dict(item))
        except BudgetPolicyError as exc:
            raise PublicProviderTraceError(str(exc)) from exc
        expected_request = role_cost_cny(role_policy, usage)
        summary = build_public_usage_summary(
            [*prior, dict(item)],
            role_policy=role_policy,
        )
        if (
            item["cache_accounting_complete"] is not True
            or item["request_cost_cny"] != expected_request
            or item["cumulative_cost_cny"]
            != summary["cumulative_cost_cny"]
            or item["budget_status_after_request"]
            not in {"continue", "pause_before_next_request"}
        ):
            raise PublicProviderTraceError(
                "public usage arithmetic or status drift"
            )
        prior.append(dict(item))
    expected_summary = build_public_usage_summary(
        items,
        role_policy=role_policy,
    )
    if (
        value["usage_summary"] != expected_summary
        or expected_summary["cache_accounting_complete"] is not True
        or expected_summary["within_abort_ceiling"] is not True
    ):
        raise PublicProviderTraceError("public usage summary drift")


def validate_public_trace_bundle(
    value: Any,
    *,
    role_policy: Mapping[str, Any],
    activation_path: Path = pt.DEFAULT_ACTIVATION,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise PublicProviderTraceError("public trace bundle must be an object")
    schema, registry = pt._schema_registry(pt.DEFAULT_SCHEMA)
    Draft202012Validator(
        schema,
        registry=registry,
        format_checker=FormatChecker(),
    ).validate(dict(value))
    if value["bundle_sha256"] != sha256_canonical_json(
        pt._bundle_core(value)
    ):
        raise PublicProviderTraceError("public trace bundle digest drift")
    rows = value["trace_rows"]
    try:
        status = validate_trace_rows(rows)
    except ValueError as exc:
        raise PublicProviderTraceError(
            "public trace row integrity failure"
        ) from exc
    if (
        value["trace_event_count"] != status["event_count"]
        or value["trace_tail_sha256"] != status["tail_sha256"]
        or value["trace_rows_sha256"] != sha256_canonical_json(rows)
        or value["completed_request_count"] != status["completed_requests"]
        or value["open_request_count"] != status["open_requests"]
    ):
        raise PublicProviderTraceError("public trace summary drift")
    commitments = pt._started_commitments(rows)
    if (
        value["request_count"] != len(commitments)
        or [item["call_index"] for item in commitments]
        != list(range(1, len(commitments) + 1))
    ):
        raise PublicProviderTraceError(
            "public request order must be unique and contiguous"
        )
    for commitment in commitments:
        if (
            commitment["execution_identity"] != value["execution_identity"]
            or commitment["work_key"] != value["work_key"]
            or commitment["provider_id"] != value["provider_id"]
            or commitment["model_id"] != value["model_id"]
            or commitment["client_request_id"]
            != pt._expected_client_request_id(commitment)
        ):
            raise PublicProviderTraceError("public bundle identity drift")
    candidates = pt._terminal_candidates(rows)
    terminal_rows = pt._terminal_rows(rows)
    activated = [
        validate_activated_attestation(
            item,
            schema_path=pt.DEFAULT_ATTESTATION_SCHEMA,
        )
        for item in value["activated_attestations"]
    ]
    if (
        len(activated) != len(candidates)
        or [item["client_request_id"] for item in activated]
        != [
            item["client_request_id"]
            for item in commitments
            if item["client_request_id"] in candidates
        ]
    ):
        raise PublicProviderTraceError("public activation ordering drift")
    activation_digest = hashlib.sha256(activation_path.read_bytes()).hexdigest()
    comparable = (
        "trace_mode",
        "client_request_id",
        "provider_request_id",
        "provider_response_id",
        "provider_id",
        "model_id",
        "payload_sha256",
        "commitment_sha256",
        "started_event_sha256",
    )
    for attestation in activated:
        candidate = candidates[attestation["client_request_id"]]
        if (
            any(
                attestation[field] != candidate[field]
                for field in comparable
            )
            or attestation["activation_manifest_sha256"] != activation_digest
        ):
            raise PublicProviderTraceError("public activation binding drift")
    response_ids = [item["provider_response_id"] for item in activated]
    if len(response_ids) != len(set(response_ids)):
        raise PublicProviderTraceError(
            "public response identities must be unique"
        )
    _validate_public_usage(
        value,
        commitments=commitments,
        terminal_rows=terminal_rows,
        activated=activated,
        role_policy=role_policy,
    )
    terminal_ids = set(candidates)
    open_ids = {
        item["client_request_id"]
        for item in commitments
        if item["client_request_id"] not in terminal_ids
    }
    failures = value["failures"]
    if {item["client_request_id"] for item in failures} != open_ids:
        raise PublicProviderTraceError(
            "public open requests and failures do not match"
        )
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
        value["bundle_status"] != expected_status
        or value["result_tier_ceiling"] != expected_tier
    ):
        raise PublicProviderTraceError("public bundle status drift")
    return copy.deepcopy(dict(value))


def build_public_trace_bundle(
    *,
    trace_path: Path,
    execution_identity: str,
    work_key: str,
    provider_id: str,
    model_id: str,
    activated_attestations: Mapping[str, Mapping[str, Any]],
    usage_evidence: Mapping[str, Mapping[str, Any]],
    failures: Mapping[str, Mapping[str, str]],
    role_policy: Mapping[str, Any],
    activation_path: Path = pt.DEFAULT_ACTIVATION,
) -> dict[str, Any]:
    rows = pt.load_trace_rows(trace_path)
    status = validate_trace_rows(rows)
    commitments = pt._started_commitments(rows)
    ordered_activated = [
        copy.deepcopy(dict(activated_attestations[item["client_request_id"]]))
        for item in commitments
        if item["client_request_id"] in activated_attestations
    ]
    ordered_failures = [
        copy.deepcopy(dict(failures[item["client_request_id"]]))
        for item in commitments
        if item["client_request_id"] in failures
    ]
    ordered_usage = [
        copy.deepcopy(dict(usage_evidence[item["client_request_id"]]))
        for item in commitments
        if item["client_request_id"] in usage_evidence
    ]
    status_name = "completed"
    tier = "formal_candidate"
    if ordered_failures:
        status_name = {
            "provider_failure": "incomplete_provider_failure",
            "paused": "incomplete_paused",
            "evidence_failure": "incomplete_evidence_failure",
        }[ordered_failures[0]["status"]]
        tier = "diagnostic"
    core = {
        "schema_version": pt.BUNDLE_SCHEMA_VERSION,
        "execution_identity": execution_identity,
        "work_key": work_key,
        "provider_id": provider_id,
        "model_id": model_id,
        "bundle_status": status_name,
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
        "usage_summary": build_public_usage_summary(
            ordered_usage,
            role_policy=role_policy,
        ),
        "failures": ordered_failures,
        "append_flush_fsync": True,
        "automatic_retry": False,
        "provider_tools_declared": False,
        "external_effects_enabled": False,
        "prompt_or_response_content_stored": False,
    }
    value = {**core, "bundle_sha256": sha256_canonical_json(core)}
    return validate_public_trace_bundle(
        value,
        role_policy=role_policy,
        activation_path=activation_path,
    )


class PublicDeepSeekJsonTracedProviderClient(pt.TracedProviderClient):
    """追踪确切 JSON 载荷与公开角色缓存成本。"""

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        case: dict[str, Any] | None = None,
        step: int = 1,
        observations: list[Any] | None = None,
    ) -> OfficialProviderCompletion:
        attempt_id = self._attempt_id(step)
        commitment = build_json_request_commitment(
            self._client,
            messages,
            execution_identity=self.execution_identity,
            work_key=self.work_key,
            call_index=step,
            attempt_id=attempt_id,
            precommitted_at=self.recorded_at(),
        )
        started = append_started_trace(self.trace_path, commitment)
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
            candidate = bind_trace_attestation(
                commitment,
                receipt,
                started_event_sha256=started["event_sha256"],
            )
            activated = activate_trace_attestation(
                candidate,
                activation_path=self.activation_path,
            )
            usage = build_public_usage_evidence(
                receipt,
                commitment,
                prior_items=list(self._usage_evidence.values()),
                role_policy=self.policy,
            )
            terminal = append_completed_trace(
                self.trace_path,
                client_request_id=commitment["client_request_id"],
                receipt=receipt,
            )
            if terminal["event"]["attestation"] != candidate:
                raise PublicProviderTraceError(
                    "public terminal trace drifted after activation"
                )
            self._activated[commitment["client_request_id"]] = activated
            self._usage_evidence[commitment["client_request_id"]] = usage
            return completion
        except Exception as exc:
            status = (
                "paused"
                if isinstance(exc, ProviderPausedError)
                else (
                    "evidence_failure"
                    if phase == "evidence_completion"
                    else "provider_failure"
                )
            )
            self._failures[commitment["client_request_id"]] = {
                "client_request_id": commitment["client_request_id"],
                "status": status,
                "error_type": type(exc).__name__,
            }
            if (
                started["event"]["client_request_id"]
                != commitment["client_request_id"]
            ):
                raise PublicProviderTraceError(
                    "persisted public start does not bind the call"
                ) from exc
            raise

    def build_bundle(self) -> dict[str, Any]:
        return build_public_trace_bundle(
            trace_path=self.trace_path,
            execution_identity=self.execution_identity,
            work_key=self.work_key,
            provider_id=self.provider_id,
            model_id=self.model,
            activated_attestations=self._activated,
            usage_evidence=self._usage_evidence,
            failures=self._failures,
            role_policy=self.policy,
            activation_path=self.activation_path,
        )
