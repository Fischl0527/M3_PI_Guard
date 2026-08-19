"""Audit the CaMeL/AgentDojo source-backed import compatibility layer.

This preflight proves only that the disclosed, process-local compatibility
preloader can remove the pinned AgentDojo suite import-order cycle while still
using official AgentDojo task-suite files and official CaMeL source modules.

It does not execute benchmark cases, call an LLM/API, start Ollama, or admit a
formal result.
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
DEFAULT_CAMEL_PYTHON = Path("E:/M3_PI_Guard_runtime/camel/.venv/Scripts/python.exe")
DEFAULT_IMPORT_PREFLIGHT = (
    ROOT / "protocols" / "paper_upgrade_v1" / "camel_source_backed_import_preflight_v1.json"
)
DEFAULT_FORMAL_FREEZE = (
    ROOT / "protocols" / "paper_upgrade_v1" / "camel_source_backed_formal_freeze_v1.json"
)
DEFAULT_OUTPUT = ROOT / "protocols" / "paper_upgrade_v1"
AUDIT_STEM = "camel_source_backed_compat_preflight_v1"
AUDIT_VERSION = "m3-paper-v1-camel-source-backed-compat-preflight-1.0"

REQUIRED_IMPORTS = (
    "agentdojo.default_suites.v1.banking.task_suite",
    "agentdojo.default_suites.v1.travel.task_suite",
    "agentdojo.default_suites.v1.workspace.task_suite",
    "agentdojo.default_suites.v1.slack.task_suite",
    "agentdojo.task_suite.load_suites",
    "camel.models",
    "camel.pipeline_elements.privileged_llm",
    "camel.pipeline_elements.security_policies.agentdojo_security_policies",
    "camel.pipeline_elements.security_policies.workspace",
    "camel.pipeline_elements.security_policies.travel",
    "camel.pipeline_elements.security_policies.banking",
    "camel.pipeline_elements.security_policies.slack",
)
EXPECTED_V1_2_TOTALS = {"user_tasks": 97, "injection_tasks": 35}


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(str(path) + " must contain a JSON object")
    return value


def _read_optional_json(path: Path) -> dict[str, Any]:
    return _read_json(path) if path.exists() else {}


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _run_json_python(
    python_executable: Path,
    source: str,
    *,
    env: Mapping[str, str],
    timeout: int = 120,
) -> dict[str, Any]:
    merged_env = os.environ.copy()
    merged_env.update({key: str(value) for key, value in env.items()})
    result = subprocess.run(
        [str(python_executable), "-c", source],
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
        env=merged_env,
    )
    try:
        payload = json.loads(result.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError):
        payload = {}
    payload.update(
        {
            "returncode": result.returncode,
            "stdout_tail": result.stdout[-4000:],
            "stderr_tail": result.stderr[-4000:],
        }
    )
    return payload


def _compat_probe(
    *,
    python_executable: Path,
    camel_checkout: Path,
) -> dict[str, Any]:
    env = {
        "PYTHONPATH": os.pathsep.join([str(ROOT), str(camel_checkout / "src")]),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    source = f"""
import importlib
import json
import socket
import sys

modules = {list(REQUIRED_IMPORTS)!r}
network_attempted = False

def _blocked_connect(*args, **kwargs):
    global network_attempted
    network_attempted = True
    raise RuntimeError("network disabled by M3 CaMeL compat preflight")

socket.create_connection = _blocked_connect
_OriginalSocket = socket.socket

class _GuardedSocket(_OriginalSocket):
    def connect(self, *args, **kwargs):
        global network_attempted
        network_attempted = True
        raise RuntimeError("network disabled by M3 CaMeL compat preflight")

socket.socket = _GuardedSocket

from experiments.paper_v1.benchmarks.camel_agentdojo_compat import (
    install_agentdojo_suite_import_compat,
)

rows = []
try:
    compat = install_agentdojo_suite_import_compat()
except Exception as exc:
    compat = {{
        "ok": False,
        "error_type": type(exc).__name__,
        "error": str(exc),
        "rows": [],
        "suite_counts": {{}},
    }}

for module_name in modules:
    try:
        imported = importlib.import_module(module_name)
        rows.append({{
            "module": module_name,
            "ok": True,
            "file": getattr(imported, "__file__", ""),
            "error_type": "",
            "error": "",
        }})
    except Exception as exc:
        rows.append({{
            "module": module_name,
            "ok": False,
            "file": "",
            "error_type": type(exc).__name__,
            "error": str(exc),
        }})

