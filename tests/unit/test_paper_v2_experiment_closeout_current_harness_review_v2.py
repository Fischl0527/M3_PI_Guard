from __future__ import annotations

import json

import pytest

from experiments.paper_v2 import experiment_closeout_current_harness_review_v2 as review
from experiments.paper_v2.contracts import sha256_canonical_json


def test_persisted_completed_harness_review_remains_historical_evidence() -> None:
    value = json.loads(review.REVIEW_PATH.read_text(encoding="utf-8"))
    core = {key: child for key, child in value.items() if key != "manifest_sha256"}

    assert value["status"] == "passed_recovered_from_terminal_harness_evidence"
    assert value["manifest_sha256"] == sha256_canonical_json(core)
    assert value["observations"]["fail_line_count"] == 0
    assert value["observations"]["terminal_zero_marker_count"] == 1
    assert value["exit_code_evidence"] == {
        "operating_system_exit_code_directly_observed": False,
        "effective_exit_code": 0,
        "basis": (
            "unique_terminal_zero_marker_plus_hash_locked_verify_script_"
            "immediate_exit_contract"
        ),
        "outer_command_timeout_seconds": 3604,
        "original_wrapper_receipt_missing": True,
    }
    assert value["verdict"]["pre_recovery_worktree_full_harness_passed"] is True
    assert (
        value["verdict"][
            "post_recovery_current_worktree_full_harness_directly_observed"
        ]
        is False
    )
    assert value["verdict"]["post_run_executable_delta_scoped_and_verified"]
    assert value["post_run_executable_and_evidence_delta"][
        "runtime_or_experiment_controller_files_changed"
    ] is False
    assert value["evidence_boundary"]["missing_wrapper_receipt_fabricated"] is False


def test_historical_review_rebuild_rejects_advanced_current_harness() -> None:
    with pytest.raises(
        review.ExperimentCloseoutCurrentHarnessReviewV2Error,
        match="current Harness verify_script SHA-256 drift",
    ):
        review.build_review()
