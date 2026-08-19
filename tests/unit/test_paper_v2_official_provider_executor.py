from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from experiments.paper_v2.official_provider_executor import (
    DEFAULT_BUDGET_POLICY,
    HTTPResponseEnvelope,
    OfficialProviderClient,
    ProviderBudgetState,
    ProviderConsentError,
    ProviderIdentityError,
    ProviderLedgerError,
    ProviderPayloadError,
    ProviderPausedError,
    ProviderUsageError,
    append_call_event,
    build_offline_transport_qualification,
    load_call_events,
    provider_receipt_to_attestation,
    validate_call_events,
    validate_messages,
    validate_provider_receipt,
)
from experiments.paper_v2.provider_execution_gate import (
    DEFAULT_OUTPUT,
    DEFAULT_QUALIFICATION,
    build_execution_preflight,
)


def _policy() -> dict:
    return json.loads(DEFAULT_BUDGET_POLICY.read_text(encoding="utf-8"))


def _deepseek_response(**overrides) -> HTTPResponseEnvelope:
    body = {
        "id": "deepseek-response-id",
        "model": "deepseek-v4-pro",
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
            "prompt_tokens": 100,
            "prompt_cache_hit_tokens": 90,
            "prompt_cache_miss_tokens": 10,
            "completion_tokens": 10,
            "total_tokens": 110,
        },
    }
    body.update(overrides)
    return HTTPResponseEnvelope(
        status_code=200,
        headers={"X-Request-ID": "deepseek-request-id"},
        body=body,
    )


def _client(provider_id: str, transport):
    policy = _policy()
    return OfficialProviderClient(
        provider_id=provider_id,
        api_key=f"test-key-{provider_id}",
        content_class="fixed_non_sensitive_runtime_instruction",
        budget_state=ProviderBudgetState(
            provider_id=provider_id, policy=policy
        ),
        policy=policy,
        transport=transport,
    )


def _as_official_network_receipt(receipt: dict) -> dict:
    value = copy.deepcopy(receipt)
    value["evidence"]["transport_kind"] = "official_network"
    from experiments.paper_v2.contracts import sha256_canonical_json

    value["evidence_sha256"] = sha256_canonical_json(value["evidence"])
    return value


def _validate_attestation_schema(attestation: dict) -> None:
    schema_path = (
        Path(__file__).resolve().parents[2]
        / "schemas/paper_v2/experiment_record_v1.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator(
        schema["$defs"]["provider_attestation"],
        format_checker=FormatChecker(),
    ).validate(attestation)


def test_real_transport_requires_consent_and_repr_redacts_key() -> None:
    policy = _policy()
    with pytest.raises(ProviderConsentError, match="explicit network consent"):
        OfficialProviderClient(
            provider_id="deepseek",
            api_key="test-key-that-must-not-appear",
            content_class="fixed_non_sensitive_runtime_instruction",
            budget_state=ProviderBudgetState(
                provider_id="deepseek", policy=policy
            ),
            policy=policy,
        )

    client = _client("deepseek", lambda *_: _deepseek_response())
    assert "test-key-deepseek" not in repr(client)


def test_payload_boundary_rejects_secret_and_unknown_content_class() -> None:
    policy = _policy()
    with pytest.raises(ProviderPayloadError, match="credential-like"):
        validate_messages(
            [{"role": "user", "content": "api_key=abcdefghijklmno"}],
            content_class="synthetic_m3_case",
            policy=policy,
        )
    with pytest.raises(ProviderPayloadError, match="content class"):
        validate_messages(
            [{"role": "user", "content": "public"}],
            content_class="unpublished_manuscript",
            policy=policy,
        )


