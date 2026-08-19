from __future__ import annotations

import copy

import pytest

from experiments.paper_v2.official_provider_executor import (
    HTTPResponseEnvelope,
    OfficialProviderClient,
    ProviderBudgetState,
)
from experiments.paper_v2.provider_live_qualification_v2 import (
    ProviderLiveQualificationV2Error,
    execute_live_qualification,
    recover_completed_trace,
    validate_artifact,
)
VALUES = {
    "M3_FRONTIER_API_CONSENT": "yes_for_network_smoke",
    "DEEPSEEK_API_KEY": "fixture-key",
    "FRONTIER_DEEPSEEK_MODEL_ID": "deepseek-v4-pro",
    "FRONTIER_DEEPSEEK_BASE_URL": "https://api.deepseek.com",
}


def _success_factory(_api_key, _policy):
    return OfficialProviderClient(
        provider_id="deepseek",
        api_key=_api_key,
        content_class="synthetic_m3_case",
        budget_state=ProviderBudgetState(
            provider_id="deepseek",
            policy=_policy,
        ),
        policy=_policy,
        temperature=0.0,
        max_tokens=16,
        network_consent=True,
    )


def _official_fixture_transport(_endpoint, _headers, payload, _timeout):
    return HTTPResponseEnvelope(
        status_code=200,
        headers={},
        body={
            "id": "fixture-deepseek-response",
            "model": payload["model"],
            "choices": [
                {
                    "message": {"role": "assistant", "content": "SAFE"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 20,
                "completion_tokens": 2,
                "total_tokens": 22,
                "prompt_cache_hit_tokens": 16,
                "prompt_cache_miss_tokens": 4,
            },
        },
    )


def _failure_factory(api_key, policy):
    def transport(*_):
        raise RuntimeError("synthetic transport failure")

    return OfficialProviderClient(
        provider_id="deepseek",
        api_key=api_key,
        content_class="synthetic_m3_case",
        budget_state=ProviderBudgetState(
            provider_id="deepseek",
            policy=policy,
        ),
        policy=policy,
        transport=transport,
        temperature=0.0,
        max_tokens=16,
        network_consent=True,
    )


def test_success_path_fsyncs_before_call_and_activates_trace(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "experiments.paper_v2.official_provider_executor._default_transport",
        _official_fixture_transport,
    )
    artifact = execute_live_qualification(
        VALUES,
        trace_ledger=tmp_path / "trace.jsonl",
        client_factory=_success_factory,
    )
    validate_artifact(artifact)

    assert artifact["status"] == "deepseek_live_v2_trace_qualified"
    assert artifact["network_call_attempts"] == 1
    assert artifact["trace_ledger"]["event_count"] == 2
    assert artifact["trace_ledger"]["completed_requests"] == 1
    assert artifact["trace_ledger"]["open_requests"] == 0
    assert artifact["response_exact_safe"] is True
    assert artifact["activated_trace_attestation"][
        "v2_trace_eligible"
    ] is True
    assert artifact["formal_matrix_authorized"] is False
    assert artifact["identity_qualification_satisfied"] is True


def test_failed_single_attempt_preserves_open_precommit(tmp_path) -> None:
    artifact = execute_live_qualification(
        VALUES,
        trace_ledger=tmp_path / "failed.jsonl",
        client_factory=_failure_factory,
    )
    validate_artifact(artifact)

    assert artifact["status"] == "failed_single_attempt_preserved"
    assert artifact["error_type"] == "RuntimeError"
    assert artifact["trace_ledger"]["event_count"] == 1
    assert artifact["trace_ledger"]["completed_requests"] == 0
    assert artifact["trace_ledger"]["open_requests"] == 1
    assert artifact["activated_trace_attestation"] is None
    assert artifact["identity_qualification_satisfied"] is False


def test_single_use_and_tamper_boundaries_fail_closed(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "experiments.paper_v2.official_provider_executor._default_transport",
        _official_fixture_transport,
    )
    ledger = tmp_path / "trace.jsonl"
    artifact = execute_live_qualification(
        VALUES,
        trace_ledger=ledger,
        client_factory=_success_factory,
    )
    with pytest.raises(
        ProviderLiveQualificationV2Error,
        match="single-use",
    ):
        execute_live_qualification(
            VALUES,
            trace_ledger=ledger,
            client_factory=_success_factory,
        )

    drifted = copy.deepcopy(artifact)
    drifted["execution_boundary"]["external_effects"] = True
    with pytest.raises(
        ProviderLiveQualificationV2Error,
        match="safety boundary",
    ):
        validate_artifact(drifted)


def test_completed_trace_can_be_recovered_without_a_second_call(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "experiments.paper_v2.official_provider_executor._default_transport",
        _official_fixture_transport,
    )
    ledger = tmp_path / "trace.jsonl"
    execute_live_qualification(
        VALUES,
        trace_ledger=ledger,
        client_factory=_success_factory,
    )

    recovered = recover_completed_trace(trace_ledger=ledger)
    validate_artifact(recovered)

    assert (
        recovered["status"]
        == "deepseek_live_v2_trace_qualified_recovered"
    )
    assert recovered["network_call_attempts"] == 1
    assert recovered["identity_qualification_satisfied"] is True
    assert recovered["response_exact_safe"] is None
    assert recovered["provider_receipt"] is None
    assert recovered["provider_receipt_sha256"]
    assert recovered["trace_ledger"]["completed_requests"] == 1
