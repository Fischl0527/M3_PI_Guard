"""Audit CaMeL's source-backed runtime imports without executing a benchmark.

This preflight sits between the offline source-smoke and a future formal CaMeL
AgentDojo run.  It verifies that the isolated CaMeL runtime exists, records the
locked dependency versions, and imports official CaMeL modules in fresh Python
processes.

The preflight deliberately does not call an LLM/API, start Ollama, execute the
CaMeL interpreter, or run AgentDojo cases.  A blocked import is recorded as an
engineering qualification blocker, not as an effect result.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .common import rows_sha256, sha256_file


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CAMEL_CHECKOUT = ROOT / "external" / "baselines" / "camel-prompt-injection"
DEFAULT_AGENTDOJO_CHECKOUT = ROOT / "external" / "benchmarks" / "agentdojo"
DEFAULT_CAMEL_PYTHON = Path("E:/M3_PI_Guard_runtime/camel/.venv/Scripts/python.exe")
DEFAULT_UV_BOOTSTRAP_PYTHON = Path("E:/M3_PI_Guard_runtime/camel_bootstrap/Scripts/python.exe")
DEFAULT_UV_CACHE = Path("E:/AI_Cache/uv")
DEFAULT_UV_LOG_DIR = ROOT / "protocols" / "paper_upgrade_v1" / "logs" / "camel_uv_sync_v1"
DEFAULT_SOURCE_SMOKE = ROOT / "protocols" / "paper_upgrade_v1" / "camel_official_source_smoke_v1.json"
DEFAULT_FORMAL_FREEZE = ROOT / "protocols" / "paper_upgrade_v1" / "camel_source_backed_formal_freeze_v1.json"
DEFAULT_OUTPUT = ROOT / "protocols" / "paper_upgrade_v1"
AUDIT_STEM = "camel_source_backed_import_preflight_v1"
AUDIT_VERSION = "m3-paper-v1-camel-source-backed-import-preflight-1.0"
EXPECTED_CAMEL_COMMIT = "f083b6b396399d3b3c7f2ddaf613a5945eaf32d8"

REQUIRED_PACKAGES = (
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
)
CORE_IMPORTS = (
    "camel.interpreter.interpreter",
    "camel.pipeline_elements.agentdojo_function",
    "agentdojo.agent_pipeline",
    "agentdojo.benchmark",
)
PIPELINE_IMPORTS = (
    "camel.models",
    "camel.pipeline_elements.privileged_llm",
    "camel.pipeline_elements.security_policies.agentdojo_security_policies",
)
SUITE_IMPORTS = (
    "agentdojo.default_suites.v1.banking.task_suite",
    "agentdojo.default_suites.v1.travel.task_suite",
    "agentdojo.default_suites.v1.workspace.task_suite",
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


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _git_head(checkout: Path) -> str:
    if not (checkout / ".git").exists():
        return ""
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=checkout,
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def _run_json_python(
    python_executable: Path,
    source: str,
    *,
    env: Mapping[str, str] | None = None,
    timeout: int = 60,
) -> dict[str, Any]:
    merged_env = os.environ.copy()
    if env:
        merged_env.update({key: str(value) for key, value in env.items()})
    result = subprocess.run(
        [str(python_executable), "-c", source],
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
        env=merged_env,
    )
    payload: dict[str, Any]
    try:
        payload = json.loads(result.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError):
        payload = {}
    payload.update(
        {
            "returncode": result.returncode,
            "stdout_tail": result.stdout[-2000:],
            "stderr_tail": result.stderr[-2000:],
        }
    )
    return payload


def _runtime_probe(python_executable: Path) -> dict[str, Any]:
    if not python_executable.exists():
        return {
            "python_executable": str(python_executable),
            "exists": False,
            "packages": {},
        }
    source = f"""
import importlib.metadata as md
import json
import platform
import sys
packages = {list(REQUIRED_PACKAGES)!r}
rows = {{}}
for package in packages:
    try:
        rows[package] = md.version(package)
    except md.PackageNotFoundError:
        rows[package] = "missing"
print(json.dumps({{
    "exists": True,
    "executable": sys.executable,
    "python_version": sys.version,
    "python_version_info": list(sys.version_info[:3]),
    "platform": platform.platform(),
    "packages": rows,
}}, sort_keys=True))
"""
    payload = _run_json_python(python_executable, source, timeout=30)
    payload["python_executable"] = str(python_executable)
    return payload


def _import_probe(
    python_executable: Path,
    module: str,
    *,
    pythonpath: list[Path],
    scenario: str,
) -> dict[str, Any]:
    env = {
        "PYTHONPATH": os.pathsep.join(str(path) for path in pythonpath),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    source = f"""
