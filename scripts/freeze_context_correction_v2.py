"""Create the Context Correction V2 execution-r3 freeze after both smoke gates pass."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.context_correction_runtime import (  # noqa: E402
    EXPECTED_FREEZE_PATHS,
    verify_freeze,
)
from experiments.manifest import sha256_file  # noqa: E402


PROTOCOL_ID = "CONTEXT_CORRECTION_V2"
WORKLOAD_REVISION = "r2"
EXECUTION_REVISION = "r3"
DEFAULT_OUTPUT = ROOT / "protocols" / "context_correction_v2" / "freeze_r3.json"
DEFAULT_PROMPT_PROOF = (
    ROOT / "protocols" / "context_correction_v2" / "prompt_verification_r2.json"
)
DEFAULT_E9_SMOKE = (
    ROOT
    / "outputs"
    / "experiments"
    / "E9_context_correction_v2_r3_smoke"
    / "manifest.json"
)
DEFAULT_E14_SMOKE = (
    ROOT
    / "outputs"
    / "experiments"
    / "E14_context_correction_v2_r3_smoke"
    / "manifest.json"
)
FORMAL_MANIFESTS = (
    ROOT / "outputs" / "experiments" / "E9_context_correction_v2_r3" / "manifest.json",
    ROOT / "outputs" / "experiments" / "E14_context_correction_v2_r3" / "manifest.json",
)
TEST_FILES = (
    "tests/unit/test_context_workloads.py",
    "tests/unit/test_context_correction_runtime.py",
    "tests/unit/test_e9_context_correction.py",
    "tests/unit/test_e14_context_correction.py",
    "tests/unit/test_core_runtime.py",
    "tests/unit/test_core_batch.py",
    "tests/unit/test_run_sandbox_isolation.py",
)


class FreezeError(RuntimeError):
    """Raised when a pre-freeze admission gate fails."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def _read_object(path: Path, *, label: str) -> dict[str, Any]:
    if not path.is_file() or path.stat().st_size <= 0:
        raise FreezeError(f"{label} is missing or empty: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise FreezeError(f"invalid {label}: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise FreezeError(f"{label} must be a JSON object: {path}")
    return value


def _file_record(path: Path, *, kind: str | None = None) -> dict[str, Any]:
    record: dict[str, Any] = {
        "path": _relative(path),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }
    if kind:
        record["kind"] = kind
    return record


def _validate_prompt_proof(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    proof = _read_object(path, label="r2 prompt verification")
    observations = proof.get("observations")
    checks = proof.get("checks")
    if (
        proof.get("protocol_id") != PROTOCOL_ID
        or proof.get("workload_revision") != WORKLOAD_REVISION
        or proof.get("status") != "pass"
        or not isinstance(observations, list)
        or len(observations) != 100
        or len({str(row.get("case_id", "")) for row in observations}) != 100
        or not isinstance(checks, Mapping)
        or not checks
        or not all(value is True for value in checks.values())
    ):
        raise FreezeError("r2 prompt verification failed its 100-case semantic gate")
    for experiment_id, expected_name in (
        ("E9", "e9_cases.jsonl"),
        ("E14", "e14_cases_r2.jsonl"),
    ):
        record = (proof.get("fixture_files") or {}).get(experiment_id) or {}
        fixture = Path(str(record.get("path", "")))
        if not fixture.is_absolute():
            fixture = ROOT / fixture
        if (
            fixture.name != expected_name
            or not fixture.is_file()
            or record.get("sha256") != sha256_file(fixture)
        ):
            raise FreezeError(f"prompt proof fixture binding failed for {experiment_id}")
    record = {
        **_file_record(path, kind="prompt_workload_verification"),
        "status": "pass",
        "workload_revision": WORKLOAD_REVISION,
        "case_count": 100,
        "target_medians": proof.get("target_medians"),
        "checks": dict(checks),
    }
    return proof, record


def _validate_smoke(path: Path, experiment_id: str) -> dict[str, Any]:
    manifest = _read_object(path, label=f"{experiment_id} r2 smoke manifest")
    validity = manifest.get("validity_checks") or {}
    expected = 48
    progress = manifest.get("progress") or {}
    jobs = manifest.get("jobs") or []
    if (
        manifest.get("experiment_id") != experiment_id
        or manifest.get("protocol_id") != PROTOCOL_ID
        or manifest.get("workload_revision") != WORKLOAD_REVISION
        or manifest.get("status") != "completed"
        or validity.get("status") != "pass"
        or int(progress.get("expected_runs", -1)) != expected
        or int(progress.get("completed_runs", -1)) != expected
        or int(progress.get("failed_jobs", -1)) != 0
        or len(jobs) != 8
        or any(job.get("status") != "completed" for job in jobs)
    ):
        raise FreezeError(f"{experiment_id} r2 smoke did not pass the exact 48-run gate")
    if experiment_id == "E14":
        matched = validity.get("matched_path") or {}
        if (
            matched.get("status") != "pass"
            or int(matched.get("expected_pairs", -1)) != 16
            or int(matched.get("observed_pairs", -1)) != 16
            or int(matched.get("valid_pairs", -1)) != 16
            or int(matched.get("failure_count", -1)) != 0
        ):
            raise FreezeError("E14 r2 smoke did not pass all 16 matched-path pairs")
    return {
        "experiment_id": experiment_id,
        "manifest_path": _relative(path),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "status": "pass",
        "expected_case_runs": expected,
        "observed_case_runs": expected,
        "validity_status": "pass",
    }


def _run_test_gate() -> dict[str, Any]:
    command = [sys.executable, "-m", "pytest", "-q", *TEST_FILES]
    process = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    output = (process.stdout + "\n" + process.stderr).strip()
    match = re.search(r"(\d+) passed", output)
    passed = int(match.group(1)) if match else 0
    if process.returncode != 0 or passed < 1:
        raise FreezeError(f"context correction test gate failed ({process.returncode}): {output}")
    return {
        "status": "pass",
        "command": command,
        "returncode": process.returncode,
        "passed": passed,
        "output_sha256": hashlib.sha256(output.encode("utf-8")).hexdigest(),
        "output_tail": output[-2000:],
    }


def _command_output(command: Sequence[str]) -> str:
    process = subprocess.run(
        list(command),
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if process.returncode != 0:
        raise FreezeError(f"command failed: {command}: {process.stderr.strip()}")
    return process.stdout.strip() or process.stderr.strip()


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def build_freeze(
    *,
    output_path: str | Path = DEFAULT_OUTPUT,
    prompt_proof_path: str | Path = DEFAULT_PROMPT_PROOF,
    e9_smoke_path: str | Path = DEFAULT_E9_SMOKE,
    e14_smoke_path: str | Path = DEFAULT_E14_SMOKE,
) -> dict[str, Any]:
    """Validate all preconditions, write one freeze, and immediately reverify it."""

    output = Path(output_path).resolve()
    if output.exists():
        raise FreezeError(f"refusing to overwrite an existing freeze: {output}")
    existing_formal = [path for path in FORMAL_MANIFESTS if path.exists()]
    if existing_formal:
        raise FreezeError(
            "refusing to freeze after formal execution exists: "
            + ", ".join(str(path) for path in existing_formal)
        )
    proof, prompt_record = _validate_prompt_proof(Path(prompt_proof_path).resolve())
    smoke_evidence = {
        "E9": _validate_smoke(Path(e9_smoke_path).resolve(), "E9"),
        "E14": _validate_smoke(Path(e14_smoke_path).resolve(), "E14"),
    }
    test_gate = _run_test_gate()
    files = []
    for relative in EXPECTED_FREEZE_PATHS:
        path = ROOT / relative
        if not path.is_file() or path.stat().st_size <= 0:
            raise FreezeError(f"freeze allowlist file is missing or empty: {relative}")
        files.append(_file_record(path))

    model_profiles: dict[str, Any] = {}
    for target, record in sorted((proof.get("model_evidence") or {}).items()):
        resident_models = ((record.get("resident_snapshot") or {}).get("models") or [])
        resident = resident_models[0] if len(resident_models) == 1 else {}
        model_profiles[str(target)] = {
            "served_model": record.get("served_model"),
            "alias_id": record.get("installed_alias_id"),
            "alias_digest": resident.get("digest"),
            "effective_context_window_tokens": record.get(
                "expected_effective_context_window_tokens"
            ),
            "resident_context_window_tokens": resident.get("context_length"),
        }
    git_status = _command_output(("git", "status", "--porcelain=v1", "--untracked-files=all"))
    payload = {
        "schema_version": "2.0",
        "protocol_id": PROTOCOL_ID,
        "workload_revision": WORKLOAD_REVISION,
        "execution_revision": EXECUTION_REVISION,
        "status": "pass",
        "freeze_complete": True,
        "created_at": _utc_now(),
        "formal_execution_started": False,
        "mutation_policy": "any frozen-file change requires a new revision and full affected rerun",
        "files": files,
        "prompt_verification": prompt_record,
        "smoke_evidence": smoke_evidence,
        "model_profiles": model_profiles,
        "test_gate": test_gate,
        "environment": {
            "python": sys.version,
            "ollama_version": _command_output(("ollama", "--version")),
            "git_head": _command_output(("git", "rev-parse", "HEAD")),
            "git_branch": _command_output(("git", "branch", "--show-current")),
            "git_status_sha256": hashlib.sha256(git_status.encode("utf-8")).hexdigest(),
            "dirty_worktree": bool(git_status),
        },
        "old_v3_policy": "preserved_invalid_diagnostic_provenance_excluded_from_v2_denominators",
        "pre_r3_evidence_policy": "preserve failed r2 formal evidence as diagnostic provenance; never resume or pool it",
    }
    _atomic_write_json(output, payload)
    try:
        verified = verify_freeze(output)
    except Exception:
        failed = output.with_name(
            f"{output.stem}.invalid-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}{output.suffix}"
        )
        os.replace(output, failed)
        raise
    return {
        "status": "pass",
        "freeze": _relative(output),
        "bytes": output.stat().st_size,
        "sha256": sha256_file(output),
        "file_count": len(files),
        "test_gate": test_gate,
        "verified_protocol_id": verified["protocol_id"],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--prompt-proof", type=Path, default=DEFAULT_PROMPT_PROOF)
    parser.add_argument("--e9-smoke", type=Path, default=DEFAULT_E9_SMOKE)
    parser.add_argument("--e14-smoke", type=Path, default=DEFAULT_E14_SMOKE)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = build_freeze(
        output_path=args.output,
        prompt_proof_path=args.prompt_proof,
        e9_smoke_path=args.e9_smoke,
        e14_smoke_path=args.e14_smoke,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
