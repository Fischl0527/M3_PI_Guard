from __future__ import annotations

import argparse
import json
from collections import Counter
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


if __name__ == "__main__":
    main()
