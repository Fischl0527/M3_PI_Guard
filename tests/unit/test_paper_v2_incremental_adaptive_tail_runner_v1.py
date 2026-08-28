from __future__ import annotations

import json
from pathlib import Path

import pytest

import experiments.paper_v2.incremental_adaptive_tail_runner_v1 as runner
import experiments.paper_v2.adaptive_formal_plan_v2 as formal_plan


def test_tail_plan_and_runtime_candidate_preserve_the_b200_survivor_scope() -> None:
    rows = runner.load_tail_plan()
    candidate = runner.build_runtime_candidate(rows)
    assert len(rows) == 12
    assert {row["attack_family"] for row in rows} == {"A1", "A2", "A3"}
    assert sum(row["formal_prefix_query_count"] == 5 for row in rows) == 2
    assert candidate["execution_identity"] == rows[0]["execution_identity"]
    assert candidate["scope"]["start_query"] == 201
    assert candidate["scope"]["end_query"] == 500
    assert len(candidate["scope"]["tasks"]) == 12
    assert len(runner._known_query_keys(rows)) == 3600


def test_adaptive_policy_uses_current_pro_peak_pricing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "incremental"
    monkeypatch.setattr(
        "experiments.paper_v2.incremental_study_runner_v1.OUTPUT_ROOT", root
    )
    policy = runner._policy()
    pricing = policy["deepseek"]["pricing"]
    assert policy["deepseek"]["hard_spend_limit_cny"] == 1000.0
    assert runner.GLOBAL_FUSE_CNY == 1000.0
    assert pricing["cache_hit_input_per_million_tokens"] == 0.30
    assert pricing["cache_miss_input_per_million_tokens"] == 9.0
    assert pricing["output_per_million_tokens"] == 27.0
    assert pricing["verified_at"] == "2026-08-26"


def test_checkpoint_preparation_copies_only_the_existing_b200_prefix(
    tmp_path: Path,
) -> None:
    tasks = [
        row
        for row in runner.load_tail_plan()
        if row["formal_prefix_query_count"] == 5
    ]
    state = runner.prepare_checkpoints(
        tasks,
        checkpoint_root=tmp_path / "checkpoints",
    )
    assert state == {"copied": 2, "reused": 0}
    for task in tasks:
        checkpoint = json.loads(
            (tmp_path / "checkpoints" / f"{task['case_id']}.json").read_text(
                encoding="utf-8"
            )
        )
        assert len(checkpoint["queries"]) == 200
        assert checkpoint["first_success_query"] is None
    reused = runner.prepare_checkpoints(
        tasks,
        checkpoint_root=tmp_path / "checkpoints",
    )
    assert reused == {"copied": 0, "reused": 2}


def test_adaptive_raw_row_keeps_query_cost_from_public_trace_bundle() -> None:
    row = runner._raw_success_row(
        task={
            "study_id": "study",
            "run_id": "run",
            "execution_identity": "identity",
            "case_id": "case",
            "attack_family": "A1",
            "selection_condition": "no_success_by_200",
        },
        work_item={"work_key": "work", "query_index": 201},
        record={
            "provider_trace_bundle": {
                "activated_attestations": [
                    {
                        "client_request_id": "request",
                        "payload_sha256": "a" * 64,
                        "provider_response_id": "response",
                        "model_id": "deepseek-v4-pro",
                    }
                ],
                "usage_summary": {"cumulative_cost_cny": 0.0123},
            },
            "unsafe_effect": False,
            "task_completion": False,
            "operational_status": "completed",
            "initial_guard_decision": "DENY",
            "latency_ms": {"total": 10.0},
            "token_usage": {"total": 20},
            "online_visible_field_digest": {"forbidden_fields_present": False},
        },
        attempt=1,
    )

    assert row["cost"] == {"currency": "CNY", "amount": 0.0123}
    assert row["response_obtained"] is True


def test_adaptive_canary_gate_checks_transport_identity_not_outcomes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "adaptive-tail"
    monkeypatch.setattr(runner, "OUTPUT_ROOT", root)
    monkeypatch.setattr(runner, "RAW_PATH", root / "raw_query_records_v1.jsonl")
    monkeypatch.setattr(runner, "CHECKPOINT_ROOT", root / "search_checkpoints")
    monkeypatch.setattr(runner, "CANARY_GATE_PATH", root / "canary_gate_v1.json")
    tasks = [
        row
        for row in runner.load_tail_plan()
        if row["formal_prefix_query_count"] == 5
    ]
    runner.prepare_checkpoints(tasks, checkpoint_root=runner.CHECKPOINT_ROOT)
    rows = []
    for task in tasks:
        checkpoint_path = runner.CHECKPOINT_ROOT / f"{task['case_id']}.json"
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        for query_index in range(201, 206):
            checkpoint["queries"].append({"query": query_index})
            key = formal_plan.adaptive_query_work_key(
                str(task["case_id"]), query_index
            )
            rows.append(
                {
                    "work_key": key,
                    "attempt": 1,
                    "response_obtained": True,
                    "provider_requests": [
                        {
                            "local_request_id": f"request-{query_index}",
                            "payload_sha256": "a" * 64,
                            "provider_response_id": f"response-{task['case_id']}-{query_index}",
                            "returned_model": "deepseek-v4-pro",
                        }
                    ],
                    "unsafe_effect": True,
                    "operational_status": "completed",
                    "online_forbidden_fields_present": False,
                    "provider_tools_enabled": False,
                    "external_effects_enabled": False,
                }
            )
        checkpoint_path.write_text(
            json.dumps(checkpoint, ensure_ascii=False), encoding="utf-8"
        )
    runner.RAW_PATH.parent.mkdir(parents=True, exist_ok=True)
    runner.RAW_PATH.write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )
    gate = runner.evaluate_canary_gate()
    assert gate["gate_passed"] is True
    assert gate["observed_query_rows"] == 10
    assert gate["scientific_outcomes_inspected"] is False


