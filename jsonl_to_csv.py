"""One-click converter from M3 RunLog JSONL files to CSV.

Usage for local checking:
1. Edit the constants below if you want to change input/output paths.
2. Run this file directly in VSCode/PyCharm, or run:
   python convert_jsonl_to_csv.py

The script keeps JSONL as the canonical machine-readable format and creates
spreadsheet-friendly CSV files for manual review.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

from m3_core.run_batch import read_jsonl, write_runlog_csv


REPO_ROOT = Path(__file__).resolve().parent

# 一键转换默认配置区：
# - JSONL_FILES 为空时，自动转换 INPUT_DIR 下所有 *.jsonl。
# - 如果只想转换指定文件，就把相对路径写进 JSONL_FILES。
# - OUTPUT_DIR 默认仍在 outputs/runs，生成同名 .csv，便于和原 JSONL 对照。
INPUT_DIR = "outputs/runs"
OUTPUT_DIR = "outputs/runs"
JSONL_FILES: List[str] = []
OVERWRITE_EXISTING = True


def main() -> None:
    """Convert configured JSONL files and print a short summary."""

    input_paths = list(_iter_input_paths())
    if not input_paths:
        raise SystemExit(f"No JSONL files found under {_repo_path(INPUT_DIR)}")

    converted_count = 0
    for jsonl_path in input_paths:
        csv_path = _csv_path_for(jsonl_path)
        if csv_path.exists() and not OVERWRITE_EXISTING:
            print(f"SKIP: {csv_path} already exists")
            continue

        # 先完整读入内存，方便统计行数；当前 RunLog 规模很小，展示和验收足够稳。
        rows = list(read_jsonl(jsonl_path))
        write_runlog_csv(csv_path, rows)
        converted_count += 1
        print(f"OK: {jsonl_path} -> {csv_path} ({len(rows)} rows)")

    print(f"DONE: converted {converted_count} JSONL file(s) to CSV.")


def _iter_input_paths() -> Iterable[Path]:
    """Yield JSONL paths from explicit config or by scanning INPUT_DIR."""

    if JSONL_FILES:
        for value in JSONL_FILES:
            path = _repo_path(value)
            if not path.exists():
                raise FileNotFoundError(f"Configured JSONL file does not exist: {path}")
            yield path
        return

    input_dir = _repo_path(INPUT_DIR)
    yield from sorted(input_dir.glob("*.jsonl"))


def _csv_path_for(jsonl_path: Path) -> Path:
    """Build the output CSV path while preserving the JSONL stem."""

    output_dir = _repo_path(OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir / f"{jsonl_path.stem}.csv"


def _repo_path(value: str) -> Path:
    """Resolve relative paths from the repository root for IDE-friendly runs."""

    path = Path(value)
    if path.is_absolute():
        return path
    return (REPO_ROOT / path).resolve()


if __name__ == "__main__":
    main()
