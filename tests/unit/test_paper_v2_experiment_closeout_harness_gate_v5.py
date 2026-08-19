from __future__ import annotations

import pytest

from experiments.paper_v2 import experiment_closeout_harness_gate_v5 as gate


def _stdout(*, passed: int = gate.EXPECTED_PYTEST_PASSED) -> str:
    lines = [f"PASS: {name}" for name in gate.EXPECTED_PASS_NAMES]
    lines.extend(
        [
            f"{passed} passed, 1 skipped, 3 warnings in 4840.55s (1:20:40)",
            "Verification failed=0",
        ]
    )
    return "\n".join(lines) + "\n"


def _stderr(*, blocks: int = gate.EXPECTED_RUNTIME_AUDITOR_DELETE_BLOCKS) -> str:
    line = "[RuntimeAuditor] Blocked tool call: delete_record"
    return "\n".join([line] * blocks) + "\n"


def test_gate_requires_exact_v7_terminal_evidence() -> None:
    value = gate.analyze_transcript(_stdout(), _stderr())

    assert value["pytest_passed"] == 1552
    assert value["runtime_auditor_delete_blocks"] == 213
    assert value["secret_pattern_hit_count"] == 0


@pytest.mark.parametrize(
    ("stdout", "stderr"),
    [
        (_stdout(passed=1551), _stderr()),
        (_stdout().replace("PASS: Harness files\n", ""), _stderr()),
        (_stdout().replace("Verification failed=0\n", ""), _stderr()),
        (_stdout(), _stderr(blocks=212)),
        (_stdout(), _stderr() + "Traceback (most recent call last)\n"),
        (_stdout(), _stderr() + "Authorization: Bearer abcdefghijklmnop\n"),
    ],
)
def test_gate_failures_remain_closed(stdout: str, stderr: str) -> None:
    with pytest.raises(
        gate.ExperimentCloseoutHarnessGateV5Error,
        match="terminal evidence did not pass|summary is missing",
    ):
        gate.analyze_transcript(stdout, stderr)


def test_gate_is_v7_specific_and_non_authorizing() -> None:
    assert gate.RUN_ROOT.name == "experiment_closeout_fresh_harness_v7_20260806"
    assert gate.GATE_PATH.name == "experiment_closeout_harness_gate_v5.json"
    source = gate.Path(gate.__file__).read_text(encoding="utf-8")
    assert '"provider_execution_authorized_by_gate": False' in source
    assert '"result_access_authorized_by_gate": False' in source
    assert "historical_medium_v7_immutable_audit" in source
    assert "adaptive_pro_50_candidate" in source
    assert "gemini_public_v5_segment_0_review" in source


def test_gate_binds_new_adaptive_wrapper_and_immutable_v7_launcher() -> None:
    assert gate.ADAPTIVE_WRAPPER_PATH.name == (
        "run_adaptive_formal_pro_v2_guarded_v3.ps1"
    )
    assert gate.LAUNCHER_PATH.name == (
        "start_experiment_closeout_fresh_harness_v7.ps1"
    )


def test_process_scoped_git_qualification_restores_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GIT_CONFIG_COUNT", "2")
    monkeypatch.setenv("GIT_CONFIG_KEY_2", "existing.key")
    monkeypatch.setenv("GIT_CONFIG_VALUE_2", "existing-value")

    with gate._process_scoped_safe_directories():
        assert gate.os.environ["GIT_CONFIG_COUNT"] == str(
            2 + len(gate.SAFE_GIT_CHECKOUTS)
        )
        assert gate.os.environ["GIT_CONFIG_KEY_2"] == "safe.directory"
        assert gate.os.environ["GIT_CONFIG_VALUE_2"] == (
            gate.SAFE_GIT_CHECKOUTS[0].resolve().as_posix()
        )

    assert gate.os.environ["GIT_CONFIG_COUNT"] == "2"
    assert gate.os.environ["GIT_CONFIG_KEY_2"] == "existing.key"
    assert gate.os.environ["GIT_CONFIG_VALUE_2"] == "existing-value"
