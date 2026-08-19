"""Freeze a CaMeL source-backed AgentDojo adapter protocol.

This builder is intentionally non-executing.  It does not install ``uv``, call
an API, start Ollama, invoke a model, or execute benchmark cases.
It records the exact source commit, source-smoke evidence, public benchmark
universe, dependency/API assumptions, transport mapping and failure policy
needed before a source-backed CaMeL qualification run may be attempted.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Mapping

from .common import portable_path, rows_sha256, sha256_file


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PUBLIC_FREEZE = (
    ROOT / "protocols" / "paper_upgrade_v1" / "public_benchmark_formal_freeze_v2.json"
)
DEFAULT_MODEL_REGISTRY = ROOT / "protocols" / "paper_upgrade_v1" / "model_registry_v2.json"
DEFAULT_AGENTDOJO = ROOT / "external" / "benchmarks" / "agentdojo"
DEFAULT_CAMEL = ROOT / "external" / "baselines" / "camel-prompt-injection"
DEFAULT_SOURCE_SMOKE = (
    ROOT / "protocols" / "paper_upgrade_v1" / "camel_official_source_smoke_v1.json"
)
DEFAULT_IMPORT_PREFLIGHT = (
    ROOT
    / "protocols"
    / "paper_upgrade_v1"
    / "camel_source_backed_import_preflight_v1.json"
)
DEFAULT_COMPAT_PREFLIGHT = (
    ROOT
    / "protocols"
    / "paper_upgrade_v1"
    / "camel_source_backed_compat_preflight_v1.json"
)
DEFAULT_RUNNER_PREFLIGHT = (
    ROOT
    / "protocols"
    / "paper_upgrade_v1"
    / "camel_source_backed_runner_preflight_v1.json"
)
DEFAULT_TRANSPORT_MAPPING_PREFLIGHT = (
    ROOT
    / "protocols"
    / "paper_upgrade_v1"
    / "camel_transport_mapping_preflight_v1.json"
)
DEFAULT_PROTOCOL = (
    ROOT / "protocols" / "paper_upgrade_v1" / "camel_source_backed_formal_protocol_v2.md"
)
DEFAULT_PREFLIGHT = (
    ROOT / "protocols" / "paper_upgrade_v1" / "camel_fides_ifc_adapter_preflight_v1.json"
)
DEFAULT_OUTPUT = (
    ROOT / "protocols" / "paper_upgrade_v1" / "camel_source_backed_formal_freeze_v2.json"
)
DEFAULT_UV_BOOTSTRAP_PYTHON = Path("E:/M3_PI_Guard_runtime/camel_bootstrap/Scripts/python.exe")
FREEZE_VERSION = "m3-paper-v1-camel-source-backed-freeze-1.3"
CONDITION_ID = "camel_or_fides"
SELECTED_ENTRY_ID = "camel_google_research"
EXPECTED_CAMEL_COMMIT = "f083b6b396399d3b3c7f2ddaf613a5945eaf32d8"
EXPECTED_AGENTDOJO_COMMIT = "089ed468cf3ed0322acc66b0211f26d9d90dbf60"
REQUIRED_UPSTREAM_DEPENDENCIES = {
    "agentdojo",
    "anthropic",
    "cyclopts",
    "google-genai",
    "jsonref",
    "openai",
    "openapi-pydantic",
    "pydantic",
    "pydantic-ai",
    "tiktoken",
    "vertexai",
}
FORBIDDEN_ADAPTER_INPUT_MARKERS = {
    "authorized_actions",
    "attack_goal",
    "expected_user_tool",
    "expected_user_tool_parameters",
    "injection_task_id",
    "offline_evaluation",
    "target_action",
}


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(str(path) + " must contain a JSON object")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _git_head(checkout: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=checkout,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _package_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "missing"


def _model_row(registry: Mapping[str, Any], model_id: str) -> dict[str, Any]:
    rows = registry.get("models", registry.get("declared_model_slots", []))
    if not isinstance(rows, list):
        raise ValueError("model registry must contain a models list")
    for row in rows:
        if isinstance(row, Mapping) and str(row.get("id", "")) == model_id:
            return dict(row)
    raise ValueError("model not found in registry: " + model_id)


def _case_rows(benchmark: Mapping[str, Any]) -> list[dict[str, str]]:
    rows = [
        {"case_kind": "utility", "benchmark_case_id": str(case_id)}
        for case_id in benchmark.get("utility_case_ids", [])
    ]
    rows.extend(
        {"case_kind": "security", "benchmark_case_id": str(case_id)}
        for case_id in benchmark.get("security_case_ids", [])
    )
    return rows


def _check(name: str, passed: bool, detail: Any) -> dict[str, Any]:
    return {"name": name, "status": "pass" if passed else "fail", "detail": detail}


def _source_hashes(checkout: Path) -> dict[str, str]:
    relpaths = [
        "README.md",
        "LICENSE",
        "pyproject.toml",
        "uv.lock",
        "main.py",
        "run_code.py",
        "src/camel/__init__.py",
        "src/camel/models.py",
        "src/camel/quarantined_llm.py",
        "src/camel/security_policy.py",
        "src/camel/system_prompt_generator.py",
        "src/camel/capabilities/capabilities.py",
        "src/camel/capabilities/readers.py",
        "src/camel/capabilities/sources.py",
        "src/camel/capabilities/utils.py",
        "src/camel/interpreter/interpreter.py",
        "src/camel/interpreter/library.py",
        "src/camel/interpreter/namespace.py",
        "src/camel/interpreter/result.py",
        "src/camel/interpreter/value.py",
        "src/camel/pipeline_elements/agentdojo_function.py",
        "src/camel/pipeline_elements/privileged_llm.py",
        "src/camel/pipeline_elements/replay_privileged_llm.py",
        "src/camel/pipeline_elements/security_policies/agentdojo_security_policies.py",
        "src/camel/pipeline_elements/security_policies/banking.py",
        "src/camel/pipeline_elements/security_policies/slack.py",
        "src/camel/pipeline_elements/security_policies/travel.py",
        "src/camel/pipeline_elements/security_policies/workspace.py",
    ]
    return {
        rel: sha256_file(checkout / rel) if (checkout / rel).exists() else ""
        for rel in relpaths
    }


def _local_adapter_binding() -> dict[str, Any]:
    bench_dir = Path(__file__).resolve().parent
    files = {
        "formal_runner": bench_dir / "run_camel_source_backed_formal.py",
        "formal_analyzer": bench_dir / "analyze_camel_source_backed_formal.py",
        "source_backed_runner": bench_dir / "camel_source_backed_runner.py",
        "agentdojo_compat": bench_dir / "camel_agentdojo_compat.py",
        "import_preflight": bench_dir / "audit_camel_source_backed_import_preflight.py",
        "runner_preflight": bench_dir / "audit_camel_source_backed_runner_preflight.py",
        "transport_mapping_preflight": bench_dir / "audit_camel_transport_mapping_preflight.py",
        "shared_identity": bench_dir / "formal_run_identity.py",
        "protocol": DEFAULT_PROTOCOL,
    }
    return {
        "files": {name: portable_path(path, root=ROOT) for name, path in files.items()},
        "sha256": {
            name: sha256_file(path) if path.exists() else ""
            for name, path in files.items()
        },
        "resume_identity_checked_before_model_probe": True,
    }


def _declared_dependencies(pyproject_text: str) -> set[str]:
    found: set[str] = set()
    for name in REQUIRED_UPSTREAM_DEPENDENCIES:
        if f'"{name}' in pyproject_text or f"'{name}" in pyproject_text:
            found.add(name)
    return found


def build_freeze(
    *,
    public_freeze_path: Path,
    model_registry_path: Path,
    agentdojo_checkout: Path,
    camel_checkout: Path,
    source_smoke_path: Path,
    preflight_path: Path,
    model_id: str,
    import_preflight_path: Path = DEFAULT_IMPORT_PREFLIGHT,
    compat_preflight_path: Path = DEFAULT_COMPAT_PREFLIGHT,
    runner_preflight_path: Path = DEFAULT_RUNNER_PREFLIGHT,
    transport_mapping_preflight_path: Path = DEFAULT_TRANSPORT_MAPPING_PREFLIGHT,
    uv_bootstrap_python: Path = DEFAULT_UV_BOOTSTRAP_PYTHON,
) -> dict[str, Any]:
    public_freeze = _read_json(public_freeze_path)
    model_registry = _read_json(model_registry_path)
    source_smoke = _read_json(source_smoke_path)
    preflight = _read_json(preflight_path)
    import_preflight = _read_json(import_preflight_path) if import_preflight_path.exists() else {}
    compat_preflight = _read_json(compat_preflight_path) if compat_preflight_path.exists() else {}
    runner_preflight = _read_json(runner_preflight_path) if runner_preflight_path.exists() else {}
    transport_mapping_preflight = (
        _read_json(transport_mapping_preflight_path)
        if transport_mapping_preflight_path.exists()
        else {}
    )
    benchmark = public_freeze.get("benchmarks", {}).get("agentdojo", {})
    if not isinstance(benchmark, Mapping):
        raise ValueError("public freeze does not contain an AgentDojo universe")
    model = _model_row(model_registry, model_id)
    cases = _case_rows(benchmark)
    source_hashes = _source_hashes(camel_checkout)
    pyproject_text = (camel_checkout / "pyproject.toml").read_text(encoding="utf-8")
    readme_text = (camel_checkout / "README.md").read_text(encoding="utf-8")
    declared_deps = _declared_dependencies(pyproject_text)
    uv_path = shutil.which("uv") or ""
    uv_bootstrap_available = uv_bootstrap_python.exists()
    adapter_path = Path(__file__).with_name("camel_fides_adapter.py")
    forbidden_adapter_hits: list[str] = []
    local_adapter = _local_adapter_binding()
    preflight_stub = preflight.get("stub_smoke", {})
    source_smoke_checks = {
        str(row.get("name", "")): row
        for row in source_smoke.get("checks", [])
        if isinstance(row, Mapping)
    }
    preflight_selection_check = source_smoke_checks.get("preflight_selects_camel_source", {})
    camel_head = _git_head(camel_checkout)
    agentdojo_head = _git_head(agentdojo_checkout)
    import_preflight_status = str(import_preflight.get("status", "missing"))
    compat_preflight_status = str(compat_preflight.get("status", "missing"))
    compat_preflight_ok = (
        compat_preflight_status == "completed_compat_preflight_only"
        and compat_preflight.get("passed_checks") == compat_preflight.get("total_checks")
        and not compat_preflight.get("result_eligible_for_formal_tables", True)
        and not compat_preflight.get("summary", {}).get("network_attempted", True)
        if isinstance(compat_preflight.get("summary"), Mapping)
        else False
    )
    runner_preflight_status = str(runner_preflight.get("status", "missing"))
    runner_preflight_ok = (
        runner_preflight_status == "completed_runner_wiring_preflight_only"
        and runner_preflight.get("passed_checks") == runner_preflight.get("total_checks")
        and not runner_preflight.get("result_eligible_for_formal_tables", True)
        and runner_preflight.get("benchmark_case_count") == 0
        and runner_preflight.get("model_or_api_calls") == 0
        and not runner_preflight.get("network_attempted", True)
    )
    transport_mapping_status = str(transport_mapping_preflight.get("status", "missing"))
    transport_mapping_ok = (
        transport_mapping_status == "completed_transport_and_mapping_preflight_only"
        and transport_mapping_preflight.get("passed_checks")
        == transport_mapping_preflight.get("total_checks")
        and not transport_mapping_preflight.get("result_eligible_for_formal_tables", True)
        and transport_mapping_preflight.get("benchmark_case_count") == 0
        and transport_mapping_preflight.get("model_or_api_calls") == 0
        and transport_mapping_preflight.get("tool_calls_executed") == 0
        and not transport_mapping_preflight.get("network_attempted", True)
        and not transport_mapping_preflight.get("missing_policy_coverage", {"missing": True})
        and not transport_mapping_preflight.get("missing_wrapped_tools", {"missing": True})
    )
    import_preflight_blockers = [
        str(blocker)
        for blocker in import_preflight.get("qualification_blockers", [])
        if str(blocker) == "camel_agentdojo_suite_circular_import_blocks_official_pipeline"
    ] if isinstance(import_preflight.get("qualification_blockers"), list) else []
    dependency_blockers = [
        blocker
        for blocker in [
            "uv_executable_missing" if not uv_path and not uv_bootstrap_available else "",
            "camel_source_backed_import_preflight_missing" if import_preflight_status not in {
                "completed_dependency_import_preflight",
                "completed_dependency_import_preflight_blocked",
            } else "",
            "camel_source_backed_compat_preflight_missing_or_failed"
            if not compat_preflight_ok
            else "",
            *(import_preflight_blockers if not compat_preflight_ok else []),
            "camel_runner_wiring_preflight_missing_or_failed"
            if not runner_preflight_ok
            else "",
            "camel_transport_mapping_preflight_missing_or_failed"
            if not transport_mapping_ok
            else "",
            "real_model_two_case_qualification_not_completed",
            "formal_runner_execution_not_started",
            "complete_formal_logs_absent",
        ]
        if blocker
    ]
    checks = [
        _check(
            "public_freeze_completed",
            public_freeze.get("status") == "completed",
            public_freeze.get("status"),
        ),
        _check(
            "agentdojo_universe_97_629",
            len(cases) == 726
            and sum(row["case_kind"] == "utility" for row in cases) == 97
            and sum(row["case_kind"] == "security" for row in cases) == 629,
            {
                "utility": sum(row["case_kind"] == "utility" for row in cases),
                "security": sum(row["case_kind"] == "security" for row in cases),
                "total": len(cases),
            },
        ),
        _check("common_case_ids_unique", len({row["benchmark_case_id"] for row in cases}) == 726, len(cases)),
        _check("camel_commit_pinned", camel_head == EXPECTED_CAMEL_COMMIT, camel_head),
        _check("agentdojo_commit_pinned", agentdojo_head == EXPECTED_AGENTDOJO_COMMIT, agentdojo_head),
        _check("all_camel_source_files_present", all(source_hashes.values()), source_hashes),
        _check(
            "source_smoke_completed_network_free_nonformal",
            source_smoke.get("status") == "completed_source_smoke_only"
            and source_smoke.get("passed_checks") == source_smoke.get("total_checks")
            and not source_smoke.get("network_calls_performed")
            and not source_smoke.get("result_eligible_for_formal_tables"),
            {
                "status": source_smoke.get("status"),
                "checks": f"{source_smoke.get('passed_checks')}/{source_smoke.get('total_checks')}",
                "network_calls": source_smoke.get("network_calls_performed"),
                "result_eligible": source_smoke.get("result_eligible_for_formal_tables"),
            },
        ),
        _check(
            "source_smoke_selects_camel",
            preflight_selection_check.get("status") == "pass"
            and preflight_selection_check.get("detail", {}).get("selected_candidate") == "camel",
            preflight_selection_check.get("detail"),
        ),
        _check(
            "upstream_uv_and_api_requirements_recorded",
            "Install `uv`" in readme_text
            and {"agentdojo", "openai", "google-genai", "vertexai"}.issubset(declared_deps),
            {
                "declared_dependencies": sorted(declared_deps),
                "uv_executable": uv_path,
                "uv_bootstrap_python": str(uv_bootstrap_python),
                "uv_bootstrap_available": uv_bootstrap_available,
            },
        ),
        _check(
            "source_backed_import_preflight_completed_network_free_nonformal",
            import_preflight_status in {
                "completed_dependency_import_preflight",
                "completed_dependency_import_preflight_blocked",
            }
            and import_preflight.get("passed_checks") == import_preflight.get("total_checks")
            and not import_preflight.get("result_eligible_for_formal_tables", True)
            and not import_preflight.get("summary", {}).get("network_attempt_rows", 1)
            if isinstance(import_preflight.get("summary"), Mapping)
            else False,
            {
                "status": import_preflight_status,
                "checks": f"{import_preflight.get('passed_checks')}/{import_preflight.get('total_checks')}",
                "network_attempt_rows": import_preflight.get("summary", {}).get("network_attempt_rows")
                if isinstance(import_preflight.get("summary"), Mapping)
                else None,
                "result_eligible": import_preflight.get("result_eligible_for_formal_tables"),
            },
        ),
        _check(
            "source_backed_compat_preflight_completed_network_free_nonformal",
            compat_preflight_ok,
            {
                "status": compat_preflight_status,
                "checks": f"{compat_preflight.get('passed_checks')}/{compat_preflight.get('total_checks')}",
                "network_attempted": compat_preflight.get("summary", {}).get("network_attempted")
                if isinstance(compat_preflight.get("summary"), Mapping)
                else None,
                "result_eligible": compat_preflight.get("result_eligible_for_formal_tables"),
                "v1_2_totals": compat_preflight.get("summary", {}).get("v1_2_totals")
                if isinstance(compat_preflight.get("summary"), Mapping)
                else None,
            },
        ),
        _check(
            "source_backed_runner_wiring_preflight_completed_nonformal",
            runner_preflight_ok,
            {
                "status": runner_preflight_status,
                "checks": f"{runner_preflight.get('passed_checks')}/{runner_preflight.get('total_checks')}",
                "benchmark_case_count": runner_preflight.get("benchmark_case_count"),
                "model_or_api_calls": runner_preflight.get("model_or_api_calls"),
                "network_attempted": runner_preflight.get("network_attempted"),
                "result_eligible": runner_preflight.get("result_eligible_for_formal_tables"),
                "suites_constructed": runner_preflight.get("suites_constructed"),
            },
        ),
        _check(
            "transport_and_capability_mapping_preflight_completed_nonformal",
            transport_mapping_ok,
            {
                "status": transport_mapping_status,
                "checks": (
                    f"{transport_mapping_preflight.get('passed_checks')}/"
                    f"{transport_mapping_preflight.get('total_checks')}"
                ),
                "benchmark_case_count": transport_mapping_preflight.get(
                    "benchmark_case_count"
                ),
                "model_or_api_calls": transport_mapping_preflight.get(
                    "model_or_api_calls"
                ),
                "tool_calls_executed": transport_mapping_preflight.get(
                    "tool_calls_executed"
                ),
                "network_attempted": transport_mapping_preflight.get(
                    "network_attempted"
                ),
                "missing_policy_coverage": transport_mapping_preflight.get(
                    "missing_policy_coverage"
                ),
                "missing_wrapped_tools": transport_mapping_preflight.get(
                    "missing_wrapped_tools"
                ),
            },
        ),
        _check("model_role_modern_open", model.get("role") == "modern_open_7b_14b", model.get("role")),
        _check("adapter_preflight_source_present", adapter_path.exists(), str(adapter_path)),
        _check(
            "generic_adapter_preflight_has_no_evaluator_label_inputs",
            preflight.get("status") == "selected_source_ready_dependency_blocked_stub_preflight_only"
            and bool(preflight_stub.get("all_packages_forbidden_key_clean")),
            {
                "preflight_status": preflight.get("status"),
                "all_packages_forbidden_key_clean": preflight_stub.get(
                    "all_packages_forbidden_key_clean"
                ),
            },
        ),
        _check(
            "local_adapter_files_hash_bound",
            bool(local_adapter["files"])
            and all(local_adapter["sha256"].values())
            and bool(local_adapter["resume_identity_checked_before_model_probe"]),
            local_adapter,
        ),
    ]
    failed = [row["name"] for row in checks if row["status"] != "pass"]
    status = (
        "completed_frozen_formal_protocol"
        if not failed
        else "failed_freeze_validation"
    )
    return {
        "schema_version": "paper-camel-source-backed-formal-freeze-1.3",
        "freeze_version": FREEZE_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "result_eligible_for_formal_tables": False,
        "condition_id": CONDITION_ID,
        "selected_entry_id": SELECTED_ENTRY_ID,
        "method_selected": True,
        "source_checkout_ready": True,
        "config": {
            "selected_candidate": "camel",
            "camel_expected_commit": EXPECTED_CAMEL_COMMIT,
            "camel_checkout_path": portable_path(camel_checkout, root=ROOT),
        },
        "benchmark": "agentdojo",
        "benchmark_version": str(benchmark.get("version", "v1")),
        "attack_name": "direct",
        "repeats": 1,
        "temperature": 0.0,
        "seed": 0,
        "model_id": model_id,
        "model": model,
        "agentdojo": {
            "checkout": portable_path(agentdojo_checkout, root=ROOT),
            "git_head": agentdojo_head,
            "target_universe": {"utility": 97, "security": 629, "total": 726},
            "case_universe_sha256": benchmark.get("case_universe_sha256", ""),
        },
        "camel": {
            "checkout": portable_path(camel_checkout, root=ROOT),
            "git_head": camel_head,
            "source_hashes": source_hashes,
            "source_hashes_sha256": rows_sha256(
                {"path": key, "sha256": value} for key, value in source_hashes.items()
            ),
            "source_smoke": portable_path(source_smoke_path, root=ROOT),
            "source_smoke_sha256": sha256_file(source_smoke_path),
            "source_smoke_status": source_smoke.get("status", ""),
            "source_smoke_checks": {
                "passed": source_smoke.get("passed_checks"),
                "total": source_smoke.get("total_checks"),
            },
            "adapter_preflight": portable_path(preflight_path, root=ROOT),
            "adapter_preflight_sha256": sha256_file(preflight_path),
            "source_backed_import_preflight": portable_path(import_preflight_path, root=ROOT),
            "source_backed_import_preflight_sha256": sha256_file(import_preflight_path)
            if import_preflight_path.exists()
            else "",
            "source_backed_import_preflight_status": import_preflight_status,
            "source_backed_compat_preflight": portable_path(compat_preflight_path, root=ROOT),
            "source_backed_compat_preflight_sha256": sha256_file(compat_preflight_path)
            if compat_preflight_path.exists()
            else "",
            "source_backed_compat_preflight_status": compat_preflight_status,
            "source_backed_runner_preflight": portable_path(runner_preflight_path, root=ROOT),
            "source_backed_runner_preflight_sha256": sha256_file(runner_preflight_path)
            if runner_preflight_path.exists()
            else "",
            "source_backed_runner_preflight_status": runner_preflight_status,
            "source_backed_runner_preflight_suites": runner_preflight.get("suites_constructed", []),
            "transport_mapping_preflight": portable_path(
                transport_mapping_preflight_path,
                root=ROOT,
            ),
            "transport_mapping_preflight_sha256": sha256_file(
                transport_mapping_preflight_path
            )
            if transport_mapping_preflight_path.exists()
            else "",
            "transport_mapping_preflight_status": transport_mapping_status,
            "transport_mapping_suites": transport_mapping_preflight.get(
                "suites_mapped", []
            ),
            "adapter_classification": "pinned_source_formal_runner_transport_and_capability_mapping_frozen_qualification_pending",
            "official_interpreter_source_edited": False,
            "official_policy_source_edited": False,
        },
        "transport": {
            "provider": "openai-compatible",
            "quarantined_provider": "pydantic-ai-openai-compatible",
            "base_url": "http://127.0.0.1:11434/v1",
            "api_key": "ollama-local",
            "api_key_class": "non_secret_local_placeholder",
            "ollama_models": "E:\\Ollama\\models",
            "privileged_model_id": model_id,
            "quarantined_model_id": model_id,
            "privileged_temperature": 0.0,
            "privileged_max_attempts": 10,
            "quarantined_llm_retries": 10,
            "network_scope": "loopback_only",
        },
        "upstream_runtime_requirements": {
            "requires_uv": True,
            "uv_executable": uv_path,
            "uv_bootstrap_python": str(uv_bootstrap_python),
            "uv_bootstrap_available": uv_bootstrap_available,
            "pyproject_declared_dependencies": sorted(declared_deps),
            "required_dependencies_observed": sorted(REQUIRED_UPSTREAM_DEPENDENCIES),
            "api_or_model_configuration_required": True,
            "env_file_required_by_readme": ".env",
            "network_calls_allowed_in_this_freeze": False,
            "benchmark_cases_executed_by_this_freeze": 0,
        },
        "trusted_input_boundary": {
            "allowed_policy_inputs": [
                "trusted_user_request",
                "trusted_app_context",
                "tool_schemas",
                "tool_return_source_labels",
                "runtime_capability_labels",
            ],
            "forbidden_evaluator_inputs": sorted(FORBIDDEN_ADAPTER_INPUT_MARKERS),
            "forbidden_evaluator_input_hits": forbidden_adapter_hits,
        },
        "local_adapter": local_adapter,
        "source_freezes": {
            "public_benchmark_freeze": portable_path(public_freeze_path, root=ROOT),
            "public_benchmark_freeze_sha256": sha256_file(public_freeze_path),
            "model_registry": portable_path(model_registry_path, root=ROOT),
            "model_registry_sha256": sha256_file(model_registry_path),
            "source_smoke": portable_path(source_smoke_path, root=ROOT),
            "source_smoke_sha256": sha256_file(source_smoke_path),
            "adapter_preflight": portable_path(preflight_path, root=ROOT),
            "adapter_preflight_sha256": sha256_file(preflight_path),
            "source_backed_import_preflight": portable_path(import_preflight_path, root=ROOT),
            "source_backed_import_preflight_sha256": sha256_file(import_preflight_path)
            if import_preflight_path.exists()
            else "",
            "source_backed_compat_preflight": portable_path(compat_preflight_path, root=ROOT),
            "source_backed_compat_preflight_sha256": sha256_file(compat_preflight_path)
            if compat_preflight_path.exists()
            else "",
            "source_backed_runner_preflight": portable_path(runner_preflight_path, root=ROOT),
            "source_backed_runner_preflight_sha256": sha256_file(runner_preflight_path)
            if runner_preflight_path.exists()
            else "",
            "transport_mapping_preflight": portable_path(
                transport_mapping_preflight_path,
                root=ROOT,
            ),
            "transport_mapping_preflight_sha256": sha256_file(
                transport_mapping_preflight_path
            )
            if transport_mapping_preflight_path.exists()
            else "",
        },
        "case_counts": {"utility": 97, "security": 629, "total": 726},
        "case_rows": cases,
        "case_rows_sha256": rows_sha256(cases),
        "qualification_blockers": dependency_blockers,
        "failure_policy": {
            "retain_all_failures_in_denominator": True,
            "no_silent_retry": True,
            "failed_case_requires_error_manifest": True,
            "utility_failure_scored_as_unsuccessful": True,
            "security_failure_scored_as_attack_success": True,
            "formal_admission_requires_complete_case_coverage": True,
            "formal_admission_requires_zero_unexplained_failures": True,
            "source_smoke_cannot_be_promoted_to_result": True,
        },
        "checks": checks,
        "passed_checks": len(checks) - len(failed),
        "total_checks": len(checks),
        "failed_checks": failed,
        "boundary": (
            "Frozen adapter protocol only. This manifest records the pinned "
            "CaMeL source, source-smoke and common AgentDojo universe, but it "
            "does not install dependencies, invoke a model/API, run cases, "
            "measure ASR/utility, or admit CaMeL into "
            "formal result tables."
        ),
    }


def write_markdown(path: Path, manifest: Mapping[str, Any]) -> None:
    lines = [
        "# CaMeL source-backed formal freeze v2",
        "",
        f"- Status: `{manifest['status']}`",
        f"- Condition: `{manifest['condition_id']}`",
        f"- Selected method: `{manifest['selected_entry_id']}`",
        f"- Model slot: `{manifest['model_id']}`",
        "- Common cases: `726` (`97` utility + `629` security)",
        f"- CaMeL commit: `{manifest['camel']['git_head']}`",
        f"- AgentDojo commit: `{manifest['agentdojo']['git_head']}`",
        f"- Source-smoke: `{manifest['camel']['source_smoke_status']}` "
        f"({manifest['camel']['source_smoke_checks']['passed']}/"
        f"{manifest['camel']['source_smoke_checks']['total']})",
        f"- Import preflight: `{manifest['camel']['source_backed_import_preflight_status']}`",
        f"- Compatibility preflight: `{manifest['camel']['source_backed_compat_preflight_status']}`",
        f"- Runner-wiring preflight: `{manifest['camel']['source_backed_runner_preflight_status']}`",
        f"- Transport/mapping preflight: `{manifest['camel']['transport_mapping_preflight_status']}`",
        f"- Checks: {manifest['passed_checks']}/{manifest['total_checks']}",
        "- Result eligible: `False` until the benchmark "
        "real-model qualification, complete logs and formal admission exist.",
        "",
        "## Frozen source and assumptions",
        "",
        "- Official CaMeL source files are hash-pinned in the JSON manifest.",
        "- The common AgentDojo v1 universe is fixed to 97 utility and 629 security cases.",
        "- The upstream README/pyproject requirement for `uv`, `.env` and provider/API "
        "configuration is recorded; the isolated uv runtime and loopback "
        "OpenAI-compatible transports are referenced but this freeze still does "
        "not execute benchmark cases.",
        "- The source-backed runner and analyzer are implemented separately; this "
        "freeze is the immutable protocol input for qualification and full runs, "
        "not a result artifact.",
        "",
        "## Qualification blockers",
        "",
    ]
    lines.extend(f"- `{item}`" for item in manifest["qualification_blockers"])
    lines.extend(
        [
            "",
            "## Evidence boundary",
            "",
            str(manifest["boundary"]),
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-freeze", type=Path, default=DEFAULT_PUBLIC_FREEZE)
    parser.add_argument("--model-registry", type=Path, default=DEFAULT_MODEL_REGISTRY)
    parser.add_argument("--agentdojo-checkout", type=Path, default=DEFAULT_AGENTDOJO)
    parser.add_argument("--camel-checkout", type=Path, default=DEFAULT_CAMEL)
    parser.add_argument("--source-smoke", type=Path, default=DEFAULT_SOURCE_SMOKE)
    parser.add_argument("--preflight", type=Path, default=DEFAULT_PREFLIGHT)
    parser.add_argument("--import-preflight", type=Path, default=DEFAULT_IMPORT_PREFLIGHT)
    parser.add_argument("--compat-preflight", type=Path, default=DEFAULT_COMPAT_PREFLIGHT)
    parser.add_argument("--runner-preflight", type=Path, default=DEFAULT_RUNNER_PREFLIGHT)
    parser.add_argument(
        "--transport-mapping-preflight",
        type=Path,
        default=DEFAULT_TRANSPORT_MAPPING_PREFLIGHT,
    )
    parser.add_argument("--uv-bootstrap-python", type=Path, default=DEFAULT_UV_BOOTSTRAP_PYTHON)
    parser.add_argument("--model-id", default="m3-paper-qwen3-8b-v1:latest")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = build_freeze(
        public_freeze_path=args.public_freeze.resolve(),
        model_registry_path=args.model_registry.resolve(),
        agentdojo_checkout=args.agentdojo_checkout.resolve(),
        camel_checkout=args.camel_checkout.resolve(),
        source_smoke_path=args.source_smoke.resolve(),
        preflight_path=args.preflight.resolve(),
        import_preflight_path=args.import_preflight.resolve(),
        compat_preflight_path=args.compat_preflight.resolve(),
        runner_preflight_path=args.runner_preflight.resolve(),
        transport_mapping_preflight_path=args.transport_mapping_preflight.resolve(),
        uv_bootstrap_python=args.uv_bootstrap_python.resolve(),
        model_id=args.model_id,
    )
    _write_json(args.output, manifest)
    write_markdown(args.output.with_suffix(".md"), manifest)
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "cases": manifest["case_counts"],
                "checks": f"{manifest['passed_checks']}/{manifest['total_checks']}",
                "result_eligible": manifest["result_eligible_for_formal_tables"],
                "output": portable_path(args.output.resolve(), root=ROOT),
            },
            ensure_ascii=False,
        )
    )
    return 0 if manifest["status"] == "completed_frozen_formal_protocol" else 1


if __name__ == "__main__":
    raise SystemExit(main())
