"""CLI for reading M3 RunLog JSONL files and computing Day-1 metrics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

from .metrics import compare_runs, load_jsonl, summarize_logs


REPO_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate M3 local Agent run logs.")
    parser.add_argument("--logs", help="Single RunLog JSONL path")
    parser.add_argument("--baseline", help="Baseline RunLog JSONL path")
    parser.add_argument("--guarded", help="Guarded RunLog JSONL path")
    parser.add_argument("--cases", help="AttackCase JSONL path")
    parser.add_argument("--out", help="Optional output JSON path")
    args = parser.parse_args()

    cases = load_jsonl(_repo_path(args.cases)) if args.cases else []
    if args.baseline and args.guarded:
        result: Dict[str, Any] = compare_runs(
            load_jsonl(_repo_path(args.baseline)),
            load_jsonl(_repo_path(args.guarded)),
            cases,
        )
    elif args.logs:
        result = summarize_logs(load_jsonl(_repo_path(args.logs)), cases)
    else:
        raise SystemExit("Provide --logs or both --baseline and --guarded")

    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        out_path = _repo_path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text + "\n", encoding="utf-8")
    print(text)


def _repo_path(value: str | None) -> Path:
    if not value:
        raise ValueError("path value is required")
    path = Path(value)
    if path.is_absolute():
        return path
    return (REPO_ROOT / path).resolve()


if __name__ == "__main__":
    main()
