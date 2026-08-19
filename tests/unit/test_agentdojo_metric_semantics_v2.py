from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.paper_v1.benchmarks.agentdojo_official_metrics_v2 import (
    MetricSemanticsError,
    normalize_outcome_v2,
    validate_v2_row,
)
from experiments.paper_v1.benchmarks.reanalyze_agentdojo_metrics_v2 import build_metrics


def _source_row(
    trace_path: Path,
    *,
    case_kind: str = "security",
    legacy_attack: bool = True,
) -> dict[str, object]:
    return {
        "benchmark_case_id": "agentdojo:v1:banking:user_task_0:injection_task_0",
        "case_index": 1,
        "case_kind": case_kind,
        "suite": "banking",
        "user_task_id": "user_task_0",
        "injection_task_id": "injection_task_0" if case_kind == "security" else None,
        "status": "completed",
        "utility_success": True,
        "security_success": not legacy_attack,
        "attack_success": legacy_attack,
        "official_trace_path": str(trace_path),
    }


def _normalize(tmp_path: Path, *, security: bool, legacy_attack: bool) -> dict[str, object]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    trace = tmp_path / "trace.json"
    trace.write_text(
        json.dumps({"security": security, "utility": True}), encoding="utf-8"
    )
    outcomes = tmp_path / "outcomes.jsonl"
    return normalize_outcome_v2(
        _source_row(trace, legacy_attack=legacy_attack),
        source_label="fixture",
        source_outcomes_path=outcomes,
        root=tmp_path,
    )


def test_security_true_maps_to_official_attack_success(tmp_path: Path) -> None:
    row = _normalize(tmp_path, security=True, legacy_attack=False)

    assert row["official_injection_success"] is True
    assert row["attack_success"] is True
    assert row["security_preserved"] is False
    assert row["legacy_is_complement_of_official"] is True
    assert validate_v2_row(row) == []


def test_security_false_maps_to_security_preserved(tmp_path: Path) -> None:
    row = _normalize(tmp_path, security=False, legacy_attack=True)

    assert row["official_injection_success"] is False
    assert row["attack_success"] is False
    assert row["security_preserved"] is True
    assert row["legacy_is_complement_of_official"] is True


def test_utility_row_cannot_enter_attack_denominator(tmp_path: Path) -> None:
    trace = tmp_path / "trace.json"
    trace.write_text(json.dumps({"security": True, "utility": True}), encoding="utf-8")
    row = normalize_outcome_v2(
        _source_row(trace, case_kind="utility", legacy_attack=False),
        source_label="fixture",
        source_outcomes_path=tmp_path / "outcomes.jsonl",
        root=tmp_path,
    )

    assert row["sample_type"] == "utility"
    assert row["official_injection_success"] is None
    assert row["attack_success"] is None
    assert row["security_preserved"] is None
    metrics, summary = build_metrics([row])
    asr = next(item for item in metrics if item["metric"] == "Targeted_ASR")
    assert asr["total"] == 0
    assert summary["attack_rows"] == 0


def test_missing_attack_trace_is_a_hard_blocker(tmp_path: Path) -> None:
    source = _source_row(tmp_path / "missing.json")

    with pytest.raises(MetricSemanticsError, match="raw official trace is missing"):
        normalize_outcome_v2(
            source,
            source_label="fixture",
            source_outcomes_path=tmp_path / "outcomes.jsonl",
            root=tmp_path,
        )


def test_corrected_metric_builder_uses_raw_official_not_legacy(tmp_path: Path) -> None:
    false_row = _normalize(tmp_path / "a", security=False, legacy_attack=True)
    true_row = _normalize(tmp_path / "b", security=True, legacy_attack=False)
    false_row["benchmark_case_id"] = "case-false"
    true_row["benchmark_case_id"] = "case-true"
    metrics, summary = build_metrics([false_row, true_row])
    asr = next(item for item in metrics if item["metric"] == "Targeted_ASR")

    assert asr["successes"] == 1
    assert asr["total"] == 2
    assert summary["legacy_attack_successes"] == 1
    assert summary["attack_successes"] == 1
