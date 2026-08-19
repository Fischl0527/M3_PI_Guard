from __future__ import annotations

import pytest

from experiments.paper_v2 import experiment_closeout_day2_harness_gate_v2 as gate


def _stdout(*, failed: int = 0, passed: int = 1500) -> str:
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


def test_transcript_requires_fresh_complete_terminal_success() -> None:
    value = gate.analyze_transcript(_stdout(), "")

    assert value["pytest_passed"] == 1500
    assert value["fail_line_count"] == 0
    assert value["terminal_zero_marker_count"] == 1
    assert value["terminal_zero_marker_is_last_nonempty_line"] is True


@pytest.mark.parametrize(
    ("stdout", "stderr"),
    [
        (_stdout(failed=1), ""),
        (_stdout(passed=gate.MINIMUM_PYTEST_PASSED - 1), ""),
        (_stdout(), "Traceback (most recent call last)\n"),
        (_stdout().replace("Verification failed=0\n", ""), ""),
        (_stdout().replace("PASS: Harness files\n", ""), ""),
    ],
)
def test_transcript_failures_remain_closed(stdout: str, stderr: str) -> None:
    with pytest.raises(
        gate.ExperimentCloseoutDay2HarnessGateV2Error,
        match="terminal evidence did not pass|summary is missing",
    ):
        gate.analyze_transcript(stdout, stderr)


def test_launcher_and_guarded_wrapper_preserve_order_and_safety() -> None:
    launcher = gate.LAUNCHER_PATH.read_text(encoding="utf-8")
    wrapper = gate.WRAPPER_PATH.read_text(encoding="utf-8")

    assert "experiment_closeout_day2_harness_v2_20260803" in launcher
    assert 'network_or_provider_call_authorized = $false' in launcher
    assert 'automatic_restart = $false' in launcher
    assert "experiment_closeout_day2_harness_gate_v2" in wrapper
    assert wrapper.index("--verify-gate") < wrapper.index("New-Item -ItemType Directory")
    assert wrapper.index("--verify-admission") < wrapper.index("--execute-canary")
    assert "automatic_retries = 0" in wrapper
    assert "provider_tools_enabled = $false" in wrapper
    assert "external_effects_enabled = $false" in wrapper


def test_gate_paths_are_fresh_and_do_not_reuse_v1_outputs() -> None:
    assert gate.RUN_ROOT.name == "experiment_closeout_day2_harness_v2_20260803"
    assert gate.GATE_PATH.name == "experiment_closeout_day2_harness_gate_v2.json"
    assert gate.RUN_ROOT.name != "experiment_closeout_day2_harness_v1_20260802"
