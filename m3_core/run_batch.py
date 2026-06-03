"""Batch runner for the local M3 Agent range.

Default use for the team: edit CONFIG at the top, then run this file.
CLI arguments are still supported for automation.
"""

from __future__ import annotations

import argparse
import csv
import json
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
        f"OK: ran {result['case_count']} cases, wrote {result['log_count']} "
        f"log rows to {result['out']}{csv_part}"
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
    cases = list(read_jsonl(cases_path))
    if not cases:
        raise SystemExit(f"No cases found in {cases_path}")

    all_logs: List[Dict[str, Any]] = []
    for case in cases:
        # 每个 case 会产生多行 RunLog：baseline 中可能多步执行工具；
        # guarded 中通常第一步高风险工具就被 deny/ask 截断。
        all_logs.extend(
            run_case(
                case,
                model=str(config.get("model") or DEFAULT_MODEL),
                backend=str(config.get("backend", "stub")),
                defense_mode=str(config.get("defense", "baseline")),
                max_steps=int(config.get("max_steps", 5)),
            )
        )

    write_jsonl(out_path, all_logs)
    if csv_path:
        write_runlog_csv(csv_path, all_logs)

    return {
        "case_count": len(cases),
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
    args = parser.parse_args(argv)
    return vars(args)


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
