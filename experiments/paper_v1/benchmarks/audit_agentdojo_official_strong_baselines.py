"""Audit AgentDojo's official strong-baseline defenses without running them.

The paper-v1 upgrade needs strong baselines, but two important AgentDojo
defenses cannot be treated as M3 local-runner conditions by name alone:

* ``tool_filter`` is implemented inside the official AgentDojo OpenAILLM
  pipeline and requires an OpenAI-compatible model transport.
* ``transformers_pi_detector`` is implemented inside the official tool
  execution loop and requires ``transformers`` plus the ProtectAI detector.

This audit records the pinned official source markers, local dependency state,
run-command templates, and the formal boundary that keeps blocked diagnostics
out of result tables.  It performs no network calls, no model calls, and no
package/model installation.
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .common import portable_path, portable_value, rows_sha256, sha256_file
from .public_replay_runner import DEFENSE_CONDITIONS


ROOT = Path(__file__).resolve().parents[3]
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
AUDIT_VERSION = "m3-paper-v1-agentdojo-official-strong-baseline-capability-audit-1.0"
AUDIT_STEM = "agentdojo_official_strong_baseline_capability_audit_v1"

OFFICIAL_FILES = {
    "pipeline": "src/agentdojo/agent_pipeline/agent_pipeline.py",
    "pi_detector": "src/agentdojo/agent_pipeline/pi_detector.py",
    "benchmark_script": "src/agentdojo/scripts/benchmark.py",
    "readme": "README.md",
    "results_docs": "docs/results.md",
}

PIPELINE_MARKERS = {
    "defenses_constant": "DEFENSES = [",
    "defenses_tool_filter": '"tool_filter"',
    "defenses_transformers_pi_detector": '"transformers_pi_detector"',
    "tool_filter_openai_guard": "if not isinstance(llm, OpenAILLM):",
    "tool_filter_component": "OpenAILLMToolFilter(TOOL_FILTER_PROMPT, llm.client, llm_name)",
    "transformers_detector_component": "TransformersBasedPIDetector(",
    "transformers_detector_model": 'model_name="protectai/deberta-v3-base-prompt-injection-v2"',
    "transformers_detector_safe_label": 'safe_label="SAFE"',
    "transformers_detector_threshold": "threshold=0.5",
    "transformers_detector_mode": 'mode="message"',
}

PI_DETECTOR_MARKERS = {
    "detector_class": "class TransformersBasedPIDetector",
    "detector_default_model": 'model_name: str = "protectai/deberta-v3-base-prompt-injection-v2"',
    "detector_default_safe_label": 'safe_label: str = "SAFE"',
    "detector_default_threshold": "threshold: float = 0.5",
    "detector_default_mode": 'mode: Literal["message", "full_conversation"] = "message"',
    "detector_transformers_import": "from transformers import pipeline",
    "detector_pipeline_call": 'pipeline("text-classification", model=self.model_name, device=device)',
    "detector_redaction_text": "<Data omitted because a prompt injection was detected>",
    "detector_decision_rule": "safety_score < self.threshold",
    "detector_install_hint": "pip install agentdojo[transformers]",
}

README_MARKERS = {
    "benchmark_module_command": "python -m agentdojo.scripts.benchmark",
    "tool_filter_example": "--defense tool_filter",
    "tool_knowledge_attack_example": "--attack tool_knowledge",
}

REQUIRED_OFFICIAL_DEFENSES = {"tool_filter", "transformers_pi_detector"}
OFFICIAL_STRONG_BASELINE_IDS = {
    "agentdojo_tool_filter",
    "agentdojo_transformers_pi_detector",
}


def _check(name: str, passed: bool, *, severity: str = "error", detail: Any = None) -> dict[str, Any]:
    return {
        "name": name,
        "status": "pass" if passed else "fail",
        "severity": severity,
        "detail": detail,
    }


def _safe_sha256(path: Path) -> str:
    return sha256_file(path) if path.exists() else ""


def _path(path: Path) -> str:
    return portable_path(path, root=ROOT)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _file_manifest(checkout: Path) -> dict[str, dict[str, Any]]:
    manifest: dict[str, dict[str, Any]] = {}
    for label, relative in OFFICIAL_FILES.items():
        path = checkout / relative
        manifest[label] = {
            "relative_path": relative,
            "path": _path(path),
            "exists": path.exists(),
            "sha256": _safe_sha256(path),
        }
    return manifest


def _agentdojo_defenses(checkout: Path) -> list[str]:
    source = checkout / OFFICIAL_FILES["pipeline"]
    if not source.exists():
        return []
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


def _marker_results(text: str, markers: Mapping[str, str]) -> dict[str, dict[str, Any]]:
    return {
        name: {
            "marker": marker,
            "present": marker in text,
        }
        for name, marker in markers.items()
    }


def _read_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _dependency_probe(
    checkout: Path,
    hf_hub_cache: Path,
    transformers_smoke_manifest: Path,
    tool_filter_freeze: Path,
    tool_filter_qualification: Path,
    tool_filter_security_qualification: Path,
) -> dict[str, Any]:
    detector_cache = hf_hub_cache / "models--protectai--deberta-v3-base-prompt-injection-v2"
    refs_main = detector_cache / "refs" / "main"
    smoke = _read_optional_json(transformers_smoke_manifest)
    smoke_required_passed = (
        smoke
        and smoke.get("summary", {}).get("required_passed")
        == smoke.get("summary", {}).get("required_total")
    )
    smoke_completed = bool(
        smoke
        and smoke.get("status") == "completed_official_detector_smoke_only"
        and smoke_required_passed
        and smoke.get("result_eligible_for_formal_tables") is False
    )
    tool_filter = _read_optional_json(tool_filter_freeze)
    tool_filter_pipeline = tool_filter.get("agentdojo", {}).get("official_pipeline_config", {}) if tool_filter else {}
    tool_filter_markers = tool_filter.get("agentdojo", {}).get("official_markers", {}) if tool_filter else {}
    tool_filter_transport = tool_filter.get("transport", {}) if tool_filter else {}
    tool_filter_qualification_manifest = _read_optional_json(tool_filter_qualification)
    tool_filter_security_qualification_manifest = _read_optional_json(
        tool_filter_security_qualification
    )
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
    return {
        "python_executable": sys.executable,
        "agentdojo_checkout_exists": checkout.exists(),
        "agentdojo_source_layout_present": (checkout / "src" / "agentdojo").exists(),
        "agentdojo_defenses": _agentdojo_defenses(checkout),
        "openai_api_key_present": bool(os.environ.get("OPENAI_API_KEY")),
        "openai_compatible_base_url_present": bool(os.environ.get("OPENAI_COMPATIBLE_BASE_URL")),
        "openai_package_installed": importlib.util.find_spec("openai") is not None,
        "transformers_installed": importlib.util.find_spec("transformers") is not None,
        "torch_installed": importlib.util.find_spec("torch") is not None,
        "huggingface_hub_installed": importlib.util.find_spec("huggingface_hub") is not None,
        "protectai_detector_cached": detector_cache.exists(),
        "protectai_detector_cache_path": _path(detector_cache),
        "protectai_detector_refs_main": refs_main.read_text(encoding="utf-8").strip()
        if refs_main.exists()
        else "",
        "hf_hub_cache": _path(hf_hub_cache),
        "transformers_runtime_smoke_manifest": _path(transformers_smoke_manifest),
        "transformers_runtime_smoke_sha256": sha256_file(transformers_smoke_manifest)
        if transformers_smoke_manifest.exists()
        else "",
        "transformers_runtime_smoke_status": smoke.get("status") if smoke else "",
        "transformers_runtime_smoke_required_passed": smoke.get("summary", {}).get("required_passed")
        if smoke
        else None,
        "transformers_runtime_smoke_required_total": smoke.get("summary", {}).get("required_total")
        if smoke
        else None,
        "transformers_runtime_smoke_python": smoke.get("python_executable") if smoke else "",
        "transformers_runtime_ready": smoke_completed,
        "tool_filter_freeze": _path(tool_filter_freeze),
        "tool_filter_freeze_sha256": sha256_file(tool_filter_freeze)
        if tool_filter_freeze.exists()
        else "",
        "tool_filter_freeze_status": tool_filter.get("status") if tool_filter else "",
        "tool_filter_freeze_model_id": tool_filter.get("model_id") if tool_filter else "",
        "tool_filter_freeze_prompt_sha256": tool_filter.get("tool_filter", {}).get("prompt_sha256")
        if tool_filter
        else "",
        "tool_filter_transport_provider": tool_filter_transport.get("provider", ""),
        "tool_filter_transport_ready": tool_filter_completed,
        "tool_filter_qualification_manifest": _path(tool_filter_qualification),
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
            _path(tool_filter_security_qualification)
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
    }


def _tool_filter_blockers(probe: Mapping[str, Any], markers_ok: bool) -> list[str]:
    blockers: list[str] = []
    if not markers_ok:
        blockers.append("official AgentDojo source markers for tool_filter did not all pass")
    if probe.get("tool_filter_transport_ready"):
        return blockers
    if not probe.get("openai_package_installed"):
        blockers.append("openai package is not installed in the current Python environment")
    if not (
        probe.get("openai_api_key_present") or probe.get("openai_compatible_base_url_present")
    ):
        blockers.append(
            "no OPENAI_API_KEY or OPENAI_COMPATIBLE_BASE_URL is configured for the official OpenAILLM transport"
        )
    return blockers


def _transformers_detector_blockers(probe: Mapping[str, Any], markers_ok: bool) -> list[str]:
    blockers: list[str] = []
    if not markers_ok:
        blockers.append(
            "official AgentDojo source markers for transformers_pi_detector did not all pass"
        )
    if probe.get("transformers_runtime_ready"):
        return blockers
    if not probe.get("transformers_installed"):
        blockers.append("transformers is not installed")
    if not probe.get("torch_installed"):
        blockers.append("torch is not installed")
    if not probe.get("protectai_detector_cached"):
        blockers.append("protectai/deberta-v3-base-prompt-injection-v2 is not cached locally")
    blockers.append("official transformers_pi_detector runtime smoke is not completed")
    return blockers


def _baseline_record(
    *,
    baseline_id: str,
    official_defense: str,
    source_files: list[str],
    blockers: list[str],
    command_template: str,
    compatibility_plan: list[str],
    ready_status: str = "ready_for_official_smoke_pending_run",
) -> dict[str, Any]:
    status = ready_status if not blockers else (
        "blocked_external_model_transport"
        if baseline_id == "agentdojo_tool_filter"
        else "blocked_missing_transformers_dependency"
    )
    return {
        "baseline_id": baseline_id,
        "official_defense": official_defense,
        "source_files": source_files,
        "capability_status": status,
        "dependency_blockers": blockers,
        "official_run_command_template": command_template,
        "compatibility_plan": compatibility_plan,
        "result_eligible_for_formal_tables": False,
        "result_exclusion_rule": (
            "Exclude from formal result tables until the byte-identical official "
            "AgentDojo pipeline has a frozen run manifest, dependency snapshot, "
            "model/API label, source hashes, and complete logs."
        ),
        "m3_local_runner_mixing_rule": (
            "Do not map this official AgentDojo defense to an M3 local runner "
            "condition unless it is separately labelled as a non-identical adapter."
        ),
    }


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_markdown(path: Path, audit: Mapping[str, Any]) -> None:
    lines = [
        "# AgentDojo official strong-baseline capability audit v1",
        "",
        f"Generated: {audit['created_at']}",
        "",
        "## Result",
        "",
        f"- Status: `{audit['status']}`",
        f"- Passed checks: {audit['passed_checks']}/{audit['total_checks']}",
        f"- Formal result eligible: `{audit['result_eligible_for_formal_tables']}`",
        f"- Q2 strong-baseline gate: `{audit['q2_strong_baseline_gate']}`",
        "",
        "## Official defenses found",
        "",
        "- " + ", ".join(audit["official_defenses"]),
        "",
        "## Baseline capability summary",
        "",
        "| Baseline | Official defense | Status | Main blockers |",
        "|---|---|---|---|",
    ]
    for baseline in audit["baselines"].values():
        blockers = "; ".join(baseline["dependency_blockers"]) or "none recorded"
        blockers = blockers.replace("|", "\\|")
        lines.append(
            f"| `{baseline['baseline_id']}` | `{baseline['official_defense']}` | "
            f"`{baseline['capability_status']}` | {blockers} |"
        )
    lines.extend(
        [
            "",
            "## Dependency probe",
            "",
        ]
    )
    for key, value in audit["dependency_probe"].items():
        if isinstance(value, list):
            value = ", ".join(value)
        lines.append(f"- `{key}`: {value}")
    lines.extend(
        [
            "",
            "## Official run command templates",
            "",
        ]
    )
    for baseline in audit["baselines"].values():
        lines.extend(
            [
                f"### {baseline['baseline_id']}",
                "",
                "```powershell",
                baseline["official_run_command_template"],
                "```",
                "",
            ]
        )
    lines.extend(
        [
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


def build_agentdojo_official_strong_baseline_audit(
    *,
    agentdojo_checkout: Path = DEFAULT_AGENTDOJO,
    output_dir: Path = DEFAULT_OUTPUT,
    hf_hub_cache: Path = DEFAULT_HF_HUB_CACHE,
    transformers_smoke_manifest: Path = DEFAULT_TRANSFORMERS_SMOKE,
    tool_filter_freeze: Path = DEFAULT_TOOL_FILTER_FREEZE,
    tool_filter_qualification: Path = DEFAULT_TOOL_FILTER_QUALIFICATION,
    tool_filter_security_qualification: Path = DEFAULT_TOOL_FILTER_SECURITY_QUALIFICATION,
) -> dict[str, Any]:
    agentdojo_checkout = agentdojo_checkout.resolve()
    output_dir = output_dir.resolve()
    hf_hub_cache = hf_hub_cache.resolve()
    transformers_smoke_manifest = transformers_smoke_manifest.resolve()
    tool_filter_freeze = tool_filter_freeze.resolve()
    tool_filter_qualification = tool_filter_qualification.resolve()
    tool_filter_security_qualification = tool_filter_security_qualification.resolve()
    files = _file_manifest(agentdojo_checkout)
    pipeline_text = _read_text(agentdojo_checkout / OFFICIAL_FILES["pipeline"])
    pi_detector_text = _read_text(agentdojo_checkout / OFFICIAL_FILES["pi_detector"])
    readme_text = _read_text(agentdojo_checkout / OFFICIAL_FILES["readme"])
    pipeline_markers = _marker_results(pipeline_text, PIPELINE_MARKERS)
    pi_detector_markers = _marker_results(pi_detector_text, PI_DETECTOR_MARKERS)
    readme_markers = _marker_results(readme_text, README_MARKERS)
    probe = _dependency_probe(
        agentdojo_checkout,
        hf_hub_cache,
        transformers_smoke_manifest,
        tool_filter_freeze,
        tool_filter_qualification,
        tool_filter_security_qualification,
    )
    official_defenses = set(probe["agentdojo_defenses"])

    tool_filter_markers_ok = all(
        pipeline_markers[name]["present"]
        for name in [
            "defenses_constant",
            "defenses_tool_filter",
            "tool_filter_openai_guard",
            "tool_filter_component",
        ]
    )
    transformer_markers_ok = all(
        pipeline_markers[name]["present"]
        for name in [
            "defenses_constant",
            "defenses_transformers_pi_detector",
            "transformers_detector_component",
            "transformers_detector_model",
            "transformers_detector_safe_label",
            "transformers_detector_threshold",
            "transformers_detector_mode",
        ]
    ) and all(item["present"] for item in pi_detector_markers.values())

    baselines = {
        "agentdojo_tool_filter": _baseline_record(
            baseline_id="agentdojo_tool_filter",
            official_defense="tool_filter",
            source_files=[OFFICIAL_FILES["pipeline"], OFFICIAL_FILES["benchmark_script"]],
            blockers=_tool_filter_blockers(probe, tool_filter_markers_ok),
            command_template=(
                "cd external\\benchmarks\\agentdojo\n"
                "python -m agentdojo.scripts.benchmark --model gpt-4o-2024-05-13 "
                "--defense tool_filter --attack tool_knowledge"
            ),
            compatibility_plan=[
                "2-case local OpenAI-compatible qualification has passed with a disclosed model-binding shim when the qualification manifest is present",
                "run the frozen 726-case formal matrix with the same official AgentDojo pipeline, shim disclosure, provider/model labels and complete official output paths",
                "keep any further non-identical tool-filter clone under a separate non-official adapter label",
            ],
            ready_status=(
                "ready_official_tool_filter_qualification_completed_formal_run_pending"
                if probe.get("tool_filter_qualification_completed")
                and probe.get("tool_filter_security_qualification_completed")
                else "ready_for_official_smoke_pending_run"
            ),
        ),
        "agentdojo_transformers_pi_detector": _baseline_record(
            baseline_id="agentdojo_transformers_pi_detector",
            official_defense="transformers_pi_detector",
            source_files=[
                OFFICIAL_FILES["pipeline"],
                OFFICIAL_FILES["pi_detector"],
                OFFICIAL_FILES["benchmark_script"],
            ],
            blockers=_transformers_detector_blockers(probe, transformer_markers_ok),
            command_template=(
                "cd external\\benchmarks\\agentdojo\n"
                "python -m agentdojo.scripts.benchmark --model gpt-4o-2024-05-13 "
                "--defense transformers_pi_detector --attack tool_knowledge"
            ),
            compatibility_plan=[
                "use the dedicated E-drive runtime smoke environment or a separately frozen AgentDojo transformers environment",
                "keep the ProtectAI detector model cache path/hash and threshold frozen before formal runs",
                "run official AgentDojo logs first, then separately compare against M3 outputs",
            ],
        ),
    }

    local_condition_ids = set(DEFENSE_CONDITIONS)
    official_baseline_ids_in_m3_runner = sorted(OFFICIAL_STRONG_BASELINE_IDS & local_condition_ids)
    checks: list[dict[str, Any]] = [
        _check(
            "official_source_files_exist",
            all(info["exists"] for info in files.values()),
            detail={label: info["exists"] for label, info in files.items()},
        ),
        _check(
            "official_defenses_list_contains_required_strong_baselines",
            REQUIRED_OFFICIAL_DEFENSES <= official_defenses,
            detail={"official_defenses": sorted(official_defenses)},
        ),
        _check(
            "pipeline_markers_present",
            all(item["present"] for item in pipeline_markers.values()),
            detail=pipeline_markers,
        ),
        _check(
            "pi_detector_markers_present",
            all(item["present"] for item in pi_detector_markers.values()),
            detail=pi_detector_markers,
        ),
        _check(
            "readme_benchmark_command_markers_present",
            all(item["present"] for item in readme_markers.values()),
            detail=readme_markers,
        ),
        _check(
            "dependency_probe_completed",
            all(key in probe for key in [
                "openai_package_installed",
                "transformers_installed",
                "torch_installed",
                "protectai_detector_cached",
                "transformers_runtime_ready",
                "tool_filter_transport_ready",
            ]),
            detail=probe,
        ),
        _check(
            "blocked_or_pending_baselines_not_result_eligible",
            all(not row["result_eligible_for_formal_tables"] for row in baselines.values()),
            detail={key: row["result_eligible_for_formal_tables"] for key, row in baselines.items()},
        ),
        _check(
            "official_command_templates_recorded",
            all(row["official_defense"] in row["official_run_command_template"] for row in baselines.values()),
            detail={key: row["official_run_command_template"] for key, row in baselines.items()},
        ),
        _check(
            "official_strong_baselines_not_mixed_into_m3_local_runner",
            not official_baseline_ids_in_m3_runner,
            detail={
                "official_baseline_ids_in_m3_runner": official_baseline_ids_in_m3_runner,
                "m3_runner_condition_ids": sorted(local_condition_ids),
            },
        ),
    ]
    passed = sum(1 for check in checks if check["status"] == "pass")
    error_failures = [
        check
        for check in checks
        if check["status"] != "pass" and check.get("severity") == "error"
    ]
    audit = {
        "schema_version": "paper-agentdojo-official-strong-baseline-capability-audit-1.0",
        "audit_version": AUDIT_VERSION,
        "status": "completed" if not error_failures else "failed",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "agentdojo_checkout": _path(agentdojo_checkout),
        "official_source_files": files,
        "official_source_manifest_sha256": rows_sha256(
            [
                {
                    "label": label,
                    "relative_path": info["relative_path"],
                    "sha256": info["sha256"],
                }
                for label, info in files.items()
            ]
        ),
        "official_defenses": sorted(official_defenses),
        "pipeline_markers": pipeline_markers,
        "pi_detector_markers": pi_detector_markers,
        "readme_markers": readme_markers,
        "dependency_probe": probe,
        "baselines": baselines,
        "checks": checks,
        "checks_sha256": rows_sha256(checks),
        "total_checks": len(checks),
        "passed_checks": passed,
        "error_failures": error_failures,
        "q2_strong_baseline_gate": "not_satisfied",
        "result_eligible_for_formal_tables": False,
        "boundary": (
            "Capability audit only. It confirms pinned official source markers "
            "and local blockers for AgentDojo's tool_filter and "
            "transformers_pi_detector. It is not a benchmark result and must not "
            "be included in formal ASR/TCR effect tables."
        ),
    }
    audit = portable_value(audit, root=ROOT)
    json_path = output_dir / f"{AUDIT_STEM}.json"
    md_path = output_dir / f"{AUDIT_STEM}.md"
    _write_json(json_path, audit)
    _write_markdown(md_path, audit)
    audit["json_path"] = _path(json_path)
    audit["markdown_path"] = _path(md_path)
    return audit


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
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
    audit = build_agentdojo_official_strong_baseline_audit(
        agentdojo_checkout=args.agentdojo_checkout,
        output_dir=args.output_dir,
        hf_hub_cache=args.hf_hub_cache,
        transformers_smoke_manifest=args.transformers_smoke_manifest,
        tool_filter_freeze=args.tool_filter_freeze,
    )
    print(json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
