"""Run Task Shield disclosed paper reproduction v1.3.

This wrapper preserves the v1.2 runner/runtime files and installs the v1.3
fail-closed contribution-scoring patch before delegating to the hash-bound
runner implementation.  It is used with a separate v1.3 freeze and output root.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from . import run_taskshield_paper_formal as legacy
from .taskshield_paper_runtime_v13 import (
    PATCH_VERSION,
    install_fail_closed_scoring_patch,
)


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_FREEZE = (
    ROOT / "protocols" / "paper_upgrade_v1" / "taskshield_paper_formal_freeze_v13.json"
)
DEFAULT_OUTPUT = (
    ROOT / "outputs" / "paper_upgrade_v1" / "baselines" / "taskshield_paper_formal_v13"
)
RUNNER_VERSION = "m3-paper-v1-taskshield-paper-runner-1.3"


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
    patch = install_fail_closed_scoring_patch()
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
