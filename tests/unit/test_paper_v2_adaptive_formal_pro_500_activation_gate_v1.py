from __future__ import annotations

import copy

import pytest

from experiments.paper_v2 import adaptive_formal_pro_500_activation_gate_v1 as gate


def _receipt_fixture() -> tuple[dict, dict, dict, dict[str, str]]:
    hashes = {
        "verify": "1" * 64,
        "helper": "2" * 64,
        "launcher": "3" * 64,
        "running": "4" * 64,
        "stdout": "5" * 64,
        "stderr": "6" * 64,
    }
    launch = {
        "schema_version": "m3-harness-detached-launch-3.0",
        "status": "launched_detached",
        "verify_script_sha256": hashes["verify"],
        "helper_script_sha256": hashes["helper"],
        "launcher_script_sha256": hashes["launcher"],
        "network_or_provider_call_authorized": False,
        "automatic_restart": False,
    }
    running = {
        "schema_version": "m3-harness-detached-running-3.0",
        "verify_script_sha256": hashes["verify"],
        "helper_script_sha256": hashes["helper"],
        "network_or_provider_call_authorized": False,
        "automatic_restart": False,
    }
    receipt = {
        "schema_version": "m3-harness-detached-receipt-3.0",
        "status": "completed_exit_zero_evidence_pass",
        "operating_system_exit_code_directly_observed": True,
        "child_exit_code": 0,
        "exit_code": 0,
        "evidence_gate_passed": True,
        "checks": {"all": True},
        "verify_script_sha256_before": hashes["verify"],
        "verify_script_sha256_after": hashes["verify"],
        "helper_script_sha256_before": hashes["helper"],
        "helper_script_sha256_after": hashes["helper"],
        "running_sha256": hashes["running"],
        "stdout_sha256": hashes["stdout"],
        "stderr_sha256": hashes["stderr"],
        "aggregate_marker_count": 1,
        "zero_marker_count": 1,
        "failed_harness_stage_count": 0,
        "network_or_provider_call_authorized": False,
        "automatic_restart": False,
    }
    return launch, running, receipt, hashes


def test_receipt_contract_accepts_only_direct_stable_exit_zero() -> None:
    launch, running, receipt, hashes = _receipt_fixture()

    gate.validate_receipt_contract(
        launch=launch,
        running=running,
        receipt=receipt,
        verify_sha256=hashes["verify"],
        helper_sha256=hashes["helper"],
        launcher_sha256=hashes["launcher"],
        running_sha256=hashes["running"],
        stdout_sha256=hashes["stdout"],
        stderr_sha256=hashes["stderr"],
    )


@pytest.mark.parametrize(
    ("field", "replacement"),
    (
        ("operating_system_exit_code_directly_observed", False),
        ("child_exit_code", 1),
        ("evidence_gate_passed", False),
        ("failed_harness_stage_count", 1),
        ("network_or_provider_call_authorized", True),
        ("automatic_restart", True),
    ),
)
def test_receipt_contract_drift_fails_closed(field: str, replacement: object) -> None:
    launch, running, receipt, hashes = _receipt_fixture()
    receipt = copy.deepcopy(receipt)
    receipt[field] = replacement

    with pytest.raises(
        gate.AdaptiveFormalPro500ActivationGateV1Error,
        match="receipt contract drift",
    ):
        gate.validate_receipt_contract(
            launch=launch,
            running=running,
            receipt=receipt,
            verify_sha256=hashes["verify"],
            helper_sha256=hashes["helper"],
            launcher_sha256=hashes["launcher"],
            running_sha256=hashes["running"],
            stdout_sha256=hashes["stdout"],
            stderr_sha256=hashes["stderr"],
        )


def test_terminal_log_contract_requires_all_stages_and_zero_marker() -> None:
    stdout = "\n".join(
        [
            *(f"PASS: {name}" for name in gate.EXPECTED_PASS_NAMES),
            "1700 passed, 1 skipped, 3 warnings in 5200.00s (1:26:40)",
            "Verification failed=0",
        ]
    )

    value = gate.validate_harness_logs(stdout, "")

    assert value["pytest_passed"] == 1700
    assert value["pytest_skipped"] == 1
    assert value["pytest_warnings"] == 3
    assert value["failed_stage_count"] == 0
    assert value["secret_pattern_hit_count"] == 0


def test_terminal_log_secret_or_failed_stage_fails_closed() -> None:
    stdout = "\n".join(
        [
            *(f"PASS: {name}" for name in gate.EXPECTED_PASS_NAMES),
            "1700 passed, 1 skipped, 3 warnings in 5200.00s",
            "FAIL: injected",
            "Verification failed=0",
            "Bearer ABCDEFGHIJKLMNOP",
        ]
    )

    with pytest.raises(
        gate.AdaptiveFormalPro500ActivationGateV1Error,
        match="terminal log contract drift",
    ):
        gate.validate_harness_logs(stdout, "")


def test_activation_gate_markers_cover_future_runner_and_launchers() -> None:
    assert set(gate.REQUIRED_VERIFY_SOURCE_MARKERS) == {
        "experiment_closeout_harness_gate_v7",
        "experiment_closeout_fresh_harness_failure_review_v10",
        "adaptive_formal_pro_500_activation_gate_v1.py",
        "adaptive_formal_pro_500_guarded_runner_v1.py",
        "start_adaptive_formal_pro_500_guarded_v1.ps1",
        "start_experiment_closeout_fresh_harness_v12.ps1",
    }
    assert len(gate._validate_verify_source()) == 64
