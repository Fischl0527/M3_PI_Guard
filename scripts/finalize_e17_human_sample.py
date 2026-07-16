"""Validate and freeze the completed E17 360-row two-human audit sample."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.e17_human_sample_review import (
    DEFAULT_OUTPUT_DIR,
    DEFAULT_PACKAGE_DIR,
    DEFAULT_REVIEWER_1,
    DEFAULT_REVIEWER_2,
    HumanSampleReviewError,
    finalize_sample_review,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-dir", type=Path, default=DEFAULT_PACKAGE_DIR)
    parser.add_argument("--reviewer-1", type=Path, default=DEFAULT_REVIEWER_1)
    parser.add_argument("--reviewer-2", type=Path, default=DEFAULT_REVIEWER_2)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = finalize_sample_review(
            package_dir=args.package_dir,
            reviewer_1_path=args.reviewer_1,
            reviewer_2_path=args.reviewer_2,
            output_dir=args.output_dir,
        )
    except HumanSampleReviewError as exc:
        raise SystemExit(f"E17 sampled human review rejected: {exc}") from exc
    print(
        json.dumps(
            {
                "manifest_path": result["manifest_path"],
                "status": result["manifest"]["status"],
                "reviewed_rows": result["interrater"]["items"],
                "agreements": result["interrater"]["agreements"],
                "disagreements": result["interrater"]["disagreements"],
                "cohen_kappa": result["interrater"]["cohen_kappa"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
