"""Audit formal-admission readiness for required strong baselines.

This gate is stricter than the source/readiness registries.  It asks whether a
strong baseline may enter a paper-v1 formal result table, not merely whether its
source, blocker list or stub adapter is documented.

The script is intentionally read-only: it does not clone repositories, install
packages, download models, start model services, call APIs or run baselines.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from .common import portable_path, portable_value, rows_sha256, sha256_file


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_BASELINE_REGISTRY = ROOT / "protocols" / "paper_upgrade_v1" / "baseline_registry.json"
DEFAULT_EXTERNAL_REGISTRY = (
    ROOT / "protocols" / "paper_upgrade_v1" / "external_strong_baselines_v1.json"
)
DEFAULT_AGENTDOJO_AUDIT = (
    ROOT
    / "protocols"
    / "paper_upgrade_v1"
    / "agentdojo_official_strong_baseline_capability_audit_v1.json"
)
DEFAULT_DEPENDENCY_SNAPSHOT = (
    ROOT
    / "protocols"
    / "paper_upgrade_v1"
    / "strong_baseline_dependency_snapshot_v1.json"
)
DEFAULT_OUTPUT = ROOT / "protocols" / "paper_upgrade_v1"
AUDIT_VERSION = "m3-paper-v1-strong-baseline-formal-readiness-audit-1.0"
AUDIT_STEM = "strong_baseline_formal_readiness_audit_v1"

REQUIRED_STRONG_BASELINES = {
    "agentdojo_tool_filter",
    "agentdojo_transformers_pi_detector",
    "promptguard",
    "task_shield",
    "ipiguard",
    "progent",
    "camel_or_fides",
}
EXTERNAL_STRONG_BASELINES = {
    "promptguard",
    "task_shield",
    "ipiguard",
    "progent",
    "camel_or_fides",
}
AGENTDOJO_OFFICIAL_STRONG_BASELINES = {
    "agentdojo_tool_filter",
    "agentdojo_transformers_pi_detector",
}
FORMAL_ADMISSION_READY_STATUSES = {"ready", "ready_detector_only_formal"}


def _check(name: str, passed: bool, *, severity: str = "error", detail: Any = None) -> dict[str, Any]:
    return {
        "name": name,
        "status": "pass" if passed else "fail",
        "severity": severity,
        "detail": detail,
    }


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(str(path) + " must contain a JSON object")
    return value


def _read_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return _read_json(path)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _condition_index(registry: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    rows = registry.get("conditions")
    if not isinstance(rows, list):
        raise ValueError("baseline registry missing conditions list")
    return {str(row.get("id", "")): dict(row) for row in rows if isinstance(row, Mapping)}


def _external_entries_by_key(registry: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    rows = registry.get("entries")
    if not isinstance(rows, list):
        raise ValueError("external strong-baseline registry missing entries list")
    by_key: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        by_key.setdefault(str(row.get("registry_key", "")), []).append(dict(row))
    return by_key


def _result_eligible(row: Mapping[str, Any]) -> bool:
    return bool(row.get("result_eligible", row.get("implementation_status") == "ready"))


def _requirement(name: str, passed: bool, detail: Any = None) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "detail": detail}


def _resolve_repo_path(value: Any) -> Path | None:
    if not value:
        return None
    path = Path(str(value))
    if not path.is_absolute():
        path = ROOT / path
    return path


def _adapter_manifest_for_condition(
    condition: Mapping[str, Any],
    entries: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    candidates: list[Any] = [
        condition.get("formal_manifest"),
        condition.get("formal_freeze"),
        condition.get("adapter_preflight"),
    ]
    for entry in entries:
        source_backed = entry.get("source_backed_formal_adapter")
        if isinstance(source_backed, Mapping):
            candidates.append(source_backed.get("freeze"))
        preflight = entry.get("adapter_preflight")
        if isinstance(preflight, Mapping):
            candidates.append(preflight.get("manifest"))
        elif preflight:
            candidates.append(preflight)
    for candidate in candidates:
        path = _resolve_repo_path(candidate)
        if path and path.exists():
            manifest = _read_optional_json(path)
            manifest["_manifest_path"] = str(path)
            manifest["_manifest_sha256"] = sha256_file(path)
            return manifest
    return {}


def _entry_preflight_status(
    entry: Mapping[str, Any],
    adapter_manifest: Mapping[str, Any],
) -> str:
    if adapter_manifest:
        return str(adapter_manifest.get("status", ""))
    preflight = entry.get("adapter_preflight")
    if isinstance(preflight, Mapping):
        return str(preflight.get("status", ""))
    return ""


def _is_source_backed_adapter_status(status: str) -> bool:
    status_lc = str(status).lower()
    if not status_lc:
        return False
    non_formal_markers = {
        "blocked",
        "stub",
        "smoke",
        "preflight_only",
        "formal_run_pending",
        "source_smoke",
        "ready_for_official_source_smoke",
    }
    return not any(marker in status_lc for marker in non_formal_markers)


def _camel_selected_entry_id(adapter_manifest: Mapping[str, Any]) -> str:
    selected = str(adapter_manifest.get("config", {}).get("selected_candidate", ""))
    if selected == "camel":
        return "camel_google_research"
    if selected == "fides":
        return "fides_microsoft"
    return ""


def _external_requirements(
    condition_id: str,
    condition: Mapping[str, Any],
    external_by_key: Mapping[str, list[dict[str, Any]]],
    dependency_snapshot: Mapping[str, Any],
) -> list[dict[str, Any]]:
    entries = list(external_by_key.get(condition_id, []))
    adapter_manifest = _adapter_manifest_for_condition(condition, entries)
    selection_manifest = adapter_manifest
    if condition_id == "camel_or_fides":
        formal_freeze_path = _resolve_repo_path(condition.get("formal_freeze"))
        if formal_freeze_path and formal_freeze_path.exists():
            selection_manifest = _read_optional_json(formal_freeze_path)
            selection_manifest["_manifest_path"] = str(formal_freeze_path)
            selection_manifest["_manifest_sha256"] = sha256_file(formal_freeze_path)
    selected_ifc_entry_id = (
        _camel_selected_entry_id(selection_manifest)
        if condition_id == "camel_or_fides"
        else ""
    )
    evidence_entries = (
        [
            entry
            for entry in entries
            if str(entry.get("id", "")) == selected_ifc_entry_id
        ]
        if condition_id == "camel_or_fides"
        else entries
    )
    readiness_by_key = dependency_snapshot.get("readiness_by_key", {})
    snapshot_row = (
        readiness_by_key.get(condition_id, {})
        if isinstance(readiness_by_key, Mapping)
        else {}
    )
    requirements = [
        _requirement(
            "external_source_entries_present",
            bool(entries),
            [entry.get("id") for entry in entries],
        ),
        _requirement(
            "external_entries_result_eligible_true",
            bool(evidence_entries)
            and all(
                entry.get("result_eligible_for_formal_tables")
                for entry in evidence_entries
            ),
            {
                str(entry.get("id", "")): entry.get("result_eligible_for_formal_tables")
                for entry in entries
            },
        ),
        _requirement(
            "adapter_is_source_backed_not_stub_only",
            bool(adapter_manifest)
            and bool(evidence_entries)
            and all(
                _is_source_backed_adapter_status(
                    _entry_preflight_status(entry, adapter_manifest)
                )
                for entry in evidence_entries
            ),
            {
                "adapter_manifest_path": adapter_manifest.get("_manifest_path", ""),
                "adapter_manifest_status": adapter_manifest.get("status", ""),
                "adapter_classification": adapter_manifest.get("ipiguard", {}).get(
                    "adapter_classification", ""
                )
                if isinstance(adapter_manifest.get("ipiguard"), Mapping)
                else "",
                "by_entry": {
                    str(entry.get("id", "")): _entry_preflight_status(
                        entry,
                        adapter_manifest,
                    )
                    for entry in entries
                },
            },
        ),
        _requirement(
            "formal_manifest_and_complete_logs_declared",
            bool(condition.get("formal_manifest")) and bool(condition.get("complete_logs")),
            {
                "formal_manifest": condition.get("formal_manifest"),
                "complete_logs": condition.get("complete_logs"),
            },
        ),
        _requirement(
            "frozen_dependency_snapshot_declared",
            dependency_snapshot.get("status") == "completed"
            and bool(snapshot_row)
            and bool(snapshot_row.get("snapshot_ready")),
            {
                "snapshot_status": dependency_snapshot.get("status", "missing"),
                "registry_key_present": bool(snapshot_row),
                "snapshot_ready": snapshot_row.get("snapshot_ready"),
                "blockers": snapshot_row.get("blockers", []),
            },
        ),
    ]
    if condition_id == "camel_or_fides":
        selected = [
            entry
            for entry in entries
            if (
                str(entry.get("id", "")) == selected_ifc_entry_id
                and selection_manifest.get("method_selected")
            )
            or entry.get("current_status") == "ready"
            or entry.get("result_eligible_for_formal_tables")
        ]
        requirements.append(
            _requirement(
                "exactly_one_ifc_capability_method_selected",
                len(selected) == 1,
                {
                    "selected_entries": [entry.get("id") for entry in selected],
                    "selection_manifest_path": selection_manifest.get("_manifest_path", ""),
                    "selected_candidate": selection_manifest.get("config", {}).get(
                        "selected_candidate", ""
                    ),
                    "method_selected": selection_manifest.get("method_selected"),
                },
            )
        )
        requirements.append(
            _requirement(
                "unselected_ifc_methods_not_result_eligible",
                bool(selected_ifc_entry_id)
                and all(
                    not entry.get("result_eligible_for_formal_tables")
                    for entry in entries
                    if str(entry.get("id", "")) != selected_ifc_entry_id
                ),
                {
                    "selected_entry": selected_ifc_entry_id,
                    "unselected_entries": {
                        str(entry.get("id", "")): entry.get(
                            "result_eligible_for_formal_tables"
                        )
                        for entry in entries
                        if str(entry.get("id", "")) != selected_ifc_entry_id
                    },
                },
            )
        )
        requirements.append(
            _requirement(
                "selected_method_source_checkout_ready",
                len(selected) == 1
                and bool(selection_manifest.get("source_checkout_ready")),
                {
                    "selection_manifest_path": selection_manifest.get("_manifest_path", ""),
                    "selected_candidate": selection_manifest.get("config", {}).get(
                        "selected_candidate", ""
                    ),
                    "source_checkout_ready": selection_manifest.get("source_checkout_ready"),
                },
            )
        )
        adapter_snapshots = dependency_snapshot.get("adapter_preflight_snapshots", {})
        camel_snapshot = (
            adapter_snapshots.get("camel_or_fides", {})
            if isinstance(adapter_snapshots, Mapping)
            else {}
        )
        requirements.append(
            _requirement(
                "selected_method_source_smoke_completed",
                camel_snapshot.get("source_smoke_status")
                == "completed_source_smoke_only"
                and not camel_snapshot.get("source_smoke_network_calls")
                and not camel_snapshot.get("source_smoke_formal_result_eligible"),
                {
                    "source_smoke_path": camel_snapshot.get("source_smoke_path", ""),
                    "source_smoke_status": camel_snapshot.get("source_smoke_status", ""),
                    "source_smoke_passed_checks": camel_snapshot.get("source_smoke_passed_checks", 0),
                    "source_smoke_total_checks": camel_snapshot.get("source_smoke_total_checks", 0),
                    "source_smoke_network_calls": camel_snapshot.get("source_smoke_network_calls"),
                    "source_smoke_formal_result_eligible": camel_snapshot.get(
                        "source_smoke_formal_result_eligible"
                    ),
                },
            )
        )
    if condition_id == "ipiguard":
        adapter_snapshots = dependency_snapshot.get("adapter_preflight_snapshots", {})
        ipiguard_snapshot = (
            adapter_snapshots.get("ipiguard", {})
            if isinstance(adapter_snapshots, Mapping)
            else {}
        )
        requirements.append(
            _requirement(
                "official_source_smoke_completed",
                ipiguard_snapshot.get("source_smoke_status")
                == "completed_source_smoke_only"
                and not ipiguard_snapshot.get("source_smoke_formal_result_eligible"),
                {
                    "source_smoke_path": ipiguard_snapshot.get(
                        "source_smoke_path", ""
                    ),
                    "source_smoke_status": ipiguard_snapshot.get(
                        "source_smoke_status", ""
                    ),
                    "passed_checks": ipiguard_snapshot.get(
                        "source_smoke_passed_checks", 0
                    ),
                    "total_checks": ipiguard_snapshot.get(
                        "source_smoke_total_checks", 0
                    ),
                    "formal_result_eligible": ipiguard_snapshot.get(
                        "source_smoke_formal_result_eligible"
                    ),
                },
            )
        )
    return requirements


def _agentdojo_requirements(
    condition_id: str,
    condition: Mapping[str, Any],
    agentdojo_audit: Mapping[str, Any],
    dependency_snapshot: Mapping[str, Any],
) -> list[dict[str, Any]]:
    baseline = {}
    baselines = agentdojo_audit.get("baselines")
    if isinstance(baselines, Mapping):
        value = baselines.get(condition_id)
        if isinstance(value, Mapping):
            baseline = dict(value)
    return [
        _requirement(
            "agentdojo_capability_audit_completed",
            agentdojo_audit.get("status") == "completed",
            agentdojo_audit.get("status"),
        ),
        _requirement("agentdojo_baseline_entry_present", bool(baseline), list(baseline)),
        _requirement(
            "agentdojo_official_dependency_blockers_resolved",
            bool(baseline) and not baseline.get("dependency_blockers"),
            {
                "registry_status": condition.get("implementation_status"),
                "dependency_blockers": baseline.get("dependency_blockers"),
                "capability_status": baseline.get("capability_status"),
            },
        ),
        _requirement(
            "formal_manifest_and_complete_logs_declared",
            bool(condition.get("formal_manifest")) and bool(condition.get("complete_logs")),
            {
                "formal_manifest": condition.get("formal_manifest"),
                "complete_logs": condition.get("complete_logs"),
            },
        ),
        _requirement(
            "frozen_dependency_snapshot_declared",
            dependency_snapshot.get("status") == "completed",
            {
                "snapshot_status": dependency_snapshot.get("status", "missing"),
                "snapshot_version": dependency_snapshot.get("snapshot_version", ""),
            },
        ),
    ]


def _readiness_row(
    condition_id: str,
    condition: Mapping[str, Any],
    external_by_key: Mapping[str, list[dict[str, Any]]],
    agentdojo_audit: Mapping[str, Any],
    dependency_snapshot: Mapping[str, Any],
) -> dict[str, Any]:
    requirements = [
        _requirement("condition_present", bool(condition), condition_id),
        _requirement(
            "condition_marked_ready",
            condition.get("implementation_status") in FORMAL_ADMISSION_READY_STATUSES,
            condition.get("implementation_status"),
        ),
        _requirement("condition_result_eligible_true", _result_eligible(condition)),
        _requirement(
            "current_blockers_empty",
            not bool(condition.get("current_blockers")),
            condition.get("current_blockers", []),
        ),
        _requirement(
            "frozen_protocol_declared",
            bool(condition.get("formal_protocol")) or bool(condition.get("upstream_source")),
            {
                "formal_protocol": condition.get("formal_protocol"),
                "upstream_source": condition.get("upstream_source"),
            },
        ),
    ]
    if condition_id in EXTERNAL_STRONG_BASELINES:
        requirements.extend(
            _external_requirements(
                condition_id,
                condition,
                external_by_key,
                dependency_snapshot,
            )
        )
    if condition_id in AGENTDOJO_OFFICIAL_STRONG_BASELINES:
        requirements.extend(
            _agentdojo_requirements(
                condition_id,
                condition,
                agentdojo_audit,
                dependency_snapshot,
            )
        )

    failed = [item for item in requirements if not item["passed"]]
    return {
        "id": condition_id,
        "display_name": condition.get("display_name", condition_id),
        "family": condition.get("family"),
        "implementation_status": condition.get("implementation_status"),
        "result_eligible": _result_eligible(condition),
        "formal_admission_status": "formal_ready" if not failed else "blocked_or_diagnostic",
        "failed_requirements": [item["name"] for item in failed],
        "requirements": requirements,
        "current_blockers": condition.get("current_blockers", []),
        "formal_exclusion_rule": condition.get("formal_exclusion_rule", ""),
    }


def _build_readiness_rows(
    baseline_registry: Mapping[str, Any],
    external_registry: Mapping[str, Any],
    agentdojo_audit: Mapping[str, Any],
    dependency_snapshot: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    index = _condition_index(baseline_registry)
    external_by_key = _external_entries_by_key(external_registry)
    return {
        condition_id: _readiness_row(
            condition_id,
            index.get(condition_id, {}),
            external_by_key,
            agentdojo_audit,
            dependency_snapshot,
        )
        for condition_id in sorted(REQUIRED_STRONG_BASELINES)
    }


def _audit_checks(
    baseline_registry: Mapping[str, Any],
    readiness_rows: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    index = _condition_index(baseline_registry)
    missing = sorted(REQUIRED_STRONG_BASELINES - set(index))
    formal_ready = [
        key
        for key, row in readiness_rows.items()
        if row.get("formal_admission_status") == "formal_ready"
    ]
    blocked_or_pending_eligible = [
        key
        for key in REQUIRED_STRONG_BASELINES
        if key in index
        and index[key].get("implementation_status") not in FORMAL_ADMISSION_READY_STATUSES
        and _result_eligible(index[key])
    ]
    blocked_without_exclusion = [
        key
        for key in REQUIRED_STRONG_BASELINES
        if key in index
        and index[key].get("implementation_status") not in FORMAL_ADMISSION_READY_STATUSES
        and not index[key].get("formal_exclusion_rule")
    ]
    blocked_without_blockers = [
        key
        for key in REQUIRED_STRONG_BASELINES
        if key in index
        and index[key].get("implementation_status") not in FORMAL_ADMISSION_READY_STATUSES
        and not index[key].get("current_blockers")
    ]
    camel_failed = readiness_rows.get("camel_or_fides", {}).get("failed_requirements", [])
    gate = baseline_registry.get("q2_gate_minimum_strong_baselines", {})
    minimum = int(gate.get("minimum_exact_or_disclosed_exclusion_count", 5))
    expected_gate = "satisfied" if len(formal_ready) >= minimum else "not_satisfied"
    return [
        _check("all_required_strong_baselines_present", not missing, detail=missing),
        _check(
            "blocked_or_pending_strong_baselines_not_result_eligible",
            not blocked_or_pending_eligible,
            detail=blocked_or_pending_eligible,
        ),
        _check(
            "blocked_or_pending_strong_baselines_have_exclusion_rules",
            not blocked_without_exclusion,
            detail=blocked_without_exclusion,
        ),
        _check(
            "blocked_or_pending_strong_baselines_have_current_blockers",
            not blocked_without_blockers,
            detail=blocked_without_blockers,
        ),
        _check(
            "no_formal_ready_baseline_without_all_admission_requirements",
            all(not row.get("failed_requirements") for row in readiness_rows.values() if row.get("formal_admission_status") == "formal_ready"),
            detail=formal_ready,
        ),
        _check(
            "camel_or_fides_not_admitted_without_formal_adapter",
            bool(camel_failed)
            and (
                "adapter_is_source_backed_not_stub_only" in camel_failed
                or "formal_manifest_and_complete_logs_declared" in camel_failed
                or "condition_result_eligible_true" in camel_failed
            ),
            severity="warning",
            detail=camel_failed,
        ),
        _check(
            "q2_gate_matches_formal_ready_count",
            gate.get("current_gate_status") == expected_gate,
            severity="warning",
            detail={
                "registry_gate": gate.get("current_gate_status"),
                "formal_ready": formal_ready,
                "formal_ready_count": len(formal_ready),
                "minimum_required": minimum,
                "expected_gate": expected_gate,
            },
        ),
    ]


def _write_markdown(path: Path, audit: Mapping[str, Any]) -> None:
    lines = [
        "# Strong-baseline formal-readiness audit v1",
        "",
        f"Generated: {audit['created_at']}",
        "",
        "## Result",
        "",
        f"- Status: `{audit['status']}`",
        f"- Passed checks: {audit['passed_checks']}/{audit['total_checks']}",
        f"- Q2 strong-baseline gate: `{audit['q2_strong_baseline_gate']}`",
        f"- Formal-ready strong baselines: {', '.join(audit['formal_ready_strong_baselines']) or 'none'}",
        f"- Result eligible for formal tables: `{audit['result_eligible_for_formal_tables']}`",
        f"- Dependency snapshot status: `{audit['dependency_snapshot_status']}`",
        f"- Dependency snapshot SHA-256: `{audit['dependency_snapshot_sha256']}`",
        "",
        "## Formal admission rows",
        "",
        "| Baseline | Status | Formal admission | Failed requirements |",
        "|---|---|---|---|",
    ]
    for row in audit["readiness_rows"].values():
        failed = ", ".join(f"`{item}`" for item in row["failed_requirements"]) or "none"
        lines.append(
            f"| `{row['id']}` | `{row['implementation_status']}` | "
            f"`{row['formal_admission_status']}` | {failed} |"
        )
    lines.extend(["", "## Checks", "", "| Check | Status | Severity | Detail |", "|---|---|---|---|"])
    for check in audit["checks"]:
        detail = json.dumps(check.get("detail"), ensure_ascii=False, sort_keys=True)
        if len(detail) > 220:
            detail = detail[:217] + "..."
        lines.append(
            f"| `{check['name']}` | `{check['status']}` | `{check['severity']}` | {detail.replace('|', '\\|')} |"
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            audit["boundary"],
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def build_strong_baseline_formal_readiness_audit(
    *,
    baseline_registry_path: Path = DEFAULT_BASELINE_REGISTRY,
    external_registry_path: Path = DEFAULT_EXTERNAL_REGISTRY,
    agentdojo_audit_path: Path = DEFAULT_AGENTDOJO_AUDIT,
    dependency_snapshot_path: Path = DEFAULT_DEPENDENCY_SNAPSHOT,
    output_dir: Path = DEFAULT_OUTPUT,
) -> dict[str, Any]:
    baseline_registry_path = baseline_registry_path.resolve()
    external_registry_path = external_registry_path.resolve()
    agentdojo_audit_path = agentdojo_audit_path.resolve()
    dependency_snapshot_path = dependency_snapshot_path.resolve()
    output_dir = output_dir.resolve()
    baseline_registry = _read_json(baseline_registry_path)
    external_registry = _read_json(external_registry_path)
    agentdojo_audit = _read_optional_json(agentdojo_audit_path)
    dependency_snapshot = _read_optional_json(dependency_snapshot_path)
    readiness_rows = portable_value(
        _build_readiness_rows(
            baseline_registry,
            external_registry,
            agentdojo_audit,
            dependency_snapshot,
        ),
        root=ROOT,
    )
    checks = portable_value(_audit_checks(baseline_registry, readiness_rows), root=ROOT)
    error_failures = [
        check
        for check in checks
        if check["status"] != "pass" and check.get("severity") == "error"
    ]
    passed = sum(1 for check in checks if check["status"] == "pass")
    formal_ready = [
        key
        for key, row in readiness_rows.items()
        if row.get("formal_admission_status") == "formal_ready"
    ]
    audit = {
        "schema_version": "paper-strong-baseline-formal-readiness-audit-1.0",
        "audit_version": AUDIT_VERSION,
        "status": "completed" if not error_failures else "failed",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "baseline_registry_path": portable_path(baseline_registry_path, root=ROOT),
        "baseline_registry_sha256": sha256_file(baseline_registry_path),
        "external_registry_path": portable_path(external_registry_path, root=ROOT),
        "external_registry_sha256": sha256_file(external_registry_path),
        "agentdojo_audit_path": portable_path(agentdojo_audit_path, root=ROOT),
        "agentdojo_audit_sha256": sha256_file(agentdojo_audit_path)
        if agentdojo_audit_path.exists()
        else "",
        "dependency_snapshot_path": portable_path(dependency_snapshot_path, root=ROOT),
        "dependency_snapshot_sha256": sha256_file(dependency_snapshot_path)
        if dependency_snapshot_path.exists()
        else "",
        "dependency_snapshot_status": dependency_snapshot.get("status", "missing"),
        "required_strong_baselines": sorted(REQUIRED_STRONG_BASELINES),
        "formal_ready_strong_baselines": sorted(formal_ready),
        "readiness_rows": readiness_rows,
        "readiness_rows_sha256": rows_sha256(readiness_rows.values()),
        "q2_strong_baseline_gate": "not_satisfied",
        "result_eligible_for_formal_tables": False,
        "checks": checks,
        "checks_sha256": rows_sha256(checks),
        "total_checks": len(checks),
        "passed_checks": passed,
        "error_failures": error_failures,
        "boundary": (
            "Formal-admission audit only. A strong baseline may enter paper "
            "result tables only after source-backed adapters, frozen dependency "
            "snapshots, formal manifests, complete logs and no-label-leakage "
            "checks exist. Current stub preflights remain outside formal effect "
            "claims."
        ),
    }
    json_path = output_dir / f"{AUDIT_STEM}.json"
    md_path = output_dir / f"{AUDIT_STEM}.md"
    _write_json(json_path, audit)
    _write_markdown(md_path, audit)
    audit["json_path"] = portable_path(json_path, root=ROOT)
    audit["markdown_path"] = portable_path(md_path, root=ROOT)
    return audit


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-registry", type=Path, default=DEFAULT_BASELINE_REGISTRY)
    parser.add_argument("--external-registry", type=Path, default=DEFAULT_EXTERNAL_REGISTRY)
    parser.add_argument("--agentdojo-audit", type=Path, default=DEFAULT_AGENTDOJO_AUDIT)
    parser.add_argument("--dependency-snapshot", type=Path, default=DEFAULT_DEPENDENCY_SNAPSHOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    audit = build_strong_baseline_formal_readiness_audit(
        baseline_registry_path=args.baseline_registry,
        external_registry_path=args.external_registry,
        agentdojo_audit_path=args.agentdojo_audit,
        dependency_snapshot_path=args.dependency_snapshot,
        output_dir=args.output_dir,
    )
    print(json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
