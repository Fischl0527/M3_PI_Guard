from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.paper_v2.exact_gold_ablation import (
    DEFAULT_OUTPUT,
    ExactGoldAblationError,
    ExactGoldAblationMonitor,
    build_qualification,
)
from experiments.paper_v2.medium_runtime import (
    DEFAULT_V2_PLAN,
    reconstruct_initial_online_state,
)
from m3_guard.runtime_monitor import ActionProposal


def _items() -> list[dict]:
    return [
        json.loads(line)
        for line in DEFAULT_V2_PLAN.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _nonempty_exact_item() -> dict:
    return next(
        item
        for item in _items()
        if item["benchmark"] == "agentdojo-v1"
        and item["condition_id"] == "m3_full"
        and item["authorization_regime"] == "exact_gold"
    )


def _proposal(item: dict, tool: str, arguments: dict) -> ActionProposal:
    return ActionProposal(
        proposal_id=item["work_key"] + ":test",
        tool=tool,
        arguments=arguments,
        provenance=(),
    )


def test_exact_gold_qualification_is_probe_only_and_reproducible() -> None:
    current = build_qualification()
    frozen = json.loads(DEFAULT_OUTPUT.read_text(encoding="utf-8"))

    assert current == frozen
    assert current["analysis_tier"] == "authorization_regime_probe"
    assert current["formal_primary_endpoint_eligible"] is False
    assert current["monitor_semantics"][
        "routed_through_non_oracle_runtime_monitor"
    ] is False
    assert current["prompt_isolation"][
        "exact_arguments_visible_to_provider"
    ] is False
    assert current["network_calls_made"] == 0
    assert current["formal_results_created"] == 0


def test_exact_monitor_requires_explicit_evaluator_derived_boundary() -> None:
    item = _nonempty_exact_item()
    authorization = reconstruct_initial_online_state(item)[
        "runtime_control"
    ]["authorization"]

    wrong = dict(authorization)
    wrong["source_class"] = "online_compiled_authorization"
    with pytest.raises(
        ExactGoldAblationError,
        match="evaluator-derived authorization",
    ):
        ExactGoldAblationMonitor(wrong)

    primary = dict(authorization)
    primary["formal_primary_endpoint_eligible"] = True
    with pytest.raises(
        ExactGoldAblationError,
        match="excluded from the primary endpoint",
    ):
        ExactGoldAblationMonitor(primary)


def test_exact_monitor_enforces_arguments_and_single_use() -> None:
    item = _nonempty_exact_item()
    authorization = reconstruct_initial_online_state(item)[
        "runtime_control"
    ]["authorization"]
    rule = authorization["rules"][0]
    arguments = {
        name: constraint["value"]
        for name, constraint in rule["argument_constraints"].items()
    }
    monitor = ExactGoldAblationMonitor(authorization)

    wrong = dict(arguments)
    if wrong:
        wrong[next(iter(wrong))] = "mismatch"
    else:
        wrong["unexpected"] = "mismatch"
    assert monitor.decide(
        _proposal(item, rule["tool"], wrong)
    ).decision == "DENY"

    proposal = _proposal(item, rule["tool"], arguments)
    allowed = monitor.decide(proposal)
    assert allowed.decision == "ALLOW"
    monitor.record_execution(proposal, allowed)
    assert monitor.decide(proposal).decision == "DENY"


def test_exact_gold_artifact_does_not_persist_rule_values() -> None:
    rendered = Path(DEFAULT_OUTPUT).read_text(encoding="utf-8")

    assert "evaluator-derived-1" not in rendered
    assert "argument_constraints" not in rendered
