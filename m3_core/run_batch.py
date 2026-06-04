"""Batch runner for the local M3 Agent range.

Default use for the team: edit CONFIG at the top, then run this file.
CLI arguments are still supported for automation.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from m3_core.agent_runner import run_case
    from m3_core.llm_client import DEFAULT_MODEL
else:
    from .agent_runner import run_case
    from .llm_client import DEFAULT_MODEL


REPO_ROOT = Path(__file__).resolve().parents[1]

# 这个 CONFIG 是“打开文件直接运行”的默认参数区。
# 如果通过命令行传参，命令行参数会覆盖这里；如果不传任何参数，则使用这里。
# 组长检查时可以只改本区域，例如 defense 改为 guarded 或 out 改为新的文件名。
CONFIG = {
    "cases": "fixtures/sample_cases.jsonl",
    "backend": "stub",
    "model": DEFAULT_MODEL,
    "defense": "baseline",
    "out": "outputs/runs/stub_baseline.jsonl",
    "csv_out": "outputs/runs/stub_baseline.csv",
    "max_steps": 5,
    "limit": None,
    "families": "",
    "case_ids": "",
    "seed": 42,
    "shuffle": False,
    "resume": False,
    "fail_fast": False,
}


def main(argv: List[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv

    # 兼容两种使用方式：
    # 1. 无参数：适合 VSCode/PyCharm 直接点运行，读取顶部 CONFIG。
    # 2. 有参数：适合自动化脚本或 CI，沿用原来的 python -m m3_core.run_batch。
    if argv:
        config = _parse_args(argv)
    else:
        config = dict(CONFIG)

    result = run_batch(config)
    csv_part = f", wrote CSV to {result['csv_out']}" if result.get("csv_out") else ""
    print(
        f"OK: selected {result['selected_case_count']} cases, ran "
        f"{result['case_count']} cases, skipped {result['skipped_case_count']} "
        f"by resume, wrote {result['log_count']} log rows to {result['out']}"
        f"{csv_part}"
    )


def run_batch(config: Dict[str, Any]) -> Dict[str, Any]:
    """Run all AttackCase rows and write JSONL plus optional CSV logs.

    这个函数是给 run_day1.py 复用的核心入口。它只负责批量调度：
    读取 cases -> 调 run_case -> 写 JSONL/CSV。具体 Agent 循环和 guard
    判断都在 m3_core.agent_runner.run_case 中。
    """

    cases_path = _repo_path(str(config["cases"]))
    out_path = _repo_path(str(config["out"]))
    csv_out = config.get("csv_out")
    csv_path = _repo_path(str(csv_out)) if csv_out else None
    all_cases = list(read_jsonl(cases_path))
    if not all_cases:
        raise SystemExit(f"No cases found in {cases_path}")

    selected_cases = _filter_cases(all_cases, config)
    existing_logs: List[Dict[str, Any]] = []
    skipped_case_count = 0
    if _enabled(config.get("resume")) and out_path.exists():
        existing_logs = list(read_jsonl(out_path))
        completed_case_ids = _completed_case_ids(existing_logs)
        before_resume = len(selected_cases)
        selected_cases = [
            case
            for case in selected_cases
            if str(case.get("case_id", "")) not in completed_case_ids
        ]
        skipped_case_count = before_resume - len(selected_cases)

    selected_cases = _order_and_limit_cases(selected_cases, config)

    all_logs: List[Dict[str, Any]] = list(existing_logs)
    error_count = 0
    for case in selected_cases:
        # 每个 case 会产生多行 RunLog：baseline 中可能多步执行工具；
        # guarded 中通常第一步高风险工具就被 deny/ask 截断。
        try:
            case_logs = run_case(
                case,
                model=str(config.get("model") or DEFAULT_MODEL),
                backend=str(config.get("backend", "stub")),
                defense_mode=str(config.get("defense", "baseline")),
                max_steps=int(config.get("max_steps", 5)),
            )
        except Exception as exc:
            error_count += 1
            if _enabled(config.get("fail_fast")):
                raise
            case_logs = [
                _error_log(
                    case,
                    model=str(config.get("model") or DEFAULT_MODEL),
                    backend=str(config.get("backend", "stub")),
                    defense_mode=str(config.get("defense", "baseline")),
                    exc=exc,
                )
            ]
        all_logs.extend(case_logs)

    write_jsonl(out_path, all_logs)
    if csv_path:
        write_runlog_csv(csv_path, all_logs)

    return {
        "input_case_count": len(all_cases),
        "selected_case_count": len(selected_cases) + skipped_case_count,
        "case_count": len(selected_cases),
        "skipped_case_count": skipped_case_count,
        "error_count": error_count,
        "log_count": len(all_logs),
        "out": str(out_path),
        "csv_out": str(csv_path) if csv_path else "",
    }


def _parse_args(argv: List[str]) -> Dict[str, Any]:
    """Parse legacy CLI arguments into the same shape as CONFIG."""

    parser = argparse.ArgumentParser(description="Run M3 local Agent attack cases.")
    parser.add_argument("--cases", required=True, help="Input AttackCase JSONL path")
    parser.add_argument("--backend", choices=["ollama", "stub"], default="stub")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--defense", choices=["baseline", "guarded"], default="baseline")
    parser.add_argument("--out", required=True, help="Output RunLog JSONL path")
    parser.add_argument("--csv-out", help="Optional output RunLog CSV path")
    parser.add_argument("--max-steps", type=int, default=5)
    parser.add_argument("--limit", type=int, help="Only run the first N selected cases")
    parser.add_argument(
        "--families",
        help="Comma-separated attack_family filter, for example rag_indirect,json_rpc",
    )
    parser.add_argument(
        "--case-ids",
        help="Comma-separated case_id filter, for example RAG-PI-001,JSONRPC-001",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed for --shuffle")
    parser.add_argument("--shuffle", action="store_true", help="Shuffle selected cases")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip case_ids that already have terminal logs in --out",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop immediately if a case raises an exception",
    )
    args = parser.parse_args(argv)
    return vars(args)


def _filter_cases(
    cases: List[Dict[str, Any]],
    config: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Apply family and case-id filters while preserving file order."""

    selected = list(cases)
    families = set(_csv_values(config.get("families")))
    case_ids = set(_csv_values(config.get("case_ids")))

    if families:
        selected = [
            case
            for case in selected
            if str(case.get("attack_family", "")).strip() in families
        ]
    if case_ids:
        selected = [
            case for case in selected if str(case.get("case_id", "")).strip() in case_ids
        ]
    return selected


