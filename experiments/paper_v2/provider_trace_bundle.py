"""封装单次实验有序、前瞻性提供商请求证据的轨迹包结构。

聚合每次交互的请求报文、应答报文、Token 计量及对应校验摘要。
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from experiments.paper_v2.contracts import (
    PaperV2ContractError,
    sha256_canonical_json,
)
from experiments.paper_v2.official_provider_executor import (
    OfficialProviderClient,
    OfficialProviderCompletion,
    ProviderPausedError,
    validate_provider_receipt,
)
from experiments.paper_v2.provider_budget import (
    DEFAULT_POLICY as DEFAULT_BUDGET_POLICY,
    deepseek_cost_cny,
    validate_deepseek_usage,
)
from experiments.paper_v2.provider_request_trace_activation import (
    DEFAULT_OUTPUT as DEFAULT_ACTIVATION,
    activate_trace_attestation,
    validate_activated_attestation,
)
from experiments.paper_v2.provider_request_trace_candidate import (
    append_completed_trace,
    append_started_trace,
    bind_trace_attestation,
    build_request_commitment,
    load_trace_rows,
    validate_request_commitment,
    validate_trace_attestation,
    validate_trace_rows,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCHEMA = (
    PROJECT_ROOT
    / "schemas/paper_v2/provider_trace_bundle_v2.schema.json"
)
DEFAULT_ATTESTATION_SCHEMA = (
    PROJECT_ROOT
    / "schemas/paper_v2/provider_trace_attestation_v2.schema.json"
)
BUNDLE_SCHEMA_VERSION = "m3-paper-v2-provider-trace-bundle-2.1"


class ProviderTraceBundleError(PaperV2ContractError):
    """当请求包不完整、模糊或被篡改时抛出的异常。"""


def _load_schema(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not isinstance(value.get("$id"), str):
        raise ProviderTraceBundleError(f"{path}: invalid JSON schema")
    return value


def _schema_registry(
    schema_path: Path,
) -> tuple[dict[str, Any], Registry]:
    schemas = [
        _load_schema(schema_path),
        _load_schema(DEFAULT_ATTESTATION_SCHEMA),
    ]
    registry = Registry().with_resources(
        [
            (schema["$id"], Resource.from_contents(schema))
            for schema in schemas
        ]
    )
    return schemas[0], registry


def _bundle_core(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: copy.deepcopy(child)
        for key, child in value.items()
        if key != "bundle_sha256"
    }


def _expected_client_request_id(
    commitment: Mapping[str, Any],
) -> str:
    identity = {
        "execution_identity": commitment["execution_identity"],
        "work_key": commitment["work_key"],
        "call_index": commitment["call_index"],
        "attempt_id": commitment["attempt_id"],
        "provider_id": commitment["provider_id"],
        "model_id": commitment["model_id"],
        "payload_sha256": commitment["payload_sha256"],
    }
    return "m3req-" + sha256_canonical_json(identity)[:32]


def _terminal_candidates(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        event = row["event"]
        if event["event_type"] != "completed":
            continue
        candidate = validate_trace_attestation(event["attestation"])
        result[str(candidate["client_request_id"])] = candidate
    return result


def _terminal_rows(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    return {
        str(row["event"]["client_request_id"]): row
        for row in rows
        if row["event"]["event_type"] == "completed"
    }


def _started_commitments(
    rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    return [
        validate_request_commitment(row["event"]["commitment"])
        for row in rows
        if row["event"]["event_type"] == "started"
    ]


def _load_budget_policy(
    path: Path = DEFAULT_BUDGET_POLICY,
) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ProviderTraceBundleError("budget policy must be an object")
    return value


def _normalized_cost(value: Any) -> float:
    return round(float(value), 12)


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


def build_deepseek_usage_summary(
    items: Sequence[Mapping[str, Any]],
    *,
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    """汇总单个工作项的无内容缓存和成本论据。"""

    totals = _usage_totals(items)
    expected_cost = _normalized_cost(
        deepseek_cost_cny(
            dict(policy),
            cache_hit_input_tokens=totals["prompt_cache_hit_tokens"],
            cache_miss_input_tokens=totals["prompt_cache_miss_tokens"],
            output_tokens=totals["completion_tokens"],
        )
    )
    ceiling = float(policy["deepseek"]["abort_ceiling_cny"])
    return {
        "completed_call_count": len(items),
        **totals,
        "cache_accounting_complete": (
            totals["prompt_tokens"]
            == totals["prompt_cache_hit_tokens"]
            + totals["prompt_cache_miss_tokens"]
        ),
        "cumulative_cost_cny": expected_cost,
        "abort_ceiling_cny": ceiling,
        "within_abort_ceiling": expected_cost <= ceiling,
    }


def build_deepseek_usage_evidence(
    receipt: Mapping[str, Any],
    commitment: Mapping[str, Any],
    *,
    prior_items: Sequence[Mapping[str, Any]],
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    """将单个官方收据投影到无内容的缓存/成本行。"""

    validate_provider_receipt(receipt)
    evidence = receipt["evidence"]
    if (
        evidence.get("provider_id") != "deepseek"
        or evidence.get("returned_model") != commitment["model_id"]
        or evidence.get("payload_sha256") != commitment["payload_sha256"]
        or not evidence.get("response_id")
    ):
        raise ProviderTraceBundleError(
            "DeepSeek usage receipt does not bind the request commitment"
        )
    usage_raw = evidence.get("usage")
    if not isinstance(usage_raw, Mapping):
        raise ProviderTraceBundleError("DeepSeek usage receipt is missing")
    usage = validate_deepseek_usage(dict(usage_raw))
    total_tokens = usage_raw.get("total_tokens")
    if (
        isinstance(total_tokens, bool)
        or not isinstance(total_tokens, int)
        or total_tokens
        < usage["prompt_tokens"] + usage["completion_tokens"]
    ):
        raise ProviderTraceBundleError(
            "DeepSeek total-token accounting is incomplete"
        )
    totals_before = _usage_totals(prior_items)
    cumulative = {
        "prompt_tokens": totals_before["prompt_tokens"]
        + usage["prompt_tokens"],
        "prompt_cache_hit_tokens": totals_before[
            "prompt_cache_hit_tokens"
        ]
        + usage["prompt_cache_hit_tokens"],
        "prompt_cache_miss_tokens": totals_before[
            "prompt_cache_miss_tokens"
        ]
        + usage["prompt_cache_miss_tokens"],
        "completion_tokens": totals_before["completion_tokens"]
        + usage["completion_tokens"],
    }
    budget = evidence.get("budget")
    if not isinstance(budget, Mapping):
        raise ProviderTraceBundleError("DeepSeek budget evidence is missing")
    budget_usage = budget.get("cumulative_usage")
    if (
        not isinstance(budget_usage, Mapping)
        or any(
            int(budget_usage.get(field, -1)) != expected
            for field, expected in cumulative.items()
        )
    ):
        raise ProviderTraceBundleError(
            "DeepSeek cumulative usage drifted from prior calls"
        )
    request_cost = _normalized_cost(
        deepseek_cost_cny(
            dict(policy),
            cache_hit_input_tokens=usage["prompt_cache_hit_tokens"],
            cache_miss_input_tokens=usage["prompt_cache_miss_tokens"],
            output_tokens=usage["completion_tokens"],
        )
    )
    cumulative_cost = _normalized_cost(
        deepseek_cost_cny(
            dict(policy),
            cache_hit_input_tokens=cumulative["prompt_cache_hit_tokens"],
            cache_miss_input_tokens=cumulative["prompt_cache_miss_tokens"],
            output_tokens=cumulative["completion_tokens"],
        )
    )
    if _normalized_cost(budget.get("cumulative_cost_cny")) != cumulative_cost:
        raise ProviderTraceBundleError(
            "DeepSeek cumulative CNY cost drifted from frozen pricing"
        )
    ceiling = float(policy["deepseek"]["abort_ceiling_cny"])
    if cumulative_cost > ceiling:
        raise ProviderTraceBundleError(
            "DeepSeek completed call crossed the approved abort ceiling"
        )
    status = str(budget.get("status", ""))
    if status not in {"continue", "pause_before_next_request"}:
        raise ProviderTraceBundleError(
            "DeepSeek budget status after request is unsupported"
        )
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
        "total_tokens": total_tokens,
        "cache_accounting_complete": True,
        "request_cost_cny": request_cost,
        "cumulative_cost_cny": cumulative_cost,
        "budget_status_after_request": status,
    }


def _validate_usage_evidence(
    value: Mapping[str, Any],
    *,
    commitments: Sequence[Mapping[str, Any]],
    terminal_rows: Mapping[str, Mapping[str, Any]],
    activated: Sequence[Mapping[str, Any]],
    policy: Mapping[str, Any],
) -> None:
    items = value["usage_evidence"]
    completed_commitments = [
        item
        for item in commitments
        if item["client_request_id"] in terminal_rows
    ]
    if len(items) != len(completed_commitments):
        raise ProviderTraceBundleError(
            "completed requests require one cache/cost evidence row each"
        )
    activated_by_id = {
        item["client_request_id"]: item for item in activated
    }
    prior: list[dict[str, Any]] = []
    for commitment, item in zip(completed_commitments, items, strict=True):
        request_id = commitment["client_request_id"]
        terminal = terminal_rows[request_id]["event"]
        attestation = activated_by_id.get(request_id)
        if attestation is None:
            raise ProviderTraceBundleError(
                "usage evidence lacks an activated request binding"
            )
        if (
            item["call_index"] != commitment["call_index"]
            or item["client_request_id"] != request_id
            or item["provider_response_id"]
            != attestation["provider_response_id"]
            or item["provider_receipt_sha256"]
            != terminal["provider_receipt_sha256"]
        ):
            raise ProviderTraceBundleError(
                "cache/cost evidence drifted from the provider trace"
            )
        usage = validate_deepseek_usage(dict(item))
        if item["total_tokens"] < (
            usage["prompt_tokens"] + usage["completion_tokens"]
        ):
            raise ProviderTraceBundleError(
                "DeepSeek total-token accounting drift"
            )
        expected_request_cost = _normalized_cost(
            deepseek_cost_cny(
                dict(policy),
                cache_hit_input_tokens=usage[
                    "prompt_cache_hit_tokens"
                ],
                cache_miss_input_tokens=usage[
                    "prompt_cache_miss_tokens"
                ],
                output_tokens=usage["completion_tokens"],
            )
        )
        cumulative_items = [*prior, dict(item)]
        expected_summary = build_deepseek_usage_summary(
            cumulative_items,
            policy=policy,
        )
        if (
            item["cache_accounting_complete"] is not True
            or item["request_cost_cny"] != expected_request_cost
            or item["cumulative_cost_cny"]
            != expected_summary["cumulative_cost_cny"]
            or item["budget_status_after_request"]
            not in {"continue", "pause_before_next_request"}
        ):
            raise ProviderTraceBundleError(
                "cache/cost evidence arithmetic drift"
            )
        prior.append(dict(item))
    expected_summary = build_deepseek_usage_summary(prior, policy=policy)
    if dict(value["usage_summary"]) != expected_summary:
        raise ProviderTraceBundleError(
            "provider cache/cost summary drift"
        )
    if (
        expected_summary["cache_accounting_complete"] is not True
        or expected_summary["within_abort_ceiling"] is not True
    ):
        raise ProviderTraceBundleError(
            "provider cache/cost evidence violates the frozen budget"
        )


def validate_provider_trace_bundle(
    value: Any,
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    activation_path: Path = DEFAULT_ACTIVATION,
    budget_policy_path: Path = DEFAULT_BUDGET_POLICY,
) -> dict[str, Any]:
    """验证 Schema、哈希链、调用顺序和激活绑定。"""

    if not isinstance(value, Mapping):
        raise ProviderTraceBundleError("provider trace bundle must be an object")
    schema, registry = _schema_registry(schema_path)
    Draft202012Validator(
        schema,
        registry=registry,
        format_checker=FormatChecker(),
    ).validate(dict(value))
    if value["bundle_sha256"] != sha256_canonical_json(_bundle_core(value)):
        raise ProviderTraceBundleError("provider trace bundle digest drift")

    rows = value["trace_rows"]
    try:
        status = validate_trace_rows(rows)
    except ValueError as exc:
        raise ProviderTraceBundleError(
            "provider trace rows failed integrity validation"
        ) from exc
    if (
        value["trace_event_count"] != status["event_count"]
        or value["trace_tail_sha256"] != status["tail_sha256"]
        or value["trace_rows_sha256"] != sha256_canonical_json(rows)
        or value["completed_request_count"] != status["completed_requests"]
        or value["open_request_count"] != status["open_requests"]
    ):
        raise ProviderTraceBundleError("provider trace summary drift")

    commitments = _started_commitments(rows)
    if value["request_count"] != len(commitments):
        raise ProviderTraceBundleError("provider request count drift")
    if [item["call_index"] for item in commitments] != list(
        range(1, len(commitments) + 1)
    ):
        raise ProviderTraceBundleError(
            "provider calls must be unique and contiguous"
        )
    for commitment in commitments:
        if (
            commitment["execution_identity"] != value["execution_identity"]
            or commitment["work_key"] != value["work_key"]
            or commitment["provider_id"] != value["provider_id"]
            or commitment["model_id"] != value["model_id"]
            or commitment["client_request_id"]
            != _expected_client_request_id(commitment)
        ):
            raise ProviderTraceBundleError(
                "provider commitment does not bind the bundle identity"
            )

    candidates = _terminal_candidates(rows)
    terminal_rows = _terminal_rows(rows)
    activated = [
        validate_activated_attestation(
            item,
            schema_path=DEFAULT_ATTESTATION_SCHEMA,
        )
        for item in value["activated_attestations"]
    ]
    if len(activated) != len(candidates):
        raise ProviderTraceBundleError(
            "completed requests require one activated attestation each"
        )
    if [item["client_request_id"] for item in activated] != [
        item["client_request_id"]
        for item in commitments
        if item["client_request_id"] in candidates
    ]:
        raise ProviderTraceBundleError(
            "activated attestations are not in provider call order"
        )
    activation_digest = hashlib.sha256(
        activation_path.read_bytes()
    ).hexdigest()
    comparable_fields = (
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
        if any(
            attestation[field] != candidate[field]
            for field in comparable_fields
        ):
            raise ProviderTraceBundleError(
                "activated trace drifted from its durable terminal event"
            )
        if attestation["activation_manifest_sha256"] != activation_digest:
            raise ProviderTraceBundleError(
                "activated trace does not bind the approval manifest"
            )
    response_ids = [
        item["provider_response_id"] for item in activated
    ]
    if len(response_ids) != len(set(response_ids)):
        raise ProviderTraceBundleError(
            "provider response IDs must be unique within a bundle"
        )
    _validate_usage_evidence(
        value,
        commitments=commitments,
        terminal_rows=terminal_rows,
        activated=activated,
        policy=_load_budget_policy(budget_policy_path),
    )

    terminal_ids = set(candidates)
    open_ids = {
        item["client_request_id"]
        for item in commitments
        if item["client_request_id"] not in terminal_ids
    }
    failures = value["failures"]
    if {item["client_request_id"] for item in failures} != open_ids:
        raise ProviderTraceBundleError(
            "open request and failure evidence do not match"
        )
    expected_bundle_status = "completed"
    expected_ceiling = "formal_candidate"
    if failures:
        failure_status = failures[0]["status"]
        expected_bundle_status = {
            "provider_failure": "incomplete_provider_failure",
            "paused": "incomplete_paused",
            "evidence_failure": "incomplete_evidence_failure",
        }[failure_status]
        expected_ceiling = "diagnostic"
    if (
        value["bundle_status"] != expected_bundle_status
        or value["result_tier_ceiling"] != expected_ceiling
    ):
        raise ProviderTraceBundleError("provider bundle status drift")
    return copy.deepcopy(dict(value))


def build_provider_trace_bundle(
    *,
    trace_path: Path,
    execution_identity: str,
    work_key: str,
    provider_id: str,
    model_id: str,
    activated_attestations: Mapping[str, Mapping[str, Any]],
    usage_evidence: Mapping[str, Mapping[str, Any]],
    failures: Mapping[str, Mapping[str, str]],
    activation_path: Path = DEFAULT_ACTIVATION,
    budget_policy_path: Path = DEFAULT_BUDGET_POLICY,
) -> dict[str, Any]:
    rows = load_trace_rows(trace_path)
    status = validate_trace_rows(rows)
    commitments = _started_commitments(rows)
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
    policy = _load_budget_policy(budget_policy_path)
    bundle_status = "completed"
    tier = "formal_candidate"
    if ordered_failures:
        bundle_status = {
            "provider_failure": "incomplete_provider_failure",
            "paused": "incomplete_paused",
            "evidence_failure": "incomplete_evidence_failure",
        }[ordered_failures[0]["status"]]
        tier = "diagnostic"
    core = {
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "execution_identity": execution_identity,
        "work_key": work_key,
        "provider_id": provider_id,
        "model_id": model_id,
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
        "usage_summary": build_deepseek_usage_summary(
            ordered_usage,
            policy=policy,
        ),
        "failures": ordered_failures,
        "append_flush_fsync": True,
        "automatic_retry": False,
        "provider_tools_declared": False,
        "external_effects_enabled": False,
        "prompt_or_response_content_stored": False,
    }
    value = {**core, "bundle_sha256": sha256_canonical_json(core)}
    return validate_provider_trace_bundle(
        value,
        activation_path=activation_path,
        budget_policy_path=budget_policy_path,
    )


class TracedProviderClient:
    """预先提交每个提供商传输的单工作项包装器。"""

    def __init__(
        self,
        client: OfficialProviderClient,
        *,
        execution_identity: str,
        work_key: str,
        trace_path: Path,
        recorded_at: Callable[[], str],
        receipt_adapter: (
            Callable[[Mapping[str, Any]], Mapping[str, Any]] | None
        ) = None,
        activation_path: Path = DEFAULT_ACTIVATION,
        physical_attempt_namespace: int = 1,
    ) -> None:
        if (
            isinstance(physical_attempt_namespace, bool)
            or not isinstance(physical_attempt_namespace, int)
            or physical_attempt_namespace < 1
        ):
            raise ProviderTraceBundleError(
                "physical attempt namespace must be a positive integer"
            )
        if trace_path.exists() and trace_path.stat().st_size:
            raise ProviderTraceBundleError(
                "automatic resume/retry of an existing trace is forbidden"
            )
        self._client = client
        self.execution_identity = execution_identity
        self.work_key = work_key
        self.trace_path = trace_path
        self.recorded_at = recorded_at
        self.receipt_adapter = receipt_adapter
        self.activation_path = activation_path
        self.physical_attempt_namespace = physical_attempt_namespace
        self._activated: dict[str, dict[str, Any]] = {}
        self._usage_evidence: dict[str, dict[str, Any]] = {}
        self._failures: dict[str, dict[str, str]] = {}

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)

    def _attempt_id(self, call_index: int) -> str:
        identity = {
            "execution_identity": self.execution_identity,
            "work_key": self.work_key,
            "call_index": call_index,
        }
        if self.physical_attempt_namespace > 1:
            identity["physical_attempt_namespace"] = (
                self.physical_attempt_namespace
            )
        return "attempt-" + sha256_canonical_json(identity)[:24]

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        case: dict[str, Any] | None = None,
        step: int = 1,
        observations: list[Any] | None = None,
    ) -> OfficialProviderCompletion:
        attempt_id = self._attempt_id(step)
        commitment = build_request_commitment(
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
            usage = build_deepseek_usage_evidence(
                receipt,
                commitment,
                prior_items=list(self._usage_evidence.values()),
                policy=self.policy,
            )
            terminal = append_completed_trace(
                self.trace_path,
                client_request_id=commitment["client_request_id"],
                receipt=receipt,
            )
            if terminal["event"]["attestation"] != candidate:
                raise ProviderTraceBundleError(
                    "terminal trace drifted after activation prevalidation"
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
            if started["event"]["client_request_id"] != commitment[
                "client_request_id"
            ]:
                raise ProviderTraceBundleError(
                    "persisted start does not bind the attempted call"
                ) from exc
            raise

    def build_bundle(self) -> dict[str, Any]:
        return build_provider_trace_bundle(
            trace_path=self.trace_path,
            execution_identity=self.execution_identity,
            work_key=self.work_key,
            provider_id=self.provider_id,
            model_id=self.model,
            activated_attestations=self._activated,
            usage_evidence=self._usage_evidence,
            failures=self._failures,
            activation_path=self.activation_path,
        )
