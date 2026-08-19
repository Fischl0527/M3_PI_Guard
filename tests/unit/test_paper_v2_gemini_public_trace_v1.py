from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Mapping

import pytest

import experiments.paper_v2.gemini_fallback_controller_v2 as fallback
import experiments.paper_v2.gemini_public_trace_v1 as gemini_trace
from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.official_provider_executor import (
    HTTPResponseEnvelope,
    OfficialProviderClient,
    ProviderBudgetState,
    ProviderIdentityError,
    ProviderPausedError,
)


MESSAGES = [
    {"role": "system", "content": "Return JSON only."},
    {"role": "user", "content": "Synthetic trace qualification."},
]


def _official_adapter(receipt: Mapping[str, Any]) -> Mapping[str, Any]:
    value = copy.deepcopy(dict(receipt))
    value["evidence"]["transport_kind"] = "official_network"
    value["evidence_sha256"] = sha256_canonical_json(value["evidence"])
    return value


def _client(
    trace_path: Path,
    *,
    status_code: int = 200,
    returned_model: str = "gemini-3.6-flash",
) -> gemini_trace.GeminiPublicTracedProviderClient:
    policy = fallback._effective_policy()

    def transport(
        endpoint: str,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
        timeout: float,
    ) -> HTTPResponseEnvelope:
        del endpoint, headers, timeout
        rows = [
            json.loads(line)
            for line in trace_path.read_text(encoding="utf-8").splitlines()
        ]
        assert rows[-1]["event"]["event_type"] == "started"
        assert rows[-1]["event"]["commitment"]["payload_sha256"]
        return HTTPResponseEnvelope(
            status_code=status_code,
            headers={"x-goog-request-id": "gemini-request-test"},
            body=(
                {}
                if status_code != 200
                else {
                    "id": "gemini-response-test",
                    "model": returned_model,
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
                }
            ),
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
    return gemini_trace.GeminiPublicTracedProviderClient(
        official,
        execution_identity="execution-test",
        work_key="work-test",
        trace_path=trace_path,
        admission_manifest_sha256="a" * 64,
        recorded_at=lambda: "2026-08-02T00:00:00+08:00",
        receipt_adapter=_official_adapter,
    )


def test_gemini_trace_precommits_payload_before_transport(tmp_path: Path) -> None:
    trace_path = tmp_path / "trace.jsonl"
    client = _client(trace_path)

    completion = client.complete(MESSAGES, step=1)
    bundle = client.build_bundle()

    assert completion.text
    assert bundle["bundle_status"] == "completed"
    assert bundle["result_tier_ceiling"] == "formal_candidate"
    assert bundle["request_count"] == 1
    assert bundle["completed_request_count"] == 1
    assert bundle["open_request_count"] == 0
    assert bundle["activated_attestations"][0]["client_request_id"].startswith(
        "m3req-"
    )
    assert bundle["usage_summary"] == {
        "requests": 1,
        "prompt_tokens": 20,
        "completion_tokens": 4,
        "total_tokens": 24,
        "billing_tier": "free",
        "charged_usd": 0.0,
        "paid_ceiling_usd": 0.0,
    }
    serialized = json.dumps(bundle)
    assert "unit-test-key" not in serialized
    assert "Synthetic trace qualification" not in serialized


def test_first_429_leaves_a_diagnostic_open_commitment(tmp_path: Path) -> None:
    client = _client(tmp_path / "trace.jsonl", status_code=429)

    with pytest.raises(ProviderPausedError):
        client.complete(MESSAGES, step=1)
    bundle = client.build_bundle()

    assert bundle["bundle_status"] == "incomplete_paused"
    assert bundle["result_tier_ceiling"] == "diagnostic"
    assert bundle["open_request_count"] == 1
    assert bundle["completed_request_count"] == 0
    assert bundle["failures"][0]["status"] == "paused"


def test_model_identity_drift_is_diagnostic(tmp_path: Path) -> None:
    client = _client(tmp_path / "trace.jsonl", returned_model="other-model")

    with pytest.raises(ProviderIdentityError):
        client.complete(MESSAGES, step=1)
    bundle = client.build_bundle()

    assert bundle["bundle_status"] == "incomplete_provider_failure"
    assert bundle["result_tier_ceiling"] == "diagnostic"
    assert bundle["failures"][0]["error_type"] == "ProviderIdentityError"


def test_existing_nonempty_trace_cannot_auto_resume(tmp_path: Path) -> None:
    trace_path = tmp_path / "trace.jsonl"
    client = _client(trace_path)
    client.complete(MESSAGES, step=1)

    with pytest.raises(
        gemini_trace.GeminiPublicTraceV1Error,
        match="cannot be automatically resumed",
    ):
        _client(trace_path)

