from __future__ import annotations

from experiments.paper_v1.adaptive_attack import OracleResult
from experiments.paper_v2.adaptive_runner import (
    run_task_budget,
    select_hardest_case_ids,
)


def test_budget_runner_resumes_without_repeating_queries(tmp_path) -> None:
    calls: list[int] = []

    def oracle(_prompt: str, query: int) -> OracleResult:
        calls.append(query)
        return OracleResult(decision="DENY", unsafe_effect=False)

    checkpoint = tmp_path / "checkpoint.json"
    first = run_task_budget(
        task_id="case-1",
        base_payload="attempt the unsafe effect",
        oracle=oracle,
        budget=50,
        checkpoint_path=checkpoint,
    )
    second = run_task_budget(
        task_id="case-1",
        base_payload="attempt the unsafe effect",
        oracle=oracle,
        budget=200,
        checkpoint_path=checkpoint,
    )

    assert first["queries_after_run"] == 50
    assert second["queries_before_resume"] == 50
    assert second["queries_after_run"] == 200
    assert calls == list(range(1, 201))


def test_success_checkpoint_does_not_spend_larger_budget(tmp_path) -> None:
    calls: list[int] = []

    def oracle(_prompt: str, query: int) -> OracleResult:
        calls.append(query)
        return OracleResult(decision="ALLOW", unsafe_effect=query == 3)

    checkpoint = tmp_path / "success.json"
    first = run_task_budget(
        task_id="case-success",
        base_payload="attempt",
        oracle=oracle,
        budget=50,
        checkpoint_path=checkpoint,
    )
    second = run_task_budget(
        task_id="case-success",
        base_payload="attempt",
        oracle=oracle,
        budget=200,
        checkpoint_path=checkpoint,
    )

    assert first["first_success_query"] == 3
    assert second["queries_after_run"] == 3
    assert calls == [1, 2, 3]


def test_hardest_subset_prioritizes_no_success_then_late_success() -> None:
    results = []
    for index in range(25):
        first = None if index < 5 else 100 + index
        results.append(
            {
                "task_id": f"case-{index:02d}",
                "budget": 500,
                "queries_after_run": 500 if first is None else first,
                "budget_completed": True,
                "first_success_query": first,
                "status": "budget_exhausted" if first is None else "success",
            }
        )

    selected = select_hardest_case_ids(results)

    assert len(selected) == 20
    assert {f"case-{index:02d}" for index in range(5)} <= set(selected)
    assert "case-24" in selected
