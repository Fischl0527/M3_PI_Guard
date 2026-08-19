from __future__ import annotations

import pytest

from experiments.paper_v2 import experiment_closeout_harness_gate_v4 as gate


def _stdout(*, passed: int = gate.EXPECTED_PYTEST_PASSED) -> str:
    lines = [f"PASS: {name}" for name in gate.EXPECTED_PASS_NAMES]
    lines.extend(
        [
            f"{passed} passed, 1 skipped, 3 warnings in 6664.43s (1:51:04)",
            "Verification failed=0",
        ]
    )
    return "\n".join(lines) + "\n"


def _stderr(*, blocks: int = gate.EXPECTED_RUNTIME_AUDITOR_DELETE_BLOCKS) -> str:
    line = "[RuntimeAuditor] Blocked tool call: delete_record"
    return "\n".join([line] * blocks) + "\n"


def test_gate_requires_exact_v6_terminal_evidence() -> None:
    value = gate.analyze_transcript(_stdout(), _stderr())

    assert value["pytest_passed"] == 1538
    assert value["runtime_auditor_delete_blocks"] == 183
    assert value["secret_pattern_hit_count"] == 0


@pytest.mark.parametrize(
    ("stdout", "stderr"),
    [
        (_stdout(passed=1537), _stderr()),
        (_stdout().replace("PASS: Harness files\n", ""), _stderr()),
        (_stdout().replace("Verification failed=0\n", ""), _stderr()),
        (_stdout(), _stderr(blocks=182)),
        (_stdout(), _stderr() + "Traceback (most recent call last)\n"),
        (_stdout(), _stderr() + "Authorization: Bearer abcdefghijklmnop\n"),
    ],
)
def test_gate_failures_remain_closed(stdout: str, stderr: str) -> None:
    with pytest.raises(
        gate.ExperimentCloseoutHarnessGateV4Error,
        match="terminal evidence did not pass|summary is missing",
    ):
        gate.analyze_transcript(stdout, stderr)


def test_gate_is_v6_specific_and_non_authorizing() -> None:
    assert gate.RUN_ROOT.name == "experiment_closeout_fresh_harness_v6_20260805"
    assert gate.GATE_PATH.name == "experiment_closeout_harness_gate_v4.json"
    source = gate.Path(gate.__file__).read_text(encoding="utf-8")
    assert '"provider_execution_authorized_by_gate": False' in source
    assert '"result_access_authorized_by_gate": False' in source
    assert "VERIFY_SCRIPT_PATH" not in source
