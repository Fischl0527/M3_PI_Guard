"""Audit CaMeL source-backed runner wiring without executing benchmark cases.

This preflight verifies that the pinned CaMeL source, the disclosed AgentDojo
suite compatibility layer, and the local runner-wiring helper can construct the
upstream ``PrivilegedLLM`` pipeline shape for each AgentDojo suite.  It does not
call any LLM/API, does not start Ollama, does not access the network, and does
not execute AgentDojo benchmark cases.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .camel_source_backed_runner import DEFAULT_MODEL_ID, SUPPORTED_SUITES
from .common import rows_sha256, sha256_file


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CAMEL_CHECKOUT = ROOT / "external" / "baselines" / "camel-prompt-injection"
DEFAULT_CAMEL_PYTHON = Path("E:/M3_PI_Guard_runtime/camel/.venv/Scripts/python.exe")
DEFAULT_COMPAT_PREFLIGHT = (
    ROOT / "protocols" / "paper_upgrade_v1" / "camel_source_backed_compat_preflight_v1.json"
)
DEFAULT_FORMAL_FREEZE = (
    ROOT / "protocols" / "paper_upgrade_v1" / "camel_source_backed_formal_freeze_v1.json"
)
DEFAULT_OUTPUT = ROOT / "protocols" / "paper_upgrade_v1"
AUDIT_STEM = "camel_source_backed_runner_preflight_v1"
AUDIT_VERSION = "m3-paper-v1-camel-source-backed-runner-preflight-1.0"
EXPECTED_COMPAT_STATUS = "completed_compat_preflight_only"


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


def _runner_wiring_probe(
    *,
    python_executable: Path,
    camel_checkout: Path,
    model_id: str,
) -> dict[str, Any]:
    env = {
        "PYTHONPATH": os.pathsep.join([str(ROOT), str(camel_checkout / "src")]),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    source = f"""
import json
import socket
import sys
from pathlib import Path

suites = {list(SUPPORTED_SUITES)!r}
model_id = {model_id!r}
network_attempted = False

def _blocked_connect(*args, **kwargs):
    global network_attempted
    network_attempted = True
    raise RuntimeError("network disabled by M3 CaMeL runner preflight")

socket.create_connection = _blocked_connect
_OriginalSocket = socket.socket

class _GuardedSocket(_OriginalSocket):
    def connect(self, *args, **kwargs):
        global network_attempted
        network_attempted = True
        raise RuntimeError("network disabled by M3 CaMeL runner preflight")

socket.socket = _GuardedSocket

from experiments.paper_v1.benchmarks.camel_agentdojo_compat import (
    install_agentdojo_suite_import_compat,
)
from experiments.paper_v1.benchmarks.camel_source_backed_runner import (
    build_camel_pipeline_skeleton,
    install_camel_source_path,
)

install_camel_source_path(Path({str(camel_checkout)!r}))
compat = install_agentdojo_suite_import_compat()
rows = []
for suite in suites:
    try:
        pipeline, wiring = build_camel_pipeline_skeleton(
            suite=suite,
            model_id=model_id,
        )
        rows.append({{
            "suite": suite,
            "ok": True,
            "error_type": "",
            "error": "",
            "pipeline_id": id(pipeline),
            **wiring.as_dict(),
        }})
    except Exception as exc:
        rows.append({{
            "suite": suite,
            "ok": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }})

