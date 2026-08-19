"""Freeze Task Shield disclosed paper reproduction v1.4.

v1.4 is a separate failure-recovery protocol for the v1.3 APITimeoutError root.
It preserves the disclosed paper-reproduction boundary and the v1.3 fail-closed
contribution-scoring behavior, then hash-binds an explicit verifier transport
timeout retry patch.  It is not a mutation of v1.3 evidence and must be run from
a fresh full output root before any formal admission is possible.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from . import build_taskshield_paper_formal_freeze_v13 as v13
from .common import sha256_file
from .taskshield_paper_runtime_v14 import (
    DEFAULT_TIMEOUT_RETRY_ATTEMPTS,
    DEFAULT_TIMEOUT_RETRY_BACKOFF_SECONDS,
    PATCH_VERSION,
)


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = ROOT / "protocols" / "paper_upgrade_v1" / "taskshield_paper_formal_freeze_v14.json"
FREEZE_VERSION = "m3-paper-v1-taskshield-reproduction-freeze-1.4"


def _portable_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(resolved)


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _adapter_paths() -> dict[str, Path]:
    bench = Path(__file__).resolve().parent
    paths = v13._adapter_paths()
    paths.update(
        {
            "runtime_timeout_retry_patch": bench / "taskshield_paper_runtime_v14.py",
            "runner": bench / "run_taskshield_paper_formal_v14.py",
            "v14_freeze_builder": bench / "build_taskshield_paper_formal_freeze_v14.py",
        }
    )
    return paths


def build_freeze(
    *,
    public_freeze_path: Path,
    model_registry_path: Path,
    agentdojo_checkout: Path,
    paper_path: Path,
    model_id: str,
    timeout_retry_attempts: int = DEFAULT_TIMEOUT_RETRY_ATTEMPTS,
    timeout_retry_backoff_seconds: float = DEFAULT_TIMEOUT_RETRY_BACKOFF_SECONDS,
) -> dict[str, Any]:
    if timeout_retry_attempts < 1:
        raise ValueError("timeout_retry_attempts must be at least 1")
    if timeout_retry_backoff_seconds < 0:
        raise ValueError("timeout_retry_backoff_seconds must be non-negative")

    manifest = v13.build_freeze(
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
            "schema_version": "paper-taskshield-reproduction-freeze-1.4",
            "freeze_version": FREEZE_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    task_shield = dict(manifest["task_shield"])
    task_shield.update(
        {
            "runtime_patch_version": PATCH_VERSION,
            "runtime_timeout_retry_patch": _portable_path(
                paths["runtime_timeout_retry_patch"]
            ),
            "runtime_timeout_retry_patch_sha256": hashes["runtime_timeout_retry_patch"],
            "timeout_retry_attempts": int(timeout_retry_attempts),
            "timeout_retry_backoff_seconds": float(timeout_retry_backoff_seconds),
            "timeout_retry_scope": "verifier_model_transport_timeout_only",
            "timeout_retry_trace_policy": "append_retry_attempt_rows_to_taskshield_trace",
            "case_retry_policy": "no_case_retry_no_failed_row_exclusion",
            "v14_change_reason": (
                "v1.3 failed on agentdojo:v1:slack:user_task_18 with APITimeoutError "
                "during verifier instruction extraction; v1.4 freezes a bounded, trace-logged "
                "transport timeout retry while preserving full-root execution and zero-failure "
                "formal admission requirements."
            ),
        }
    )
    manifest["task_shield"] = task_shield
    local_adapter = dict(manifest["local_adapter"])
    local_adapter["files"] = {
        name: _portable_path(path) for name, path in paths.items()
    }
    local_adapter["sha256"] = hashes
    local_adapter["v14_timeout_retry_patch"] = True
    local_adapter["v13_fail_closed_scoring_patch"] = True
    local_adapter["resume_identity_checked_before_model_probe"] = True
    manifest["local_adapter"] = local_adapter

    failure_policy = dict(manifest["failure_policy"])
    failure_policy.update(
        {
            "no_case_level_retry": True,
            "no_selective_failed_row_retry": True,
            "verifier_timeout_transport_retry_is_explicit_and_trace_logged": True,
            "transport_retry_max_attempts": int(timeout_retry_attempts),
        }
    )
    manifest["failure_policy"] = failure_policy

    checks = [
        (
            {
                **dict(row),
                "detail": hashes,
            }
            if row.get("name") == "local_adapter_files_hash_bound"
            else dict(row)
        )
        for row in manifest["checks"]
    ]
    checks.append(
        {
            "name": "v14_timeout_retry_patch_hash_bound",
            "status": "pass"
            if hashes["runtime_timeout_retry_patch"] and hashes["runner"]
            else "fail",
            "detail": {
                "patch_version": PATCH_VERSION,
                "runner": _portable_path(paths["runner"]),
                "runtime_timeout_retry_patch": _portable_path(
                    paths["runtime_timeout_retry_patch"]
                ),
                "timeout_retry_attempts": int(timeout_retry_attempts),
                "timeout_retry_backoff_seconds": float(timeout_retry_backoff_seconds),
            },
        }
    )
    checks.append(
        {
            "name": "v14_is_fresh_failure_recovery_protocol",
            "status": "pass",
            "detail": {
                "supersedes_for_future_runs_only": "taskshield_paper_formal_freeze_v13",
                "does_not_modify_v13_outputs": True,
                "requires_fresh_full_root": "outputs/paper_upgrade_v1/baselines/taskshield_paper_formal_v14",
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
        "official Task Shield source. v1.4 is a future full-root failure-recovery "
        "protocol after a v1.3 APITimeoutError; it does not repair, retry or exclude "
        "the v1.3 failed row and cannot enter tables before fresh qualification or "
        "full 726-case execution, complete traces, analysis and explicit admission."
    )
    return v13._relativize_project_paths(manifest)


def write_markdown(path: Path, manifest: Mapping[str, Any]) -> None:
    lines = [
        "# Task Shield disclosed paper-reproduction freeze v1.4",
        "",
        f"- Status: `{manifest['status']}`",
        f"- Checks: {manifest['passed_checks']}/{manifest['total_checks']}",
        f"- Cases: {manifest['case_counts']['total']} ({manifest['case_counts']['utility']} utility + {manifest['case_counts']['security']} security)",
        f"- Model: `{manifest['model_id']}`",
        f"- Runtime patch: `{manifest['task_shield']['runtime_patch_version']}`",
        f"- Timeout retry attempts: `{manifest['task_shield']['timeout_retry_attempts']}`",
        f"- Timeout retry backoff seconds: `{manifest['task_shield']['timeout_retry_backoff_seconds']}`",
        "- Result eligible: `False` until fresh full-root formal admission.",
        "",
        "## v1.4 change",
        "",
        str(manifest["task_shield"]["v14_change_reason"]),
        "",
        "The retry scope is verifier-model transport timeout only. Case-level retry, selective failed-row retry and failed-row exclusion remain forbidden.",
        "",
        "## Evidence boundary",
        "",
        str(manifest["boundary"]),
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-freeze", type=Path, default=v13.legacy.DEFAULT_PUBLIC_FREEZE)
    parser.add_argument("--model-registry", type=Path, default=v13.legacy.DEFAULT_MODEL_REGISTRY)
    parser.add_argument("--agentdojo-checkout", type=Path, default=v13.legacy.DEFAULT_AGENTDOJO)
    parser.add_argument("--paper", type=Path, default=v13.legacy.DEFAULT_PAPER)
    parser.add_argument("--model-id", default="m3-paper-qwen3-8b-v1:latest")
    parser.add_argument("--timeout-retry-attempts", type=int, default=DEFAULT_TIMEOUT_RETRY_ATTEMPTS)
    parser.add_argument(
        "--timeout-retry-backoff-seconds",
        type=float,
        default=DEFAULT_TIMEOUT_RETRY_BACKOFF_SECONDS,
    )
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
        timeout_retry_attempts=args.timeout_retry_attempts,
        timeout_retry_backoff_seconds=args.timeout_retry_backoff_seconds,
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
