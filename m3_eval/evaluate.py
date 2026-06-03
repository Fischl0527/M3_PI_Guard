"""CLI for evaluating M3_PI_Guard RunLog JSONL files."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from .metrics import (
    SUMMARY_FIELDS,
    blocked_records,
    build_summary_rows,
    compare_runs,
    load_jsonl,
    summarize_logs,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate M3_PI_Guard RunLog JSONL files.")
    parser.add_argument("--logs", nargs="*", help="RunLog JSONL files")
    parser.add_argument("--baseline", help="Baseline RunLog JSONL path")
    parser.add_argument("--guarded", help="Guarded RunLog JSONL path")
    parser.add_argument("--cases", help="AttackCase JSONL file")
    parser.add_argument("--out", help="Output summary CSV path, or JSON path for legacy mode")
    args = parser.parse_args(argv)

    cases = load_jsonl(_repo_path(args.cases)) if args.cases else []

    if args.logs:
        if not args.out:
            raise SystemExit("--out is required when using --logs")
        logs_by_file = {log_path: load_jsonl(_repo_path(log_path)) for log_path in args.logs}
        rows = build_summary_rows(logs_by_file, cases)
        out_csv = _repo_path(args.out)
        out_csv.parent.mkdir(parents=True, exist_ok=True)
        _write_csv(out_csv, rows, SUMMARY_FIELDS)

        grouped_by_family = [row for row in rows if row.get("scope") == "attack_family"]
        family_csv = out_csv.with_name("day3_grouped_by_family.csv")
        _write_csv(family_csv, grouped_by_family, SUMMARY_FIELDS)

        out_json = out_csv.with_suffix(".json")
        payload = {
            "cases_file": Path(args.cases).as_posix() if args.cases else "",
            "log_files": [Path(path).as_posix() for path in args.logs],
            "summary_csv": out_csv.as_posix(),
            "grouped_by_family_csv": family_csv.as_posix(),
            "rows": rows,
            "grouped_by_family": grouped_by_family,
            "blocked_records": blocked_records(logs_by_file),
        }
        out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {out_csv}")
        print(f"wrote {out_json}")
        print(f"wrote {family_csv}")
        return 0

    if args.baseline and args.guarded:
        result: dict[str, Any] = compare_runs(
            load_jsonl(_repo_path(args.baseline)),
            load_jsonl(_repo_path(args.guarded)),
            cases,
        )
    elif args.baseline:
        result = summarize_logs(load_jsonl(_repo_path(args.baseline)), cases)
    elif args.guarded:
        result = summarize_logs(load_jsonl(_repo_path(args.guarded)), cases)
    else:
        raise SystemExit("Provide --logs or --baseline/--guarded")

    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        out_path = _repo_path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


def _repo_path(value: str | None) -> Path:
    if not value:
        raise ValueError("path value is required")
    path = Path(value)
    if path.is_absolute():
        return path
    return (REPO_ROOT / path).resolve()


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    raise SystemExit(main())
