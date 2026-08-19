"""Qualify a process-scoped Git safe-directory remediation for AgentDojo.

The qualification records one sanitized observation of the sandbox ownership
rejection and proves that an exact, child-process-only ``safe.directory``
entry can read the frozen AgentDojo commit.  It never writes Git configuration,
does not access provider credentials, and does not authorize network execution.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Mapping

from experiments.paper_v2.contracts import canonical_json_bytes, sha256_canonical_json


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CHECKOUT = PROJECT_ROOT / "external/benchmarks/agentdojo"
QUALIFICATION_PATH = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/sandbox_git_safe_directory_qualification_v1.json"
)
EXPECTED_COMMIT = "089ed468cf3ed0322acc66b0211f26d9d90dbf60"
SCHEMA_VERSION = "m3-paper-v2-sandbox-git-safe-directory-qualification-1.0"
QUALIFIED_AT = "2026-08-05T00:00:00+08:00"


class SandboxGitSafeDirectoryQualificationV1Error(ValueError):
    """Raised when the Git compatibility evidence is invalid or drifts."""


def _git_environment(*, safe_directory: bool) -> dict[str, str]:
    environment = dict(os.environ)
    for name in tuple(environment):
        if name == "GIT_CONFIG_COUNT" or name.startswith("GIT_CONFIG_KEY_") or name.startswith(
            "GIT_CONFIG_VALUE_"
        ):
            environment.pop(name, None)
    if safe_directory:
        environment.update(
            {
                "GIT_CONFIG_COUNT": "1",
                "GIT_CONFIG_KEY_0": "safe.directory",
                "GIT_CONFIG_VALUE_0": CHECKOUT.resolve().as_posix(),
            }
        )
    return environment


def _run_git(*, safe_directory: bool) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", "-C", str(CHECKOUT), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        env=_git_environment(safe_directory=safe_directory),
    )


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SandboxGitSafeDirectoryQualificationV1Error(
            f"{path}: invalid qualification JSON"
        ) from exc
    if not isinstance(value, dict):
        raise SandboxGitSafeDirectoryQualificationV1Error(
            f"{path}: expected qualification object"
        )
    return value


def _safe_probe() -> dict[str, Any]:
    result = _run_git(safe_directory=True)
    head = result.stdout.decode("ascii", errors="replace").strip()
    if result.returncode != 0 or head != EXPECTED_COMMIT:
        raise SandboxGitSafeDirectoryQualificationV1Error(
            "process-scoped safe.directory qualification failed"
        )
    return {
        "exit_code": result.returncode,
        "observed_commit": head,
        "stdout_sha256": hashlib.sha256(result.stdout).hexdigest(),
        "stderr_sha256": hashlib.sha256(result.stderr).hexdigest(),
        "stderr_bytes": len(result.stderr),
    }


def build_qualification() -> dict[str, Any]:
    unsafe = _run_git(safe_directory=False)
    unsafe_stderr = unsafe.stderr.decode("utf-8", errors="replace")
    if unsafe.returncode == 0 or "dubious ownership" not in unsafe_stderr.lower():
        raise SandboxGitSafeDirectoryQualificationV1Error(
            "expected sandbox Git ownership rejection was not observed"
        )
    safe = _safe_probe()
    core = {
        "schema_version": SCHEMA_VERSION,
        "artifact_role": "sanitized_process_scoped_git_compatibility_qualification",
        "qualified_at": QUALIFIED_AT,
        "status": "qualified_process_scoped_safe_directory",
        "checkout": CHECKOUT.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix(),
        "expected_commit": EXPECTED_COMMIT,
        "unsafe_observation": {
            "exit_code": unsafe.returncode,
            "stderr_sha256": hashlib.sha256(unsafe.stderr).hexdigest(),
            "stderr_bytes": len(unsafe.stderr),
            "dubious_ownership_marker_present": True,
            "owner_identity_redacted": True,
            "raw_stderr_persisted": False,
        },
        "safe_observation": safe,
        "remediation": {
            "scope": "process_only",
            "git_config_count": 1,
            "git_config_key_0": "safe.directory",
            "git_config_value_0": CHECKOUT.resolve().as_posix(),
            "global_git_config_mutated": False,
            "repository_git_config_mutated": False,
        },
        "evidence_boundary": {
            "credentials_read": False,
            "provider_calls": 0,
            "network_calls": 0,
            "provider_execution_authorized": False,
            "scientific_results_authorized": False,
        },
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def validate_qualification(value: Mapping[str, Any]) -> dict[str, Any]:
    candidate = dict(value)
    manifest = candidate.pop("manifest_sha256", None)
    if manifest != sha256_canonical_json(candidate):
        raise SandboxGitSafeDirectoryQualificationV1Error(
            "qualification manifest drift"
        )
    unsafe = candidate.get("unsafe_observation")
    remediation = candidate.get("remediation")
    boundary = candidate.get("evidence_boundary")
    if (
        candidate.get("schema_version") != SCHEMA_VERSION
        or candidate.get("status") != "qualified_process_scoped_safe_directory"
        or candidate.get("expected_commit") != EXPECTED_COMMIT
        or candidate.get("checkout")
        != CHECKOUT.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
        or not isinstance(unsafe, Mapping)
        or unsafe.get("exit_code") == 0
        or unsafe.get("dubious_ownership_marker_present") is not True
        or unsafe.get("owner_identity_redacted") is not True
        or unsafe.get("raw_stderr_persisted") is not False
        or not isinstance(remediation, Mapping)
        or remediation.get("scope") != "process_only"
        or remediation.get("global_git_config_mutated") is not False
        or remediation.get("repository_git_config_mutated") is not False
        or not isinstance(boundary, Mapping)
        or boundary.get("provider_calls") != 0
        or boundary.get("network_calls") != 0
        or boundary.get("provider_execution_authorized") is not False
    ):
        raise SandboxGitSafeDirectoryQualificationV1Error(
            "qualification contract drift"
        )
    safe = _safe_probe()
    if candidate.get("safe_observation") != safe:
        raise SandboxGitSafeDirectoryQualificationV1Error(
            "process-scoped safe-directory probe drift"
        )
    return dict(value)


def write_qualification() -> dict[str, Any]:
    value = build_qualification()
    QUALIFICATION_PATH.parent.mkdir(parents=True, exist_ok=True)
    QUALIFICATION_PATH.write_bytes(canonical_json_bytes(value) + b"\n")
    return value


def verify_qualification() -> dict[str, Any]:
    if not QUALIFICATION_PATH.is_file():
        raise SandboxGitSafeDirectoryQualificationV1Error(
            "Git safe-directory qualification artifact missing"
        )
    return validate_qualification(_read_json(QUALIFICATION_PATH))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write-qualification", action="store_true")
    action.add_argument("--verify-qualification", action="store_true")
    args = parser.parse_args()
    value = write_qualification() if args.write_qualification else verify_qualification()
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
