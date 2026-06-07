from __future__ import annotations

import argparse
import re
import json
from collections import Counter
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


REQUIRED_FIELDS = {
    "case_id",
    "attack_family",
    "carrier",
    "language",
    "user_task",
    "document_content",
    "injected_content",
    "expected_safe_behavior",
    "unsafe_target_actions",
    "risk_tags",
    "severity",
    "notes",
}

ALLOWED_UNSAFE_ACTIONS = {
    "read_file:sandbox/secrets/api_key.txt",
    "write_file:sandbox/public/notes.txt",
    "send_email:redteam@example.test",
    "call_api:/mock/external/submit",
    "run_code:mock_only",
}

ALLOWED_ATTACK_FAMILIES = {
    "direct_jailbreak",
    "rag_indirect",
    "multilingual_t2l",
    "json_rpc",
    "tool_output_injection",
    "benign_clean",
}

EXPECTED_DETECTORS_BY_FAMILY = {
    "direct_jailbreak": ["instruction_like_text", "tool_lure"],
    "rag_indirect": [
        "instruction_like_text",
        "tool_lure",
        "untrusted_source_instruction",
        "intent_action_mismatch",
    ],
    "multilingual_t2l": [
        "multilingual_obfuscation",
        "instruction_like_text",
        "tool_lure",
    ],
    "json_rpc": ["structured_injection", "tool_lure", "intent_action_mismatch"],
    "tool_output_injection": [
        "tool_output_injection",
        "instruction_like_text",
        "tool_lure",
    ],
    "benign_clean": [],
}

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
REAL_ATTACK_COMMAND_RE = re.compile(
    r"\b(rm\s+-rf|curl\s+https?://|wget\s+https?://|powershell\s+-enc|"
    r"nc\s+-|nmap\b|sqlmap\b|metasploit\b|msfconsole\b)\b",
    re.IGNORECASE,
)


def iter_case_files(cases_dir: Path, out_path: Path) -> list[Path]:
    files: list[Path] = []
    resolved_out = out_path.resolve()
    for path in sorted(cases_dir.glob("*.jsonl")):
        if path.resolve() == resolved_out:
            continue
        files.append(path)
    return files


def load_cases(paths: list[Path]) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    seen_ids: dict[str, Path] = {}
    errors: list[str] = []

    for path in paths:
        with path.open("r", encoding="utf-8") as handle:
            for line_no, raw_line in enumerate(handle, start=1):
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    case = json.loads(line)
                except json.JSONDecodeError as exc:
                    errors.append(f"{path}:{line_no}: invalid JSON: {exc}")
                    continue

                missing = REQUIRED_FIELDS - set(case)
                if missing:
                    errors.append(
                        f"{path}:{line_no}: missing fields: {', '.join(sorted(missing))}"
                    )

                case_id = case.get("case_id")
                if not isinstance(case_id, str) or not case_id:
                    errors.append(f"{path}:{line_no}: case_id must be a non-empty string")
                elif case_id in seen_ids:
                    errors.append(
                        f"{path}:{line_no}: duplicate case_id {case_id!r}; "
                        f"first seen in {seen_ids[case_id]}"
                    )
                else:
                    seen_ids[case_id] = path

                actions = case.get("unsafe_target_actions")
                if not isinstance(actions, list) or not all(
                    isinstance(action, str) for action in actions
                ):
                    errors.append(
                        f"{path}:{line_no}: unsafe_target_actions must be a list of strings"
                    )
                else:
                    disallowed = sorted(set(actions) - ALLOWED_UNSAFE_ACTIONS)
                    if disallowed:
                        errors.append(
                            f"{path}:{line_no}: disallowed unsafe_target_actions: "
                            f"{', '.join(disallowed)}"
                        )

                tags = case.get("risk_tags")
                if not isinstance(tags, list) or not all(
                    isinstance(tag, str) for tag in tags
                ):
                    errors.append(f"{path}:{line_no}: risk_tags must be a list of strings")

                cases.append(case)

    if errors:
        raise SystemExit("Validation failed:\n" + "\n".join(errors))

    return cases


def build_stats(cases: list[dict[str, Any]]) -> dict[str, Any]:
    family_counts = Counter(case["attack_family"] for case in cases)
    carrier_counts = Counter(case["carrier"] for case in cases)
    language_counts = Counter(case["language"] for case in cases)
    severity_counts = Counter(case["severity"] for case in cases)
    demo_priority_counts = Counter(
        str(case.get("demo_priority", "unset")) for case in cases
    )
    action_counts = Counter(
        action for case in cases for action in case["unsafe_target_actions"]
    )

    return {
        "total_cases": len(cases),
        "attack_family_count": dict(sorted(family_counts.items())),
        "carrier_count": dict(sorted(carrier_counts.items())),
        "language_count": dict(sorted(language_counts.items())),
        "severity_count": dict(sorted(severity_counts.items())),
        "demo_priority_count": dict(sorted(demo_priority_counts.items())),
        "unsafe_target_actions_count": dict(sorted(action_counts.items())),
        "benign_count": family_counts.get("benign_clean", 0),
        "missing_required_fields": 0,
        "duplicate_case_id": 0,
    }


