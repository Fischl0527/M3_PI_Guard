from __future__ import annotations

import copy

import pytest

import experiments.paper_v2.gemini_public_segment_abort_review_v1 as review


@pytest.fixture(scope="module")
def frozen_review() -> dict[str, object]:
    return review.build_review()


def test_request_chain_classifies_the_exact_missing_provider_id_case() -> None:
    assert (
        review.classify_request_chain(
            provider_request_id=None,
            provider_response_id="response-1",
            trace_mode="precommitted_local_plus_provider_response",
            request_trace_complete=False,
            identity_verified=True,
        )
        == "local_precommit_complete_provider_request_id_unavailable"
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("provider_response_id", None),
        ("trace_mode", "provider_dual_id_plus_precommitted_local"),
        ("request_trace_complete", True),
        ("identity_verified", False),
    ],
)
def test_request_chain_rejects_nearby_incomplete_cases(
    field: str, value: object
) -> None:
    arguments = {
        "provider_request_id": None,
        "provider_response_id": "response-1",
        "trace_mode": "precommitted_local_plus_provider_response",
        "request_trace_complete": False,
        "identity_verified": True,
    }
    arguments[field] = value

    assert review.classify_request_chain(**arguments) == (
        "unclassified_request_chain"
    )


def test_frozen_segment_builds_a_result_ineligible_review(
    frozen_review: dict[str, object],
) -> None:
    value = frozen_review

    assert value["status"] == (
        "aborted_result_ineligible_contract_revision_required"
    )
    assert value["disposition"]["result_eligible"] is False
    assert value["disposition"]["same_work_item_retry_allowed"] is False
    assert value["technical_checks"]
    assert all(value["technical_checks"].values())


def test_manifest_tamper_is_detectable(
    frozen_review: dict[str, object],
) -> None:
    value = frozen_review
    tampered = copy.deepcopy(value)
    tampered["disposition"]["result_eligible"] = True

    assert tampered["manifest_sha256"] != review.sha256_canonical_json(
        review._without_manifest(tampered)
    )
