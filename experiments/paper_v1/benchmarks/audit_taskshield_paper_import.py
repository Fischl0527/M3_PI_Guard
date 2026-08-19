"""Audit the Task Shield paper reproduction without a model-service call."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .common import sha256_file


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_FREEZE = ROOT / "protocols" / "paper_upgrade_v1" / "taskshield_paper_formal_freeze_v1.json"
DEFAULT_OUTPUT = ROOT / "protocols" / "paper_upgrade_v1"
AUDIT_STEM = "taskshield_paper_import_preflight_v1"
CHILD_CODE = r'''
import json, socket, sys
from pathlib import Path
from experiments.paper_v1.benchmarks.taskshield_paper_runtime import build_taskshield_pipeline
from experiments.paper_v1.benchmarks.formal_run_identity import validate_hash_bound_files
def blocked(*args, **kwargs):
    raise RuntimeError("network disabled by Task Shield import preflight")
socket.socket.connect = blocked
freeze = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
validate_hash_bound_files(freeze.get("local_adapter", {}))
pipeline = build_taskshield_pipeline(freeze)
print(json.dumps({
    "pipeline_name": pipeline.name,
    "replacements": pipeline.m3_taskshield_replacements,
    "trace_class": type(pipeline.m3_taskshield_trace).__name__,
    "verifier_class": type(pipeline.m3_taskshield_verifier).__name__,
    "network_guard_active": True,
    "local_adapter_hashes_valid": True,
}, sort_keys=True))
'''


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(str(path) + " must contain an object")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _check(name: str, passed: bool, detail: Any) -> dict[str, Any]:
    return {"name": name, "status": "pass" if passed else "fail", "detail": detail}


def audit(*, freeze_path: Path, output_dir: Path) -> dict[str, Any]:
    freeze = _read_json(freeze_path)
    task = freeze.get("task_shield", {})
    paper_path = Path(str(task.get("paper_pdf", "")))
    runtime_path = Path(str(task.get("runtime_source", "")))
    completed = subprocess.run(
        [sys.executable, "-B", "-c", CHILD_CODE, str(freeze_path.resolve())],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    child: dict[str, Any] = {}
    error = ""
    if completed.returncode == 0:
        lines = [line for line in completed.stdout.splitlines() if line.strip().startswith("{")]
        if lines:
            child = json.loads(lines[-1])
        else:
            error = "child returned no JSON"
    else:
        error = f"ChildBuildError(exit={completed.returncode}): {completed.stderr[-2000:]}"
    checks = [
        _check("freeze_completed", freeze.get("status") == "completed_frozen_formal_protocol", freeze.get("status")),
        _check("paper_hash_matches", paper_path.exists() and sha256_file(paper_path) == task.get("paper_pdf_sha256"), str(paper_path)),
        _check("runtime_hash_matches", runtime_path.exists() and sha256_file(runtime_path) == task.get("runtime_source_sha256"), str(runtime_path)),
        _check("pipeline_builds_without_model_call", bool(child.get("pipeline_name")) and not error, error or child.get("pipeline_name")),
        _check("all_required_elements_replaced", child.get("replacements") == {"init_query": 1, "assistant_llm": 2, "tools_executor": 1}, child.get("replacements")),
        _check("verifier_constructed", child.get("verifier_class") == "TaskShieldPaperVerifier", child.get("verifier_class")),
        _check("network_guard_active", child.get("network_guard_active") is True, child.get("network_guard_active")),
        _check("paper_reproduction_not_official_source", task.get("classification") == "disclosed_paper_reproduction_not_official_source" and task.get("official_runnable_repository_identified") is False, task.get("classification")),
        _check("local_adapter_hashes_match_freeze", child.get("local_adapter_hashes_valid") is True, freeze.get("local_adapter", {}).get("sha256", {})),
    ]
    failed = [row["name"] for row in checks if row["status"] != "pass"]
    result = {
        "schema_version": "paper-taskshield-import-preflight-1.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "completed_import_preflight_only" if not failed else "failed_import_preflight",
        "result_eligible_for_formal_tables": False,
        "network_calls_performed": False,
        "ollama_probe_performed": False,
        "benchmark_cases_executed": 0,
        "freeze_path": str(freeze_path.resolve()),
        "freeze_sha256": sha256_file(freeze_path),
        "child_build": child,
        "checks": checks,
        "passed_checks": len(checks) - len(failed),
        "total_checks": len(checks),
        "failed_checks": failed,
        "boundary": "Import/build preflight only. It proves that the disclosed paper reproduction can be constructed in a network-blocked fresh process. It does not call a verifier, probe Ollama, execute a case, or reproduce the paper's GPT-4o results.",
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{AUDIT_STEM}.json"
    md_path = output_dir / f"{AUDIT_STEM}.md"
    _write_json(json_path, result)
    md_path.write_text(
        "\n".join(
            [
                "# Task Shield paper-reproduction import preflight v1",
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
