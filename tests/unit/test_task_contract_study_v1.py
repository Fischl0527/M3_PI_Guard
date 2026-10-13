"""本study调度、ITT与开放trace恢复边界测试。"""
from __future__ import annotations

import json

import pytest

from experiments.paper_v2 import task_contract_study_v1 as subject


def _row(key, *, payload="same", status="completed"):
    return {"work_key":key, "model_group":"deepseek_pro", "model_id":"deepseek-v4-pro",
        "base_task_id":"b", "scenario":"normal", "replicate_index":1,
        "operational_status":status, "online_forbidden_fields_present":[],
        "events":[{"parse_ok":True}], "provider_requests":[{"response_received":True,
        "local_request_id":key, "payload_sha256":payload,"provider_response_id":"r", "returned_model":"deepseek-v4-pro"}],
        "cost":{"currency":"CNY","amount":0.1}, "latency_ms":{"total":1200}}


def test_prefix_is_outcome_blind_and_payload_paired():
    rows = [_row("a"), _row("b")]
    assert subject.technical_prefix(rows, expected=2, threshold=2)["passed"]
    rows[0].update(unsafe_effect=True, task_completion=False)
    assert subject.technical_prefix(rows, expected=2, threshold=2)["passed"]
    rows[1]["provider_requests"][0]["payload_sha256"] = "changed"
    assert "initial_payload_mismatch_across_conditions" in subject.technical_prefix(rows, expected=2, threshold=2)["reasons"]


@pytest.mark.parametrize("status",[401,403,429,404])
def test_fatal_http_always_stops(status):
    row = _row("a")
    row["provider_requests"][0]["http_status"] = status
    assert subject.record_failure_reason(row)


def test_annotation_keeps_unknown_in_itt():
    row = _row("a",status="provider_failure")
    row.update(unsafe_effect=None,task_completion=None)
    out = subject.annotate(row)
    assert out["unsafe_effect"] is None and out["task_completion"] is None
    assert out["max_tokens"] == 512 and out["latency_seconds"] == 1.2
    assert out["cost_estimate_cny"] == 0.1


def test_annotation_preserves_real_safety_anomalies_and_bool_field_leak():
    row = _row("a")
    row.update(provider_tools_enabled=True,real_external_effects=2,online_forbidden_fields_present=True)
    out = subject.annotate(row)
    assert out["provider_tools_enabled"] is True
    assert out["real_external_effects"] == 2
    assert out["evaluator_fields_online"] == 1


def test_six_diagnostics_cover_read_write_final_without_reusing_legacy_keys():
    from collections import Counter
    rows = subject.diagnostic_plan()
    assert Counter(r["diagnostic_kind"] for r in rows) == {"read":2,"write":2,"final":2}
    assert len({r["work_key"] for r in rows}) == 6
    assert all(r["model_group"] == "gemini_flash" and r["max_provider_calls"] == 1 for r in rows)


def test_open_trace_rejected_before_client_creation(tmp_path):
    plan = [{**_row("w"),"formal_prefix":True,"attempt":1}]
    path = tmp_path / "plan.jsonl"
    path.write_text(json.dumps(plan[0])+"\n", encoding="utf-8")
    trace = tmp_path / "pro/internal/deepseek_pro/w.attempt1.jsonl"
    trace.parent.mkdir(parents=True)
    trace.write_text("open",encoding="utf-8")
    def forbidden(**kwargs):
        raise AssertionError("must not create client")
    with pytest.raises(RuntimeError,match="open trace"):
        subject.run_provider("pro",plan_path=path,output=tmp_path,api_key="offline",prefix_only=True,
            runtime=object(),client_factory=forbidden)
