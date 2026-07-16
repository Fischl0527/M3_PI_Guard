from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_harness_engineering_is_separate_from_project_source() -> None:
    harness_paths = (
        "harness/README.md",
        "harness/config/permissions.yaml",
        "harness/config/policies.md",
        "harness/config/workflow.md",
        "harness/state/current-task.md",
        "harness/state/progress.md",
        "harness/state/session-handoff.md",
        "harness/specs/product-spec.md",
        "harness/features/feature_list.json",
        "harness/tasks/task.md",
        "harness/scripts/verify.ps1",
        "harness/scripts/test.ps1",
        "harness/workspaces/runpro/10_analysis/approval-gate.md",
    )
    assert all((REPO_ROOT / relative).is_file() for relative in harness_paths)

    project_directories = (
        "m3_core",
        "m3_guard",
        "m3_eval",
        "m3_attacks",
        "experiments",
        "protocols",
        "schemas",
        "fixtures",
        "tests",
        "scripts",
    )
    assert all((REPO_ROOT / relative).is_dir() for relative in project_directories)

    legacy_harness_paths = (
        "README_AGENT.md",
        ".agent",
        "features",
        "specs",
        "tasks",
        "runpro_workspace",
        "agent/current-task.md",
        "agent/failure-log.md",
        "agent/memory.md",
        "agent/progress.md",
        "agent/session-handoff.md",
        "agent/task-history.md",
    )
    assert all(not (REPO_ROOT / relative).exists() for relative in legacy_harness_paths)

    feature_list = json.loads(
        (REPO_ROOT / "harness/features/feature_list.json").read_text(encoding="utf-8")
    )
    assert feature_list["schemaVersion"] == "1.0"
    assert (REPO_ROOT / "AGENTS.md").is_file()
    assert (REPO_ROOT / "agent/README.md").is_file()
