"""Audit the source-backed IPIGuard adapter without calling a model service."""

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
    ROOT / "protocols" / "paper_upgrade_v1" / "ipiguard_source_backed_formal_freeze_v1.json"
)
DEFAULT_OUTPUT = ROOT / "protocols" / "paper_upgrade_v1"
AUDIT_STEM = "ipiguard_source_backed_import_preflight_v1"
AUDIT_VERSION = "m3-paper-v1-ipiguard-source-backed-import-preflight-1.0"
CHILD_BUILD_CODE = r"""
import json
import sys
from pathlib import Path
from experiments.paper_v1.benchmarks.run_agentdojo_official_detector_formal import _read_json
from experiments.paper_v1.benchmarks.run_ipiguard_source_backed_formal import (
    _build_pipeline,
    _validate_local_adapter_freeze,
)

freeze = _read_json(Path(sys.argv[1]))
_validate_local_adapter_freeze(freeze)
pipeline, source_root = _build_pipeline(freeze)
isolation = sys.modules.get("agentdojo.agent_pipeline.llms.google_llm")
print(json.dumps({
    "pipeline_name": pipeline.name,
    "source_root": str(source_root.resolve()),
    "optional_provider_isolation_active": bool(
        isolation
        and getattr(isolation, "__m3_optional_provider_import_isolation__", False)
    ),
    "local_adapter_hashes_valid": True,
}, sort_keys=True))
"""


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
    checkout = Path(str(freeze.get("ipiguard", {}).get("checkout", "")))
    source_root = checkout / "agentdojo" / "src"
    declared_hashes = freeze.get("ipiguard", {}).get("source_hashes", {})
    actual_hashes = {
        str(relpath): sha256_file(checkout / str(relpath))
        if (checkout / str(relpath)).exists()
        else ""
        for relpath in declared_hashes
    }
    child_payload: dict[str, Any] = {}
    build_error = ""
    completed = subprocess.run(
        [sys.executable, "-B", "-c", CHILD_BUILD_CODE, str(freeze_path.resolve())],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode == 0:
        try:
            value = json.loads(completed.stdout.strip())
            child_payload = value if isinstance(value, dict) else {}
        except json.JSONDecodeError as exc:
            build_error = type(exc).__name__ + ": child output was not JSON"
    else:
        stderr_tail = completed.stderr.strip().splitlines()[-1:] or ["child build failed"]
        build_error = f"ChildBuildError(exit={completed.returncode}): {stderr_tail[0]}"
    pipeline_name = str(child_payload.get("pipeline_name", ""))
    built_source = Path(str(child_payload["source_root"])) if child_payload.get("source_root") else None
    checks = [
        _check(
            "freeze_completed",
            freeze.get("status") == "completed_frozen_formal_protocol",
            freeze.get("status"),
        ),
        _check(
            "source_hashes_match_freeze",
            bool(declared_hashes) and actual_hashes == declared_hashes,
            actual_hashes,
        ),
        _check(
            "adapter_builds_without_model_call",
            bool(pipeline_name) and not build_error,
            build_error or pipeline_name,
        ),
        _check(
            "source_root_matches_freeze",
            built_source is not None and built_source.resolve() == source_root.resolve(),
            str(built_source or ""),
        ),
        _check(
            "optional_provider_isolation_active",
            child_payload.get("optional_provider_isolation_active") is True,
            freeze.get("optional_provider_import_isolation", {}),
        ),
        _check(
            "algorithm_change_declared_false",
            freeze.get("optional_provider_import_isolation", {}).get("algorithm_change")
            is False,
            freeze.get("optional_provider_import_isolation", {}).get("algorithm_change"),
        ),
        _check(
            "local_adapter_hashes_match_freeze",
            child_payload.get("local_adapter_hashes_valid") is True,
            freeze.get("local_adapter", {}).get("sha256", {}),
        ),
    ]
    failed = [row["name"] for row in checks if row["status"] != "pass"]
    portable_checks = portable_value(checks, root=ROOT)
    result = {
        "schema_version": "paper-ipiguard-source-backed-import-preflight-1.0",
        "audit_version": AUDIT_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "completed_import_preflight_only" if not failed else "failed_import_preflight",
        "result_eligible_for_formal_tables": False,
        "network_calls_performed": False,
        "ollama_probe_performed": False,
        "benchmark_cases_executed": 0,
        "freeze_path": _path(freeze_path),
        "freeze_sha256": sha256_file(freeze_path),
        "pipeline_name": pipeline_name,
        "source_root": _path(built_source) if built_source else "",
        "child_build": portable_value(child_payload, root=ROOT),
        "source_hashes": actual_hashes,
        "source_hashes_sha256": rows_sha256(
            {"path": path, "sha256": digest} for path, digest in sorted(actual_hashes.items())
        ),
        "checks": portable_checks,
        "passed_checks": len(checks) - len(failed),
        "total_checks": len(checks),
        "failed_checks": failed,
        "boundary": (
            "Import/build qualification only. It proves that the pinned IPIGuard source-backed "
            "adapter can be constructed in a fresh subprocess without Vertex dependencies or "
            "network access. Subprocess isolation prevents the older fork from contaminating the "
            "main project runtime. It is not a model smoke, benchmark result, or formal effect estimate."
        ),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{AUDIT_STEM}.json"
    md_path = output_dir / f"{AUDIT_STEM}.md"
    _write_json(json_path, result)
    md_path.write_text(
        "\n".join(
            [
                "# IPIGuard source-backed import preflight v1",
                "",
                f"- Status: `{result['status']}`",
                f"- Checks: {result['passed_checks']}/{result['total_checks']}",
                "- Network calls: `False`",
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
