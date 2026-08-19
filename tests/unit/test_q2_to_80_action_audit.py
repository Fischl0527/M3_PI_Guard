from __future__ import annotations

import json
from pathlib import Path

from experiments.paper_v1.benchmarks.plan_q2_to_80_actions import (
    build_q2_to_80_action_audit,
)


def _write(path: Path, value: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_q2_to_80_audit_requires_all_caps_below_80(tmp_path: Path) -> None:
    q2 = _write(
        tmp_path / "q2.json",
        {
            "raw_score": 66.0,
            "capped_score": 60.0,
            "goal_80_met": False,
            "goal_90_met": False,
            "readiness_band": "paper_upgrade_in_progress",
            "caps": [
                {"name": "frontier_api_model_gate", "cap": 60.0, "gate_missing": True},
                {"name": "adaptive_budget_gate", "cap": 60.0, "gate_missing": True},
                {"name": "independent_blind_gate", "cap": 65.0, "gate_missing": True},
                {"name": "strong_baseline_gate", "cap": 70.0, "gate_missing": True},
                {"name": "public_benchmark_gate", "cap": 75.0, "gate_missing": True},
            ],
            "criteria": [
                {"id": "independent_blind_evidence", "status": "blocked"},
                {"id": "source_backed_strong_baselines", "status": "blocked"},
                {"id": "public_benchmark_results", "status": "blocked"},
                {"id": "model_coverage", "status": "partial"},
                {"id": "adaptive_budget_attacks", "status": "blocked"},
            ],
        },
    )
    plan = _write(
        tmp_path / "plan.json",
        {
            "resource_gate": "busy",
            "next_safe_action": {
                "action_id": "monitor_active_formal_workload",
                "command": "python monitor.py",
                "reason": "live formal workload",
            },
            "active_workloads": [{"workload": "task_shield_formal"}],
            "public_matrix": {"status_counts": {"pending": 84}},
        },
    )
    strong = _write(
        tmp_path / "strong.json",
        {"formal_ready_strong_baselines": ["agentdojo_tool_filter", "promptguard"]},
    )
    frontier = _write(
        tmp_path / "frontier.json",
        {
            "status": "blocked_missing_or_unsafe_local_config",
            "configured_vendor_count": 0,
            "registered_vendor_count": 0,
            "network_calls_performed": False,
        },
    )
    blind = _write(
        tmp_path / "blind.json",
        {
            "status": "blocked_missing_candidate",
            "candidate_exists": False,
            "result_eligible_for_confirmatory_q2_tables": False,
        },
    )
    adaptive = _write(
        tmp_path / "adaptive.json",
        {"health_status": "missing_manifest", "manifest_status": ""},
    )

    audit = build_q2_to_80_action_audit(
        q2_audit_path=q2,
        execution_plan_path=plan,
        strong_baseline_audit_path=strong,
        frontier_audit_path=frontier,
        blind_audit_path=blind,
        adaptive_monitor_path=adaptive,
        output_dir=tmp_path / "out",
    )

    assert audit["status"] == "blocked_by_active_hard_caps"
    assert audit["q2_readiness"]["capped_score"] == 60.0
    gates = {row["gate"]: row for row in audit["actions_required_before_80"]}
    assert set(gates) == {
        "frontier_api_model_gate",
        "adaptive_budget_gate",
        "independent_blind_gate",
        "strong_baseline_gate",
        "public_benchmark_gate",
    }
    assert gates["strong_baseline_gate"]["current_state"]["formal_ready_count"] == 2
    assert gates["adaptive_budget_gate"]["can_execute_now"] is False
    assert gates["frontier_api_model_gate"]["blocking_kind"] == "user_local_config_and_external_api"
    assert (tmp_path / "out" / "q2_to_80_action_audit_v1.json").is_file()
    assert (tmp_path / "out" / "q2_to_80_action_audit_v1.md").is_file()
