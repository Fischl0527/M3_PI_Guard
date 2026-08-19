"""Validate a Task Shield v1.4 operator recovery decision artifact.

The validator is deliberately fail-closed.  It reads a recovery package and a
separate operator decision JSON, then reports whether v1.4 qualification may be
started later by a human/operator.  It never stops processes, starts model work,
retries cases, analyzes formal roots, admits registries, or changes Q2
readiness.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from .common import portable_path
from .prepare_taskshield_v14_recovery_package import (
    DECISION_APPROVED_JSON_NAME,
    DEFAULT_OUTPUT_DIR,
    PACKAGE_JSON_NAME,
    ROOT,
)


DEFAULT_PACKAGE = DEFAULT_OUTPUT_DIR / PACKAGE_JSON_NAME
DEFAULT_DECISION = DEFAULT_OUTPUT_DIR / DECISION_APPROVED_JSON_NAME
AUDIT_JSON_NAME = "taskshield_v14_operator_decision_validation_v1.json"
AUDIT_MD_NAME = "taskshield_v14_operator_decision_validation_v1.md"
REQUIRED_ACKNOWLEDGEMENTS = (
    "v1_3_failed_root_is_preserved_and_ineligible",
    "no_selective_failed_case_retry",
    "no_failed_row_exclusion",
    "no_v1_3_partial_admission",
    "v14_must_start_from_fresh_roots",
    "q2_score_does_not_change_until_clean_admission",
    "validator_does_not_stop_or_start_processes",
)
APPROVED_PATH = "preserve_v1_3_failed_root_start_fresh_v14"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
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


def _sha256(path: Path) -> str:
    if not path.exists():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _valid_iso_datetime(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _write_markdown(path: Path, audit: Mapping[str, Any]) -> None:
    lines = [
        "# Task Shield v1.4 operator decision validation",
        "",
        f"- Status: `{audit['status']}`",
        f"- Result eligible: `{audit['result_eligible_for_formal_tables']}`",
        f"- Q2 score change: `{audit['q2_score_change']}`",
        f"- Approved to start v1.4 qualification: `{audit['approved_to_start_v14_qualification']}`",
        "",
        "## Blockers",
        "",
    ]
    blockers = audit.get("blockers", [])
    if blockers:
        lines.extend(f"- `{blocker}`" for blocker in blockers)
    else:
        lines.append("- none")
    lines.extend(["", "## Boundary", "", str(audit["boundary"]), ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def build_operator_decision_validation(
    *,
    package_path: Path = DEFAULT_PACKAGE,
    decision_path: Path = DEFAULT_DECISION,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    package = _read_json(package_path)
    decision = _read_json(decision_path)
    blockers: list[str] = []

    if not package:
        blockers.append("missing_recovery_package")
    if not decision:
        blockers.append("missing_operator_decision")

    package_sha256 = _sha256(package_path)
    if decision and decision.get("recovery_package_sha256") != package_sha256:
        blockers.append("decision_recovery_package_sha256_mismatch")
    if package.get("can_start_v14_qualification_now") is not True:
        blockers.append("recovery_package_not_ready_for_v14_qualification")
    if package.get("status") != "ready_for_v14_qualification_after_explicit_decision":
        blockers.append("recovery_package_status_not_ready")

    # A missing decision is one actionable blocker, not a cascade of synthetic
    # schema, acknowledgement and identity mismatches. Validate decision-only
    # fields only after a real decision object exists; the gate remains
    # fail-closed while the operator handoff becomes precise.
    if decision:
        if decision.get("schema_version") != "paper-taskshield-v14-operator-decision-1.0":
            blockers.append("decision_schema_version_invalid")
        if decision.get("decision_status") != "approved":
            blockers.append("decision_status_not_approved")
        if not str(decision.get("approved_by", "")).strip():
            blockers.append("approved_by_missing")
        if not _valid_iso_datetime(decision.get("approved_at_utc")):
            blockers.append("approved_at_utc_missing_or_invalid")
        if decision.get("chosen_recovery_path") != APPROVED_PATH:
            blockers.append("chosen_recovery_path_not_v14_fresh_root")

        acknowledgements = decision.get("acknowledgements", {})
        if not isinstance(acknowledgements, Mapping):
            acknowledgements = {}
        for key in REQUIRED_ACKNOWLEDGEMENTS:
            if acknowledgements.get(key) is not True:
                blockers.append(f"acknowledgement_missing:{key}")

        v13 = (
            package.get("v1_3_root", {})
            if isinstance(package.get("v1_3_root"), Mapping)
            else {}
        )
        v14 = (
            package.get("v1_4_protocol", {})
            if isinstance(package.get("v1_4_protocol"), Mapping)
            else {}
        )
        qualification_root = (
            v14.get("qualification_root", {})
            if isinstance(v14.get("qualification_root"), Mapping)
            else {}
        )
        formal_root = (
            v14.get("formal_root", {})
            if isinstance(v14.get("formal_root"), Mapping)
            else {}
        )
        expected_checks = {
            "expected_v1_3_run_dir": v13.get("run_dir", ""),
            "expected_v1_3_monitor_sha256": v13.get("monitor_sha256", ""),
            "expected_v14_qualification_root": qualification_root.get("path", ""),
            "expected_v14_formal_root": formal_root.get("path", ""),
        }
        for key, expected in expected_checks.items():
            if decision.get(key) != expected:
                blockers.append(f"{key}_mismatch")

    approved = not blockers
    audit = {
        "schema_version": "paper-taskshield-v14-operator-decision-validation-1.0",
        "status": (
            "approved_to_start_v14_qualification"
            if approved
            else "blocked_not_approved_to_start_v14"
        ),
        "created_at": datetime.now().astimezone().isoformat(),
        "approved_to_start_v14_qualification": approved,
        "result_eligible_for_formal_tables": False,
        "q2_score_change": 0.0,
        "blockers": blockers,
        "package": {
            "path": portable_path(package_path, root=ROOT),
            "sha256": package_sha256,
            "status": package.get("status", ""),
            "can_start_v14_qualification_now": package.get(
                "can_start_v14_qualification_now", False
            ),
        },
        "decision": {
            "path": portable_path(decision_path, root=ROOT),
            "sha256": _sha256(decision_path),
            "decision_status": decision.get("decision_status", ""),
            "chosen_recovery_path": decision.get("chosen_recovery_path", ""),
        },
        "boundary": (
            "Read-only operator decision validation. It does not stop processes, "
            "start v1.4, retry cases, analyze formal roots, admit registries or "
            "change Q2 readiness."
        ),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / AUDIT_JSON_NAME, audit)
    _write_markdown(output_dir / AUDIT_MD_NAME, audit)
    return audit


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, default=DEFAULT_PACKAGE)
    parser.add_argument("--decision", type=Path, default=DEFAULT_DECISION)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--fail-on-blocked",
        action="store_true",
        help="Return a non-zero exit code when the decision is not approved.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    audit = build_operator_decision_validation(
        package_path=args.package,
        decision_path=args.decision,
        output_dir=args.output_dir,
    )
    print(json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True))
    if args.fail_on_blocked and not audit["approved_to_start_v14_qualification"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
