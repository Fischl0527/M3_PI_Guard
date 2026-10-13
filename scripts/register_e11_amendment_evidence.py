"""在构建最终分析报告前安全注册 E11 事后修正实验证据。

执行数据契约验证后将 E11 补充证据写入正式实验注册表。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.registry import load_registry, save_registry, validate_registry_payload
from scripts.build_final_analysis import (
    E11_SUPPLEMENT_DENOMINATOR_POLICY,
    E11_SUPPLEMENT_EXECUTION_REVISION,
    E11_SUPPLEMENT_ID,
    E11_SUPPLEMENT_RELATIVE,
    E11_SUPPLEMENT_VISUALIZATION_REVISION,
    FinalAnalysisError,
    validate_e11_supplement,
)


DEFAULT_REGISTRY = ROOT / "experiments" / "registry.json"
FINAL_ANALYSIS_RELATIVE = Path("outputs/experiments/final_analysis")


class RegistrationError(RuntimeError):
    """在向注册表写入之前，当边界不安全时抛出。"""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _inside_root(path: str | Path, root: Path, *, label: str, require_file: bool = True) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise RegistrationError(f"{label} escapes repository root: {path}") from exc
    if require_file and (not resolved.is_file() or resolved.stat().st_size <= 0):
        raise RegistrationError(f"{label} is missing or empty: {resolved}")
    return resolved


def _relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root).as_posix()


def _artifact_paths(
    manifest: Mapping[str, Any], *, supplement_dir: Path, root: Path
) -> list[Path]:
    values: list[Path] = []
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        raise RegistrationError("supplement manifest has no artifact ledger")
    for index, item in enumerate(artifacts):
        if not isinstance(item, Mapping):
            raise RegistrationError(f"supplement artifact[{index}] is not an object")
        raw = item.get("path")
        if not isinstance(raw, str) or not raw.strip():
            raise RegistrationError(f"supplement artifact[{index}] has no path")
        candidate = Path(raw)
        if not candidate.is_absolute():
            candidate = supplement_dir / candidate
        values.append(_inside_root(candidate, root, label=f"supplement artifact[{index}]"))
    return values


def prepare_registration(
    *,
    registry_path: str | Path,
    repository_root: str | Path,
    supplement_dir: str | Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    root = Path(repository_root).resolve()
    registry_file = _inside_root(registry_path, root, label="registry")
    registry = load_registry(registry_file)
    candidate = deepcopy(registry)
    e11 = next((item for item in candidate["experiments"] if item.get("id") == "E11"), None)
    if not isinstance(e11, dict) or e11.get("status") != "completed":
        raise RegistrationError("E11 must already be completed before its supplement is registered")

    original_required = deepcopy(e11.get("required_artifacts"))
    if not isinstance(original_required, list) or not original_required:
        raise RegistrationError("E11 required_artifacts are missing")
    resolved_required = [
        _inside_root(value, root, label=f"E11 required_artifacts[{index}]")
        for index, value in enumerate(original_required)
    ]
    manifest_candidates = [
        path
        for path in resolved_required
        if path.name == "manifest.json" and path.parent.name.casefold() == "e11"
    ]
    if len(manifest_candidates) != 1:
        raise RegistrationError(
            "E11 required_artifacts must preserve exactly one primary manifest in the original E11 directory"
        )
    original_manifest = manifest_candidates[0]
    original_payload = json.loads(original_manifest.read_text(encoding="utf-8"))
    if original_payload.get("experiment_id") != "E11" or original_payload.get("status") != "completed":
        raise RegistrationError("the original E11 primary manifest is not a completed E11 manifest")

    try:
        supplement, _ledger = validate_e11_supplement(
            supplement_dir, repository_root=root
        )
    except FinalAnalysisError as exc:
        raise RegistrationError(f"E11 post-hoc supplement failed validation: {exc}") from exc
    append_paths = [
        supplement.manifest_path,
        *_artifact_paths(supplement.manifest, supplement_dir=supplement.directory, root=root),
        supplement.execution_manifest_path,
        supplement.freeze_path,
    ]
    evidence = list(e11.get("evidence") or [])
    existing = {
        _relative(_inside_root(value, root, label=f"E11 evidence[{index}]"), root)
        for index, value in enumerate(evidence)
    }
    appended: list[str] = []
    for path in append_paths:
        value = _relative(path, root)
        if value not in existing:
            evidence.append(value)
            existing.add(value)
            appended.append(value)
    e11["evidence"] = evidence
    claim_boundary = {
        "schema_version": "1.0",
        "original_primary_manifest": {
            "path": _relative(original_manifest, root),
            "sha256": _sha256(original_manifest),
            "required_artifacts_preserved": True,
        },
        "posthoc_supplement": {
            "protocol_id": E11_SUPPLEMENT_ID,
            "visualization_revision": E11_SUPPLEMENT_VISUALIZATION_REVISION,
            "execution_revision": E11_SUPPLEMENT_EXECUTION_REVISION,
            "manifest_path": _relative(supplement.manifest_path, root),
            "manifest_sha256": _sha256(supplement.manifest_path),
            "pre_registered": False,
            "denominator_policy": E11_SUPPLEMENT_DENOMINATOR_POLICY,
            "evidence_role": "independently_denominated_posthoc_supplement",
        },
        "pooling_prohibited": True,
        "original_e11_replaced": False,
        "retroactive_preregistration_claimed": False,
        "acceptance_matrix_changed": False,
        "e18_structured_boundary": "outputs/experiments/final_analysis/manifest.json#e11_scope_boundary",
        "workflow_order": "register_then_regenerate_final_analysis",
    }
    e11["claim_boundary"] = claim_boundary

    # Current registry validation intentionally permits structured metadata. If
    # a future schema rejects it, keep the evidence append and rely on the E18
    # structured boundary rather than bypassing registry validation.
    boundary_mode = "registry_and_e18"
    try:
        validate_registry_payload(candidate)
    except (TypeError, ValueError):
        e11.pop("claim_boundary", None)
        boundary_mode = "evidence_only_registry_boundary_in_e18"
        try:
            validate_registry_payload(candidate)
        except (TypeError, ValueError) as exc:
            raise RegistrationError(f"candidate registry is invalid: {exc}") from exc
    if e11.get("required_artifacts") != original_required:
        raise RegistrationError("registration attempted to change E11 required_artifacts")
    if _relative(original_manifest, root) not in {
        _relative(_inside_root(value, root, label="post-registration required artifact"), root)
        for value in e11["required_artifacts"]
    }:
        raise RegistrationError("registration lost the original E11 primary manifest")
    summary = {
        "status": "validated",
        "registry": _relative(registry_file, root),
        "experiment_id": "E11",
        "protocol_id": E11_SUPPLEMENT_ID,
        "visualization_revision": E11_SUPPLEMENT_VISUALIZATION_REVISION,
        "execution_revision": E11_SUPPLEMENT_EXECUTION_REVISION,
        "appended_evidence": appended,
        "appended_evidence_count": len(appended),
        "required_artifacts_changed": False,
        "original_primary_manifest": _relative(original_manifest, root),
        "original_primary_manifest_sha256": _sha256(original_manifest),
        "supplement_manifest": _relative(supplement.manifest_path, root),
        "supplement_manifest_sha256": _sha256(supplement.manifest_path),
        "pre_registered": False,
        "denominator_policy": E11_SUPPLEMENT_DENOMINATOR_POLICY,
        "boundary_mode": boundary_mode,
        "next_step": "regenerate outputs/experiments/final_analysis after registration",
    }
    return candidate, summary


def register(
    *,
    registry_path: str | Path = DEFAULT_REGISTRY,
    repository_root: str | Path = ROOT,
    supplement_dir: str | Path | None = None,
    apply: bool = False,
) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    registry_file = _inside_root(registry_path, root, label="registry")
    supplement_source = (
        Path(supplement_dir)
        if supplement_dir is not None
        else root / E11_SUPPLEMENT_RELATIVE
    )
    candidate, summary = prepare_registration(
        registry_path=registry_file,
        repository_root=root,
        supplement_dir=supplement_source,
    )
    final_analysis = root / FINAL_ANALYSIS_RELATIVE
    if apply and final_analysis.exists():
        raise RegistrationError(
            "refusing to mutate the registry after final_analysis exists; remove/regenerate E18 through the normal final build workflow"
        )
    if not apply:
        return {**summary, "mode": "dry_run", "registry_written": False}
    before_required = deepcopy(
        next(item for item in load_registry(registry_file)["experiments"] if item["id"] == "E11")[
            "required_artifacts"
        ]
    )
    save_registry(candidate, registry_file)
    stored = load_registry(registry_file)
    stored_e11 = next(item for item in stored["experiments"] if item["id"] == "E11")
    if stored_e11["required_artifacts"] != before_required:
        raise RegistrationError("post-write verification found E11 required_artifact drift")
    return {
        **summary,
        "mode": "apply",
        "registry_written": True,
        "registry_sha256": _sha256(registry_file),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Register the hash-verified E11 post-hoc supplement without replacing original E11"
    )
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--repository-root", default=str(ROOT))
    parser.add_argument("--supplement", default=None)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Atomically write the validated evidence append; default is dry-run",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = register(
            registry_path=args.registry,
            repository_root=args.repository_root,
            supplement_dir=args.supplement,
            apply=args.apply,
        )
    except RegistrationError as exc:
        print(f"E11 amendment registration rejected: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
