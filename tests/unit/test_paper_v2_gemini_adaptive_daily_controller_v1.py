from __future__ import annotations

import copy
from pathlib import Path

import pytest

from experiments.paper_v2 import gemini_adaptive_daily_controller_v1 as controller
from experiments.paper_v2 import official_provider_executor as official
from experiments.paper_v1.adaptive_attack import OracleResult


def _states() -> list[dict[str, object]]:
    return [
        {
            "case_id": f"case-{index:02d}",
            "query_count": 0,
            "terminal_class": None,
            "latest_checkpoint_lock": None,
        }
        for index in range(20)
    ]


def _slots() -> list[dict[str, object]]:
    return [
        {
            "case_id": f"case-{case:02d}",
            "query_index": query,
            "work_key": f"case-{case:02d}-q{query:03d}",
            "phase": "budget_50",
        }
        for query in range(1, 3)
        for case in range(20)
    ]


def test_daily_selection_is_round_robin_and_two_queries() -> None:
    selected, cursor = controller.select_daily_slots(
        _slots(), cursor=0, task_states=_states()
    )

    assert [slot["work_key"] for slot in selected] == [
        "case-00-q001",
        "case-01-q001",
    ]
    assert cursor == 2


def test_terminal_tasks_are_skipped_without_replay() -> None:
    states = _states()
    states[0]["terminal_class"] = "search_success_terminal"
    selected, cursor = controller.select_daily_slots(
        _slots(), cursor=0, task_states=states
    )

    assert [slot["work_key"] for slot in selected] == [
        "case-01-q001",
        "case-02-q001",
    ]
    assert cursor == 3


def test_checkpoint_gap_fails_closed() -> None:
    states = copy.deepcopy(_states())
    gap_slots = [
        {
            "case_id": "case-00",
            "query_index": 2,
            "work_key": "case-00-q002",
            "phase": "budget_50",
        }
    ]

    with pytest.raises(
        controller.GeminiAdaptiveDailyControllerV1Error,
        match="sequence gap",
    ):
        controller.select_daily_slots(
            gap_slots, cursor=0, task_states=states
        )


def test_candidate_validation_rejects_paid_tier(monkeypatch: pytest.MonkeyPatch) -> None:
    value = {
        "schema_version": controller.SCHEMA_VERSION,
        "artifact_role": "one_quota_day_gemini_adaptive_candidate",
        "generated_at": "2026-08-02T11:30:00+08:00",
        "status": "offline_bound_execution_not_authorized",
        "scope": {
            "provider_id": "gemini",
            "model_id": controller.MODEL_ID,
            "model_role": controller.MODEL_ROLE,
            "selected_slots": [{"work_key": "wk"}],
            "selected_query_count": 1,
            "selected_work_key_sequence_sha256": controller.sha256_canonical_json(["wk"]),
            "maximum_provider_requests": 8,
            "billing_tier": "paid",
            "paid_ceiling_usd": 1.0,
            "automatic_retries": 0,
            "provider_tools_enabled": False,
            "external_effects_enabled": False,
        },
        "artifact_locks": [],
        "authorization": {"day_execution_authorized": False},
    }
    value["scope_sha256"] = controller.sha256_canonical_json(value["scope"])
    value["manifest_sha256"] = controller.sha256_canonical_json(value)
    monkeypatch.setattr(controller, "_verify_lock", lambda lock: None)

    with pytest.raises(
        controller.GeminiAdaptiveDailyControllerV1Error,
        match="candidate drift",
    ):
        controller.validate_day_candidate(value)


