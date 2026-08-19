from __future__ import annotations

import json
from pathlib import Path

from experiments.paper_v1.benchmarks.analyze_taskshield_v15_expanded_qualification import (
    analyze,
)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_v15_analysis_rejects_failed_qualification_and_keeps_effect_denominators(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    _write_json(
        run_dir / "run_manifest.json",
        {
            "qualification_protocol": {
                "exact_frozen_selection": True,
                "passed_operational_gate": False,
            }
        },
    )
    rows = []
    for index in range(6):
        rows.append(
            {
                "benchmark_case_id": f"utility-{index}",
                "case_kind": "utility",
                "status": "failed" if index == 5 else "completed",
                "utility_success": index == 0,
                "security_success": None,
                "attack_success": False,
                "error_type": "APITimeoutError" if index == 5 else "",
                "error": "Request timed out." if index == 5 else "",
                "result_eligible_for_formal_tables": False,
            }
        )
    for index in range(6):
        rows.append(
            {
                "benchmark_case_id": f"security-{index}",
                "case_kind": "security",
                "status": "completed",
                "utility_success": False,
                "security_success": False,
                "attack_success": True,
                "result_eligible_for_formal_tables": False,
                "taskshield_trace": {"model_requests": [], "content_checks": []},
            }
        )
    (run_dir / "outcomes.jsonl").write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )
    progress = []
    for index, row in enumerate(rows):
        progress.extend(
            [
                {
                    "benchmark_case_id": row["benchmark_case_id"],
                    "status": "running",
                    "created_at": f"2026-01-01T00:{index:02d}:00+00:00",
                },
                {
                    "benchmark_case_id": row["benchmark_case_id"],
                    "status": row["status"],
                    "created_at": f"2026-01-01T00:{index:02d}:30+00:00",
                },
            ]
        )
    (run_dir / "progress.jsonl").write_text(
        "\n".join(json.dumps(row) for row in progress) + "\n",
        encoding="utf-8",
    )

    result = analyze(run_dir=run_dir, output_dir=tmp_path / "analysis")

    assert result["operational_result"]["qualification_passed"] is False
    assert result["operational_result"]["completed_cases"] == 11
    assert result["operational_result"]["failed_cases"] == 1
    assert result["diagnostic_effect_results"]["utility_success_rate_percent"] == 16.666667
    assert result["diagnostic_effect_results"]["attack_success_rate_percent"] == 100.0
    assert result["contract_and_trace_audit"]["failed_case_trace_retained"] is False
    assert result["result_eligible_for_formal_tables"] is False
    assert (tmp_path / "analysis" / "qualification_analysis.json").is_file()
    assert (tmp_path / "analysis" / "case_summary.csv").is_file()
