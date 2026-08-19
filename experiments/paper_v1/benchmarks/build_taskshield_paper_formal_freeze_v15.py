"""Freeze the Task Shield v1.5 post-hoc expanded-qualification protocol."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from . import build_taskshield_paper_formal_freeze_v14 as v14
from .audit_taskshield_v15_failure_modes import (
    DEFAULT_OUTPUT_DIR as DEFAULT_AUDIT_DIR,
)
from .audit_taskshield_v15_failure_modes import AUDIT_JSON_NAME
from .common import rows_sha256, sha256_file
from .taskshield_paper_runtime_v15 import (
    DEFAULT_CONTRACT_RETRY_ATTEMPTS,
    DEFAULT_RETRY_BACKOFF_SECONDS,
    DEFAULT_TIMEOUT_RETRY_ATTEMPTS,
    PATCH_VERSION,
)


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_AUDIT = DEFAULT_AUDIT_DIR / AUDIT_JSON_NAME
DEFAULT_OUTPUT = (
    ROOT / "protocols" / "paper_upgrade_v1" / "taskshield_paper_formal_freeze_v15.json"
)
FREEZE_VERSION = "m3-paper-v1-taskshield-reproduction-freeze-1.5"


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


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def _adapter_paths(audit_path: Path) -> dict[str, Path]:
    bench = Path(__file__).resolve().parent
    paths = v14._adapter_paths()
    paths.update(
        {
            "runtime_contract_recovery_patch": bench / "taskshield_paper_runtime_v15.py",
            "runner": bench / "run_taskshield_paper_formal_v15.py",
            "v15_freeze_builder": bench / "build_taskshield_paper_formal_freeze_v15.py",
            "v15_failure_mode_audit": audit_path,
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
    audit_path: Path = DEFAULT_AUDIT,
    timeout_retry_attempts: int = DEFAULT_TIMEOUT_RETRY_ATTEMPTS,
    contract_retry_attempts: int = DEFAULT_CONTRACT_RETRY_ATTEMPTS,
    retry_backoff_seconds: float = DEFAULT_RETRY_BACKOFF_SECONDS,
) -> dict[str, Any]:
    if timeout_retry_attempts < 1 or contract_retry_attempts < 1:
        raise ValueError("retry attempts must be at least 1")
    if retry_backoff_seconds < 0:
        raise ValueError("retry backoff must be non-negative")

    audit = _read_json(audit_path)
    contract = audit.get("v15_change_contract", {})
    manifest = v14.build_freeze(
        public_freeze_path=public_freeze_path,
        model_registry_path=model_registry_path,
        agentdojo_checkout=agentdojo_checkout,
        paper_path=paper_path,
        model_id=model_id,
        timeout_retry_attempts=timeout_retry_attempts,
        timeout_retry_backoff_seconds=retry_backoff_seconds,
    )
    paths = _adapter_paths(audit_path)
    hashes = {
        name: sha256_file(path) if path.exists() else "" for name, path in paths.items()
    }
    qualification_rows = [
        dict(row)
        for row in audit.get("qualification_case_rows", [])
        if isinstance(row, Mapping)
    ]
    qualification_ids = [str(row["benchmark_case_id"]) for row in qualification_rows]
    manifest.update(
        {
            "schema_version": "paper-taskshield-reproduction-freeze-1.5",
            "freeze_version": FREEZE_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "v15_change_contract": dict(contract),
            "qualification_case_ids": qualification_ids,
            "qualification_case_rows": qualification_rows,
            "qualification_case_rows_sha256": rows_sha256(qualification_rows),
            "qualification_result_eligible_for_formal_tables": False,
        }
    )
    task_shield = dict(manifest["task_shield"])
    task_shield.update(
        {
            "runtime_patch_version": PATCH_VERSION,
            "runtime_contract_recovery_patch": _portable_path(
                paths["runtime_contract_recovery_patch"]
            ),
            "runtime_contract_recovery_patch_sha256": hashes[
                "runtime_contract_recovery_patch"
            ],
            "timeout_retry_attempts": int(timeout_retry_attempts),
            "contract_retry_attempts": int(contract_retry_attempts),
            "retry_backoff_seconds": float(retry_backoff_seconds),
            "raw_output_trace_policy": "append_raw_output_before_strict_json_parse",
            "untrusted_extraction_failure_policy": (
                "assistant_or_tool_output_fail_closed_suppression_after_contract_retries"
            ),
            "trusted_extraction_failure_policy": "strict_case_failure_after_contract_retries",
            "contribution_failure_policy": "zero_scores_after_retries_or_schema_failure",
            "case_retry_policy": "no_case_retry_no_failed_row_exclusion",
            "v15_change_reason": (
                "The sealed v1.4 root retained two invalid-JSON failures during assistant "
                "content instruction extraction and did not retain their raw verifier output. "
                "v1.5 prospectively logs raw output before parsing, adds bounded contract "
                "recovery, and suppresses exhausted untrusted content fail-closed."
            ),
        }
    )
    manifest["task_shield"] = task_shield

    local_adapter = dict(manifest["local_adapter"])
    local_adapter["files"] = {
        name: _portable_path(path) for name, path in paths.items()
    }
    local_adapter["sha256"] = hashes
    local_adapter["v15_contract_recovery_patch"] = True
    local_adapter["v14_timeout_retry_semantics_retained"] = True
    local_adapter["v13_fail_closed_scoring_semantics_retained"] = True
    manifest["local_adapter"] = local_adapter

    failure_policy = dict(manifest["failure_policy"])
    failure_policy.update(
        {
            "no_case_level_retry": True,
            "no_selective_failed_row_retry": True,
            "no_failed_row_exclusion": True,
            "raw_verifier_output_logged_before_parse": True,
            "invalid_json_or_non_array_retry_max_attempts": int(
                contract_retry_attempts
            ),
            "v15_full_formal_run_authorized": False,
        }
    )
    manifest["failure_policy"] = failure_policy

    audit_ready = bool(
        audit.get("status") == "completed_failure_mode_audit"
        and audit.get("ready_to_build_v15") is True
        and audit.get("result_eligible_for_formal_tables") is False
    )
    contract_matches = bool(
        contract.get("full_726_case_run_authorized") is False
        and contract.get("case_level_retry") is False
        and contract.get("selective_failed_row_retry") is False
        and contract.get("failed_row_exclusion") is False
    )
    selection_valid = bool(
        len(qualification_rows) == 12
        and len(set(qualification_ids)) == 12
        and rows_sha256(qualification_rows)
        == audit.get("qualification_case_rows_sha256")
    )
    checks = [
        (
            {**dict(row), "detail": hashes}
            if row.get("name") == "local_adapter_files_hash_bound"
            else dict(row)
        )
        for row in manifest["checks"]
    ]
    checks.extend(
        [
            {
                "name": "v15_failure_audit_is_complete_and_hash_bound",
                "status": "pass" if audit_ready and hashes["v15_failure_mode_audit"] else "fail",
                "detail": {
                    "audit": _portable_path(audit_path),
                    "sha256": hashes["v15_failure_mode_audit"],
                },
            },
            {
                "name": "v15_change_contract_is_fail_closed_and_qualification_only",
                "status": "pass" if contract_matches else "fail",
                "detail": dict(contract),
            },
            {
                "name": "v15_expanded_qualification_selection_is_exact_and_frozen",
                "status": "pass" if selection_valid else "fail",
                "detail": {
                    "cases": len(qualification_rows),
                    "sha256": rows_sha256(qualification_rows),
                },
            },
        ]
    )
    failed = [str(row["name"]) for row in checks if row.get("status") != "pass"]
    manifest["checks"] = checks
    manifest["passed_checks"] = len(checks) - len(failed)
    manifest["total_checks"] = len(checks)
    manifest["failed_checks"] = failed
    manifest["status"] = (
        "completed_frozen_formal_protocol" if not failed else "failed_freeze_validation"
    )
    manifest["result_eligible_for_formal_tables"] = False
    manifest["boundary"] = (
        "Post-hoc failure-recovery protocol freeze only. v1.5 supersedes v1.4 for future "
        "qualification without modifying or retrying v1.4 evidence. This freeze authorizes "
        "only the exact fresh 12-case operational qualification, never a 726-case formal run, "
        "formal admission, failed-row exclusion or Q2 score increase."
    )
    return v14.v13._relativize_project_paths(manifest)


def write_markdown(path: Path, manifest: Mapping[str, Any]) -> None:
    lines = [
        "# Task Shield disclosed paper-reproduction freeze v1.5",
        "",
        f"- Status: `{manifest['status']}`",
        f"- Checks: `{manifest['passed_checks']}/{manifest['total_checks']}`",
        f"- Frozen benchmark cases: `{manifest['case_counts']['total']}`",
        f"- Expanded qualification cases: `{len(manifest['qualification_case_rows'])}`",
        f"- Runtime patch: `{manifest['task_shield']['runtime_patch_version']}`",
        "- Full 726-case run authorized: `False`",
        "- Result eligible for formal tables: `False`",
        "- Q2 score change: `0`",
        "",
        "## v1.5 change",
        "",
        str(manifest["task_shield"]["v15_change_reason"]),
        "",
        "## Expanded qualification",
        "",
    ]
    lines.extend(f"- `{case_id}`" for case_id in manifest["qualification_case_ids"])
    lines.extend(["", "## Evidence boundary", "", str(manifest["boundary"]), ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-freeze", type=Path, default=v14.v13.legacy.DEFAULT_PUBLIC_FREEZE)
    parser.add_argument("--model-registry", type=Path, default=v14.v13.legacy.DEFAULT_MODEL_REGISTRY)
    parser.add_argument("--agentdojo-checkout", type=Path, default=v14.v13.legacy.DEFAULT_AGENTDOJO)
    parser.add_argument("--paper", type=Path, default=v14.v13.legacy.DEFAULT_PAPER)
    parser.add_argument("--model-id", default="m3-paper-qwen3-8b-v1:latest")
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--timeout-retry-attempts", type=int, default=DEFAULT_TIMEOUT_RETRY_ATTEMPTS)
    parser.add_argument("--contract-retry-attempts", type=int, default=DEFAULT_CONTRACT_RETRY_ATTEMPTS)
    parser.add_argument("--retry-backoff-seconds", type=float, default=DEFAULT_RETRY_BACKOFF_SECONDS)
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
        audit_path=args.audit.resolve(),
        timeout_retry_attempts=args.timeout_retry_attempts,
        contract_retry_attempts=args.contract_retry_attempts,
        retry_backoff_seconds=args.retry_backoff_seconds,
    )
    _write_json(args.output, manifest)
    write_markdown(args.output.with_suffix(".md"), manifest)
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "checks": f"{manifest['passed_checks']}/{manifest['total_checks']}",
                "qualification_cases": len(manifest["qualification_case_rows"]),
                "output": _portable_path(args.output),
            },
            ensure_ascii=False,
        )
    )
    return 0 if manifest["status"] == "completed_frozen_formal_protocol" else 1


if __name__ == "__main__":
    raise SystemExit(main())
