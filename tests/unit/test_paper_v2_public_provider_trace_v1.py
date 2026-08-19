from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Mapping

import pytest

from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.official_provider_executor import HTTPResponseEnvelope
from experiments.paper_v2.provider_trace_bundle import ProviderTraceBundleError
from experiments.paper_v2.public_deepseek_client_v1 import (
    PublicDeepSeekJsonOfficialClient,
)
from experiments.paper_v2.public_provider_budget_v1 import (
    PublicProviderBudgetState,
    build_role_policy,
    load_public_policy,
)
from experiments.paper_v2.public_provider_trace_v1 import (
    PublicDeepSeekJsonTracedProviderClient,
    PublicProviderTraceError,
    validate_public_trace_bundle,
)


def _transport(
    endpoint: str,
    headers: Mapping[str, str],
    payload: Mapping[str, Any],
    timeout: float,
) -> HTTPResponseEnvelope:
    del endpoint, headers, timeout
    return HTTPResponseEnvelope(
        status_code=200,
        headers={"x-request-id": "public-trace-request"},
        body={
            "id": f"public-trace-{payload['model']}-response",
            "model": payload["model"],
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": (
                            '{"tool":"final","arguments":'
                            '{"answer":"QUALIFIED"}}'
                        ),
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 20,
                "total_tokens": 120,
                "prompt_cache_hit_tokens": 80,
                "prompt_cache_miss_tokens": 20,
            },
        },
    )


def _as_official_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    value = copy.deepcopy(dict(receipt))
    evidence = value["evidence"]
    evidence["transport_kind"] = "official_network"
    evidence["identity_verified"] = True
    evidence["request_trace_complete"] = True
    evidence["evidence_level"] = (
        "official_exact_model_with_request_and_response_ids"
    )
    evidence["requested_at"] = "2026-07-28T00:20:00+08:00"
    evidence["model_latency_ms"] = 0.0
    value["evidence_sha256"] = sha256_canonical_json(evidence)
    return value


@pytest.mark.parametrize("role", ("primary", "second"))
def test_public_trace_bundle_reconstructs_for_both_roles(
    tmp_path: Path,
    role: str,
) -> None:
    role_policy = build_role_policy(load_public_policy(), role)
    client = PublicDeepSeekJsonOfficialClient(
        provider_id="deepseek",
        api_key="offline-public-trace-key",
        content_class="public_benchmark_case",
        budget_state=PublicProviderBudgetState("deepseek", role_policy),
        policy=role_policy,
        model_role=role,
        transport=_transport,
    )
    traced = PublicDeepSeekJsonTracedProviderClient(
        client,
        execution_identity=f"offline-public-{role}-identity",
        work_key=f"offline-public-{role}-work",
        trace_path=tmp_path / f"{role}.jsonl",
        recorded_at=lambda: "2026-07-28T00:20:00+08:00",
        receipt_adapter=_as_official_receipt,
    )

    traced.complete(
        [{"role": "user", "content": "offline public trace qualification"}]
    )
    bundle = traced.build_bundle()

    assert bundle["bundle_status"] == "completed"
    assert bundle["request_count"] == 1
    assert bundle["completed_request_count"] == 1
    assert bundle["provider_tools_declared"] is False
    assert bundle["external_effects_enabled"] is False
    assert bundle["model_id"] == client.model
    assert validate_public_trace_bundle(
        bundle,
        role_policy=role_policy,
    ) == bundle


def test_public_trace_rejects_digest_drift(tmp_path: Path) -> None:
    role_policy = build_role_policy(load_public_policy(), "primary")
    client = PublicDeepSeekJsonOfficialClient(
        provider_id="deepseek",
        api_key="offline-public-trace-key",
        content_class="public_benchmark_case",
        budget_state=PublicProviderBudgetState("deepseek", role_policy),
        policy=role_policy,
        model_role="primary",
        transport=_transport,
    )
    traced = PublicDeepSeekJsonTracedProviderClient(
        client,
        execution_identity="offline-public-primary-identity",
        work_key="offline-public-primary-work",
        trace_path=tmp_path / "trace.jsonl",
        recorded_at=lambda: "2026-07-28T00:20:00+08:00",
        receipt_adapter=_as_official_receipt,
    )
    traced.complete(
        [{"role": "user", "content": "offline public trace qualification"}]
    )
    bundle = traced.build_bundle()
    drifted = copy.deepcopy(bundle)
    drifted["usage_summary"]["completion_tokens"] += 1

    with pytest.raises(PublicProviderTraceError, match="digest drift"):
        validate_public_trace_bundle(
            drifted,
            role_policy=role_policy,
        )


def test_public_trace_forbids_automatic_resume(tmp_path: Path) -> None:
    trace = tmp_path / "existing.jsonl"
    trace.write_text("{}\n", encoding="utf-8")
    role_policy = build_role_policy(load_public_policy(), "primary")
    client = PublicDeepSeekJsonOfficialClient(
        provider_id="deepseek",
        api_key="offline-public-trace-key",
        content_class="public_benchmark_case",
        budget_state=PublicProviderBudgetState("deepseek", role_policy),
        policy=role_policy,
        model_role="primary",
        transport=_transport,
    )

    with pytest.raises(ProviderTraceBundleError, match="resume/retry"):
        PublicDeepSeekJsonTracedProviderClient(
            client,
            execution_identity="offline-public-primary-identity",
            work_key="offline-public-primary-work",
            trace_path=trace,
            recorded_at=lambda: "2026-07-28T00:20:00+08:00",
        )
