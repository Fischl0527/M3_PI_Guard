from __future__ import annotations

import pytest

from experiments.paper_v2 import gemini_public_v4_wrapper_recovery_v1 as recovery


def test_build_recovery_reconciles_terminal_segment_without_receipt() -> None:
    value = recovery.build_recovery()

    assert value["status"] == (
        "gemini_segment_terminal_reconciled_wrapper_exit_unknown"
    )
    assert value["verdict"] == {
        "segment_evidence_terminal": True,
        "segment_zero_retry_preserved": True,
        "segment_can_be_counted_in_itt": True,
        "future_matrix_continuation_eligible": True,
        "same_segment_retry_authorized": False,
        "wrapper_operating_system_exit_known": False,
        "original_wrapper_receipt_fabricated": False,
        "scientific_result_admission_authorized": False,
    }
    assert value["failure_aware_v5_reconciliation"][
        "runner_failures_retained_in_itt"
    ] == 1
    assert value["evidence_boundary"]["new_provider_calls_made"] == 0


def test_recovery_fails_closed_if_original_receipt_appears(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    receipt = tmp_path / "receipt.json"
    receipt.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(recovery, "MISSING_RECEIPT_PATH", receipt)

    with pytest.raises(
        recovery.GeminiPublicV4WrapperRecoveryV1Error,
        match="unexpectedly exists",
    ):
        recovery.build_recovery()


def test_recovery_fails_closed_on_historical_hash_drift(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    expected = dict(recovery.EXPECTED_HISTORICAL_SHA256)
    first_path = next(iter(expected))
    expected[first_path] = "0" * 64
    monkeypatch.setattr(recovery, "EXPECTED_HISTORICAL_SHA256", expected)

    with pytest.raises(
        recovery.GeminiPublicV4WrapperRecoveryV1Error,
        match="historical source-lock drift",
    ):
        recovery.build_recovery()
