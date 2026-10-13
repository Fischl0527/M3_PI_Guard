"""针对已准入的自适应金丝雀分析（Adaptive Canary Analysis）执行独立完整性审查。

独立复核八任务 DeepSeek 金丝雀实验的统计计算、预算开销和准入契约，
确保自适应金丝雀结果在进入正式论文结论前满足严格的不可变性与完整性标准。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import experiments.paper_v2.adaptive_canary_analysis_v1 as analysis_v1
import experiments.paper_v2.adaptive_canary_result_admission_v1 as admission_v1
import experiments.paper_v2.adaptive_recovery_technical_review_v1 as technical_v1
from experiments.paper_v2.contracts import (
    canonical_json_bytes,
    sha256_canonical_json,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ANALYSIS_ROOT = analysis_v1.DEFAULT_OUTPUT
DEFAULT_OUTPUT = ANALYSIS_ROOT / "analysis_review_v1.json"
SCHEMA_VERSION = "m3-paper-v2-adaptive-analysis-review-1.0"
REVIEWED_AT = "2026-07-30T03:07:00+08:00"


class AdaptiveCanaryAnalysisReviewError(ValueError):
    """当自适应分析中间构件无法复现时抛出的异常。"""


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AdaptiveCanaryAnalysisReviewError(
            f"{path}: expected an object"
        )
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value) + b"\n")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve(path: str) -> Path:
    value = (PROJECT_ROOT / path).resolve()
    try:
        value.relative_to(PROJECT_ROOT.resolve())
    except ValueError as exc:
        raise AdaptiveCanaryAnalysisReviewError(
            "adaptive analysis path escapes project"
        ) from exc
    return value


def build_review() -> dict[str, Any]:
    manifest_path = ANALYSIS_ROOT / "analysis_manifest.json"
    manifest = _load_json(manifest_path)
    if manifest.get("manifest_sha256") != sha256_canonical_json(
        {
            key: child
            for key, child in manifest.items()
            if key != "manifest_sha256"
        }
    ):
        raise AdaptiveCanaryAnalysisReviewError(
            "adaptive analysis manifest drift"
        )
    admission = admission_v1.validate_admission(
        _load_json(admission_v1.ADMISSION_PATH)
    )
    technical = technical_v1.verify_review()
    if (
        manifest.get("admission_manifest_sha256")
        != admission["manifest_sha256"]
        or manifest.get("technical_review_manifest_sha256")
        != technical["manifest_sha256"]
    ):
        raise AdaptiveCanaryAnalysisReviewError(
            "adaptive analysis source admission drift"
        )
    for field in ("summary", "task_results"):
        artifact = manifest.get(field)
        if not isinstance(artifact, Mapping):
            raise AdaptiveCanaryAnalysisReviewError(
                f"adaptive analysis lacks {field}"
            )
        path = _resolve(str(artifact["path"]))
        if (
            not path.is_file()
            or _sha256_file(path) != artifact["sha256"]
        ):
            raise AdaptiveCanaryAnalysisReviewError(
                f"adaptive analysis {field} hash drift"
            )
    for artifact in manifest.get("figures", []):
        path = _resolve(str(artifact["path"]))
        if (
            not path.is_file()
            or _sha256_file(path) != artifact["sha256"]
        ):
            raise AdaptiveCanaryAnalysisReviewError(
                "adaptive analysis figure hash drift"
            )
    summary = _load_json(_resolve(str(manifest["summary"]["path"])))
    with _resolve(
        str(manifest["task_results"]["path"])
    ).open(encoding="utf-8-sig", newline="") as stream:
        task_rows = list(csv.DictReader(stream))
    successes = sum(
        row["unsafe_effect_within_50"].lower() == "true"
        for row in task_rows
    )
    diagnostics = sum(int(row["diagnostic_queries"]) for row in task_rows)
    expected_estimate = analysis_v1._wilson(successes, len(task_rows))
    checks = {
        "exact_eight_task_rows": len(task_rows) == 8,
        "success_count_reproduced": (
            successes == summary["unsafe_effect_successes"]
        ),
        "diagnostic_count_reproduced": (
            diagnostics == summary["diagnostic_query_count"]
        ),
        "wilson_interval_reproduced": (
            expected_estimate == summary["unsafe_effect_rate_at_50"]
        ),
        "technical_query_count_bound": (
            summary["terminal_query_count"]
            == technical["terminal_query_count"]
        ),
        "technical_call_count_bound": (
            summary["completed_provider_call_count"]
            == technical["completed_provider_call_count"]
        ),
        "claim_boundary_preserved": (
            summary["interpretation_boundary"]
            == manifest["scientific_claim_boundary"]
            and summary["interpretation_boundary"][
                "sota_claim_authorized"
            ]
            is False
        ),
    }
    if not all(checks.values()):
        raise AdaptiveCanaryAnalysisReviewError(
            "adaptive analysis reproduction failed"
        )
    core = {
        "schema_version": SCHEMA_VERSION,
        "artifact_role": "independent_adaptive_analysis_integrity_review",
        "reviewed_at": REVIEWED_AT,
        "status": "adaptive_canary_analysis_integrity_pass",
        "analysis_manifest_sha256": manifest["manifest_sha256"],
        "summary_sha256": manifest["summary"]["sha256"],
        "task_results_sha256": manifest["task_results"]["sha256"],
        "task_count": len(task_rows),
        "unsafe_effect_successes": successes,
        "unsafe_effect_rate_at_50": expected_estimate,
        "diagnostic_query_count": diagnostics,
        "checks": checks,
        "interpretation_boundary": summary["interpretation_boundary"],
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def write_review() -> dict[str, Any]:
    value = build_review()
    _write_json(DEFAULT_OUTPUT, value)
    return value


def verify_review() -> dict[str, Any]:
    observed = _load_json(DEFAULT_OUTPUT)
    expected = build_review()
    if observed != expected:
        raise AdaptiveCanaryAnalysisReviewError(
            "adaptive analysis review drift"
        )
    return observed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    value = write_review() if args.write else verify_review()
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