import importlib
import json
import socket
import sys

module_name = {module!r}
network_attempted = False

def _blocked_connect(*args, **kwargs):
    global network_attempted
    network_attempted = True
    raise RuntimeError("network disabled by M3 CaMeL import preflight")

socket.create_connection = _blocked_connect
_OriginalSocket = socket.socket

class _GuardedSocket(_OriginalSocket):
    def connect(self, *args, **kwargs):
        global network_attempted
        network_attempted = True
        raise RuntimeError("network disabled by M3 CaMeL import preflight")

socket.socket = _GuardedSocket

try:
    imported = importlib.import_module(module_name)
    result = {{
        "module": module_name,
        "ok": True,
        "file": getattr(imported, "__file__", ""),
        "error_type": "",
        "error": "",
    }}
except Exception as exc:
    result = {{
        "module": module_name,
        "ok": False,
        "file": "",
        "error_type": type(exc).__name__,
        "error": str(exc),
    }}
result.update({{
    "network_attempted": network_attempted,
    "python_executable": sys.executable,
}})
print(json.dumps(result, ensure_ascii=False, sort_keys=True))
"""
    payload = _run_json_python(python_executable, source, env=env, timeout=90)
    payload["scenario"] = scenario
    payload["pythonpath"] = [str(path) for path in pythonpath]
    return payload


def _check(name: str, passed: bool, detail: Any = None, *, severity: str = "error") -> dict[str, Any]:
    return {
        "name": name,
        "status": "pass" if passed else "fail",
        "severity": severity,
        "detail": detail,
    }


def _artifact_reference(path: Path) -> dict[str, str]:
    return {
        "path": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
        "sha256": sha256_file(path) if path.exists() else "",
    }


def _manifest_status_reference(path: Path, manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Reference a manifest without hashing it to avoid bidirectional hash cycles."""

    return {
        "path": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
        "status": manifest.get("status", "missing"),
        "result_eligible_for_formal_tables": bool(
            manifest.get("result_eligible_for_formal_tables")
        ),
    }


