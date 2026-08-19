"""Audit frontier API model-slot readiness without making network calls.

Q2-grade evidence requires two different frontier API vendors in addition to
local open models.  This audit checks the local, ignored configuration for
provider readiness while preserving two boundaries:

* it never prints credential values;
* it never calls external APIs or uploads benchmark content.

Passing this audit is only a pre-network-smoke gate.  A provider becomes a
formal model slot only after explicit user consent, provider smoke, frozen
model metadata, complete run manifests and model-registry admission.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from m3_core.project_config import (
    is_placeholder,
    parse_env_file,
    redacted_config,
    resolve_config_path,
)
from scripts.check_project_config import tracked_secret_hits

from .common import portable_path, rows_sha256, sha256_file


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = ROOT / "protocols" / "paper_upgrade_v1"
DEFAULT_MODEL_REGISTRY = DEFAULT_OUTPUT / "model_registry_v2.json"
DEFAULT_SMOKE_MANIFEST = (
    ROOT / "outputs" / "paper_upgrade_v1" / "frontier_api_smoke_v1" / "manifest.json"
)
DEFAULT_REGISTRY_ADMISSION = DEFAULT_OUTPUT / "frontier_api_model_slot_registry_admission_v1.json"
FRONTIER_CLIENT = ROOT / "experiments" / "paper_v1" / "frontier_client.py"
AUDIT_STEM = "frontier_api_model_slot_admission_audit_v1"
AUDIT_VERSION = "m3-paper-v1-frontier-api-model-slot-admission-audit-1.0"
CONSENT_VALUE = "yes_for_network_smoke"
REQUIRED_VENDOR_COUNT = 2
PROVIDERS = {
    "openai": {
        "api_key": "OPENAI_API_KEY",
        "model_id": "FRONTIER_OPENAI_MODEL_ID",
        "base_url": "FRONTIER_OPENAI_BASE_URL",
    },
    "anthropic": {
        "api_key": "ANTHROPIC_API_KEY",
        "model_id": "FRONTIER_ANTHROPIC_MODEL_ID",
        "base_url": "FRONTIER_ANTHROPIC_BASE_URL",
    },
}


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def _git_ignore_status(path: Path) -> dict[str, Any]:
    try:
        relative = path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return {"inside_repository": False, "ignored": None, "tracked": None}
    ignored = subprocess.run(
        ["git", "check-ignore", "--quiet", "--", relative],
        cwd=ROOT,
        check=False,
    ).returncode == 0
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "--", relative],
        cwd=ROOT,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode == 0
    return {"inside_repository": True, "ignored": ignored, "tracked": tracked}


def _path(path: Path) -> str:
    return portable_path(path, root=ROOT)


def _check(name: str, passed: bool, detail: Any = None, *, severity: str = "error") -> dict[str, Any]:
    return {
        "name": name,
        "status": "pass" if passed else "fail",
        "severity": severity,
        "detail": detail,
    }


def _provider_rows(values: Mapping[str, str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for provider, fields in PROVIDERS.items():
        api_key_field = str(fields["api_key"])
        model_field = str(fields["model_id"])
        base_url_field = str(fields["base_url"])
        api_key_present = not is_placeholder(values.get(api_key_field))
        model_id_present = not is_placeholder(values.get(model_field))
        base_url_configured = not is_placeholder(values.get(base_url_field))
        missing = [
            field
            for field, present in [
                (api_key_field, api_key_present),
                (model_field, model_id_present),
            ]
            if not present
        ]
        rows.append(
            {
                "provider": provider,
                "api_key_field": api_key_field,
                "api_key_status": "set_redacted" if api_key_present else "missing_or_placeholder",
                "model_id_field": model_field,
                "model_id": values.get(model_field, "") if model_id_present else "",
                "base_url_field": base_url_field,
                "base_url_configured": base_url_configured,
                "configured_for_network_smoke": api_key_present and model_id_present,
                "missing_fields": missing,
                "formal_slot_status": (
                    "configured_pending_explicit_network_smoke"
                    if api_key_present and model_id_present
                    else "blocked_missing_local_config"
                ),
            }
        )
    return rows


def _frontier_models_in_registry(model_registry: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = model_registry.get("models", [])
    if not isinstance(rows, list):
        return []
    return [
        dict(row)
        for row in rows
        if isinstance(row, Mapping) and row.get("role") == "frontier_api_vendor"
    ]


def _select_registered_model_registry(
    *,
    base_registry_path: Path,
    registry_admission_path: Path,
) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    base_registry = _read_json(base_registry_path)
    admission = _read_json(registry_admission_path)
    candidate_path = Path(str(admission.get("output_registry_path", "")))
    if candidate_path and not candidate_path.is_absolute():
        candidate_path = ROOT / candidate_path
    candidate_sha = str(admission.get("output_registry_sha256", ""))
    candidate_ok = (
        admission.get("status") == "admitted_registry_candidate"
        and admission.get("output_registry_written") is True
        and candidate_path.is_file()
        and bool(candidate_sha)
        and sha256_file(candidate_path) == candidate_sha
    )
    if candidate_ok:
        return (
            candidate_path.resolve(),
            _read_json(candidate_path),
            {
                "selected_model_registry_path": _path(candidate_path),
                "selection_reason": "admitted_frontier_registry_candidate",
                "base_model_registry_path": _path(base_registry_path),
                "registry_admission_path": _path(registry_admission_path),
                "registry_admission_status": admission.get("status", ""),
                "registry_admission_sha256": sha256_file(registry_admission_path),
            },
        )
    return (
        base_registry_path.resolve(),
        base_registry,
        {
            "selected_model_registry_path": _path(base_registry_path),
            "selection_reason": "base_registry_no_admitted_frontier_candidate",
            "base_model_registry_path": _path(base_registry_path),
            "registry_admission_path": _path(registry_admission_path),
            "registry_admission_status": admission.get("status", ""),
            "registry_admission_sha256": sha256_file(registry_admission_path)
            if registry_admission_path.exists()
            else "",
        },
    )


def build_frontier_api_model_slot_audit(
    *,
    config_path: Path | None = None,
    model_registry_path: Path = DEFAULT_MODEL_REGISTRY,
    registry_admission_path: Path = DEFAULT_REGISTRY_ADMISSION,
    smoke_manifest_path: Path = DEFAULT_SMOKE_MANIFEST,
    output_dir: Path = DEFAULT_OUTPUT,
) -> dict[str, Any]:
    resolved_config = resolve_config_path(config_path)
    output_dir = output_dir.resolve()
    model_registry_path = model_registry_path.resolve()
    registry_admission_path = registry_admission_path.resolve()
    smoke_manifest_path = smoke_manifest_path.resolve()
    values: dict[str, str] = {}
    config_errors: list[str] = []
    if resolved_config.exists():
        values = parse_env_file(resolved_config)
    else:
        config_errors.append("project local configuration file is missing")
    redacted = redacted_config(values)
    git_status = _git_ignore_status(resolved_config)
    secret_hits = tracked_secret_hits(values, root=ROOT) if values else []
    provider_rows = _provider_rows(values)
    configured_vendors = [
        row["provider"] for row in provider_rows if row["configured_for_network_smoke"]
    ]
    consent = str(values.get("M3_FRONTIER_API_CONSENT", "")).strip()
    explicit_network_consent = consent == CONSENT_VALUE
    selected_registry_path, model_registry, registry_selection = _select_registered_model_registry(
        base_registry_path=model_registry_path,
        registry_admission_path=registry_admission_path,
    )
    smoke_manifest = _read_json(smoke_manifest_path)
    registered_frontier_models = _frontier_models_in_registry(model_registry)
    registered_vendor_ids = sorted(
        {
            str(row.get("provider", row.get("family", row.get("id", ""))))
            for row in registered_frontier_models
        }
    )
    checks = [
        _check("local_config_exists", resolved_config.exists(), _path(resolved_config)),
        _check(
            "local_config_ignored_and_untracked",
            bool(git_status.get("inside_repository"))
            and bool(git_status.get("ignored"))
            and not bool(git_status.get("tracked")),
            git_status,
        ),
        _check("tracked_files_do_not_contain_configured_secrets", not secret_hits, secret_hits),
        _check(
            "two_distinct_vendors_configured_for_network_smoke",
            len(configured_vendors) >= REQUIRED_VENDOR_COUNT,
            configured_vendors,
        ),
        _check(
            "explicit_network_smoke_consent_recorded",
            explicit_network_consent,
            {
                "field": "M3_FRONTIER_API_CONSENT",
                "expected_value": CONSENT_VALUE,
                "current_status": "set" if consent else "missing_or_placeholder",
            },
            severity="warning",
        ),
        _check(
            "model_registry_has_two_frontier_api_vendor_slots",
            len(registered_frontier_models) >= REQUIRED_VENDOR_COUNT,
            {
                "registered_vendor_ids": registered_vendor_ids,
                "selection_reason": registry_selection["selection_reason"],
            },
        ),
        _check(
            "redacted_transport_and_plan_only_smoke_are_safe",
            FRONTIER_CLIENT.is_file()
            and smoke_manifest.get("status") == "plan_only_no_network"
            and smoke_manifest.get("network_calls_performed") is False
            and int(smoke_manifest.get("network_call_count", -1)) == 0
            and smoke_manifest.get("result_eligible_for_formal_tables") is False,
            {
                "frontier_client_present": FRONTIER_CLIENT.is_file(),
                "smoke_manifest": _path(smoke_manifest_path),
                "smoke_status": smoke_manifest.get("status", ""),
                "network_calls_performed": smoke_manifest.get("network_calls_performed"),
                "network_call_count": smoke_manifest.get("network_call_count"),
                "formal_result_eligible": smoke_manifest.get(
                    "result_eligible_for_formal_tables"
                ),
            },
            severity="warning",
        ),
    ]
    error_failures = [
        check
        for check in checks
        if check["status"] != "pass" and check.get("severity") == "error"
    ]
    configured_ready = not any(
        check["name"] in {
            "local_config_exists",
            "local_config_ignored_and_untracked",
            "tracked_files_do_not_contain_configured_secrets",
            "two_distinct_vendors_configured_for_network_smoke",
        }
        and check["status"] != "pass"
        for check in checks
    )
    audit = {
        "schema_version": "paper-frontier-api-model-slot-admission-audit-1.0",
        "audit_version": AUDIT_VERSION,
        "status": (
            "registry_satisfied_pending_formal_runs"
            if len(registered_frontier_models) >= REQUIRED_VENDOR_COUNT
            else
            "configured_pending_network_smoke"
            if configured_ready
            else "blocked_missing_or_unsafe_local_config"
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "config_path": _path(resolved_config),
        "config_exists": resolved_config.exists(),
        "config_git_safety": git_status,
        "config_redacted": redacted,
        "model_registry_path": _path(model_registry_path),
        "selected_model_registry_path": _path(selected_registry_path),
        "model_registry_selection": registry_selection,
        "model_registry_exists": model_registry_path.exists(),
        "model_registry_sha256": sha256_file(model_registry_path)
        if model_registry_path.exists()
        else "",
        "frontier_client_path": _path(FRONTIER_CLIENT),
        "frontier_client_sha256": sha256_file(FRONTIER_CLIENT)
        if FRONTIER_CLIENT.exists()
        else "",
        "smoke_manifest_path": _path(smoke_manifest_path),
        "smoke_manifest_sha256": sha256_file(smoke_manifest_path)
        if smoke_manifest_path.exists()
        else "",
        "smoke_manifest_status": smoke_manifest.get("status", ""),
        "provider_rows": provider_rows,
        "provider_rows_sha256": rows_sha256(provider_rows),
        "configured_vendor_count": len(configured_vendors),
        "configured_vendors": configured_vendors,
        "registered_frontier_api_vendor_count": len(registered_frontier_models),
        "registered_frontier_api_vendor_ids": registered_vendor_ids,
        "explicit_network_smoke_consent": explicit_network_consent,
        "network_calls_performed": False,
        "result_eligible_for_formal_tables": False,
        "frontier_api_q2_gate": (
            "registry_satisfied_pending_formal_runs"
            if len(registered_frontier_models) >= REQUIRED_VENDOR_COUNT
            else "not_satisfied_registry_slots_missing"
        ),
        "checks": checks,
        "checks_sha256": rows_sha256(checks),
        "passed_checks": sum(1 for check in checks if check["status"] == "pass"),
        "total_checks": len(checks),
        "error_failures": error_failures,
        "config_errors": config_errors,
        "tracked_secret_hits": secret_hits,
        "boundary": (
            "This is a local configuration admission audit only. It never calls "
            "frontier APIs and never prints credentials. API providers can be "
            "registered as paper model slots only after explicit consent, network "
            "smoke, exact model identifiers, cost/log disclosure and frozen formal "
            "run manifests exist."
        ),
    }
    _write_outputs(output_dir, audit)
    return audit


def _write_outputs(output_dir: Path, audit: Mapping[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{AUDIT_STEM}.json"
    md_path = output_dir / f"{AUDIT_STEM}.md"
    json_path.write_text(
        json.dumps(dict(audit), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_markdown(md_path, audit)


def _write_markdown(path: Path, audit: Mapping[str, Any]) -> None:
    lines = [
        "# Frontier API model-slot admission audit v1",
        "",
        f"Generated: {audit['created_at']}",
        "",
        "## Result",
        "",
        f"- Status: `{audit['status']}`",
        f"- Configured vendors: {audit['configured_vendor_count']}",
        f"- Registered frontier API slots: {audit['registered_frontier_api_vendor_count']}",
        f"- Explicit network smoke consent: `{audit['explicit_network_smoke_consent']}`",
        f"- Network calls performed: `{audit['network_calls_performed']}`",
        f"- Result eligible for formal tables: `{audit['result_eligible_for_formal_tables']}`",
        "",
        "## Provider readiness",
        "",
        "| Provider | Key | Model | Status | Missing fields |",
        "|---|---|---|---|---|",
    ]
    for row in audit["provider_rows"]:
        missing = ", ".join(row["missing_fields"]) or "none"
        model = row["model_id"] or ""
        lines.append(
            f"| `{row['provider']}` | `{row['api_key_status']}` | "
            f"`{model}` | `{row['formal_slot_status']}` | {missing} |"
        )
    lines.extend(["", "## Checks", "", "| Check | Status | Severity | Detail |", "|---|---|---|---|"])
    for check in audit["checks"]:
        detail = json.dumps(check.get("detail"), ensure_ascii=False, sort_keys=True)
        if len(detail) > 220:
            detail = detail[:217] + "..."
        lines.append(
            f"| `{check['name']}` | `{check['status']}` | `{check['severity']}` | "
            f"{detail.replace('|', '\\|')} |"
        )
    lines.extend(["", "## Boundary", "", str(audit["boundary"]), ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--model-registry", type=Path, default=DEFAULT_MODEL_REGISTRY)
    parser.add_argument("--smoke-manifest", type=Path, default=DEFAULT_SMOKE_MANIFEST)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    audit = build_frontier_api_model_slot_audit(
        config_path=args.config,
        model_registry_path=args.model_registry,
        smoke_manifest_path=args.smoke_manifest,
        output_dir=args.output_dir,
    )
    print(json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
