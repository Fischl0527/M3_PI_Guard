"""Audit CaMeL local transports and AgentDojo capability coverage offline.

This preflight constructs the frozen privileged and quarantined local model
bindings, then verifies that every tool in each public AgentDojo suite is
represented by CaMeL's upstream wrapper and is covered by either a suite
security policy or the suite's no-side-effect set.  It blocks sockets and
executes no model query, tool call, benchmark case, or network request.
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
DEFAULT_COMPAT_PREFLIGHT = (
    ROOT / "protocols" / "paper_upgrade_v1" / "camel_source_backed_compat_preflight_v1.json"
)
DEFAULT_RUNNER_PREFLIGHT = (
    ROOT / "protocols" / "paper_upgrade_v1" / "camel_source_backed_runner_preflight_v1.json"
)
DEFAULT_OUTPUT = ROOT / "protocols" / "paper_upgrade_v1"
AUDIT_STEM = "camel_transport_mapping_preflight_v1"
AUDIT_VERSION = "m3-paper-v1-camel-transport-mapping-preflight-1.0"
SUPPORTED_SUITES = ("workspace", "travel", "banking", "slack")
EXPECTED_COMPAT_STATUS = "completed_compat_preflight_only"
EXPECTED_RUNNER_STATUS = "completed_runner_wiring_preflight_only"
DEFAULT_MODEL_ID = "m3-paper-qwen3-8b-v1:latest"
DEFAULT_TRANSPORT = {
    "provider": "openai-compatible",
    "quarantined_provider": "pydantic-ai-openai-compatible",
    "base_url": "http://127.0.0.1:11434/v1",
    "api_key": "ollama-local",
    "api_key_class": "non_secret_local_placeholder",
    "ollama_models": "E:\\Ollama\\models",
    "privileged_max_attempts": 10,
    "quarantined_llm_retries": 10,
}


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


def _run_probe(
    *,
    python_executable: Path,
    camel_checkout: Path,
    agentdojo_checkout: Path,
    model_id: str,
    transport: Mapping[str, Any],
) -> dict[str, Any]:
    env = {
        "PYTHONPATH": os.pathsep.join(
            [
                str(ROOT),
                str(agentdojo_checkout / "src"),
                str(camel_checkout / "src"),
            ]
        ),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    source = f'''
import json
import socket
import sys

network_attempted = False
tool_calls_executed = 0
model_or_api_calls = 0

def _blocked_connect(*args, **kwargs):
    global network_attempted
    network_attempted = True
    raise RuntimeError("network disabled by M3 CaMeL transport/mapping preflight")

socket.create_connection = _blocked_connect
_OriginalSocket = socket.socket

class _GuardedSocket(_OriginalSocket):
    def connect(self, *args, **kwargs):
        global network_attempted
        network_attempted = True
        raise RuntimeError("network disabled by M3 CaMeL transport/mapping preflight")

socket.socket = _GuardedSocket

from experiments.paper_v1.benchmarks.camel_agentdojo_compat import install_agentdojo_suite_import_compat
compat = install_agentdojo_suite_import_compat()
from agentdojo.functions_runtime import FunctionsRuntime
from agentdojo.task_suite.load_suites import get_suite
from camel.interpreter.namespace import Namespace
from camel.pipeline_elements.agentdojo_function import make_agentdojo_namespace
from camel.pipeline_elements.security_policies import (
    BankingSecurityPolicyEngine,
    SlackSecurityPolicyEngine,
    TravelSecurityPolicyEngine,
    WorkspaceSecurityPolicyEngine,
)
from experiments.paper_v1.benchmarks.camel_source_backed_runner import build_camel_source_backed_pipeline

engines = {{
    "workspace": WorkspaceSecurityPolicyEngine,
    "travel": TravelSecurityPolicyEngine,
    "banking": BankingSecurityPolicyEngine,
    "slack": SlackSecurityPolicyEngine,
}}
transport = {dict(transport)!r}
rows = []
for suite_name in {list(SUPPORTED_SUITES)!r}:
    try:
        suite = get_suite("v1", suite_name)
        environment = suite.load_and_inject_default_environment({{}})
        engine = engines[suite_name](environment)
        tool_names = {{tool.name for tool in suite.tools}}
        policy_tools = {{name for name, _ in engine.policies}}
        no_side_effect_tools = set(engine.no_side_effect_tools)
        covered_tools = policy_tools | no_side_effect_tools
        runtime = FunctionsRuntime(suite.tools)
        namespace = Namespace.with_builtins()
        wrapped = make_agentdojo_namespace(namespace, runtime, environment)
        wrapped_tool_names = {{name for name in tool_names if name in wrapped}}
        wrapper_classes = {{name: type(wrapped[name]).__name__ for name in sorted(wrapped_tool_names)}}
        pipeline, binding = build_camel_source_backed_pipeline(
            suite=suite_name,
            transport=transport,
            privileged_model_id={model_id!r},
            quarantined_model_id={model_id!r},
            temperature=0.0,
        )
        rows.append({{
            "suite": suite_name,
            "ok": True,
            "user_tasks": len(suite.user_tasks),
            "injection_tasks": len(suite.injection_tasks),
            "tool_count": len(tool_names),
            "tool_names": sorted(tool_names),
            "policy_tools": sorted(policy_tools),
            "no_side_effect_tools": sorted(no_side_effect_tools),
            "missing_policy_coverage": sorted(tool_names - covered_tools),
            "extra_policy_symbols": sorted(covered_tools - tool_names),
            "wrapped_tool_count": len(wrapped_tool_names),
            "missing_wrapped_tools": sorted(tool_names - wrapped_tool_names),
            "non_agentdojo_wrappers": sorted(name for name, cls in wrapper_classes.items() if cls != "AgentDojoFunction"),
            "pipeline_name": pipeline.name,
            "pipeline_elements": [type(element).__name__ for element in pipeline.elements],
            "transport_binding": binding.as_dict(),
            "error_type": "",
            "error": "",
        }})
    except Exception as exc:
        rows.append({{
            "suite": suite_name,
            "ok": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }})

print(json.dumps({{
    "ok": bool(compat.get("ok")) and all(row.get("ok") for row in rows),
    "compat_ok": bool(compat.get("ok")),
    "rows": rows,
    "network_attempted": network_attempted,
    "tool_calls_executed": tool_calls_executed,
    "model_or_api_calls": model_or_api_calls,
    "benchmark_case_count": 0,
    "python_executable": sys.executable,
}}, ensure_ascii=False, sort_keys=True))
'''
    merged_env = os.environ.copy()
    merged_env.update(env)
    result = subprocess.run(
        [str(python_executable), "-c", source],
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
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


def _check(name: str, passed: bool, detail: Any) -> dict[str, Any]:
    return {"name": name, "status": "pass" if passed else "fail", "detail": detail}


def build_camel_transport_mapping_preflight(
    *,
    camel_checkout: Path,
    agentdojo_checkout: Path,
    camel_python: Path,
    compat_preflight_path: Path,
    runner_preflight_path: Path,
    output_dir: Path,
    model_id: str = DEFAULT_MODEL_ID,
    transport: Mapping[str, Any] = DEFAULT_TRANSPORT,
) -> dict[str, Any]:
    compat = _read_optional_json(compat_preflight_path)
    runner = _read_optional_json(runner_preflight_path)
    probe = (
        _run_probe(
            python_executable=camel_python,
            camel_checkout=camel_checkout,
            agentdojo_checkout=agentdojo_checkout,
            model_id=model_id,
            transport=transport,
        )
        if camel_python.exists()
        else {}
    )
    rows = probe.get("rows", []) if isinstance(probe.get("rows"), list) else []
    successful_rows = [row for row in rows if isinstance(row, Mapping) and row.get("ok")]
    suites = sorted(str(row.get("suite", "")) for row in successful_rows)
    missing_coverage = {
        str(row.get("suite", "")): list(row.get("missing_policy_coverage", []))
        for row in successful_rows
        if row.get("missing_policy_coverage")
    }
    missing_wrappers = {
        str(row.get("suite", "")): list(row.get("missing_wrapped_tools", []))
        for row in successful_rows
        if row.get("missing_wrapped_tools")
    }
    non_agentdojo_wrappers = {
        str(row.get("suite", "")): list(row.get("non_agentdojo_wrappers", []))
        for row in successful_rows
        if row.get("non_agentdojo_wrappers")
    }
    expected_counts = {
        "workspace": {"user_tasks": 40, "injection_tasks": 6, "tool_count": 24},
        "travel": {"user_tasks": 20, "injection_tasks": 7, "tool_count": 28},
        "banking": {"user_tasks": 16, "injection_tasks": 9, "tool_count": 11},
        "slack": {"user_tasks": 21, "injection_tasks": 5, "tool_count": 11},
    }
    observed_counts = {
        str(row.get("suite", "")): {
            "user_tasks": int(row.get("user_tasks", -1)),
            "injection_tasks": int(row.get("injection_tasks", -1)),
            "tool_count": int(row.get("tool_count", -1)),
        }
        for row in successful_rows
    }
    bindings = [
        row.get("transport_binding", {})
        for row in successful_rows
        if isinstance(row.get("transport_binding"), Mapping)
    ]
    checks = [
        _check("camel_runtime_python_exists", camel_python.exists(), str(camel_python)),
        _check("pinned_camel_checkout_exists", camel_checkout.exists(), str(camel_checkout)),
        _check("pinned_agentdojo_checkout_exists", agentdojo_checkout.exists(), str(agentdojo_checkout)),
        _check(
            "compat_preflight_completed_nonformal",
            compat.get("status") == EXPECTED_COMPAT_STATUS
            and compat.get("result_eligible_for_formal_tables") is False,
            compat.get("status"),
        ),
        _check(
            "runner_wiring_preflight_completed_nonformal",
            runner.get("status") == EXPECTED_RUNNER_STATUS
            and runner.get("result_eligible_for_formal_tables") is False,
            runner.get("status"),
        ),
        _check("probe_returned_zero", probe.get("returncode") == 0, probe.get("stderr_tail")),
        _check("compat_loaded_before_camel", probe.get("compat_ok") is True, probe.get("compat_ok")),
        _check("all_four_public_suites_mapped", suites == sorted(SUPPORTED_SUITES), suites),
        _check("public_suite_counts_match_freeze", observed_counts == expected_counts, observed_counts),
        _check("all_public_tools_have_policy_coverage", not missing_coverage, missing_coverage),
        _check("all_public_tools_have_camel_wrappers", not missing_wrappers, missing_wrappers),
        _check("all_tool_wrappers_are_upstream_agentdojo_function", not non_agentdojo_wrappers, non_agentdojo_wrappers),
        _check(
            "privileged_and_quarantined_transports_bound",
            len(bindings) == 4
            and all(row.get("privileged_transport") for row in bindings)
            and all(row.get("quarantined_transport") for row in bindings),
            bindings,
        ),
        _check(
            "upstream_interpreter_and_policies_unedited",
            len(bindings) == 4
            and all(row.get("upstream_privileged_llm") for row in bindings)
            and all(row.get("upstream_security_policy") for row in bindings)
            and all(not row.get("upstream_interpreter_edited") for row in bindings)
            and all(not row.get("upstream_policy_edited") for row in bindings),
            bindings,
        ),
        _check(
            "no_network_model_tool_or_case_execution",
            not probe.get("network_attempted", True)
            and probe.get("model_or_api_calls") == 0
            and probe.get("tool_calls_executed") == 0
            and probe.get("benchmark_case_count") == 0,
            {
                "network_attempted": probe.get("network_attempted"),
                "model_or_api_calls": probe.get("model_or_api_calls"),
                "tool_calls_executed": probe.get("tool_calls_executed"),
                "benchmark_case_count": probe.get("benchmark_case_count"),
            },
        ),
        _check("result_not_formally_admitted", True, "transport and mapping preflight only"),
    ]
    passed = sum(row["status"] == "pass" for row in checks)
    status = (
        "completed_transport_and_mapping_preflight_only"
        if passed == len(checks)
        else "blocked_transport_and_mapping_preflight"
    )
    blockers = [
        "real_model_two_case_qualification_not_completed",
        "complete_726_case_formal_logs_absent",
        "formal_analysis_and_admission_absent",
    ]
    manifest = {
        "schema_version": "paper-camel-transport-mapping-preflight-1.0",
        "audit_version": AUDIT_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "boundary": (
            "Transport and capability-mapping preflight only. Client and pipeline "
            "objects are constructed with sockets blocked, but no model query, tool "
            "call or benchmark case is executed. This is not formal effect evidence."
        ),
        "camel_checkout": str(camel_checkout.resolve()),
        "agentdojo_checkout": str(agentdojo_checkout.resolve()),
        "camel_python": str(camel_python),
        "model_id": model_id,
        "transport": dict(transport),
        "compat_preflight": {
            "path": str(compat_preflight_path.resolve()),
            "status": compat.get("status", ""),
            "sha256": sha256_file(compat_preflight_path) if compat_preflight_path.exists() else "",
        },
        "runner_preflight": {
            "path": str(runner_preflight_path.resolve()),
            "status": runner.get("status", ""),
            "sha256": sha256_file(runner_preflight_path) if runner_preflight_path.exists() else "",
        },
        "probe": probe,
        "mapping_rows": rows,
        "mapping_rows_sha256": rows_sha256(rows),
        "suites_mapped": suites,
        "observed_counts": observed_counts,
        "missing_policy_coverage": missing_coverage,
        "missing_wrapped_tools": missing_wrappers,
        "non_agentdojo_wrappers": non_agentdojo_wrappers,
        "benchmark_case_count": int(probe.get("benchmark_case_count", -1)) if probe else -1,
        "model_or_api_calls": int(probe.get("model_or_api_calls", -1)) if probe else -1,
        "tool_calls_executed": int(probe.get("tool_calls_executed", -1)) if probe else -1,
        "network_attempted": bool(probe.get("network_attempted", True)),
        "checks": checks,
        "passed_checks": passed,
        "total_checks": len(checks),
        "qualification_blockers": blockers,
        "formal_result_admitted_now": False,
        "result_eligible_for_formal_tables": False,
    }
    json_path = output_dir / f"{AUDIT_STEM}.json"
    md_path = output_dir / f"{AUDIT_STEM}.md"
    manifest["json_path"] = str(json_path.resolve())
    manifest["markdown_path"] = str(md_path.resolve())
    _write_json(json_path, manifest)
    _write_markdown(md_path, manifest)
    return manifest


def _write_markdown(path: Path, manifest: Mapping[str, Any]) -> None:
    lines = [
        "# CaMeL transport and capability-mapping preflight v1",
        "",
        f"- Status: `{manifest['status']}`",
        f"- Checks: {manifest['passed_checks']}/{manifest['total_checks']}",
        f"- Suites mapped: {', '.join(manifest['suites_mapped'])}",
        f"- Model/API calls: {manifest['model_or_api_calls']}",
        f"- Tool calls: {manifest['tool_calls_executed']}",
        f"- Benchmark cases: {manifest['benchmark_case_count']}",
        f"- Network attempted: `{manifest['network_attempted']}`",
        f"- Result eligible: `{manifest['result_eligible_for_formal_tables']}`",
        "",
        "## Boundary",
        "",
        str(manifest["boundary"]),
        "",
        "## Coverage",
        "",
        "| Suite | Tools | Missing policy coverage | Missing wrappers |",
        "|---|---:|---:|---:|",
    ]
    for row in manifest["mapping_rows"]:
        if not isinstance(row, Mapping):
            continue
        lines.append(
            f"| `{row.get('suite')}` | {row.get('tool_count', 0)} | "
            f"{len(row.get('missing_policy_coverage', []))} | "
            f"{len(row.get('missing_wrapped_tools', []))} |"
        )
    lines.extend(["", "## Remaining blockers", ""])
    lines.extend(f"- `{blocker}`" for blocker in manifest["qualification_blockers"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--camel-checkout", type=Path, default=DEFAULT_CAMEL_CHECKOUT)
    parser.add_argument("--agentdojo-checkout", type=Path, default=DEFAULT_AGENTDOJO_CHECKOUT)
    parser.add_argument("--camel-python", type=Path, default=DEFAULT_CAMEL_PYTHON)
    parser.add_argument("--compat-preflight", type=Path, default=DEFAULT_COMPAT_PREFLIGHT)
    parser.add_argument("--runner-preflight", type=Path, default=DEFAULT_RUNNER_PREFLIGHT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--model-id", default=DEFAULT_MODEL_ID)
    args = parser.parse_args()
    manifest = build_camel_transport_mapping_preflight(
        camel_checkout=args.camel_checkout.resolve(),
        agentdojo_checkout=args.agentdojo_checkout.resolve(),
        camel_python=args.camel_python.resolve(),
        compat_preflight_path=args.compat_preflight.resolve(),
        runner_preflight_path=args.runner_preflight.resolve(),
        output_dir=args.output_dir.resolve(),
        model_id=args.model_id,
    )
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "checks": f"{manifest['passed_checks']}/{manifest['total_checks']}",
                "suites": manifest["suites_mapped"],
                "result_eligible": manifest["result_eligible_for_formal_tables"],
                "output": manifest["json_path"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if manifest["status"] == "completed_transport_and_mapping_preflight_only" else 1


if __name__ == "__main__":
    raise SystemExit(main())
