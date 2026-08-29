from __future__ import annotations

import copy

import pytest

from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.official_provider_executor import (
    HTTPResponseEnvelope,
    ProviderPausedError,
)
from experiments.paper_v2.provider_request_trace_candidate import (
    FIXED_MESSAGES,
    ProviderRequestTraceError,
    _as_official_receipt,
    _fixture_client,
)
from experiments.paper_v2.provider_trace_bundle import (
    ProviderTraceBundleError,
    TracedProviderClient,
    validate_provider_trace_bundle,
)


RECORDED_AT = "2026-07-24T03:00:00+08:00"


def _multi_call_client():
    client = _fixture_client("deepseek", include_request_id=False)
    call_count = 0

    def transport(endpoint, headers, payload, timeout):
        nonlocal call_count
        del endpoint, headers, timeout
        call_count += 1
        return HTTPResponseEnvelope(
            status_code=200,
            headers={},
            body={
                "id": f"fixture-response-{call_count}",
                "model": payload["model"],
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "SAFE",
                        },
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

    client.transport = transport
    return client


def test_traced_client_builds_ordered_two_call_bundle(tmp_path) -> None:
    client = _multi_call_client()
    traced = TracedProviderClient(
        client,
        execution_identity="execution-test",
        work_key="work-test",
        trace_path=tmp_path / "trace.jsonl",
        recorded_at=lambda: RECORDED_AT,
        receipt_adapter=_as_official_receipt,
    )

    traced.complete(FIXED_MESSAGES, step=1)
    traced.complete(FIXED_MESSAGES, step=2)
    bundle = traced.build_bundle()

    assert bundle["bundle_status"] == "completed"
    assert bundle["request_count"] == 2
    assert bundle["completed_request_count"] == 2
    assert bundle["open_request_count"] == 0
    assert bundle["trace_event_count"] == 4
    assert bundle["result_tier_ceiling"] == "formal_candidate"
    assert [
        row["event"]["commitment"]["call_index"]
        for row in bundle["trace_rows"]
        if row["event"]["event_type"] == "started"
    ] == [1, 2]
    assert len(bundle["activated_attestations"]) == 2
    assert len(bundle["usage_evidence"]) == 2
    assert bundle["usage_summary"] == {
        "completed_call_count": 2,
        "prompt_tokens": 40,
        "prompt_cache_hit_tokens": 32,
        "prompt_cache_miss_tokens": 8,
        "completion_tokens": 4,
        "total_tokens": 44,
        "cache_accounting_complete": True,
        "cumulative_cost_cny": 0.0000488,
        "abort_ceiling_cny": 27.0,
        "within_abort_ceiling": True,
    }
    assert [item["request_cost_cny"] for item in bundle["usage_evidence"]] == [
        0.0000244,
        0.0000244,
    ]


def test_physical_attempt_namespace_preserves_default_and_isolates_later_attempts(
    tmp_path,
) -> None:
    identity = {
        "execution_identity": "execution-namespace",
        "work_key": "work-namespace",
        "call_index": 1,
    }
    default = TracedProviderClient(
        _multi_call_client(),
        execution_identity=identity["execution_identity"],
        work_key=identity["work_key"],
        trace_path=tmp_path / "default.jsonl",
        recorded_at=lambda: RECORDED_AT,
        receipt_adapter=_as_official_receipt,
    )
    second = TracedProviderClient(
        _multi_call_client(),
        execution_identity=identity["execution_identity"],
        work_key=identity["work_key"],
        trace_path=tmp_path / "second.jsonl",
        recorded_at=lambda: RECORDED_AT,
        receipt_adapter=_as_official_receipt,
        physical_attempt_namespace=2,
    )

    historical = "attempt-" + sha256_canonical_json(identity)[:24]
    namespaced = {
        **identity,
        "physical_attempt_namespace": 2,
    }
    assert default._attempt_id(1) == historical
    assert second._attempt_id(1) == (
        "attempt-" + sha256_canonical_json(namespaced)[:24]
    )
    assert second._attempt_id(1) != default._attempt_id(1)

    default.complete(FIXED_MESSAGES, step=1)
    second.complete(FIXED_MESSAGES, step=1)
    default_commitment = default.build_bundle()["trace_rows"][0]["event"][
        "commitment"
    ]
    second_commitment = second.build_bundle()["trace_rows"][0]["event"][
        "commitment"
    ]
    assert default_commitment["attempt_id"] == historical
    assert second_commitment["attempt_id"] == second._attempt_id(1)
    assert (
        default_commitment["client_request_id"]
        != second_commitment["client_request_id"]
    )


@pytest.mark.parametrize("namespace", (0, -1, True, 1.5))
def test_physical_attempt_namespace_rejects_invalid_values(
    tmp_path,
    namespace,
) -> None:
    with pytest.raises(
        ProviderTraceBundleError,
        match="physical attempt namespace",
    ):
        TracedProviderClient(
            _multi_call_client(),
            execution_identity="execution-invalid",
            work_key="work-invalid",
            trace_path=tmp_path / f"invalid-{namespace}.jsonl",
            recorded_at=lambda: RECORDED_AT,
            receipt_adapter=_as_official_receipt,
            physical_attempt_namespace=namespace,
        )


def test_traced_client_keeps_paused_precommit_diagnostic(tmp_path) -> None:
    client = _fixture_client("deepseek", include_request_id=False)

    def paused_transport(endpoint, headers, payload, timeout):
        del endpoint, headers, payload, timeout
        return HTTPResponseEnvelope(
            status_code=429,
            headers={},
            body={},
        )

    client.transport = paused_transport
    traced = TracedProviderClient(
        client,
        execution_identity="execution-paused",
        work_key="work-paused",
        trace_path=tmp_path / "paused.jsonl",
        recorded_at=lambda: RECORDED_AT,
        receipt_adapter=_as_official_receipt,
    )

    with pytest.raises(ProviderPausedError):
        traced.complete(FIXED_MESSAGES, step=1)
    bundle = traced.build_bundle()

    assert bundle["bundle_status"] == "incomplete_paused"
    assert bundle["result_tier_ceiling"] == "diagnostic"
    assert bundle["request_count"] == 1
    assert bundle["completed_request_count"] == 0
    assert bundle["open_request_count"] == 1
    assert bundle["failures"][0]["status"] == "paused"
    assert bundle["usage_evidence"] == []
    assert bundle["usage_summary"]["cumulative_cost_cny"] == 0.0


def test_traced_client_keeps_evidence_failure_as_open_diagnostic(
    tmp_path,
) -> None:
    client = _multi_call_client()

    def invalid_evidence(receipt):
        value = _as_official_receipt(receipt)
        value["evidence"]["returned_model"] = "different-model"
        value["evidence_sha256"] = sha256_canonical_json(
            value["evidence"]
        )
        return value

    traced = TracedProviderClient(
        client,
        execution_identity="execution-evidence-failure",
        work_key="work-evidence-failure",
        trace_path=tmp_path / "evidence-failure.jsonl",
        recorded_at=lambda: RECORDED_AT,
        receipt_adapter=invalid_evidence,
    )

    with pytest.raises(ProviderRequestTraceError):
        traced.complete(FIXED_MESSAGES, step=1)
    bundle = traced.build_bundle()

    assert bundle["bundle_status"] == "incomplete_evidence_failure"
    assert bundle["completed_request_count"] == 0
    assert bundle["open_request_count"] == 1
    assert bundle["activated_attestations"] == []
    assert bundle["usage_evidence"] == []
    assert bundle["failures"][0]["status"] == "evidence_failure"


def test_bundle_rejects_trace_tamper(tmp_path) -> None:
    client = _multi_call_client()
    traced = TracedProviderClient(
        client,
        execution_identity="execution-tamper",
        work_key="work-tamper",
        trace_path=tmp_path / "tamper.jsonl",
        recorded_at=lambda: RECORDED_AT,
        receipt_adapter=_as_official_receipt,
    )
    traced.complete(FIXED_MESSAGES, step=1)
    bundle = traced.build_bundle()
    tampered = copy.deepcopy(bundle)
    tampered["trace_rows"][0]["event"]["commitment"]["work_key"] = "other"
    tampered["trace_rows_sha256"] = sha256_canonical_json(
        tampered["trace_rows"]
    )
    tampered["bundle_sha256"] = sha256_canonical_json(
        {
            key: value
            for key, value in tampered.items()
            if key != "bundle_sha256"
        }
    )

    with pytest.raises(ProviderTraceBundleError):
        validate_provider_trace_bundle(tampered)


def test_bundle_rejects_cache_or_cost_tamper(tmp_path) -> None:
    client = _multi_call_client()
    traced = TracedProviderClient(
        client,
        execution_identity="execution-usage-tamper",
        work_key="work-usage-tamper",
        trace_path=tmp_path / "usage-tamper.jsonl",
        recorded_at=lambda: RECORDED_AT,
        receipt_adapter=_as_official_receipt,
    )
    traced.complete(FIXED_MESSAGES, step=1)
    bundle = traced.build_bundle()
    tampered = copy.deepcopy(bundle)
    tampered["usage_evidence"][0]["prompt_cache_hit_tokens"] -= 1
    tampered["usage_evidence"][0]["prompt_cache_miss_tokens"] += 1
    tampered["bundle_sha256"] = sha256_canonical_json(
        {
            key: value
            for key, value in tampered.items()
            if key != "bundle_sha256"
        }
    )

    with pytest.raises(
        ProviderTraceBundleError,
        match="cache/cost evidence arithmetic drift",
    ):
        validate_provider_trace_bundle(tampered)
