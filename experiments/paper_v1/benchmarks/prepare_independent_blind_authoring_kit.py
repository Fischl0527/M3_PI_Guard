"""Prepare a content-free handoff kit for independent blind-set authors.

The kit contains 600 stratified assignment slots, schemas and custody
instructions, but deliberately contains no candidate prompts, attacks, expected
effects or model outputs.  Project developers must not fill the candidate from
this repository because doing so would invalidate independent authorship.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .audit_m3_v2_independent_blind import EXPECTED_ATTACK_FAMILIES
from .common import rows_sha256, sha256_file


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = (
    ROOT / "protocols" / "paper_upgrade_v1" / "independent_blind_authoring_kit_v1"
)
KIT_VERSION = "m3-paper-v1-independent-blind-authoring-kit-1.0"
LANGUAGES = ("zh", "en", "zh_en", "pinyin", "zh_hant", "cross_lingual")
AUTHORIZATION_PROFILES = (
    "auto_compiled_exact",
    "trusted_context_exact",
    "ambiguous_recipient",
    "partial_resource_scope",
    "dynamic_parameter",
    "incorrect_or_conflicting_scope",
)


def build_slots() -> list[dict[str, Any]]:
    slots: list[dict[str, Any]] = []
    ordinal = 0
    for family_index, family in enumerate(sorted(EXPECTED_ATTACK_FAMILIES)):
        for within_family in range(40):
            ordinal += 1
            slots.append(
                {
                    "slot_id": f"IB-A-{ordinal:03d}",
                    "sample_type": "attack",
                    "attack_family": family,
                    "language": LANGUAGES[(within_family + family_index) % len(LANGUAGES)],
                    "authorization_profile": AUTHORIZATION_PROFILES[
                        (within_family * 2 + family_index) % len(AUTHORIZATION_PROFILES)
                    ],
                    "scenario_type": (
                        "legal_tool_under_attack"
                        if within_family % 2
                        else "no_tool_under_attack"
                    ),
                    "author_group": 1 + (ordinal - 1) % 2,
                    "template_id_prefix": f"M3V2-IB-T-A-{ordinal:03d}",
                }
            )
    for sample_type, prefix, scenario in (
        ("benign_no_tool", "BN", "normal_no_tool"),
        ("benign_legal_tool", "BT", "legal_tool"),
    ):
        for index in range(120):
            ordinal += 1
            slots.append(
                {
                    "slot_id": f"IB-{prefix}-{index + 1:03d}",
                    "sample_type": sample_type,
                    "attack_family": "benign_clean",
                    "language": LANGUAGES[index % len(LANGUAGES)],
                    "authorization_profile": AUTHORIZATION_PROFILES[
                        (index + (0 if prefix == "BN" else 3))
                        % len(AUTHORIZATION_PROFILES)
                    ],
                    "scenario_type": scenario,
                    "author_group": 1 + index % 2,
                    "template_id_prefix": f"M3V2-IB-T-{prefix}-{index + 1:03d}",
                }
            )
    if len(slots) != 600:
        raise AssertionError(f"independent blind slot count drifted: {len(slots)}")
    return slots


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_slots_csv(path: Path, slots: list[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(slots[0]))
        writer.writeheader()
        writer.writerows(slots)


def _write_slots_jsonl(path: Path, slots: list[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for slot in slots:
            handle.write(json.dumps(dict(slot), ensure_ascii=False, sort_keys=True) + "\n")


def _case_template() -> dict[str, Any]:
    return {
        "schema_version": "paper-case-1.0",
        "dataset_version": "m3-v2-independent-blind-1.0",
        "case_id": "M3V2-IB-<unique-id>",
        "template_id": "<copy the unique template_id_prefix for this slot>",
        "split": "independent_blind",
        "evidence_level": "independent_blind",
        "sample_type": "<attack|benign_no_tool|benign_legal_tool>",
        "attack_family": "<assigned family; benign_clean for benign slots>",
        "language": "<assigned language>",
        "authorization_profile": "<assigned authorization profile>",
        "scenario_type": "<assigned scenario type>",
        "mutation_id": "<independent-author mutation id>",
        "trusted_user_request": "<author content>",
        "trusted_app_context": {"request_id": "<independent id>"},
        "untrusted_content": "<author content>",
        "untrusted_memory": [],
        "attack_dimensions": {},
        "offline_evaluation": {
            "offline_only": True,
            "expected_outcome": "<evaluator-only label>",
            "expected_allowed_effects": [],
            "expected_unsafe_effects": [],
            "requires_tool_for_success": False,
        },
        "generation": {
            "generator": "<independent author or independent generator name>",
            "generator_kind": "<human|independent_program|mixed>",
            "seed": "<record if applicable>",
        },
        "custody": {
            "independent_source": "<team/member pseudonymous id>",
            "sealed_at": "<ISO-8601 after content freeze>",
        },
    }


def _custody_template() -> dict[str, Any]:
    return {
        "schema_version": "m3-independent-blind-custody-1.0",
        "status": "sealed_candidate",
        "candidate_filename": "m3_v2_independent_blind_candidate.jsonl",
        "candidate_sha256": "<SHA-256 after final write>",
        "candidate_row_count": 600,
        "independent_author_ids": ["<author-1>", "<author-2-if-used>"],
        "authoring_method": "<human|independent_program|mixed and version>",
        "authoring_environment": "<separate directory/machine and dependency lock>",
        "developer_access_before_seal": False,
        "reference_material_allowed": [
            "public threat taxonomy",
            "tool schemas without M3 expected answers",
            "this content-free assignment kit",
        ],
        "reference_material_forbidden": [
            "M3-v2 development/validation/holdout case content",
            "M3 experiment outputs or failure cases",
            "Guard rules, detector scores or thresholds",
        ],
        "sealed_at": "<ISO-8601>",
        "custodian_id": "<person who controls release>",
        "release_condition": "after code, thresholds, hypotheses and exclusions freeze",
        "notes": "",
    }


def _validator_script() -> str:
    return r'''"""Self-contained pre-release validator for M3-v2 independent blind candidates.

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
'''


def _readme() -> str:
    return """# Independent blind authoring kit v1

## What this kit is

This folder is a content-free assignment and custody package for an independent 600-case confirmatory blind set. It is not a dataset and cannot raise the Q2 evidence score by itself. Project developers must not fill the prompts or expected effects.

## Who should author the candidate

Use at least one person or independently operated generator that has not read M3-v2 case content, experiment outputs, failure logs, Guard rules, detector thresholds or per-case expected actions. Two authors may split the rows using `author_group`; independence is about separation from model/defense development, not about manually typing every row.

An independent program is acceptable and is more realistic than 600 manually written rows, provided its source, seed, dependencies and generation prompts are frozen outside this repository before the M3 developers receive the candidate. Human authors should inspect a stratified sample before sealing.

## Authoring procedure

1. Copy this kit to a separate working directory controlled by the independent author/custodian. Do not give that environment access to `m3_attacks/cases/paper_v1`, `outputs`, Harness progress/failure files or Guard source.
2. Use `authoring_slots.csv` or `authoring_slots.jsonl` as the required distribution. Every slot becomes exactly one unique semantic template and one case.
3. Create 360 attack rows (40 for each of 9 families), 120 benign no-tool rows and 120 benign legal-tool rows. Keep the assigned language, authorization profile and scenario type unless a documented impossibility is found before sealing.
4. Fill fields using `case_template.json`. The runtime fields are the trusted request/context plus untrusted content/memory. Evaluation labels stay only inside `offline_evaluation`.
5. Do not add `authorized_actions`, top-level `requires_tool`, `expected_safe_behavior`, `unsafe_target_actions`, `target_actions`, `expected_answer`, `detector_answer` or any exact detector/Guard answer to the runtime object.
6. Keep every `case_id` and `template_id` unique. Do not copy or paraphrase known M3-v2 cases. Use mock-only recipients, endpoints and sandbox paths; never reference real credentials, real email addresses or destructive tools.
7. Validate the 600 JSONL rows in the independent environment. Record all validation commands and any excluded/replaced slot before seal.
8. Write the final candidate exactly once, compute SHA-256, then complete `custody_manifest_template.json` as `m3_v2_independent_blind_custody.json`. Set the same `sealed_at` timestamp in every row's custody block.
9. Run the package-local self-check before release:

   ```powershell
   python validate_candidate_before_release.py --candidate m3_v2_independent_blind_candidate.jsonl --custody-manifest m3_v2_independent_blind_custody.json --output pre_release_self_check.json
   ```

   A PASS here only checks content-free structure and custody consistency. It does not compare against M3 development data.
10. The custodian withholds the candidate from M3 developers until code, thresholds, hypotheses and exclusions are frozen. Release the candidate, custody manifest and pre-release self-check together.
11. In the M3 repository, place the released candidate at `m3_attacks/cases/paper_v1/m3_v2_independent_blind_candidate.jsonl`, run `audit_m3_v2_independent_blind.py`, and preserve any failed audit without editing results. A passing admission audit only freezes input; it is not a model result.

## Review burden

Do not ask two people to inspect all future model-run rows. Before sealing, independently inspect a stratified sample of the 600 authored cases (recommended 120–180 total, oversampling complex cross-tool/memory/obfuscation rows). After experiments, use the already established two-reviewer stratified sampling workflow for outcome/error taxonomy. Conflicts are adjudicated; targeted diagnostic rows are not pooled into population estimates.

## Release boundary

The independent candidate remains invalid for confirmatory claims if developers saw it before code/threshold freeze, if it was generated from existing M3 cases/results, if custody is incomplete, or if admission checks are weakened after inspecting model performance.
"""


def prepare_kit(output_dir: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    slots = build_slots()
    csv_path = output_dir / "authoring_slots.csv"
    jsonl_path = output_dir / "authoring_slots.jsonl"
    case_template_path = output_dir / "case_template.json"
    custody_template_path = output_dir / "custody_manifest_template.json"
    validator_path = output_dir / "validate_candidate_before_release.py"
    readme_path = output_dir / "README.md"
    _write_slots_csv(csv_path, slots)
    _write_slots_jsonl(jsonl_path, slots)
    _write_json(case_template_path, _case_template())
    _write_json(custody_template_path, _custody_template())
    validator_path.write_text(_validator_script(), encoding="utf-8")
    readme_path.write_text(_readme(), encoding="utf-8")
    sample_counts = dict(sorted(Counter(row["sample_type"] for row in slots).items()))
    family_counts = dict(
        sorted(
            Counter(
                row["attack_family"] for row in slots if row["sample_type"] == "attack"
            ).items()
        )
    )
    artifacts = {}
    for path in (
        csv_path,
        jsonl_path,
        case_template_path,
        custody_template_path,
        validator_path,
        readme_path,
    ):
        artifacts[path.name] = {
            "path": path.relative_to(output_dir).as_posix(),
            "sha256": sha256_file(path),
        }
    manifest = {
        "schema_version": "paper-independent-blind-authoring-kit-manifest-1.0",
        "kit_version": KIT_VERSION,
        "status": "completed_authoring_kit_only",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "result_eligible_for_confirmatory_q2_tables": False,
        "candidate_cases_created": 0,
        "assignment_slot_count": len(slots),
        "assignment_slots_sha256": rows_sha256(slots),
        "sample_type_counts": sample_counts,
        "attack_family_counts": family_counts,
        "artifacts": artifacts,
        "boundary": (
            "Content-free authoring/custody handoff only. Independent authors must create "
            "and seal the actual candidate without access to M3 cases, results or Guard internals."
        ),
    }
    _write_json(output_dir / "manifest.json", manifest)
    return manifest


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    return parser


def main() -> int:
    args = _parser().parse_args()
    manifest = prepare_kit(args.output_dir)
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
