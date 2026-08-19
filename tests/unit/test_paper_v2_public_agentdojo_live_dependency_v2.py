from __future__ import annotations

import json

import pytest

from experiments.paper_v2.agentdojo_live_dependency import (
    AgentDojoLiveDependencyError,
    FrozenAgentDojoCaseResolver,
)
from experiments.paper_v2.formal_condition_executors import (
    OnlineExecutorContext,
)
from experiments.paper_v2.public_agentdojo_live_dependency_v2 import (
    PublicFrozenAgentDojoCaseResolverV2,
    build_public_resolver_qualification,
)
from experiments.paper_v2.public_matrix_plan_v1 import (
    DEFAULT_PLAN,
    reconstruct_public_initial_online_state,
)


def _rows() -> list[dict]:
    return [
        json.loads(line)
        for line in DEFAULT_PLAN.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _public_agentdojo_item() -> dict:
    return next(
        row
        for row in _rows()
        if row["model_role"] == "primary"
        and row["benchmark"] == "agentdojo-v1"
        and row["condition_id"] == "no_defense"
        and row["evaluation_case_type"] == "attack"
    )


def test_public_resolver_qualification_is_offline_and_complete() -> None:
    value = build_public_resolver_qualification()

    assert (
        value["status"]
        == "public_plan_agentdojo_bindings_qualified_offline"
    )
    assert value["plan_records"] == 6873
    assert value["qualification_probe_count"] == 4
    assert value["network_calls_made"] == 0
    assert value["provider_calls_made"] == 0
    assert value["formal_results_created"] == 0


def test_public_work_key_resolves_but_medium_resolver_rejects_it() -> None:
    item = _public_agentdojo_item()
    binding = PublicFrozenAgentDojoCaseResolverV2().resolve(
        item["work_key"]
    )

    assert binding.benchmark_case_id == item["case_id"]
    assert binding.source_record_sha256 == item["source_record_sha256"]
    with pytest.raises(
        AgentDojoLiveDependencyError,
        match="unknown paper-v2 work key",
    ):
        FrozenAgentDojoCaseResolver().resolve(item["work_key"])


def test_public_private_binding_is_absent_from_online_state() -> None:
    item = _public_agentdojo_item()
    state = reconstruct_public_initial_online_state(item)
    binding = PublicFrozenAgentDojoCaseResolverV2().resolve(
        item["work_key"]
    )
    rendered = json.dumps(state, ensure_ascii=False, sort_keys=True)

    assert binding.injection_task_id is not None
    assert "injection_task_id" not in rendered
    assert binding.injection_task_id not in rendered


def test_public_resolver_builds_official_in_memory_backend() -> None:
    item = _public_agentdojo_item()
    state = reconstruct_public_initial_online_state(item)
    context = OnlineExecutorContext(
        execution_identity=item["execution_identity"],
        work_key=item["work_key"],
        benchmark=item["benchmark"],
        condition_id=item["condition_id"],
        max_provider_calls=item["max_provider_calls"],
        online_state=state,
    )
    schemas = state["agent_input"]["online_inputs"]["tool_schemas"]
    schemas = {
        **schemas,
        "final": {
            "arguments": {
                "answer": {"type": "string", "required": True}
            }
        },
    }
    backend = PublicFrozenAgentDojoCaseResolverV2().build_backend(
        context,
        schemas,
    )
    try:
        material = backend.evaluator_material()
        binding = PublicFrozenAgentDojoCaseResolverV2().resolve(
            item["work_key"]
        )
        assert (
            material["evaluator_context"]["binding_sha256"]
            == binding.binding_sha256
        )
    finally:
        backend.close()
