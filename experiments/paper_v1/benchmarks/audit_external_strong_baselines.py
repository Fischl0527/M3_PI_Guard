"""Audit external strong-baseline source/readiness records for paper-v1.

This audit is intentionally non-experimental.  It checks whether the source
registry for PromptGuard, Task Shield, IPIGuard, Progent and CaMeL/FIDES is
complete enough to guide future formal baseline work, while keeping all blocked
or unadapted methods out of paper result tables.

The script does not clone repositories, install packages, download models, call
LLMs or run baselines.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .common import huggingface_model_cache_probe, portable_value, rows_sha256, sha256_file


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REGISTRY = ROOT / "protocols" / "paper_upgrade_v1" / "external_strong_baselines_v1.json"
DEFAULT_OUTPUT = ROOT / "protocols" / "paper_upgrade_v1"
DEFAULT_SOURCE_CHECKOUT_MANIFEST = (
    ROOT / "protocols" / "paper_upgrade_v1" / "strong_baseline_source_checkout_manifest_v1.json"
)
AUDIT_VERSION = "m3-paper-v1-external-strong-baseline-source-audit-1.0"
AUDIT_STEM = "external_strong_baseline_source_audit_v1"

REQUIRED_REGISTRY_KEYS = {
    "promptguard",
    "task_shield",
    "ipiguard",
    "progent",
    "camel_or_fides",
}
REQUIRED_ENTRY_FIELDS = {
    "id",
    "registry_key",
    "display_name",
    "baseline_family",
    "primary_reference",
    "minimum_adapter_requirements",
    "current_status",
    "current_blockers",
    "formal_exclusion_rule",
    "result_eligible_for_formal_tables",
}
PROMPTGUARD_MODEL_IDS = (
    "meta-llama/Llama-Prompt-Guard-2-86M",
    "meta-llama/Llama-Prompt-Guard-2-22M",
)
CHECKOUT_PROBE_TO_ENTRY_ID = {
    "promptguard_purplellama": "promptguard_llama_prompt_guard_2",
    "ipiguard": "ipiguard_github_emnlp2025",
    "progent": "progent_arxiv2025",
    "camel": "camel_google_research",
    "fides": "fides_microsoft",
}


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


def _entries(registry: Mapping[str, Any]) -> list[dict[str, Any]]:
    entries = registry.get("entries")
    if not isinstance(entries, list):
        raise ValueError("external baseline registry missing entries list")
    return [dict(row) for row in entries if isinstance(row, Mapping)]


def _reference_urls(row: Mapping[str, Any]) -> list[str]:
    urls: list[str] = []
    primary = row.get("primary_reference")
    if isinstance(primary, Mapping) and primary.get("url"):
        urls.append(str(primary["url"]))
    secondary = row.get("secondary_references")
    if isinstance(secondary, list):
        for item in secondary:
            if isinstance(item, Mapping) and item.get("url"):
                urls.append(str(item["url"]))
    return urls


def _has_remote_head(row: Mapping[str, Any]) -> bool:
    secondary = row.get("secondary_references")
    if not isinstance(secondary, list):
        return False
    return any(
        isinstance(item, Mapping)
        and item.get("kind") == "repository"
        and bool(item.get("remote_head_sha"))
        for item in secondary
    )


def _dependency_probe(*, hf_hub_cache: Path | None = None) -> dict[str, Any]:
    return {
        "python_executable": sys.executable,
        "python_version": sys.version.split()[0],
        "transformers_installed": importlib.util.find_spec("transformers") is not None,
        "torch_installed": importlib.util.find_spec("torch") is not None,
        "huggingface_hub_installed": importlib.util.find_spec("huggingface_hub") is not None,
        "openai_installed": importlib.util.find_spec("openai") is not None,
        "uv_executable": shutil.which("uv") or "",
        "promptguard_model_cache": {
            model_id: huggingface_model_cache_probe(model_id, hub_cache=hf_hub_cache)
            for model_id in PROMPTGUARD_MODEL_IDS
        },
        "external_baseline_checkouts": {
            "promptguard_purplellama": (ROOT / "external" / "baselines" / "PurpleLlama").exists(),
            "ipiguard": (ROOT / "external" / "baselines" / "ipiguard").exists(),
            "progent": (ROOT / "external" / "baselines" / "progent").exists(),
            "camel": (ROOT / "external" / "baselines" / "camel-prompt-injection").exists(),
            "fides": (ROOT / "external" / "baselines" / "fides").exists(),
        },
    }


def _entry_summary(entries: list[dict[str, Any]]) -> dict[str, Any]:
    by_key: dict[str, list[str]] = {}
    status_counts: dict[str, int] = {}
    remote_head_entries: list[str] = []
    paper_only_entries: list[str] = []
    for row in entries:
        key = str(row.get("registry_key", ""))
        by_key.setdefault(key, []).append(str(row.get("id", "")))
        status = str(row.get("current_status", ""))
        status_counts[status] = status_counts.get(status, 0) + 1
        if _has_remote_head(row):
            remote_head_entries.append(str(row.get("id", "")))
        else:
            paper_only_entries.append(str(row.get("id", "")))
    return {
        "entry_count": len(entries),
        "entries_by_registry_key": {key: sorted(ids) for key, ids in sorted(by_key.items())},
        "status_counts": status_counts,
        "entries_with_remote_repository_head": sorted(remote_head_entries),
        "paper_or_model_card_only_entries": sorted(paper_only_entries),
    }


def _manifest_ready_entries(source_checkout_manifest: Mapping[str, Any]) -> set[str]:
    ready = source_checkout_manifest.get("source_ready_entries")
    if isinstance(ready, list):
        return {str(item) for item in ready}
    entries = source_checkout_manifest.get("entries")
    if not isinstance(entries, list):
        return set()
    return {
        str(row.get("entry_id", ""))
        for row in entries
        if isinstance(row, Mapping) and row.get("source_checkout_ready")
    }


def _local_checkouts_are_manifested(
    probe: Mapping[str, Any],
    source_checkout_manifest: Mapping[str, Any],
) -> tuple[bool, dict[str, Any]]:
    present = {
        key: bool(value)
        for key, value in probe.get("external_baseline_checkouts", {}).items()
        if bool(value)
    }
    ready_entries = _manifest_ready_entries(source_checkout_manifest)
    unrecorded = {
        key: CHECKOUT_PROBE_TO_ENTRY_ID.get(key, "")
        for key in present
        if CHECKOUT_PROBE_TO_ENTRY_ID.get(key, "") not in ready_entries
    }
    return not unrecorded, {
        "present_checkouts": present,
        "source_checkout_manifest_status": source_checkout_manifest.get("status", "missing"),
        "ready_entries": sorted(ready_entries),
        "unrecorded_present_checkouts": unrecorded,
    }


def _audit_entries(
    registry: Mapping[str, Any],
    probe: Mapping[str, Any],
    source_checkout_manifest: Mapping[str, Any],
) -> list[dict[str, Any]]:
    entries = _entries(registry)
    ids = [str(row.get("id", "")) for row in entries]
    keys = {str(row.get("registry_key", "")) for row in entries}
    formal_entries = [
        row for row in entries if bool(row.get("result_eligible_for_formal_tables"))
    ]
    blocked_entries = [
        row for row in entries if not bool(row.get("result_eligible_for_formal_tables"))
    ]
    promptguard_entry = next(
        (row for row in entries if row.get("registry_key") == "promptguard"),
        {},
    )
    promptguard_blockers = " ".join(
        str(item).casefold()
        for item in promptguard_entry.get("current_blockers", [])
    )
    promptguard_cache_ready = any(
        item.get("model_cache_complete")
        for item in probe.get("promptguard_model_cache", {}).values()
        if isinstance(item, Mapping)
    )
    promptguard_dependencies_ready = bool(
        probe.get("transformers_installed") and promptguard_cache_ready
    )
    stale_promptguard_blocker_markers = (
        "gated",
        "not cached",
        "no model weights",
        "transformers missing",
        "transformers is not installed",
    )
    promptguard_probe_matches_registry = bool(
        (
            promptguard_entry.get("result_eligible_for_formal_tables")
            and promptguard_entry.get("formal_result", {}).get("status")
            == "completed_source_backed_formal_detector_baseline"
        )
        or (
            promptguard_entry.get("current_blockers")
            and (
            not promptguard_dependencies_ready
            or not any(
                marker in promptguard_blockers
                for marker in stale_promptguard_blocker_markers
            )
            )
        )
    )
    checks: list[dict[str, Any]] = [
        _check("unique_entry_ids", len(ids) == len(set(ids)), detail=ids),
        _check(
            "required_registry_keys_covered",
            REQUIRED_REGISTRY_KEYS <= keys,
            detail={"missing": sorted(REQUIRED_REGISTRY_KEYS - keys), "present": sorted(keys)},
        ),
        _check(
            "entry_required_fields_present",
            all(REQUIRED_ENTRY_FIELDS <= set(row) for row in entries),
            detail={
                row.get("id", ""): sorted(REQUIRED_ENTRY_FIELDS - set(row))
                for row in entries
                if not REQUIRED_ENTRY_FIELDS <= set(row)
            },
        ),
        _check(
            "all_entries_have_primary_reference_url",
            all(
                isinstance(row.get("primary_reference"), Mapping)
                and bool(row["primary_reference"].get("url"))
                for row in entries
            ),
            detail={row.get("id", ""): _reference_urls(row) for row in entries},
        ),
        _check(
            "all_entries_have_blockers_plans_and_exclusion_rules",
            all(
                row.get("minimum_adapter_requirements")
                and (
                    bool(row.get("current_blockers") and row.get("formal_exclusion_rule"))
                    or bool(row.get("formal_result"))
                )
                for row in entries
            ),
            detail=[
                row.get("id", "")
                for row in entries
                if not (
                    row.get("minimum_adapter_requirements")
                    and (
                        bool(row.get("current_blockers") and row.get("formal_exclusion_rule"))
                        or bool(row.get("formal_result"))
                    )
                )
            ],
        ),
        _check(
            "blocked_entries_not_result_eligible",
            all(not bool(row.get("result_eligible_for_formal_tables")) for row in blocked_entries),
            detail={
                row.get("id", ""): row.get("result_eligible_for_formal_tables")
                for row in blocked_entries
            },
        ),
        _check(
            "formal_entries_have_detector_scope_and_artifacts",
            all(
                row.get("formal_result", {}).get("status")
                == "completed_source_backed_formal_detector_baseline"
                and "detector_performance" in row.get("formal_result", {}).get(
                    "eligible_table_scope", []
                )
                and bool(row.get("formal_result", {}).get("analysis_manifest"))
                and bool(row.get("formal_result", {}).get("run_manifest"))
                and bool(row.get("formal_result", {}).get("complete_logs"))
                for row in formal_entries
            ),
            detail={
                row.get("id", ""): row.get("formal_result", {}) for row in formal_entries
            },
        ),
        _check(
            "promptguard_dependency_blockers_match_probe",
            promptguard_probe_matches_registry,
            severity="warning",
            detail={
                "transformers_installed": probe.get("transformers_installed"),
                "dependencies_ready": promptguard_dependencies_ready,
                "stale_dependency_blocker_present": any(
                    marker in promptguard_blockers
                    for marker in stale_promptguard_blocker_markers
                ),
                "promptguard_model_cache": probe.get("promptguard_model_cache"),
            },
        ),
        _check(
            "camel_or_fides_has_two_candidates",
            len([row for row in entries if row.get("registry_key") == "camel_or_fides"]) >= 2,
            severity="warning",
            detail=[
                row.get("id")
                for row in entries
                if row.get("registry_key") == "camel_or_fides"
            ],
        ),
        _check(
            "code_candidates_have_remote_head_or_are_declared_paper_only",
            all(
                _has_remote_head(row)
                or row.get("current_status") in {
                    "blocked_no_runnable_code_pinned",
                    "blocked_no_official_code_pinned",
                    "blocked_missing_transformers_dependency_and_model_cache",
                    "adapter_preflight_ready_reproduction_semantics_blocked",
                    "adapter_preflight_ready_dsl_semantics_blocked",
                    "disclosed_paper_reproduction_runner_analyzer_implemented_qualification_pending",
                    "disclosed_paper_reproduction_v1_2_hash_bound_runner_analyzer_implemented_qualification_pending",
                    "disclosed_paper_reproduction_v1_3_qualification_completed_formal_running",
                    "disclosed_paper_reproduction_v1_3_formal_running_failed_case_present",
                    "disclosed_paper_reproduction_v1_4_failure_recovery_protocol_prepared_qualification_pending",
                    "disclosed_paper_reproduction_v1_4_qualification_completed_formal_running",
                    "disclosed_paper_reproduction_v1_4_formal_running_failed_case_present",
                }
                for row in entries
            ),
            detail={row.get("id", ""): _has_remote_head(row) for row in entries},
        ),
    ]
    manifested, manifest_detail = _local_checkouts_are_manifested(
        probe,
        source_checkout_manifest,
    )
    checks.append(
        _check(
            "local_checkouts_absent_or_recorded_in_source_manifest",
            manifested,
            severity="warning",
            detail=manifest_detail,
        )
    )
    return checks


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_markdown(path: Path, audit: Mapping[str, Any]) -> None:
    lines = [
        "# External strong-baseline source audit v1",
        "",
        f"Generated: {audit['created_at']}",
        "",
        "## Result",
        "",
        f"- Status: `{audit['status']}`",
        f"- Passed checks: {audit['passed_checks']}/{audit['total_checks']}",
        f"- Q2 strong-baseline gate: `{audit['q2_strong_baseline_gate']}`",
        f"- Formal result eligible: `{audit['result_eligible_for_formal_tables']}`",
        f"- Source checkout manifest status: `{audit['source_checkout_manifest_status']}`",
        "",
        "## Baselines covered",
        "",
        "| Registry key | Entries |",
        "|---|---|",
    ]
    for key, ids in audit["summary"]["entries_by_registry_key"].items():
        lines.append(f"| `{key}` | {', '.join('`' + item + '`' for item in ids)} |")
    lines.extend(
        [
            "",
            "## Dependency probe",
            "",
        ]
    )
    for key, value in audit["dependency_probe"].items():
        if isinstance(value, dict):
            value = json.dumps(value, ensure_ascii=False, sort_keys=True)
        lines.append(f"- `{key}`: {value}")
    lines.extend(
        [
            "",
            "## Entry statuses",
            "",
            "| Entry | Status | Primary reference | Result eligible |",
            "|---|---|---|---|",
        ]
    )
    for row in audit["entries"]:
        reference = row["primary_reference"]["url"]
        lines.append(
            f"| `{row['id']}` | `{row['current_status']}` | {reference} | "
            f"`{row['result_eligible_for_formal_tables']}` |"
        )
    lines.extend(
        [
            "",
            "## Checks",
            "",
            "| Check | Status | Severity | Detail |",
            "|---|---|---|---|",
        ]
    )
    for check in audit["checks"]:
        detail = json.dumps(check.get("detail"), ensure_ascii=False, sort_keys=True)
        if len(detail) > 220:
            detail = detail[:217] + "..."
        detail = detail.replace("|", "\\|")
        lines.append(
            f"| `{check['name']}` | `{check['status']}` | `{check['severity']}` | {detail} |"
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


def build_external_strong_baseline_audit(
    *,
    registry_path: Path = DEFAULT_REGISTRY,
    source_checkout_manifest_path: Path = DEFAULT_SOURCE_CHECKOUT_MANIFEST,
    output_dir: Path = DEFAULT_OUTPUT,
    hf_hub_cache: Path | None = None,
) -> dict[str, Any]:
    registry_path = registry_path.resolve()
    source_checkout_manifest_path = source_checkout_manifest_path.resolve()
    output_dir = output_dir.resolve()
    registry = _read_json(registry_path)
    entries = _entries(registry)
    probe = _dependency_probe(hf_hub_cache=hf_hub_cache)
    source_checkout_manifest = _read_optional_json(source_checkout_manifest_path)
    checks = _audit_entries(registry, probe, source_checkout_manifest)
    error_failures = [
        check
        for check in checks
        if check["status"] != "pass" and check.get("severity") == "error"
    ]
    passed = sum(1 for check in checks if check["status"] == "pass")
    audit = {
        "schema_version": "paper-external-strong-baseline-source-audit-1.0",
        "audit_version": AUDIT_VERSION,
        "status": "completed" if not error_failures else "failed",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "registry_path": str(registry_path),
        "registry_sha256": sha256_file(registry_path),
        "source_checkout_manifest_path": str(source_checkout_manifest_path),
        "source_checkout_manifest_sha256": sha256_file(source_checkout_manifest_path)
        if source_checkout_manifest_path.exists()
        else "",
        "source_checkout_manifest_status": source_checkout_manifest.get("status", "missing"),
        "required_registry_keys": sorted(REQUIRED_REGISTRY_KEYS),
        "dependency_probe": probe,
        "summary": _entry_summary(entries),
        "entries": entries,
        "entries_sha256": rows_sha256(entries),
        "checks": checks,
        "checks_sha256": rows_sha256(checks),
        "total_checks": len(checks),
        "passed_checks": passed,
        "error_failures": error_failures,
        "q2_strong_baseline_gate": "not_satisfied",
        "result_eligible_for_formal_tables": False,
        "boundary": (
            "Source/readiness audit only. External baselines remain blocked or "
            "diagnostic until exact source, dependencies, adapters, frozen "
            "manifests and complete logs exist; entries with a declared formal "
            "result are eligible only for their explicitly recorded table scope."
        ),
    }
    json_path = output_dir / f"{AUDIT_STEM}.json"
    md_path = output_dir / f"{AUDIT_STEM}.md"
    audit["json_path"] = str(json_path)
    audit["markdown_path"] = str(md_path)
    audit = portable_value(audit, root=ROOT)
    _write_json(json_path, audit)
    _write_markdown(md_path, audit)
    return audit


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument(
        "--source-checkout-manifest",
        type=Path,
        default=DEFAULT_SOURCE_CHECKOUT_MANIFEST,
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--hf-hub-cache", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    audit = build_external_strong_baseline_audit(
        registry_path=args.registry,
        source_checkout_manifest_path=args.source_checkout_manifest,
        output_dir=args.output_dir,
        hf_hub_cache=args.hf_hub_cache,
    )
    print(json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