def test_deepseek_single_attempt_receipt_has_cache_cost_and_no_content() -> None:
    captured = {}

    def transport(endpoint, headers, payload, timeout):
        captured.update(
            {
                "endpoint": endpoint,
                "headers": dict(headers),
                "payload": copy.deepcopy(payload),
                "timeout": timeout,
            }
        )
        return _deepseek_response()

    client = _client("deepseek", transport)
    result = client.complete(
        [{"role": "user", "content": "fixed synthetic text"}]
    )
    receipt = result.receipt
    validate_provider_receipt(receipt)

    assert result.provider_attempts == 1
    assert captured["endpoint"] == "https://api.deepseek.com/chat/completions"
    assert set(captured["payload"]) == {
        "model",
        "messages",
        "temperature",
        "max_tokens",
        "stream",
    }
    assert "tools" not in captured["payload"]
    assert captured["headers"]["Authorization"] == "Bearer test-key-deepseek"
    assert receipt["evidence"]["request_id"] == "deepseek-request-id"
    assert receipt["evidence"]["response_id"] == "deepseek-response-id"
    assert receipt["evidence"]["identity_verified"] is True
    assert receipt["evidence"]["usage"]["prompt_cache_hit_tokens"] == 90
    assert receipt["evidence"]["budget"]["cumulative_cost_cny"] == pytest.approx(
        0.00009225
    )
    assert "fixed synthetic text" not in repr(receipt)
    assert result.text not in repr(receipt)
    assert "test-key-deepseek" not in repr(receipt)


def test_deepseek_rejects_model_drift_and_missing_cache_usage() -> None:
    drift = _client(
        "deepseek",
        lambda *_: _deepseek_response(model="different-model"),
    )
    with pytest.raises(ProviderIdentityError, match="frozen model"):
        drift.complete([{"role": "user", "content": "synthetic"}])

    response = _deepseek_response()
    response.body["usage"].pop("prompt_cache_hit_tokens")
    missing = _client("deepseek", lambda *_: response)
    with pytest.raises(ProviderUsageError, match="cache hit and miss"):
        missing.complete([{"role": "user", "content": "synthetic"}])


def test_gemini_free_usage_and_request_id_are_recorded() -> None:
    def transport(*_):
        return HTTPResponseEnvelope(
            status_code=200,
            headers={"x-goog-request-id": "gemini-request-id"},
            body={
                "id": "gemini-response-id",
                "model": "gemini-3.6-flash",
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "SAFE"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 25,
                    "completion_tokens": 5,
                    "total_tokens": 32,
                },
            },
        )

    result = _client("gemini", transport).complete(
        [{"role": "user", "content": "synthetic"}]
    )
    evidence = result.receipt["evidence"]
    assert evidence["request_id"] == "gemini-request-id"
    assert evidence["identity_verified"] is True
    assert evidence["budget"]["charged_usd"] == 0.0
    assert result.total_tokens == 32


def test_official_response_id_verifies_identity_when_request_id_is_unavailable() -> None:
    result = _client(
        "deepseek",
        lambda *_: HTTPResponseEnvelope(
            status_code=200,
            headers={},
            body=_deepseek_response().body,
        ),
    ).complete([{"role": "user", "content": "synthetic"}])
    evidence = result.receipt["evidence"]

    assert evidence["request_id"] is None
    assert evidence["response_id"] == "deepseek-response-id"
    assert evidence["identity_verified"] is True
    assert evidence["request_trace_complete"] is False
    assert evidence["evidence_level"] == (
        "official_exact_model_with_response_id_request_id_unavailable"
    )


def test_receipt_binding_requires_real_transport_and_complete_request_trace() -> None:
    fixture_receipt = dict(
        _client("deepseek", lambda *_: _deepseek_response())
        .complete([{"role": "user", "content": "synthetic"}])
        .receipt
    )
    local = provider_receipt_to_attestation(fixture_receipt)
    _validate_attestation_schema(local)
    assert local["endpoint_type"] == "stub"
    assert local["identity_verified"] is False
    assert local["evidence_level"] == "local_qualification"
    assert local["request_id"] is None
    assert local["response_id"] is None

    official = provider_receipt_to_attestation(
        _as_official_network_receipt(fixture_receipt)
    )
    _validate_attestation_schema(official)
    assert official["endpoint_type"] == "official_api"
    assert official["identity_verified"] is True
    assert official["evidence_level"] == "formal_candidate"
    assert official["request_id"] == "deepseek-request-id"
    assert official["response_id"] == "deepseek-response-id"


