from __future__ import annotations

import copy
from pathlib import Path

import pytest

from experiments.paper_v2 import adaptive_formal_pro_500_guarded_runner_v1 as runner
from experiments.paper_v2 import adaptive_formal_pro_controller_v2 as controller


def _fixtures() -> tuple[dict, dict, dict]:
    candidate = controller.verify_stage_candidate("pro_500")
    admission = controller.validate_stage_admission(
        runner._read_json(runner.ADMISSION_PATH),
        stage="pro_500",
    )
    activation = {
        "status": "fresh_harness_passed_exact_pro_500_wrapper_eligible",
        "verdict": {
            "exact_pro_500_guarded_runner_eligible": True,
            "provider_execution_authorized_by_gate_alone": False,
            "result_access_authorized_by_gate": False,
        },
    }
    return activation, candidate, admission


def test_runner_preflight_binds_exact_pro500_scope() -> None:
    activation, candidate, admission = _fixtures()

    value = runner.validate_preflight(
        activation=activation,
        candidate=candidate,
        admission=admission,
        output_root_touched=False,
    )

    assert value["authorized_task_count"] == 36
    assert value["retained_cumulative_diagnostic_count"] == 4
    assert value["source_checkpoint_budget"] == 200
    assert value["target_budget"] == 500
    assert value["stage_hard_limit_cny"] == 35.0


@pytest.mark.parametrize(
    "mutation",
    (
        "gate_authorizes_provider",
        "terminal_replay",
        "automatic_retry",
        "provider_tools",
        "external_effects",
        "result_admission",
        "touched_output",
    ),
)
def test_runner_preflight_safety_drift_fails_closed(mutation: str) -> None:
    activation, candidate, admission = _fixtures()
    activation = copy.deepcopy(activation)
    candidate = copy.deepcopy(candidate)
    admission = copy.deepcopy(admission)
    touched = False
    if mutation == "gate_authorizes_provider":
        activation["verdict"]["provider_execution_authorized_by_gate_alone"] = True
    elif mutation == "terminal_replay":
        admission["authorization"]["terminal_query_replay_authorized"] = True
    elif mutation == "automatic_retry":
        admission["authorization"]["automatic_retries"] = 1
    elif mutation == "provider_tools":
        admission["authorization"]["provider_tools_enabled"] = True
    elif mutation == "external_effects":
        admission["authorization"]["external_effects_enabled"] = True
    elif mutation == "result_admission":
        admission["authorization"]["result_admission_authorized"] = True
    else:
        touched = True

    with pytest.raises(
        runner.AdaptiveFormalPro500GuardedRunnerV1Error,
        match="safety boundary drift",
    ):
        runner.validate_preflight(
            activation=activation,
            candidate=candidate,
            admission=admission,
            output_root_touched=touched,
        )


def test_runner_source_has_one_execute_no_retry_and_direct_child_receipts() -> None:
    source = Path(runner.__file__).read_text(encoding="utf-8")

    assert source.count('"--execute-stage"') == 1
    assert "subprocess.run(" in source
    assert "check=False" in source
    assert "shell=False" in source
    assert "operating_system_exit_code_directly_observed" in source
    assert "automatic_retries" in source
    assert "provider_tools_enabled" in source
    assert "external_effects_enabled" in source
    assert "scientific_outcomes_accessed_by_runner" in source
    assert "result_admission_authorized" in source
    assert "for attempt" not in source
    assert "time.sleep" not in source
    assert "tenacity" not in source
    assert "retrying" not in source


def test_runner_does_not_read_config_contents() -> None:
    source = Path(runner.__file__).read_text(encoding="utf-8")

    assert "CONFIG_PATH.read_" not in source
    assert "dotenv" not in source
    assert "--config" in source