def normalize_for_similarity(case: dict[str, Any]) -> str:
    text = " ".join(
        str(case.get(field, ""))
        for field in ("user_task", "document_content", "injected_content")
    )
    return re.sub(r"\s+", " ", text.lower()).strip()


def audit_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    issues: dict[str, list[Any]] = {
        "duplicate_case_id": [],
        "invalid_attack_family": [],
        "invalid_language": [],
        "disallowed_unsafe_target_actions": [],
        "empty_document_content": [],
        "empty_injected_content": [],
        "benign_with_unsafe_actions": [],
        "real_email_or_url": [],
        "real_attack_command": [],
        "overly_similar_pairs": [],
        "invalid_demo_priority": [],
        "missing_expected_detectors": [],
        "unexpected_expected_detectors": [],
    }

    seen_ids: dict[str, int] = {}
    for idx, case in enumerate(cases):
        case_id = case["case_id"]
        family = case["attack_family"]
        language = case["language"]

        if case_id in seen_ids:
            issues["duplicate_case_id"].append(
                {"case_id": case_id, "first_index": seen_ids[case_id], "index": idx}
            )
        seen_ids[case_id] = idx

        if family not in ALLOWED_ATTACK_FAMILIES:
            issues["invalid_attack_family"].append(
                {"case_id": case_id, "attack_family": family}
            )

        if not isinstance(language, str) or not language.strip():
            issues["invalid_language"].append({"case_id": case_id, "language": language})

        actions = case["unsafe_target_actions"]
        disallowed = sorted(set(actions) - ALLOWED_UNSAFE_ACTIONS)
        if disallowed:
            issues["disallowed_unsafe_target_actions"].append(
                {"case_id": case_id, "actions": disallowed}
            )

        if not str(case.get("document_content", "")).strip():
            issues["empty_document_content"].append(case_id)

        if family != "benign_clean" and not str(case.get("injected_content", "")).strip():
            issues["empty_injected_content"].append(case_id)

        if family == "benign_clean" and actions:
            issues["benign_with_unsafe_actions"].append(
                {"case_id": case_id, "actions": actions}
            )

        all_text = " ".join(
            str(case.get(field, ""))
            for field in (
                "user_task",
                "document_content",
                "injected_content",
                "expected_safe_behavior",
                "notes",
            )
        )
        emails = [email for email in EMAIL_RE.findall(all_text) if not email.endswith(".test")]
        urls = [
            url
            for url in URL_RE.findall(all_text)
            if "example." not in url and "/mock/" not in url
        ]
        if emails or urls:
            issues["real_email_or_url"].append(
                {"case_id": case_id, "emails": sorted(set(emails)), "urls": urls}
            )

        commands = REAL_ATTACK_COMMAND_RE.findall(all_text)
        if commands:
            issues["real_attack_command"].append(
                {"case_id": case_id, "matches": sorted(set(commands))}
            )

        priority = case.get("demo_priority")
        if priority is not None and priority not in {1, 2, 3}:
            issues["invalid_demo_priority"].append(
                {"case_id": case_id, "demo_priority": priority}
            )

        expected = case.get("expected_detectors")
        expected_by_family = EXPECTED_DETECTORS_BY_FAMILY.get(family)
        if expected_by_family is not None:
            if expected is None:
                issues["missing_expected_detectors"].append(case_id)
            elif expected != expected_by_family:
                issues["unexpected_expected_detectors"].append(
                    {
                        "case_id": case_id,
                        "actual": expected,
                        "expected": expected_by_family,
                    }
                )

    normalized = [(case["case_id"], normalize_for_similarity(case)) for case in cases]
    for left_idx, (left_id, left_text) in enumerate(normalized):
        if not left_text:
            continue
        for right_id, right_text in normalized[left_idx + 1 :]:
            if not right_text:
                continue
            similarity = SequenceMatcher(None, left_text, right_text).ratio()
            if similarity >= 0.96:
                issues["overly_similar_pairs"].append(
                    {
                        "case_id_a": left_id,
                        "case_id_b": right_id,
                        "similarity": round(similarity, 4),
                    }
                )

    issue_counts = {key: len(value) for key, value in issues.items()}
    hard_fail_issue_keys = [
        "duplicate_case_id",
        "invalid_attack_family",
        "disallowed_unsafe_target_actions",
        "empty_document_content",
        "empty_injected_content",
        "benign_with_unsafe_actions",
        "real_email_or_url",
        "real_attack_command",
        "invalid_demo_priority",
        "missing_expected_detectors",
        "unexpected_expected_detectors",
    ]
    hard_fail_count = sum(issue_counts[key] for key in hard_fail_issue_keys)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_cases": len(cases),
        "checks": {
            "case_id_unique": issue_counts["duplicate_case_id"] == 0,
            "attack_family_valid": issue_counts["invalid_attack_family"] == 0,
            "language_non_empty": issue_counts["invalid_language"] == 0,
            "unsafe_actions_mock_only": issue_counts["disallowed_unsafe_target_actions"]
            == 0,
            "document_content_non_empty": issue_counts["empty_document_content"] == 0,
            "attack_injected_content_non_empty": issue_counts["empty_injected_content"]
            == 0,
            "benign_clean_has_no_unsafe_actions": issue_counts[
                "benign_with_unsafe_actions"
            ]
            == 0,
            "no_real_email_or_url": issue_counts["real_email_or_url"] == 0,
            "no_real_attack_command": issue_counts["real_attack_command"] == 0,
            "demo_priority_valid": issue_counts["invalid_demo_priority"] == 0,
            "expected_detectors_present": issue_counts["missing_expected_detectors"]
            == 0,
            "expected_detectors_match_family": issue_counts[
                "unexpected_expected_detectors"
            ]
            == 0,
        },
        "issue_counts": issue_counts,
        "issues": issues,
        "hard_fail_count": hard_fail_count,
        "status": "pass" if hard_fail_count == 0 else "review_required",
        "repaired_or_removed_case_ids": [],
    }


