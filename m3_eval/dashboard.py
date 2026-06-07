"""Streamlit dashboard for M3_PI_Guard metrics and RunLog replay."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


STOP_DECISIONS = {"ask", "deny"}
STOP_STATUSES = {"blocked", "needs_confirmation"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="M3_PI_Guard dashboard")
    parser.add_argument("--logs", required=True, help="RunLog JSONL file or directory")
    parser.add_argument("--metrics", required=True, help="summary.csv from m3_eval.evaluate")
    args = parser.parse_args(argv)

    import streamlit as st

    st.set_page_config(page_title="M3_PI_Guard", layout="wide")
    st.title("M3_PI_Guard")

    metric_rows = _read_csv(Path(args.metrics))
    logs_by_file = _read_logs(Path(args.logs))
    all_logs = [item for logs in logs_by_file.values() for item in logs]

    overall_rows = [row for row in metric_rows if row.get("scope") == "overall"]
    guarded_overall = _pick_overall(overall_rows, "guarded") or (overall_rows[-1] if overall_rows else {})

    cols = st.columns(6)
    for col, key in zip(cols, ("ASR", "UTR", "DSR", "BSR", "FPR", "WRS")):
        col.metric(key, guarded_overall.get(key, "n/a"))

    st.subheader("Baseline vs Guarded")
    st.dataframe(overall_rows, use_container_width=True)

    st.subheader("Attack Family")
    family_rows = [row for row in metric_rows if row.get("scope") == "attack_family"]
    st.dataframe(family_rows, use_container_width=True)

    st.subheader("Grouped Metrics")
    group_scope = st.selectbox(
        "scope",
        ["carrier", "language", "severity", "model", "defense_mode"],
        index=0,
    )
    st.dataframe(
        [row for row in metric_rows if row.get("scope") == group_scope],
        use_container_width=True,
    )

    st.subheader("Blocks")
    blocked = _blocked_records(logs_by_file)
    st.dataframe(blocked, use_container_width=True)

    st.subheader("Case Replay")
    case_ids = sorted({str(item.get("case_id", "")) for item in all_logs if item.get("case_id")})
    if case_ids:
        case_id = st.selectbox("case_id", case_ids)
        replay = sorted(
            [item for item in all_logs if str(item.get("case_id", "")) == case_id],
            key=lambda item: (str(item.get("run_id", "")), int(item.get("step", 0) or 0)),
        )
        st.dataframe([_compact_log_row(item) for item in replay], use_container_width=True)
        for item in replay:
            with st.expander(f"step {item.get('step')} | {item.get('guard_decision')} | {item.get('final_status')}"):
                st.json(item)
    else:
        st.info("No RunLog records found.")

    st.subheader("Raw Logs")
    log_files = list(logs_by_file)
    if log_files:
        selected_log = st.selectbox("log_file", log_files)
        raw_rows = logs_by_file[selected_log]
        st.dataframe([_compact_log_row(item) for item in raw_rows], use_container_width=True)
        raw_index = st.number_input(
            "raw_row",
            min_value=0,
            max_value=max(0, len(raw_rows) - 1),
            value=0,
            step=1,
        )
        if raw_rows:
            st.json(raw_rows[int(raw_index)])
    else:
        st.info("No raw log files found.")

    return 0


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_logs(path: Path) -> dict[str, list[dict[str, Any]]]:
    files: list[Path]
    if path.is_dir():
        files = sorted(item for item in path.glob("*.jsonl") if item.is_file())
    else:
        files = [path]

    logs_by_file: dict[str, list[dict[str, Any]]] = {}
    for file_path in files:
        logs_by_file[file_path.as_posix()] = _read_jsonl(file_path)
    return logs_by_file


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not path.exists():
        return records
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            value = json.loads(line)
            if isinstance(value, dict):
                records.append(value)
    return records


def _pick_overall(rows: list[dict[str, str]], mode: str) -> dict[str, str] | None:
    for row in rows:
        if row.get("defense_mode") == mode:
            return row
    return None


def _blocked_records(logs_by_file: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for log_file, logs in logs_by_file.items():
        for item in logs:
            decision = str(item.get("guard_decision", "")).lower()
            status = str(item.get("final_status", "")).lower()
            if decision not in STOP_DECISIONS and status not in STOP_STATUSES:
                continue
            tool_call = item.get("parsed_tool_call") if isinstance(item.get("parsed_tool_call"), dict) else {}
            records.append(
                {
                    "log_file": log_file,
                    "case_id": item.get("case_id", ""),
                    "step": item.get("step", ""),
                    "tool": tool_call.get("tool", ""),
                    "decision": item.get("guard_decision", ""),
                    "risk": item.get("risk_score", ""),
                    "status": item.get("final_status", ""),
                    "reasons": " | ".join(str(reason) for reason in item.get("reasons", [])),
                }
            )
    return records


def _compact_log_row(item: dict[str, Any]) -> dict[str, Any]:
    tool_call = item.get("parsed_tool_call") if isinstance(item.get("parsed_tool_call"), dict) else {}
    return {
        "run_id": item.get("run_id", ""),
        "step": item.get("step", ""),
        "tool": tool_call.get("tool", ""),
        "decision": item.get("guard_decision", ""),
        "risk": item.get("risk_score", ""),
        "status": item.get("final_status", ""),
        "reasons": " | ".join(str(reason) for reason in item.get("reasons", [])),
        "observation": _short_text(item.get("observation", "")),
    }


def _short_text(value: Any, limit: int = 160) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return text if len(text) <= limit else text[: limit - 3] + "..."


if __name__ == "__main__":
    raise SystemExit(main())
