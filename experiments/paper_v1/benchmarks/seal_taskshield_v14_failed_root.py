"""Seal the stopped Task Shield v1.4 failed formal root without editing it."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from . import seal_taskshield_v13_failed_root as common
from .common import portable_path, sha256_file


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RUN_DIR = (
    ROOT / "outputs" / "paper_upgrade_v1" / "baselines" / "taskshield_paper_formal_v14"
)
DEFAULT_MONITOR = (
    ROOT
    / "protocols"
    / "paper_upgrade_v1"
    / "monitors"
    / "task_shield_formal_v14"
    / "agentdojo_official_formal_run_monitor_v1.json"
)
DEFAULT_DIAGNOSTIC = (
    ROOT
    / "protocols"
    / "paper_upgrade_v1"
    / "execution"
    / "taskshield_formal_v14_failure_diagnostic_v1"
    / "failure_diagnostic.json"
)
DEFAULT_DECISION = (
    ROOT
    / "protocols"
    / "paper_upgrade_v1"
    / "execution"
    / "taskshield_v15_failure_audit_v1"
    / "taskshield_v15_operator_decision.approved.json"
)
DEFAULT_OUTPUT_DIR = (
    ROOT
    / "protocols"
    / "paper_upgrade_v1"
    / "execution"
    / "taskshield_v14_failed_root_seal_v1"
)
SEAL_JSON_NAME = "taskshield_v14_failed_root_seal_v1.json"
SEAL_MD_NAME = "taskshield_v14_failed_root_seal_v1.md"
RECOVERY_PATH = (
    "preserve_v1_4_failed_root_start_v1_5_failure_audit_and_expanded_qualification"
)


def _write_markdown(path: Path, seal: Mapping[str, Any]) -> None:
    counts = seal["counts"]
    lines = [
        "# Task Shield v1.4 failed-root seal",
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
        f"- Completed: `{counts['completed_cases']}`",
        f"- Failed: `{counts['failed_cases']}`",
        f"- Missing: `{counts['missing_cases']}`",
        f"- Expected: `{counts['expected_cases']}`",
        "",
        "## Checks",
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
    monitor = common._read_json(monitor_path)
    diagnostic = common._read_json(diagnostic_path)
    decision = common._read_json(decision_path)
    run_manifest_path = run_dir / "run_manifest.json"
    run_manifest = common._read_json(run_manifest_path)
    counts = monitor.get("counts", {}) if isinstance(monitor.get("counts"), Mapping) else {}
    diagnostic_counts = (
        diagnostic.get("counts", {})
        if isinstance(diagnostic.get("counts"), Mapping)
        else {}
    )
    rows = common._inventory(run_dir)
    expected_run_dir = portable_path(run_dir, root=ROOT)
    acknowledgements = decision.get("acknowledgements", {})
    checks = [
        common._check("run_root_exists", run_dir.is_dir(), expected_run_dir),
        common._check("run_manifest_exists", run_manifest_path.is_file(), expected_run_dir),
        common._check(
            "monitor_pid_is_not_alive", monitor.get("pid_alive") is False, monitor.get("pid")
        ),
        common._check(
            "monitor_matches_run_root",
            monitor.get("run_dir") == expected_run_dir,
            monitor.get("run_dir"),
        ),
        common._check(
            "failed_cases_are_retained",
            int(counts.get("failed_cases", 0) or 0) > 0,
            counts.get("failed_cases"),
        ),
        common._check(
            "partial_root_not_admitted",
            monitor.get("formal_result_admitted_now") is False,
            monitor.get("formal_result_admitted_now"),
        ),
        common._check(
            "failure_diagnostic_matches_monitor",
            int(diagnostic_counts.get("failed_rows", 0) or 0)
            == int(counts.get("failed_cases", 0) or 0),
            {
                "diagnostic_failed_rows": diagnostic_counts.get("failed_rows", 0),
                "monitor_failed_cases": counts.get("failed_cases", 0),
            },
        ),
        common._check(
            "operator_decision_approved_fresh_v15_audit",
            decision.get("decision_status") == "approved"
            and decision.get("chosen_recovery_path") == RECOVERY_PATH
            and isinstance(acknowledgements, Mapping)
            and all(bool(value) for value in acknowledgements.values()),
            decision.get("chosen_recovery_path", ""),
        ),
        common._check("root_inventory_nonempty", bool(rows), len(rows)),
    ]
    failed_checks = [row["name"] for row in checks if row["status"] != "pass"]
    seal = {
        "schema_version": "paper-taskshield-v14-failed-root-seal-1.0",
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
            "selected_case_rows_sha256": run_manifest.get(
                "selected_case_rows_sha256", ""
            ),
        },
        "references": {
            "run_manifest": {
                "path": portable_path(run_manifest_path, root=ROOT),
                "sha256": sha256_file(run_manifest_path),
            },
            "monitor": {
                "path": portable_path(monitor_path, root=ROOT),
                "sha256": sha256_file(monitor_path),
            },
            "failure_diagnostic": {
                "path": portable_path(diagnostic_path, root=ROOT),
                "sha256": sha256_file(diagnostic_path),
            },
            "operator_decision": {
                "path": portable_path(decision_path, root=ROOT),
                "sha256": sha256_file(decision_path),
            },
        },
        "file_count": len(rows),
        "total_bytes": sum(int(row["bytes"]) for row in rows),
        "inventory_sha256": common._rows_sha256(rows),
        "files": rows,
        "checks": checks,
        "failed_checks": failed_checks,
        "boundary": (
            "The seal is written outside the failed root. It hashes but never edits, "
            "resumes, retries, excludes, pools, analyzes or admits v1.4 evidence."
        ),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    common._write_json(output_dir / SEAL_JSON_NAME, seal)
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
