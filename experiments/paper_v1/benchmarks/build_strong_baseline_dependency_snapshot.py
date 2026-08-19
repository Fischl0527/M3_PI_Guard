"""Build a frozen dependency/source snapshot for required strong baselines.

This snapshot is deliberately non-experimental.  It records the local state
that blocks or enables source-backed baseline work:

* Python package availability;
* selected model caches;
* local source checkouts and their Git HEADs;
* whether local checkouts match the remote HEADs already recorded in the
  external strong-baseline registry.

It does not install packages, download models, clone repositories, start model
services, call APIs or run baselines.  The output is an auditable input to the
strong-baseline formal-readiness gate, not a baseline result.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .common import huggingface_model_cache_probe, portable_value, rows_sha256, sha256_file


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_EXTERNAL_REGISTRY = (
    ROOT / "protocols" / "paper_upgrade_v1" / "external_strong_baselines_v1.json"
)
DEFAULT_OUTPUT = ROOT / "protocols" / "paper_upgrade_v1"
DEFAULT_BASELINE_ROOT = ROOT / "external" / "baselines"
DEFAULT_CAMEL_FIDES_PREFLIGHT = (
    ROOT / "protocols" / "paper_upgrade_v1" / "camel_fides_ifc_adapter_preflight_v1.json"
)
DEFAULT_CAMEL_SOURCE_SMOKE = (
    ROOT / "protocols" / "paper_upgrade_v1" / "camel_official_source_smoke_v1.json"
)
DEFAULT_CAMEL_SOURCE_BACKED_IMPORT = (
    ROOT
    / "protocols"
    / "paper_upgrade_v1"
    / "camel_source_backed_import_preflight_v1.json"
)
DEFAULT_CAMEL_SOURCE_BACKED_COMPAT = (
    ROOT
    / "protocols"
    / "paper_upgrade_v1"
    / "camel_source_backed_compat_preflight_v1.json"
)
DEFAULT_CAMEL_SOURCE_BACKED_RUNNER = (
    ROOT
    / "protocols"
    / "paper_upgrade_v1"
    / "camel_source_backed_runner_preflight_v1.json"
)
DEFAULT_CAMEL_TRANSPORT_MAPPING = (
    ROOT / "protocols" / "paper_upgrade_v1" / "camel_transport_mapping_preflight_v1.json"
)
DEFAULT_CAMEL_SOURCE_BACKED_FREEZE = (
    ROOT
    / "protocols"
    / "paper_upgrade_v1"
    / "camel_source_backed_formal_freeze_v3.json"
)
DEFAULT_IPIGUARD_TDG_PREFLIGHT = (
    ROOT / "protocols" / "paper_upgrade_v1" / "ipiguard_tdg_adapter_preflight_v1.json"
)
DEFAULT_IPIGUARD_SOURCE_SMOKE = (
    ROOT / "protocols" / "paper_upgrade_v1" / "ipiguard_official_source_smoke_v1.json"
)
DEFAULT_IPIGUARD_SOURCE_BACKED_IMPORT = (
    ROOT
    / "protocols"
    / "paper_upgrade_v1"
    / "ipiguard_source_backed_import_preflight_v1.json"
)
DEFAULT_PROGENT_SOURCE_SMOKE = (
    ROOT / "protocols" / "paper_upgrade_v1" / "progent_official_source_smoke_v1.json"
)
DEFAULT_PROGENT_SOURCE_BACKED_FREEZE = (
    ROOT
    / "protocols"
    / "paper_upgrade_v1"
    / "progent_source_backed_formal_freeze_v1.json"
)
DEFAULT_PROGENT_SOURCE_BACKED_IMPORT = (
    ROOT
    / "protocols"
    / "paper_upgrade_v1"
    / "progent_source_backed_import_preflight_v1.json"
)
DEFAULT_TASKSHIELD_PAPER_FREEZE = (
    ROOT
    / "protocols"
    / "paper_upgrade_v1"
    / "taskshield_paper_formal_freeze_v14.json"
)
DEFAULT_TASKSHIELD_PAPER_IMPORT = (
    ROOT
    / "protocols"
    / "paper_upgrade_v1"
    / "taskshield_paper_import_preflight_v1.json"
)
DEFAULT_PROMPTGUARD_PREFLIGHT = (
    ROOT / "protocols" / "paper_upgrade_v1" / "promptguard_detector_adapter_preflight_v1.json"
)
DEFAULT_PROMPTGUARD_FORMAL_ANALYSIS = (
    ROOT
    / "outputs"
    / "paper_upgrade_v1"
    / "baselines"
    / "promptguard_detector_formal_v1"
    / "analysis"
    / "analysis_manifest.json"
)
SNAPSHOT_VERSION = "m3-paper-v1-strong-baseline-dependency-snapshot-1.0"
SNAPSHOT_STEM = "strong_baseline_dependency_snapshot_v1"

REQUIRED_KEYS = {
    "promptguard",
    "task_shield",
    "ipiguard",
    "progent",
    "camel_or_fides",
}
LOCAL_CHECKOUT_BY_ENTRY_ID = {
    "promptguard_llama_prompt_guard_2": "PurpleLlama",
    "ipiguard_github_emnlp2025": "ipiguard",
    "progent_arxiv2025": "progent",
    "camel_google_research": "camel-prompt-injection",
    "fides_microsoft": "fides",
}
PROMPTGUARD_MODEL_IDS = (
    "meta-llama/Llama-Prompt-Guard-2-86M",
    "meta-llama/Llama-Prompt-Guard-2-22M",
)
PACKAGE_NAMES = (
    "transformers",
    "torch",
    "huggingface_hub",
    "openai",
    "numpy",
    "pandas",
)


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


def _entries(registry: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = registry.get("entries")
    if not isinstance(rows, list):
        raise ValueError("external strong-baseline registry missing entries list")
    return [dict(row) for row in rows if isinstance(row, Mapping)]


def _repository_reference(entry: Mapping[str, Any]) -> dict[str, Any] | None:
    references = entry.get("secondary_references")
    if not isinstance(references, list):
        return None
    for item in references:
        if isinstance(item, Mapping) and item.get("kind") == "repository":
            return dict(item)
    return None


def _git_head(path: Path) -> str:
    if not (path / ".git").exists():
        return ""
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception:
        return ""
    return result.stdout.strip()


def _package_probe(
    *,
    hf_hub_cache: Path | None = None,
    promptguard_environment_snapshot: Path | None = None,
    promptguard_download_snapshot: Path | None = None,
) -> dict[str, Any]:
    packages: dict[str, Any] = {}
    for name in PACKAGE_NAMES:
        spec = importlib.util.find_spec(name)
        packages[name] = {"installed": spec is not None, "origin": spec.origin if spec else ""}
    environment = _read_optional_json(promptguard_environment_snapshot) if promptguard_environment_snapshot else {}
    selected = environment.get("selected_packages", {})
    selected = selected if isinstance(selected, Mapping) else {}
    package_aliases = {"huggingface_hub": "huggingface-hub"}
    if environment.get("status") == "passed":
        for name in ("transformers", "torch", "huggingface_hub"):
            selected_name = package_aliases.get(name, name)
            version = str(selected.get(selected_name, ""))
            if version:
                packages[name] = {
                    "installed": True,
                    "origin": "promptguard_environment_snapshot",
                    "version": version,
                }
    download = _read_optional_json(promptguard_download_snapshot) if promptguard_download_snapshot else {}
    return {
        "python_executable": sys.executable,
        "python_version": sys.version.split()[0],
        "packages": packages,
        "executables": {
            "git": shutil.which("git") or "",
            "uv": shutil.which("uv") or "",
        },
        "promptguard_model_cache": {
            model_id: huggingface_model_cache_probe(model_id, hub_cache=hf_hub_cache)
            for model_id in PROMPTGUARD_MODEL_IDS
        },
        "promptguard_environment_snapshot": {
            "path": str(promptguard_environment_snapshot) if promptguard_environment_snapshot else "",
            "sha256": sha256_file(promptguard_environment_snapshot)
            if promptguard_environment_snapshot and promptguard_environment_snapshot.exists()
            else "",
            "status": environment.get("status", "missing"),
            "python_executable": environment.get("python_executable", ""),
            "selected_packages": dict(selected),
        },
        "promptguard_download_snapshot": {
            "path": str(promptguard_download_snapshot) if promptguard_download_snapshot else "",
            "sha256": sha256_file(promptguard_download_snapshot)
            if promptguard_download_snapshot and promptguard_download_snapshot.exists()
            else "",
            "status": download.get("status", "missing"),
            "resolved_revision": download.get("resolved_revision", ""),
            "retry_performed": download.get("retry_performed"),
            "blocker": download.get("blocker", ""),
        },
    }


def _source_snapshot_for_entry(
    entry: Mapping[str, Any],
    *,
    baseline_root: Path,
) -> dict[str, Any]:
    entry_id = str(entry.get("id", ""))
    repo = _repository_reference(entry)
    checkout_name = LOCAL_CHECKOUT_BY_ENTRY_ID.get(entry_id, "")
    local_path = baseline_root / checkout_name if checkout_name else None
    local_exists = bool(local_path and local_path.exists())
    local_head = _git_head(local_path) if local_path and local_exists else ""
    expected_head = str(repo.get("remote_head_sha", "")) if repo else ""
    relevant_path = str(repo.get("relevant_path", "")) if repo else ""
    relevant_path_exists = bool(
        local_path and relevant_path and (local_path / relevant_path).exists()
    )
    return {
        "entry_id": entry_id,
        "registry_key": str(entry.get("registry_key", "")),
        "display_name": str(entry.get("display_name", "")),
        "repository_url": str(repo.get("url", "")) if repo else "",
        "expected_remote_head_sha": expected_head,
        "expected_remote_head_observed_at": str(repo.get("remote_head_observed_at", "")) if repo else "",
        "local_path": str(local_path) if local_path else "",
        "local_checkout_expected": bool(checkout_name),
        "local_checkout_exists": local_exists,
        "local_git_head": local_head,
        "local_head_matches_expected": bool(local_head and expected_head and local_head == expected_head),
        "relevant_path": relevant_path,
        "relevant_path_exists": relevant_path_exists,
        "source_snapshot_status": (
            "source_checkout_matched"
            if local_head and expected_head and local_head == expected_head
            else "source_checkout_missing"
            if checkout_name and not local_exists
            else "source_checkout_mismatch_or_not_git"
            if checkout_name
            else "paper_or_model_card_only_no_checkout_expected"
        ),
    }


def _adapter_preflight_snapshots() -> dict[str, dict[str, Any]]:
    promptguard = _read_optional_json(DEFAULT_PROMPTGUARD_PREFLIGHT)
    promptguard_formal = _read_optional_json(DEFAULT_PROMPTGUARD_FORMAL_ANALYSIS)
    camel = _read_optional_json(DEFAULT_CAMEL_FIDES_PREFLIGHT)
    camel_source_smoke = _read_optional_json(DEFAULT_CAMEL_SOURCE_SMOKE)
    camel_source_backed_import = _read_optional_json(DEFAULT_CAMEL_SOURCE_BACKED_IMPORT)
    camel_source_backed_compat = _read_optional_json(DEFAULT_CAMEL_SOURCE_BACKED_COMPAT)
    camel_source_backed_runner = _read_optional_json(DEFAULT_CAMEL_SOURCE_BACKED_RUNNER)
    camel_transport_mapping = _read_optional_json(DEFAULT_CAMEL_TRANSPORT_MAPPING)
    camel_source_backed_freeze = _read_optional_json(DEFAULT_CAMEL_SOURCE_BACKED_FREEZE)
    ipiguard_preflight = _read_optional_json(DEFAULT_IPIGUARD_TDG_PREFLIGHT)
    ipiguard_source_smoke = _read_optional_json(DEFAULT_IPIGUARD_SOURCE_SMOKE)
    ipiguard_source_backed_import = _read_optional_json(
        DEFAULT_IPIGUARD_SOURCE_BACKED_IMPORT
    )
    progent_source_smoke = _read_optional_json(DEFAULT_PROGENT_SOURCE_SMOKE)
    progent_source_backed_freeze = _read_optional_json(
        DEFAULT_PROGENT_SOURCE_BACKED_FREEZE
    )
    progent_source_backed_import = _read_optional_json(
        DEFAULT_PROGENT_SOURCE_BACKED_IMPORT
    )
    taskshield_paper_freeze = _read_optional_json(DEFAULT_TASKSHIELD_PAPER_FREEZE)
    taskshield_paper_import = _read_optional_json(DEFAULT_TASKSHIELD_PAPER_IMPORT)
    return {
        "promptguard": {
            "path": str(DEFAULT_PROMPTGUARD_PREFLIGHT),
            "sha256": sha256_file(DEFAULT_PROMPTGUARD_PREFLIGHT)
            if DEFAULT_PROMPTGUARD_PREFLIGHT.exists()
            else "",
            "status": promptguard.get("status", "missing"),
            "real_detector_ready": bool(promptguard.get("real_detector_ready")),
            "real_smoke_completed": bool(
                promptguard.get("real_detector_smoke", {}).get("completed")
            )
            if isinstance(promptguard.get("real_detector_smoke"), Mapping)
            else False,
            "real_smoke_sha256": promptguard.get("real_detector_smoke", {}).get(
                "sha256", ""
            )
            if isinstance(promptguard.get("real_detector_smoke"), Mapping)
            else "",
            "formal_result_eligible": bool(
                promptguard.get("result_eligible_for_formal_tables")
            ),
            "formal_analysis_path": str(DEFAULT_PROMPTGUARD_FORMAL_ANALYSIS),
            "formal_analysis_sha256": sha256_file(DEFAULT_PROMPTGUARD_FORMAL_ANALYSIS)
            if DEFAULT_PROMPTGUARD_FORMAL_ANALYSIS.exists()
            else "",
            "formal_analysis_status": promptguard_formal.get("status", "missing"),
            "formal_detector_result_eligible": bool(
                promptguard_formal.get("result_eligible_for_formal_tables")
            ),
            "formal_detector_scope": promptguard_formal.get("eligible_table_scope", []),
            "formal_detector_case_count": promptguard_formal.get("summary", {}).get("n", 0)
            if isinstance(promptguard_formal.get("summary"), Mapping)
            else 0,
        },
        "task_shield": {
            "paper_freeze_path": str(DEFAULT_TASKSHIELD_PAPER_FREEZE),
            "paper_freeze_sha256": sha256_file(DEFAULT_TASKSHIELD_PAPER_FREEZE)
            if DEFAULT_TASKSHIELD_PAPER_FREEZE.exists()
            else "",
            "paper_freeze_status": taskshield_paper_freeze.get("status", "missing"),
            "paper_freeze_version": taskshield_paper_freeze.get("freeze_version", ""),
            "paper_freeze_passed_checks": taskshield_paper_freeze.get("passed_checks", 0),
            "paper_freeze_total_checks": taskshield_paper_freeze.get("total_checks", 0),
            "paper_freeze_case_count": taskshield_paper_freeze.get(
                "case_counts", {}
            ).get("total", 0)
            if isinstance(taskshield_paper_freeze.get("case_counts"), Mapping)
            else 0,
            "paper_reproduction_classification": taskshield_paper_freeze.get(
                "task_shield", {}
            ).get("classification", "")
            if isinstance(taskshield_paper_freeze.get("task_shield"), Mapping)
            else "",
            "paper_freeze_formal_result_eligible": bool(
                taskshield_paper_freeze.get("result_eligible_for_formal_tables")
            ),
            "paper_import_path": str(DEFAULT_TASKSHIELD_PAPER_IMPORT),
            "paper_import_sha256": sha256_file(DEFAULT_TASKSHIELD_PAPER_IMPORT)
            if DEFAULT_TASKSHIELD_PAPER_IMPORT.exists()
            else "",
            "paper_import_status": taskshield_paper_import.get("status", "missing"),
            "paper_import_passed_checks": taskshield_paper_import.get(
                "passed_checks", 0
            ),
            "paper_import_total_checks": taskshield_paper_import.get(
                "total_checks", 0
            ),
            "paper_import_network_calls": bool(
                taskshield_paper_import.get("network_calls_performed")
            ),
            "paper_import_formal_result_eligible": bool(
                taskshield_paper_import.get("result_eligible_for_formal_tables")
            ),
        },
        "ipiguard": {
            "tdg_preflight_path": str(DEFAULT_IPIGUARD_TDG_PREFLIGHT),
            "tdg_preflight_sha256": sha256_file(DEFAULT_IPIGUARD_TDG_PREFLIGHT)
            if DEFAULT_IPIGUARD_TDG_PREFLIGHT.exists()
            else "",
            "tdg_preflight_status": ipiguard_preflight.get("status", "missing"),
            "tdg_preflight_source_checkout_ready": bool(
                ipiguard_preflight.get("source_checkout_ready")
            ),
            "source_smoke_path": str(DEFAULT_IPIGUARD_SOURCE_SMOKE),
            "source_smoke_sha256": sha256_file(DEFAULT_IPIGUARD_SOURCE_SMOKE)
            if DEFAULT_IPIGUARD_SOURCE_SMOKE.exists()
            else "",
            "source_smoke_status": ipiguard_source_smoke.get("status", "missing"),
            "source_smoke_passed_checks": ipiguard_source_smoke.get(
                "summary", {}
            ).get("passed_checks", 0)
            if isinstance(ipiguard_source_smoke.get("summary"), Mapping)
            else 0,
            "source_smoke_total_checks": ipiguard_source_smoke.get(
                "summary", {}
            ).get("total_checks", 0)
            if isinstance(ipiguard_source_smoke.get("summary"), Mapping)
            else 0,
            "source_smoke_formal_result_eligible": bool(
                ipiguard_source_smoke.get("result_eligible_for_formal_tables")
            ),
            "source_backed_import_path": str(DEFAULT_IPIGUARD_SOURCE_BACKED_IMPORT),
            "source_backed_import_sha256": sha256_file(
                DEFAULT_IPIGUARD_SOURCE_BACKED_IMPORT
            )
            if DEFAULT_IPIGUARD_SOURCE_BACKED_IMPORT.exists()
            else "",
            "source_backed_import_status": ipiguard_source_backed_import.get(
                "status", "missing"
            ),
            "source_backed_import_passed_checks": ipiguard_source_backed_import.get(
                "passed_checks", 0
            ),
            "source_backed_import_total_checks": ipiguard_source_backed_import.get(
                "total_checks", 0
            ),
            "source_backed_import_network_calls": bool(
                ipiguard_source_backed_import.get("network_calls_performed")
            ),
            "source_backed_import_formal_result_eligible": bool(
                ipiguard_source_backed_import.get(
                    "result_eligible_for_formal_tables"
                )
            ),
        },
        "progent": {
            "source_smoke_path": str(DEFAULT_PROGENT_SOURCE_SMOKE),
            "source_smoke_sha256": sha256_file(DEFAULT_PROGENT_SOURCE_SMOKE)
            if DEFAULT_PROGENT_SOURCE_SMOKE.exists()
            else "",
            "source_smoke_status": progent_source_smoke.get("status", "missing"),
            "source_checkout_ready": bool(
                progent_source_smoke.get("source_checkout", {}).get(
                    "matches_expected_commit"
                )
            )
            if isinstance(progent_source_smoke.get("source_checkout"), Mapping)
            else False,
            "offline_runtime_smoke_passed": bool(
                progent_source_smoke.get("offline_runtime_smoke", {}).get("passed")
            )
            if isinstance(progent_source_smoke.get("offline_runtime_smoke"), Mapping)
            else False,
            "network_calls_performed": bool(
                progent_source_smoke.get("network_calls_performed")
            ),
            "formal_result_eligible": bool(
                progent_source_smoke.get("result_eligible_for_formal_tables")
            ),
            "source_backed_freeze_path": str(DEFAULT_PROGENT_SOURCE_BACKED_FREEZE),
            "source_backed_freeze_sha256": sha256_file(
                DEFAULT_PROGENT_SOURCE_BACKED_FREEZE
            )
            if DEFAULT_PROGENT_SOURCE_BACKED_FREEZE.exists()
            else "",
            "source_backed_freeze_status": progent_source_backed_freeze.get(
                "status", "missing"
            ),
            "source_backed_freeze_version": progent_source_backed_freeze.get(
                "freeze_version", ""
            ),
            "source_backed_freeze_case_count": progent_source_backed_freeze.get(
                "case_counts", {}
            ).get("total", 0)
            if isinstance(progent_source_backed_freeze.get("case_counts"), Mapping)
            else 0,
            "source_backed_freeze_passed_checks": progent_source_backed_freeze.get(
                "passed_checks", 0
            ),
            "source_backed_freeze_total_checks": progent_source_backed_freeze.get(
                "total_checks", 0
            ),
            "source_backed_freeze_formal_result_eligible": bool(
                progent_source_backed_freeze.get("result_eligible_for_formal_tables")
            ),
            "source_backed_import_path": str(DEFAULT_PROGENT_SOURCE_BACKED_IMPORT),
            "source_backed_import_sha256": sha256_file(
                DEFAULT_PROGENT_SOURCE_BACKED_IMPORT
            )
            if DEFAULT_PROGENT_SOURCE_BACKED_IMPORT.exists()
            else "",
            "source_backed_import_status": progent_source_backed_import.get(
                "status", "missing"
            ),
            "source_backed_import_passed_checks": progent_source_backed_import.get(
                "passed_checks", 0
            ),
            "source_backed_import_total_checks": progent_source_backed_import.get(
                "total_checks", 0
            ),
            "source_backed_import_network_calls": bool(
                progent_source_backed_import.get("network_calls_performed")
            ),
            "source_backed_import_formal_result_eligible": bool(
                progent_source_backed_import.get("result_eligible_for_formal_tables")
            ),
        },
        "camel_or_fides": {
            "path": str(DEFAULT_CAMEL_FIDES_PREFLIGHT),
            "sha256": sha256_file(DEFAULT_CAMEL_FIDES_PREFLIGHT)
            if DEFAULT_CAMEL_FIDES_PREFLIGHT.exists()
            else "",
            "status": camel.get("status", "missing"),
            "method_selected": bool(camel.get("method_selected")),
            "selected_candidate": camel.get("config", {}).get("selected_candidate", "")
            if isinstance(camel.get("config"), Mapping)
            else "",
            "source_checkout_ready": bool(camel.get("source_checkout_ready")),
            "source_smoke_path": str(DEFAULT_CAMEL_SOURCE_SMOKE),
            "source_smoke_sha256": sha256_file(DEFAULT_CAMEL_SOURCE_SMOKE)
            if DEFAULT_CAMEL_SOURCE_SMOKE.exists()
            else "",
            "source_smoke_status": camel_source_smoke.get("status", "missing"),
            "source_smoke_passed_checks": camel_source_smoke.get("passed_checks", 0),
            "source_smoke_total_checks": camel_source_smoke.get("total_checks", 0),
            "source_smoke_network_calls": bool(
                camel_source_smoke.get("network_calls_performed")
            ),
            "source_smoke_formal_result_eligible": bool(
                camel_source_smoke.get("result_eligible_for_formal_tables")
            ),
            "source_backed_import_path": str(DEFAULT_CAMEL_SOURCE_BACKED_IMPORT),
            "source_backed_import_sha256": sha256_file(
                DEFAULT_CAMEL_SOURCE_BACKED_IMPORT
            )
            if DEFAULT_CAMEL_SOURCE_BACKED_IMPORT.exists()
            else "",
            "source_backed_import_status": camel_source_backed_import.get(
                "status", "missing"
            ),
            "source_backed_import_passed_checks": camel_source_backed_import.get(
                "passed_checks", 0
            ),
            "source_backed_import_total_checks": camel_source_backed_import.get(
                "total_checks", 0
            ),
            "source_backed_import_network_attempt_rows": camel_source_backed_import.get(
                "summary", {}
            ).get("network_attempt_rows", 0)
            if isinstance(camel_source_backed_import.get("summary"), Mapping)
            else 0,
            "source_backed_import_formal_result_eligible": bool(
                camel_source_backed_import.get("result_eligible_for_formal_tables")
            ),
            "source_backed_import_qualification_blockers": camel_source_backed_import.get(
                "qualification_blockers", []
            )
            if isinstance(camel_source_backed_import.get("qualification_blockers"), list)
            else [],
            "source_backed_compat_path": str(DEFAULT_CAMEL_SOURCE_BACKED_COMPAT),
            "source_backed_compat_sha256": sha256_file(DEFAULT_CAMEL_SOURCE_BACKED_COMPAT)
            if DEFAULT_CAMEL_SOURCE_BACKED_COMPAT.exists()
            else "",
            "source_backed_compat_status": camel_source_backed_compat.get(
                "status", "missing"
            ),
            "source_backed_compat_passed_checks": camel_source_backed_compat.get(
                "passed_checks", 0
            ),
            "source_backed_compat_total_checks": camel_source_backed_compat.get(
                "total_checks", 0
            ),
            "source_backed_compat_network_attempted": bool(
                camel_source_backed_compat.get("summary", {}).get("network_attempted", True)
            )
            if isinstance(camel_source_backed_compat.get("summary"), Mapping)
            else True,
            "source_backed_compat_formal_result_eligible": bool(
                camel_source_backed_compat.get("result_eligible_for_formal_tables")
            ),
            "source_backed_compat_qualification_blockers": camel_source_backed_compat.get(
                "qualification_blockers", []
            )
            if isinstance(camel_source_backed_compat.get("qualification_blockers"), list)
            else [],
            "source_backed_runner_path": str(DEFAULT_CAMEL_SOURCE_BACKED_RUNNER),
            "source_backed_runner_sha256": sha256_file(DEFAULT_CAMEL_SOURCE_BACKED_RUNNER)
            if DEFAULT_CAMEL_SOURCE_BACKED_RUNNER.exists()
            else "",
            "source_backed_runner_status": camel_source_backed_runner.get(
                "status", "missing"
            ),
            "source_backed_runner_passed_checks": camel_source_backed_runner.get(
                "passed_checks", 0
            ),
            "source_backed_runner_total_checks": camel_source_backed_runner.get(
                "total_checks", 0
            ),
            "source_backed_runner_benchmark_case_count": camel_source_backed_runner.get(
                "benchmark_case_count", -1
            ),
            "source_backed_runner_model_or_api_calls": camel_source_backed_runner.get(
                "model_or_api_calls", -1
            ),
            "source_backed_runner_network_attempted": bool(
                camel_source_backed_runner.get("network_attempted")
            ),
            "source_backed_runner_formal_result_eligible": bool(
                camel_source_backed_runner.get("result_eligible_for_formal_tables")
            ),
            "source_backed_runner_suites_constructed": camel_source_backed_runner.get(
                "suites_constructed", []
            )
            if isinstance(camel_source_backed_runner.get("suites_constructed"), list)
            else [],
            "source_backed_runner_qualification_blockers": camel_source_backed_runner.get(
                "qualification_blockers", []
            )
            if isinstance(camel_source_backed_runner.get("qualification_blockers"), list)
            else [],
            "transport_mapping_path": str(DEFAULT_CAMEL_TRANSPORT_MAPPING),
            "transport_mapping_sha256": sha256_file(DEFAULT_CAMEL_TRANSPORT_MAPPING)
            if DEFAULT_CAMEL_TRANSPORT_MAPPING.exists()
            else "",
            "transport_mapping_status": camel_transport_mapping.get(
                "status", "missing"
            ),
            "transport_mapping_passed_checks": camel_transport_mapping.get(
                "passed_checks", 0
            ),
            "transport_mapping_total_checks": camel_transport_mapping.get(
                "total_checks", 0
            ),
            "transport_mapping_benchmark_case_count": camel_transport_mapping.get(
                "benchmark_case_count", -1
            ),
            "transport_mapping_model_or_api_calls": camel_transport_mapping.get(
                "model_or_api_calls", -1
            ),
            "transport_mapping_network_attempted": bool(
                camel_transport_mapping.get("network_attempted")
            ),
            "transport_mapping_formal_result_eligible": bool(
                camel_transport_mapping.get("result_eligible_for_formal_tables")
            ),
            "transport_mapping_suites_mapped": camel_transport_mapping.get(
                "suites_mapped", []
            )
            if isinstance(camel_transport_mapping.get("suites_mapped"), list)
            else [],
            "source_backed_freeze_path": str(DEFAULT_CAMEL_SOURCE_BACKED_FREEZE),
            "source_backed_freeze_sha256": sha256_file(DEFAULT_CAMEL_SOURCE_BACKED_FREEZE)
            if DEFAULT_CAMEL_SOURCE_BACKED_FREEZE.exists()
            else "",
            "source_backed_freeze_status": camel_source_backed_freeze.get(
                "status", "missing"
            ),
            "source_backed_freeze_case_count": camel_source_backed_freeze.get(
                "case_counts", {}
            ).get("total", 0)
            if isinstance(camel_source_backed_freeze.get("case_counts"), Mapping)
            else 0,
            "source_backed_freeze_passed_checks": camel_source_backed_freeze.get(
                "passed_checks", 0
            ),
            "source_backed_freeze_total_checks": camel_source_backed_freeze.get(
                "total_checks", 0
            ),
            "source_backed_freeze_formal_result_eligible": bool(
                camel_source_backed_freeze.get("result_eligible_for_formal_tables")
            ),
            "source_backed_freeze_qualification_blockers": camel_source_backed_freeze.get(
                "qualification_blockers", []
            )
            if isinstance(camel_source_backed_freeze.get("qualification_blockers"), list)
            else [],
        }
    }


def _key_readiness(
    *,
    key: str,
    entries: list[dict[str, Any]],
    sources: Mapping[str, Mapping[str, Any]],
    probe: Mapping[str, Any],
    adapter_preflights: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    blockers: list[str] = []
    entry_ids = [str(entry.get("id", "")) for entry in entries]
    packages = probe.get("packages", {}) if isinstance(probe.get("packages"), Mapping) else {}
    caches = probe.get("promptguard_model_cache", {})
    cache_any = any(
        isinstance(item, Mapping) and bool(item.get("model_cache_complete"))
        for item in caches.values()
    ) if isinstance(caches, Mapping) else False

    if key == "promptguard":
        promptguard_snapshot = adapter_preflights.get("promptguard", {})
        formal_detector_completed = (
            promptguard_snapshot.get("formal_analysis_status")
            == "completed_source_backed_formal_detector_baseline"
            and bool(promptguard_snapshot.get("formal_detector_result_eligible"))
        )
        if not formal_detector_completed:
            if not packages.get("transformers", {}).get("installed"):
                blockers.append("transformers_missing")
            if not packages.get("torch", {}).get("installed"):
                blockers.append("torch_missing")
            if not cache_any:
                blockers.append("promptguard_model_cache_missing")
            download_status = probe.get("promptguard_download_snapshot", {}).get("status")
            if download_status == "blocked_gated_repository":
                blockers.append("promptguard_model_access_gated")
            if not promptguard_snapshot.get("real_detector_ready"):
                blockers.append("promptguard_real_detector_not_ready")
            if not promptguard_snapshot.get("real_smoke_completed"):
                blockers.append("promptguard_real_smoke_missing_or_failed")
        if promptguard_snapshot.get("formal_result_eligible"):
            blockers.append("promptguard_qualification_smoke_marked_formal_eligible")
        if not formal_detector_completed:
            blockers.append("promptguard_formal_detector_result_missing_or_ineligible")
    elif key in {"ipiguard", "camel_or_fides"}:
        matched = [
            entry_id
            for entry_id in entry_ids
            if sources.get(entry_id, {}).get("local_head_matches_expected")
        ]
        if not matched:
            blockers.append("expected_source_checkout_missing_or_mismatch")
        if key == "ipiguard":
            ipiguard_snapshot = adapter_preflights.get("ipiguard", {})
            if ipiguard_snapshot.get("tdg_preflight_status") != "ready_for_official_source_smoke":
                blockers.append("ipiguard_tdg_preflight_not_source_ready")
            if ipiguard_snapshot.get("source_smoke_status") != "completed_source_smoke_only":
                blockers.append("ipiguard_official_source_smoke_missing_or_failed")
            if ipiguard_snapshot.get("source_smoke_formal_result_eligible"):
                blockers.append("ipiguard_source_smoke_marked_formal_eligible")
            if (
                ipiguard_snapshot.get("source_backed_import_status")
                != "completed_import_preflight_only"
            ):
                blockers.append("ipiguard_source_backed_import_preflight_missing_or_failed")
            if ipiguard_snapshot.get("source_backed_import_network_calls"):
                blockers.append("ipiguard_import_preflight_performed_network_calls")
            if ipiguard_snapshot.get("source_backed_import_formal_result_eligible"):
                blockers.append("ipiguard_import_preflight_marked_formal_eligible")
        if key == "camel_or_fides":
            camel_preflight = adapter_preflights.get("camel_or_fides", {})
            if not camel_preflight.get("method_selected"):
                blockers.append("ifc_capability_method_not_selected")
            if (
                camel_preflight.get("source_smoke_status")
                != "completed_source_smoke_only"
            ):
                blockers.append("camel_official_source_smoke_missing_or_failed")
            if camel_preflight.get("source_smoke_network_calls"):
                blockers.append("camel_source_smoke_performed_network_calls")
            if camel_preflight.get("source_smoke_formal_result_eligible"):
                blockers.append("camel_source_smoke_marked_formal_eligible")
            if (
                camel_preflight.get("source_smoke_status")
                != "completed_source_smoke_only"
                and not probe.get("executables", {}).get("uv")
            ):
                blockers.append("uv_missing")
            if camel_preflight.get("source_backed_import_status") not in {
                "completed_dependency_import_preflight",
                "completed_dependency_import_preflight_blocked",
            }:
                blockers.append("camel_source_backed_import_preflight_missing")
            if camel_preflight.get("source_backed_import_network_attempt_rows"):
                blockers.append("camel_import_preflight_performed_network_calls")
            if camel_preflight.get("source_backed_import_formal_result_eligible"):
                blockers.append("camel_import_preflight_marked_formal_eligible")
            compat_ready = (
                camel_preflight.get("source_backed_compat_status")
                == "completed_compat_preflight_only"
                and camel_preflight.get("source_backed_compat_passed_checks")
                == camel_preflight.get("source_backed_compat_total_checks")
                and not camel_preflight.get("source_backed_compat_network_attempted")
                and not camel_preflight.get("source_backed_compat_formal_result_eligible")
            )
            if not compat_ready:
                blockers.append("camel_source_backed_compat_preflight_missing_or_failed")
            if (
                not compat_ready
                and "camel_agentdojo_suite_circular_import_blocks_official_pipeline"
                in set(camel_preflight.get("source_backed_import_qualification_blockers", []))
            ):
                blockers.append(
                    "camel_agentdojo_suite_circular_import_blocks_official_pipeline"
                )
            runner_ready = (
                camel_preflight.get("source_backed_runner_status")
                == "completed_runner_wiring_preflight_only"
                and camel_preflight.get("source_backed_runner_passed_checks")
                == camel_preflight.get("source_backed_runner_total_checks")
                and camel_preflight.get("source_backed_runner_benchmark_case_count") == 0
                and camel_preflight.get("source_backed_runner_model_or_api_calls") == 0
                and not camel_preflight.get("source_backed_runner_network_attempted")
                and not camel_preflight.get("source_backed_runner_formal_result_eligible")
            )
            if not runner_ready:
                blockers.append("camel_source_backed_runner_preflight_missing_or_failed")
            transport_mapping_ready = (
                camel_preflight.get("transport_mapping_status")
                == "completed_transport_and_mapping_preflight_only"
                and camel_preflight.get("transport_mapping_passed_checks")
                == camel_preflight.get("transport_mapping_total_checks")
                and camel_preflight.get("transport_mapping_benchmark_case_count") == 0
                and camel_preflight.get("transport_mapping_model_or_api_calls") == 0
                and not camel_preflight.get("transport_mapping_network_attempted")
                and not camel_preflight.get("transport_mapping_formal_result_eligible")
                and sorted(camel_preflight.get("transport_mapping_suites_mapped", []))
                == ["banking", "slack", "travel", "workspace"]
            )
            if not transport_mapping_ready:
                blockers.append("camel_transport_mapping_preflight_missing_or_failed")
            source_backed_freeze_ready = (
                camel_preflight.get("source_backed_freeze_status")
                == "completed_frozen_formal_protocol"
                and camel_preflight.get("source_backed_freeze_case_count") == 726
                and camel_preflight.get("source_backed_freeze_passed_checks")
                == camel_preflight.get("source_backed_freeze_total_checks")
                and not camel_preflight.get("source_backed_freeze_formal_result_eligible")
            )
            if not source_backed_freeze_ready:
                blockers.append("camel_source_backed_formal_freeze_missing_or_failed")
    elif key == "task_shield":
        taskshield_snapshot = adapter_preflights.get("task_shield", {})
        if (
            taskshield_snapshot.get("paper_freeze_status")
            != "completed_frozen_formal_protocol"
            or taskshield_snapshot.get("paper_freeze_case_count") != 726
        ):
            blockers.append("taskshield_disclosed_reproduction_freeze_missing_or_failed")
        if (
            taskshield_snapshot.get("paper_reproduction_classification")
            != "disclosed_paper_reproduction_not_official_source"
        ):
            blockers.append("taskshield_reproduction_boundary_missing")
        if taskshield_snapshot.get("paper_freeze_formal_result_eligible"):
            blockers.append("taskshield_unexecuted_freeze_marked_formal_eligible")
        if (
            taskshield_snapshot.get("paper_import_status")
            != "completed_import_preflight_only"
        ):
            blockers.append("taskshield_import_preflight_missing_or_failed")
        if taskshield_snapshot.get("paper_import_network_calls"):
            blockers.append("taskshield_import_preflight_performed_network_calls")
        if taskshield_snapshot.get("paper_import_formal_result_eligible"):
            blockers.append("taskshield_import_preflight_marked_formal_eligible")
    elif key == "progent":
        matched = [
            entry_id
            for entry_id in entry_ids
            if sources.get(entry_id, {}).get("local_head_matches_expected")
        ]
        if not matched:
            blockers.append("expected_source_checkout_missing_or_mismatch")
        progent_snapshot = adapter_preflights.get("progent", {})
        if (
            progent_snapshot.get("source_smoke_status")
            != "completed_source_smoke_only"
            or not progent_snapshot.get("offline_runtime_smoke_passed")
        ):
            blockers.append("progent_official_source_smoke_missing_or_failed")
        if progent_snapshot.get("network_calls_performed"):
            blockers.append("progent_source_smoke_performed_network_calls")
        if progent_snapshot.get("formal_result_eligible"):
            blockers.append("progent_source_smoke_marked_formal_eligible")
        if (
            progent_snapshot.get("source_backed_freeze_status")
            != "completed_frozen_formal_protocol"
            or progent_snapshot.get("source_backed_freeze_case_count") != 726
            or progent_snapshot.get("source_backed_freeze_passed_checks")
            != progent_snapshot.get("source_backed_freeze_total_checks")
            or not progent_snapshot.get("source_backed_freeze_total_checks")
        ):
            blockers.append("progent_source_backed_formal_freeze_missing_or_failed")
        if progent_snapshot.get("source_backed_freeze_formal_result_eligible"):
            blockers.append("progent_unexecuted_freeze_marked_formal_eligible")
        if (
            progent_snapshot.get("source_backed_import_status")
            != "completed_import_preflight_only"
        ):
            blockers.append("progent_source_backed_import_preflight_missing_or_failed")
        if progent_snapshot.get("source_backed_import_network_calls"):
            blockers.append("progent_import_preflight_performed_network_calls")
        if progent_snapshot.get("source_backed_import_formal_result_eligible"):
            blockers.append("progent_import_preflight_marked_formal_eligible")
    return {
        "registry_key": key,
        "entry_ids": sorted(entry_ids),
        "snapshot_ready": not blockers,
        "blockers": blockers,
        "result_eligible_for_formal_tables": (
            key == "promptguard"
            and not blockers
            and bool(
                adapter_preflights.get("promptguard", {}).get(
                    "formal_detector_result_eligible"
                )
            )
        ),
    }


def _check(name: str, passed: bool, *, severity: str = "error", detail: Any = None) -> dict[str, Any]:
    return {
        "name": name,
        "status": "pass" if passed else "fail",
        "severity": severity,
        "detail": detail,
    }


def _write_markdown(path: Path, snapshot: Mapping[str, Any]) -> None:
    lines = [
        "# Strong-baseline dependency snapshot v1",
        "",
        f"Generated: {snapshot['created_at']}",
        "",
        "## Result",
        "",
        f"- Status: `{snapshot['status']}`",
        f"- Q2 strong-baseline gate: `{snapshot['q2_strong_baseline_gate']}`",
        f"- Result eligible for formal tables: `{snapshot['result_eligible_for_formal_tables']}`",
        "",
        "## Readiness by registry key",
        "",
        "| Registry key | Snapshot ready | Blockers |",
        "|---|---:|---|",
    ]
    for key, row in snapshot["readiness_by_key"].items():
        blockers = ", ".join(f"`{item}`" for item in row["blockers"]) or "none"
        lines.append(f"| `{key}` | `{row['snapshot_ready']}` | {blockers} |")
    lines.extend(
        [
            "",
            "## Source checkouts",
            "",
            "| Entry | Status | Expected HEAD | Local HEAD |",
            "|---|---|---|---|",
        ]
    )
    for row in snapshot["source_snapshots"].values():
        lines.append(
            f"| `{row['entry_id']}` | `{row['source_snapshot_status']}` | "
            f"`{row['expected_remote_head_sha']}` | `{row['local_git_head']}` |"
        )
    lines.extend(["", "## Checks", "", "| Check | Status | Severity | Detail |", "|---|---|---|---|"])
    for check in snapshot["checks"]:
        detail = json.dumps(check.get("detail"), ensure_ascii=False, sort_keys=True)
        if len(detail) > 220:
            detail = detail[:217] + "..."
        lines.append(
            f"| `{check['name']}` | `{check['status']}` | `{check['severity']}` | {detail.replace('|', '\\|')} |"
        )
    lines.extend(["", "## Boundary", "", snapshot["boundary"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def build_strong_baseline_dependency_snapshot(
    *,
    external_registry_path: Path = DEFAULT_EXTERNAL_REGISTRY,
    baseline_root: Path = DEFAULT_BASELINE_ROOT,
    output_dir: Path = DEFAULT_OUTPUT,
    hf_hub_cache: Path | None = None,
    promptguard_environment_snapshot: Path | None = None,
    promptguard_download_snapshot: Path | None = None,
) -> dict[str, Any]:
    external_registry_path = external_registry_path.resolve()
    baseline_root = baseline_root.resolve()
    output_dir = output_dir.resolve()
    registry = _read_json(external_registry_path)
    entries = _entries(registry)
    by_key: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        by_key.setdefault(str(entry.get("registry_key", "")), []).append(entry)
    probe = _package_probe(
        hf_hub_cache=hf_hub_cache,
        promptguard_environment_snapshot=promptguard_environment_snapshot,
        promptguard_download_snapshot=promptguard_download_snapshot,
    )
    adapter_preflights = _adapter_preflight_snapshots()
    sources = {
        str(entry.get("id", "")): _source_snapshot_for_entry(entry, baseline_root=baseline_root)
        for entry in entries
    }
    readiness_by_key = {
        key: _key_readiness(
            key=key,
            entries=by_key.get(key, []),
            sources=sources,
            probe=probe,
            adapter_preflights=adapter_preflights,
        )
        for key in sorted(REQUIRED_KEYS)
    }
    checks = [
        _check(
            "external_registry_loaded",
            bool(entries),
            detail={"path": str(external_registry_path), "entries": len(entries)},
        ),
        _check(
            "all_required_keys_have_entries",
            REQUIRED_KEYS <= set(by_key),
            detail={"missing": sorted(REQUIRED_KEYS - set(by_key)), "present": sorted(by_key)},
        ),
        _check(
            "repository_entries_record_expected_remote_heads",
            all(
                row["expected_remote_head_sha"] or not row["local_checkout_expected"]
                for row in sources.values()
            ),
            detail={
                key: row["expected_remote_head_sha"]
                for key, row in sources.items()
                if row["local_checkout_expected"]
            },
        ),
        _check(
            "ready_keys_have_no_unresolved_blockers",
            all(
                bool(row.get("snapshot_ready")) == (not bool(row.get("blockers")))
                for row in readiness_by_key.values()
            ),
            severity="warning",
            detail={key: row["blockers"] for key, row in readiness_by_key.items()},
        ),
        _check(
            "snapshot_not_result_eligible",
            True,
            severity="warning",
            detail=False,
        ),
    ]
    snapshot = {
        "schema_version": "paper-strong-baseline-dependency-snapshot-1.0",
        "snapshot_version": SNAPSHOT_VERSION,
        "status": "completed",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "external_registry_path": str(external_registry_path),
        "external_registry_sha256": sha256_file(external_registry_path),
        "baseline_root": str(baseline_root),
        "dependency_probe": probe,
        "adapter_preflight_snapshots": adapter_preflights,
        "source_snapshots": sources,
        "source_snapshots_sha256": rows_sha256(sources.values()),
        "readiness_by_key": readiness_by_key,
        "readiness_by_key_sha256": rows_sha256(readiness_by_key.values()),
        "checks": checks,
        "checks_sha256": rows_sha256(checks),
        "total_checks": len(checks),
        "passed_checks": sum(1 for check in checks if check["status"] == "pass"),
        "q2_strong_baseline_gate": "not_satisfied",
        "result_eligible_for_formal_tables": False,
        "boundary": (
            "Dependency/source snapshot only. It records local environment and "
            "source-checkout state for required strong baselines, but it does "
            "not run baselines or create formal effect evidence."
        ),
    }
    json_path = output_dir / f"{SNAPSHOT_STEM}.json"
    md_path = output_dir / f"{SNAPSHOT_STEM}.md"
    snapshot["json_path"] = str(json_path)
    snapshot["markdown_path"] = str(md_path)
    snapshot = portable_value(snapshot, root=ROOT)
    _write_json(json_path, snapshot)
    _write_markdown(md_path, snapshot)
    return snapshot


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--external-registry", type=Path, default=DEFAULT_EXTERNAL_REGISTRY)
    parser.add_argument("--baseline-root", type=Path, default=DEFAULT_BASELINE_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--hf-hub-cache", type=Path)
    parser.add_argument("--promptguard-environment-snapshot", type=Path)
    parser.add_argument("--promptguard-download-snapshot", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    snapshot = build_strong_baseline_dependency_snapshot(
        external_registry_path=args.external_registry,
        baseline_root=args.baseline_root,
        output_dir=args.output_dir,
        hf_hub_cache=args.hf_hub_cache,
        promptguard_environment_snapshot=args.promptguard_environment_snapshot,
        promptguard_download_snapshot=args.promptguard_download_snapshot,
    )
    print(json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
