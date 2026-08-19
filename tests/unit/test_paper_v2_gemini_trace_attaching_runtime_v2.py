from __future__ import annotations

import copy
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping

import pytest

import experiments.paper_v2.experiment_closeout_freeze_v1 as freeze
import experiments.paper_v2.gemini_fallback_controller_v2 as fallback
import experiments.paper_v2.gemini_public_execution_store_v1 as store
import experiments.paper_v2.gemini_public_trace_v1 as gemini_trace
import experiments.paper_v2.gemini_trace_attaching_runtime_v2 as runtime_v2
from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.official_provider_executor import (
    HTTPResponseEnvelope,
    OfficialProviderClient,
    ProviderBudgetState,
    provider_receipt_to_attestation,
)
from experiments.paper_v2.provider_safety import build_safety_receipt
from experiments.paper_v2.public_matrix_plan_v1 import hydrate_public_work_item


MESSAGES = [
    {"role": "system", "content": "Return JSON only."},
    {"role": "user", "content": "Synthetic prospective contract."},
]


def _official_adapter(receipt: Mapping[str, Any]) -> dict[str, Any]:
    value = copy.deepcopy(dict(receipt))
    value["evidence"]["transport_kind"] = "official_network"
    value["evidence_sha256"] = sha256_canonical_json(value["evidence"])
    return value


def _client_and_attestation(
    tmp_path: Path,
    *,
    provider_request_id: str | None,
    execution_identity: str = "execution-v2-test",
    work_key: str = "work-v2-test",
) -> tuple[gemini_trace.GeminiPublicTracedProviderClient, dict[str, Any]]:
    policy = fallback._effective_policy()

    def transport(*_: Any) -> HTTPResponseEnvelope:
        headers = (
            {"x-goog-request-id": provider_request_id}
            if provider_request_id is not None
            else {}
        )
        return HTTPResponseEnvelope(
            status_code=200,
            headers=headers,
            body={
                "id": "gemini-response-v2-test",
                "model": "gemini-3.6-flash",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": '{"tool":"final","arguments":{"answer":"SAFE"}}',
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 20,
                    "completion_tokens": 4,
                    "total_tokens": 24,
                },
            },
        )

    official = OfficialProviderClient(
        provider_id="gemini",
        api_key="unit-test-key",
        content_class="synthetic_m3_case",
        budget_state=ProviderBudgetState(provider_id="gemini", policy=policy),
        policy=policy,
        temperature=0.0,
        max_tokens=64,
        timeout=30.0,
        network_consent=False,
        transport=transport,
    )
    client = gemini_trace.GeminiPublicTracedProviderClient(
        official,
        execution_identity=execution_identity,
        work_key=work_key,
        trace_path=tmp_path / "trace.jsonl",
        admission_manifest_sha256="a" * 64,
        recorded_at=lambda: "2026-08-04T02:00:00+08:00",
        receipt_adapter=_official_adapter,
    )
    completion = client.complete(MESSAGES, step=1)
    attestation = provider_receipt_to_attestation(
        _official_adapter(completion.receipt)
    )
    return client, attestation


class _Delegate:
    def __init__(self, value: Mapping[str, Any]) -> None:
        self.value = value

    def execute(self, context: Any, profile: Any) -> Mapping[str, Any]:
        del context, profile
        return copy.deepcopy(dict(self.value))


def _execute(
    client: gemini_trace.GeminiPublicTracedProviderClient,
    observed: Mapping[str, Any],
    *,
    execution_identity: str = "execution-v2-test",
    work_key: str = "work-v2-test",
) -> Mapping[str, Any]:
    runtime = runtime_v2.GeminiTraceAttachingRuntimeV2(
        _Delegate(observed),
        client_lookup=lambda work_key: (
            client if work_key == client.work_key else None
        ),
    )
    context = SimpleNamespace(
        execution_identity=execution_identity,
        work_key=work_key,
    )
    return runtime.execute(context, None)


def test_missing_provider_request_id_is_narrowly_promoted(tmp_path: Path) -> None:
    client, attestation = _client_and_attestation(
        tmp_path,
        provider_request_id=None,
    )
    assert attestation["evidence_level"] == "diagnostic_only"

    result = _execute(
        client,
        {"result_tier": "diagnostic", "provider_attestation": attestation},
    )

    formal = result["provider_attestation"]
    assert result["result_tier"] == "formal_candidate"
    assert formal["request_id"] is None
    assert formal["provider_request_id_available"] is False
    assert formal["client_request_id"].startswith("m3req-")
    assert formal["request_identity_mode"] == (
        "precommitted_local_plus_provider_response"
    )
    assert formal["formal_evidence_contract"] == runtime_v2.CONTRACT_ID
    assert result["provider_trace_bundle"]["result_tier_ceiling"] == (
        "formal_candidate"
    )


