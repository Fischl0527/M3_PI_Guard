from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from experiments.paper_v1.benchmarks.analyze_taskshield_v16_qualification import analyze
from experiments.paper_v1.benchmarks.build_taskshield_paper_formal_freeze_v16 import (
    build_freeze,
)
from experiments.paper_v1.benchmarks.common import rows_sha256, sha256_file
from experiments.paper_v1.benchmarks.run_taskshield_paper_formal_v16 import (
    _corrected_metric_fields,
    _selection,
    _terminal_row,
    parse_args,
    validate_fresh_output_root,
)


ROOT = Path(__file__).resolve().parents[2]


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_v16_fresh_output_root_rejects_any_existing_artifact(tmp_path: Path) -> None:
    root = tmp_path / "run"
    root.mkdir()
    (root / "stderr.log").write_text("old", encoding="utf-8")
    with pytest.raises(ValueError, match="fresh empty"):
        validate_fresh_output_root(root)


def test_v16_fresh_output_root_allows_missing_or_empty(tmp_path: Path) -> None:
    validate_fresh_output_root(tmp_path / "missing")
    empty = tmp_path / "empty"
    empty.mkdir()
    validate_fresh_output_root(empty)


def test_v16_selection_preserves_frozen_order_and_rejects_duplicates() -> None:
    freeze = {
        "preflight_case_ids": ["b", "a"],
        "case_rows": [
            {"benchmark_case_id": "a"},
            {"benchmark_case_id": "b"},
        ],
    }
    assert [row["benchmark_case_id"] for row in _selection(freeze, "preflight")] == ["b", "a"]
    freeze["preflight_case_ids"] = ["a", "a"]
    with pytest.raises(ValueError, match="duplicated"):
        _selection(freeze, "preflight")


def test_v16_corrected_metric_mapping_uses_raw_official_security() -> None:
    parsed = {"case_kind": "security"}
    fields = _corrected_metric_fields(parsed=parsed, outcome={"security_success": True})
    assert fields["official_injection_success"] is True
    assert fields["attack_success"] is True
    assert fields["security_preserved"] is False
    assert fields["legacy_attack_success"] is False


def test_v16_failure_terminal_row_retains_trace_and_independent_timestamps() -> None:
    parsed = {
        "case_kind": "security",
        "suite": "banking",
        "user_task_id": "user_task_0",
        "injection_task_id": "injection_task_0",
    }
    row = _terminal_row(
        parsed=parsed,
        case_id="case",
        index=1,
        started_at="2026-01-01T00:00:00+00:00",
        finished_at="2026-01-01T00:00:02+00:00",
        duration_ms=2000.0,
        trace={"model_requests": [{"request_attempt": 1}]},
        trace_path="trace.json",
        trace_sha256="a" * 64,
        exc=RuntimeError("boom"),
    )
    assert row["status"] == "failed"
    assert row["taskshield_trace"]["model_requests"]
    assert row["started_at"] != row["finished_at"]
    assert row["case_retry_count"] == 0


def _synthetic_run(
    tmp_path: Path,
    *,
    count: int,
    utility_successes: int,
    attack_utility_successes: int,
    metric_mismatch: bool = False,
) -> tuple[Path, Path]:
    run_dir = tmp_path / "run"
    rows: list[dict] = []
    progress: list[dict] = []
    comparator: list[dict] = []
    utility_count = count // 2
    for index in range(count):
        is_attack = index % 2 == 1
        case_id = f"case-{index}"
        verifier_trace = {
            "model_requests": [{"request_attempt": 1, "contract_valid": True}],
            "tool_calls": [{"decision": "allow"}],
            "denied_tool_calls": 0,
        }
        verifier_path = tmp_path / "traces" / f"verifier-{index}.json"
        _write_json(verifier_path, verifier_trace)
        row = {
            "benchmark_case_id": case_id,
            "case_kind": "security" if is_attack else "utility",
            "status": "completed",
            "utility_success": (
                index // 2 < attack_utility_successes
                if is_attack
                else index // 2 < utility_successes
            ),
            "official_injection_success": None,
            "attack_success": None,
            "security_preserved": None,
            "duration_ms": 1000.0 + index,
            "taskshield_trace": verifier_trace,
            "taskshield_trace_path": str(verifier_path),
            "taskshield_trace_sha256": sha256_file(verifier_path),
            "case_retry_count": 0,
            "result_eligible_for_formal_tables": False,
        }
        if is_attack:
            official = index % 4 == 1
            official_path = tmp_path / "traces" / f"official-{index}.json"
            _write_json(official_path, {"security": official, "utility": row["utility_success"]})
            row.update(
                {
                    "official_trace_path": str(official_path),
                    "official_trace_sha256": sha256_file(official_path),
                    "official_injection_success": not official if metric_mismatch else official,
                    "attack_success": official,
                    "security_preserved": not official,
                }
            )
        rows.append(row)
        progress.extend(
            [
                {
                    "benchmark_case_id": case_id,
                    "status": "running",
                    "started_at": "2026-01-01T00:00:00+00:00",
                },
                {
                    "benchmark_case_id": case_id,
                    "status": "completed",
                    "started_at": "2026-01-01T00:00:00+00:00",
                    "finished_at": "2026-01-01T00:00:01+00:00",
                    "duration_ms": row["duration_ms"],
                },
            ]
        )
        comparator.append({"benchmark_case_id": case_id, "elapsed_ms": 500.0})
    _write_json(
        run_dir / "run_manifest.json",
        {
            "selection_name": "preflight" if count == 4 else "expanded",
            "resume": False,
            "retry_failed": False,
            "result_eligible_for_formal_tables": False,
        },
    )
    _write_jsonl(run_dir / "outcomes.jsonl", rows)
    _write_jsonl(run_dir / "progress.jsonl", progress)
    comparator_path = tmp_path / "comparator.jsonl"
    _write_jsonl(comparator_path, comparator)
    assert utility_count in {2, 6}
    return run_dir, comparator_path


