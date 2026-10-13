"""原子性、便于审计的实验清册（Manifest）与运行环境快照管理器。

记录实验启动时的操作系统、硬件平台、Python 依赖版本与 Git 提交哈希。
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .catalog import EXPERIMENT_BY_ID


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_SCHEMA_VERSION = "2.0"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_paths(paths: Iterable[str | Path]) -> str:
    """以确定性的仓库相对顺序对路径标签和字节计算哈希。"""

    digest = hashlib.sha256()
    normalized = sorted(Path(path).resolve() for path in paths)
    for path in normalized:
        try:
            label = path.relative_to(REPO_ROOT.resolve()).as_posix()
        except ValueError:
            label = path.name
        digest.update(label.encode("utf-8"))
        digest.update(b"\0")
        digest.update(bytes.fromhex(sha256_file(path)))
    return digest.hexdigest()


def command_output(command: list[str], *, timeout: float = 10.0) -> str:
    try:
        completed = subprocess.run(
            command,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return f"unavailable: {type(exc).__name__}"
    output = (completed.stdout or completed.stderr).strip()
    return output if output else f"exit={completed.returncode}"


def git_state() -> dict[str, Any]:
    commit = command_output(["git", "rev-parse", "HEAD"])
    branch = command_output(["git", "branch", "--show-current"])
    status = command_output(["git", "status", "--porcelain=v1"])
    return {
        "commit": commit,
        "branch": branch,
        "dirty": bool(status and not status.startswith("exit=")),
        "status_sha256": hashlib.sha256(status.encode("utf-8")).hexdigest(),
    }


def environment_snapshot() -> dict[str, Any]:
    ollama = shutil.which("ollama")
    if not ollama:
        candidate = Path(r"D:\Ollama\app\ollama.exe")
        ollama = str(candidate) if candidate.exists() else "ollama"
    return {
        "captured_at": utc_now(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "ollama_version": command_output([ollama, "--version"]),
        "ollama_models": command_output([ollama, "list"], timeout=30.0),
        "gpu": command_output(
            [
                "nvidia-smi",
                "--query-gpu=name,driver_version,memory.total,memory.free",
                "--format=csv,noheader,nounits",
            ]
        ),
    }


def new_manifest(
    experiment_id: str,
    *,
    dataset_paths: Iterable[str | Path],
    configuration: dict[str, Any],
    expected_runs: int | None,
    models: Iterable[str] = (),
    command: list[str] | None = None,
) -> dict[str, Any]:
    definition = EXPERIMENT_BY_ID[experiment_id]
    paths = [Path(path) for path in dataset_paths]
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError(f"manifest dataset path(s) missing: {missing}")
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "experiment_id": definition.id,
        "experiment_name": definition.name,
        "question": definition.question,
        "status": "running",
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "completed_at": None,
        "git": git_state(),
        "dataset": {
            "paths": [_display_path(path) for path in paths],
            "sha256": sha256_paths(paths),
        },
        "models": list(models),
        "configuration": configuration,
        "command": list(command or []),
        "environment": environment_snapshot(),
        "progress": {
            "expected_runs": expected_runs,
            "completed_runs": 0,
            "failed_jobs": 0,
            "unresolved_cases": 0,
        },
        "artifacts": [],
        "events": [{"at": utc_now(), "type": "started", "message": "experiment started"}],
        "failure": None,
    }


def save_manifest(payload: dict[str, Any], path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload["updated_at"] = utc_now()
    handle, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
        os.replace(temp_name, target)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def record_event(payload: dict[str, Any], event_type: str, message: str, **details: Any) -> None:
    event = {"at": utc_now(), "type": event_type, "message": message}
    if details:
        event["details"] = details
    payload.setdefault("events", []).append(event)


def register_artifact(payload: dict[str, Any], path: str | Path, *, kind: str) -> None:
    artifact_path = Path(path)
    if not artifact_path.exists() or not artifact_path.is_file():
        raise FileNotFoundError(artifact_path)
    entry = {
        "path": _display_path(artifact_path),
        "kind": kind,
        "bytes": artifact_path.stat().st_size,
        "sha256": sha256_file(artifact_path),
    }
    artifacts = payload.setdefault("artifacts", [])
    artifacts[:] = [item for item in artifacts if item.get("path") != entry["path"]]
    artifacts.append(entry)


def finish_manifest(
    payload: dict[str, Any],
    *,
    completed_runs: int,
    failed_jobs: int = 0,
    unresolved_cases: int = 0,
) -> None:
    expected = payload.get("progress", {}).get("expected_runs")
    if expected is not None and completed_runs != int(expected):
        raise ValueError(f"completed_runs={completed_runs} does not match expected_runs={expected}")
    if failed_jobs:
        raise ValueError("a completed experiment manifest cannot contain failed jobs")
    payload["progress"] = {
        "expected_runs": expected,
        "completed_runs": completed_runs,
        "failed_jobs": failed_jobs,
        "unresolved_cases": unresolved_cases,
    }
    payload["status"] = "completed"
    payload["completed_at"] = utc_now()
    payload["failure"] = None
    record_event(payload, "completed", "experiment completed", completed_runs=completed_runs)


def fail_manifest(payload: dict[str, Any], *, category: str, message: str) -> None:
    payload["status"] = "failed"
    payload["failure"] = {"category": category, "message": message, "at": utc_now()}
    record_event(payload, "failed", message, category=category)


def validate_completed_manifest(payload: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    if payload.get("status") != "completed":
        problems.append(f"manifest status is {payload.get('status')!r}")
    progress = payload.get("progress", {})
    expected = progress.get("expected_runs")
    completed = progress.get("completed_runs")
    if expected is not None and completed != expected:
        problems.append(f"run count mismatch: completed={completed}, expected={expected}")
    if progress.get("failed_jobs"):
        problems.append(f"failed_jobs={progress.get('failed_jobs')}")
    if not payload.get("git", {}).get("commit"):
        problems.append("missing Git commit")
    if not payload.get("dataset", {}).get("sha256"):
        problems.append("missing dataset hash")
    return problems


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.name