def test_missing_official_request_id_is_bound_as_diagnostic_only() -> None:
    receipt = dict(
        _client(
            "deepseek",
            lambda *_: HTTPResponseEnvelope(
                status_code=200,
                headers={},
                body=_deepseek_response().body,
            ),
        )
        .complete([{"role": "user", "content": "synthetic"}])
        .receipt
    )
    attestation = provider_receipt_to_attestation(
        _as_official_network_receipt(receipt)
    )
    _validate_attestation_schema(attestation)

    assert attestation["identity_verified"] is True
    assert attestation["request_id"] is None
    assert attestation["evidence_level"] == "diagnostic_only"


def test_429_pauses_after_exactly_one_attempt_without_retry() -> None:
    calls = []

    def transport(*args):
        calls.append(args)
        raise ProviderPausedError("HTTP 429", http_status=429)

    client = _client("gemini", transport)
    with pytest.raises(ProviderPausedError) as caught:
        client.complete([{"role": "user", "content": "synthetic"}])
    assert len(calls) == 1
    assert caught.value.automatic_retry is False


def _event(
    event_type: str,
    *,
    attempt_id: str,
    resume_mode: str | None = None,
    provider_id: str = "deepseek",
    receipt: dict | None = None,
    manual_resume_authorization_id: str | None = None,
) -> dict:
    event = {
        "schema_version": "m3-paper-v2-provider-call-event-1.0",
        "execution_identity": "execution-identity",
        "provider_id": provider_id,
        "model_id": "deepseek-v4-pro",
        "work_key": "work-key",
        "call_index": 1,
        "attempt_id": attempt_id,
        "event_type": event_type,
        "automatic_retry": False,
    }
    if resume_mode is not None:
        event["resume_mode"] = resume_mode
    if manual_resume_authorization_id is not None:
        event["manual_resume_authorization_id"] = manual_resume_authorization_id
    if event_type == "paused":
        event["http_status"] = 429
    if receipt is not None:
        event["receipt"] = receipt
    return event


def test_ledger_allows_only_manual_same_provider_resume_after_429() -> None:
    receipt = dict(
        _client("deepseek", lambda *_: _deepseek_response())
        .complete([{"role": "user", "content": "synthetic"}])
        .receipt
    )
    events = [
        _event("started", attempt_id="attempt-1", resume_mode="none"),
        _event("paused", attempt_id="attempt-1"),
        _event(
            "started",
            attempt_id="attempt-2",
            resume_mode="manual_provider_recovery",
            manual_resume_authorization_id="operator-decision-1",
        ),
        _event("completed", attempt_id="attempt-2", receipt=receipt),
    ]
    status = validate_call_events(
        events,
        execution_identity="execution-identity",
        provider_id="deepseek",
        model_id="deepseek-v4-pro",
    )
    assert status["completed_calls"] == 1
    assert status["manual_resumed_calls"] == 1

    automatic = copy.deepcopy(events)
    automatic[2]["automatic_retry"] = True
    with pytest.raises(ProviderLedgerError, match="automatic retry"):
        validate_call_events(
            automatic,
            execution_identity="execution-identity",
            provider_id="deepseek",
            model_id="deepseek-v4-pro",
        )

    missing_manual_authorization = copy.deepcopy(events)
    missing_manual_authorization[2].pop("manual_resume_authorization_id")
    with pytest.raises(ProviderLedgerError, match="authorization is required"):
        validate_call_events(
            missing_manual_authorization,
            execution_identity="execution-identity",
            provider_id="deepseek",
            model_id="deepseek-v4-pro",
        )

    fallback = copy.deepcopy(events)
    fallback[2]["provider_id"] = "gemini"
    with pytest.raises(ProviderLedgerError, match="cross-provider"):
        validate_call_events(
            fallback,
            execution_identity="execution-identity",
            provider_id="deepseek",
            model_id="deepseek-v4-pro",
        )


