from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.paper_v2.agentdojo_live_dependency import (
    DEFAULT_OUTPUT,
    AgentDojoLiveDependencyError,
    AgentDojoOfflineOutcomeEvaluator,
    FrozenAgentDojoCaseResolver,
    build_qualification,
)
from experiments.paper_v2.formal_condition_executors import OnlineExecutorContext
from experiments.paper_v2.medium_runtime import (
    DEFAULT_V2_PLAN,
    reconstruct_initial_online_state,
)


def _items() -> list[dict]:
    return [
        json.loads(line)
        for line in DEFAULT_V2_PLAN.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _attack_items() -> list[dict]:
    return [
        item
        for item in _items()
        if item["benchmark"] == "agentdojo-v1"
        and item["condition_id"] == "no_defense"
        and item["analysis_tier"] == "primary"
        and "injection_task" in item["case_id"]
    ]


def _context(item: dict) -> OnlineExecutorContext:
    return OnlineExecutorContext(
        execution_identity=item["execution_identity"],
        work_key=item["work_key"],
        benchmark=item["benchmark"],
        condition_id=item["condition_id"],
        max_provider_calls=item["max_provider_calls"],
        online_state=reconstruct_initial_online_state(item),
    )


def test_frozen_official_agentdojo_dependency_reproduces_without_network() -> None:
    current = build_qualification()
    frozen = json.loads(DEFAULT_OUTPUT.read_text(encoding="utf-8"))

    assert current == frozen
    assert (
        current["status"]
        == "official_environment_and_offline_evaluator_qualified"
    )
    assert current["source_lock"]["worktree_clean"] is True
    assert current["qualification_probes"][0]["task_completion"] is True
    assert current["qualification_probes"][0]["unsafe_effect"] is False
    assert current["qualification_probes"][1]["unsafe_effect"] is True
    assert current["network_calls_made"] == 0
    assert current["api_calls_made"] == 0
    assert current["model_calls_made"] == 0
    assert current["formal_results_created"] == 0


def test_private_agentdojo_binding_is_not_in_the_online_projection() -> None:
    item = _attack_items()[0]
    state = reconstruct_initial_online_state(item)
    rendered = json.dumps(state, ensure_ascii=False, sort_keys=True)
    binding = FrozenAgentDojoCaseResolver().resolve(item["work_key"])

    assert binding.injection_task_id is not None
    assert "injection_task_id" not in rendered
    assert binding.injection_task_id not in rendered


def test_offline_evaluator_rejects_material_from_another_work_key() -> None:
    first, second = _attack_items()[:2]
    resolver = FrozenAgentDojoCaseResolver()
    first_context = _context(first)
    schemas = first_context.online_state["agent_input"]["online_inputs"][
        "tool_schemas"
    ]
    schemas = {
        **schemas,
        "final": {
            "arguments": {
                "answer": {"type": "string", "required": True}
            }
        },
    }
    backend = resolver.build_backend(first_context, schemas)
    try:
        material = backend.evaluator_material()
        with pytest.raises(
            AgentDojoLiveDependencyError,
            match="not bound to this frozen work item",
        ):
            AgentDojoOfflineOutcomeEvaluator(resolver).evaluate(
                second, {"offline_evaluator_input": material}
            )
    finally:
        backend.close()


def test_frozen_artifact_does_not_persist_injection_text() -> None:
    rendered = Path(DEFAULT_OUTPUT).read_text(encoding="utf-8")

    assert "TODO:" not in rendered
    assert "injection_payload_sha256" in rendered
