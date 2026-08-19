"""Create a read-only health snapshot for the adaptive MCTS formal run."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .common import portable_path, portable_value, rows_sha256, sha256_file


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RUN_DIR = ROOT / "outputs" / "paper_upgrade_v1" / "adaptive_mcts_budget_v1"
DEFAULT_OUTPUT = ROOT / "protocols" / "paper_upgrade_v1" / "monitors" / "adaptive_mcts_budget_v1"
MONITOR_STEM = "adaptive_mcts_budget_formal_monitor_v1"
MONITOR_VERSION = "m3-paper-v1-adaptive-mcts-budget-monitor-1.0"
DEFAULT_STALL_SECONDS = 2700


def _path(path: Path) -> str:
    return portable_path(path, root=ROOT)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                value = json.loads(line)
                if isinstance(value, dict):
                    rows.append(value)
    return rows


def _pid_alive(pid: int | None) -> bool:
    if not pid or pid <= 0:
        return False
    if os.name == "nt":
        import ctypes

        process_query_limited_information = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(  # type: ignore[attr-defined]
            process_query_limited_information,
            False,
            pid,
        )
        if not handle:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)  # type: ignore[attr-defined]
        return True
    try:
        os.kill(pid, 0)
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _latest_artifact_time(run_dir: Path, manifest: Mapping[str, Any]) -> datetime | None:
    candidates: list[datetime] = []
    updated = _parse_time(manifest.get("updated_at"))
    if updated:
        candidates.append(updated)
    for path in (
        run_dir / "manifest.json",
        run_dir / "task_results.jsonl",
        run_dir / "failures.jsonl",
    ):
        if path.exists():
            candidates.append(datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc))
    task_root = run_dir / "tasks"
    if task_root.is_dir():
        for path in task_root.glob("*/queries/*.json"):
            candidates.append(datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc))
    return max(candidates) if candidates else None


def _health_status(
    *,
    manifest_status: str,
    pid_alive: bool,
    unresolved_failures: int,
    latest_age_seconds: float | None,
    stall_seconds: int,
) -> tuple[str, list[str]]:
    blockers: list[str] = []
    if not manifest_status:
        return "missing_manifest", ["run_manifest_missing"]
    if manifest_status == "completed_formal":
        return "completed_formal_admitted", []
    if manifest_status == "completed_formal_run_pending_analysis":
        return "completed_formal_pending_analysis", []
    if manifest_status == "completed_qualification_only":
        return "completed_qualification_only", []
    if manifest_status == "failed_preserved" or unresolved_failures:
        blockers.append("unresolved_failures_present")
        return "failed_requires_attention", blockers
    if manifest_status == "running":
        if not pid_alive:
            blockers.append("recorded_pid_not_alive")
            return "running_pid_not_alive", blockers
        if latest_age_seconds is not None and latest_age_seconds > stall_seconds:
            blockers.append("no_artifact_progress_within_stall_window")
            return "running_stalled", blockers
        return "running_progressing", []
    return "unrecognized_manifest_status", ["manifest_status_not_recognized"]


def build_monitor_snapshot(
    *,
    run_dir: Path = DEFAULT_RUN_DIR,
    output_dir: Path = DEFAULT_OUTPUT,
    stall_seconds: int = DEFAULT_STALL_SECONDS,
    now: datetime | None = None,
) -> dict[str, Any]:
    if stall_seconds < 1:
        raise ValueError("stall_seconds must be positive")
    run_dir = run_dir.resolve()
    output_dir = output_dir.resolve()
    manifest_path = run_dir / "manifest.json"
    config_path = run_dir / "execution_config.json"
    results_path = run_dir / "task_results.jsonl"
    failures_path = run_dir / "failures.jsonl"
    manifest = _read_json(manifest_path)
    config = _read_json(config_path)
    results = _read_jsonl(results_path)
    failures = _read_jsonl(failures_path)
    completed_ids = {str(row.get("task_id", "")) for row in results if row.get("task_id")}
    unresolved_failure_ids = {
        str(row.get("task_id", ""))
        for row in failures
        if row.get("task_id") and str(row.get("task_id", "")) not in completed_ids
    }
    frozen_tasks = int(manifest.get("frozen_task_count", config.get("selected_case_ids") and 80 or 0) or 0)
    selected_tasks = int(
        manifest.get("selected_task_count", len(config.get("selected_case_ids", []))) or 0
    )
    completed_tasks = len(completed_ids)
    missing_tasks = max(0, selected_tasks - completed_tasks - len(unresolved_failure_ids))
    query_files = list((run_dir / "tasks").glob("*/queries/*.json")) if (run_dir / "tasks").is_dir() else []
    observed_queries = len(query_files)
    manifest_queries = int(manifest.get("queries_executed", 0) or 0)
    latest = _latest_artifact_time(run_dir, manifest)
    snapshot_at = now or datetime.now(timezone.utc)
    latest_age = max(0.0, (snapshot_at - latest).total_seconds()) if latest else None
    pid = int(manifest.get("pid", 0) or 0)
    alive = _pid_alive(pid)
    health, blockers = _health_status(
        manifest_status=str(manifest.get("status", "")),
        pid_alive=alive,
        unresolved_failures=len(unresolved_failure_ids),
        latest_age_seconds=latest_age,
        stall_seconds=stall_seconds,
    )
    snapshot = {
        "schema_version": "paper-adaptive-mcts-budget-monitor-1.0",
        "monitor_version": MONITOR_VERSION,
        "status": "completed",
        "created_at": snapshot_at.isoformat(),
        "run_dir": _path(run_dir),
        "manifest_path": _path(manifest_path),
        "manifest_exists": manifest_path.is_file(),
        "manifest_sha256": sha256_file(manifest_path) if manifest_path.is_file() else "",
        "manifest_status": manifest.get("status", ""),
        "result_eligible_for_formal_tables": manifest.get(
            "result_eligible_for_formal_tables", False
        ),
        "analysis_manifest": portable_value(manifest.get("analysis_manifest", ""), root=ROOT),
        "pid": pid,
        "pid_alive": alive,
        "health_status": health,
        "health_blockers": blockers,
        "counts": {
            "frozen_tasks": frozen_tasks,
            "selected_tasks": selected_tasks,
            "completed_tasks": completed_tasks,
            "unresolved_failed_tasks": len(unresolved_failure_ids),
            "missing_tasks": missing_tasks,
            "manifest_queries_executed": manifest_queries,
            "query_artifact_count": observed_queries,
            "query_count_matches_manifest": observed_queries == manifest_queries,
        },
        "timing": {
            "latest_artifact_at": latest.isoformat() if latest else "",
            "latest_artifact_age_seconds": round(latest_age, 3) if latest_age is not None else None,
            "stall_threshold_seconds": stall_seconds,
        },
        "artifacts": {
            "execution_config": {
                "path": _path(config_path),
                "exists": config_path.is_file(),
                "sha256": sha256_file(config_path) if config_path.is_file() else "",
            },
            "task_results": {
                "path": _path(results_path),
                "exists": results_path.is_file(),
                "sha256": sha256_file(results_path) if results_path.is_file() else "",
            },
            "failures": {
                "path": _path(failures_path),
                "exists": failures_path.is_file(),
                "sha256": sha256_file(failures_path) if failures_path.is_file() else "",
            },
        },
        "snapshot_rows_sha256": rows_sha256(results),
        "boundary": (
            "Read-only monitoring only. This snapshot never retries tasks, changes query "
            "budgets, promotes manifests, or admits adaptive results."
        ),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{MONITOR_STEM}.json"
    md_path = output_dir / f"{MONITOR_STEM}.md"
    json_path.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(
        "\n".join(
            [
                "# Adaptive MCTS budget formal monitor v1",
                "",
                f"- Health: `{health}`",
                f"- Manifest status: `{manifest.get('status', '')}`",
                f"- PID alive: `{alive}`",
                f"- Tasks: {completed_tasks}/{selected_tasks}; failures: {len(unresolved_failure_ids)}; missing: {missing_tasks}",
                f"- Queries: manifest={manifest_queries}, artifacts={observed_queries}",
                "",
                "## Boundary",
                "",
                str(snapshot["boundary"]),
                "",
            ]
        ),
        encoding="utf-8",
    )
    snapshot["json_path"] = _path(json_path)
    snapshot["markdown_path"] = _path(md_path)
    return snapshot


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--stall-seconds", type=int, default=DEFAULT_STALL_SECONDS)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    snapshot = build_monitor_snapshot(
        run_dir=args.run_dir,
        output_dir=args.output_dir,
        stall_seconds=args.stall_seconds,
    )
    print(json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
