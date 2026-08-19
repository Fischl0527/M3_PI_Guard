"""Run Task Shield disclosed paper reproduction v1.4.

v1.4 is a failure-recovery protocol for the v1.3 timeout failure.  It installs
the v1.3 fail-closed scoring patch plus a frozen, trace-logged verifier
transport timeout retry policy, then delegates to the unchanged formal runner.
It must be run from a fresh output root; it is not a selective retry of v1.3.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from . import run_taskshield_paper_formal as legacy
from .taskshield_paper_runtime_v14 import (
    DEFAULT_TIMEOUT_RETRY_ATTEMPTS,
    DEFAULT_TIMEOUT_RETRY_BACKOFF_SECONDS,
    PATCH_VERSION,
    install_timeout_retry_patch,
)


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_FREEZE = (
    ROOT / "protocols" / "paper_upgrade_v1" / "taskshield_paper_formal_freeze_v14.json"
)
DEFAULT_OUTPUT = (
    ROOT / "outputs" / "paper_upgrade_v1" / "baselines" / "taskshield_paper_formal_v14"
)
RUNNER_VERSION = "m3-paper-v1-taskshield-paper-runner-1.4"


def _read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(str(path) + " must contain an object")
    return value


def _install_retry_environment(freeze: dict) -> dict[str, str]:
    task_shield = freeze.get("task_shield", {})
    attempts = int(
        task_shield.get("timeout_retry_attempts", DEFAULT_TIMEOUT_RETRY_ATTEMPTS)
    )
    backoff_seconds = float(
        task_shield.get(
            "timeout_retry_backoff_seconds",
            DEFAULT_TIMEOUT_RETRY_BACKOFF_SECONDS,
        )
    )
    previous = {
        "M3_TASKSHIELD_TIMEOUT_RETRY_ATTEMPTS": os.environ.get(
            "M3_TASKSHIELD_TIMEOUT_RETRY_ATTEMPTS",
            "",
        ),
        "M3_TASKSHIELD_TIMEOUT_RETRY_BACKOFF_SECONDS": os.environ.get(
            "M3_TASKSHIELD_TIMEOUT_RETRY_BACKOFF_SECONDS",
            "",
        ),
    }
    os.environ["M3_TASKSHIELD_TIMEOUT_RETRY_ATTEMPTS"] = str(attempts)
    os.environ["M3_TASKSHIELD_TIMEOUT_RETRY_BACKOFF_SECONDS"] = str(backoff_seconds)
    return previous


def _restore_environment(previous: dict[str, str]) -> None:
    for key, value in previous.items():
        if value:
            os.environ[key] = value
        else:
            os.environ.pop(key, None)


def run(
    *,
    freeze_path: Path,
    output_dir: Path,
    case_limit: int | None,
    case_ids: list[str] | None,
    admit_formal: bool,
    resume: bool,
    retry_failed: bool,
) -> dict:
    freeze = _read_json(freeze_path)
    previous_environment = _install_retry_environment(freeze)
    patch = install_timeout_retry_patch()
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
            retry_failed=retry_failed,
        )
    finally:
        os.chdir(previous_cwd)
        legacy.RUNNER_VERSION = previous_version
        _restore_environment(previous_environment)
    result["runtime_patch"] = patch | {"patch_version": PATCH_VERSION}
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
    parser.add_argument("--retry-failed", action="store_true")
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
        retry_failed=args.retry_failed,
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "summary": result["summary"],
                "result_eligible": result["result_eligible_for_formal_tables"],
                "manifest": str((args.output_dir / "run_manifest.json").resolve()),
                "runtime_patch": result.get("runtime_patch", {}),
            },
            ensure_ascii=False,
        )
    )
    return 0 if result["status"] in {"completed_formal", "completed_diagnostic_partial"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
