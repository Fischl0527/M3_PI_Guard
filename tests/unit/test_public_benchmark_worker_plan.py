from __future__ import annotations

import re
from pathlib import Path

from experiments.paper_v1.benchmarks.plan_public_benchmark_workers import (
    build_worker_plan,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
CELL_ROOT = REPO_ROOT / "outputs" / "paper_upgrade_v1" / "public_benchmark_formal_runs_v2"
DRIVE_ABSOLUTE = re.compile(r"(?i)\b[A-Z]:[\\/]")


def test_seven_worker_plan_is_complete_model_affine_and_portable() -> None:
    plan = build_worker_plan(cell_root=CELL_ROOT, worker_count=7)
    assert plan["status"] == "completed_plan_only"
    assert plan["worker_count"] == 7
    assert plan["model_count"] == 7
    assert plan["cell_count"] == 84
    assert plan["case_runs"] == 74_760

    cells = [cell for worker in plan["workers"] for cell in worker["cells"]]
    assert len({cell["cell_id"] for cell in cells}) == 84
    model_workers: dict[str, set[str]] = {}
    for worker in plan["workers"]:
        assert len(worker["models"]) == 1
        assert len(worker["cells"]) == 12
        assert worker["case_runs"] == 10_680
        for cell in worker["cells"]:
            model_workers.setdefault(cell["model"], set()).add(worker["worker_id"])
            assert DRIVE_ABSOLUTE.search(cell["command"]) is None
            assert all(DRIVE_ABSOLUTE.search(value) is None for value in cell["arguments"])
    assert all(len(workers) == 1 for workers in model_workers.values())


def test_four_worker_plan_keeps_model_groups_intact_without_duplicate_cells() -> None:
    first = build_worker_plan(cell_root=CELL_ROOT, worker_count=4)
    second = build_worker_plan(cell_root=CELL_ROOT, worker_count=4)
    assert first["assignments_sha256"] == second["assignments_sha256"]
    assert first["cell_count"] == 84
    assert first["case_runs"] == 74_760
    cells = [cell for worker in first["workers"] for cell in worker["cells"]]
    assert len(cells) == len({cell["cell_id"] for cell in cells}) == 84


def test_worker_plan_commands_use_formal_source_admission_flags() -> None:
    plan = build_worker_plan(cell_root=CELL_ROOT, worker_count=7)
    for worker in plan["workers"]:
        for cell in worker["cells"]:
            arguments = cell["arguments"]
            assert "--execute" in arguments
            assert "--ingest" in arguments
            assert "--materialize" in arguments
            if cell["benchmark"] == "agentdojo":
                assert "--admit-formal-source" in arguments
            else:
                assert "--formal-source-admission" in arguments
                assert arguments[arguments.index("--prompt-style") + 1] == "official_react"