def test_ledger_append_round_trip_rejects_persisted_headers(tmp_path: Path) -> None:
    path = tmp_path / "provider-events.jsonl"
    event = _event("started", attempt_id="attempt-1", resume_mode="none")
    append_call_event(
        path,
        event,
        execution_identity="execution-identity",
        provider_id="deepseek",
        model_id="deepseek-v4-pro",
    )
    assert load_call_events(path) == [event]

    unsafe = dict(event)
    unsafe["headers"] = {"Authorization": "Bearer forbidden"}
    with pytest.raises(ProviderPayloadError, match="forbidden persisted"):
        append_call_event(
            path,
            unsafe,
            execution_identity="execution-identity",
            provider_id="deepseek",
            model_id="deepseek-v4-pro",
        )


def test_offline_qualification_is_two_provider_zero_network_and_reproducible() -> None:
    qualification = build_offline_transport_qualification()
    frozen = json.loads(DEFAULT_QUALIFICATION.read_text(encoding="utf-8"))

    assert qualification == frozen
    assert qualification["network_calls_made"] == 0
    assert qualification["credentials_read"] is False
    assert qualification["automatic_retries"] == 0
    assert qualification["formal_result_created"] is False
    assert set(qualification["providers"]) == {"deepseek", "gemini"}
    assert all(
        row["provider_tools_declared"] is False
        for row in qualification["providers"].values()
    )
    assert all(
        row["experiment_record_evidence_level"] == "local_qualification"
        and row["formal_record_eligible"] is False
        for row in qualification["providers"].values()
    )


