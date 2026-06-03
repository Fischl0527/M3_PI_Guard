"""CLI for evaluating M3_PI_Guard RunLog JSONL files."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from .metrics import SUMMARY_FIELDS, blocked_records, build_summary_rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate M3_PI_Guard RunLog JSONL files.")
    parser.add_argument("--logs", nargs="+", required=True, help="RunLog JSONL files")
    parser.add_argument("--cases", required=True, help="AttackCase JSONL file")
    parser.add_argument("--out", required=True, help="Output summary CSV path")
    args = parser.parse_args(argv)

    cases = _read_jsonl(Path(args.cases))
    logs_by_file = {log_path: _read_jsonl(Path(log_path)) for log_path in args.logs}
    rows = build_summary_rows(logs_by_file, cases)

    out_csv = Path(args.out)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    _write_csv(out_csv, rows, SUMMARY_FIELDS)

    grouped_by_family = [row for row in rows if row.get("scope") == "attack_family"]
    family_csv = out_csv.with_name("day3_grouped_by_family.csv")
    _write_csv(family_csv, grouped_by_family, SUMMARY_FIELDS)

    out_json = out_csv.with_suffix(".json")
    payload = {
        "cases_file": Path(args.cases).as_posix(),
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


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSONL line") from exc
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_no}: JSONL record must be an object")
            records.append(value)
    return records


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    raise SystemExit(main())