def build_camel_source_backed_import_preflight(
    *,
    camel_checkout: Path,
    agentdojo_checkout: Path,
    camel_python: Path,
    uv_bootstrap_python: Path,
    uv_cache: Path,
    uv_log_dir: Path,
    source_smoke_path: Path,
    formal_freeze_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    source_smoke = _read_optional_json(source_smoke_path)
    formal_freeze = _read_optional_json(formal_freeze_path)
    runtime = _runtime_probe(camel_python)
    camel_head = _git_head(camel_checkout)
    source_path = camel_checkout / "src"
    local_agentdojo_source = agentdojo_checkout / "src"
    package_versions = runtime.get("packages", {})
    if not isinstance(package_versions, Mapping):
        package_versions = {}

    scenarios = {
        "official_camel_source_with_installed_agentdojo": [source_path],
        "official_camel_source_with_local_agentdojo_checkout": [source_path, local_agentdojo_source],
    }
    import_rows: list[dict[str, Any]] = []
    if camel_python.exists():
        for scenario, paths in scenarios.items():
            for module in (*CORE_IMPORTS, *PIPELINE_IMPORTS, *SUITE_IMPORTS):
                import_rows.append(
                    _import_probe(
                        camel_python,
                        module,
                        pythonpath=paths,
                        scenario=scenario,
                    )
                )

    def rows_for(modules: tuple[str, ...]) -> list[dict[str, Any]]:
        return [row for row in import_rows if row.get("module") in modules]

    runtime_deps_present = bool(package_versions) and all(
        package_versions.get(package) not in {None, "missing"} for package in REQUIRED_PACKAGES
    )
    core_rows = rows_for(CORE_IMPORTS)
    pipeline_rows = rows_for(PIPELINE_IMPORTS)
    suite_rows = rows_for(SUITE_IMPORTS)
    core_imports_pass = bool(core_rows) and all(row.get("ok") for row in core_rows if row.get("module") in CORE_IMPORTS)
    pipeline_blockers = [
        row
        for row in (*pipeline_rows, *suite_rows)
        if not row.get("ok")
        and "circular import" in str(row.get("error", "")).lower()
        and "agentdojo.default_suites.v1" in str(row.get("error", ""))
    ]
    network_attempts = [row for row in import_rows if row.get("network_attempted")]
    log_files = sorted(path for path in uv_log_dir.glob("*") if path.is_file()) if uv_log_dir.exists() else []
    uv_log_artifacts = [_artifact_reference(path) for path in log_files]

    checks = [
        _check("camel_runtime_python_exists", camel_python.exists(), str(camel_python)),
        _check(
            "camel_runtime_python_3_10_12",
            runtime.get("python_version_info") == [3, 10, 12],
            runtime.get("python_version"),
        ),
        _check("uv_bootstrap_python_exists", uv_bootstrap_python.exists(), str(uv_bootstrap_python)),
        _check("uv_cache_on_e_drive", str(uv_cache).lower().startswith("e:"), str(uv_cache)),
        _check("camel_commit_pinned", camel_head == EXPECTED_CAMEL_COMMIT, camel_head),
        _check(
            "source_smoke_completed_nonformal",
            source_smoke.get("status") == "completed_source_smoke_only"
            and not source_smoke.get("result_eligible_for_formal_tables", True),
            {
                "status": source_smoke.get("status"),
                "result_eligible": source_smoke.get("result_eligible_for_formal_tables"),
            },
        ),
        _check(
            "formal_freeze_completed_nonformal",
            formal_freeze.get("status")
            in {
                "completed_dependency_blocked_frozen_protocol",
                "completed_import_preflight_blocked_frozen_protocol",
                "completed_compat_preflight_frozen_protocol",
                "completed_frozen_formal_protocol",
            }
            and not formal_freeze.get("result_eligible_for_formal_tables", True),
            {
                "status": formal_freeze.get("status"),
                "result_eligible": formal_freeze.get("result_eligible_for_formal_tables"),
            },
        ),
        _check("runtime_dependencies_present", runtime_deps_present, dict(package_versions)),
        _check(
            "official_core_imports_pass",
            core_imports_pass,
            [
                {
                    "scenario": row.get("scenario"),
                    "module": row.get("module"),
                    "ok": row.get("ok"),
                    "error": row.get("error"),
                }
                for row in core_rows
            ],
        ),
        _check(
            "official_pipeline_imports_blocked_by_agentdojo_suite_circular_import",
            bool(pipeline_blockers),
            [
                {
                    "scenario": row.get("scenario"),
                    "module": row.get("module"),
                    "error_type": row.get("error_type"),
                    "error": row.get("error"),
                }
                for row in pipeline_blockers
            ],
            severity="warning",
        ),
        _check("no_network_attempted_during_imports", not network_attempts, network_attempts),
        _check("result_not_formally_admitted", True, "import preflight only"),
    ]
    passed_checks = sum(row["status"] == "pass" for row in checks)
    qualification_blockers = [
        blocker
        for blocker in [
            "camel_runtime_dependency_sync_absent" if not runtime_deps_present else "",
            (
                "camel_agentdojo_suite_circular_import_blocks_official_pipeline"
                if pipeline_blockers
                else ""
            ),
            "camel_interpreter_benchmark_runner_not_implemented",
            "model_or_api_transport_for_privileged_llm_not_frozen",
            "label_capability_mapping_not_validated_on_public_benchmarks",
            "complete_formal_logs_absent",
        ]
        if blocker
    ]
    status = (
        "completed_dependency_import_preflight_blocked"
        if pipeline_blockers
        else "completed_dependency_import_preflight"
    )
    manifest: dict[str, Any] = {
        "schema_version": "paper-camel-source-backed-import-preflight-1.0",
        "audit_version": AUDIT_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "result_eligible_for_formal_tables": False,
        "formal_result_admitted_now": False,
        "boundary": (
            "Dependency/import qualification only. This preflight does not run "
            "CaMeL on AgentDojo cases, does not call an LLM/API, does not start "
            "Ollama, and must not be mixed into formal effect denominators."
        ),
        "runtime": runtime,
        "runtime_paths": {
            "camel_python": str(camel_python),
            "uv_bootstrap_python": str(uv_bootstrap_python),
            "uv_cache": str(uv_cache),
            "uv_log_dir": str(uv_log_dir),
        },
        "source": {
            "camel_checkout": str(camel_checkout),
            "camel_head": camel_head,
            "expected_camel_head": EXPECTED_CAMEL_COMMIT,
            "camel_pyproject_sha256": sha256_file(camel_checkout / "pyproject.toml"),
            "camel_uv_lock_sha256": sha256_file(camel_checkout / "uv.lock"),
            "agentdojo_checkout": str(agentdojo_checkout),
        },
        "source_smoke": _artifact_reference(source_smoke_path),
        "formal_freeze": _manifest_status_reference(formal_freeze_path, formal_freeze),
        "uv_sync_logs": uv_log_artifacts,
        "import_modules": {
            "core_imports": list(CORE_IMPORTS),
            "pipeline_imports": list(PIPELINE_IMPORTS),
            "suite_imports": list(SUITE_IMPORTS),
        },
        "import_rows": import_rows,
        "import_rows_sha256": rows_sha256(import_rows),
        "summary": {
            "passed_checks": passed_checks,
            "total_checks": len(checks),
            "core_import_rows": len(core_rows),
            "pipeline_or_suite_blocker_rows": len(pipeline_blockers),
            "network_attempt_rows": len(network_attempts),
            "qualification_blockers": qualification_blockers,
        },
        "checks": checks,
        "passed_checks": passed_checks,
        "total_checks": len(checks),
        "qualification_blockers": qualification_blockers,
        "next_required_work": [
            "Implement a source-backed CaMeL/AgentDojo compatibility layer that avoids the suite import cycle without changing CaMeL's security algorithm.",
            "Freeze the privileged/quarantined LLM transport and cost policy before executing CaMeL on public benchmark cases.",
            "Validate label/capability mapping on public benchmark online inputs only.",
            "Run the complete frozen AgentDojo universe and store complete logs before admitting any CaMeL result.",
        ],
    }
    json_path = output_dir / f"{AUDIT_STEM}.json"
    md_path = output_dir / f"{AUDIT_STEM}.md"
    _write_json(json_path, manifest)
    md_path.write_text(_markdown(manifest), encoding="utf-8")
    manifest["json_path"] = str(json_path)
    manifest["markdown_path"] = str(md_path)
    return manifest


def _markdown(manifest: Mapping[str, Any]) -> str:
    blockers = manifest.get("qualification_blockers", [])
    lines = [
        "# CaMeL Source-Backed Import Preflight v1",
        "",
        f"- Status: `{manifest.get('status')}`",
        f"- Formal result admitted: `{manifest.get('formal_result_admitted_now')}`",
        f"- Result eligible for formal tables: `{manifest.get('result_eligible_for_formal_tables')}`",
        f"- Checks: `{manifest.get('passed_checks')}/{manifest.get('total_checks')}`",
        f"- Import rows SHA-256: `{manifest.get('import_rows_sha256')}`",
        "",
        "## Boundary",
        "",
        str(manifest.get("boundary", "")),
        "",
        "## Runtime",
        "",
    ]
    runtime = manifest.get("runtime", {})
    if isinstance(runtime, Mapping):
        lines.extend(
            [
                f"- Python: `{runtime.get('python_version', '')}`",
                f"- Executable: `{runtime.get('executable', runtime.get('python_executable', ''))}`",
            ]
        )
    lines.extend(["", "## Qualification blockers", ""])
    if blockers:
        lines.extend(f"- `{blocker}`" for blocker in blockers)
    else:
        lines.append("- None recorded.")
    lines.extend(["", "## Import outcomes", ""])
    for row in manifest.get("import_rows", []):
        if not isinstance(row, Mapping):
            continue
        status = "PASS" if row.get("ok") else "BLOCKED"
        detail = row.get("file") if row.get("ok") else f"{row.get('error_type')}: {row.get('error')}"
        lines.append(f"- `{status}` `{row.get('scenario')}` `{row.get('module')}` — {detail}")
    lines.extend(["", "## Next required work", ""])
    lines.extend(f"- {item}" for item in manifest.get("next_required_work", []))
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--camel-checkout", type=Path, default=DEFAULT_CAMEL_CHECKOUT)
    parser.add_argument("--agentdojo-checkout", type=Path, default=DEFAULT_AGENTDOJO_CHECKOUT)
    parser.add_argument("--camel-python", type=Path, default=DEFAULT_CAMEL_PYTHON)
    parser.add_argument("--uv-bootstrap-python", type=Path, default=DEFAULT_UV_BOOTSTRAP_PYTHON)
    parser.add_argument("--uv-cache", type=Path, default=DEFAULT_UV_CACHE)
    parser.add_argument("--uv-log-dir", type=Path, default=DEFAULT_UV_LOG_DIR)
    parser.add_argument("--source-smoke", type=Path, default=DEFAULT_SOURCE_SMOKE)
    parser.add_argument("--formal-freeze", type=Path, default=DEFAULT_FORMAL_FREEZE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    manifest = build_camel_source_backed_import_preflight(
        camel_checkout=args.camel_checkout,
        agentdojo_checkout=args.agentdojo_checkout,
        camel_python=args.camel_python,
        uv_bootstrap_python=args.uv_bootstrap_python,
        uv_cache=args.uv_cache,
        uv_log_dir=args.uv_log_dir,
        source_smoke_path=args.source_smoke,
        formal_freeze_path=args.formal_freeze,
        output_dir=args.output_dir,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
