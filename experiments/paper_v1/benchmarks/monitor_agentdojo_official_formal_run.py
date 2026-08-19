"""Monitor an official AgentDojo formal-run directory without mutating results.

The formal runners write three independent evidence streams:

* ``run_manifest.json`` for run-level status and admission metadata;
* ``progress.jsonl`` for append-only case start/end events;
* ``outcomes.jsonl`` plus per-case manifests for completed/failed case rows.

This monitor deliberately stays read-only.  It is meant for long-running cells
where the correct next action depends on whether the run is still progressing,
has completed with formal admission, or has produced failures that must be
analyzed before any retry.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import math
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .common import portable_path, rows_sha256, sha256_file


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RUN_DIR = (
    ROOT
    / "outputs"
    / "paper_upgrade_v1"
    / "baselines"
    / "agentdojo_transformers_pi_detector_official_resource_isolated_formal_v1"
)
DEFAULT_OUTPUT_DIR = ROOT / "protocols" / "paper_upgrade_v1"
MONITOR_STEM = "agentdojo_official_formal_run_monitor_v1"
MONITOR_VERSION = "m3-paper-v1-agentdojo-official-formal-run-monitor-1.0"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_no} must contain a JSON object")
        rows.append(value)
    return rows


def _parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _latest_time(rows: Iterable[Mapping[str, Any]], *fields: str) -> datetime | None:
    times: list[datetime] = []
    for row in rows:
        for field in fields:
            parsed = _parse_time(row.get(field))
            if parsed is not None:
                times.append(parsed)
    return max(times) if times else None


def _seconds_since(moment: datetime | None, now: datetime) -> float | None:
    if moment is None:
        return None
    return max(0.0, (now - moment).total_seconds())


def _pid_alive(pid: Any) -> bool | None:
    try:
        pid_int = int(pid)
    except (TypeError, ValueError):
        return None
    if pid_int <= 0:
        return None
    if os.name == "nt":
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        process_query_limited_information = 0x1000
        still_active = 259
        kernel32.OpenProcess.argtypes = [
            ctypes.c_uint32,
            ctypes.c_int,
            ctypes.c_uint32,
        ]
        kernel32.OpenProcess.restype = ctypes.c_void_p
        kernel32.GetExitCodeProcess.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_uint32),
        ]
        kernel32.GetExitCodeProcess.restype = ctypes.c_int
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel32.CloseHandle.restype = ctypes.c_int
        handle = kernel32.OpenProcess(
            process_query_limited_information,
            False,
            pid_int,
        )
        if handle:
            exit_code = ctypes.c_uint32()
            try:
                if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                    return None
                return exit_code.value == still_active
            finally:
                kernel32.CloseHandle(handle)
        error_access_denied = 5
        return kernel32.GetLastError() == error_access_denied
    try:
        os.kill(pid_int, 0)
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _expected_cases(
    manifest: Mapping[str, Any],
    progress_rows: list[Mapping[str, Any]],
    outcomes_rows: list[Mapping[str, Any]],
) -> int:
    summary = manifest.get("summary")
    if isinstance(summary, Mapping):
        value = summary.get("expected_cases")
        if value not in {None, ""}:
            return int(value)
    for row in reversed(progress_rows):
        value = row.get("selected_cases")
        if value not in {None, ""}:
            return int(value)
    return len(outcomes_rows)


def _status_counts(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get("status", "")) for row in rows).items()))


def _case_kind_counts(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get("case_kind", "")) for row in rows).items()))


def _rate_per_hour(done: int, started_at: datetime | None, now: datetime) -> float | None:
    elapsed = _seconds_since(started_at, now)
    if elapsed is None or elapsed <= 0:
        return None
    return done / (elapsed / 3600.0)


def _eta_hours(missing: int, rate_per_hour: float | None) -> float | None:
    if not rate_per_hour or rate_per_hour <= 0:
        return None
    return missing / rate_per_hour


def _round_or_none(value: float | None, digits: int = 3) -> float | None:
    if value is None or not math.isfinite(value):
        return None
    return round(value, digits)


def _health_status(
    *,
    manifest_status: str,
    expected: int,
    completed: int,
    failed: int,
    missing: int,
    process_alive: bool | None,
    last_update_age_seconds: float | None,
    stall_seconds: int,
) -> tuple[str, list[str]]:
    blockers: list[str] = []
    if manifest_status == "completed_formal" and missing == 0 and failed == 0:
        return "completed_formal_admitted", blockers
    if manifest_status.startswith("completed") and failed:
        blockers.append("failed_cases_present")
        return "completed_with_failures_requires_analysis", blockers
    if manifest_status.startswith("completed") and missing:
        blockers.append("missing_cases_present")
        return "completed_incomplete_requires_analysis", blockers
    if failed:
        blockers.append("failed_cases_present")
        return "running_with_failures_requires_attention", blockers
    if manifest_status == "running":
        if process_alive is False:
            blockers.append("manifest_running_but_pid_not_alive")
            return "stopped_without_terminal_manifest", blockers
        if last_update_age_seconds is not None and last_update_age_seconds > stall_seconds:
            blockers.append("no_progress_after_stall_threshold")
            return "running_stall_suspected", blockers
        if expected and completed + failed > expected:
            blockers.append("case_count_exceeds_expected")
            return "running_inconsistent_counts", blockers
        return "running_progressing", blockers
    if not manifest_status:
        blockers.append("run_manifest_missing_or_empty")
        return "missing_manifest", blockers
    if expected and completed == expected and failed == 0 and missing == 0:
        blockers.append("manifest_not_formally_admitted")
        return "complete_but_not_formally_admitted", blockers
    blockers.append("unrecognized_or_nonterminal_manifest_status")
    return "requires_manual_review", blockers


def build_monitor_snapshot(
    *,
    run_dir: Path = DEFAULT_RUN_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    stall_minutes: int = 45,
    write_files: bool = True,
    now: datetime | None = None,
) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    output_dir = output_dir.resolve()
    now = now or datetime.now(timezone.utc)
    manifest_path = run_dir / "run_manifest.json"
    progress_path = run_dir / "progress.jsonl"
    outcomes_path = run_dir / "outcomes.jsonl"
    case_root = run_dir / "case_manifests"

    manifest = _read_json(manifest_path)
    progress_rows = _read_jsonl(progress_path)
    outcomes_rows = _read_jsonl(outcomes_path)
    case_manifest_count = (
        len(list(case_root.glob("*.json"))) if case_root.exists() else 0
    )
    expected = _expected_cases(manifest, progress_rows, outcomes_rows)
    completed = sum(1 for row in outcomes_rows if row.get("status") == "completed")
    failed = sum(1 for row in outcomes_rows if row.get("status") == "failed")
    observed = len(outcomes_rows)
    missing = max(0, expected - observed) if expected else 0
    started_at = _parse_time(manifest.get("started_at"))
    manifest_updated_at = _parse_time(manifest.get("updated_at")) or _parse_time(
        manifest.get("completed_at")
    )
    latest_progress_at = _latest_time(progress_rows, "created_at")
    latest_outcome_at = _latest_time(outcomes_rows, "created_at", "completed_at")
    latest_update_at = max(
        [t for t in [manifest_updated_at, latest_progress_at, latest_outcome_at] if t],
        default=None,
    )
    elapsed_seconds = _seconds_since(started_at, now)
    last_update_age_seconds = _seconds_since(latest_update_at, now)
    rate = _rate_per_hour(observed, started_at, now)
    eta = _eta_hours(missing, rate)
    process_alive = _pid_alive(manifest.get("pid"))
    stall_seconds = int(stall_minutes * 60)
    health, blockers = _health_status(
        manifest_status=str(manifest.get("status", "")),
        expected=expected,
        completed=completed,
        failed=failed,
        missing=missing,
        process_alive=process_alive,
        last_update_age_seconds=last_update_age_seconds,
        stall_seconds=stall_seconds,
    )
    last_event = progress_rows[-1] if progress_rows else {}
    formal_admitted = (
        manifest.get("status") == "completed_formal"
        and bool(manifest.get("result_eligible_for_formal_tables"))
        and missing == 0
        and failed == 0
    )
    snapshot = {
        "schema_version": "paper-agentdojo-official-formal-run-monitor-1.0",
        "monitor_version": MONITOR_VERSION,
        "status": "completed",
        "created_at": now.isoformat(),
        "run_dir": portable_path(run_dir, root=ROOT),
        "run_manifest_path": portable_path(manifest_path, root=ROOT),
        "run_manifest_exists": manifest_path.exists(),
        "run_manifest_sha256": sha256_file(manifest_path) if manifest_path.exists() else "",
        "progress_path": portable_path(progress_path, root=ROOT),
        "progress_exists": progress_path.exists(),
        "progress_sha256": sha256_file(progress_path) if progress_path.exists() else "",
        "outcomes_path": portable_path(outcomes_path, root=ROOT),
        "outcomes_exists": outcomes_path.exists(),
        "outcomes_sha256": sha256_file(outcomes_path) if outcomes_path.exists() else "",
        "manifest_status": str(manifest.get("status", "")),
        "condition_id": str(manifest.get("condition_id", "")),
        "model_id": str(manifest.get("model_id", "")),
        "pid": manifest.get("pid"),
        "pid_alive": process_alive,
        "formal_result_admitted_now": formal_admitted,
        "health_status": health,
        "health_blockers": blockers,
        "counts": {
            "expected_cases": expected,
            "observed_outcomes": observed,
            "case_manifest_count": case_manifest_count,
            "completed_cases": completed,
            "failed_cases": failed,
            "missing_cases": missing,
            "progress_events": len(progress_rows),
            "progress_status_counts": _status_counts(progress_rows),
            "outcome_status_counts": _status_counts(outcomes_rows),
            "outcome_case_kind_counts": _case_kind_counts(outcomes_rows),
        },
        "timing": {
            "started_at": started_at.isoformat() if started_at else "",
            "latest_update_at": latest_update_at.isoformat() if latest_update_at else "",
            "elapsed_seconds": _round_or_none(elapsed_seconds),
            "last_update_age_seconds": _round_or_none(last_update_age_seconds),
            "observed_cases_per_hour": _round_or_none(rate),
            "eta_hours_at_current_rate": _round_or_none(eta),
            "stall_threshold_seconds": stall_seconds,
        },
        "last_progress_event": last_event,
        "snapshot_rows_sha256": rows_sha256(
            [
                {
                    "manifest_status": str(manifest.get("status", "")),
                    "expected": expected,
                    "observed": observed,
                    "completed": completed,
                    "failed": failed,
                    "missing": missing,
                    "health_status": health,
                    "latest_update_at": latest_update_at.isoformat()
                    if latest_update_at
                    else "",
                }
            ]
        ),
        "boundary": (
            "Read-only monitoring snapshot. It does not repair, retry, admit, "
            "exclude, or analyze formal results. Only a completed formal run "
            "with exact frozen coverage and zero unexplained failures may enter "
            "paper result tables."
        ),
    }
    if write_files:
        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = output_dir / f"{MONITOR_STEM}.json"
        md_path = output_dir / f"{MONITOR_STEM}.md"
        json_path.write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        _write_markdown(md_path, snapshot)
        snapshot["json_path"] = portable_path(json_path, root=ROOT)
        snapshot["markdown_path"] = portable_path(md_path, root=ROOT)
    return snapshot


def _write_markdown(path: Path, snapshot: Mapping[str, Any]) -> None:
    counts = snapshot["counts"]
    timing = snapshot["timing"]
    blockers = "; ".join(snapshot["health_blockers"]) or "none"
    lines = [
        "# AgentDojo official formal-run monitor v1",
        "",
        f"Generated: {snapshot['created_at']}",
        "",
        "## Status",
        "",
        f"- Health: `{snapshot['health_status']}`",
        f"- Manifest status: `{snapshot['manifest_status']}`",
        f"- Formal result admitted now: `{snapshot['formal_result_admitted_now']}`",
        f"- Condition: `{snapshot['condition_id']}`",
        f"- Model: `{snapshot['model_id']}`",
        f"- PID: `{snapshot['pid']}`; alive: `{snapshot['pid_alive']}`",
        f"- Blockers: {blockers}",
        "",
        "## Counts",
        "",
        f"- Expected cases: {counts['expected_cases']}",
        f"- Observed outcomes: {counts['observed_outcomes']}",
        f"- Completed / failed / missing: {counts['completed_cases']} / "
        f"{counts['failed_cases']} / {counts['missing_cases']}",
        f"- Case manifests: {counts['case_manifest_count']}",
        f"- Progress events: {counts['progress_events']}",
        "",
        "## Timing",
        "",
        f"- Started: `{timing['started_at']}`",
        f"- Latest update: `{timing['latest_update_at']}`",
        f"- Elapsed seconds: `{timing['elapsed_seconds']}`",
        f"- Last update age seconds: `{timing['last_update_age_seconds']}`",
        f"- Observed cases/hour: `{timing['observed_cases_per_hour']}`",
        f"- ETA hours at current rate: `{timing['eta_hours_at_current_rate']}`",
        "",
        "## Boundary",
        "",
        str(snapshot["boundary"]),
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--stall-minutes", type=int, default=45)
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Print the snapshot only; do not write monitor JSON/Markdown files.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    snapshot = build_monitor_snapshot(
        run_dir=args.run_dir,
        output_dir=args.output_dir,
        stall_minutes=args.stall_minutes,
        write_files=not args.no_write,
    )
    print(json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
