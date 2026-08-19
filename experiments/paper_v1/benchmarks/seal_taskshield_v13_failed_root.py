"""Seal the preserved Task Shield v1.3 failed formal root without editing it."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .common import portable_path, sha256_file


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RUN_DIR = (
    ROOT / "outputs" / "paper_upgrade_v1" / "baselines" / "taskshield_paper_formal_v13"
)
DEFAULT_MONITOR = (
    ROOT
    / "protocols"
    / "paper_upgrade_v1"
    / "monitors"
    / "task_shield_formal_v13"
    / "agentdojo_official_formal_run_monitor_v1.json"
)
DEFAULT_DIAGNOSTIC = (
    ROOT
    / "protocols"
    / "paper_upgrade_v1"
    / "diagnostics"
    / "task_shield_formal_v13"
    / "failure_diagnostic.json"
)
DEFAULT_DECISION = (
    ROOT
    / "protocols"
    / "paper_upgrade_v1"
    / "execution"
    / "taskshield_v14_recovery_decision_v1"
    / "taskshield_v14_operator_decision.approved.json"
)
DEFAULT_OUTPUT_DIR = (
    ROOT
    / "protocols"
    / "paper_upgrade_v1"
    / "execution"
    / "taskshield_v13_failed_root_seal_v1"
)
SEAL_JSON_NAME = "taskshield_v13_failed_root_seal_v1.json"
SEAL_MD_NAME = "taskshield_v13_failed_root_seal_v1.md"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
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


def _inventory(run_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not run_dir.is_dir():
        return rows
    for path in sorted(item for item in run_dir.rglob("*") if item.is_file()):
        rows.append(
            {
                "path": portable_path(path, root=ROOT),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return rows


def _rows_sha256(rows: list[dict[str, Any]]) -> str:
    payload = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _check(name: str, passed: bool, detail: Any) -> dict[str, Any]:
    return {"name": name, "status": "pass" if passed else "fail", "detail": detail}


def _write_markdown(path: Path, seal: Mapping[str, Any]) -> None:
    lines = [
        "# Task Shield v1.3 failed-root seal",
        "",
        f"- Status: `{seal['status']}`",
        f"- Result eligible: `{seal['result_eligible_for_formal_tables']}`",
        f"- Run root: `{seal['run_root']}`",
        f"- Files sealed: `{seal['file_count']}`",
        f"- Bytes sealed: `{seal['total_bytes']}`",
        f"- Inventory SHA-256: `{seal['inventory_sha256']}`",
        "",
        "## Final observed counts",
        "",
        f"- Completed: `{seal['counts']['completed_cases']}`",
        f"- Failed: `{seal['counts']['failed_cases']}`",
        f"- Missing: `{seal['counts']['missing_cases']}`",
        f"- Expected: `{seal['counts']['expected_cases']}`",
        "",
        "## Seal checks",
        "",
    ]
    lines.extend(
        f"- `{row['status']}` — `{row['name']}`: `{row['detail']}`"
        for row in seal["checks"]
    )
    lines.extend(["", "## Boundary", "", str(seal["boundary"]), ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def build_failed_root_seal(
    *,
    run_dir: Path = DEFAULT_RUN_DIR,
    monitor_path: Path = DEFAULT_MONITOR,
    diagnostic_path: Path = DEFAULT_DIAGNOSTIC,
    decision_path: Path = DEFAULT_DECISION,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    monitor = _read_json(monitor_path)
    diagnostic = _read_json(diagnostic_path)
    decision = _read_json(decision_path)
    run_manifest_path = run_dir / "run_manifest.json"
    run_manifest = _read_json(run_manifest_path)
    counts = monitor.get("counts", {}) if isinstance(monitor.get("counts"), Mapping) else {}
    diagnostic_counts = (
        diagnostic.get("counts", {})
        if isinstance(diagnostic.get("counts"), Mapping)
        else {}
    )
    rows = _inventory(run_dir)
    expected_run_dir = portable_path(run_dir, root=ROOT)
    checks = [
        _check("run_root_exists", run_dir.is_dir(), expected_run_dir),
        _check("run_manifest_exists", run_manifest_path.is_file(), expected_run_dir),
        _check("monitor_pid_is_not_alive", monitor.get("pid_alive") is False, monitor.get("pid")),
        _check("monitor_matches_run_root", monitor.get("run_dir") == expected_run_dir, monitor.get("run_dir")),
        _check("failed_case_is_retained", int(counts.get("failed_cases", 0) or 0) > 0, counts.get("failed_cases")),
        _check("partial_root_not_admitted", monitor.get("formal_result_admitted_now") is False, monitor.get("formal_result_admitted_now")),
        _check(
            "failure_diagnostic_matches_monitor",
            int(diagnostic_counts.get("failed_rows", 0) or 0)
            == int(counts.get("failed_cases", 0) or 0),
            {
                "diagnostic_failed_rows": diagnostic_counts.get("failed_rows", 0),
                "monitor_failed_cases": counts.get("failed_cases", 0),
            },
        ),
        _check(
            "operator_decision_approved_fresh_root",
            decision.get("decision_status") == "approved"
            and decision.get("chosen_recovery_path")
            == "preserve_v1_3_failed_root_start_fresh_v14",
            decision.get("chosen_recovery_path", ""),
        ),
        _check("root_inventory_nonempty", bool(rows), len(rows)),
    ]
    failed_checks = [row["name"] for row in checks if row["status"] != "pass"]
    seal = {
        "schema_version": "paper-taskshield-v13-failed-root-seal-1.0",
        "status": "sealed_failed_formal_root" if not failed_checks else "blocked_not_sealed",
        "sealed_at": datetime.now(timezone.utc).isoformat(),
        "run_root": expected_run_dir,
        "result_eligible_for_formal_tables": False,
        "root_write_policy": "preserve_read_only_do_not_resume_retry_exclude_pool_or_admit",
        "counts": {
            "completed_cases": int(counts.get("completed_cases", 0) or 0),
            "failed_cases": int(counts.get("failed_cases", 0) or 0),
            "missing_cases": int(counts.get("missing_cases", 0) or 0),
            "expected_cases": int(counts.get("expected_cases", 0) or 0),
        },
        "identity": {
            "runner_version": run_manifest.get("runner_version", ""),
            "model_id": run_manifest.get("model_id", ""),
            "freeze_sha256": run_manifest.get("freeze_sha256", ""),
            "selected_case_rows_sha256": run_manifest.get("selected_case_rows_sha256", ""),
        },
        "references": {
            "run_manifest": {"path": portable_path(run_manifest_path, root=ROOT), "sha256": sha256_file(run_manifest_path)},
            "monitor": {"path": portable_path(monitor_path, root=ROOT), "sha256": sha256_file(monitor_path)},
            "failure_diagnostic": {"path": portable_path(diagnostic_path, root=ROOT), "sha256": sha256_file(diagnostic_path)},
            "operator_decision": {"path": portable_path(decision_path, root=ROOT), "sha256": sha256_file(decision_path)},
        },
        "file_count": len(rows),
        "total_bytes": sum(int(row["bytes"]) for row in rows),
        "inventory_sha256": _rows_sha256(rows),
        "files": rows,
        "checks": checks,
        "failed_checks": failed_checks,
        "boundary": (
            "The seal is written outside the failed root. It hashes but never edits, "
            "resumes, retries, excludes, pools, analyzes or admits v1.3 evidence."
        ),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / SEAL_JSON_NAME, seal)
    _write_markdown(output_dir / SEAL_MD_NAME, seal)
    return seal


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--monitor", type=Path, default=DEFAULT_MONITOR)
    parser.add_argument("--diagnostic", type=Path, default=DEFAULT_DIAGNOSTIC)
    parser.add_argument("--decision", type=Path, default=DEFAULT_DECISION)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--fail-on-blocked", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    seal = build_failed_root_seal(
        run_dir=args.run_dir,
        monitor_path=args.monitor,
        diagnostic_path=args.diagnostic,
        decision_path=args.decision,
        output_dir=args.output_dir,
    )
    print(json.dumps(seal, ensure_ascii=False, indent=2, sort_keys=True))
    if args.fail_on_blocked and seal["status"] != "sealed_failed_formal_root":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
