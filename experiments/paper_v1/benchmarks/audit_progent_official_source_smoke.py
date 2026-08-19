"""Audit the pinned official Progent source with a network-blocked runtime smoke.

This audit is a source/dependency qualification only.  It imports the official
``secagent`` package from the pinned checkout, disables policy generation, and
exercises deterministic rule enforcement plus the Z3-backed subset check.  It
does not call a model, execute an AgentDojo case, or create formal effect
evidence.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .common import portable_path, portable_value, rows_sha256, sha256_file


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CHECKOUT = ROOT / "external" / "baselines" / "progent"
DEFAULT_REGISTRY = (
    ROOT / "protocols" / "paper_upgrade_v1" / "external_strong_baselines_v1.json"
)
DEFAULT_OUTPUT = ROOT / "protocols" / "paper_upgrade_v1"
EXPECTED_REPOSITORY = "https://github.com/sunblaze-ucb/progent"
EXPECTED_COMMIT = "8a8eb894b9d568a32b4e58252fea85b47f789c77"
AUDIT_STEM = "progent_official_source_smoke_v1"
AUDIT_VERSION = "m3-paper-v1-progent-official-source-smoke-1.0"

REQUIRED_PATHS = (
    "README.md",
    "pyproject.toml",
    "secagent/__init__.py",
    "secagent/tool.py",
    "secagent/policy_analysis.py",
    "agentdojo/README.md",
    "agentdojo/run.sh",
    "agentdojo/src/agentdojo/agent_pipeline/basic_elements.py",
    "agentdojo/src/agentdojo/agent_pipeline/tool_execution.py",
)


def _path(path: Path) -> str:
    return portable_path(path, root=ROOT)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _git_head(path: Path) -> str:
    if not (path / ".git").exists():
        return ""
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def _repository_reference(registry: Mapping[str, Any]) -> dict[str, Any]:
    entries = registry.get("entries", [])
    if not isinstance(entries, list):
        return {}
    entry = next(
        (
            row
            for row in entries
            if isinstance(row, Mapping) and row.get("id") == "progent_arxiv2025"
        ),
        {},
    )
    references = entry.get("secondary_references", [])
    if not isinstance(references, list):
        return {}
    return dict(
        next(
            (
                row
                for row in references
                if isinstance(row, Mapping) and row.get("kind") == "repository"
            ),
            {},
        )
    )


def _check(
    name: str,
    passed: bool,
    *,
    severity: str = "error",
    detail: Any = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "status": "pass" if passed else "fail",
        "severity": severity,
        "detail": detail,
    }


def _runtime_smoke(checkout: Path, python_executable: Path) -> dict[str, Any]:
    source = r'''
import json
import socket
import sys
from pathlib import Path

checkout = Path(sys.argv[1])
sys.path.insert(0, str(checkout))

def blocked_connect(*args, **kwargs):
    raise RuntimeError("network disabled by Progent source-smoke harness")

socket.socket.connect = blocked_connect

import secagent
from secagent.policy_analysis import security_policy_subset_check

secagent.reset_security_policy(include_human_policy=True)
secagent.update_available_tools([
    {
        "name": "send_email",
        "description": "send email",
        "args": {
            "recipient": {"type": "string"},
            "body": {"type": "string"},
        },
    },
    {
        "name": "read_email",
        "description": "read email",
        "args": {"email_id": {"type": "string"}},
    },
])
policy = {
    "read_email": [
        (100, 0, {"email_id": {"type": "string", "enum": ["trusted-id"]}}, 0)
    ],
    "send_email": [
        (
            100,
            0,
            {
                "recipient": {
                    "type": "string",
                    "enum": ["alice@example.com"],
                }
            },
            0,
        )
    ],
}
secagent.update_security_policy(policy)

decisions = {}
for name, tool, args in [
    (
        "allow_exact",
        "send_email",
        {"recipient": "alice@example.com", "body": "ok"},
    ),
    (
        "deny_bad_recipient",
        "send_email",
        {"recipient": "eve@example.com", "body": "leak"},
    ),
    ("deny_missing_tool", "delete_all", {}),
]:
    try:
        secagent.check_tool_call(tool, args)
        decisions[name] = "allow"
    except Exception as exc:
        decisions[name] = {
            "decision": "deny",
            "exception": type(exc).__name__,
        }

old = {
    "send_email": [(100, 0, {"recipient": {"type": "string"}}, 0)]
}
narrow = {
    "send_email": [
        (
            100,
            0,
            {
                "recipient": {
                    "type": "string",
                    "enum": ["alice@example.com"],
                }
            },
            0,
        )
    ]
}
expand = {"send_email": [(100, 0, {}, 0)]}
decisions["narrow_is_subset"] = security_policy_subset_check(old, narrow)
decisions["expand_is_subset"] = security_policy_subset_check(narrow, expand)
decisions["network_guard_active"] = True
print(json.dumps(decisions, ensure_ascii=False, sort_keys=True))
'''
    env = dict(os.environ)
    env.update(
        {
            "SECAGENT_GENERATE": "False",
            "ENABLE_SECAGENT": "False",
            "SECAGENT_POLICY_MODEL": "offline-source-smoke",
        }
    )
    result = subprocess.run(
        [str(python_executable), "-c", source, str(checkout)],
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
        env=env,
    )
    parsed: dict[str, Any] = {}
    if result.returncode == 0:
        stdout_lines = [line for line in result.stdout.splitlines() if line.strip()]
        if stdout_lines:
            try:
                candidate = json.loads(stdout_lines[-1])
                if isinstance(candidate, dict):
                    parsed = candidate
            except json.JSONDecodeError:
                parsed = {}
    expected = {
        "allow_exact": "allow",
        "deny_bad_recipient": {
            "decision": "deny",
            "exception": "ValidationError",
        },
        "deny_missing_tool": {
            "decision": "deny",
            "exception": "ValidationError",
        },
        "narrow_is_subset": True,
        "expand_is_subset": False,
        "network_guard_active": True,
    }
    return {
        "passed": result.returncode == 0 and parsed == expected,
        "returncode": result.returncode,
        "python_executable": str(python_executable),
        "observed": parsed,
        "expected": expected,
        "stdout_tail": result.stdout[-2000:],
        "stderr_tail": result.stderr[-4000:],
        "network_guard_active": True,
    }


def _write_markdown(path: Path, audit: Mapping[str, Any]) -> None:
    lines = [
        "# Progent official source smoke v1",
        "",
        f"Generated: {audit['created_at']}",
        "",
        "## Result",
        "",
        f"- Status: `{audit['status']}`",
        f"- Source commit: `{audit['source_checkout']['actual_commit']}`",
        f"- Offline runtime smoke: `{audit['offline_runtime_smoke']['passed']}`",
        f"- Network calls performed: `{audit['network_calls_performed']}`",
        f"- Formal result eligible: `{audit['result_eligible_for_formal_tables']}`",
        "",
        "## Checks",
        "",
        "| Check | Status | Severity | Detail |",
        "|---|---|---|---|",
    ]
    for check in audit["checks"]:
        detail = json.dumps(check.get("detail"), ensure_ascii=False, sort_keys=True)
        if len(detail) > 220:
            detail = detail[:217] + "..."
        lines.append(
            f"| `{check['name']}` | `{check['status']}` | "
            f"`{check['severity']}` | {detail.replace('|', '\\|')} |"
        )
    lines.extend(["", "## Boundary", "", audit["boundary"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def build_progent_official_source_smoke(
    *,
    checkout: Path = DEFAULT_CHECKOUT,
    registry_path: Path = DEFAULT_REGISTRY,
    output_dir: Path = DEFAULT_OUTPUT,
    python_executable: Path | None = None,
) -> dict[str, Any]:
    checkout = checkout.resolve()
    registry_path = registry_path.resolve()
    output_dir = output_dir.resolve()
    python_executable = (python_executable or Path(sys.executable)).resolve()
    registry = _read_json(registry_path)
    repository_reference = _repository_reference(registry)
    actual_commit = _git_head(checkout)
    required_paths = {
        relative: (checkout / relative).exists() for relative in REQUIRED_PATHS
    }
    runtime = _runtime_smoke(checkout, python_executable)
    license_candidates = [
        checkout / "LICENSE",
        checkout / "LICENSE.txt",
        checkout / "COPYING",
    ]
    top_level_license_present = any(path.exists() for path in license_candidates)
    checks = [
        _check("checkout_exists", checkout.exists(), detail=_path(checkout)),
        _check(
            "checkout_matches_expected_commit",
            actual_commit == EXPECTED_COMMIT,
            detail={"expected": EXPECTED_COMMIT, "actual": actual_commit},
        ),
        _check(
            "registry_repository_matches_expected",
            repository_reference.get("url") == EXPECTED_REPOSITORY
            and repository_reference.get("remote_head_sha") == EXPECTED_COMMIT,
            detail=repository_reference,
        ),
        _check(
            "required_source_paths_present",
            all(required_paths.values()),
            detail=required_paths,
        ),
        _check(
            "offline_runtime_smoke_passed",
            bool(runtime.get("passed")),
            detail=runtime.get("observed"),
        ),
        _check(
            "top_level_license_present",
            top_level_license_present,
            severity="warning",
            detail=[_path(path) for path in license_candidates],
        ),
        _check(
            "source_smoke_not_formal_effect_evidence",
            True,
            severity="warning",
            detail=False,
        ),
    ]
    error_failures = [
        row
        for row in checks
        if row["status"] == "fail" and row["severity"] == "error"
    ]
    audit = {
        "schema_version": "paper-progent-official-source-smoke-1.0",
        "audit_version": AUDIT_VERSION,
        "status": "completed_source_smoke_only" if not error_failures else "failed",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "registry_path": _path(registry_path),
        "registry_sha256": sha256_file(registry_path),
        "source_checkout": {
            "path": _path(checkout),
            "repository": EXPECTED_REPOSITORY,
            "expected_commit": EXPECTED_COMMIT,
            "actual_commit": actual_commit,
            "matches_expected_commit": actual_commit == EXPECTED_COMMIT,
            "required_paths": required_paths,
            "top_level_license_present": top_level_license_present,
        },
        "offline_runtime_smoke": runtime,
        "network_calls_performed": False,
        "checks": checks,
        "checks_sha256": rows_sha256(checks),
        "passed_checks": sum(row["status"] == "pass" for row in checks),
        "total_checks": len(checks),
        "error_failures": error_failures,
        "result_eligible_for_formal_tables": False,
        "boundary": (
            "Official-source and offline deterministic-runtime qualification only. "
            "It does not validate policy-generation quality, execute AgentDojo, "
            "measure ASR or utility, or admit Progent into formal result tables."
        ),
    }
    audit = portable_value(audit, root=ROOT)
    audit["checks_sha256"] = rows_sha256(audit["checks"])
    json_path = output_dir / f"{AUDIT_STEM}.json"
    markdown_path = output_dir / f"{AUDIT_STEM}.md"
    _write_json(json_path, audit)
    _write_markdown(markdown_path, audit)
    audit["json_path"] = _path(json_path)
    audit["markdown_path"] = _path(markdown_path)
    return audit


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", type=Path, default=DEFAULT_CHECKOUT)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--python-executable", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    audit = build_progent_official_source_smoke(
        checkout=args.checkout,
        registry_path=args.registry,
        output_dir=args.output_dir,
        python_executable=args.python_executable,
    )
    print(json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
