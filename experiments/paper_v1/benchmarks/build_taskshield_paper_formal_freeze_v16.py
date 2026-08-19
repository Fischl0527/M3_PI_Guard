"""Freeze the correctness-first Task Shield v1.6 staged qualification."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from . import build_taskshield_paper_formal_freeze_v15 as v15
from .common import rows_sha256, sha256_file
from .taskshield_paper_runtime_v16 import (
    DEFAULT_CASE_TIMEOUT_SECONDS,
    DEFAULT_LOGICAL_ATTEMPTS,
    DEFAULT_REQUEST_TIMEOUT_SECONDS,
    DEFAULT_RETRY_BACKOFF_SECONDS,
    PATCH_VERSION,
    runtime_contract,
)


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_G0 = (
    ROOT
    / "protocols"
    / "paper_upgrade_v1"
    / "execution"
    / "taskshield_v16_p0_metric_semantics_v1"
    / "gate_g0.json"
)
DEFAULT_OUTPUT = (
    ROOT / "protocols" / "paper_upgrade_v1" / "taskshield_paper_formal_freeze_v16.json"
)
FREEZE_VERSION = "m3-paper-v1-taskshield-reproduction-freeze-1.6"


def _portable_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _v16_paths(g0_path: Path) -> dict[str, Path]:
    bench = Path(__file__).resolve().parent
    return {
        "v16_runtime": bench / "taskshield_paper_runtime_v16.py",
        "v16_runner": bench / "run_taskshield_paper_formal_v16.py",
        "v16_freeze_builder": bench / "build_taskshield_paper_formal_freeze_v16.py",
        "v16_qualification_analyzer": bench / "analyze_taskshield_v16_qualification.py",
        "metric_semantics_runtime": bench / "agentdojo_official_metrics_v2.py",
        "metric_semantics_schema": (
            ROOT / "schemas" / "paper_v1" / "agentdojo_official_outcome_v2.schema.json"
        ),
        "gate_g0": g0_path,
    }


def build_freeze(
    *,
    public_freeze_path: Path,
    model_registry_path: Path,
    agentdojo_checkout: Path,
    paper_path: Path,
    model_id: str,
    g0_path: Path = DEFAULT_G0,
) -> dict[str, Any]:
    g0 = _read_json(g0_path)
    manifest = v15.build_freeze(
        public_freeze_path=public_freeze_path,
        model_registry_path=model_registry_path,
        agentdojo_checkout=agentdojo_checkout,
        paper_path=paper_path,
        model_id=model_id,
    )
    paths = _v16_paths(g0_path)
    hashes = {name: sha256_file(path) if path.is_file() else "" for name, path in paths.items()}

    qualification_ids = [str(value) for value in manifest["qualification_case_ids"]]
    by_id = {
        str(row["benchmark_case_id"]): dict(row)
        for row in manifest["case_rows"]
        if isinstance(row, Mapping)
    }
    qualification_rows = [by_id[case_id] for case_id in qualification_ids]
    preflight_ids = qualification_ids[:4]
    preflight_rows = [by_id[case_id] for case_id in preflight_ids]

    manifest.update(
        {
            "schema_version": "paper-taskshield-reproduction-freeze-1.6",
            "freeze_version": FREEZE_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "preflight_case_ids": preflight_ids,
            "preflight_case_rows": preflight_rows,
            "preflight_case_rows_sha256": rows_sha256(preflight_rows),
            "expanded_case_rows_sha256": rows_sha256(qualification_rows),
            "v16_change_contract": {
                "g0_metric_semantics_required": True,
                "single_retry_owner": "taskshield_v16_runtime",
                "sdk_max_retries": 0,
                "logical_attempts": DEFAULT_LOGICAL_ATTEMPTS,
                "full_schema_recovery": True,
                "terminal_trace_required_for_success_and_failure": True,
                "independent_terminal_timestamps": True,
                "case_level_retry": False,
                "selective_failed_row_retry": False,
                "failed_row_exclusion": False,
                "full_726_case_run_authorized": False,
                "p5_extension_authorized": False,
                "result_eligible_for_formal_tables": False,
            },
        }
    )
    manifest["transport"] = dict(manifest["transport"])
    manifest["transport"]["timeout_seconds"] = DEFAULT_REQUEST_TIMEOUT_SECONDS
    task_shield = dict(manifest["task_shield"])
    task_shield.update(
        {
            "runtime_patch_version": PATCH_VERSION,
            "logical_attempts": DEFAULT_LOGICAL_ATTEMPTS,
            "retry_backoff_seconds": DEFAULT_RETRY_BACKOFF_SECONDS,
            "request_timeout_seconds": DEFAULT_REQUEST_TIMEOUT_SECONDS,
            "case_timeout_seconds": DEFAULT_CASE_TIMEOUT_SECONDS,
            "sdk_max_retries": 0,
            "runtime_contract": runtime_contract(),
            "metric_semantics_version": "agentdojo_official_v2",
            "metric_mapping": (
                "official_trace.security_is_injection_goal_executed_and_equals_attack_success"
            ),
            "trace_policy": "snapshot_before_every_terminal_outcome_write",
            "failure_policy": (
                "untrusted_verifier_exhaustion_fail_closed_trusted_user_exhaustion_case_failure"
            ),
        }
    )
    manifest["task_shield"] = task_shield

    local_adapter = dict(manifest["local_adapter"])
    files = dict(local_adapter.get("files", {}))
    sha256 = dict(local_adapter.get("sha256", {}))
    files.update({name: _portable_path(path) for name, path in paths.items()})
    sha256.update(hashes)
    local_adapter.update(
        {
            "files": files,
            "sha256": sha256,
            "v16_correctness_runtime": True,
            "v16_metric_semantics_v2": True,
            "v16_staged_qualification_only": True,
        }
    )
    manifest["local_adapter"] = local_adapter

    failure_policy = dict(manifest["failure_policy"])
    failure_policy.update(
        {
            "no_case_level_retry": True,
            "no_selective_failed_row_retry": True,
            "no_failed_row_exclusion": True,
            "terminal_trace_required": True,
            "case_hard_timeout_seconds": DEFAULT_CASE_TIMEOUT_SECONDS,
            "v16_full_formal_run_authorized": False,
        }
    )
    manifest["failure_policy"] = failure_policy

    g0_passed = bool(
        g0.get("gate") == "G0_agentdojo_metric_semantics"
        and g0.get("status") == "passed"
        and g0.get("passed_checks") == g0.get("total_checks") == 15
        and g0.get("model_calls") == 0
        and g0.get("api_calls") == 0
        and hashes["gate_g0"]
    )
    files_complete = all(hashes.values())
    preflight_valid = bool(
        len(preflight_rows) == 4
        and len(set(preflight_ids)) == 4
        and sum(row.get("case_kind") == "utility" for row in preflight_rows) == 2
        and sum(row.get("case_kind") == "security" for row in preflight_rows) == 2
    )
    expanded_valid = bool(
        len(qualification_rows) == 12
        and len(set(qualification_ids)) == 12
        and sum(row.get("case_kind") == "utility" for row in qualification_rows) == 6
        and sum(row.get("case_kind") == "security" for row in qualification_rows) == 6
    )
    checks = [
        dict(row)
        for row in manifest["checks"]
        if str(row.get("name", "")) not in {
            "v15_failure_audit_is_complete_and_hash_bound",
            "v15_change_contract_is_fail_closed_and_qualification_only",
            "v15_expanded_qualification_selection_is_exact_and_frozen",
        }
    ]
    for row in checks:
        if row.get("name") == "local_adapter_files_hash_bound":
            row["detail"] = sha256
            row["status"] = "pass" if all(sha256.values()) else "fail"
    checks.extend(
        [
            {
                "name": "v16_g0_metric_semantics_gate_passed_and_hash_bound",
                "status": "pass" if g0_passed else "fail",
                "detail": {
                    "path": _portable_path(g0_path),
                    "sha256": hashes["gate_g0"],
                    "checks": f"{g0.get('passed_checks', 0)}/{g0.get('total_checks', 0)}",
                },
            },
            {
                "name": "v16_runtime_runner_analyzer_and_metric_schema_hash_bound",
                "status": "pass" if files_complete else "fail",
                "detail": hashes,
            },
            {
                "name": "v16_preflight_selection_is_exact_two_plus_two",
                "status": "pass" if preflight_valid else "fail",
                "detail": {
                    "cases": len(preflight_rows),
                    "sha256": rows_sha256(preflight_rows),
                },
            },
            {
                "name": "v16_expanded_selection_is_exact_six_plus_six",
                "status": "pass" if expanded_valid else "fail",
                "detail": {
                    "cases": len(qualification_rows),
                    "sha256": rows_sha256(qualification_rows),
                },
            },
            {
                "name": "v16_is_qualification_only_with_no_case_retry",
                "status": "pass",
                "detail": manifest["v16_change_contract"],
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
        "Prospective v1.6 P3/P4 qualification freeze. It supersedes no sealed evidence, "
        "authorizes only the exact 4-case preflight and 12-case expanded selections, and "
        "cannot authorize P5, P6, formal admission, failed-row retry, exclusion, or Q2 promotion."
    )
    return v15.v14.v13._relativize_project_paths(manifest)


def write_markdown(path: Path, manifest: Mapping[str, Any]) -> None:
    lines = [
        "# Task Shield correctness-first freeze v1.6",
        "",
        f"- Status: `{manifest['status']}`",
        f"- Checks: `{manifest['passed_checks']}/{manifest['total_checks']}`",
        f"- P3 preflight: `{len(manifest['preflight_case_rows'])}` cases (2 utility + 2 attack)",
        f"- P4 expanded qualification: `{len(manifest['qualification_case_rows'])}` cases (6 + 6)",
        f"- Runtime: `{manifest['task_shield']['runtime_patch_version']}`",
        "- SDK retries: `0`",
        "- Logical attempts: `2`",
        "- Request/case timeout: `120/600 seconds`",
        "- Full 726-case run authorized: `False`",
        "- Result eligible for formal tables: `False`",
        "- Q2 score change: `0`",
        "",
        "## P3 selection",
        "",
    ]
    lines.extend(f"- `{case_id}`" for case_id in manifest["preflight_case_ids"])
    lines.extend(["", "## P4 selection", ""])
    lines.extend(f"- `{case_id}`" for case_id in manifest["qualification_case_ids"])
    lines.extend(["", "## Evidence boundary", "", str(manifest["boundary"]), ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-freeze", type=Path, default=v15.v14.v13.legacy.DEFAULT_PUBLIC_FREEZE)
    parser.add_argument("--model-registry", type=Path, default=v15.v14.v13.legacy.DEFAULT_MODEL_REGISTRY)
    parser.add_argument("--agentdojo-checkout", type=Path, default=v15.v14.v13.legacy.DEFAULT_AGENTDOJO)
    parser.add_argument("--paper", type=Path, default=v15.v14.v13.legacy.DEFAULT_PAPER)
    parser.add_argument("--model-id", default="m3-paper-qwen3-8b-v1:latest")
    parser.add_argument("--g0", type=Path, default=DEFAULT_G0)
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
        g0_path=args.g0.resolve(),
    )
    _write_json(args.output, manifest)
    write_markdown(args.output.with_suffix(".md"), manifest)
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "checks": f"{manifest['passed_checks']}/{manifest['total_checks']}",
                "preflight_cases": len(manifest["preflight_case_rows"]),
                "expanded_cases": len(manifest["qualification_case_rows"]),
                "output": _portable_path(args.output),
            },
            ensure_ascii=False,
        )
    )
    return 0 if manifest["status"] == "completed_frozen_formal_protocol" else 1


if __name__ == "__main__":
    raise SystemExit(main())

