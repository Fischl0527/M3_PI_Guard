from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from experiments.paper_v2 import (
    adaptive_formal_pro_200_host_timeout_review_v1 as review,
)


def test_null_watcher_exit_is_never_upgraded_to_direct_exit() -> None:
    value = review.recompute_direct_exit_observation(
        {
            "operating_system_exit_code_directly_observed": True,
            "execute_child_exit_code": None,
        }
    )

    assert value["watcher_raw_direct_claim"] is True
    assert value["watcher_exit_code"] is None
    assert value["watcher_exit_code_is_integer"] is False
    assert value["execute_child_exit_code_directly_observed_recomputed"] is False
    assert value["raw_claim_contradicted_by_null_exit"] is True
    assert value["invalid_or_missing_direct_exit_reason"] == (
        "watcher_returned_null_exit_code"
    )


def test_integer_watcher_exit_requires_an_explicit_direct_claim() -> None:
    claimed = review.recompute_direct_exit_observation(
        {
            "operating_system_exit_code_directly_observed": True,
            "execute_child_exit_code": 0,
        }
    )
    unclaimed = review.recompute_direct_exit_observation(
        {
            "operating_system_exit_code_directly_observed": False,
            "execute_child_exit_code": 0,
        }
    )

    assert claimed["execute_child_exit_code_directly_observed_recomputed"] is True
    assert claimed["invalid_or_missing_direct_exit_reason"] is None
    assert unclaimed["execute_child_exit_code_directly_observed_recomputed"] is False
    assert unclaimed["invalid_or_missing_direct_exit_reason"] == (
        "watcher_did_not_claim_direct_observation"
    )


def test_host_timeout_review_freezes_split_exit_and_technical_evidence() -> None:
    value = review.verify_review()
    chain = value["host_timeout_chain"]
    stable = value["independent_stable_technical_recomputation"]

    assert value["status"] == (
        "host_timeout_frozen_technical_gate_verified_wrapper_exit_unproven"
    )
    assert chain["original_wrapper"]["receipt_exists"] is False
    assert (
        chain["original_wrapper"]["original_wrapper_exit_code_directly_observed"]
        is False
    )
    assert (
        chain["watcher"]["execute_child_exit_code_directly_observed_recomputed"]
        is False
    )
    assert chain["watcher"]["watcher_exit_code"] is None
    assert chain["watcher_process_identity"] == {
        "process_id": 9956,
        "process_start_time": "2026-08-07T07:54:27.1237445+08:00",
        "executable": r"F:\robot\Anaconda3\python.exe",
        "running_and_observation_identity_match": True,
        "schema_and_status_match": True,
    }
    assert chain["execute_terminal_contract"]["effective_exit_code"] == 0
    assert chain["execute_terminal_contract"][
        "terminal_query_count_this_stage"
    ] == 5504
    assert chain["v1_finalizer"]["failed_closed"] is True
    assert (
        chain["v2_finalizer"][
            "technical_review_child_exit_code_directly_observed"
        ]
        is True
    )
    assert chain["v2_finalizer"]["technical_review_child_exit_code"] == 0
    assert stable["authorized_task_count_from_candidate"] == 39
    assert stable["terminal_task_count_from_task_metadata"] == 39
    assert stable["unique_terminal_task_count_from_task_metadata"] == 39
    assert stable["target_budget_from_candidate"] == 200
    assert stable["task_event_chain_valid"] is True
    assert stable["budget_event_chain_valid"] is True
    assert stable["final_query_count_sum_from_task_metadata"] == 7454
    assert stable["source_prefix_query_count_from_candidate"] == 1950
    assert stable["terminal_query_count_this_stage_recomputed"] == 5504
    assert stable["terminal_query_count_matches_stdout_and_review"] is True
    assert stable["checkpoint_lock_count"] == 39
    assert stable["stage_cost_cny_independently_summed"] == pytest.approx(
        8.0544754
    )
    assert stable["stage_hard_limit_cny_from_candidate"] == 20.0
    assert stable["stage_cost_within_hard_limit"] is True
    assert stable["technical_review_stable_fields_match"] is True
    assert stable["result_remains_unadmitted"] is True
    assert value["claim_boundary"]["original_wrapper_direct_exit_proven"] is False
    assert value["claim_boundary"]["execute_child_direct_exit_proven"] is False
    assert (
        value["claim_boundary"]["technical_review_child_direct_exit_zero_proven"]
        is True
    )
    assert value["claim_boundary"]["successor_stage_execution_authorized"] is False
    assert value["evidence_boundary"]["query_ledger_opened"] is False
    assert value["evidence_boundary"]["checkpoint_semantics_parsed"] is False
    assert value["evidence_boundary"]["checkpoint_bytes_read_for_hashing"] is True
    assert value["evidence_boundary"]["scientific_outcomes_read"] is False
    assert value["evidence_boundary"]["result_access_authorized"] is False