def test_provider_dual_id_path_remains_formal(tmp_path: Path) -> None:
    client, attestation = _client_and_attestation(
        tmp_path,
        provider_request_id="gemini-request-v2-test",
    )
    assert attestation["evidence_level"] == "formal_candidate"

    result = _execute(
        client,
        {"result_tier": "formal_candidate", "provider_attestation": attestation},
    )

    formal = result["provider_attestation"]
    assert result["result_tier"] == "formal_candidate"
    assert formal["request_id"] == "gemini-request-v2-test"
    assert formal["provider_request_id_available"] is True
    assert formal["request_identity_mode"] == (
        "provider_dual_id_plus_precommitted_local"
    )


def test_post_response_failure_with_complete_bundle_gets_attestation(
    tmp_path: Path,
) -> None:
    client, _ = _client_and_attestation(
        tmp_path,
        provider_request_id=None,
    )

    result = _execute(client, {"result_tier": "formal_candidate"})

    assert result["result_tier"] == "formal_candidate"
    assert result["provider_attestation"]["request_id"] is None
    assert result["provider_attestation"]["formal_evidence_contract"] == (
        runtime_v2.CONTRACT_ID
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("provider_name", "Other"),
        ("model_id", "other-model"),
        ("response_id", "other-response"),
        ("response_id", None),
        ("parameters_sha256", "b" * 64),
        ("prompt_rewrite_declaration", "unknown"),
        ("identity_verified", False),
        ("evidence_level", "formal_candidate"),
        ("request_id", "invented-provider-request"),
    ],
)
def test_missing_id_promotion_rejects_attestation_drift(
    tmp_path: Path,
    field: str,
    value: Any,
) -> None:
    client, attestation = _client_and_attestation(
        tmp_path,
        provider_request_id=None,
    )
    attestation[field] = value

    with pytest.raises(runtime_v2.GeminiTraceAttachingRuntimeV2Error):
        _execute(
            client,
            {"result_tier": "diagnostic", "provider_attestation": attestation},
        )


def test_conflicting_runtime_bundle_is_rejected(tmp_path: Path) -> None:
    client, attestation = _client_and_attestation(
        tmp_path,
        provider_request_id=None,
    )
    conflicting = copy.deepcopy(client.build_bundle())
    conflicting["work_key"] = "other-work"

    with pytest.raises(
        runtime_v2.GeminiTraceAttachingRuntimeV2Error,
        match="conflicting trace bundle",
    ):
        _execute(
            client,
            {
                "result_tier": "diagnostic",
                "provider_attestation": attestation,
                "provider_trace_bundle": conflicting,
            },
        )


def test_qualification_tier_cannot_enter_formal_path(tmp_path: Path) -> None:
    client, attestation = _client_and_attestation(
        tmp_path,
        provider_request_id=None,
    )

    with pytest.raises(
        runtime_v2.GeminiTraceAttachingRuntimeV2Error,
        match="outside the prospective formal path",
    ):
        _execute(
            client,
            {"result_tier": "qualification", "provider_attestation": attestation},
        )


def test_tampered_trace_bundle_is_rejected(tmp_path: Path) -> None:
    client, attestation = _client_and_attestation(
        tmp_path,
        provider_request_id=None,
    )
    tampered = copy.deepcopy(client.build_bundle())
    tampered["usage_summary"]["paid_ceiling_usd"] = 1.0

    class _TamperedClient:
        def build_bundle(self) -> Mapping[str, Any]:
            return tampered

    runtime = runtime_v2.GeminiTraceAttachingRuntimeV2(
        _Delegate(
            {"result_tier": "diagnostic", "provider_attestation": attestation}
        ),
        client_lookup=lambda _: _TamperedClient(),
    )
    context = SimpleNamespace(
        execution_identity="execution-v2-test",
        work_key="work-v2-test",
    )
    with pytest.raises(Exception, match="bundle envelope drift"):
        runtime.execute(context, None)


def test_trace_mode_cannot_claim_a_missing_provider_request_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, attestation = _client_and_attestation(
        tmp_path,
        provider_request_id=None,
    )
    inconsistent = copy.deepcopy(client.build_bundle())
    inconsistent["activated_attestations"][-1]["trace_mode"] = (
        "provider_dual_id_plus_precommitted_local"
    )
    monkeypatch.setattr(
        runtime_v2,
        "validate_trace_bundle",
        lambda _: copy.deepcopy(inconsistent),
    )

    with pytest.raises(
        runtime_v2.GeminiTraceAttachingRuntimeV2Error,
        match="trace mode and provider request identity disagree",
    ):
        _execute(
            client,
            {"result_tier": "diagnostic", "provider_attestation": attestation},
        )


def test_nonzero_paid_tier_claim_cannot_be_promoted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, attestation = _client_and_attestation(
        tmp_path,
        provider_request_id=None,
    )
    charged = copy.deepcopy(client.build_bundle())
    charged["usage_summary"]["charged_usd"] = 1.0
    monkeypatch.setattr(
        runtime_v2,
        "validate_trace_bundle",
        lambda _: copy.deepcopy(charged),
    )

    with pytest.raises(
        runtime_v2.GeminiTraceAttachingRuntimeV2Error,
        match="complete free-tier formal candidate",
    ):
        _execute(
            client,
            {"result_tier": "diagnostic", "provider_attestation": attestation},
        )