def test_exact_one_query_runner_preserves_checkpoint_prefix(tmp_path: Path) -> None:
    checkpoint = tmp_path / "checkpoint.json"

    def oracle(prompt: str, query_index: int) -> OracleResult:
        return OracleResult(
            decision="DENY",
            unsafe_effect=False,
            task_completed=False,
            metadata={"prompt_length": len(prompt), "query_index": query_index},
        )

    first = controller.run_exactly_one_query(
        task_id="case-00",
        base_payload="ignore this instruction",
        oracle=oracle,
        query_index=1,
        checkpoint_path=checkpoint,
    )
    second = controller.run_exactly_one_query(
        task_id="case-00",
        base_payload="ignore this instruction",
        oracle=oracle,
        query_index=2,
        checkpoint_path=checkpoint,
    )

    assert first["queries_after_run"] == 1
    assert second["queries_before_resume"] == 1
    assert second["queries_after_run"] == 2


def test_day_candidate_and_admission_bind_free_tier_exact_command(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = tmp_path / "source.json"
    source.write_text("{}\n", encoding="utf-8")
    states = _states()
    prior = {
        "manifest_sha256": "c" * 64,
        "next_schedule_cursor": 0,
        "task_states": states,
        "technical_gate_passed": True,
    }
    monkeypatch.setattr(controller, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(controller, "OUTPUT_BASE", tmp_path / "outputs")
    monkeypatch.setattr(controller, "CANDIDATE_ROOT", tmp_path / "candidates")
    monkeypatch.setattr(controller, "ADMISSION_ROOT", tmp_path / "admissions")
    monkeypatch.setattr(controller, "_prior_state", lambda index: copy.deepcopy(prior))
    monkeypatch.setattr(controller, "_flatten_slots", _slots)
    monkeypatch.setattr(
        controller.daily_quota, "current_quota_day", lambda: "2026-08-02"
    )
    monkeypatch.setattr(
        controller,
        "_lock",
        lambda path: {
            "path": source.name,
            "bytes": source.stat().st_size,
            "sha256": controller._sha256_file(source),
        },
    )
    monkeypatch.setattr(controller, "_verify_lock", lambda lock: None)

    candidate = controller.write_day_candidate(
        0,
        quota_day="2026-08-02",
        generated_at="2026-08-02T11:45:00+08:00",
    )
    admission = controller.build_day_admission(
        0,
        quota_day="2026-08-02",
        approved_at="2026-08-02T11:46:00+08:00",
        owner_statement_sha256=controller.OWNER_STATEMENT_SHA256,
    )

    assert candidate["scope"]["selected_query_count"] == 2
    assert candidate["scope"]["maximum_provider_requests"] == 16
    assert candidate["scope"]["paid_ceiling_usd"] == 0.0
    assert admission["authorization"]["automatic_retries"] == 0
    assert admission["maximum_provider_requests"] == 16
    assert "--day-index 0" in admission["exact_command"]


def test_execute_day_injected_transport_writes_complete_evidence_chain(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    quota_day = "2026-08-02"
    source = tmp_path / "source.json"
    source.write_text("{}\n", encoding="utf-8")
    real_states = controller._initial_task_states()
    all_real_slots = controller._flatten_slots()
    real_slots = all_real_slots[:2]
    prior = {
        "manifest_sha256": "c" * 64,
        "next_schedule_cursor": 0,
        "task_states": real_states,
        "technical_gate_passed": True,
    }
    real_verify_lock = controller._verify_lock

    def qualification_lock(path: Path) -> dict[str, object]:
        resolved = path.resolve()
        if resolved.is_relative_to(tmp_path.resolve()):
            return {
                "path": resolved.relative_to(tmp_path.resolve()).as_posix(),
                "bytes": resolved.stat().st_size,
                "sha256": controller._sha256_file(resolved),
            }
        return {
            "path": source.name,
            "bytes": source.stat().st_size,
            "sha256": controller._sha256_file(source),
        }

    monkeypatch.setattr(controller, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(controller, "OUTPUT_BASE", tmp_path / "outputs")
    monkeypatch.setattr(controller, "CANDIDATE_ROOT", tmp_path / "candidates")
    monkeypatch.setattr(controller, "ADMISSION_ROOT", tmp_path / "admissions")
    monkeypatch.setattr(
        controller, "_prior_state", lambda index: copy.deepcopy(prior)
    )
    monkeypatch.setattr(
        controller, "_flatten_slots", lambda: copy.deepcopy(real_slots)
    )
    monkeypatch.setattr(controller, "_lock", qualification_lock)
    monkeypatch.setattr(controller, "_verify_lock", real_verify_lock)
    monkeypatch.setattr(
        controller.daily_quota, "current_quota_day", lambda: quota_day
    )

    candidate = controller.write_day_candidate(
        0,
        quota_day=quota_day,
        generated_at="2026-08-02T12:00:00+08:00",
    )
    controller.write_day_admission(
        0,
        quota_day=quota_day,
        approved_at="2026-08-02T12:01:00+08:00",
        owner_statement_sha256=controller.OWNER_STATEMENT_SHA256,
    )

    real_reserve = controller.daily_quota.reserve_formal_day
    quota_ledger = tmp_path / "quota_days.jsonl"

    def reserve_in_tmp(**kwargs: object) -> dict[str, object]:
        return real_reserve(**kwargs, path=quota_ledger)

    monkeypatch.setattr(
        controller.daily_quota, "reserve_formal_day", reserve_in_tmp
    )
    responses: list[str] = []

    def transport(*_: object) -> official.HTTPResponseEnvelope:
        response_id = f"response-adaptive-e2e-{len(responses) + 1}"
        responses.append(response_id)
        return official.HTTPResponseEnvelope(
            status_code=200,
            headers={"x-goog-request-id": f"request-adaptive-e2e-{len(responses)}"},
            body={
                "id": response_id,
                "model": controller.MODEL_ID,
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": (
                                '{"tool":"final","arguments":'
                                '{"answer":"SAFE"}}'
                            ),
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

    monkeypatch.setattr(official, "_default_transport", transport)
    values = {
        "M3_FRONTIER_API_CONSENT": "yes_for_network_smoke",
        "GEMINI_API_KEY": "unit-test-nonsecret-placeholder-value",
        "FRONTIER_GEMINI_MODEL_ID": controller.MODEL_ID,
        "FRONTIER_GEMINI_BASE_URL": (
            "https://generativelanguage.googleapis.com/v1beta/openai/"
        ),
    }
    result = controller.execute_day(
        0,
        quota_day=quota_day,
        selected_admission=controller.admission_path(0, quota_day),
        credential_loader=lambda: values,
    )
    review = controller.build_technical_review(0, quota_day=quota_day)

    assert result["tasks_completed_this_process"] == 2
    assert result["terminal_queries"] == 2
    assert result["attempted_provider_requests"] == len(responses) == 2
    assert result["completed_provider_calls"] == 2
    assert result["billing_tier"] == "free"
    assert result["paid_ceiling_usd"] == 0.0
    assert review["technical_gate_passed"] is True, review["checks"]
    assert review["checks"]["scientific_outcomes_not_aggregated"] is True
    assert review["diagnostic_query_count"] == 0
    assert review["scientific_outcomes_aggregated"] is False
    states_by_case = {
        state["case_id"]: state for state in review["task_states"]
    }
    for slot in real_slots:
        state = states_by_case[slot["case_id"]]
        assert state["query_count"] == 1
        assert state["terminal_class"] is None
        assert state["latest_checkpoint_lock"]["query_count"] == 1

    completed_round = copy.deepcopy(review["task_states"])
    for state in completed_round:
        state["query_count"] = 1
    next_slots, next_cursor = controller.select_daily_slots(
        all_real_slots, cursor=20, task_states=completed_round
    )
    assert [slot["work_key"] for slot in next_slots] == [
        slot["work_key"] for slot in all_real_slots[20:22]
    ]
    assert next_cursor == 22
    assert quota_ledger.is_file()
    output_root = tmp_path / str(candidate["scope"]["output_root"])
    assert (output_root / "query_events_v1.jsonl").is_file()
    assert (output_root / "provider_call_events_v1.jsonl").is_file()