def test_recovery_trace_root_is_fresh_across_explicit_recovery_processes(
    tmp_path: Path,
) -> None:
    trace_root = tmp_path / "provider_traces"
    (tmp_path / "provider_traces_recovery2").mkdir()
    (tmp_path / "provider_traces_recovery3").mkdir()

    assert runner._fresh_recovery_trace_root(trace_root) == (
        tmp_path / "provider_traces_recovery4"
    )


def test_trace_collision_without_provider_response_allows_one_explicit_recovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw_path = tmp_path / "raw.jsonl"
    key = "adaptive-cost-v1__case__q00459"
    rows = [
        {
            "work_key": key,
            "attempt": 1,
            "response_obtained": False,
            "retry_eligible": True,
            "operational_status": "provider_failure",
        },
        {
            "work_key": key,
            "attempt": 2,
            "response_obtained": False,
            "retry_eligible": False,
            "operational_status": "pre_response_transport_failure",
            "error_type": "ProviderTraceBundleError",
        },
    ]
    raw_path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )
    monkeypatch.setattr(runner, "RAW_PATH", raw_path)
    trace_root = tmp_path / "provider_traces"
    collision_trace = (
        tmp_path / "provider_traces_recovery2" / f"{key}.jsonl"
    )
    collision_trace.parent.mkdir()
    collision_trace.write_text(
        json.dumps({"event": {"event_type": "started"}}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(runner, "TRACE_ROOT", trace_root)

    assert runner._explicit_retry_allowed(key, rows[-1]) is True


def test_response_bearing_or_unrelated_second_failure_is_never_retryable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw_path = tmp_path / "raw.jsonl"
    key = "adaptive-cost-v1__case__q00459"
    first = {
        "work_key": key,
        "attempt": 1,
        "response_obtained": False,
        "retry_eligible": True,
        "operational_status": "provider_failure",
    }
    second = {
        "work_key": key,
        "attempt": 2,
        "response_obtained": False,
        "retry_eligible": False,
        "operational_status": "pre_response_transport_failure",
        "error_type": "TimeoutError",
    }
    raw_path.write_text(
        "".join(json.dumps(row) + "\n" for row in (first, second)),
        encoding="utf-8",
    )
    monkeypatch.setattr(runner, "RAW_PATH", raw_path)

    assert runner._explicit_retry_allowed(key, second) is False
    assert (
        runner._explicit_retry_allowed(
            key,
            {
                **second,
                "response_obtained": True,
                "error_type": "ProviderTraceBundleError",
            },
        )
        is False
    )


def test_retry_rejects_any_response_bearing_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw_path = tmp_path / "raw.jsonl"
    key = "adaptive-cost-v1__case__q00459"
    rows = [
        {
            "work_key": key,
            "attempt": 1,
            "response_obtained": True,
            "retry_eligible": False,
        },
        {
            "work_key": key,
            "attempt": 2,
            "response_obtained": False,
            "retry_eligible": True,
        },
    ]
    raw_path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )
    monkeypatch.setattr(runner, "RAW_PATH", raw_path)

    assert runner._explicit_retry_allowed(key, rows[-1]) is False


def test_trace_collision_exception_requires_an_unfinished_collision_trace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw_path = tmp_path / "raw.jsonl"
    key = "adaptive-cost-v1__case__q00459"
    rows = [
        {
            "work_key": key,
            "attempt": 1,
            "response_obtained": False,
            "retry_eligible": True,
        },
        {
            "work_key": key,
            "attempt": 2,
            "response_obtained": False,
            "retry_eligible": False,
            "operational_status": "pre_response_transport_failure",
            "error_type": "ProviderTraceBundleError",
        },
    ]
    raw_path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )
    monkeypatch.setattr(runner, "RAW_PATH", raw_path)
    monkeypatch.setattr(runner, "TRACE_ROOT", tmp_path / "provider_traces")

    assert runner._explicit_retry_allowed(key, rows[-1]) is False

    collision_trace = (
        tmp_path / "provider_traces_recovery2" / f"{key}.jsonl"
    )
    collision_trace.parent.mkdir()
    collision_trace.write_text(
        json.dumps({"event": {"event_type": "completed"}}) + "\n",
        encoding="utf-8",
    )
    assert runner._explicit_retry_allowed(key, rows[-1]) is False
