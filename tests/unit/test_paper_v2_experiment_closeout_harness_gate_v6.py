from __future__ import annotations

import json

import pytest

from experiments.paper_v2 import experiment_closeout_harness_gate_v6 as gate


def _stdout(*, passed: int = gate.EXPECTED_PYTEST_PASSED) -> str:
    lines = [f"PASS: {name}" for name in gate.prior_gate.EXPECTED_PASS_NAMES]
    lines.extend(
        [
            f"{passed} passed, 1 skipped, 3 warnings in 7212.00s (2:00:12)",
            "Verification failed=0",
        ]
    )
    return "\n".join(lines) + "\n"


def _stderr(*, blocks: int = gate.EXPECTED_RUNTIME_AUDITOR_DELETE_BLOCKS) -> str:
    line = "[RuntimeAuditor] Blocked tool call: delete_record"
    return "\n".join([line] * blocks) + "\n"


def test_gate_requires_exact_v8_terminal_evidence() -> None:
    value = gate.analyze_transcript(_stdout(), _stderr())

    assert value["pytest_passed"] == 1568
    assert value["runtime_auditor_delete_blocks"] == 303
    assert value["secret_pattern_hit_count"] == 0


@pytest.mark.parametrize(
    ("stdout", "stderr"),
    [
        (_stdout(passed=1567), _stderr()),
        (_stdout().replace("PASS: Harness files\n", ""), _stderr()),
        (_stdout().replace("Verification failed=0\n", ""), _stderr()),
        (_stdout(), _stderr(blocks=302)),
        (_stdout(), _stderr() + "Traceback (most recent call last)\n"),
        (_stdout(), _stderr() + "Authorization: Bearer abcdefghijklmnop\n"),
    ],
)
def test_gate_failures_remain_closed(stdout: str, stderr: str) -> None:
    with pytest.raises(
        gate.ExperimentCloseoutHarnessGateV6Error,
        match="terminal evidence did not pass|summary is missing",
    ):
        gate.analyze_transcript(stdout, stderr)


def test_gate_is_v8_specific_and_non_authorizing() -> None:
    assert gate.RUN_ROOT.name == "experiment_closeout_fresh_harness_v8_20260806"
    assert gate.GATE_PATH.name == "experiment_closeout_harness_gate_v6.json"
    source = gate.Path(gate.__file__).read_text(encoding="utf-8")
    assert '"provider_execution_authorized_by_gate": False' in source
    assert '"result_access_authorized_by_gate": False' in source
    assert "completed Adaptive Pro-50 evidence drift" in source
    assert "completed Gemini Public-v5 s1 evidence drift" in source
    assert "prospective Adaptive Pro-200 path drift" in source


def test_gate_binds_single_use_pro_200_wrapper_and_v8_launcher() -> None:
    assert gate.PRO_200_WRAPPER_PATH.name == (
        "run_adaptive_formal_pro_v2_guarded_v4.ps1"
    )
    assert gate.LAUNCHER_PATH.name == (
        "start_experiment_closeout_fresh_harness_v8.ps1"
    )
    assert gate.GEMINI_WRAPPER_GATE_PATH.name == (
        "experiment_closeout_harness_gate_v4.json"
    )


def test_gate_closes_after_pro_200_execution_and_freeze_is_preserved() -> None:
    with pytest.raises(
        gate.ExperimentCloseoutHarnessGateV6Error,
        match="prospective Adaptive Pro-200 path drift",
    ):
        gate._validate_pro_200_path()

    frozen = json.loads(gate.GATE_PATH.read_text(encoding="utf-8"))
    assert frozen["status"] == (
        "fresh_v8_and_completed_prefix_prerequisites_satisfied"
    )
    assert frozen["manifest_sha256"] == (
        "73a57abbd955d6b5099f3fdd1fbb0503017576e3d4758c29d7d760e3f3363a5d"
    )
    assert frozen["technical_scope"]["adaptive_next_tasks"] == 39
    assert frozen["technical_scope"]["adaptive_next_target_budget"] == 200
    assert frozen["verdict"]["provider_execution_authorized_by_gate"] is False
    assert frozen["verdict"]["result_access_authorized_by_gate"] is False
