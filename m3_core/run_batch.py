"""Batch runner CLI for the local M3 Agent range."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

from .agent_runner import run_case
from .llm_client import DEFAULT_MODEL


REPO_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run M3 local Agent attack cases.")
    parser.add_argument("--cases", required=True, help="Input AttackCase JSONL path")
    parser.add_argument("--backend", choices=["ollama", "stub"], default="stub")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--defense", choices=["baseline", "guarded"], default="baseline")
    parser.add_argument("--out", required=True, help="Output RunLog JSONL path")
    parser.add_argument("--max-steps", type=int, default=5)
    args = parser.parse_args()

    cases_path = _repo_path(args.cases)
    out_path = _repo_path(args.out)
    cases = list(read_jsonl(cases_path))
    if not cases:
        raise SystemExit(f"No cases found in {cases_path}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    log_count = 0
    with out_path.open("w", encoding="utf-8") as handle:
        for case in cases:
            logs = run_case(
                case,
                model=args.model,
                backend=args.backend,
                defense_mode=args.defense,
                max_steps=args.max_steps,
            )
            for log in logs:
                handle.write(json.dumps(log, ensure_ascii=False) + "\n")
                log_count += 1

    print(
        f"OK: ran {len(cases)} cases, wrote {log_count} log rows to {out_path}"
    )


def read_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                yield json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_number}") from exc


def _repo_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return (REPO_ROOT / path).resolve()


if __name__ == "__main__":
    main()