def test_host_timeout_review_tamper_fails_closed() -> None:
    value = copy.deepcopy(review.verify_review())
    value["host_timeout_chain"]["watcher"][
        "execute_child_exit_code_directly_observed_recomputed"
    ] = True

    with pytest.raises(
        review.AdaptiveFormalPro200HostTimeoutReviewV1Error,
        match="host-timeout review artifact drift",
    ):
        review.validate_review(value)


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


@pytest.mark.parametrize(
    ("field", "replacement"),
    (
        ("process_id", 9957),
        ("process_start_time", "2026-08-07T07:54:28+08:00"),
        ("executable", r"F:\other\python.exe"),
        ("schema_version", "m3-drifted"),
        ("status", "drifted"),
    ),
)
def test_watcher_process_identity_drift_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    replacement: object,
) -> None:
    value = json.loads(
        review.EXECUTE_EXIT_OBSERVATION_PATH.read_text(encoding="utf-8")
    )
    value[field] = replacement
    path = tmp_path / "execute_exit_observation.json"
    _write_json(path, value)
    monkeypatch.setattr(review, "EXECUTE_EXIT_OBSERVATION_PATH", path)

    with pytest.raises(
        review.AdaptiveFormalPro200HostTimeoutReviewV1Error,
        match="finalization chain drift",
    ):
        review._validate_static_chain()


@pytest.mark.parametrize(
    ("field", "replacement"),
    (
        ("execute_child_effective_exit_code", 1),
        ("execute_child_effective_exit_basis", "unsupported"),
        ("controller_sha256", "0" * 64),
        ("execute_stdout_sha256", "0" * 64),
    ),
)
def test_effective_exit_receipt_drift_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    replacement: object,
) -> None:
    value = json.loads(
        review.FINALIZER_V2_RECEIPT_PATH.read_text(encoding="utf-8")
    )
    value[field] = replacement
    path = tmp_path / "technical_review_recovery_receipt_v2.json"
    _write_json(path, value)
    monkeypatch.setattr(review, "FINALIZER_V2_RECEIPT_PATH", path)

    with pytest.raises(
        review.AdaptiveFormalPro200HostTimeoutReviewV1Error,
        match="finalization chain drift",
    ):
        review._validate_static_chain()


def test_execute_stdout_multiple_lines_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "05_execute.stdout.log"
    path.write_text('{}\n{}\n', encoding="utf-8")
    monkeypatch.setattr(review, "ORIGINAL_EXECUTE_STDOUT_PATH", path)

    with pytest.raises(
        review.AdaptiveFormalPro200HostTimeoutReviewV1Error,
        match="exactly one nonempty JSON line",
    ):
        review._validate_static_chain()


def test_missing_wrapper_receipt_cannot_suddenly_appear(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "receipt.json"
    path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(review, "ORIGINAL_RECEIPT_PATH", path)

    with pytest.raises(
        review.AdaptiveFormalPro200HostTimeoutReviewV1Error,
        match="finalization chain drift",
    ):
        review._validate_static_chain()


def test_metadata_ledger_rejects_non_allowlisted_field(tmp_path: Path) -> None:
    path = tmp_path / "metadata.jsonl"
    _write_json(path, {"allowed": 1, "unsafe_effect": True})

    with pytest.raises(
        review.AdaptiveFormalPro200HostTimeoutReviewV1Error,
        match="non-metadata fields or schema drift",
    ):
        review._read_metadata_jsonl(path, allowed_keys=frozenset({"allowed"}))


def test_controller_source_drift_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "controller.py"
    path.write_text(
        review.CONTROLLER_V2_PATH.read_text(encoding="utf-8") + "\n# drift\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(review, "CONTROLLER_V2_PATH", path)

    with pytest.raises(
        review.AdaptiveFormalPro200HostTimeoutReviewV1Error,
        match="terminal exit contract drift",
    ):
        review._verify_controller_exit_contract()
