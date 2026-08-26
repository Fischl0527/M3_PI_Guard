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
