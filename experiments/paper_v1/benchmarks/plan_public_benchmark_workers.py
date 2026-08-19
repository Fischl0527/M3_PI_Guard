"""Build a portable, model-affine worker plan for the frozen public matrix.

This planner never starts a model, changes a cell manifest, retries a case or
admits a result.  It groups whole model families onto workers so a remote GPU
worker can keep one Ollama model resident while executing its AgentDojo and
InjecAgent cells.  All emitted repository paths are relative to the checkout.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CELL_ROOT = (
    ROOT / "outputs" / "paper_upgrade_v1" / "public_benchmark_formal_runs_v2"
)
DEFAULT_OUTPUT_DIR = (
    ROOT
    / "protocols"
    / "paper_upgrade_v1"
    / "execution"
    / "public_benchmark_workers_v1"
)
EXPECTED_CELLS = 84
EXPECTED_CASE_RUNS = 74_760
DRIVE_ABSOLUTE = re.compile(r"(?i)\b[A-Z]:[\\/]")


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def _rows_sha256(rows: Iterable[Mapping[str, Any]]) -> str:
    digest = hashlib.sha256()
    for row in rows:
        digest.update(
            json.dumps(dict(row), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            )
        )
        digest.update(b"\n")
    return digest.hexdigest()


def _load_cells(cell_root: Path) -> list[dict[str, Any]]:
    cells_dir = cell_root.resolve() / "cells"
    rows: list[dict[str, Any]] = []
    for manifest_path in sorted(cells_dir.glob("*/manifest.json")):
        manifest = _read_json(manifest_path)
        cell_id = str(manifest.get("cell_id", ""))
        if not cell_id or manifest_path.parent.name != cell_id:
            raise ValueError(f"cell identity mismatch: {manifest_path}")
        case_runs = int(manifest.get("case_runs", 0) or 0)
        if case_runs <= 0:
            raise ValueError(f"invalid case_runs for {cell_id}")
        rows.append(
            {
                "benchmark": str(manifest.get("benchmark", "")),
                "case_runs": case_runs,
                "cell_id": cell_id,
                "condition_id": str(manifest.get("condition_id", "")),
                "manifest_path": _relative(manifest_path),
                "model": str(manifest.get("model", "")),
                "status": str(manifest.get("status", "")),
                "todo_cases_path": _relative(manifest_path.parent / "todo_cases.jsonl"),
            }
        )
    if len(rows) != EXPECTED_CELLS:
        raise ValueError(f"expected {EXPECTED_CELLS} cells, found {len(rows)}")
    total_case_runs = sum(int(row["case_runs"]) for row in rows)
    if total_case_runs != EXPECTED_CASE_RUNS:
        raise ValueError(
            f"expected {EXPECTED_CASE_RUNS} case-runs, found {total_case_runs}"
        )
    return rows


def _runner_arguments(cell: Mapping[str, Any], *, cell_root: Path) -> list[str]:
    common = [
        "python",
        "-m",
    ]
    result_root = _relative(cell_root)
    cell_id = str(cell["cell_id"])
    if cell["benchmark"] == "agentdojo":
        return [
            *common,
            "experiments.paper_v1.benchmarks.run_agentdojo_formal_cell",
            "--cell-id",
            cell_id,
            "--result-root",
            result_root,
            "--backend",
            "ollama",
            "--temperature",
            "0",
            "--seed",
            "0",
            "--execute",
            "--admit-formal-source",
            "--ingest",
            "--materialize",
        ]
    if cell["benchmark"] == "injecagent":
        return [
            *common,
            "experiments.paper_v1.benchmarks.run_injecagent_formal_cell",
            "--cell-id",
            cell_id,
            "--result-root",
            result_root,
            "--backend",
            "ollama",
            "--temperature",
            "0",
            "--seed",
            "0",
            "--prompt-style",
            "official_react",
            "--execute",
            "--formal-source-admission",
            "--ingest",
            "--materialize",
        ]
    raise ValueError(f"unsupported benchmark: {cell['benchmark']}")


def _display_command(arguments: Iterable[str]) -> str:
    values = list(arguments)
    if any(DRIVE_ABSOLUTE.search(value) for value in values):
        raise ValueError("worker command contains a drive-absolute path")
    return " ".join(values)


def build_worker_plan(*, cell_root: Path, worker_count: int = 7) -> dict[str, Any]:
    if worker_count <= 0:
        raise ValueError("worker_count must be positive")
    cells = _load_cells(cell_root)
    by_model: dict[str, list[dict[str, Any]]] = {}
    for cell in cells:
        by_model.setdefault(str(cell["model"]), []).append(cell)
    if worker_count > len(by_model):
        worker_count = len(by_model)

    model_groups = sorted(
        by_model.items(),
        key=lambda item: (-sum(int(row["case_runs"]) for row in item[1]), item[0]),
    )
    workers: list[dict[str, Any]] = [
        {"worker_id": f"worker_{index + 1:02d}", "models": [], "cells": [], "case_runs": 0}
        for index in range(worker_count)
    ]
    for model, model_cells in model_groups:
        worker = min(workers, key=lambda row: (int(row["case_runs"]), str(row["worker_id"])))
        worker["models"].append(model)
        for cell in sorted(model_cells, key=lambda row: (str(row["benchmark"]), str(row["condition_id"]))):
            arguments = _runner_arguments(cell, cell_root=cell_root)
            worker["cells"].append(
                {
                    **cell,
                    "arguments": arguments,
                    "command": _display_command(arguments),
                }
            )
            worker["case_runs"] = int(worker["case_runs"]) + int(cell["case_runs"])

    assignment_rows = [
        {
            "worker_id": str(worker["worker_id"]),
            "model": str(cell["model"]),
            "cell_id": str(cell["cell_id"]),
            "case_runs": int(cell["case_runs"]),
        }
        for worker in workers
        for cell in worker["cells"]
    ]
    if len({row["cell_id"] for row in assignment_rows}) != EXPECTED_CELLS:
        raise ValueError("worker assignments do not cover 84 unique cells")
    return {
        "schema_version": "paper-public-benchmark-worker-plan-1.0",
        "status": "completed_plan_only",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "cell_root": _relative(cell_root),
        "worker_count": len(workers),
        "model_count": len(by_model),
        "cell_count": len(assignment_rows),
        "case_runs": sum(int(row["case_runs"]) for row in assignment_rows),
        "assignments_sha256": _rows_sha256(assignment_rows),
        "workers": workers,
        "result_eligible_for_formal_tables": False,
        "boundary": (
            "Planning only. This artifact starts no service, executes no case, retries no failure, "
            "changes no frozen cell and admits no paper result. Each worker must use an independently "
            "verified checkout, identical model digests and the frozen cell queues."
        ),
    }


def _markdown(plan: Mapping[str, Any]) -> str:
    lines = [
        "# Public benchmark worker plan v1",
        "",
        f"- Status: `{plan['status']}`",
        f"- Workers: {plan['worker_count']}",
        f"- Models: {plan['model_count']}",
        f"- Cells: {plan['cell_count']}",
        f"- Case-runs: {plan['case_runs']}",
        f"- Assignment SHA-256: `{plan['assignments_sha256']}`",
        "",
        "> This is a plan-only artifact. It is not experimental evidence and does not change Q2 readiness.",
        "",
        "## Worker assignments",
        "",
    ]
    for worker in plan["workers"]:
        lines.extend(
            [
                f"### {worker['worker_id']}",
                "",
                f"- Models: {', '.join(f'`{model}`' for model in worker['models'])}",
                f"- Cells: {len(worker['cells'])}",
                f"- Case-runs: {worker['case_runs']}",
                "",
            ]
        )
        for cell in worker["cells"]:
            lines.append(f"- `{cell['cell_id']}` — `{cell['command']}`")
        lines.append("")
    lines.extend(
        [
            "## Execution boundary",
            "",
            "Run at most one model workload per GPU. Do not add `--retry-failed` automatically. "
            "A worker failure remains explicit until it is diagnosed and a new approved action is recorded.",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cell-root", type=Path, default=DEFAULT_CELL_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--workers", type=int, default=7)
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args(argv)

    plan = build_worker_plan(cell_root=args.cell_root, worker_count=args.workers)
    if not args.no_write:
        output_dir = args.output_dir.resolve()
        _write_json(output_dir / "public_benchmark_worker_plan_v1.json", plan)
        (output_dir / "public_benchmark_worker_plan_v1.md").write_text(
            _markdown(plan), encoding="utf-8"
        )
    print(
        json.dumps(
            {
                key: plan[key]
                for key in (
                    "status",
                    "worker_count",
                    "model_count",
                    "cell_count",
                    "case_runs",
                    "assignments_sha256",
                )
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
