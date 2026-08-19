from __future__ import annotations

import pytest

from experiments.paper_v2 import experiment_closeout_day2_harness_gate_v1 as gate


def _stdout(*, failed: int = 0, passed: int = 1400) -> str:
    lines = [f"PASS: {name}" for name in gate.EXPECTED_PASS_NAMES]
    if failed:
        lines.append("FAIL: synthetic failure")
    lines.extend(
        [
            f"{passed} passed, 1 skipped, 3 warnings in 5000.00s (1:23:20)",
            f"Verification failed={failed}",
        ]
    )
    return "\n".join(lines) + "\n"


def test_transcript_requires_complete_terminal_success() -> None:
    value = gate.analyze_transcript(_stdout(), "")

    assert value["pytest_passed"] == 1400
    assert value["fail_line_count"] == 0
    assert value["terminal_zero_marker_count"] == 1
    assert value["terminal_zero_marker_is_last_nonempty_line"] is True


@pytest.mark.parametrize(
    ("stdout", "stderr"),
    [
        (_stdout(failed=1), ""),
        (_stdout(passed=1364), ""),
        (_stdout(), "Traceback (most recent call last)\n"),
        (_stdout().replace("Verification failed=0\n", ""), ""),
    ],
)
def test_transcript_failures_remain_closed(stdout: str, stderr: str) -> None:
    with pytest.raises(
        gate.ExperimentCloseoutDay2HarnessGateV1Error,
        match="terminal evidence did not pass|summary is missing",
    ):
        gate.analyze_transcript(stdout, stderr)
