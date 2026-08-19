"""Audit the pinned official CaMeL source with an offline policy smoke.

This audit is a source/dependency qualification only. It imports CaMeL from the
pinned checkout, isolates AgentDojo type-only imports, and exercises the
official capability and security-policy semantics on deterministic values.

It does not run the CaMeL interpreter, call an LLM/API, execute AgentDojo cases,
or create formal effect evidence.
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
DEFAULT_CHECKOUT = ROOT / "external" / "baselines" / "camel-prompt-injection"
DEFAULT_PREFLIGHT = ROOT / "protocols" / "paper_upgrade_v1" / "camel_fides_ifc_adapter_preflight_v1.json"
DEFAULT_REGISTRY = ROOT / "protocols" / "paper_upgrade_v1" / "external_strong_baselines_v1.json"
DEFAULT_OUTPUT = ROOT / "protocols" / "paper_upgrade_v1"
EXPECTED_REPOSITORY = "https://github.com/google-research/camel-prompt-injection"
EXPECTED_COMMIT = "f083b6b396399d3b3c7f2ddaf613a5945eaf32d8"
AUDIT_STEM = "camel_official_source_smoke_v1"
AUDIT_VERSION = "m3-paper-v1-camel-official-source-smoke-1.0"

REQUIRED_PATHS = (
    "README.md",
    "LICENSE",
    "pyproject.toml",
    "src/camel/__init__.py",
    "src/camel/security_policy.py",
    "src/camel/capabilities/capabilities.py",
    "src/camel/capabilities/readers.py",
    "src/camel/capabilities/sources.py",
    "src/camel/capabilities/utils.py",
    "src/camel/interpreter/value.py",
    "src/camel/pipeline_elements/security_policies/agentdojo_security_policies.py",
    "src/camel/pipeline_elements/security_policies/workspace.py",
    "src/camel/pipeline_elements/security_policies/slack.py",
    "src/camel/pipeline_elements/security_policies/travel.py",
    "src/camel/pipeline_elements/security_policies/banking.py",
)
SOURCE_MARKERS = {
    "capability_metadata": (
        "class Capabilities",
        "sources_set",
        "readers_set",
    ),
    "trust_and_reader_checks": (
        "def is_trusted",
        "def can_readers_read_value",
        "def get_all_readers",
    ),
    "security_policy_engine": (
        "class SecurityPolicyEngine",
        "def base_security_policy",
        "Defaulting to denial",
    ),
    "workspace_policy": (
        "class WorkspaceSecurityPolicyEngine",
        "def send_email_policy",
        "can_readers_read_value",
    ),
    "slack_policy": (
        "class SlackSecurityPolicyEngine",
        "def send_direct_message_policy",
        "def send_channel_message_policy",
    ),
}


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
    rows = registry.get("entries", [])
    if not isinstance(rows, list):
        return {}
    entry = next(
        (
            row
            for row in rows
            if isinstance(row, Mapping) and row.get("id") == "camel_google_research"
        ),
        {},
    )
    refs = entry.get("secondary_references", [])
    if not isinstance(refs, list):
        return {}
    return dict(
        next(
            (
                row
                for row in refs
                if isinstance(row, Mapping) and row.get("kind") == "repository"
            ),
            {},
        )
    )


def _source_profiles(checkout: Path) -> dict[str, dict[str, Any]]:
    profiles: dict[str, dict[str, Any]] = {}
    for relative in REQUIRED_PATHS:
        path = checkout / relative
        text = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
        profiles[relative] = {
            "relative_path": relative,
            "path": _path(path),
            "exists": path.exists(),
            "sha256": sha256_file(path) if path.exists() else "",
            "line_count": text.count("\n") + (1 if text else 0),
        }
    return profiles


def _marker_scan(checkout: Path) -> dict[str, dict[str, Any]]:
    text_by_relative = {
        relative: (checkout / relative).read_text(encoding="utf-8", errors="replace")
        for relative in REQUIRED_PATHS
        if (checkout / relative).exists()
    }
    joined = "\n".join(text_by_relative.values())
    results: dict[str, dict[str, Any]] = {}
    for name, markers in SOURCE_MARKERS.items():
        missing = [marker for marker in markers if marker not in joined]
        results[name] = {
            "markers": list(markers),
            "missing_markers": missing,
            "passed": not missing,
        }
    return results


def _check(name: str, passed: bool, *, severity: str = "error", detail: Any = None) -> dict[str, Any]:
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
import types
from pathlib import Path

checkout = Path(sys.argv[1])
sys.path.insert(0, str(checkout / "src"))

def blocked_connect(*args, **kwargs):
    raise RuntimeError("network disabled by CaMeL source-smoke harness")

socket.socket.connect = blocked_connect

def stub(name, **attrs):
    mod = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(mod, key, value)
    sys.modules[name] = mod
    return mod

class TaskEnvironment: ...
class WorkspaceEnvironment: ...
class TravelEnvironment: ...
class SlackEnvironment: ...
class BankingEnvironment: ...

for name in [
    "agentdojo",
    "agentdojo.default_suites",
    "agentdojo.default_suites.v1",
    "agentdojo.default_suites.v1.workspace",
    "agentdojo.default_suites.v1.travel",
    "agentdojo.default_suites.v1.slack",
    "agentdojo.default_suites.v1.banking",
]:
    stub(name)
stub("agentdojo.functions_runtime", TaskEnvironment=TaskEnvironment)
stub("agentdojo.default_suites.v1.workspace.task_suite", WorkspaceEnvironment=WorkspaceEnvironment)
stub("agentdojo.default_suites.v1.travel.task_suite", TravelEnvironment=TravelEnvironment)
stub("agentdojo.default_suites.v1.slack.task_suite", SlackEnvironment=SlackEnvironment)
stub("agentdojo.default_suites.v1.banking.task_suite", BankingEnvironment=BankingEnvironment)

from camel.capabilities import Capabilities, is_trusted, readers, sources
from camel.interpreter.value import CaMeLList, CaMeLStr
from camel.security_policy import base_security_policy
from camel.pipeline_elements.security_policies.workspace import WorkspaceSecurityPolicyEngine
from camel.pipeline_elements.security_policies.slack import SlackSecurityPolicyEngine

def value(text, metadata):
    return CaMeLStr.from_raw(text, metadata, ())

def value_list(items, metadata):
    return CaMeLList([value(item, metadata) for item in items], metadata, ())

trusted = Capabilities.default()
untrusted_public = Capabilities(frozenset({sources.Tool("external_email", frozenset({"outside"}))}), readers.Public())
private_alice = Capabilities(frozenset({sources.Tool("external_email", frozenset({"outside"}))}), frozenset({"alice@example.com"}))
private_channel = Capabilities(frozenset({sources.Tool("external_slack", frozenset({"outside"}))}), frozenset({"alice", "bob"}))

workspace = WorkspaceSecurityPolicyEngine(object())

class SlackObj:
    user_channels = {"alice": ["project"], "bob": ["project"], "eve": ["other"]}

class SlackEnv:
    slack = SlackObj()

slack = SlackSecurityPolicyEngine(SlackEnv())

observed = {
    "trusted_user_value_is_trusted": is_trusted(value("alice@example.com", trusted)),
    "untrusted_tool_value_is_not_trusted": not is_trusted(value("alice@example.com", untrusted_public)),
    "base_policy_denies_private_side_effect": type(base_security_policy("send_email", {"body": value("secret", private_alice)}, set())).__name__,
    "base_policy_allows_private_no_side_effect": type(base_security_policy("query_ai_assistant", {"body": value("secret", private_alice)}, {"query_ai_assistant"})).__name__,
    "workspace_allows_trusted_recipient": type(workspace.send_email_policy("send_email", {
        "recipients": value_list(["eve@example.com"], trusted),
        "body": value("secret", private_alice),
        "subject": value("secret", private_alice),
    })).__name__,
    "workspace_allows_authorized_reader": type(workspace.send_email_policy("send_email", {
        "recipients": value_list(["alice@example.com"], untrusted_public),
        "body": value("secret", private_alice),
        "subject": value("secret", private_alice),
    })).__name__,
    "workspace_denies_reader_mismatch": type(workspace.send_email_policy("send_email", {
        "recipients": value_list(["eve@example.com"], untrusted_public),
        "body": value("secret", private_alice),
        "subject": value("secret", private_alice),
    })).__name__,
    "slack_allows_trusted_direct_recipient": type(slack.send_direct_message_policy("send_direct_message", {
        "recipient": value("eve", trusted),
        "body": value("secret", private_channel),
    })).__name__,
    "slack_denies_reader_mismatch": type(slack.send_direct_message_policy("send_direct_message", {
        "recipient": value("eve", untrusted_public),
        "body": value("secret", private_channel),
    })).__name__,
    "slack_allows_channel_members": type(slack.send_channel_message_policy("send_channel_message", {
        "channel": value("project", untrusted_public),
        "body": value("secret", private_channel),
    })).__name__,
    "network_guard_active": True,
}
print(json.dumps(observed, ensure_ascii=False, sort_keys=True))
'''
    env = dict(os.environ)
    env["PYTHONPATH"] = str(checkout / "src")
    result = subprocess.run(
        [str(python_executable), "-c", source, str(checkout)],
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
        env=env,
    )
    observed: dict[str, Any] = {}
    if result.returncode == 0:
        stdout_lines = [line for line in result.stdout.splitlines() if line.strip()]
        if stdout_lines:
            try:
                candidate = json.loads(stdout_lines[-1])
                if isinstance(candidate, dict):
                    observed = candidate
            except json.JSONDecodeError:
                observed = {}
    expected = {
        "trusted_user_value_is_trusted": True,
        "untrusted_tool_value_is_not_trusted": True,
        "base_policy_denies_private_side_effect": "Denied",
        "base_policy_allows_private_no_side_effect": "Allowed",
        "workspace_allows_trusted_recipient": "Allowed",
        "workspace_allows_authorized_reader": "Allowed",
        "workspace_denies_reader_mismatch": "Denied",
        "slack_allows_trusted_direct_recipient": "Allowed",
        "slack_denies_reader_mismatch": "Denied",
        "slack_allows_channel_members": "Allowed",
        "network_guard_active": True,
    }
    return {
        "passed": result.returncode == 0 and observed == expected,
        "returncode": result.returncode,
        "python_executable": str(python_executable),
        "observed": observed,
        "expected": expected,
        "stdout_tail": result.stdout[-2000:],
        "stderr_tail": result.stderr[-4000:],
        "agentdojo_import_isolation": {
            "used": True,
            "reason": "CaMeL policy modules import AgentDojo environment type names; local AgentDojo version triggers circular registration during direct import.",
            "algorithm_change": False,
        },
        "network_guard_active": True,
    }


def _write_markdown(path: Path, audit: Mapping[str, Any]) -> None:
    lines = [
        "# CaMeL official source smoke v1",
        "",
        f"Generated: {audit['created_at']}",
        "",
        "## Result",
        "",
        f"- Status: `{audit['status']}`",
        f"- Source commit: `{audit['source_checkout']['actual_commit']}`",
        f"- Offline policy smoke: `{audit['offline_policy_smoke']['passed']}`",
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
    lines.extend(["", "## Boundary", "", str(audit["boundary"]), ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def build_camel_official_source_smoke(
    *,
    checkout: Path = DEFAULT_CHECKOUT,
    preflight_path: Path = DEFAULT_PREFLIGHT,
    registry_path: Path = DEFAULT_REGISTRY,
    output_dir: Path = DEFAULT_OUTPUT,
    python_executable: Path | None = None,
) -> dict[str, Any]:
    checkout = checkout.resolve()
    preflight_path = preflight_path.resolve()
    registry_path = registry_path.resolve()
    output_dir = output_dir.resolve()
    python_executable = (python_executable or Path(sys.executable)).resolve()
    preflight = _read_json(preflight_path)
    registry = _read_json(registry_path)
    repository_reference = _repository_reference(registry)
    actual_commit = _git_head(checkout)
    source_profiles = _source_profiles(checkout)
    marker_groups = _marker_scan(checkout)
    runtime = _runtime_smoke(checkout, python_executable)
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
            "preflight_selects_camel_source",
            preflight.get("method_selected") is True
            and preflight.get("config", {}).get("selected_candidate") == "camel"
            and bool(preflight.get("source_checkout_ready")),
            detail={
                "status": preflight.get("status", ""),
                "selected_candidate": preflight.get("config", {}).get("selected_candidate", ""),
                "source_checkout_ready": preflight.get("source_checkout_ready"),
            },
        ),
        _check(
            "required_source_paths_present",
            all(profile["exists"] for profile in source_profiles.values()),
            detail={key: value["exists"] for key, value in source_profiles.items()},
        ),
        _check(
            "official_source_marker_groups_present",
            all(row["passed"] for row in marker_groups.values()),
            detail=marker_groups,
        ),
        _check(
            "offline_policy_smoke_passed",
            bool(runtime.get("passed")),
            detail=runtime.get("observed"),
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
        "schema_version": "paper-camel-official-source-smoke-1.0",
        "audit_version": AUDIT_VERSION,
        "status": "completed_source_smoke_only" if not error_failures else "failed",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "preflight_path": _path(preflight_path),
        "preflight_sha256": sha256_file(preflight_path),
        "registry_path": _path(registry_path),
        "registry_sha256": sha256_file(registry_path),
        "source_checkout": {
            "path": _path(checkout),
            "repository": EXPECTED_REPOSITORY,
            "expected_commit": EXPECTED_COMMIT,
            "actual_commit": actual_commit,
            "matches_expected_commit": actual_commit == EXPECTED_COMMIT,
            "required_paths": source_profiles,
        },
        "marker_groups": marker_groups,
        "offline_policy_smoke": runtime,
        "network_calls_performed": False,
        "checks": checks,
        "checks_sha256": rows_sha256(checks),
        "passed_checks": sum(row["status"] == "pass" for row in checks),
        "total_checks": len(checks),
        "error_failures": error_failures,
        "result_eligible_for_formal_tables": False,
        "boundary": (
            "Official-source and offline deterministic policy qualification only. "
            "It uses import isolation only for AgentDojo environment type names. "
            "It does not validate CaMeL interpreter generation, execute AgentDojo "
            "cases, measure ASR or utility, or admit CaMeL into formal tables."
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
    parser.add_argument("--preflight", type=Path, default=DEFAULT_PREFLIGHT)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--python-executable", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    audit = build_camel_official_source_smoke(
        checkout=args.checkout,
        preflight_path=args.preflight,
        registry_path=args.registry,
        output_dir=args.output_dir,
        python_executable=args.python_executable,
    )
    print(json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
