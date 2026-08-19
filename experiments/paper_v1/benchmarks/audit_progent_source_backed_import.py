"""Audit the Progent source-backed adapter without calling a model service."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .common import portable_path, portable_value, rows_sha256, sha256_file


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_FREEZE = (
    ROOT / "protocols" / "paper_upgrade_v1" / "progent_source_backed_formal_freeze_v1.json"
)
DEFAULT_OUTPUT = ROOT / "protocols" / "paper_upgrade_v1"
AUDIT_STEM = "progent_source_backed_import_preflight_v1"
AUDIT_VERSION = "m3-paper-v1-progent-source-backed-import-preflight-1.0"
CHILD_BUILD_CODE = r'''
import json
import socket
import sys
from pathlib import Path
from experiments.paper_v1.benchmarks.formal_run_identity import validate_hash_bound_files
from experiments.paper_v1.benchmarks.progent_source_backed_runtime import build_progent_pipeline

def blocked_connect(*args, **kwargs):
    raise RuntimeError("network disabled by Progent import-preflight harness")

socket.socket.connect = blocked_connect
freeze = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
validate_hash_bound_files(freeze.get("local_adapter", {}))
pipeline = build_progent_pipeline(freeze)
secagent_module = sys.modules["secagent"]
tool_module = sys.modules["secagent.tool"]
print(json.dumps({
    "pipeline_name": pipeline.name,
    "replacements": pipeline.m3_progent_replacements,
    "binding": pipeline.m3_progent_binding,
    "trace_class": type(pipeline.m3_progent_trace).__name__,
    "secagent_path": str(Path(secagent_module.__file__).resolve()),
    "secagent_tool_path": str(Path(tool_module.__file__).resolve()),
    "network_guard_active": True,
    "local_adapter_hashes_valid": True,
}, sort_keys=True))
'''


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


def _check(name: str, passed: bool, detail: Any) -> dict[str, Any]:
    return {"name": name, "status": "pass" if passed else "fail", "detail": detail}


def _path(path: Path) -> str:
    return portable_path(path, root=ROOT)


def audit(*, freeze_path: Path, output_dir: Path) -> dict[str, Any]:
    freeze = _read_json(freeze_path)
    progent_checkout = Path(str(freeze.get("progent", {}).get("checkout", "")))
    agentdojo_checkout = Path(str(freeze.get("agentdojo", {}).get("checkout", "")))
    progent_declared = dict(freeze.get("progent", {}).get("source_hashes", {}))
    agentdojo_declared = dict(freeze.get("agentdojo", {}).get("source_hashes", {}))
    progent_actual = {
        str(path): sha256_file(progent_checkout / str(path))
        if (progent_checkout / str(path)).exists()
        else ""
        for path in progent_declared
    }
    agentdojo_actual = {
        str(path): sha256_file(agentdojo_checkout / str(path))
        if (agentdojo_checkout / str(path)).exists()
        else ""
        for path in agentdojo_declared
    }
    adapter_path = Path(str(freeze.get("progent", {}).get("adapter_source", "")))
    adapter_sha256 = sha256_file(adapter_path) if adapter_path.exists() else ""
    completed = subprocess.run(
        [sys.executable, "-B", "-c", CHILD_BUILD_CODE, str(freeze_path.resolve())],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    child: dict[str, Any] = {}
    build_error = ""
    if completed.returncode == 0:
        lines = [line for line in completed.stdout.splitlines() if line.strip().startswith("{")]
        if lines:
            try:
                value = json.loads(lines[-1])
                child = value if isinstance(value, dict) else {}
            except json.JSONDecodeError as exc:
                build_error = type(exc).__name__ + ": child output was not JSON"
        else:
            build_error = "child output did not contain JSON"
    else:
        build_error = f"ChildBuildError(exit={completed.returncode}): {completed.stderr[-2000:]}"
    expected_secagent = (progent_checkout / "secagent" / "__init__.py").resolve()
    expected_tool = (progent_checkout / "secagent" / "tool.py").resolve()
    checks = [
        _check("freeze_completed", freeze.get("status") == "completed_frozen_formal_protocol", freeze.get("status")),
        _check("progent_source_hashes_match", bool(progent_declared) and progent_actual == progent_declared, progent_actual),
        _check("agentdojo_source_hashes_match", bool(agentdojo_declared) and agentdojo_actual == agentdojo_declared, agentdojo_actual),
        _check("adapter_source_hash_matches", bool(adapter_sha256) and adapter_sha256 == freeze.get("progent", {}).get("adapter_source_sha256"), adapter_sha256),
        _check("adapter_builds_without_model_call", bool(child.get("pipeline_name")) and not build_error, build_error or child.get("pipeline_name")),
        _check("exact_pipeline_elements_replaced", child.get("replacements") == {"init_query": 1, "tools_executor": 1}, child.get("replacements")),
        _check("official_secagent_source_loaded", Path(str(child.get("secagent_path", ""))).resolve() == expected_secagent and Path(str(child.get("secagent_tool_path", ""))).resolve() == expected_tool, {"secagent": child.get("secagent_path"), "tool": child.get("secagent_tool_path")}),
        _check("transport_binding_does_not_change_prompts_or_enforcement", child.get("binding", {}).get("prompt_templates_changed") is False and child.get("binding", {}).get("policy_enforcement_changed") is False, child.get("binding")),
        _check("network_guard_active", child.get("network_guard_active") is True, child.get("network_guard_active")),
        _check("local_adapter_hashes_match_freeze", child.get("local_adapter_hashes_valid") is True, freeze.get("local_adapter", {}).get("sha256", {})),
    ]
    failed = [row["name"] for row in checks if row["status"] != "pass"]
    portable_checks = portable_value(checks, root=ROOT)
    result = {
        "schema_version": "paper-progent-source-backed-import-preflight-1.0",
        "audit_version": AUDIT_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "completed_import_preflight_only" if not failed else "failed_import_preflight",
        "result_eligible_for_formal_tables": False,
        "network_calls_performed": False,
        "ollama_probe_performed": False,
        "benchmark_cases_executed": 0,
        "freeze_path": _path(freeze_path),
        "freeze_sha256": sha256_file(freeze_path),
        "pipeline_name": str(child.get("pipeline_name", "")),
        "child_build": portable_value(child, root=ROOT),
        "source_hashes_sha256": rows_sha256(
            {"repository": repository, "path": path, "sha256": digest}
            for repository, hashes in (("progent", progent_actual), ("agentdojo", agentdojo_actual))
            for path, digest in sorted(hashes.items())
        ),
        "checks": portable_checks,
        "passed_checks": len(checks) - len(failed),
        "total_checks": len(checks),
        "failed_checks": failed,
        "boundary": (
            "Import/build qualification only. It proves in a network-blocked fresh subprocess that the pinned official Progent policy source can be bound to the common current AgentDojo lifecycle. It does not generate a policy, probe Ollama, execute a benchmark case, or produce formal effect evidence."
        ),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{AUDIT_STEM}.json"
    md_path = output_dir / f"{AUDIT_STEM}.md"
    _write_json(json_path, result)
    md_path.write_text(
        "\n".join(
            [
                "# Progent source-backed import preflight v1",
                "",
                f"- Status: `{result['status']}`",
                f"- Checks: {result['passed_checks']}/{result['total_checks']}",
                "- Network calls: `False`",
                "- Ollama probe: `False`",
                "- Benchmark cases: `0`",
                "- Formal result eligible: `False`",
                "",
                "## Boundary",
                "",
                result["boundary"],
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    result["json_path"] = _path(json_path)
    result["markdown_path"] = _path(md_path)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", type=Path, default=DEFAULT_FREEZE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = audit(freeze_path=args.freeze.resolve(), output_dir=args.output_dir.resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "completed_import_preflight_only" else 1


if __name__ == "__main__":
    raise SystemExit(main())