def test_v3_preflight_binds_transport_but_keeps_execution_blocked() -> None:
    preflight = build_execution_preflight()
    frozen = json.loads(DEFAULT_OUTPUT.read_text(encoding="utf-8"))

    assert preflight == frozen
    assert preflight["transport_adapters_qualified"] == 2
    assert preflight["formal_condition_executors_registered"] == 6
    assert preflight["qualified_benchmark_condition_pairs"] == 12
    assert preflight["formal_record_store_offline_qualified"] is True
    assert preflight["formal_record_store_v2_offline_qualified"] is True
    assert preflight["experiment_record_v2_schema_qualified"] is True
    assert preflight["live_formal_records_persisted"] == 0
    assert preflight["record_store_qualification"]["transient_entries"] == 12
    assert preflight["record_store_qualification"][
        "transient_cleanup_verified"
    ] is True
    store_v2 = preflight["record_store_v2_qualification"]
    assert store_v2["status"] == "offline_v2_record_store_qualified"
    assert store_v2["transient_entries"] == 2
    assert store_v2["hash_chain_complete"] is True
    assert store_v2["append_flush_fsync"] is True
    assert store_v2["negative_cases_rejected"] == 2
    assert store_v2["v1_record_contract_modified"] is False
    assert store_v2["v1_record_store_modified"] is False
    assert store_v2["live_runtime_v2_wiring_qualified"] is False
    assert preflight["live_condition_dependencies_qualified"] is True
    assert preflight["live_condition_composition_offline_qualified"] is True
    assert preflight["promptguard_live_inference_qualified"] is True
    assert (
        preflight["agentdojo_environment_and_evaluator_qualified"] is True
    )
    assert preflight["offline_outcome_evaluators_qualified"] is True
    assert preflight["exact_gold_ablation_monitor_qualified"] is True
    assert preflight["vigil_provider_bridge_qualified"] is True
    assert preflight["live_provider_identity_qualified"] is True
    assert preflight["deepseek_live_v2_trace_qualified"] is True
    assert preflight["provider_trace_v2_candidate_qualified"] is True
    assert preflight["provider_trace_v2_activated"] is True
    assert preflight["gemini_quota_snapshot_bound"] is True
    assert preflight["gemini_quota_gate_satisfied"] is True
    assert preflight["promptguard_qualification"]["decision_matches"] == 2
    assert preflight["agentdojo_qualification"][
        "official_utility_checker"
    ] is True
    assert preflight["agentdojo_qualification"][
        "official_security_checker"
    ] is True
    assert preflight["agentdojo_qualification"][
        "qualification_probes"
    ] == 2
    assert preflight["m3_evaluator_qualification"][
        "qualified_benchmarks"
    ] == ["agentdojo-v1", "m3-v2"]
    assert preflight["m3_evaluator_qualification"][
        "labels_visible_online"
    ] is False
    assert preflight["exact_gold_qualification"][
        "formal_primary_endpoint_eligible"
    ] is False
    assert preflight["vigil_qualification"][
        "provider_calls_consumed"
    ] == 1
    assert preflight["vigil_qualification"][
        "silent_default_fallback_accepted"
    ] is False
    assert preflight["provider_live_qualification"][
        "qualified_provider_count"
    ] == 0
    assert preflight["provider_live_qualification"][
        "network_call_attempts"
    ] == 2
    assert preflight["provider_live_qualification"][
        "credentials_stored"
    ] is False
    assert preflight["provider_live_qualification"][
        "prompt_or_response_content_stored"
    ] is False
    live_v2 = preflight["provider_live_qualification_v2"]
    assert (
        live_v2["status"]
        == "deepseek_live_v2_trace_qualified_recovered"
    )
    assert live_v2["provider_id"] == "deepseek"
    assert live_v2["identity_qualification_satisfied"] is True
    assert live_v2["network_call_attempts"] == 1
    assert live_v2["trace_ledger"]["event_count"] == 2
    assert live_v2["trace_ledger"]["completed_requests"] == 1
    assert live_v2["trace_ledger"]["open_requests"] == 0
    assert live_v2["response_exact_safe"] is None
    assert live_v2["provider_receipt_persisted"] is False
    assert live_v2["prompt_or_response_content_stored"] is False
    assert live_v2["result_eligible_for_effect_tables"] is False
    trace = preflight["provider_trace_v2_candidate"]
    assert trace["qualified_provider_count"] == 2
    assert trace["negative_cases_rejected"] == 3
    assert trace["append_flush_fsync"] is True
    assert trace["old_smoke_retroactive_upgrade"] is False
    assert trace["v1_contract_unchanged"] is True
    assert trace["v2_schema_activated"] is False
    activation = preflight["provider_trace_v2_activation"]
    assert activation["approved_provider_ids"] == ["deepseek"]
    assert activation["request_trace_protocol_activated"] is True
    assert activation["fresh_prospective_requests_only"] is True
    assert activation["v1_contract_unchanged"] is True
    assert (
        activation["historical_artifacts_retroactively_eligible"] is False
    )
    assert activation["formal_matrix_authorized"] is False
    quota = preflight["gemini_quota_snapshot"]
    assert quota["status"] == "active_project_quota_captured"
    assert quota["quota_gate_satisfied"] is True
    assert quota["active_limits"] == {
        "rpm": 1_000,
        "tpm": 2_000_000,
        "rpd": 10_000,
    }
    assert quota["paid_tier_allowed"] is False
    assert quota["project_identifier_stored"] is False
    assert quota["api_key_or_credential_stored"] is False
    assert preflight["live_runtime_qualification"]["qualified_pairs"] == 12
    assert preflight["live_runtime_qualification"][
        "strict_parser_negative_cases_rejected"
    ] == 5
    assert preflight["live_runtime_qualification"][
        "exact_gold_integration_routes"
    ] == 2
    assert preflight["live_runtime_qualification"][
        "live_dependencies_fully_qualified"
    ] is False
    assert preflight["execution_authorized"] is False
    assert preflight["gate_pass"] is False
    assert len(preflight["blockers"]) == 1
