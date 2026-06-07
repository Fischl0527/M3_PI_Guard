"""DAY5 RunLog integrity and safety audit tool."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = "outputs/metrics/day5_log_audit.json"
REQUIRED_FIELDS = {
    "run_id",
    "case_id",
    "model",
    "defense_mode",
    "step",
    "parsed_tool_call",
    "guard_decision",
    "final_status",
    "parse_ok",
    "parse_error",
}
PATH_KEYS = {"path", "file", "filename", "filepath", "target", "source"}
ENDPOINT_KEYS = {"endpoint", "url", "uri"}
SAFE_EMAIL_DOMAINS = {".test", "example.com", "example.org", "example.net", "localhost"}
SAFE_URL_HOSTS = {"127.0.0.1", "localhost", "::1"}
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,}|localhost)\b")
URL_RE = re.compile(r"\bhttps?://[^\s\"'<>]+", re.I)


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit DAY5 RunLog JSONL files.")
    parser.add_argument("--log-dir", required=True, help="RunLog JSONL file or directory")
    parser.add_argument("--out", default=DEFAULT_OUT, help="Audit JSON output path")
    args = parser.parse_args(argv)

    report = audit_logs(_repo_path(args.log_dir))
    out_path = _repo_path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out_path}")
    print(
        f"status={report['status']} files={report['file_count']} rows={report['row_count']} "
        f"cases={report['case_count']} issues={report['issue_count']} parse_errors={report['parse_error_count']}"
    )
    return 0 if report["status"] in {"pass", "warn"} else 1


def audit_logs(path: Path) -> Dict[str, Any]:
    log_files = _log_files(path)
    issues: List[Dict[str, Any]] = []
    rows: List[Dict[str, Any]] = []
    by_file: List[Dict[str, Any]] = []

    if not log_files:
        issues.append(_issue("error", str(path), 0, "", "no_jsonl_files", "No JSONL log files found."))

    for log_file in log_files:
        file_rows = list(_read_jsonl(log_file, issues))
        if not file_rows:
            issues.append(_issue("error", log_file, 0, "", "empty_log", "RunLog file is empty."))
        by_file.append(
            {
                "file": _relative_or_name(log_file),
                "rows": len(file_rows),
                "cases": len({str(row.get("case_id", "")) for row in file_rows if row.get("case_id")}),
            }
        )
        rows.extend(file_rows)

    parse_error_case_ids: set[str] = set()
    for index, row in enumerate(rows, start=1):
        case_id = str(row.get("case_id", ""))
        missing = sorted(REQUIRED_FIELDS - set(row))
        if missing:
            issues.append(
                _issue("error", "", index, case_id, "missing_required_fields", ",".join(missing))
            )

        if row.get("parse_ok") is False or str(row.get("parse_error", "")).strip():
            parse_error_case_ids.add(case_id)
            issues.append(
                _issue(
                    "warn",
                    "",
                    index,
                    case_id,
                    "parse_error",
                    str(row.get("parse_error", ""))[:300],
                )
            )

        tool_call = row.get("parsed_tool_call")
        if not isinstance(tool_call, dict):
            issues.append(_issue("error", "", index, case_id, "invalid_tool_call", "parsed_tool_call is not an object"))
            continue

        _audit_tool_call(tool_call, index, case_id, issues)

    error_count = sum(1 for item in issues if item["severity"] == "error")
    warn_count = sum(1 for item in issues if item["severity"] == "warn")
    status = "fail" if error_count else "warn" if warn_count else "pass"
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "log_input": _relative_or_name(path),
        "file_count": len(log_files),
        "row_count": len(rows),
        "case_count": len({str(row.get("case_id", "")) for row in rows if row.get("case_id")}),
        "parse_error_count": len(parse_error_case_ids),
        "parse_error_case_ids": sorted(case_id for case_id in parse_error_case_ids if case_id),
        "unstable_case_ids": sorted(case_id for case_id in parse_error_case_ids if case_id),
        "issue_count": len(issues),
        "error_count": error_count,
        "warn_count": warn_count,
        "by_file": by_file,
        "by_defense_mode": dict(Counter(str(row.get("defense_mode", "")) for row in rows)),
        "issues": issues,
    }


def _audit_tool_call(
    tool_call: Dict[str, Any],
    row_number: int,
    case_id: str,
    issues: List[Dict[str, Any]],
) -> None:
    tool = str(tool_call.get("tool", "")).strip()
    arguments = tool_call.get("arguments")
    if not isinstance(arguments, dict):
        issues.append(_issue("error", "", row_number, case_id, "invalid_arguments", "Tool arguments are not an object."))
        return

    for key, value in _walk(arguments):
        key_lower = key.lower()
        text = str(value)
        if key_lower in PATH_KEYS or "path" in key_lower:
            _audit_path(text, row_number, case_id, issues)
        for email in EMAIL_RE.finditer(text):
            domain = email.group(1).lower()
            if not _safe_email_domain(domain):
                issues.append(_issue("error", "", row_number, case_id, "real_email_detected", email.group(0)))
        for url in URL_RE.findall(text):
            if not _safe_url(url):
                issues.append(_issue("error", "", row_number, case_id, "real_url_detected", url))

    if tool == "call_api":
        endpoint = ""
        for key in ENDPOINT_KEYS:
            if key in arguments:
                endpoint = str(arguments.get(key, ""))
                break
        if endpoint and not _safe_mock_endpoint(endpoint):
            issues.append(_issue("error", "", row_number, case_id, "non_mock_endpoint", endpoint))
        elif not endpoint:
            issues.append(_issue("warn", "", row_number, case_id, "missing_api_endpoint", "call_api has no endpoint/url field."))


def _audit_path(value: str, row_number: int, case_id: str, issues: List[Dict[str, Any]]) -> None:
    normalized = value.strip().replace("\\", "/")
    if not normalized:
        return
    if "://" in normalized:
        return
    if normalized.startswith("sandbox/") or normalized in {"sandbox", "public"}:
        return
    if normalized.startswith("public/"):
        return
    if normalized.startswith("./sandbox/"):
        return
    if Path(normalized).is_absolute():
        issues.append(_issue("error", "", row_number, case_id, "absolute_path_detected", value))
        return
    if ".." in Path(normalized).parts:
        issues.append(_issue("error", "", row_number, case_id, "path_traversal_detected", value))


def _safe_email_domain(domain: str) -> bool:
    return any(domain == safe.lstrip(".") or domain.endswith(safe) for safe in SAFE_EMAIL_DOMAINS)


def _safe_url(url: str) -> bool:
    lowered = url.lower()
    if lowered.startswith("http://127.0.0.1") or lowered.startswith("http://localhost"):
        return True
    if lowered.startswith("https://127.0.0.1") or lowered.startswith("https://localhost"):
        return True
    return any(host in lowered for host in SAFE_URL_HOSTS) or "example." in lowered


def _safe_mock_endpoint(endpoint: str) -> bool:
    value = endpoint.strip().lower()
    return (
        value == "mock"
        or value == "/mock"
        or value.startswith("mock/")
        or value.startswith("/mock/")
        or value.startswith("mock://")
    )


def _walk(value: Any, prefix: str = "") -> Iterable[tuple[str, Any]]:
    if isinstance(value, dict):
        for key, item in value.items():
            name = f"{prefix}.{key}" if prefix else str(key)
            yield from _walk(item, name)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk(item, f"{prefix}[{index}]")
    else:
        yield prefix, value


def _log_files(path: Path) -> List[Path]:
    if path.is_file():
        return [path] if path.suffix.lower() == ".jsonl" else []
    if path.is_dir():
        return sorted(item for item in path.glob("*.jsonl") if item.is_file())
    return []


def _read_jsonl(path: Path, issues: List[Dict[str, Any]]) -> Iterable[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                row = json.loads(stripped)
            except json.JSONDecodeError as exc:
                issues.append(_issue("error", path, line_number, "", "invalid_json", exc.msg))
                continue
            if not isinstance(row, dict):
                issues.append(_issue("error", path, line_number, "", "row_not_object", "JSONL row is not an object."))
                continue
            yield row


def _issue(
    severity: str,
    file_path: str | Path,
    row_number: int,
    case_id: str,
    code: str,
    message: str,
) -> Dict[str, Any]:
    return {
        "severity": severity,
        "file": _relative_or_name(Path(file_path)) if file_path else "",
        "row": row_number,
        "case_id": case_id,
        "code": code,
        "message": message,
    }


def _relative_or_name(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except Exception:
        return path.as_posix()


def _repo_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return (REPO_ROOT / path).resolve()


if __name__ == "__main__":
    raise SystemExit(main())
