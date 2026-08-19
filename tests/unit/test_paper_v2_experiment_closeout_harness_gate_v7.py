from __future__ import annotations

import copy

import pytest

from experiments.paper_v2 import experiment_closeout_harness_gate_v7 as gate


def test_gate_rebuilds_fresh_v9_pro200_and_pro500_prerequisites() -> None:
    value = gate.build_gate()

    assert value["status"] == (
        "pro_500_prerequisites_satisfied_fresh_harness_required"
    )
    assert value["fresh_harness_v9"]["direct_os_exit_observed"] is True
    assert value["fresh_harness_v9"]["exit_code"] == 0
    assert value["fresh_harness_v9"]["pytest_passed"] == 1584
    assert value["pro_200_closeout"]["terminal_tasks"] == 39
    assert value["pro_200_closeout"]["incremental_terminal_queries"] == 5504
    assert value["pro_500"]["authorized_tasks"] == 36
    assert value["pro_500"]["retained_cumulative_diagnostics"] == 4
    assert value["pro_500"]["source_checkpoint_budget"] == 200
    assert value["pro_500"]["target_budget"] == 500


def test_gate_is_explicitly_non_authorizing_until_new_full_harness() -> None:
    value = gate.build_gate()

    assert value["verdict"]["provider_execution_authorized_by_gate"] is False
    assert value["verdict"]["result_access_authorized_by_gate"] is False
    assert value["verdict"]["post_integration_full_harness_required"] is True
    assert value["verdict"]["detached_single_use_wrapper_required"] is True
    assert value["evidence_boundary"]["provider_calls_made"] == 0
    assert value["evidence_boundary"]["scientific_outcomes_accessed"] is False


def test_gate_preserves_split_pro200_exit_claim() -> None:
    value = gate.build_gate()["pro_200_closeout"]

    assert value["original_wrapper_direct_exit_proven"] is False
    assert value["execute_child_direct_exit_proven"] is False
    assert value["technical_review_child_direct_exit_zero_proven"] is True
    assert value["result_admission_authorized"] is False


def test_gate_artifact_tamper_fails_closed() -> None:
    value = copy.deepcopy(gate.build_gate())
    value["verdict"]["provider_execution_authorized_by_gate"] = True

    with pytest.raises(
        gate.ExperimentCloseoutHarnessGateV7Error,
        match="gate artifact drift",
    ):
        gate.validate_gate(value)
