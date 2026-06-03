"""CLI for evaluating M3_PI_Guard RunLog JSONL files."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from .metrics import build_summary_rows


CSV_FIELDS = [
    "scope",
    "group",
    "log_file",
    "model",
    "defense_mode",
    "cases",
    "attack_cases",
    "clean_cases",
    "ASR",
    "UTR",
    "DSR",
    "BSR",
    "FPR",
    "AvgRisk",
    "WRS",
]


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
    with out_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    out_json = out_csv.with_suffix(".json")
    payload = {
        "cases_file": Path(args.cases).as_posix(),
        "log_files": [Path(path).as_posix() for path in args.logs],
        "summary_csv": out_csv.as_posix(),
        "rows": rows,
    }
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"wrote {out_csv}")
    print(f"wrote {out_json}")
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


if __name__ == "__main__":
    raise SystemExit(main())
