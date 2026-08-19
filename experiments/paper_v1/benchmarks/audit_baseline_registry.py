"""Audit paper-v1 baseline registry readiness and exclusion boundaries.

This script turns the baseline list into a reproducible gate.  It does not make
pending baselines usable; it records whether each required baseline is either
implemented, exactly diagnosable, or explicitly excluded with a reason.
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .common import portable_value, rows_sha256, sha256_file
from .public_replay_runner import DEFENSE_CONDITIONS


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REGISTRY = ROOT / "protocols" / "paper_upgrade_v1" / "baseline_registry.json"
DEFAULT_AGENTDOJO = ROOT / "external" / "benchmarks" / "agentdojo"
DEFAULT_OUTPUT = ROOT / "protocols" / "paper_upgrade_v1"
DEFAULT_HF_HUB_CACHE = Path(os.environ.get("HF_HUB_CACHE", Path.home() / ".cache" / "huggingface" / "hub"))
DEFAULT_TRANSFORMERS_SMOKE = (
    ROOT
    / "outputs"
    / "paper_upgrade_v1"
    / "baselines"
    / "agentdojo_transformers_pi_detector_smoke_v1"
    / "smoke_manifest.json"
)
DEFAULT_TRANSFORMERS_LONG_OUTPUT_DIRECT_SMOKE = (
    ROOT
    / "outputs"
    / "paper_upgrade_v1"
    / "baselines"
    / "agentdojo_transformers_pi_detector_long_output_direct_smoke_v1"
    / "smoke_manifest.json"
)
DEFAULT_TOOL_FILTER_FREEZE = (
    ROOT
    / "protocols"
    / "paper_upgrade_v1"
    / "agentdojo_tool_filter_formal_freeze_v1.json"
)
DEFAULT_TOOL_FILTER_QUALIFICATION = (
    ROOT
    / "outputs"
    / "paper_upgrade_v1"
    / "baselines"
    / "agentdojo_tool_filter_official_qualification_v1"
    / "run_manifest.json"
)
DEFAULT_TOOL_FILTER_SECURITY_QUALIFICATION = (
    ROOT
    / "outputs"
    / "paper_upgrade_v1"
    / "baselines"
    / "agentdojo_tool_filter_official_security_qualification_v1"
    / "run_manifest.json"
)
DEFAULT_TOOL_FILTER_FORMAL_RUN = (
    ROOT
    / "outputs"
    / "paper_upgrade_v1"
    / "baselines"
    / "agentdojo_tool_filter_official_formal_v1"
    / "run_manifest.json"
)
DEFAULT_TOOL_FILTER_FORMAL_ANALYSIS = (
    ROOT
    / "outputs"
    / "paper_upgrade_v1"
    / "baselines"
    / "agentdojo_tool_filter_official_formal_v1"
    / "analysis"
    / "analysis_manifest.json"
)
AUDIT_VERSION = "m3-paper-v1-baseline-registry-audit-1.0"
AUDIT_STEM = "baseline_registry_audit_v1"
REQUIRED_EXTERNAL = {"promptguard", "task_shield", "ipiguard", "progent", "camel_or_fides"}
REQUIRED_AGENTDOJO_OFFICIAL = {"agentdojo_tool_filter", "agentdojo_transformers_pi_detector"}
BLOCKED_STATUSES = {
    "pending_exact_adapter",
    "pending_method_selection_and_exact_adapter",
    "real_model_qualification_completed_formal_adapter_pending",
    "ready_official_detector_smoke_completed_formal_run_pending",
    "ready_for_official_smoke_pending_run",
    "ready_official_tool_filter_qualification_completed_formal_run_pending",
    "source_backed_adapter_implemented_pending_qualification",
    "source_backed_adapter_runtime_qualification_failed_model_dag_schema",
    "source_backed_official_detector_resource_blocked_exact_formal",
    "blocked_external_model_transport",
    "blocked_missing_transformers_dependency",
}
DIAGNOSTIC_STATUSES = {"ready_diagnostic_adapter"}
READY_STATUSES = {"ready"}
FORMAL_READY_STATUSES = READY_STATUSES | {"ready_detector_only_formal"}


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


def _agentdojo_defenses(checkout: Path) -> list[str]:
    source = checkout / "src" / "agentdojo" / "agent_pipeline" / "agent_pipeline.py"
    module = ast.parse(source.read_text(encoding="utf-8"))
    for node in module.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "DEFENSES":
                value = ast.literal_eval(node.value)
                if isinstance(value, list):
                    return [str(item) for item in value]
    return []


def _read_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _dependency_probe(
    agentdojo_checkout: Path,
    hf_hub_cache: Path,
    transformers_smoke_manifest: Path,
    transformers_long_output_direct_smoke: Path,
    tool_filter_freeze: Path,
    tool_filter_qualification: Path,
    tool_filter_security_qualification: Path,
    tool_filter_formal_run: Path = DEFAULT_TOOL_FILTER_FORMAL_RUN,
    tool_filter_formal_analysis: Path = DEFAULT_TOOL_FILTER_FORMAL_ANALYSIS,
) -> dict[str, Any]:
    hf_model_cache = hf_hub_cache / "models--protectai--deberta-v3-base-prompt-injection-v2"
    smoke = _read_optional_json(transformers_smoke_manifest)
    long_output_smoke = _read_optional_json(transformers_long_output_direct_smoke)
    smoke_completed = bool(
        smoke
        and smoke.get("status") == "completed_official_detector_smoke_only"
        and smoke.get("summary", {}).get("required_passed")
        == smoke.get("summary", {}).get("required_total")
    )
    tool_filter = _read_optional_json(tool_filter_freeze)
    tool_filter_pipeline = tool_filter.get("agentdojo", {}).get("official_pipeline_config", {}) if tool_filter else {}
    tool_filter_markers = tool_filter.get("agentdojo", {}).get("official_markers", {}) if tool_filter else {}
    tool_filter_transport = tool_filter.get("transport", {}) if tool_filter else {}
    tool_filter_qualification_manifest = _read_optional_json(tool_filter_qualification)
    tool_filter_security_qualification_manifest = _read_optional_json(
        tool_filter_security_qualification
    )
    tool_filter_formal_run_manifest = _read_optional_json(tool_filter_formal_run)
    tool_filter_formal_analysis_manifest = _read_optional_json(tool_filter_formal_analysis)
    tool_filter_completed = bool(
        tool_filter
        and tool_filter.get("status") == "completed_frozen_formal_protocol"
        and tool_filter.get("result_eligible_for_formal_tables") is False
        and tool_filter_pipeline.get("llm") == "OPENAI_COMPATIBLE"
        and tool_filter_transport.get("provider") == "openai-compatible"
        and tool_filter_markers.get("official_filter_component") is True
        and tool_filter_markers.get("openai_compatible_provider") is True
    )
    binding = (
        tool_filter_qualification_manifest.get("openai_compatible_tool_filter_binding", {})
        if tool_filter_qualification_manifest
        else {}
    )
    tool_filter_qualification_completed = bool(
        tool_filter_qualification_manifest
        and tool_filter_qualification_manifest.get("status") == "completed_diagnostic_partial"
        and tool_filter_qualification_manifest.get("result_eligible_for_formal_tables") is False
        and tool_filter_qualification_manifest.get("summary", {}).get("expected_cases") == 2
        and tool_filter_qualification_manifest.get("summary", {}).get("completed_cases") == 2
        and tool_filter_qualification_manifest.get("summary", {}).get("failed_cases") == 0
        and binding.get("shim") == "openai_compatible_tool_filter_model_binding"
        and binding.get("algorithm_changed") is False
        and binding.get("prompt_changed") is False
        and binding.get("selection_rule_changed") is False
    )
    security_binding = (
        tool_filter_security_qualification_manifest.get(
            "openai_compatible_tool_filter_binding", {}
        )
        if tool_filter_security_qualification_manifest
        else {}
    )
    tool_filter_security_qualification_completed = bool(
        tool_filter_security_qualification_manifest
        and tool_filter_security_qualification_manifest.get("status")
        == "completed_diagnostic_partial"
        and tool_filter_security_qualification_manifest.get(
            "result_eligible_for_formal_tables"
        )
        is False
        and tool_filter_security_qualification_manifest.get("summary", {}).get(
            "expected_cases"
        )
        == 2
        and tool_filter_security_qualification_manifest.get("summary", {}).get(
            "completed_cases"
        )
        == 2
        and tool_filter_security_qualification_manifest.get("summary", {}).get(
            "failed_cases"
        )
        == 0
        and tool_filter_security_qualification_manifest.get("summary", {}).get(
            "utility_cases"
        )
        == 1
        and tool_filter_security_qualification_manifest.get("summary", {}).get(
            "security_cases"
        )
        == 1
        and security_binding.get("shim") == "openai_compatible_tool_filter_model_binding"
        and security_binding.get("algorithm_changed") is False
        and security_binding.get("prompt_changed") is False
        and security_binding.get("selection_rule_changed") is False
    )
    tool_filter_formal_completed = bool(
        tool_filter_formal_run_manifest
        and tool_filter_formal_run_manifest.get("status") == "completed_formal"
        and tool_filter_formal_run_manifest.get("result_eligible_for_formal_tables") is True
        and tool_filter_formal_run_manifest.get("summary", {}).get("expected_cases") == 726
        and tool_filter_formal_run_manifest.get("summary", {}).get("completed_cases") == 726
        and tool_filter_formal_run_manifest.get("summary", {}).get("failed_cases") == 0
        and tool_filter_formal_run_manifest.get("exact_frozen_coverage") is True
    )
    tool_filter_formal_analysis_completed = bool(
        tool_filter_formal_analysis_manifest
        and tool_filter_formal_analysis_manifest.get("status") == "completed_formal_analysis"
        and tool_filter_formal_analysis_manifest.get("result_eligible_for_formal_tables")
        is True
        and tool_filter_formal_analysis_manifest.get("run_manifest_sha256")
        == (sha256_file(tool_filter_formal_run) if tool_filter_formal_run.exists() else "")
    )
    long_output_resource_blocked = bool(
        long_output_smoke
        and long_output_smoke.get("status") == "failed_long_output_direct_smoke"
        and int(long_output_smoke.get("selected_tool_output", {}).get("char_count", 0) or 0)
        >= 10_000
        and "DefaultCPUAllocator" in str(long_output_smoke.get("error", ""))
    )
    return {
        "agentdojo_checkout_exists": agentdojo_checkout.exists(),
        "agentdojo_pipeline_sha256": sha256_file(
            agentdojo_checkout / "src" / "agentdojo" / "agent_pipeline" / "agent_pipeline.py"
        )
        if agentdojo_checkout.exists()
        else "",
        "openai_api_key_present": bool(os.environ.get("OPENAI_API_KEY")),
        "transformers_installed": importlib.util.find_spec("transformers") is not None,
        "torch_installed": importlib.util.find_spec("torch") is not None,
        "protectai_detector_cached": hf_model_cache.exists(),
        "protectai_detector_cache_path": str(hf_model_cache),
        "hf_hub_cache": str(hf_hub_cache),
        "transformers_runtime_smoke_manifest": str(transformers_smoke_manifest),
        "transformers_runtime_smoke_status": smoke.get("status") if smoke else "",
        "transformers_long_output_direct_smoke_manifest": str(
            transformers_long_output_direct_smoke
        ),
        "transformers_long_output_direct_smoke_status": long_output_smoke.get("status")
        if long_output_smoke
        else "",
        "transformers_long_output_direct_smoke_chars": long_output_smoke.get(
            "selected_tool_output", {}
        ).get("char_count")
        if long_output_smoke
        else None,
        "transformers_long_output_resource_blocked": long_output_resource_blocked,
        "transformers_runtime_smoke_required_passed": smoke.get("summary", {}).get("required_passed")
        if smoke
        else None,
        "transformers_runtime_smoke_required_total": smoke.get("summary", {}).get("required_total")
        if smoke
        else None,
        "transformers_runtime_ready": smoke_completed,
        "tool_filter_freeze": str(tool_filter_freeze),
        "tool_filter_freeze_sha256": sha256_file(tool_filter_freeze)
        if tool_filter_freeze.exists()
        else "",
        "tool_filter_freeze_status": tool_filter.get("status") if tool_filter else "",
        "tool_filter_freeze_model_id": tool_filter.get("model_id") if tool_filter else "",
        "tool_filter_transport_provider": tool_filter_transport.get("provider", ""),
        "tool_filter_transport_ready": tool_filter_completed,
        "tool_filter_qualification_manifest": str(tool_filter_qualification),
        "tool_filter_qualification_sha256": sha256_file(tool_filter_qualification)
        if tool_filter_qualification.exists()
        else "",
        "tool_filter_qualification_status": tool_filter_qualification_manifest.get("status")
        if tool_filter_qualification_manifest
        else "",
        "tool_filter_qualification_completed": tool_filter_qualification_completed,
        "tool_filter_qualification_cases": tool_filter_qualification_manifest.get("summary", {})
        if tool_filter_qualification_manifest
        else {},
        "tool_filter_openai_compatible_binding": binding,
        "tool_filter_security_qualification_manifest": str(
            tool_filter_security_qualification
        ),
        "tool_filter_security_qualification_sha256": sha256_file(
            tool_filter_security_qualification
        )
        if tool_filter_security_qualification.exists()
        else "",
        "tool_filter_security_qualification_status": tool_filter_security_qualification_manifest.get(
            "status"
        )
        if tool_filter_security_qualification_manifest
        else "",
        "tool_filter_security_qualification_completed": tool_filter_security_qualification_completed,
        "tool_filter_security_qualification_cases": tool_filter_security_qualification_manifest.get(
            "summary", {}
        )
        if tool_filter_security_qualification_manifest
        else {},
        "tool_filter_security_openai_compatible_binding": security_binding,
        "tool_filter_formal_run_manifest": str(tool_filter_formal_run),
        "tool_filter_formal_run_sha256": sha256_file(tool_filter_formal_run)
        if tool_filter_formal_run.exists()
        else "",
        "tool_filter_formal_run_status": tool_filter_formal_run_manifest.get("status")
        if tool_filter_formal_run_manifest
        else "",
        "tool_filter_formal_completed": tool_filter_formal_completed,
        "tool_filter_formal_analysis_manifest": str(tool_filter_formal_analysis),
        "tool_filter_formal_analysis_sha256": sha256_file(tool_filter_formal_analysis)
        if tool_filter_formal_analysis.exists()
        else "",
        "tool_filter_formal_analysis_status": tool_filter_formal_analysis_manifest.get(
            "status"
        )
        if tool_filter_formal_analysis_manifest
        else "",
        "tool_filter_formal_analysis_completed": tool_filter_formal_analysis_completed,
        "agentdojo_defenses": _agentdojo_defenses(agentdojo_checkout)
        if agentdojo_checkout.exists()
        else [],
    }


def _condition_index(registry: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    conditions = registry.get("conditions")
    if not isinstance(conditions, list):
        raise ValueError("baseline registry missing conditions list")
    result: dict[str, dict[str, Any]] = {}
    for row in conditions:
        if isinstance(row, Mapping):
            result[str(row.get("id", ""))] = dict(row)
    return result


def _is_result_eligible(row: Mapping[str, Any]) -> bool:
    return bool(row.get("result_eligible", row.get("implementation_status") == "ready"))


def _audit_conditions(registry: Mapping[str, Any], probe: Mapping[str, Any]) -> list[dict[str, Any]]:
    index = _condition_index(registry)
    conditions = list(index.values())
    ids = [str(row.get("id", "")) for row in conditions]
    checks: list[dict[str, Any]] = [
        _check("unique_condition_ids", len(ids) == len(set(ids)), detail=ids),
        _check(
            "required_external_baselines_represented",
            REQUIRED_EXTERNAL <= set(ids),
            detail={"missing": sorted(REQUIRED_EXTERNAL - set(ids))},
        ),
        _check(
            "required_agentdojo_official_baselines_represented",
            REQUIRED_AGENTDOJO_OFFICIAL <= set(ids),
            detail={"missing": sorted(REQUIRED_AGENTDOJO_OFFICIAL - set(ids))},
        ),
    ]
    local_condition_ids = set(DEFENSE_CONDITIONS)
    ready_local_ids = {
        str(row["id"])
        for row in conditions
        if row.get("implementation_status") in READY_STATUSES | DIAGNOSTIC_STATUSES
        and str(row.get("family", "")).startswith(("local", "m3", "agentdojo_official_prompt"))
    }
    checks.append(
        _check(
            "ready_and_diagnostic_local_conditions_have_runtime_entries",
            ready_local_ids <= local_condition_ids,
            detail={"missing_runtime_entries": sorted(ready_local_ids - local_condition_ids)},
        )
    )
    blocked_rows = [
        row
        for row in conditions
        if str(row.get("implementation_status", "")) in BLOCKED_STATUSES
    ]
    checks.append(
        _check(
            "blocked_or_pending_rows_not_result_eligible",
            all(not _is_result_eligible(row) for row in blocked_rows),
            detail=[row.get("id") for row in blocked_rows if _is_result_eligible(row)],
        )
    )
    checks.append(
        _check(
            "blocked_or_pending_rows_have_exclusion_rules",
            all(row.get("formal_exclusion_rule") for row in blocked_rows),
            detail=[row.get("id") for row in blocked_rows if not row.get("formal_exclusion_rule")],
        )
    )
    checks.append(
        _check(
            "blocked_or_pending_rows_have_blockers_and_plans",
            all(row.get("current_blockers") and row.get("compatibility_plan") for row in blocked_rows),
            detail=[
                row.get("id")
                for row in blocked_rows
                if not (row.get("current_blockers") and row.get("compatibility_plan"))
            ],
        )
    )
    official_defenses = set(probe.get("agentdojo_defenses", []))
    checks.append(
        _check(
            "agentdojo_official_defenses_present_upstream",
            {"tool_filter", "transformers_pi_detector"} <= official_defenses,
            detail={"agentdojo_defenses": sorted(official_defenses)},
        )
    )
    checks.append(
        _check(
            "agentdojo_tool_filter_blocker_matches_probe",
            index.get("agentdojo_tool_filter", {}).get("implementation_status")
            == (
                "ready"
                if probe.get("tool_filter_formal_completed")
                and probe.get("tool_filter_formal_analysis_completed")
                else
                "ready_official_tool_filter_qualification_completed_formal_run_pending"
                if probe.get("tool_filter_qualification_completed")
                and probe.get("tool_filter_security_qualification_completed")
                else "ready_for_official_smoke_pending_run"
                if probe.get("tool_filter_transport_ready")
                else "blocked_external_model_transport"
            ),
            severity="warning",
            detail={
                "registry_status": index.get("agentdojo_tool_filter", {}).get("implementation_status"),
                "openai_api_key_present": probe.get("openai_api_key_present"),
                "tool_filter_transport_ready": probe.get("tool_filter_transport_ready"),
                "tool_filter_freeze_status": probe.get("tool_filter_freeze_status"),
                "tool_filter_freeze_model_id": probe.get("tool_filter_freeze_model_id"),
                "tool_filter_qualification_status": probe.get(
                    "tool_filter_qualification_status"
                ),
                "tool_filter_qualification_completed": probe.get(
                    "tool_filter_qualification_completed"
                ),
                "tool_filter_security_qualification_status": probe.get(
                    "tool_filter_security_qualification_status"
                ),
                "tool_filter_security_qualification_completed": probe.get(
                    "tool_filter_security_qualification_completed"
                ),
                "tool_filter_formal_run_status": probe.get("tool_filter_formal_run_status"),
                "tool_filter_formal_completed": probe.get("tool_filter_formal_completed"),
                "tool_filter_formal_analysis_status": probe.get(
                    "tool_filter_formal_analysis_status"
                ),
                "tool_filter_formal_analysis_completed": probe.get(
                    "tool_filter_formal_analysis_completed"
                ),
            },
        )
    )
    checks.append(
        _check(
            "agentdojo_transformers_detector_blocker_matches_probe",
            index.get("agentdojo_transformers_pi_detector", {}).get("implementation_status")
            in (
                ["source_backed_official_detector_resource_blocked_exact_formal"]
                if probe.get("transformers_long_output_resource_blocked")
                else [
                    "ready_official_detector_smoke_completed_formal_run_pending",
                    "blocked_missing_transformers_dependency",
                ]
            )
            and (
                bool(probe.get("transformers_runtime_ready"))
                or index.get("agentdojo_transformers_pi_detector", {}).get(
                    "implementation_status"
                )
                == "blocked_missing_transformers_dependency"
            ),
            severity="warning",
            detail={
                "registry_status": index.get("agentdojo_transformers_pi_detector", {}).get("implementation_status"),
                "transformers_installed": probe.get("transformers_installed"),
                "protectai_detector_cached": probe.get("protectai_detector_cached"),
                "transformers_runtime_ready": probe.get("transformers_runtime_ready"),
                "transformers_runtime_smoke_status": probe.get("transformers_runtime_smoke_status"),
                "transformers_long_output_direct_smoke_status": probe.get(
                    "transformers_long_output_direct_smoke_status"
                ),
                "transformers_long_output_direct_smoke_chars": probe.get(
                    "transformers_long_output_direct_smoke_chars"
                ),
                "transformers_long_output_resource_blocked": probe.get(
                    "transformers_long_output_resource_blocked"
                ),
            },
        )
    )
    checks.append(
        _check(
            "q2_gate_not_satisfied_until_strong_baselines_ready",
            registry.get("q2_gate_minimum_strong_baselines", {}).get("current_gate_status")
            == (
                "satisfied"
                if len(
                    [
                        row
                        for row in conditions
                        if str(row.get("id", "")) in REQUIRED_EXTERNAL | REQUIRED_AGENTDOJO_OFFICIAL
                        and row.get("implementation_status") in FORMAL_READY_STATUSES
                        and _is_result_eligible(row)
                    ]
                )
                >= int(
                    registry.get("q2_gate_minimum_strong_baselines", {}).get(
                        "minimum_exact_or_disclosed_exclusion_count", 5
                    )
                )
                else "not_satisfied"
            ),
            severity="warning",
            detail={
                **registry.get("q2_gate_minimum_strong_baselines", {}),
                "formal_ready_count": len(
                    [
                        row
                        for row in conditions
                        if str(row.get("id", "")) in REQUIRED_EXTERNAL | REQUIRED_AGENTDOJO_OFFICIAL
                        and row.get("implementation_status") in FORMAL_READY_STATUSES
                        and _is_result_eligible(row)
                    ]
                ),
            },
        )
    )
    return checks


def _summarize_conditions(registry: Mapping[str, Any]) -> dict[str, Any]:
    conditions = registry.get("conditions", [])
    counts: dict[str, int] = {}
    families: dict[str, int] = {}
    result_eligible: list[str] = []
    blocked_or_pending: list[str] = []
    for row in conditions:
        if not isinstance(row, Mapping):
            continue
        status = str(row.get("implementation_status", ""))
        family = str(row.get("family", ""))
        counts[status] = counts.get(status, 0) + 1
        families[family] = families.get(family, 0) + 1
        if _is_result_eligible(row):
            result_eligible.append(str(row.get("id", "")))
        if status in BLOCKED_STATUSES:
            blocked_or_pending.append(str(row.get("id", "")))
    return {
        "condition_count": len([row for row in conditions if isinstance(row, Mapping)]),
        "status_counts": counts,
        "family_counts": families,
        "result_eligible_by_registry": sorted(result_eligible),
        "blocked_or_pending": sorted(blocked_or_pending),
    }


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_markdown(path: Path, audit: Mapping[str, Any]) -> None:
    lines = [
        "# Baseline registry audit v1",
        "",
        f"Generated: {audit['created_at']}",
        "",
        "## Result",
        "",
        f"- Status: `{audit['status']}`",
        f"- Passed checks: {audit['passed_checks']}/{audit['total_checks']}",
        f"- Q2 strong-baseline gate: `{audit['q2_strong_baseline_gate']}`",
        f"- Registry SHA-256: `{audit['baseline_registry_sha256']}`",
        "",
        "## Summary",
        "",
        f"- Condition count: {audit['summary']['condition_count']}",
        f"- Result-eligible by registry: {', '.join(audit['summary']['result_eligible_by_registry'])}",
        f"- Blocked or pending: {', '.join(audit['summary']['blocked_or_pending'])}",
        "",
        "## Dependency probe",
        "",
    ]
    for key, value in audit["dependency_probe"].items():
        if key == "agentdojo_defenses":
            value = ", ".join(value)
        lines.append(f"- `{key}`: {value}")
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
            "This audit is a readiness/exclusion gate. It does not convert blocked or pending strong baselines into formal comparison results.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def build_baseline_registry_audit(
    *,
    registry_path: Path = DEFAULT_REGISTRY,
    agentdojo_checkout: Path = DEFAULT_AGENTDOJO,
    output_dir: Path = DEFAULT_OUTPUT,
    hf_hub_cache: Path = DEFAULT_HF_HUB_CACHE,
    transformers_smoke_manifest: Path = DEFAULT_TRANSFORMERS_SMOKE,
    transformers_long_output_direct_smoke: Path = DEFAULT_TRANSFORMERS_LONG_OUTPUT_DIRECT_SMOKE,
    tool_filter_freeze: Path = DEFAULT_TOOL_FILTER_FREEZE,
    tool_filter_qualification: Path = DEFAULT_TOOL_FILTER_QUALIFICATION,
    tool_filter_security_qualification: Path = DEFAULT_TOOL_FILTER_SECURITY_QUALIFICATION,
) -> dict[str, Any]:
    registry_path = registry_path.resolve()
    agentdojo_checkout = agentdojo_checkout.resolve()
    hf_hub_cache = hf_hub_cache.resolve()
    transformers_smoke_manifest = transformers_smoke_manifest.resolve()
    transformers_long_output_direct_smoke = transformers_long_output_direct_smoke.resolve()
    tool_filter_freeze = tool_filter_freeze.resolve()
    tool_filter_qualification = tool_filter_qualification.resolve()
    tool_filter_security_qualification = tool_filter_security_qualification.resolve()
    registry = _read_json(registry_path)
    probe = _dependency_probe(
        agentdojo_checkout,
        hf_hub_cache,
        transformers_smoke_manifest,
        transformers_long_output_direct_smoke,
        tool_filter_freeze,
        tool_filter_qualification,
        tool_filter_security_qualification,
    )
    checks = _audit_conditions(registry, probe)
    error_failures = [
        check
        for check in checks
        if check["status"] != "pass" and check.get("severity") == "error"
    ]
    passed = sum(1 for check in checks if check["status"] == "pass")
    summary = _summarize_conditions(registry)
    strong_ready = [
        row_id
        for row_id, row in _condition_index(registry).items()
        if row_id in REQUIRED_EXTERNAL | REQUIRED_AGENTDOJO_OFFICIAL
        and row.get("implementation_status") in FORMAL_READY_STATUSES
        and _is_result_eligible(row)
    ]
    audit = {
        "schema_version": "paper-baseline-registry-audit-1.0",
        "audit_version": AUDIT_VERSION,
        "status": "completed" if not error_failures else "failed",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "baseline_registry": str(registry_path),
        "baseline_registry_sha256": sha256_file(registry_path),
        "agentdojo_checkout": str(agentdojo_checkout),
        "dependency_probe": probe,
        "summary": summary,
        "q2_strong_baseline_gate": "not_satisfied",
        "ready_required_strong_baselines": sorted(strong_ready),
        "required_strong_baselines": sorted(REQUIRED_EXTERNAL | REQUIRED_AGENTDOJO_OFFICIAL),
        "checks": checks,
        "checks_sha256": rows_sha256(checks),
        "total_checks": len(checks),
        "passed_checks": passed,
        "error_failures": error_failures,
        "result_eligible_for_formal_tables": False,
        "boundary": (
            "Readiness/exclusion audit only. Formal baseline comparisons still "
            "require exact adapters, dependency snapshots, frozen protocols and "
            "formal run manifests."
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
    parser.add_argument("--agentdojo-checkout", type=Path, default=DEFAULT_AGENTDOJO)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--hf-hub-cache", type=Path, default=DEFAULT_HF_HUB_CACHE)
    parser.add_argument(
        "--transformers-smoke-manifest",
        type=Path,
        default=DEFAULT_TRANSFORMERS_SMOKE,
    )
    parser.add_argument(
        "--tool-filter-freeze",
        type=Path,
        default=DEFAULT_TOOL_FILTER_FREEZE,
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    audit = build_baseline_registry_audit(
        registry_path=args.registry,
        agentdojo_checkout=args.agentdojo_checkout,
        output_dir=args.output_dir,
        hf_hub_cache=args.hf_hub_cache,
        transformers_smoke_manifest=args.transformers_smoke_manifest,
        tool_filter_freeze=args.tool_filter_freeze,
    )
    print(json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