def test_v16_g2_passes_complete_traceable_four_case_fixture(tmp_path: Path) -> None:
    run_dir, comparator = _synthetic_run(
        tmp_path,
        count=4,
        utility_successes=2,
        attack_utility_successes=1,
    )
    result = analyze(
        run_dir=run_dir,
        output_dir=tmp_path / "analysis",
        selection_name="preflight",
        comparator_path=comparator,
    )
    assert result["gate"]["status"] == "passed"
    assert result["gate"]["name"] == "G2_v16_preflight"


def test_v16_g2_fails_raw_metric_mismatch(tmp_path: Path) -> None:
    run_dir, comparator = _synthetic_run(
        tmp_path,
        count=4,
        utility_successes=2,
        attack_utility_successes=1,
        metric_mismatch=True,
    )
    result = analyze(
        run_dir=run_dir,
        output_dir=tmp_path / "analysis",
        selection_name="preflight",
        comparator_path=comparator,
    )
    assert result["gate"]["checks"]["official_metrics_match_raw_trace"] is False
    assert result["gate"]["status"] == "failed"


def test_v16_g3_rejects_utility_below_two_of_six(tmp_path: Path) -> None:
    run_dir, comparator = _synthetic_run(
        tmp_path,
        count=12,
        utility_successes=1,
        attack_utility_successes=2,
    )
    result = analyze(
        run_dir=run_dir,
        output_dir=tmp_path / "analysis",
        selection_name="expanded",
        comparator_path=comparator,
    )
    assert result["gate"]["checks"]["standalone_utility_at_least_2_of_6"] is False
    assert result["gate"]["status"] == "failed"


def test_v16_cli_has_no_resume_or_retry_failed_switch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "argv", ["runner", "--selection", "preflight"])
    args = parse_args()
    assert not hasattr(args, "resume")
    assert not hasattr(args, "retry_failed")


def test_v16_freeze_hash_binds_g0_runtime_runner_and_selections() -> None:
    manifest = build_freeze(
        public_freeze_path=(
            ROOT / "protocols" / "paper_upgrade_v1" / "public_benchmark_formal_freeze_v2.json"
        ),
        model_registry_path=(
            ROOT / "protocols" / "paper_upgrade_v1" / "model_registry_v2.json"
        ),
        agentdojo_checkout=ROOT / "external" / "benchmarks" / "agentdojo",
        paper_path=(
            ROOT / "external" / "baselines" / "task-shield-paper" / "2025.acl-long.1435.pdf"
        ),
        model_id="m3-paper-qwen3-8b-v1:latest",
    )
    assert manifest["status"] == "completed_frozen_formal_protocol"
    assert len(manifest["preflight_case_rows"]) == 4
    assert len(manifest["qualification_case_rows"]) == 12
    assert manifest["preflight_case_rows_sha256"] == rows_sha256(manifest["preflight_case_rows"])
    assert manifest["expanded_case_rows_sha256"] == rows_sha256(manifest["qualification_case_rows"])
    assert manifest["v16_change_contract"]["full_726_case_run_authorized"] is False
    assert str(ROOT) not in json.dumps(manifest, ensure_ascii=False)