print(json.dumps({{
    "ok": bool(compat.get("ok")) and all(row["ok"] for row in rows),
    "compat": compat,
    "import_rows": rows,
    "network_attempted": network_attempted,
    "python_executable": sys.executable,
}}, ensure_ascii=False, sort_keys=True))
"""
    return _run_json_python(python_executable, source, env=env)


def _check(name: str, passed: bool, detail: Any = None, *, severity: str = "error") -> dict[str, Any]:
    return {
        "name": name,
        "status": "pass" if passed else "fail",
        "severity": severity,
        "detail": detail,
    }


def build_camel_source_backed_compat_preflight(
    *,
    camel_checkout: Path,
    camel_python: Path,
    import_preflight_path: Path,
    formal_freeze_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    import_preflight = _read_optional_json(import_preflight_path)
    formal_freeze = _read_optional_json(formal_freeze_path)
    probe = _compat_probe(python_executable=camel_python, camel_checkout=camel_checkout) if camel_python.exists() else {}
    compat = probe.get("compat", {}) if isinstance(probe.get("compat"), Mapping) else {}
    import_rows = probe.get("import_rows", []) if isinstance(probe.get("import_rows"), list) else []
    suite_counts = compat.get("suite_counts", {}) if isinstance(compat.get("suite_counts"), Mapping) else {}
    v1_2 = suite_counts.get("v1.2", {}) if isinstance(suite_counts.get("v1.2"), Mapping) else {}
    v1_2_totals = {
        "user_tasks": sum(
            int(row.get("user_tasks", 0)) for row in v1_2.values() if isinstance(row, Mapping)
        ),
        "injection_tasks": sum(
            int(row.get("injection_tasks", 0)) for row in v1_2.values() if isinstance(row, Mapping)
        ),
    }
    network_attempted = bool(probe.get("network_attempted"))
    import_blockers = [
        str(blocker)
        for blocker in import_preflight.get("qualification_blockers", [])
        if str(blocker)
    ] if isinstance(import_preflight.get("qualification_blockers"), list) else []
    checks = [
        _check("camel_runtime_python_exists", camel_python.exists(), str(camel_python)),
        _check("plain_import_preflight_recorded_prior_blocker", "camel_agentdojo_suite_circular_import_blocks_official_pipeline" in import_blockers, import_blockers),
        _check("compat_preloader_succeeded", bool(compat.get("ok")), compat),
        _check("required_imports_succeeded_after_compat", bool(import_rows) and all(row.get("ok") for row in import_rows), import_rows),
        _check("agentdojo_v1_2_suite_totals_match_public_universe", v1_2_totals == EXPECTED_V1_2_TOTALS, v1_2_totals),
        _check("no_network_attempted_during_compat_preflight", not network_attempted, network_attempted),
        _check("no_benchmark_cases_executed", True, 0, severity="warning"),
        _check(
            "formal_freeze_still_nonformal",
            bool(formal_freeze)
            and not formal_freeze.get("result_eligible_for_formal_tables", True),
            {
                "status": formal_freeze.get("status", "missing"),
                "result_eligible": formal_freeze.get("result_eligible_for_formal_tables"),
            },
            severity="warning",
        ),
    ]
    passed = sum(row["status"] == "pass" for row in checks)
    status = "completed_compat_preflight_only" if passed == len(checks) else "failed_compat_preflight"
    qualification_blockers = [
        "camel_interpreter_benchmark_runner_not_implemented",
        "model_or_api_transport_for_privileged_llm_not_frozen",
        "label_capability_mapping_not_validated_on_public_benchmarks",
        "complete_formal_logs_absent",
    ]
    manifest: dict[str, Any] = {
        "schema_version": "paper-camel-source-backed-compat-preflight-1.0",
        "audit_version": AUDIT_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "result_eligible_for_formal_tables": False,
        "formal_result_admitted_now": False,
        "boundary": (
            "Compatibility import preflight only. The process-local preloader "
            "resolves the pinned AgentDojo suite import-order cycle without "
            "editing external source, but this manifest does not execute CaMeL "
            "on any benchmark case, call an LLM/API, start Ollama, or admit a "
            "formal result."
        ),
        "runtime": {
            "camel_python": str(camel_python),
            "python_executable": probe.get("python_executable", ""),
            "returncode": probe.get("returncode"),
        },
        "source": {
            "camel_checkout": str(camel_checkout),
            "compat_module": str(Path(__file__).with_name("camel_agentdojo_compat.py")),
            "compat_module_sha256": sha256_file(Path(__file__).with_name("camel_agentdojo_compat.py")),
        },
        "plain_import_preflight": {
            "path": str(import_preflight_path),
            "sha256": sha256_file(import_preflight_path) if import_preflight_path.exists() else "",
            "status": import_preflight.get("status", "missing"),
            "qualification_blockers": import_blockers,
        },
        "formal_freeze": {
            "path": str(formal_freeze_path),
            "status": formal_freeze.get("status", "missing"),
            "result_eligible_for_formal_tables": formal_freeze.get(
                "result_eligible_for_formal_tables"
            ),
        },
        "compat_probe": probe,
        "import_rows": import_rows,
        "import_rows_sha256": rows_sha256(import_rows),
        "suite_counts": suite_counts,
        "suite_counts_sha256": rows_sha256(
            [
                {"version": version, "suite": suite, **dict(counts)}
                for version, suite_rows in suite_counts.items()
                if isinstance(suite_rows, Mapping)
                for suite, counts in suite_rows.items()
                if isinstance(counts, Mapping)
            ]
        ),
        "summary": {
            "passed_checks": passed,
            "total_checks": len(checks),
            "v1_2_totals": v1_2_totals,
            "network_attempted": network_attempted,
            "qualification_blockers": qualification_blockers,
        },
        "checks": checks,
        "passed_checks": passed,
        "total_checks": len(checks),
        "qualification_blockers": qualification_blockers,
        "next_required_work": [
            "Freeze a source-backed CaMeL runner that calls the compatibility preloader before importing CaMeL pipeline modules.",
            "Freeze privileged/quarantined model transport and cost policy.",
            "Validate label/capability mapping on public benchmark online inputs.",
            "Run a two-case qualification before any full 726-case AgentDojo run.",
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
    lines = [
        "# CaMeL Source-Backed Compatibility Preflight v1",
        "",
        f"- Status: `{manifest.get('status')}`",
        f"- Formal result admitted: `{manifest.get('formal_result_admitted_now')}`",
        f"- Result eligible for formal tables: `{manifest.get('result_eligible_for_formal_tables')}`",
        f"- Checks: `{manifest.get('passed_checks')}/{manifest.get('total_checks')}`",
        f"- Import rows SHA-256: `{manifest.get('import_rows_sha256')}`",
        f"- Suite counts SHA-256: `{manifest.get('suite_counts_sha256')}`",
        "",
        "## Boundary",
        "",
        str(manifest.get("boundary", "")),
        "",
        "## Qualification blockers",
        "",
    ]
    lines.extend(f"- `{item}`" for item in manifest.get("qualification_blockers", []))
    lines.extend(["", "## Required imports after compatibility preload", ""])
    for row in manifest.get("import_rows", []):
        if not isinstance(row, Mapping):
            continue
        status = "PASS" if row.get("ok") else "BLOCKED"
        detail = row.get("file") if row.get("ok") else f"{row.get('error_type')}: {row.get('error')}"
        lines.append(f"- `{status}` `{row.get('module')}` — {detail}")
    lines.extend(["", "## Next required work", ""])
    lines.extend(f"- {item}" for item in manifest.get("next_required_work", []))
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--camel-checkout", type=Path, default=DEFAULT_CAMEL_CHECKOUT)
    parser.add_argument("--camel-python", type=Path, default=DEFAULT_CAMEL_PYTHON)
    parser.add_argument("--import-preflight", type=Path, default=DEFAULT_IMPORT_PREFLIGHT)
    parser.add_argument("--formal-freeze", type=Path, default=DEFAULT_FORMAL_FREEZE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    manifest = build_camel_source_backed_compat_preflight(
        camel_checkout=args.camel_checkout.resolve(),
        camel_python=args.camel_python.resolve(),
        import_preflight_path=args.import_preflight.resolve(),
        formal_freeze_path=args.formal_freeze.resolve(),
        output_dir=args.output_dir.resolve(),
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
