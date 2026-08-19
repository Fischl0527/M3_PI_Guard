"""Self-contained pre-release validator for M3-v2 independent blind candidates.

Run this in the independent author/custodian environment before releasing the
candidate to M3 developers.  It performs only content-free contract checks.  It
does not compare against M3 development data; the repository-side admission audit
will still perform reference-overlap checks after release.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping


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


def _read_json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_iso8601(value: Any) -> bool:
    try:
        datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return False
    return True


def _non_placeholder(value: Any) -> bool:
    text = str(value or "").strip()
    return bool(text) and not (text.startswith("<") and text.endswith(">"))


def _counts_by(rows: Iterable[Mapping[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(key, "")) for row in rows).items()))


def _check(name: str, passed: bool, detail: Any) -> dict[str, Any]:
    return {"name": name, "status": "pass" if passed else "fail", "detail": detail}


def validate(candidate_path: Path, custody_path: Path) -> dict[str, Any]:
    rows = _read_jsonl(candidate_path)
    custody = _read_json_object(custody_path)
    candidate_sha = _sha256(candidate_path)
    ids = [str(row.get("case_id", "")) for row in rows]
    templates = [str(row.get("template_id", "")) for row in rows]
    attack_rows = [row for row in rows if row.get("sample_type") == "attack"]
    row_sealed_at_values = sorted(
        {
            str(row.get("custody", {}).get("sealed_at", ""))
            for row in rows
            if isinstance(row.get("custody"), Mapping)
        }
    )
    template_splits: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        template_splits[str(row.get("template_id", ""))].add(str(row.get("split", "")))
    forbidden_hits = [
        {"case_id": str(row.get("case_id", "")), "fields": sorted(set(row) & FORBIDDEN_RUNTIME_FIELDS)}
        for row in rows
        if set(row) & FORBIDDEN_RUNTIME_FIELDS
    ]
    custody_missing = [
        str(row.get("case_id", ""))
        for row in rows
        if not isinstance(row.get("custody"), Mapping)
        or not row.get("custody", {}).get("independent_source")
        or not row.get("custody", {}).get("sealed_at")
    ]
    author_ids = custody.get("independent_author_ids", [])
    author_ids_valid = (
        isinstance(author_ids, list)
        and bool(author_ids)
        and all(_non_placeholder(item) for item in author_ids)
        and len({str(item).strip() for item in author_ids}) == len(author_ids)
    )
    checks = [
        _check("total_600_cases", len(rows) == 600, len(rows)),
        _check("unique_case_ids", len(set(ids)) == len(ids), [item for item, count in Counter(ids).items() if count > 1]),
        _check("unique_template_ids", len(set(templates)) == len(templates), [item for item, count in Counter(templates).items() if count > 1]),
        _check("sample_type_360_120_120", _counts_by(rows, "sample_type") == EXPECTED_COUNTS, _counts_by(rows, "sample_type")),
        _check(
            "nine_attack_families_40_each",
            _counts_by(attack_rows, "attack_family") == {family: 40 for family in EXPECTED_ATTACK_FAMILIES},
            _counts_by(attack_rows, "attack_family"),
        ),
        _check("all_split_independent_blind", _counts_by(rows, "split") == {"independent_blind": 600}, _counts_by(rows, "split")),
        _check("all_evidence_level_independent_blind", _counts_by(rows, "evidence_level") == {"independent_blind": 600}, _counts_by(rows, "evidence_level")),
        _check("no_template_cross_split", all(len(value) == 1 for value in template_splits.values()), {key: sorted(value) for key, value in template_splits.items() if len(value) > 1}),
        _check("custody_record_present_for_every_case", not custody_missing, custody_missing[:20]),
        _check("no_oracle_runtime_fields", not forbidden_hits, forbidden_hits[:20]),
        _check("custody_schema_and_status_valid", custody.get("schema_version") == "m3-independent-blind-custody-1.0" and custody.get("status") == "sealed_candidate", {"schema_version": custody.get("schema_version"), "status": custody.get("status")}),
        _check("custody_candidate_filename_matches", custody.get("candidate_filename") == candidate_path.name, custody.get("candidate_filename")),
        _check("custody_candidate_row_count_matches", custody.get("candidate_row_count") == len(rows) == 600, {"manifest": custody.get("candidate_row_count"), "observed": len(rows)}),
        _check("custody_candidate_sha256_matches", custody.get("candidate_sha256") == candidate_sha, {"manifest": custody.get("candidate_sha256"), "observed": candidate_sha}),
        _check("custody_developer_access_before_seal_false", custody.get("developer_access_before_seal") is False, custody.get("developer_access_before_seal")),
        _check("custody_independent_authors_identified", author_ids_valid, author_ids),
        _check("custody_custodian_and_authoring_method_recorded", _non_placeholder(custody.get("custodian_id")) and _non_placeholder(custody.get("authoring_method")) and _non_placeholder(custody.get("authoring_environment")), {"custodian_id": custody.get("custodian_id"), "authoring_method": custody.get("authoring_method"), "authoring_environment": custody.get("authoring_environment")}),
        _check("custody_sealed_at_valid_and_matches_every_row", _is_iso8601(custody.get("sealed_at")) and row_sealed_at_values == [str(custody.get("sealed_at"))], {"manifest": custody.get("sealed_at"), "row_values": row_sealed_at_values}),
    ]
    failures = [row for row in checks if row["status"] != "pass"]
    return {
        "schema_version": "m3-independent-blind-pre-release-self-check-1.0",
        "status": "pass" if not failures else "fail",
        "candidate_path": str(candidate_path),
        "custody_manifest_path": str(custody_path),
        "checks": checks,
        "passed_checks": sum(1 for row in checks if row["status"] == "pass"),
        "total_checks": len(checks),
        "failures": failures,
        "boundary": "Content-free pre-release validation only. Repository-side reference-overlap and formal-result admission are still required.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, default=Path("m3_v2_independent_blind_candidate.jsonl"))
    parser.add_argument("--custody-manifest", type=Path, default=Path("m3_v2_independent_blind_custody.json"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = validate(args.candidate, args.custody_manifest)
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
