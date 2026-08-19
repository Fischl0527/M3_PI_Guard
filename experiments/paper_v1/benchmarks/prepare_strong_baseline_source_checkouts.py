"""Prepare pinned local source checkouts for required strong baselines.

This is a reproducibility helper for the paper-v1 strong-baseline gate.  It
reads the external strong-baseline source registry, prepares local source
checkouts under ``external/baselines/`` and writes an auditable manifest.

The default mode is dry-run.  It does not install Python packages, download
model weights, start model services, call APIs or run any baseline.  With
``--execute`` it performs only Git source operations for repository entries
that already have an expected remote HEAD in the registry.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from .build_strong_baseline_dependency_snapshot import (
    DEFAULT_BASELINE_ROOT,
    DEFAULT_EXTERNAL_REGISTRY,
    LOCAL_CHECKOUT_BY_ENTRY_ID,
)
from .common import portable_path, portable_value, rows_sha256, sha256_file


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = ROOT / "protocols" / "paper_upgrade_v1"
MANIFEST_STEM = "strong_baseline_source_checkout_manifest_v1"
MANIFEST_VERSION = "m3-paper-v1-strong-baseline-source-checkout-1.0"


def _path(path: Path) -> str:
    return portable_path(path, root=ROOT)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(str(path) + " must contain a JSON object")
    return value


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _entries(registry: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = registry.get("entries")
    if not isinstance(rows, list):
        raise ValueError("external strong-baseline registry missing entries list")
    return [dict(row) for row in rows if isinstance(row, Mapping)]


def _repository_reference(entry: Mapping[str, Any]) -> dict[str, Any] | None:
    references = entry.get("secondary_references")
    if not isinstance(references, list):
        return None
    for item in references:
        if isinstance(item, Mapping) and item.get("kind") == "repository":
            return dict(item)
    return None


def _git_head(path: Path) -> str:
    if not (path / ".git").exists():
        return ""
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception:
        return ""
    return result.stdout.strip()


def _path_size_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for item in path.rglob("*"):
        try:
            if item.is_file():
                total += item.stat().st_size
        except OSError:
            continue
    return total


def _run_git(args: Sequence[str], *, timeout: int = 180) -> dict[str, Any]:
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return {
        "args": ["git", *args],
        "returncode": result.returncode,
        "stdout_tail": result.stdout[-1200:],
        "stderr_tail": result.stderr[-1200:],
    }


def _entry_plan(
    entry: Mapping[str, Any],
    *,
    baseline_root: Path,
) -> dict[str, Any]:
    entry_id = str(entry.get("id", ""))
    repo = _repository_reference(entry)
    checkout_name = LOCAL_CHECKOUT_BY_ENTRY_ID.get(entry_id, "")
    local_path = baseline_root / checkout_name if checkout_name else None
    expected_head = str(repo.get("remote_head_sha", "")) if repo else ""
    repository_url = str(repo.get("url", "")) if repo else ""
    relevant_path = str(repo.get("relevant_path", "")) if repo else ""
    existing_head = _git_head(local_path) if local_path else ""
    exists = bool(local_path and local_path.exists())
    matched = bool(existing_head and expected_head and existing_head == expected_head)
    return {
        "entry_id": entry_id,
        "registry_key": str(entry.get("registry_key", "")),
        "display_name": str(entry.get("display_name", "")),
        "repository_url": repository_url,
        "expected_head": expected_head,
        "remote_head_observed_at": str(repo.get("remote_head_observed_at", "")) if repo else "",
        "checkout_name": checkout_name,
        "local_path": str(local_path) if local_path else "",
        "local_exists_before": exists,
        "local_head_before": existing_head,
        "local_head_matches_before": matched,
        "relevant_path": relevant_path,
        "repository_entry": bool(repo and checkout_name and expected_head),
        "planned_action": (
            "skip_not_repository_entry"
            if not repo or not checkout_name
            else "skip_missing_expected_head"
            if not expected_head
            else "already_matched"
            if matched
            else "clone_or_fetch_checkout"
        ),
    }


def _prepare_entry(
    plan: Mapping[str, Any],
    *,
    execute: bool,
) -> dict[str, Any]:
    row = dict(plan)
    commands: list[dict[str, Any]] = []
    path = Path(str(plan.get("local_path", ""))) if plan.get("local_path") else None
    expected_head = str(plan.get("expected_head", ""))
    repository_url = str(plan.get("repository_url", ""))
    row["executed"] = False
    row["commands"] = commands
    row["error"] = ""

    if plan.get("planned_action") in {
        "skip_not_repository_entry",
        "skip_missing_expected_head",
        "already_matched",
    }:
        row["status"] = str(plan.get("planned_action"))
    elif not execute:
        row["status"] = "planned_not_executed"
    elif path is None:
        row["status"] = "failed_no_local_path"
    elif path.exists() and not (path / ".git").exists():
        row["status"] = "failed_existing_non_git_path"
        row["error"] = "local path exists but is not a Git checkout"
    else:
        row["executed"] = True
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            commands.append(
                _run_git(
                    [
                        "clone",
                        "--filter=blob:none",
                        "--depth",
                        "1",
                        "--no-tags",
                        repository_url,
                        str(path),
                    ],
                    timeout=300,
                )
            )
        else:
            commands.append(_run_git(["-C", str(path), "fetch", "--depth", "1", "origin", expected_head]))

        if commands and commands[-1]["returncode"] != 0:
            row["status"] = "failed_git_fetch_or_clone"
        else:
            commands.append(_run_git(["-C", str(path), "checkout", "--detach", expected_head]))
            if commands[-1]["returncode"] != 0:
                row["status"] = "failed_git_checkout"
            else:
                row["status"] = "checkout_command_completed"

    final_head = _git_head(path) if path else ""
    relevant_path = str(plan.get("relevant_path", ""))
    row["local_exists_after"] = bool(path and path.exists())
    row["local_head_after"] = final_head
    row["local_head_matches_expected_after"] = bool(final_head and expected_head and final_head == expected_head)
    row["relevant_path_exists_after"] = bool(path and relevant_path and (path / relevant_path).exists())
    row["checkout_size_bytes"] = _path_size_bytes(path) if path and path.exists() else 0
    row["source_checkout_ready"] = bool(row["local_head_matches_expected_after"])
    if relevant_path:
        row["source_checkout_ready"] = bool(
            row["source_checkout_ready"] and row["relevant_path_exists_after"]
        )
    if row["status"] == "checkout_command_completed" and row["source_checkout_ready"]:
        row["status"] = "source_checkout_ready"
    elif row["status"] == "already_matched" and row["source_checkout_ready"]:
        row["status"] = "source_checkout_ready"
    elif row["status"] == "checkout_command_completed":
        row["status"] = "checkout_completed_but_not_ready"
    return row


def _check(name: str, passed: bool, *, severity: str = "error", detail: Any = None) -> dict[str, Any]:
    return {
        "name": name,
        "status": "pass" if passed else "fail",
        "severity": severity,
        "detail": detail,
    }


def _write_markdown(path: Path, manifest: Mapping[str, Any]) -> None:
    lines = [
        "# Strong-baseline source checkout manifest v1",
        "",
        f"Generated: {manifest['created_at']}",
        "",
        "## Result",
        "",
        f"- Status: `{manifest['status']}`",
        f"- Execute mode: `{manifest['execute']}`",
        f"- Checkout root: `{manifest['baseline_root']}`",
        f"- Source-ready entries: `{manifest['source_ready_entries']}`",
        f"- Result eligible for formal tables: `{manifest['result_eligible_for_formal_tables']}`",
        "",
        "## Entries",
        "",
        "| Entry | Action/status | Expected HEAD | Local HEAD | Ready | Size MiB |",
        "|---|---|---|---|---:|---:|",
    ]
    for row in manifest["entries"]:
        size_mib = round(float(row.get("checkout_size_bytes", 0)) / (1024 * 1024), 2)
        lines.append(
            f"| `{row['entry_id']}` | `{row['status']}` | `{row['expected_head']}` | "
            f"`{row['local_head_after']}` | `{row['source_checkout_ready']}` | {size_mib} |"
        )
    lines.extend(["", "## Checks", "", "| Check | Status | Severity | Detail |", "|---|---|---|---|"])
    for check in manifest["checks"]:
        detail = json.dumps(check.get("detail"), ensure_ascii=False, sort_keys=True)
        if len(detail) > 220:
            detail = detail[:217] + "..."
        lines.append(
            f"| `{check['name']}` | `{check['status']}` | `{check['severity']}` | {detail.replace('|', '\\|')} |"
        )
    lines.extend(["", "## Boundary", "", manifest["boundary"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def prepare_strong_baseline_source_checkouts(
    *,
    external_registry_path: Path = DEFAULT_EXTERNAL_REGISTRY,
    baseline_root: Path = DEFAULT_BASELINE_ROOT,
    output_dir: Path = DEFAULT_OUTPUT,
    execute: bool = False,
    entry_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    external_registry_path = external_registry_path.resolve()
    baseline_root = baseline_root.resolve()
    output_dir = output_dir.resolve()
    registry = _read_json(external_registry_path)
    selected = set(entry_ids or [])
    source_entries = []
    for entry in _entries(registry):
        entry_id = str(entry.get("id", ""))
        if selected and entry_id not in selected:
            continue
        source_entries.append(entry)
    rows = [
        _prepare_entry(_entry_plan(entry, baseline_root=baseline_root), execute=execute)
        for entry in source_entries
    ]
    requested_missing = sorted(selected - {str(entry.get("id", "")) for entry in source_entries})
    ready = sorted(row["entry_id"] for row in rows if row.get("source_checkout_ready"))
    failed = sorted(
        row["entry_id"]
        for row in rows
        if str(row.get("status", "")).startswith("failed")
        or row.get("status") == "checkout_completed_but_not_ready"
    )
    checks = [
        _check(
            "external_registry_loaded",
            bool(source_entries),
            detail={"path": _path(external_registry_path), "selected_entries": len(source_entries)},
        ),
        _check(
            "requested_entries_exist",
            not requested_missing,
            detail={"missing": requested_missing},
        ),
        _check(
            "repository_entries_have_expected_heads",
            all(row.get("expected_head") or not row.get("repository_entry") for row in rows),
            detail={
                row["entry_id"]: row.get("expected_head", "")
                for row in rows
                if row.get("repository_entry")
            },
        ),
        _check(
            "executed_checkouts_have_matching_heads",
            not execute or not failed,
            detail={"failed_or_not_ready": failed},
        ),
        _check(
            "source_checkout_manifest_not_result_eligible",
            True,
            severity="warning",
            detail=False,
        ),
    ]
    portable_rows = portable_value(rows, root=ROOT)
    portable_checks = portable_value(checks, root=ROOT)
    manifest = {
        "schema_version": "paper-strong-baseline-source-checkout-manifest-1.0",
        "manifest_version": MANIFEST_VERSION,
        "status": "completed" if all(check["status"] == "pass" for check in checks) else "failed",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "execute": execute,
        "external_registry_path": _path(external_registry_path),
        "external_registry_sha256": sha256_file(external_registry_path),
        "baseline_root": _path(baseline_root),
        "entry_filter": sorted(selected),
        "entries": portable_rows,
        "entries_sha256": rows_sha256(portable_rows),
        "source_ready_entries": ready,
        "failed_or_not_ready_entries": failed,
        "checks": portable_checks,
        "checks_sha256": rows_sha256(portable_checks),
        "total_checks": len(checks),
        "passed_checks": sum(1 for check in checks if check["status"] == "pass"),
        "result_eligible_for_formal_tables": False,
        "boundary": (
            "Source checkout preparation only. It may clone or fetch Git source "
            "repositories when execute=true, but it does not install packages, "
            "download model weights, start model services, call APIs, run "
            "baselines or create formal effect evidence."
        ),
    }
    json_path = output_dir / f"{MANIFEST_STEM}.json"
    md_path = output_dir / f"{MANIFEST_STEM}.md"
    _write_json(json_path, manifest)
    _write_markdown(md_path, manifest)
    manifest["json_path"] = _path(json_path)
    manifest["markdown_path"] = _path(md_path)
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--external-registry", type=Path, default=DEFAULT_EXTERNAL_REGISTRY)
    parser.add_argument("--baseline-root", type=Path, default=DEFAULT_BASELINE_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--entry-id", action="append", default=[])
    parser.add_argument("--execute", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = prepare_strong_baseline_source_checkouts(
        external_registry_path=args.external_registry,
        baseline_root=args.baseline_root,
        output_dir=args.output_dir,
        execute=args.execute,
        entry_ids=args.entry_id,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
