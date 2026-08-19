"""Run the fresh Task Shield v1.5 post-hoc qualification protocol."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from . import run_taskshield_paper_formal as legacy
from .common import portable_path
from .taskshield_paper_runtime_v15 import (
    DEFAULT_CONTRACT_RETRY_ATTEMPTS,
    DEFAULT_RETRY_BACKOFF_SECONDS,
    DEFAULT_TIMEOUT_RETRY_ATTEMPTS,
    PATCH_VERSION,
    install_contract_recovery_patch,
)


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_FREEZE = (
    ROOT / "protocols" / "paper_upgrade_v1" / "taskshield_paper_formal_freeze_v15.json"
)
DEFAULT_OUTPUT = (
    ROOT
    / "outputs"
    / "paper_upgrade_v1"
    / "baselines"
    / "taskshield_paper_qualification_v15_expanded"
)
RUNNER_VERSION = "m3-paper-v1-taskshield-paper-runner-1.5"


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def _install_environment(freeze: dict[str, Any]) -> dict[str, str]:
    task_shield = freeze.get("task_shield", {})
    values = {
        "M3_TASKSHIELD_TIMEOUT_RETRY_ATTEMPTS": str(
            int(task_shield.get("timeout_retry_attempts", DEFAULT_TIMEOUT_RETRY_ATTEMPTS))
        ),
        "M3_TASKSHIELD_CONTRACT_RETRY_ATTEMPTS": str(
            int(task_shield.get("contract_retry_attempts", DEFAULT_CONTRACT_RETRY_ATTEMPTS))
        ),
        "M3_TASKSHIELD_RETRY_BACKOFF_SECONDS": str(
            float(task_shield.get("retry_backoff_seconds", DEFAULT_RETRY_BACKOFF_SECONDS))
        ),
    }
    previous = {key: os.environ.get(key, "") for key in values}
    os.environ.update(values)
    return previous


def _restore_environment(previous: dict[str, str]) -> None:
    for key, value in previous.items():
        if value:
            os.environ[key] = value
        else:
            os.environ.pop(key, None)


def _normalize_project_paths(result: dict[str, Any]) -> None:
    for key in ("freeze_path", "output_dir", "outcomes_path", "progress_path"):
        value = result.get(key)
        if value:
            result[key] = portable_path(Path(str(value)), root=ROOT)


def run(
    *,
    freeze_path: Path,
    output_dir: Path,
    case_limit: int | None,
    case_ids: list[str] | None,
    admit_formal: bool,
    resume: bool,
) -> dict[str, Any]:
    freeze = _read_json(freeze_path)
    contract = freeze.get("v15_change_contract", {})
    if admit_formal and contract.get("full_726_case_run_authorized") is not True:
        raise ValueError(
            "v1.5 freeze authorizes expanded qualification only, not a full formal run"
        )
    previous_environment = _install_environment(freeze)
    patch = install_contract_recovery_patch()
    previous_version = legacy.RUNNER_VERSION
    previous_cwd = Path.cwd()
    legacy.RUNNER_VERSION = RUNNER_VERSION
    try:
        os.chdir(ROOT)
        result = legacy.run(
            freeze_path=freeze_path,
            output_dir=output_dir,
            case_limit=case_limit,
            case_ids=case_ids,
            admit_formal=admit_formal,
            resume=resume,
            retry_failed=False,
        )
    finally:
        os.chdir(previous_cwd)
        legacy.RUNNER_VERSION = previous_version
        _restore_environment(previous_environment)

    expected_ids = set(freeze.get("qualification_case_ids", []))
    requested_ids = set(case_ids or [])
    summary = result.get("summary", {})
    exact_qualification = bool(
        expected_ids
        and requested_ids == expected_ids
        and len(requested_ids) == 12
        and int(summary.get("expected_cases", 0)) == 12
    )
    qualification_passed = bool(
        exact_qualification
        and int(summary.get("completed_cases", 0)) == 12
        and int(summary.get("failed_cases", 0)) == 0
        and int(summary.get("missing_cases", 0)) == 0
    )
    result.update(
        {
            "runtime_patch": patch | {"patch_version": PATCH_VERSION},
            "post_hoc_failure_recovery_disclosed": True,
            "qualification_protocol": {
                "exact_frozen_selection": exact_qualification,
                "passed_operational_gate": qualification_passed,
                "result_eligible_for_formal_tables": False,
                "full_formal_run_authorized": False,
            },
            "result_eligible_for_formal_tables": False,
            "formal_admission_blockers": sorted(
                set(result.get("formal_admission_blockers", []))
                | {"v15_expanded_qualification_is_not_formal_evidence"}
            ),
        }
    )
    _normalize_project_paths(result)
    legacy._write_json(output_dir / "run_manifest.json", result)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", type=Path, default=DEFAULT_FREEZE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--case-limit", type=int, default=None)
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--admit-formal", action="store_true")
    parser.add_argument("--no-resume", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run(
        freeze_path=args.freeze.resolve(),
        output_dir=args.output_dir.resolve(),
        case_limit=args.case_limit,
        case_ids=list(args.case_id),
        admit_formal=args.admit_formal,
        resume=not args.no_resume,
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "summary": result["summary"],
                "result_eligible": result["result_eligible_for_formal_tables"],
                "qualification_protocol": result["qualification_protocol"],
                "manifest": portable_path(args.output_dir / "run_manifest.json", root=ROOT),
                "runtime_patch": result.get("runtime_patch", {}),
            },
            ensure_ascii=False,
        )
    )
    return 0 if result["status"] == "completed_diagnostic_partial" else 1


if __name__ == "__main__":
    raise SystemExit(main())
