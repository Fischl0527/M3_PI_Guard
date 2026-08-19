"""Audit an independently authored M3-v2 blind candidate.

The existing ``m3_v2_sealed_holdout`` split is useful for engineering
regression, but it was produced by the deterministic local generator and must
not be upgraded into confirmatory blind evidence.  This audit defines the
admission gate for a future independently authored blind candidate without
reading any model outputs or changing historical freezes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .common import portable_value, rows_sha256, sha256_file


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CANDIDATE = (
    ROOT / "m3_attacks" / "cases" / "paper_v1" / "m3_v2_independent_blind_candidate.jsonl"
)
DEFAULT_CUSTODY_FILENAME = "m3_v2_independent_blind_custody.json"
DEFAULT_REFERENCE_DATASET = ROOT / "m3_attacks" / "cases" / "paper_v1" / "m3_v2_all.jsonl"
DEFAULT_OUTPUT = ROOT / "protocols" / "paper_upgrade_v1"
PREREGISTRATION_SNAPSHOT_STEM = "m3_v2_independent_blind_admission_audit_v1"
AUDIT_STEM = "m3_v2_independent_blind_admission_audit_v2"
AUDIT_VERSION = "m3-paper-v1-m3-v2-independent-blind-admission-audit-1.1"
EXPECTED_COUNTS = {"attack": 360, "benign_no_tool": 120, "benign_legal_tool": 120}
EXPECTED_ATTACK_FAMILIES = {
    "direct_jailbreak",
    "rag_indirect",
    "multilingual_t2l",
    "json_rpc",
    "tool_output_injection",
    "memory_poisoning",
    "environment_context_pollution",
    "cross_tool_attack_chain",
    "obfuscation_evasion",
}
FORBIDDEN_RUNTIME_FIELDS = {
    "authorized_actions",
    "requires_tool",
    "expected_safe_behavior",
    "unsafe_target_actions",
    "expected_answer",
    "detector_answer",
    "target_actions",
    "ExpectedSafeBehavior",
}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash_runtime_view(case: Mapping[str, Any]) -> str:
    runtime = {
        key: case.get(key)
        for key in (
            "trusted_user_request",
            "trusted_app_context",
            "untrusted_content",
            "untrusted_memory",
        )
    }
    return hashlib.sha256(_canonical_json(runtime).encode("utf-8")).hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_no} must contain a JSON object")
        rows.append(value)
    return rows


def _read_reference(path: Path) -> list[dict[str, Any]]:
    return _read_jsonl(path) if path.exists() else []


def _read_json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _is_non_placeholder_text(value: Any) -> bool:
    text = str(value or "").strip()
    return bool(text) and not (text.startswith("<") and text.endswith(">"))


def _is_iso8601(value: Any) -> bool:
    try:
        datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return False
    return True


def _check(name: str, passed: bool, detail: Any = None, *, severity: str = "error") -> dict[str, Any]:
    return {
        "name": name,
        "status": "pass" if passed else "fail",
        "severity": severity,
        "detail": detail,
    }


def _counts_by(rows: Iterable[Mapping[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(key, "")) for row in rows).items()))


def _template_splits(rows: Iterable[Mapping[str, Any]]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        result[str(row.get("template_id", ""))].add(str(row.get("split", "")))
    return result


def build_independent_blind_audit(
    *,
    candidate_path: Path = DEFAULT_CANDIDATE,
    custody_manifest_path: Path | None = None,
    reference_dataset_path: Path = DEFAULT_REFERENCE_DATASET,
    output_dir: Path = DEFAULT_OUTPUT,
    audit_stem: str = AUDIT_STEM,
) -> dict[str, Any]:
    candidate_path = candidate_path.resolve()
    custody_manifest_path = (
        custody_manifest_path.resolve()
        if custody_manifest_path is not None
        else candidate_path.with_name(DEFAULT_CUSTODY_FILENAME)
    )
    reference_dataset_path = reference_dataset_path.resolve()
    output_dir = output_dir.resolve()
    created_at = datetime.now(timezone.utc).isoformat()
    if not candidate_path.exists():
        audit = {
            "schema_version": "paper-m3-v2-independent-blind-admission-audit-1.0",
            "audit_version": AUDIT_VERSION,
            "status": "blocked_missing_candidate",
            "created_at": created_at,
            "candidate_path": str(candidate_path),
            "candidate_exists": False,
            "custody_manifest_path": str(custody_manifest_path),
            "custody_manifest_exists": custody_manifest_path.exists(),
            "reference_dataset_path": str(reference_dataset_path),
            "required_candidate_contract": {
                "total_cases": 600,
                "sample_type_counts": EXPECTED_COUNTS,
                "attack_family_count_each": 40,
                "split": "independent_blind",
                "evidence_level": "independent_blind",
                "custody_required": True,
                "custody_sidecar_required": True,
                "custody_sidecar_filename": DEFAULT_CUSTODY_FILENAME,
                "custody_candidate_hash_must_match": True,
                "no_template_overlap_with_reference": True,
                "no_exact_runtime_duplicate_with_reference": True,
                "no_oracle_runtime_fields": sorted(FORBIDDEN_RUNTIME_FIELDS),
            },
            "checks": [
                _check(
                    "candidate_jsonl_present",
                    False,
                    str(candidate_path),
                )
            ],
            "passed_checks": 0,
            "total_checks": 1,
            "result_eligible_for_confirmatory_q2_tables": False,
            "boundary": (
                "Admission audit only. The current deterministic sealed holdout "
                "remains excluded from independent confirmatory claims until a "
                "separately authored candidate JSONL passes this gate."
            ),
        }
        audit = portable_value(audit, root=ROOT)
        _write_outputs(output_dir, audit, audit_stem=audit_stem)
        return audit

    rows = _read_jsonl(candidate_path)
    candidate_sha256 = sha256_file(candidate_path)
    reference_rows = _read_reference(reference_dataset_path)
    custody_manifest: dict[str, Any] = {}
    custody_parse_error = ""
    if custody_manifest_path.exists():
        try:
            custody_manifest = _read_json_object(custody_manifest_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            custody_parse_error = f"{type(exc).__name__}: {exc}"
    ids = [str(row.get("case_id", "")) for row in rows]
    templates = [str(row.get("template_id", "")) for row in rows]
    reference_templates = {str(row.get("template_id", "")) for row in reference_rows}
    reference_runtime_hashes = {_hash_runtime_view(row) for row in reference_rows}
    candidate_runtime_hashes = [_hash_runtime_view(row) for row in rows]
    attack_rows = [row for row in rows if row.get("sample_type") == "attack"]
    family_counts = _counts_by(attack_rows, "attack_family")
    sample_counts = _counts_by(rows, "sample_type")
    split_counts = _counts_by(rows, "split")
    evidence_counts = _counts_by(rows, "evidence_level")
    generator_rows = [
        {
            "generator": row.get("generation", {}).get("generator", "")
            if isinstance(row.get("generation"), Mapping)
            else ""
        }
        for row in rows
    ]
    generator_counts = _counts_by(generator_rows, "generator")
    custody_missing = [
        str(row.get("case_id", ""))
        for row in rows
        if not isinstance(row.get("custody"), Mapping)
        or not row.get("custody", {}).get("independent_source")
        or not row.get("custody", {}).get("sealed_at")
    ]
    row_sealed_at_values = sorted(
        {
            str(row.get("custody", {}).get("sealed_at", ""))
            for row in rows
            if isinstance(row.get("custody"), Mapping)
        }
    )
    independent_author_ids = custody_manifest.get("independent_author_ids", [])
    independent_author_ids_valid = (
        isinstance(independent_author_ids, list)
        and bool(independent_author_ids)
        and all(_is_non_placeholder_text(item) for item in independent_author_ids)
        and len({str(item).strip() for item in independent_author_ids})
        == len(independent_author_ids)
    )
    sidecar_sealed_at = custody_manifest.get("sealed_at", "")
    forbidden_hits = [
        {"case_id": str(row.get("case_id", "")), "fields": sorted(set(row) & FORBIDDEN_RUNTIME_FIELDS)}
        for row in rows
        if set(row) & FORBIDDEN_RUNTIME_FIELDS
    ]
    template_split_map = _template_splits(rows)
    checks = [
        _check("candidate_jsonl_present", True, str(candidate_path)),
        _check(
            "custody_sidecar_present",
            custody_manifest_path.is_file(),
            str(custody_manifest_path),
        ),
        _check(
            "custody_sidecar_parses_as_json_object",
            custody_manifest_path.is_file() and not custody_parse_error,
            custody_parse_error or "parsed",
        ),
        _check(
            "custody_schema_and_status_valid",
            custody_manifest.get("schema_version") == "m3-independent-blind-custody-1.0"
            and custody_manifest.get("status") == "sealed_candidate",
            {
                "schema_version": custody_manifest.get("schema_version"),
                "status": custody_manifest.get("status"),
            },
        ),
        _check(
            "custody_candidate_filename_matches",
            custody_manifest.get("candidate_filename") == candidate_path.name,
            custody_manifest.get("candidate_filename"),
        ),
        _check(
            "custody_candidate_row_count_matches",
            custody_manifest.get("candidate_row_count") == len(rows) == 600,
            {
                "manifest": custody_manifest.get("candidate_row_count"),
                "observed": len(rows),
            },
        ),
        _check(
            "custody_candidate_sha256_matches",
            custody_manifest.get("candidate_sha256") == candidate_sha256,
            {
                "manifest": custody_manifest.get("candidate_sha256"),
                "observed": candidate_sha256,
            },
        ),
        _check(
            "custody_declares_no_developer_access_before_seal",
            custody_manifest.get("developer_access_before_seal") is False,
            custody_manifest.get("developer_access_before_seal"),
        ),
        _check(
            "custody_independent_authors_identified",
            independent_author_ids_valid,
            independent_author_ids,
        ),
        _check(
            "custody_custodian_and_authoring_method_recorded",
            _is_non_placeholder_text(custody_manifest.get("custodian_id"))
            and _is_non_placeholder_text(custody_manifest.get("authoring_method"))
            and _is_non_placeholder_text(custody_manifest.get("authoring_environment")),
            {
                "custodian_id": custody_manifest.get("custodian_id"),
                "authoring_method": custody_manifest.get("authoring_method"),
                "authoring_environment": custody_manifest.get("authoring_environment"),
            },
        ),
        _check(
            "custody_sealed_at_valid_and_matches_every_row",
            _is_iso8601(sidecar_sealed_at)
            and row_sealed_at_values == [str(sidecar_sealed_at)],
            {
                "manifest": sidecar_sealed_at,
                "row_values": row_sealed_at_values,
            },
        ),
        _check("total_600_cases", len(rows) == 600, len(rows)),
        _check("unique_case_ids", len(set(ids)) == len(ids), [item for item, count in Counter(ids).items() if count > 1]),
        _check("sample_type_360_120_120", sample_counts == EXPECTED_COUNTS, sample_counts),
        _check("all_split_independent_blind", split_counts == {"independent_blind": 600}, split_counts),
        _check("all_evidence_level_independent_blind", evidence_counts == {"independent_blind": 600}, evidence_counts),
        _check(
            "nine_attack_families_40_each",
            family_counts == {family: 40 for family in EXPECTED_ATTACK_FAMILIES},
            family_counts,
        ),
        _check(
            "template_ids_unique_within_candidate",
            len(set(templates)) == len(templates),
            [item for item, count in Counter(templates).items() if count > 1],
        ),
        _check(
            "templates_do_not_overlap_reference_dataset",
            not (set(templates) & reference_templates),
            sorted(set(templates) & reference_templates)[:20],
        ),
        _check(
            "no_exact_runtime_duplicate_with_reference",
            not (set(candidate_runtime_hashes) & reference_runtime_hashes),
            len(set(candidate_runtime_hashes) & reference_runtime_hashes),
        ),
        _check(
            "no_exact_runtime_duplicate_inside_candidate",
            len(set(candidate_runtime_hashes)) == len(candidate_runtime_hashes),
            len(candidate_runtime_hashes) - len(set(candidate_runtime_hashes)),
        ),
        _check(
            "no_template_cross_split_inside_candidate",
            all(len(splits) == 1 for splits in template_split_map.values()),
            {key: sorted(value) for key, value in template_split_map.items() if len(value) > 1},
        ),
        _check("custody_record_present_for_every_case", not custody_missing, custody_missing[:20]),
        _check("no_oracle_runtime_fields", not forbidden_hits, forbidden_hits[:20]),
        _check(
            "not_generated_by_local_m3_v2_generator",
            "m3_attacks.m3_v2_generator" not in generator_counts,
            generator_counts,
        ),
    ]
    error_failures = [
        check
        for check in checks
        if check["status"] != "pass" and check.get("severity") == "error"
    ]
    audit = {
        "schema_version": "paper-m3-v2-independent-blind-admission-audit-1.0",
        "audit_version": AUDIT_VERSION,
        "status": "admitted_independent_blind" if not error_failures else "blocked_candidate_failed",
        "created_at": created_at,
        "candidate_path": str(candidate_path),
        "candidate_exists": True,
        "candidate_sha256": candidate_sha256,
        "custody_manifest_path": str(custody_manifest_path),
        "custody_manifest_exists": custody_manifest_path.is_file(),
        "custody_manifest_sha256": sha256_file(custody_manifest_path)
        if custody_manifest_path.is_file()
        else "",
        "reference_dataset_path": str(reference_dataset_path),
        "reference_dataset_exists": reference_dataset_path.exists(),
        "reference_dataset_sha256": sha256_file(reference_dataset_path)
        if reference_dataset_path.exists()
        else "",
        "counts": {
            "total": len(rows),
            "sample_type_counts": sample_counts,
            "split_counts": split_counts,
            "evidence_level_counts": evidence_counts,
            "attack_family_counts": family_counts,
            "generator_counts": generator_counts,
        },
        "checks": checks,
        "checks_sha256": rows_sha256(checks),
        "passed_checks": sum(1 for check in checks if check["status"] == "pass"),
        "total_checks": len(checks),
        "result_eligible_for_confirmatory_q2_tables": not error_failures,
        "error_failures": error_failures,
        "boundary": (
            "A candidate that passes this audit is eligible to be frozen as an "
            "independent blind input. It is still not a result: model runs, human "
            "review sampling, statistics and manifest sealing must happen after "
            "this admission step."
        ),
    }
    audit = portable_value(audit, root=ROOT)
    _write_outputs(output_dir, audit, audit_stem=audit_stem)
    return audit


def _write_outputs(
    output_dir: Path,
    audit: Mapping[str, Any],
    *,
    audit_stem: str,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{audit_stem}.json"
    md_path = output_dir / f"{audit_stem}.md"
    json_path.write_text(
        json.dumps(dict(audit), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_markdown(md_path, audit)


def _write_markdown(path: Path, audit: Mapping[str, Any]) -> None:
    lines = [
        "# M3-v2 independent blind post-preregistration admission audit",
        "",
        f"Generated: {audit['created_at']}",
        "",
        "## Result",
        "",
        f"- Status: `{audit['status']}`",
        f"- Candidate exists: `{audit['candidate_exists']}`",
        f"- Result eligible for confirmatory Q2 tables: `{audit['result_eligible_for_confirmatory_q2_tables']}`",
        f"- Passed checks: {audit['passed_checks']}/{audit['total_checks']}",
        "",
        "## Checks",
        "",
        "| Check | Status | Severity | Detail |",
        "|---|---|---|---|",
    ]
    for check in audit["checks"]:
        detail = json.dumps(check.get("detail"), ensure_ascii=False, sort_keys=True)
        if len(detail) > 220:
            detail = detail[:217] + "..."
        lines.append(
            f"| `{check['name']}` | `{check['status']}` | `{check['severity']}` | "
            f"{detail.replace('|', '\\|')} |"
        )
    lines.extend(["", "## Boundary", "", str(audit["boundary"]), ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument("--custody-manifest", type=Path)
    parser.add_argument("--reference-dataset", type=Path, default=DEFAULT_REFERENCE_DATASET)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--audit-stem",
        default=AUDIT_STEM,
        help=(
            "Output stem. The default is v2 so the preregistration-bound v1 "
            "snapshot is never overwritten."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    audit = build_independent_blind_audit(
        candidate_path=args.candidate,
        custody_manifest_path=args.custody_manifest,
        reference_dataset_path=args.reference_dataset,
        output_dir=args.output_dir,
        audit_stem=args.audit_stem,
    )
    print(json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
