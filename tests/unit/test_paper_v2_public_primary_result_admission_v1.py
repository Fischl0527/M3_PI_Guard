from __future__ import annotations

import copy

import pytest

import experiments.paper_v2.public_primary_result_admission_v1 as admission
from experiments.paper_v2.contracts import sha256_canonical_json


def _candidate() -> dict:
    scope = {
        "claim_boundary": {
            "primary_model_only": True,
            "cross_model_claim_authorized": False,
            "cross_provider_claim_authorized": False,
            "clean_mechanism_quality_claim_authorized": False,
            "empirical_security_utility_fallback_only": True,
            "sota_claim_authorized": False,
        }
    }
    core = {
        "schema_version": admission.SCHEMA_VERSION,
        "artifact_role": (
            "public_primary_scientific_result_access_candidate"
        ),
        "generated_at": admission.GENERATED_AT,
        "status": "primary_integrity_passed_result_access_not_authorized",
        "scope": scope,
        "scope_sha256": sha256_canonical_json(scope),
        "artifact_locks": [
            {"path": "example", "bytes": 1, "sha256": "a" * 64}
        ],
        "authorization": {
            "candidate_only": True,
            "scientific_outcome_access_authorized": False,
            "new_provider_execution_authorized": False,
            "second_model_execution_authorized": False,
        },
    }
    return {
        **core,
        "manifest_sha256": sha256_canonical_json(core),
    }


def test_candidate_requires_sealed_outcome_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(admission, "_verify_lock", lambda lock: None)
    candidate = _candidate()

    assert admission.validate_candidate(candidate) == candidate

    drifted = copy.deepcopy(candidate)
    drifted["authorization"][
        "scientific_outcome_access_authorized"
    ] = True
    drifted["manifest_sha256"] = admission._manifest_sha(drifted)
    with pytest.raises(
        admission.PublicPrimaryResultAdmissionError,
        match="candidate drift",
    ):
        admission.validate_candidate(drifted)


def test_result_admission_authorizes_analysis_not_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = _candidate()
    monkeypatch.setattr(admission, "verify_candidate", lambda: candidate)

    value = admission.build_admission(
        owner_statement_sha256="b" * 64,
        approved_at="2026-07-30T06:30:00+08:00",
    )

    authorization = value["authorization"]
    assert authorization["scientific_outcome_access_authorized"] is True
    assert authorization["new_provider_execution_authorized"] is False
    assert authorization["second_model_execution_authorized"] is False
    assert authorization["automatic_retries"] == 0
