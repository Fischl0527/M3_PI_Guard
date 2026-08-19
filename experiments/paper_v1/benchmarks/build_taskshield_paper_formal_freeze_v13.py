"""Freeze Task Shield disclosed paper reproduction v1.3.

v1.3 is a new protocol, not a mutation of the v1.2 freeze.  It preserves the
same AgentDojo universe, paper PDF, model alias and disclosed reproduction
boundary, but hash-binds a fail-closed contribution-scoring compatibility patch
that converts verifier scoring parse/cardinality errors into zero contribution
instead of crashing the case.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from . import build_taskshield_paper_formal_freeze as legacy
from .common import sha256_file
from .taskshield_paper_runtime_v13 import PATCH_VERSION


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = ROOT / "protocols" / "paper_upgrade_v1" / "taskshield_paper_formal_freeze_v13.json"
FREEZE_VERSION = "m3-paper-v1-taskshield-reproduction-freeze-1.3"


def _portable_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(resolved)


def _relativize_project_paths(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _relativize_project_paths(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_relativize_project_paths(item) for item in value]
    if isinstance(value, str):
        root_text = str(ROOT.resolve()).replace("/", "\\")
        candidate = value.replace("/", "\\")
        if candidate.lower() == root_text.lower() or candidate.lower().startswith(root_text.lower() + "\\"):
            try:
                return Path(value).resolve().relative_to(ROOT.resolve()).as_posix()
            except ValueError:
                return value
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _adapter_paths() -> dict[str, Path]:
    bench = Path(__file__).resolve().parent
    return {
        "runtime": bench / "taskshield_paper_runtime.py",
        "runtime_fail_closed_patch": bench / "taskshield_paper_runtime_v13.py",
        "runner": bench / "run_taskshield_paper_formal_v13.py",
        "legacy_runner_delegate": bench / "run_taskshield_paper_formal.py",
        "analyzer": bench / "analyze_taskshield_paper_formal.py",
        "import_preflight": bench / "audit_taskshield_paper_import.py",
        "resume_identity_helper": bench / "formal_run_identity.py",
        "protocol": ROOT / "protocols" / "paper_upgrade_v1" / "taskshield_paper_formal_protocol_v1.md",
    }


def build_freeze(
    *,
    public_freeze_path: Path,
    model_registry_path: Path,
    agentdojo_checkout: Path,
    paper_path: Path,
    model_id: str,
) -> dict[str, Any]:
    manifest = legacy.build_freeze(
        public_freeze_path=public_freeze_path,
        model_registry_path=model_registry_path,
        agentdojo_checkout=agentdojo_checkout,
        paper_path=paper_path,
        model_id=model_id,
    )
    paths = _adapter_paths()
    hashes = {name: sha256_file(path) if path.exists() else "" for name, path in paths.items()}
    manifest.update(
        {
            "schema_version": "paper-taskshield-reproduction-freeze-1.3",
            "freeze_version": FREEZE_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    task_shield = dict(manifest["task_shield"])
    task_shield.update(
        {
            "invalid_verifier_output_policy": (
                "trusted_task_extraction_remains_strict; contribution_scoring_parse_schema_score_"
                "or_cardinality_errors_fail_closed_to_zero_contribution"
            ),
            "runtime_fail_closed_patch": _portable_path(paths["runtime_fail_closed_patch"]),
            "runtime_fail_closed_patch_sha256": hashes["runtime_fail_closed_patch"],
            "runtime_patch_version": PATCH_VERSION,
            "v13_change_reason": (
                "v1.2 failed utility case agentdojo:v1:banking:user_task_13 because the local "
                "verifier returned a contribution row count different from the trusted task count; "
                "v1.3 denies/suppresses such proposals instead of terminating the case."
            ),
        }
    )
    manifest["task_shield"] = task_shield
    manifest["local_adapter"] = {
        "files": {name: _portable_path(path) for name, path in paths.items()},
        "sha256": hashes,
        "resume_identity_checked_before_model_probe": True,
        "v13_fail_closed_scoring_patch": True,
    }
    checks = [dict(row) for row in manifest["checks"]]
    checks = [
        (
            {
                **row,
                "detail": hashes,
            }
            if row.get("name") == "local_adapter_files_hash_bound"
            else row
        )
        for row in checks
    ]
    checks.append(
        {
            "name": "v13_fail_closed_scoring_patch_hash_bound",
            "status": "pass" if hashes["runtime_fail_closed_patch"] and hashes["runner"] else "fail",
            "detail": {
                "patch_version": PATCH_VERSION,
                "runner": _portable_path(paths["runner"]),
                "runtime_fail_closed_patch": _portable_path(paths["runtime_fail_closed_patch"]),
            },
        }
    )
    failed = [str(row["name"]) for row in checks if row.get("status") != "pass"]
    manifest["checks"] = checks
    manifest["passed_checks"] = len(checks) - len(failed)
    manifest["total_checks"] = len(checks)
    manifest["failed_checks"] = failed
    manifest["status"] = "completed_frozen_formal_protocol" if not failed else "failed_freeze_validation"
    manifest["boundary"] = (
        "Protocol freeze only. This is a disclosed Task Shield paper reproduction, not "
        "official Task Shield source. v1.3 adds a hash-bound fail-closed contribution-scoring "
        "compatibility patch after a v1.2 parser/cardinality failure; it must be reported "
        "separately from v1.2 and cannot enter tables before fresh qualification, exact "
        "726-case execution, complete traces, analysis and explicit admission."
    )
    return _relativize_project_paths(manifest)


def write_markdown(path: Path, manifest: Mapping[str, Any]) -> None:
    lines = [
        "# Task Shield disclosed paper-reproduction freeze v1.3",
        "",
        f"- Status: `{manifest['status']}`",
        f"- Checks: {manifest['passed_checks']}/{manifest['total_checks']}",
        f"- Cases: {manifest['case_counts']['total']} ({manifest['case_counts']['utility']} utility + {manifest['case_counts']['security']} security)",
        f"- Model: `{manifest['model_id']}`",
        f"- Runtime patch: `{manifest['task_shield']['runtime_patch_version']}`",
        "- Result eligible: `False` until fresh qualification and full formal admission.",
        "",
        "## v1.3 change",
        "",
        str(manifest["task_shield"]["v13_change_reason"]),
        "",
        "Contribution-scoring parse/schema/score/cardinality errors now fail closed to zero contribution. Trusted task extraction remains strict.",
        "",
        "## Evidence boundary",
        "",
        str(manifest["boundary"]),
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-freeze", type=Path, default=legacy.DEFAULT_PUBLIC_FREEZE)
    parser.add_argument("--model-registry", type=Path, default=legacy.DEFAULT_MODEL_REGISTRY)
    parser.add_argument("--agentdojo-checkout", type=Path, default=legacy.DEFAULT_AGENTDOJO)
    parser.add_argument("--paper", type=Path, default=legacy.DEFAULT_PAPER)
    parser.add_argument("--model-id", default="m3-paper-qwen3-8b-v1:latest")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = build_freeze(
        public_freeze_path=args.public_freeze.resolve(),
        model_registry_path=args.model_registry.resolve(),
        agentdojo_checkout=args.agentdojo_checkout.resolve(),
        paper_path=args.paper.resolve(),
        model_id=args.model_id,
    )
    _write_json(args.output, manifest)
    write_markdown(args.output.with_suffix(".md"), manifest)
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "checks": f"{manifest['passed_checks']}/{manifest['total_checks']}",
                "cases": manifest["case_counts"],
                "output": str(args.output.resolve()),
            },
            ensure_ascii=False,
        )
    )
    return 0 if manifest["status"] == "completed_frozen_formal_protocol" else 1


if __name__ == "__main__":
    raise SystemExit(main())
