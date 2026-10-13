"""重新校验已完成的 E17 产物包并原子性注册其证据至实验注册表。

核实盲审评分数据完整性并提交至形式化结论清单。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments import e17_review
from experiments.manifest import validate_completed_manifest
from experiments.registry import load_registry, save_registry


DEFAULT_REGISTRY = ROOT / "experiments" / "registry.json"
DEFAULT_SOURCE_INDEX = ROOT / "outputs" / "experiments" / "e17_source_index_corrected_v2.json"
DEFAULT_MANIFEST = ROOT / "outputs" / "experiments" / "E17" / "manifest.json"
FINAL_ANALYSIS_RELATIVE = Path("outputs/experiments/final_analysis")


class E17RegistrationError(RuntimeError):
    """在向注册表写入之前，当 E17 准入边界检查失败时抛出。"""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _inside_root(
    value: str | Path,
    root: Path,
    *,
    label: str,
    require_file: bool = True,
) -> Path:
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise E17RegistrationError(f"{label} escapes repository root: {value}") from exc
    if require_file and (not resolved.is_file() or resolved.stat().st_size <= 0):
        raise E17RegistrationError(f"{label} is missing or empty: {resolved}")
    return resolved


def _relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root).as_posix()


def _load_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise E17RegistrationError(f"invalid {label}: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise E17RegistrationError(f"{label} must be a JSON object: {path}")
    return payload


def _artifact_paths(
    manifest: Mapping[str, Any], *, manifest_path: Path, root: Path
) -> list[Path]:
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise E17RegistrationError("completed E17 manifest has no artifact ledger")
    paths: list[Path] = []
    seen: set[str] = set()
    for index, entry in enumerate(artifacts):
        if not isinstance(entry, Mapping):
            raise E17RegistrationError(f"E17 artifact[{index}] is not an object")
        raw = entry.get("path")
        if not isinstance(raw, str) or not raw.strip():
            raise E17RegistrationError(f"E17 artifact[{index}] has no path")
        candidate = Path(raw)
        if not candidate.is_absolute():
            # E17 records canonical repository-relative paths.  Retain support
            # for manifest-relative test fixtures without allowing traversal.
            root_candidate = root / candidate
            candidate = root_candidate if root_candidate.exists() else manifest_path.parent / candidate
        path = _inside_root(candidate, root, label=f"E17 artifact[{index}]")
        if int(entry.get("bytes", -1)) != path.stat().st_size:
            raise E17RegistrationError(f"E17 artifact[{index}] size mismatch: {path}")
        if str(entry.get("sha256", "")) != _sha256(path):
            raise E17RegistrationError(f"E17 artifact[{index}] hash mismatch: {path}")
        relative = _relative(path, root)
        if relative in seen:
            raise E17RegistrationError(f"duplicate E17 artifact path: {relative}")
        seen.add(relative)
        paths.append(path)
    return paths


def _source_contract(
    manifest: Mapping[str, Any],
    *,
    source_index: Path,
    root: Path,
) -> dict[str, Any]:
    """重新计算修正后的源图并将其绑定到 E17 计划。"""

    try:
        bundle = e17_review.load_source_index(source_index)
    except Exception as exc:
        raise E17RegistrationError(f"corrected E17 source index failed validation: {exc}") from exc
    if bundle.get("source_mode") != e17_review.SOURCE_MODE_FORMAL_CORRECTED:
        raise E17RegistrationError("E17 source index is not formal_program_corrected_context")
    expected = {
        "path": _relative(source_index, root),
        "sha256": _sha256(source_index),
    }
    configuration = manifest.get("configuration")
    plan = manifest.get("plan")
    if not isinstance(configuration, Mapping) or not isinstance(plan, Mapping):
        raise E17RegistrationError("completed E17 manifest lacks source-bound configuration/plan")
    if (
        configuration.get("source_mode") != e17_review.SOURCE_MODE_FORMAL_CORRECTED
        or configuration.get("registry_eligible") is not True
        or plan.get("source_mode") != e17_review.SOURCE_MODE_FORMAL_CORRECTED
    ):
        raise E17RegistrationError("completed E17 manifest is not registry-eligible corrected formal evidence")
    for label, record in (
        ("configuration.source_index", configuration.get("source_index")),
        ("plan.source_index", plan.get("source_index")),
    ):
        if not isinstance(record, Mapping):
            raise E17RegistrationError(f"completed E17 manifest lacks {label}")
        raw = Path(str(record.get("path", "")))
        path = raw.resolve() if raw.is_absolute() else (root / raw).resolve()
        if path != source_index or str(record.get("sha256", "")) != expected["sha256"]:
            raise E17RegistrationError(f"completed E17 manifest {label} hash/path mismatch")
    coverage = bundle.get("coverage")
    if (
        not isinstance(coverage, Mapping)
        or coverage.get("status") != "pass"
        or int(coverage.get("duplicate_logical_run_count", -1)) != 0
        or int(coverage.get("duplicate_logical_step_count", -1)) != 0
        or dict(configuration.get("coverage") or {}) != dict(coverage)
        or dict(plan.get("coverage") or {}) != dict(coverage)
    ):
        raise E17RegistrationError("completed E17 manifest coverage differs from recomputed source coverage")
    return {
        **expected,
        "schema_version": e17_review.SOURCE_INDEX_SCHEMA_VERSION,
        "source_mode": bundle["source_mode"],
        "coverage": dict(coverage),
    }


def _required_artifacts(
    registry: Mapping[str, Any], *, root: Path
) -> tuple[Mapping[str, Any], list[Path]]:
    item = next(
        (entry for entry in registry.get("experiments", []) if entry.get("id") == "E17"),
        None,
    )
    if not isinstance(item, Mapping):
        raise E17RegistrationError("registry has no E17 entry")
    values = item.get("required_artifacts")
    if not isinstance(values, list) or not values:
        raise E17RegistrationError("E17 required_artifacts are missing")
    paths = [
        _inside_root(value, root, label=f"E17 required_artifacts[{index}]")
        for index, value in enumerate(values)
    ]
    return item, paths


def _normalize_result_manifest(
    result: Mapping[str, Any], *, expected_manifest: Path, root: Path
) -> dict[str, Any]:
    returned_path = _inside_root(
        result.get("manifest_path", expected_manifest),
        root,
        label="E17 execute manifest",
    )
    if returned_path != expected_manifest:
        raise E17RegistrationError(
            f"E17 execute returned a different manifest: {returned_path}"
        )
    payload = result.get("manifest")
    if not isinstance(payload, Mapping):
        raise E17RegistrationError("E17 execute returned no manifest object")
    stored = _load_object(expected_manifest, label="E17 manifest")
    if dict(payload) != stored:
        raise E17RegistrationError("E17 execute manifest differs from the retained manifest")
    return stored


def prepare_registration(
    *,
    registry_path: str | Path,
    repository_root: str | Path,
    source_index_path: str | Path,
    manifest_path: str | Path,
) -> tuple[dict[str, Any], list[str]]:
    """运行已完成的快速路径，并返回无写操作的注册摘要。"""

    root = Path(repository_root).resolve()
    registry_file = _inside_root(registry_path, root, label="registry")
    source_index = _inside_root(source_index_path, root, label="E17 source index")
    manifest_file = _inside_root(manifest_path, root, label="E17 manifest")
    if (root / FINAL_ANALYSIS_RELATIVE).exists():
        raise E17RegistrationError(
            "refusing E17 registration after final_analysis exists; rebuild synthesis only after registration"
        )

    # Do not invoke the workflow on a pending manifest: its normal continuation
    # path rewrites packets.  Registration is only a hash-revalidation fast path.
    before = _load_object(manifest_file, label="E17 manifest")
    if before.get("experiment_id") != "E17":
        raise E17RegistrationError("manifest is not for E17")
    if before.get("status") != "completed" or before.get("phase") != "completed":
        raise E17RegistrationError(
            "E17 manifest must already be status=completed and phase=completed before registration"
        )
    source_contract = _source_contract(
        before, source_index=source_index, root=root
    )

    result = e17_review.execute(
        source_index_path=source_index,
        out_dir=manifest_file.parent,
        command=("python", "-m", "experiments.e17_review", "--source-index", _relative(source_index, root)),
    )
    manifest = _normalize_result_manifest(result, expected_manifest=manifest_file, root=root)
    if manifest.get("status") != "completed" or manifest.get("phase") != "completed":
        raise E17RegistrationError("E17 fast-path revalidation did not return a completed manifest")
    problems = validate_completed_manifest(manifest)
    if problems:
        raise E17RegistrationError("completed E17 manifest failed common validation: " + "; ".join(problems))

    registry = load_registry(registry_file)
    item, required = _required_artifacts(registry, root=root)
    if manifest_file not in required:
        raise E17RegistrationError("E17 required_artifacts do not include the revalidated manifest")
    artifact_paths = _artifact_paths(manifest, manifest_path=manifest_file, root=root)
    artifact_set = set(artifact_paths)
    unregistered_required = [
        path
        for path in required
        if path not in {manifest_file, source_index} and path not in artifact_set
    ]
    if unregistered_required:
        raise E17RegistrationError(
            "E17 required artifacts are absent from the manifest hash ledger: "
            + ", ".join(_relative(path, root) for path in unregistered_required)
        )
    evidence = [
        _relative(manifest_file, root),
        _relative(source_index, root),
        *(_relative(path, root) for path in artifact_paths),
    ]
    # Preserve order while guaranteeing one evidence record per path.
    evidence = list(dict.fromkeys(evidence))
    summary = {
        "status": "validated",
        "experiment_id": "E17",
        "manifest": _relative(manifest_file, root),
        "manifest_sha256": _sha256(manifest_file),
        "source_index": source_contract,
        "registry_sha256_before": _sha256(registry_file),
        "required_artifacts": [_relative(path, root) for path in required],
        "evidence_count": len(evidence),
        "evidence": evidence,
        "fast_path_revalidated": True,
        "already_registered": item.get("status") == "completed"
        and list(item.get("evidence") or []) == evidence
        and item.get("completion_registrar") == "scripts/register_e17_evidence.py"
        and (item.get("source_index") or {}).get("sha256")
        == source_contract["sha256"],
    }
    return summary, evidence


def _complete_e17_atomically(
    *,
    registry_path: Path,
    root: Path,
    summary: Mapping[str, Any],
    evidence: list[str],
) -> None:
    """专用的 E17 完成态流转函数；绝不调用通用门禁。"""

    if _sha256(registry_path) != str(summary.get("registry_sha256_before", "")):
        raise E17RegistrationError("registry changed after E17 validation; rerun admission")
    manifest_path = _inside_root(summary["manifest"], root, label="E17 manifest")
    source_record = summary.get("source_index")
    if not isinstance(source_record, Mapping):
        raise E17RegistrationError("validated E17 summary lacks source-index binding")
    source_path = _inside_root(source_record.get("path", ""), root, label="E17 source index")
    if (
        _sha256(manifest_path) != str(summary.get("manifest_sha256", ""))
        or _sha256(source_path) != str(source_record.get("sha256", ""))
    ):
        raise E17RegistrationError("E17 manifest or source index changed before registry write")
    live_manifest = _load_object(manifest_path, label="E17 manifest")
    live_source = _source_contract(live_manifest, source_index=source_path, root=root)
    if live_source["sha256"] != source_record.get("sha256"):
        raise E17RegistrationError("E17 source contract changed before registry write")
    live_artifacts = set(
        _artifact_paths(live_manifest, manifest_path=manifest_path, root=root)
    )
    payload = load_registry(registry_path)
    _, live_required = _required_artifacts(payload, root=root)
    if manifest_path not in live_required or any(
        path not in {manifest_path, source_path} and path not in live_artifacts
        for path in live_required
    ):
        raise E17RegistrationError("E17 required artifact contract changed before registry write")
    candidate = copy.deepcopy(payload)
    item = next(
        (entry for entry in candidate["experiments"] if entry.get("id") == "E17"),
        None,
    )
    if not isinstance(item, dict):
        raise E17RegistrationError("registry has no mutable E17 entry")
    now = datetime.now(timezone.utc).isoformat()
    item.update(
        {
            "status": "completed",
            "error": "",
            "evidence": list(evidence),
            "updated_at": now,
            "completed_at": now,
            "primary_manifest": _relative(manifest_path, root),
            "completion_registrar": "scripts/register_e17_evidence.py",
            "source_index": {
                "path": _relative(source_path, root),
                "sha256": str(source_record["sha256"]),
                "schema_version": e17_review.SOURCE_INDEX_SCHEMA_VERSION,
                "source_mode": e17_review.SOURCE_MODE_FORMAL_CORRECTED,
            },
        }
    )
    save_registry(candidate, registry_path)


def register(
    *,
    registry_path: str | Path = DEFAULT_REGISTRY,
    repository_root: str | Path = ROOT,
    source_index_path: str | Path | None = None,
    manifest_path: str | Path | None = None,
    apply: bool = False,
) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    registry_file = _inside_root(registry_path, root, label="registry")
    source_index = source_index_path or root / DEFAULT_SOURCE_INDEX.relative_to(ROOT)
    manifest_file = manifest_path or root / DEFAULT_MANIFEST.relative_to(ROOT)
    summary, evidence = prepare_registration(
        registry_path=registry_file,
        repository_root=root,
        source_index_path=source_index,
        manifest_path=manifest_file,
    )
    if not apply:
        return {**summary, "mode": "dry_run", "registry_written": False}
    if summary["already_registered"]:
        return {**summary, "mode": "apply", "registry_written": False, "no_op": True}

    _complete_e17_atomically(
        registry_path=registry_file,
        root=root,
        summary=summary,
        evidence=evidence,
    )
    stored = load_registry(registry_file)
    item = next(entry for entry in stored["experiments"] if entry["id"] == "E17")
    source_record = item.get("source_index") or {}
    if (
        item.get("status") != "completed"
        or item.get("evidence") != evidence
        or source_record.get("sha256") != summary["source_index"]["sha256"]
        or item.get("completion_registrar") != "scripts/register_e17_evidence.py"
    ):
        raise E17RegistrationError("post-write E17 registry verification failed")
    return {
        **summary,
        "mode": "apply",
        "registry_written": True,
        "no_op": False,
        "registry_sha256": _sha256(registry_file),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Revalidate a completed E17 bundle and register its evidence"
    )
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--source-index", type=Path, default=DEFAULT_SOURCE_INDEX)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--apply", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = register(
            registry_path=args.registry,
            repository_root=ROOT,
            source_index_path=args.source_index,
            manifest_path=args.manifest,
            apply=args.apply,
        )
    except E17RegistrationError as exc:
        parser.exit(2, f"E17 registration rejected: {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
