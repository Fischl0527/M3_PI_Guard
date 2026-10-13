"""验证并对比两组诊断性 E17 自动化盲审结果。

对比大模型自动化打分与人类专家评审之间的一致性指标（Kappa 评分等）。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.e17_review import (  # noqa: E402
    CONFIDENCE_LEVELS,
    EVIDENCE_FIELDS,
    PRIMARY_CODES,
    REVIEW_FIELDS,
    SOURCE_MODE_FORMAL_CORRECTED,
    load_source_index,
)


DEFAULT_ROOT = REPO_ROOT / "outputs" / "experiments" / "E17_auto_review"
DEFAULT_PACKET_ROOT = REPO_ROOT / "outputs" / "experiments" / "E17" / "packets"
DEFAULT_SOURCE_INDEX = (
    REPO_ROOT / "outputs" / "experiments" / "e17_source_index_corrected_v2.json"
)
DEFAULT_E17_MANIFEST = REPO_ROOT / "outputs" / "experiments" / "E17" / "manifest.json"
AUTOMATED_ATTESTATION = "independent_automated_review_completed"
EXPECTED_ROWS = 3379
DISAGREEMENT_FIELDS = (
    "blind_id",
    "reviewer_a_primary",
    "reviewer_a_secondary",
    "reviewer_a_confidence",
    "reviewer_a_rationale",
    "reviewer_b_primary",
    "reviewer_b_secondary",
    "reviewer_b_confidence",
    "reviewer_b_rationale",
    "primary_agrees",
    "secondary_set_agrees",
)


class AutomatedReviewValidationError(ValueError):
    """当诊断性自动化审查违反其隔离契约时抛出。"""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _record_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _read_csv(path: Path, expected_header: Sequence[str]) -> list[dict[str, str]]:
    if not path.is_file():
        raise AutomatedReviewValidationError(f"missing CSV: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != tuple(expected_header):
            raise AutomatedReviewValidationError(f"invalid header: {path}")
        return [dict(row) for row in reader]


def _load_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AutomatedReviewValidationError(f"invalid {label}: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise AutomatedReviewValidationError(f"{label} must be a JSON object: {path}")
    return value


def _validate_source_contract(
    *,
    source_index: Path,
    e17_manifest: Path,
    templates: Sequence[Path],
) -> dict[str, Any]:
    """将诊断性审查绑定到修正后的数据包源，且不包含私有标签。"""

    source_index = source_index.resolve()
    e17_manifest = e17_manifest.resolve()
    if not source_index.is_file() or not e17_manifest.is_file():
        raise AutomatedReviewValidationError("corrected source index or E17 manifest is missing")
    try:
        bundle = load_source_index(source_index)
    except Exception as exc:
        raise AutomatedReviewValidationError(
            f"corrected E17 source index failed validation: {exc}"
        ) from exc
    if bundle.get("source_mode") != SOURCE_MODE_FORMAL_CORRECTED:
        raise AutomatedReviewValidationError("automated review requires corrected formal source mode")
    manifest = _load_object(e17_manifest, label="E17 manifest")
    configuration = manifest.get("configuration")
    plan = manifest.get("plan")
    expected_hash = _sha256(source_index)
    if not isinstance(configuration, Mapping) or not isinstance(plan, Mapping):
        raise AutomatedReviewValidationError("E17 manifest lacks source-bound plan/configuration")
    if (
        configuration.get("source_mode") != SOURCE_MODE_FORMAL_CORRECTED
        or plan.get("source_mode") != SOURCE_MODE_FORMAL_CORRECTED
    ):
        raise AutomatedReviewValidationError("E17 manifest source mode is not corrected formal")
    for label, record in (
        ("configuration.source_index", configuration.get("source_index")),
        ("plan.source_index", plan.get("source_index")),
    ):
        if not isinstance(record, Mapping):
            raise AutomatedReviewValidationError(f"E17 manifest lacks {label}")
        raw = Path(str(record.get("path", "")))
        resolved = raw.resolve() if raw.is_absolute() else (REPO_ROOT / raw).resolve()
        if resolved != source_index or str(record.get("sha256", "")) != expected_hash:
            raise AutomatedReviewValidationError(f"E17 manifest {label} binding mismatch")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        raise AutomatedReviewValidationError("E17 manifest has no packet artifact ledger")
    by_path: dict[Path, Mapping[str, Any]] = {}
    for record in artifacts:
        if not isinstance(record, Mapping):
            continue
        raw = Path(str(record.get("path", "")))
        resolved = raw.resolve() if raw.is_absolute() else (REPO_ROOT / raw).resolve()
        by_path[resolved] = record
    for template in templates:
        target = template.resolve()
        record = by_path.get(target)
        if (
            record is None
            or int(record.get("bytes", -1)) != target.stat().st_size
            or str(record.get("sha256", "")) != _sha256(target)
        ):
            raise AutomatedReviewValidationError(
                f"blinded template is not hash-bound by E17 manifest: {target}"
            )
    coverage = bundle.get("coverage") or {}
    candidate_count = plan.get("candidate_count")
    if not isinstance(candidate_count, int) or candidate_count <= 0:
        raise AutomatedReviewValidationError("E17 manifest plan has no positive candidate_count")
    return {
        "source_mode": SOURCE_MODE_FORMAL_CORRECTED,
        "source_index": {"path": _record_path(source_index), "sha256": expected_hash},
        "e17_manifest": {"path": _record_path(e17_manifest), "sha256": _sha256(e17_manifest)},
        "coverage_status": coverage.get("status"),
        "duplicate_logical_run_count": coverage.get("duplicate_logical_run_count"),
        "duplicate_logical_step_count": coverage.get("duplicate_logical_step_count"),
        "candidate_count": candidate_count,
    }


def _index_rows(
    rows: Sequence[Mapping[str, str]],
    *,
    source: Path,
    expected_rows: int | None = None,
) -> dict[str, dict[str, str]]:
    expected_rows = EXPECTED_ROWS if expected_rows is None else int(expected_rows)
    if len(rows) != expected_rows:
        raise AutomatedReviewValidationError(
            f"{source} has {len(rows)} rows; expected {expected_rows}"
        )
    indexed: dict[str, dict[str, str]] = {}
    for row_number, row in enumerate(rows, start=2):
        blind_id = str(row.get("blind_id", "")).strip()
        if not blind_id:
            raise AutomatedReviewValidationError(f"blank blind_id at {source}:{row_number}")
        if blind_id in indexed:
            raise AutomatedReviewValidationError(f"duplicate blind_id {blind_id} in {source}")
        indexed[blind_id] = dict(row)
    return indexed


def _secondary_set(value: str, *, blind_id: str, primary: str) -> tuple[str, ...]:
    codes = [code.strip().lower() for code in value.replace(",", "|").split("|") if code.strip()]
    if len(codes) != len(set(codes)):
        raise AutomatedReviewValidationError(f"duplicate secondary code for {blind_id}")
    invalid = [code for code in codes if code not in PRIMARY_CODES or code == "none"]
    if invalid:
        raise AutomatedReviewValidationError(f"invalid secondary code for {blind_id}: {invalid}")
    if primary in codes:
        raise AutomatedReviewValidationError(f"primary code repeated as secondary for {blind_id}")
    return tuple(sorted(codes))


def _validate_review(
    review_path: Path,
    template_path: Path,
    *,
    expected_rows: int | None = None,
) -> tuple[str, dict[str, dict[str, str]], dict[str, tuple[str, ...]]]:
    template = _index_rows(
        _read_csv(template_path, REVIEW_FIELDS),
        source=template_path,
        expected_rows=expected_rows,
    )
    review = _index_rows(
        _read_csv(review_path, REVIEW_FIELDS),
        source=review_path,
        expected_rows=expected_rows,
    )
    if set(template) != set(review):
        raise AutomatedReviewValidationError(f"blind_id coverage drift: {review_path}")

    reviewer_ids: set[str] = set()
    secondary: dict[str, tuple[str, ...]] = {}
    for blind_id in template:
        original = template[blind_id]
        completed = review[blind_id]
        for field in EVIDENCE_FIELDS:
            if completed[field] != original[field]:
                raise AutomatedReviewValidationError(
                    f"evidence field {field} changed for {blind_id}: {review_path}"
                )
        reviewer_id = completed["reviewer_id"].strip()
        if not reviewer_id:
            raise AutomatedReviewValidationError(f"blank reviewer_id for {blind_id}")
        reviewer_ids.add(reviewer_id)
        if completed["independent_attestation"].strip() != AUTOMATED_ATTESTATION:
            raise AutomatedReviewValidationError(f"invalid automated attestation for {blind_id}")
        primary = completed["primary_code"].strip().lower()
        if primary not in PRIMARY_CODES:
            raise AutomatedReviewValidationError(f"invalid primary code for {blind_id}: {primary}")
        confidence = completed["confidence"].strip().lower()
        if confidence not in CONFIDENCE_LEVELS:
            raise AutomatedReviewValidationError(
                f"invalid confidence for {blind_id}: {confidence}"
            )
        if len(completed["rationale"].strip()) < 5:
            raise AutomatedReviewValidationError(f"short rationale for {blind_id}")
        secondary[blind_id] = _secondary_set(
            completed["secondary_codes"], blind_id=blind_id, primary=primary
        )

    if len(reviewer_ids) != 1:
        raise AutomatedReviewValidationError(
            f"one automated reviewer_id required in {review_path}; got {sorted(reviewer_ids)}"
        )
    return next(iter(reviewer_ids)), review, secondary


def _wilson_interval(numerator: int, denominator: int) -> tuple[float, float]:
    if denominator <= 0:
        return (0.0, 0.0)
    z = 1.959963984540054
    p = numerator / denominator
    z2 = z * z
    centre = (p + z2 / (2 * denominator)) / (1 + z2 / denominator)
    half = (
        z
        * math.sqrt((p * (1 - p) + z2 / (4 * denominator)) / denominator)
        / (1 + z2 / denominator)
    )
    return (max(0.0, centre - half), min(1.0, centre + half))


def _cohen_kappa(left: Sequence[str], right: Sequence[str]) -> float | None:
    if len(left) != len(right) or not left:
        return None
    total = len(left)
    observed = sum(a == b for a, b in zip(left, right)) / total
    left_counts = Counter(left)
    right_counts = Counter(right)
    expected = sum(
        (left_counts[code] / total) * (right_counts[code] / total)
        for code in PRIMARY_CODES
    )
    if math.isclose(expected, 1.0):
        return 1.0 if math.isclose(observed, 1.0) else None
    return (observed - expected) / (1 - expected)


def _write_text_atomic(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _write_csv_atomic(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=DISAGREEMENT_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def compare(
    *,
    reviewer_a: Path,
    reviewer_b: Path,
    template_a: Path,
    template_b: Path,
    output_dir: Path,
    source_index: Path | None = None,
    e17_manifest: Path | None = None,
) -> dict[str, Any]:
    if (source_index is None) != (e17_manifest is None):
        raise AutomatedReviewValidationError(
            "source_index and e17_manifest must be provided together"
        )
    source_contract = (
        _validate_source_contract(
            source_index=source_index,
            e17_manifest=e17_manifest,
            templates=(template_a, template_b),
        )
        if source_index is not None and e17_manifest is not None
        else None
    )
    expected_rows = (
        int(source_contract["candidate_count"])
        if source_contract is not None
        else EXPECTED_ROWS
    )
    reviewer_a_id, left, left_secondary = _validate_review(
        reviewer_a, template_a, expected_rows=expected_rows
    )
    reviewer_b_id, right, right_secondary = _validate_review(
        reviewer_b, template_b, expected_rows=expected_rows
    )
    if reviewer_a_id.casefold() == reviewer_b_id.casefold():
        raise AutomatedReviewValidationError("automated reviewer IDs must be distinct")
    ids = sorted(left)
    if set(ids) != set(right):
        raise AutomatedReviewValidationError("reviewer blind_id sets differ")

    left_primary = [left[item]["primary_code"].strip().lower() for item in ids]
    right_primary = [right[item]["primary_code"].strip().lower() for item in ids]
    primary_agreements = sum(a == b for a, b in zip(left_primary, right_primary))
    secondary_agreements = sum(left_secondary[item] == right_secondary[item] for item in ids)
    full_agreements = sum(
        left[item]["primary_code"].strip().lower() == right[item]["primary_code"].strip().lower()
        and left_secondary[item] == right_secondary[item]
        for item in ids
    )
    primary_ci = _wilson_interval(primary_agreements, len(ids))
    full_ci = _wilson_interval(full_agreements, len(ids))

    confusion = {
        left_code: {right_code: 0 for right_code in PRIMARY_CODES}
        for left_code in PRIMARY_CODES
    }
    disagreements: list[dict[str, Any]] = []
    for blind_id in ids:
        left_code = left[blind_id]["primary_code"].strip().lower()
        right_code = right[blind_id]["primary_code"].strip().lower()
        confusion[left_code][right_code] += 1
        primary_agrees = left_code == right_code
        secondary_agrees = left_secondary[blind_id] == right_secondary[blind_id]
        if not (primary_agrees and secondary_agrees):
            disagreements.append(
                {
                    "blind_id": blind_id,
                    "reviewer_a_primary": left_code,
                    "reviewer_a_secondary": "|".join(left_secondary[blind_id]),
                    "reviewer_a_confidence": left[blind_id]["confidence"].strip().lower(),
                    "reviewer_a_rationale": left[blind_id]["rationale"].strip(),
                    "reviewer_b_primary": right_code,
                    "reviewer_b_secondary": "|".join(right_secondary[blind_id]),
                    "reviewer_b_confidence": right[blind_id]["confidence"].strip().lower(),
                    "reviewer_b_rationale": right[blind_id]["rationale"].strip(),
                    "primary_agrees": str(primary_agrees).lower(),
                    "secondary_set_agrees": str(secondary_agrees).lower(),
                }
            )

    result: dict[str, Any] = {
        "schema_version": "e17-diagnostic-automated-review-comparison-v1",
        "diagnostic_only": True,
        "human_review_gate_satisfied": False,
        "eligible_for_formal_e17_submission": False,
        "source_contract": source_contract,
        "reviewer_a": {
            "reviewer_id": reviewer_a_id,
            "path": _record_path(reviewer_a),
            "sha256": _sha256(reviewer_a),
            "primary_counts": dict(sorted(Counter(left_primary).items())),
        },
        "reviewer_b": {
            "reviewer_id": reviewer_b_id,
            "path": _record_path(reviewer_b),
            "sha256": _sha256(reviewer_b),
            "primary_counts": dict(sorted(Counter(right_primary).items())),
        },
        "templates": [
            {"path": _record_path(template_a), "sha256": _sha256(template_a)},
            {"path": _record_path(template_b), "sha256": _sha256(template_b)},
        ],
        "items": len(ids),
        "primary_agreement": {
            "count": primary_agreements,
            "rate": primary_agreements / len(ids),
            "wilson_95_ci": {"low": primary_ci[0], "high": primary_ci[1]},
            "cohen_kappa": _cohen_kappa(left_primary, right_primary),
        },
        "secondary_set_agreement": {
            "count": secondary_agreements,
            "rate": secondary_agreements / len(ids),
        },
        "full_code_set_agreement": {
            "count": full_agreements,
            "rate": full_agreements / len(ids),
            "wilson_95_ci": {"low": full_ci[0], "high": full_ci[1]},
        },
        "disagreements": len(disagreements),
        "primary_confusion_matrix": confusion,
        "isolation_boundary": {
            "inputs": [
                _record_path(reviewer_a),
                _record_path(reviewer_b),
                _record_path(template_a),
                _record_path(template_b),
                *(
                    [
                        _record_path(source_index),
                        _record_path(e17_manifest),
                    ]
                    if source_index is not None and e17_manifest is not None
                    else []
                ),
            ],
            "excluded": [
                "outputs/experiments/E17/private",
                "experiments/registry.json",
                "human reviewer packets and submissions",
            ],
        },
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    disagreement_path = output_dir / "automated_disagreements.csv"
    comparison_path = output_dir / "comparison.json"
    report_path = output_dir / "comparison.md"
    _write_csv_atomic(disagreement_path, disagreements)
    result["outputs"] = {
        "comparison": _record_path(comparison_path),
        "disagreements": _record_path(disagreement_path),
        "disagreements_sha256": _sha256(disagreement_path),
    }
    markdown = "\n".join(
        [
            "# E17 Diagnostic Automated Blind-Review Comparison",
            "",
            "> Diagnostic only. This comparison does not satisfy or replace either required human blind review.",
            "",
            f"- Items: {len(ids):,}",
            f"- Primary-code agreement: {primary_agreements:,}/{len(ids):,} ({primary_agreements / len(ids):.1%}; Wilson 95% CI {primary_ci[0]:.1%}-{primary_ci[1]:.1%})",
            f"- Cohen's kappa: {result['primary_agreement']['cohen_kappa']:.3f}" if result["primary_agreement"]["cohen_kappa"] is not None else "- Cohen's kappa: undefined",
            f"- Full primary+secondary agreement: {full_agreements:,}/{len(ids):,} ({full_agreements / len(ids):.1%}; Wilson 95% CI {full_ci[0]:.1%}-{full_ci[1]:.1%})",
            f"- Items requiring diagnostic reconciliation: {len(disagreements):,}",
            "",
            "The completed human packets remain the sole formal E17 inputs. Automated disagreements are not shown to either human reviewer.",
            "",
        ]
    )
    _write_text_atomic(report_path, markdown)
    result["outputs"]["report"] = _record_path(report_path)
    result["outputs"]["report_sha256"] = _sha256(report_path)
    _write_text_atomic(comparison_path, json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reviewer-a", type=Path, default=DEFAULT_ROOT / "reviewer_a_canonical_completed.csv"
    )
    parser.add_argument(
        "--reviewer-b", type=Path, default=DEFAULT_ROOT / "reviewer_b_canonical_completed.csv"
    )
    parser.add_argument("--template-a", type=Path, default=DEFAULT_PACKET_ROOT / "reviewer_1_blinded_template.csv")
    parser.add_argument("--template-b", type=Path, default=DEFAULT_PACKET_ROOT / "reviewer_2_blinded_template.csv")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--source-index", type=Path, default=DEFAULT_SOURCE_INDEX)
    parser.add_argument("--e17-manifest", type=Path, default=DEFAULT_E17_MANIFEST)
    args = parser.parse_args(argv)
    result = compare(
        reviewer_a=args.reviewer_a.resolve(),
        reviewer_b=args.reviewer_b.resolve(),
        template_a=args.template_a.resolve(),
        template_b=args.template_b.resolve(),
        output_dir=args.output_dir.resolve(),
        source_index=args.source_index.resolve(),
        e17_manifest=args.e17_manifest.resolve(),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
