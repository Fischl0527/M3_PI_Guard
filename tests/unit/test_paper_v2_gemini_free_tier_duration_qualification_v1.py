from __future__ import annotations

import copy

import pytest

import experiments.paper_v2.gemini_free_tier_duration_qualification_v1 as duration
from experiments.paper_v2.contracts import sha256_canonical_json


def test_free_tier_duration_bounds_are_reconstructed_from_frozen_plans() -> None:
    value = duration.build_qualification()
    workloads = value["workloads"]
    bounds = value["duration_bounds_quota_days"]

    assert workloads["canary"]["records"] == 12
    assert workloads["canary"]["safe_quota_days"] == 8
    assert workloads["public_matrix"]["records"] == 1_791
    assert workloads["public_matrix"]["canary_prefix_records"] == 12
    assert workloads["public_matrix"]["pending_only_records"] == 1_779
    assert workloads["public_matrix"]["maximum_provider_calls"] == 19_104
    assert (
        workloads["public_matrix"]["pending_only_maximum_provider_calls"]
        == 18_976
    )
    assert workloads["public_matrix"]["pending_only_safe_quota_days"] == 1_186
    assert workloads["adaptive"]["maximum_queries"] == 4_000
    assert workloads["adaptive"]["safe_quota_days"] == 2_000
    assert bounds["theoretical_one_call_per_item"]["total"] == 323
    assert bounds["prospective_minimum_with_locked_canary"]["total"] == 330
    assert bounds["precommitted_worst_case_safe_packing"]["total"] == 3_194


def test_duration_qualification_rejects_a_twenty_one_day_claim() -> None:
    value = duration.build_qualification()
    tampered = copy.deepcopy(value)
    tampered["conclusion"][
        "twenty_one_day_completion_possible_under_current_free_tier"
    ] = True
    core = {
        key: child for key, child in tampered.items() if key != "manifest_sha256"
    }
    tampered["manifest_sha256"] = sha256_canonical_json(core)

    with pytest.raises(duration.GeminiFreeTierDurationQualificationV1Error):
        duration.validate_qualification(tampered)
