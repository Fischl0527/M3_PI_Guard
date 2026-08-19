from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Mapping

import pytest

import experiments.paper_v2.experiment_closeout_freeze_v1 as freeze
import experiments.paper_v2.gemini_fallback_controller_v2 as fallback
import experiments.paper_v2.gemini_public_execution_store_v1 as store
import experiments.paper_v2.gemini_public_trace_v1 as gemini_trace
from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.official_provider_executor import (
    HTTPResponseEnvelope,
    OfficialProviderClient,
    ProviderBudgetState,
    provider_receipt_to_attestation,
)
from experiments.paper_v2.provider_safety import build_safety_receipt
from experiments.paper_v2.public_matrix_plan_v1 import hydrate_public_work_item


def _official_adapter(receipt: Mapping[str, Any]) -> Mapping[str, Any]:
    value = copy.deepcopy(dict(receipt))
    value["evidence"]["transport_kind"] = "official_network"
    value["evidence_sha256"] = sha256_canonical_json(value["evidence"])
    return value


def _result(
    tmp_path: Path,
    item: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    policy = fallback._effective_policy()

    def transport(*_: Any) -> HTTPResponseEnvelope:
        return HTTPResponseEnvelope(
            status_code=200,
            headers={"x-goog-request-id": "request-store-test"},
            body={
                "id": "response-store-test",
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
        content_class="public_benchmark_case",
        budget_state=ProviderBudgetState(provider_id="gemini", policy=policy),
        policy=policy,
        temperature=0.0,
        max_tokens=64,
        timeout=30.0,
        network_consent=False,
        transport=transport,
    )
    traced = gemini_trace.GeminiPublicTracedProviderClient(
        official,
        execution_identity=str(item["execution_identity"]),
        work_key=str(item["work_key"]),
        trace_path=tmp_path / "trace.jsonl",
        admission_manifest_sha256="a" * 64,
        recorded_at=lambda: "2026-08-02T00:00:00+08:00",
        receipt_adapter=_official_adapter,
    )
    completion = traced.complete(
        [
            {"role": "system", "content": "Return JSON only."},
            {"role": "user", "content": "Synthetic store qualification."},
        ],
        step=1,
    )
    receipt = _official_adapter(completion.receipt)
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
            "reason_code": "synthetic_store_qualification",
            "violated_constraints": [],
        },
        "controller_evidence": {
            "controller_id": "synthetic-store",
            "decision": "ALLOW",
            "score": None,
            "threshold": None,
            "scan_count": 0,
            "source_sha256": None,
            "details_sha256": sha256_canonical_json({"safe": True}),
        },
        "execution_attempted": True,
        "execution_succeeded": True,
        "response_text_sha256": receipt["evidence"]["response_text_sha256"],
        "response_text_bytes": receipt["evidence"]["response_text_bytes"],
        "observation_sha256": sha256_canonical_json({"status": "completed"}),
        "observation_bytes": 22,
        "provider_receipt_sha256": sha256_canonical_json(receipt),
    }
    safety = build_safety_receipt(
        provider_id="gemini",
        endpoint_url=(
            "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
        ),
        effect_backend="m3_sandbox_fixture",
        tool="final",
        arguments=arguments,
    )
    result = {
        "initial_guard_decision": "ALLOW",
        "ask_reason": None,
        "confirmation_result": "not_requested",
        "unsafe_effect": False,
        "task_completion": True,
        "operational_status": "completed",
        "provider_attestation": provider_receipt_to_attestation(receipt),
        "provider_trace_bundle": traced.build_bundle(),
        "safety_receipt": safety,
        "result_tier": "formal_candidate",
        "admission_manifest_sha256": "a" * 64,
        "latency_ms": {"total": 1.0, "model": 1.0, "guard": 0.0, "tool": 0.0},
        "token_usage": {"input": 20, "output": 4, "total": 24, "available": True},
        "runtime_visibility_events": [event],
        "recorded_at": "2026-08-02T00:00:01+08:00",
    }
    _, initial_state = hydrate_public_work_item(item)
    return result, initial_state


def test_gemini_public_record_atomically_binds_trace_and_safety(tmp_path: Path) -> None:
    item = freeze.build_gemini_public_plan()[0]
    result, initial_state = _result(tmp_path, item)

    entry = store.append_execution_result(
        tmp_path / "records.jsonl",
        work_items=[item],
        work_item=item,
        initial_online_state=initial_state,
        execution_result=result,
        execution_identity=str(item["execution_identity"]),
        run_id=str(item["run_id"]),
    )

    record = entry["record"]
    assert record["provider_id"] == "gemini"
    assert record["model_id"] == "gemini-3.6-flash"
    assert record["model_role"] == "second"
    assert record["included_in_intention_to_treat"] is True
    assert record["provider_attestation"]["response_id"] == "response-store-test"
    assert record["isolated_effect_receipt_sha256"] == record[
        "provider_safety_receipt"
    ]["evidence_sha256"]
    assert entry["previous_entry_sha256"] is None
    assert store.validate_record_entries(
        [entry],
        work_items=[item],
        execution_identity=str(item["execution_identity"]),
        run_id=str(item["run_id"]),
    )["hash_chain_complete"] is True
    assert "unit-test-key" not in json.dumps(entry)


def test_record_tampering_breaks_the_chain(tmp_path: Path) -> None:
    item = freeze.build_gemini_public_plan()[0]
    result, initial_state = _result(tmp_path, item)
    path = tmp_path / "records.jsonl"
    entry = store.append_execution_result(
        path,
        work_items=[item],
        work_item=item,
        initial_online_state=initial_state,
        execution_result=result,
        execution_identity=str(item["execution_identity"]),
        run_id=str(item["run_id"]),
    )
    entry["record"]["task_completion"] = False

    with pytest.raises(store.GeminiPublicExecutionStoreV1Error):
        store.validate_record_entries(
            [entry],
            work_items=[item],
            execution_identity=str(item["execution_identity"]),
            run_id=str(item["run_id"]),
        )

