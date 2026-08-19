from __future__ import annotations

import json
from pathlib import Path

from experiments.paper_v1.benchmarks.audit_q2_readiness import _reproducibility
from experiments.paper_v1.benchmarks.build_paper_v1_preregistration_freeze import (
    DEFAULT_REFERENCES,
    build_preregistration_freeze,
)


def test_preregistration_freezes_hypotheses_statistics_and_figures(tmp_path: Path) -> None:
    result = build_preregistration_freeze(
        output_dir=tmp_path,
        references=DEFAULT_REFERENCES,
        created_at="2026-07-21T00:00:00+00:00",
    )

    assert result["status"] == "completed_frozen_preregistration"
    assert result["passed_checks"] == result["total_checks"] == 9
    assert len(result["hypotheses"]) == 5
    assert len(result["figure_plan"]) == 10
    assert result["analysis_contract"]["bootstrap_iterations"] == 10_000
    assert result["failure_and_exclusion_policy"]["case_exclusions_after_freeze"] == "forbidden"
    assert len(result["preregistration_sha256"]) == 64
    persisted = json.loads(
        (tmp_path / "paper_v1_confirmatory_preregistration_freeze_v1.json").read_text(
            encoding="utf-8"
        )
    )
    assert persisted["preregistration_sha256"] == result["preregistration_sha256"]


def test_preregistration_hash_is_independent_of_creation_timestamp(tmp_path: Path) -> None:
    first = build_preregistration_freeze(
        output_dir=tmp_path / "one",
        references=DEFAULT_REFERENCES,
        created_at="2026-07-21T00:00:00+00:00",
    )
    second = build_preregistration_freeze(
        output_dir=tmp_path / "two",
        references=DEFAULT_REFERENCES,
        created_at="2026-07-22T00:00:00+00:00",
    )

    assert first["preregistration_sha256"] == second["preregistration_sha256"]


def test_q2_reproducibility_requires_completed_preregistration() -> None:
    complete = _reproducibility(
        {"status": "completed"},
        {"status": "completed"},
        {"status": "completed"},
        {"status": "completed_frozen_formal_protocol"},
        {
            "status": "completed_frozen_preregistration",
            "preregistration_sha256": "a" * 64,
            "passed_checks": 9,
            "total_checks": 9,
        },
    )
    missing = _reproducibility(
        {"status": "completed"},
        {"status": "completed"},
        {"status": "completed"},
        {"status": "completed_frozen_formal_protocol"},
        {},
    )

    assert complete["earned"] == 8.0
    assert complete["status"] == "complete"
    assert missing["earned"] < 8.0
    assert "confirmatory_preregistration_frozen" in missing["blockers"]