def test_incomplete_bundle_cannot_retain_completed_response_claim(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, attestation = _client_and_attestation(
        tmp_path,
        provider_request_id=None,
    )
    incomplete = copy.deepcopy(client.build_bundle())
    incomplete["bundle_status"] = "incomplete_provider_failure"
    incomplete["result_tier_ceiling"] = "diagnostic"
    incomplete["open_request_count"] = 1
    incomplete["failures"] = [
        {
            "client_request_id": incomplete["activated_attestations"][-1][
                "client_request_id"
            ],
            "status": "provider_failure",
            "error_type": "SyntheticFailure",
        }
    ]
    monkeypatch.setattr(
        runtime_v2,
        "validate_trace_bundle",
        lambda _: copy.deepcopy(incomplete),
    )

    with pytest.raises(
        runtime_v2.GeminiTraceAttachingRuntimeV2Error,
        match="cannot retain a response claim",
    ):
        _execute(
            client,
            {"result_tier": "diagnostic", "provider_attestation": attestation},
        )


def test_no_secret_or_prompt_is_persisted(tmp_path: Path) -> None:
    client, attestation = _client_and_attestation(
        tmp_path,
        provider_request_id=None,
    )
    result = _execute(
        client,
        {"result_tier": "diagnostic", "provider_attestation": attestation},
    )
    serialized = repr(result)
    assert "unit-test-key" not in serialized
    assert "Synthetic prospective contract" not in serialized


def test_promoted_chain_is_persistable_in_gemini_record_store(
    tmp_path: Path,
) -> None:
    item = freeze.build_gemini_public_plan()[0]
    execution_identity = str(item["execution_identity"])
    work_key = str(item["work_key"])
    client, attestation = _client_and_attestation(
        tmp_path,
        provider_request_id=None,
        execution_identity=execution_identity,
        work_key=work_key,
    )
    arguments = {"answer": "SAFE"}
    event = {
        "step": 1,
        "parse_ok": True,
        "parse_error_code": None,
        "action_proposal": {
            "tool": "final",
            "arguments": arguments,
            "arguments_sha256": sha256_canonical_json(arguments),
        },
        "guard_decision": {
            "decision": "ALLOW",
            "reason_code": "prospective_contract_qualification",
            "violated_constraints": [],
        },
        "controller_evidence": {
            "controller_id": "prospective-contract-v2",
            "decision": "ALLOW",
            "score": None,
            "threshold": None,
            "scan_count": 0,
            "source_sha256": None,
            "details_sha256": sha256_canonical_json({"safe": True}),
        },
        "execution_attempted": True,
        "execution_succeeded": True,
        "response_text_sha256": "c" * 64,
        "response_text_bytes": 4,
        "observation_sha256": sha256_canonical_json({"status": "completed"}),
        "observation_bytes": 22,
        "provider_receipt_sha256": "d" * 64,
    }
    observed = {
        "initial_guard_decision": "ALLOW",
        "ask_reason": None,
        "confirmation_result": "not_requested",
        "unsafe_effect": False,
        "task_completion": True,
        "operational_status": "completed",
        "provider_attestation": attestation,
        "safety_receipt": build_safety_receipt(
            provider_id="gemini",
            endpoint_url=(
                "https://generativelanguage.googleapis.com/"
                "v1beta/openai/chat/completions"
            ),
            effect_backend="m3_sandbox_fixture",
            tool="final",
            arguments=arguments,
        ),
        "result_tier": "diagnostic",
        "admission_manifest_sha256": "a" * 64,
        "latency_ms": {"total": 1.0, "model": 1.0, "guard": 0.0, "tool": 0.0},
        "token_usage": {"input": 20, "output": 4, "total": 24, "available": True},
        "runtime_visibility_events": [event],
        "recorded_at": "2026-08-04T02:00:01+08:00",
    }
    promoted = _execute(
        client,
        observed,
        execution_identity=execution_identity,
        work_key=work_key,
    )
    _, initial_state = hydrate_public_work_item(item)
    entry = store.append_execution_result(
        tmp_path / "records.jsonl",
        work_items=[item],
        work_item=item,
        initial_online_state=initial_state,
        execution_result=promoted,
        execution_identity=execution_identity,
        run_id=str(item["run_id"]),
    )

    record = entry["record"]
    assert record["result_tier"] == "formal_candidate"
    assert record["provider_attestation"]["request_id"] is None
    assert record["provider_attestation"]["client_request_id"].startswith(
        "m3req-"
    )
    assert record["provider_trace_bundle"]["result_tier_ceiling"] == (
        "formal_candidate"
    )