def _order_and_limit_cases(
    cases: List[Dict[str, Any]],
    config: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Apply optional shuffle and limit after filters and resume skipping."""

    selected = list(cases)
    if _enabled(config.get("shuffle")):
        rng = random.Random(int(config.get("seed", 42)))
        rng.shuffle(selected)

    limit = config.get("limit")
    if limit not in {None, ""}:
        selected = selected[: int(limit)]
    return selected


def _completed_case_ids(logs: Iterable[Dict[str, Any]]) -> set[str]:
    """Return case_ids with terminal RunLog status for resume mode."""

    terminal_statuses = {
        "completed",
        "blocked",
        "needs_confirmation",
        "max_steps_reached",
        "error",
    }
    completed = set()
    for row in logs:
        status = str(row.get("final_status", ""))
        if status in terminal_statuses:
            case_id = str(row.get("case_id", "")).strip()
            if case_id:
                completed.add(case_id)
    return completed


def _error_log(
    case: Dict[str, Any],
    *,
    model: str,
    backend: str,
    defense_mode: str,
    exc: Exception,
) -> Dict[str, Any]:
    """Create a schema-compatible RunLog row for non-fail-fast errors."""

    return {
        "run_id": "runner-error",
        "case_id": case.get("case_id", ""),
        "model": model,
        "backend": backend,
        "defense_mode": defense_mode,
        "step": 0,
        "attack_family": case.get("attack_family", ""),
        "risk_tags": case.get("risk_tags", []),
        "unsafe_target_actions": case.get("unsafe_target_actions", []),
        "raw_model_output": "",
        "parsed_tool_call": {},
        "guard_decision": "error",
        "risk_score": None,
        "reasons": ["runner_exception"],
        "observation": f"ERROR: {type(exc).__name__}: {exc}",
        "final_status": "error",
    }


def _csv_values(value: Any) -> List[str]:
    """Normalize comma-separated config values into non-empty strings."""

    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).split(",") if item.strip()]


def _enabled(value: Any) -> bool:
    """Interpret booleans from CONFIG or argparse consistently."""

    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def read_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    """Stream JSONL rows and report exact line number on malformed JSON."""

    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                yield json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_number}") from exc


def write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    """Write step-level logs in JSONL, which is the canonical machine format."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_runlog_csv(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    """Write a spreadsheet-friendly flattened RunLog CSV.

    JSONL 保留原始嵌套结构，适合程序读取；CSV 将 parsed_tool_call、
    risk_tags、reasons、observation 等嵌套字段压成字符串，方便 Excel/WPS 查看。
    使用 utf-8-sig 是为了 Windows Excel 打开中文时更稳。
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "run_id",
        "case_id",
        "model",
        "backend",
        "defense_mode",
        "step",
        "attack_family",
        "risk_tags",
        "unsafe_target_actions",
        "tool",
        "tool_arguments",
        "guard_decision",
        "risk_score",
        "reasons",
        "observation",
        "final_status",
        "raw_model_output",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            tool_call = row.get("parsed_tool_call")
            if not isinstance(tool_call, dict):
                tool_call = {}

            # CSV 单元格不能直接放 dict/list，所以统一通过 _csv_cell 转成
            # JSON 字符串；这样既能被表格打开，也能保留原始信息。
            writer.writerow(
                {
                    "run_id": row.get("run_id", ""),
                    "case_id": row.get("case_id", ""),
                    "model": row.get("model", ""),
                    "backend": row.get("backend", ""),
                    "defense_mode": row.get("defense_mode", ""),
                    "step": row.get("step", ""),
                    "attack_family": row.get("attack_family", ""),
                    "risk_tags": _csv_cell(row.get("risk_tags", [])),
                    "unsafe_target_actions": _csv_cell(
                        row.get("unsafe_target_actions", [])
                    ),
                    "tool": tool_call.get("tool", ""),
                    "tool_arguments": _csv_cell(tool_call.get("arguments", {})),
                    "guard_decision": row.get("guard_decision", ""),
                    "risk_score": row.get("risk_score", ""),
                    "reasons": _csv_cell(row.get("reasons", [])),
                    "observation": _csv_cell(row.get("observation", "")),
                    "final_status": row.get("final_status", ""),
                    "raw_model_output": row.get("raw_model_output", ""),
                }
            )


def _csv_cell(value: Any) -> str:
    """Convert nested Python values to a single safe CSV cell."""

    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    if value is None:
        return ""
    return str(value)


def _repo_path(value: str) -> Path:
    """Resolve paths relative to repository root for stable IDE execution."""

    path = Path(value)
    if path.is_absolute():
        return path
    return (REPO_ROOT / path).resolve()


if __name__ == "__main__":
    main()
