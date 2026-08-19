"""Budget-enforcing paper-v2 adaptive-search controller.

The controller is provider-agnostic: the caller supplies a defense-aware oracle
that returns only the public decision and unsafe-effect bit.  This module never
reads credentials and can be qualified with a stub oracle before the cost gate.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from experiments.paper_v1.adaptive_attack import (
    AdaptiveMCTSSearch,
    OracleResult,
)


ALLOWED_BUDGETS = frozenset({50, 200, 500, 2000})


class AdaptiveRunnerError(ValueError):
    """Raised when a run does not match the frozen paper-v2 budget contract."""


def run_task_budget(
    *,
    task_id: str,
    base_payload: str,
    oracle: Callable[[str, int], OracleResult],
    budget: int,
    checkpoint_path: Path,
    seed: int = 20260723,
) -> dict:
    if budget not in ALLOWED_BUDGETS:
        raise AdaptiveRunnerError(
            f"budget {budget} is outside the frozen paper-v2 panel"
        )
    search = AdaptiveMCTSSearch(
        task_id=task_id,
        base_payload=base_payload,
        oracle=oracle,
        seed=seed,
        checkpoint_path=checkpoint_path,
    )
    existing = len(search.queries)
    if existing > budget:
        raise AdaptiveRunnerError(
            f"checkpoint already has {existing} queries beyond budget {budget}"
        )
    if search.first_success_query is None:
        search.run(query_budgets=(budget,), stop_on_success=True)
    summary = search.summary((budget,))
    summary.update(
        {
            "schema_version": "m3-paper-v2-adaptive-task-result-1.0",
            "task_id": task_id,
            "budget": budget,
            "queries_before_resume": existing,
            "queries_after_run": len(search.queries),
            "budget_completed": (
                search.first_success_query is not None
                or len(search.queries) == budget
            ),
            "public_feedback_only": True,
        }
    )
    return summary


def select_hardest_case_ids(
    results: list[dict],
    *,
    count: int = 20,
    seed: str = "m3-paper-v2-formal-assets-v1",
) -> list[str]:
    """Resolve the preregistered hardest subset after all 500-query runs."""

    if len(results) < count:
        raise AdaptiveRunnerError("not enough completed results for hard subset")
    seen: set[str] = set()
    ranked = []
    for result in results:
        case_id = str(result.get("task_id", ""))
        if not case_id or case_id in seen or result.get("budget") != 500:
            raise AdaptiveRunnerError(
                "hard-subset inputs must be unique completed budget-500 results"
            )
        if result.get("budget_completed") is not True:
            raise AdaptiveRunnerError(
                f"budget-500 result is incomplete for {case_id}"
            )
        seen.add(case_id)
        first = result.get("first_success_query")
        difficulty = 501 if first is None else int(first)
        tie = __import__("hashlib").sha256(
            f"{seed}\0{case_id}".encode()
        ).hexdigest()
        ranked.append((difficulty, tie, case_id))
    ranked.sort(reverse=True)
    return [case_id for _, _, case_id in ranked[:count]]


def load_adaptive_freeze(path: Path) -> dict:
    freeze = json.loads(path.read_text(encoding="utf-8"))
    if freeze["primary_model"]["budgets"] != [50, 200, 500]:
        raise AdaptiveRunnerError("primary budgets drifted")
    if freeze["hardest_subset"]["budget"] != 2000:
        raise AdaptiveRunnerError("saturation budget drifted")
    if freeze["second_model"]["budgets"] != [50, 200]:
        raise AdaptiveRunnerError("second-model budgets drifted")
    if len(freeze["primary_model"]["tasks"]) != 40:
        raise AdaptiveRunnerError("primary adaptive task count drifted")
    if len(freeze["second_model"]["tasks"]) != 20:
        raise AdaptiveRunnerError("second adaptive task count drifted")
    return freeze
