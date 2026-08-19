from __future__ import annotations

import copy
from pathlib import Path

import pytest

import experiments.paper_v2.gemini_local_precommit_contract_v2_candidate as candidate


@pytest.fixture(scope="module")
def frozen_candidate() -> dict[str, object]:
    return candidate.build_candidate()


def test_candidate_is_non_executable_and_binds_negative_probes(
    frozen_candidate: dict[str, object],
) -> None:
    value = candidate.validate_candidate(frozen_candidate)

    assert value["status"] == "candidate_pending_fresh_full_harness"
    assert value["authorization"] == {
        "candidate_only": True,
        "provider_execution_authorized": False,
        "historical_response_upgrade_authorized": False,
        "same_segment_retry_authorized": False,
        "result_admission_authorized": False,
    }
    assert value["contract"]["provider_request_id"] is None
    assert value["contract"]["paid_ceiling_usd"] == 0.0
    assert len(value["negative_probes"]) == 14
    assert value["evidence_boundary"] == {
        "credentials_read": False,
        "network_calls_made": 0,
        "scientific_outcomes_read": 0,
        "historical_files_mutated": 0,
    }


def test_candidate_write_and_verify(
    tmp_path: Path,
    frozen_candidate: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(candidate, "build_candidate", lambda: frozen_candidate)
    path = tmp_path / "candidate.json"

    written = candidate.write_candidate(path)
    verified = candidate.verify_candidate(path)

    assert written == verified == frozen_candidate


def test_candidate_rejects_execution_authority(
    frozen_candidate: dict[str, object],
) -> None:
    tampered = copy.deepcopy(frozen_candidate)
    tampered["authorization"]["provider_execution_authorized"] = True

    with pytest.raises(candidate.GeminiLocalPrecommitContractV2CandidateError):
        candidate.validate_candidate(tampered)


def test_candidate_rejects_fabricated_provider_request_id(
    frozen_candidate: dict[str, object],
) -> None:
    tampered = copy.deepcopy(frozen_candidate)
    tampered["contract"]["provider_request_id"] = "invented"

    with pytest.raises(candidate.GeminiLocalPrecommitContractV2CandidateError):
        candidate.validate_candidate(tampered)
