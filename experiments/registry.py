"""具备原子状态变迁能力的持久化实验注册表（Registry）。

集中管理所有实验单元（E0-E17）的当前生命周期状态（planned / in_progress / completed / verified）。
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = Path(__file__).with_name("registry.json")
ALLOWED_STATUSES = {"pending", "running", "completed", "failed"}
EXPERIMENT_IDS = tuple(f"E{index}" for index in range(18))
DEDICATED_COMPLETION_EXPERIMENTS = frozenset({"E9", "E14", "E17"})


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_registry(path: str | Path = REGISTRY_PATH) -> dict[str, Any]:
    registry_path = Path(path)
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    validate_registry_payload(payload)
    return payload


def validate_registry_payload(payload: dict[str, Any]) -> None:
    experiments = payload.get("experiments")
    if not isinstance(experiments, list):
        raise ValueError("registry experiments must be a list")
    ids = [str(item.get("id", "")) for item in experiments]
    if tuple(ids) != EXPERIMENT_IDS:
        raise ValueError(f"registry must contain ordered IDs {EXPERIMENT_IDS}, got {ids}")
    for item in experiments:
        status = str(item.get("status", ""))
        if status not in ALLOWED_STATUSES:
            raise ValueError(f"{item.get('id')}: invalid status {status!r}")
        required = item.get("required_artifacts")
        if not isinstance(required, list) or not required:
            raise ValueError(f"{item.get('id')}: required_artifacts must be non-empty")


def save_registry(payload: dict[str, Any], path: str | Path = REGISTRY_PATH) -> None:
    validate_registry_payload(payload)
    registry_path = Path(path)
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    payload["updated_at"] = utc_now()
    handle, temp_name = tempfile.mkstemp(
        prefix=f".{registry_path.name}.", suffix=".tmp", dir=registry_path.parent
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temp_name, registry_path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def set_status(
    experiment_id: str,
    status: str,
    *,
    error: str = "",
    evidence: list[str] | None = None,
    path: str | Path = REGISTRY_PATH,
) -> dict[str, Any]:
    if status == "completed":
        raise ValueError(
            "completed status cannot be set directly; use the experiment completion registrar"
        )
    if status not in ALLOWED_STATUSES:
        raise ValueError(f"invalid experiment status: {status}")
    return _set_status(
        experiment_id,
        status,
        error=error,
        evidence=evidence,
        path=path,
    )


def _set_status(
    experiment_id: str,
    status: str,
    *,
    error: str = "",
    evidence: list[str] | None = None,
    path: str | Path = REGISTRY_PATH,
) -> dict[str, Any]:
    """在其公开完成门禁通过后，持久化经验证的状态流转。"""

    payload = load_registry(path)
    for item in payload["experiments"]:
        if item["id"] != experiment_id:
            continue
        item["status"] = status
        item["updated_at"] = utc_now()
        item["error"] = error
        if evidence is not None:
            item["evidence"] = evidence
        if status == "running" and not item.get("started_at"):
            item["started_at"] = utc_now()
        if status == "completed":
            item["completed_at"] = utc_now()
        else:
            # A completed experiment can later be invalidated by a provenance
            # or integrity audit.  Its active record must not retain a stale
            # completion timestamp once the status is no longer completed.
            item.pop("completed_at", None)
        save_registry(payload, path)
        return item
    raise KeyError(experiment_id)


def resolve_artifact(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


def missing_artifacts(item: dict[str, Any]) -> list[str]:
    return [
        value
        for value in item.get("required_artifacts", [])
        if not resolve_artifact(str(value)).exists()
    ]


def invalid_artifacts(item: dict[str, Any]) -> list[str]:
    """返回缺失、为空或非常规文件的必选构件列表。"""

    invalid: list[str] = []
    for value in item.get("required_artifacts", []):
        path = resolve_artifact(str(value))
        if not path.exists() or not path.is_file() or path.stat().st_size == 0:
            invalid.append(str(value))
    return invalid


def complete_experiment(
    experiment_id: str,
    *,
    manifest_path: str | Path,
    evidence: list[str],
    path: str | Path = REGISTRY_PATH,
) -> dict[str, Any]:
    """仅在清单和每个声明的构件均通过后才标记为完成。"""

    from .manifest import validate_completed_manifest

    if experiment_id in DEDICATED_COMPLETION_EXPERIMENTS:
        raise ValueError(
            f"{experiment_id} requires a dedicated completion registrar; "
            "generic complete_experiment is not permitted"
        )

    manifest_file = Path(manifest_path)
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    problems = validate_completed_manifest(manifest)
    manifest_experiment_id = manifest.get("experiment_id")
    if manifest_experiment_id != experiment_id:
        problems.append(
            "manifest experiment_id mismatch: "
            f"expected {experiment_id!r}, got {manifest_experiment_id!r}"
        )
    payload = load_registry(path)
    item = next(entry for entry in payload["experiments"] if entry["id"] == experiment_id)
    problems.extend(f"invalid artifact: {value}" for value in invalid_artifacts(item))
    if problems:
        raise ValueError("; ".join(problems))
    return _set_status(experiment_id, "completed", evidence=evidence, path=path)
