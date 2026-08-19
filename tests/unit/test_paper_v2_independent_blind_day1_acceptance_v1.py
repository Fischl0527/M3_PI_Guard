from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from experiments.paper_v2 import independent_blind_day1_acceptance_v1 as day1


def test_frozen_day1_registration_acceptance_replays() -> None:
    value = day1.verify_acceptance()

    assert value["status"] == "independent_custodian_day1_registration_accepted"
    assert len(value["source_files"]) == 3
    assert all(value["checks"].values())
    assert value["registration"]["recorded_check_count"] == 28
    assert value["evidence_boundary"] == {
        "offline_identity_attestation_content_opened": False,
        "private_key_opened": False,
        "candidate_or_label_files_received": 0,
        "label_rows_read": 0,
        "network_calls_made": 0,
        "provider_calls_made": 0,
        "execution_authorized": False,
        "clock_start_technical_gate_satisfied": True,
        "real_person_identity_remains_offline_attestation": True,
        "blind_dataset_authoring_completed": False,
    }


def test_day1_import_rejects_an_extra_file(tmp_path: Path) -> None:
    for source in day1.DEFAULT_INBOX.iterdir():
        shutil.copyfile(source, tmp_path / source.name)
    (tmp_path / "labels.jsonl").write_text("forbidden\n", encoding="utf-8")

    with pytest.raises(
        day1.IndependentBlindDay1AcceptanceV1Error,
        match="exactly the three public registration files",
    ):
        day1.build_acceptance(inbox=tmp_path)