print(json.dumps({{
    "ok": bool(compat.get("ok")) and all(row.get("ok") for row in rows),
    "compat_ok": bool(compat.get("ok")),
    "rows": rows,
    "network_attempted": network_attempted,
    "benchmark_case_count": 0,
    "model_or_api_calls": 0,
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


def build_camel_source_backed_runner_preflight(
    *,
    camel_checkout: Path,
    camel_python: Path,
    compat_preflight_path: Path,
    formal_freeze_path: Path,
    output_dir: Path,
    model_id: str = DEFAULT_MODEL_ID,
) -> dict[str, Any]:
    compat_preflight = _read_optional_json(compat_preflight_path)
    probe = (
        _runner_wiring_probe(
            python_executable=camel_python,
            camel_checkout=camel_checkout,
            model_id=model_id,
        )
        if camel_python.exists()
        else {}
    )
    rows = probe.get("rows", []) if isinstance(probe.get("rows"), list) else []
    ok_rows = [row for row in rows if isinstance(row, Mapping) and row.get("ok")]
    suites_constructed = sorted(str(row.get("suite", "")) for row in ok_rows)
    policy_map = {
        str(row.get("suite", "")): str(row.get("privileged_security_policy_engine", ""))
        for row in ok_rows
    }
    network_attempted = bool(probe.get("network_attempted"))
    model_or_api_calls = int(probe.get("model_or_api_calls", -1)) if probe else -1
    benchmark_case_count = int(probe.get("benchmark_case_count", -1)) if probe else -1
    all_use_upstream_privileged = all(bool(row.get("uses_upstream_privileged_llm")) for row in ok_rows)
    all_use_upstream_policy = all(bool(row.get("uses_upstream_security_policy")) for row in ok_rows)
    all_have_expected_elements = all(
        "PrivilegedLLM" in row.get("pipeline_element_classes", []) for row in ok_rows
    )
    dry_run_not_invoked = all(not bool(row.get("dry_run_llm_query_invoked")) for row in ok_rows)

    checks = [
        _check("camel_runtime_python_exists", camel_python.exists(), str(camel_python)),
        _check("camel_checkout_exists", camel_checkout.exists(), str(camel_checkout)),
        _check(
            "compat_preflight_completed_nonformal",
            compat_preflight.get("status") == EXPECTED_COMPAT_STATUS
            and compat_preflight.get("result_eligible_for_formal_tables") is False,
            {
                "status": compat_preflight.get("status"),
                "result_eligible": compat_preflight.get("result_eligible_for_formal_tables"),
            },
        ),
        _check(
            "formal_freeze_not_used_as_runner_wiring_input",
            True,
            {
                "path": str(formal_freeze_path),
                "used_as_input": False,
                "reason": "prevents a cyclic freeze-to-preflight hash dependency",
            },
        ),
        _check("runner_wiring_probe_returned_zero", probe.get("returncode") == 0, probe.get("stderr_tail")),
        _check("compat_layer_loaded_in_runner_probe", probe.get("compat_ok") is True, probe.get("compat_ok")),
        _check(
            "all_supported_suites_constructible",
            suites_constructed == sorted(SUPPORTED_SUITES),
            suites_constructed,
        ),
        _check("upstream_privileged_llm_used", all_use_upstream_privileged, rows),
        _check("upstream_security_policies_used", all_use_upstream_policy, policy_map),
        _check("privileged_llm_present_in_pipeline", all_have_expected_elements, rows),
        _check("dry_run_llm_not_queried", dry_run_not_invoked, rows),
        _check("no_network_or_model_api_invoked", not network_attempted and model_or_api_calls == 0, probe),
        _check("no_benchmark_cases_executed", benchmark_case_count == 0, benchmark_case_count),
        _check("result_not_formally_admitted", True, "runner wiring preflight only"),
    ]
    passed = sum(1 for row in checks if row["status"] == "pass")
    status = (
        "completed_runner_wiring_preflight_only"
        if passed == len(checks)
        else "blocked_runner_wiring_preflight"
    )
    blockers = [
        "transport_and_capability_mapping_not_proven_by_runner_wiring_preflight",
        "complete_formal_logs_absent",
        "formal_runner_execution_not_started",
    ]
    manifest = {
        "schema_version": "paper-camel-source-backed-runner-preflight-1.0",
        "audit_version": AUDIT_VERSION,
        "status": status,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "boundary": (
            "Runner wiring preflight only. This constructs upstream CaMeL pipeline "
            "objects with a dry-run LLM and executes zero benchmark cases. It is "
            "not a CaMeL result and must not enter effect denominators."
        ),
        "camel_checkout": str(camel_checkout.resolve()),
        "camel_python": str(camel_python),
        "model_id": model_id,
        "compat_preflight": {
            "path": str(compat_preflight_path),
            "status": compat_preflight.get("status", ""),
            "sha256": sha256_file(compat_preflight_path) if compat_preflight_path.exists() else "",
        },
        "formal_freeze": {
            "path": str(formal_freeze_path),
            "used_as_input": False,
            "sha256_recorded": False,
            "reason": "the formal freeze consumes this preflight, so reverse hashing would be cyclic",
        },
        "probe": probe,
        "runner_wiring_rows": rows,
        "runner_wiring_rows_sha256": rows_sha256(rows),
        "supported_suites": list(SUPPORTED_SUITES),
        "suites_constructed": suites_constructed,
        "policy_map": policy_map,
        "benchmark_case_count": benchmark_case_count,
        "model_or_api_calls": model_or_api_calls,
        "network_attempted": network_attempted,
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
        "# CaMeL source-backed runner wiring preflight v1",
        "",
        f"- Status: `{manifest['status']}`.",
        f"- Checks: {manifest['passed_checks']}/{manifest['total_checks']}.",
        f"- Constructed suites: {', '.join(manifest['suites_constructed'])}.",
        f"- Benchmark cases executed: {manifest['benchmark_case_count']}.",
        f"- Model/API calls: {manifest['model_or_api_calls']}.",
        f"- Network attempted: `{manifest['network_attempted']}`.",
        f"- Result eligible for formal tables: `{manifest['result_eligible_for_formal_tables']}`.",
        "",
        "## Boundary",
        "",
        str(manifest["boundary"]),
        "",
        "## Remaining qualification blockers",
        "",
    ]
    for blocker in manifest["qualification_blockers"]:
        lines.append(f"- `{blocker}`")
    lines.extend(["", "## Suite wiring", ""])
    for row in manifest["runner_wiring_rows"]:
        if not isinstance(row, Mapping):
            continue
        lines.append(
            "- "
            f"`{row.get('suite')}`: ok={row.get('ok')}, "
            f"policy=`{row.get('privileged_security_policy_engine', '')}`, "
            f"elements={row.get('pipeline_element_classes', [])}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--camel-checkout", type=Path, default=DEFAULT_CAMEL_CHECKOUT)
    parser.add_argument("--camel-python", type=Path, default=DEFAULT_CAMEL_PYTHON)
    parser.add_argument("--compat-preflight", type=Path, default=DEFAULT_COMPAT_PREFLIGHT)
    parser.add_argument("--formal-freeze", type=Path, default=DEFAULT_FORMAL_FREEZE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--model-id", default=DEFAULT_MODEL_ID)
    args = parser.parse_args()
    manifest = build_camel_source_backed_runner_preflight(
        camel_checkout=args.camel_checkout.resolve(),
        camel_python=args.camel_python,
        compat_preflight_path=args.compat_preflight.resolve(),
        formal_freeze_path=args.formal_freeze.resolve(),
        output_dir=args.output_dir.resolve(),
        model_id=args.model_id,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if manifest["status"] == "completed_runner_wiring_preflight_only" else 2


if __name__ == "__main__":
    raise SystemExit(main())
