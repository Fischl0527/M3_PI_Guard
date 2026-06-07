"""Build final DAY5 summary files from individual experiment summaries."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


FIELDS = [
    "dataset",
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
    parser = argparse.ArgumentParser(description="Aggregate DAY5 final summaries.")
    parser.add_argument("--stub", required=True, help="Stub matrix summary CSV")
    parser.add_argument("--qwen", required=True, help="Qwen representative summary CSV")
    parser.add_argument("--demo", required=True, help="Demo summary CSV")
    parser.add_argument("--out", required=True, help="Final output CSV")
    args = parser.parse_args(argv)

    sources = [
        ("stub_all_four_modes", Path(args.stub)),
        ("qwen25_representative", Path(args.qwen)),
        ("demo_cases", Path(args.demo)),
    ]

    rows: list[dict[str, Any]] = []
    for dataset, path in sources:
        for row in _read_csv(path):
            rows.append({"dataset": dataset, **row})

    out_csv = Path(args.out)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    out_json = out_csv.with_suffix(".json")
    payload = {
        "summary_csv": out_csv.as_posix(),
        "sources": [{"dataset": name, "summary": path.as_posix()} for name, path in sources],
        "overall": [row for row in rows if row.get("scope") == "overall"],
        "rows": rows,
        "notes": _build_notes(rows),
    }
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {out_csv}")
    print(f"wrote {out_json}")
    return 0


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _build_notes(rows: list[dict[str, Any]]) -> list[str]:
    notes: list[str] = []
    qwen_overall = [
        row
        for row in rows
        if row.get("dataset") == "qwen25_representative" and row.get("scope") == "overall"
    ]
    if any(str(row.get("clean_cases")) == "0" for row in qwen_overall):
        notes.append("Qwen representative fixture currently reports clean_cases=0; FPR is not informative for that subset.")
    return notes


if __name__ == "__main__":
    raise SystemExit(main())