def write_cases(cases: list[dict[str, Any]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="\n") as handle:
        for case in cases:
            handle.write(json.dumps(case, ensure_ascii=False, sort_keys=True))
            handle.write("\n")


def write_stats(stats: dict[str, Any], stats_path: Path) -> None:
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    with stats_path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(stats, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def write_audit(audit: dict[str, Any], audit_path: Path) -> None:
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    with audit_path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(audit, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def print_stats(stats: dict[str, Any]) -> None:
    print(f"total_cases: {stats['total_cases']}")
    print("attack_family_count:")
    for key, value in stats["attack_family_count"].items():
        print(f"  {key}: {value}")
    print("carrier_count:")
    for key, value in stats["carrier_count"].items():
        print(f"  {key}: {value}")
    print("language_count:")
    for key, value in stats["language_count"].items():
        print(f"  {key}: {value}")
    print("severity_count:")
    for key, value in stats["severity_count"].items():
        print(f"  {key}: {value}")
    print("demo_priority_count:")
    for key, value in stats["demo_priority_count"].items():
        print(f"  {key}: {value}")
    print("unsafe_target_actions_count:")
    for key, value in stats["unsafe_target_actions_count"].items():
        print(f"  {key}: {value}")
    print(f"benign_count: {stats['benign_count']}")
    print(f"duplicate_case_id: {stats['duplicate_case_id']}")
    print(f"missing_required_fields: {stats['missing_required_fields']}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate and merge M3_PI_Guard local sandbox attack cases."
    )
    parser.add_argument(
        "--out",
        default="m3_attacks/cases/all_cases.jsonl",
        help="Output JSONL path. Defaults to m3_attacks/cases/all_cases.jsonl.",
    )
    parser.add_argument(
        "--stats",
        help="Optional JSON statistics output path, for example outputs/metrics/day3_case_stats.json.",
    )
    parser.add_argument(
        "--audit",
        help="Optional JSON quality audit output path, for example outputs/metrics/day4_case_audit.json.",
    )
    args = parser.parse_args()

    package_dir = Path(__file__).resolve().parent
    cases_dir = package_dir / "cases"
    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = Path.cwd() / out_path

    paths = iter_case_files(cases_dir, out_path)
    if not paths:
        raise SystemExit(f"No JSONL case files found in {cases_dir}")

    cases = load_cases(paths)
    write_cases(cases, out_path)
    stats = build_stats(cases)
    print_stats(stats)
    print(f"Wrote: {out_path}")
    if args.stats:
        stats_path = Path(args.stats)
        if not stats_path.is_absolute():
            stats_path = Path.cwd() / stats_path
        write_stats(stats, stats_path)
        print(f"Wrote stats: {stats_path}")
    if args.audit:
        audit_path = Path(args.audit)
        if not audit_path.is_absolute():
            audit_path = Path.cwd() / audit_path
        audit = audit_cases(cases)
        write_audit(audit, audit_path)
        print(f"audit_status: {audit['status']}")
        print(f"audit_hard_fail_count: {audit['hard_fail_count']}")
        print(f"Wrote audit: {audit_path}")


if __name__ == "__main__":
    main()
