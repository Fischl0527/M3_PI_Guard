from __future__ import annotations

import pytest

import experiments.paper_v2.public_second_evidence_merge_v1 as merge


def test_global_fraction_never_waives_a_failed_shard_gate() -> None:
    value = merge._claim_quality(
        shard_quality=[False, True],
        diagnostic_records=16,
        total_records=1791,
    )

    assert value["global_fraction_below_one_percent"] is True
    assert value["global_fraction_used_to_waive_shard_failure"] is False
    assert value["frozen_one_percent_gate_waived"] is False
    assert value["clean_mechanism_quality_claim_eligible"] is False
    assert value["empirical_security_utility_fallback_only"] is True


def test_exact_prefix_suffix_partition_is_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(merge, "EXPECTED_ROLE_RECORDS", 6)

    merge._validate_partition_sequences(
        expected_canary=["c0", "c1"],
        observed_canary=["c0", "c1"],
        expected_partitions=[["a", "b"], ["x", "y"]],
        observed_prefixes=[["a"], ["x"]],
        observed_recoveries=[["b"], ["y"]],
    )


def test_partition_reordering_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(merge, "EXPECTED_ROLE_RECORDS", 6)

    with pytest.raises(
        merge.PublicSecondEvidenceMergeV1Error,
        match="partition drift",
    ):
        merge._validate_partition_sequences(
            expected_canary=["c0", "c1"],
            observed_canary=["c0", "c1"],
            expected_partitions=[["a", "b"], ["x", "y"]],
            observed_prefixes=[["a"], ["x"]],
            observed_recoveries=[["b"], ["z"]],
        )


def test_duplicate_role_work_key_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(merge, "EXPECTED_ROLE_RECORDS", 6)

    with pytest.raises(
        merge.PublicSecondEvidenceMergeV1Error,
        match="unique work keys",
    ):
        merge._validate_partition_sequences(
            expected_canary=["a", "c1"],
            observed_canary=["a", "c1"],
            expected_partitions=[["a", "b"], ["x", "y"]],
            observed_prefixes=[["a"], ["x"]],
            observed_recoveries=[["b"], ["y"]],
        )
