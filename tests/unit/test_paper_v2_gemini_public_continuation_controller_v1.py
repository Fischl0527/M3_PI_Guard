from __future__ import annotations

import copy
from pathlib import Path

import pytest

from experiments.paper_v2 import gemini_public_continuation_controller_v1 as controller


def _offline_dependencies(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    source_file = tmp_path / "source.json"
    source_file.write_text("{}\n", encoding="utf-8")
    gate = {
        "manifest_sha256": "a" * 64,
        "matrix_continuation_eligible": True,
    }
    schedule = [
        {
            "quota_segment_index": 0,
            "logical_shard_index": 0,
            "record_count": 1,
            "work_keys": ["work-1"],
            "work_key_sequence_sha256": controller.sha256_canonical_json(
                ["work-1"]
            ),
            "maximum_provider_requests": 8,
            "segment_sha256": "b" * 64,
        }
    ]
    monkeypatch.setattr(controller, "_schedule_rows", lambda: copy.deepcopy(schedule))
    monkeypatch.setattr(
        controller,
        "_source_rows_by_key",
        lambda: {
            "work-1": {
                "work_key": "work-1",
                "execution_identity": "old",
                "max_provider_calls": 8,
            }
        },
    )
    monkeypatch.setattr(controller, "_prior_review", lambda index: copy.deepcopy(gate))
    monkeypatch.setattr(controller.daily_quota, "current_quota_day", lambda: "2026-08-02")
    monkeypatch.setattr(controller, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(controller, "OUTPUT_BASE", tmp_path / "out")
    monkeypatch.setattr(controller, "CANDIDATE_ROOT", tmp_path / "candidate")
    monkeypatch.setattr(controller, "ADMISSION_ROOT", tmp_path / "admission")
    monkeypatch.setattr(controller, "_lock", lambda path: {
        "path": source_file.name,
        "bytes": source_file.stat().st_size,
        "sha256": controller._sha256_file(source_file),
    })


def test_daily_candidate_is_free_tier_and_fresh_identity(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _offline_dependencies(monkeypatch, tmp_path)

    value = controller.build_segment_candidate(
        0,
        quota_day="2026-08-02",
        generated_at="2026-08-02T10:30:00+08:00",
    )

    scope = value["scope"]
    assert scope["maximum_provider_requests"] == 8
    assert scope["paid_ceiling_usd"] == 0.0
    assert scope["automatic_retries"] == 0
    assert scope["work_items"][0]["execution_identity"] == scope["execution_identity"]
    assert value["authorization"]["segment_execution_authorized"] is False


def test_daily_candidate_rejects_wrong_quota_day(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _offline_dependencies(monkeypatch, tmp_path)

    with pytest.raises(
        controller.GeminiPublicContinuationControllerV1Error,
        match="current provider quota day",
    ):
        controller.build_segment_candidate(
            0,
            quota_day="2026-08-01",
            generated_at="2026-08-02T10:30:00+08:00",
        )


def test_candidate_tampering_fails_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _offline_dependencies(monkeypatch, tmp_path)
    value = controller.build_segment_candidate(
        0,
        quota_day="2026-08-02",
        generated_at="2026-08-02T10:30:00+08:00",
    )
    value["scope"]["paid_ceiling_usd"] = 1.0

    with pytest.raises(
        controller.GeminiPublicContinuationControllerV1Error,
        match="candidate drift",
    ):
        controller.validate_segment_candidate(value)
