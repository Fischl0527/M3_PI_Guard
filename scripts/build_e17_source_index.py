"""构建确定性的 E17 Schema-2.0 修正版形式化源码索引。

为 E17 盲测人工审计构建源文件索引映射，确保可追踪性与审计透明度。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

_BOOT_ROOT = Path(__file__).resolve().parents[1]
if str(_BOOT_ROOT) not in sys.path:
    sys.path.insert(0, str(_BOOT_ROOT))

from experiments import e17_review as e17


ROOT = e17.REPO_ROOT
DEFAULT_PROGRAM_MANIFEST = ROOT / "outputs" / "experiments" / "program_manifest_final_v3.json"
DEFAULT_PROGRAM_ROOT = ROOT / "outputs" / "experiments" / "program_final_v3"
DEFAULT_INVALID_AUDIT = ROOT / "agent" / "audits" / "context_experiment_validity.json"
DEFAULT_CORRECTION_FREEZE = ROOT / "protocols" / "context_correction_v2" / "freeze_r3.json"
DEFAULT_CORRECTION_AUDIT = ROOT / "agent" / "audits" / "context_correction_v2.json"
DEFAULT_E16_MANIFEST = ROOT / "outputs" / "experiments" / "E16" / "manifest.json"
DEFAULT_OUTPUT = ROOT / "outputs" / "experiments" / "e17_source_index_corrected_v2.json"


class SourceIndexBuildError(RuntimeError):
    """在源索引固化前发生错误时抛出。"""


def _inside(path: Path, root: Path) -> Path:
    target = path.expanduser().resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError as exc:
        raise SourceIndexBuildError(f"source-index input escaped repository: {target}") from exc
    if not target.is_file():
        raise FileNotFoundError(target)
    return target


def _directory(path: Path, root: Path) -> Path:
    target = path.expanduser().resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError as exc:
        raise SourceIndexBuildError(f"program root escaped repository: {target}") from exc
    if not target.is_dir():
        raise FileNotFoundError(target)
    return target


def _read_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SourceIndexBuildError(f"invalid {label}: {path}: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise SourceIndexBuildError(f"{label} must be a JSON object: {path}")
    return value


def _reference(path: Path, root: Path) -> dict[str, Any]:
    target = _inside(path, root)
    return {
        "path": target.relative_to(root.resolve()).as_posix(),
        "bytes": target.stat().st_size,
        "sha256": e17._sha256_file(target),
    }


def _audit_manifest_reference(
    audit: Mapping[str, Any],
    *,
    experiment_id: str,
    root: Path,
) -> tuple[Path, dict[str, Any]]:
    """从独立审计绑定中解析修正后的清单。"""

    try:
        candidate = e17._correction_audit_manifest_binding(
            audit, experiment_id=experiment_id
        )
    except e17.E17Error as exc:
        raise SourceIndexBuildError(str(exc)) from exc
    raw = Path(str(candidate["path"]))
    path = raw.resolve() if raw.is_absolute() else (root / raw).resolve()
    observed = _reference(path, root)
    if (
        observed["sha256"] != str(candidate.get("sha256", ""))
        or (
            candidate.get("bytes") is not None
            and observed["bytes"] != int(candidate["bytes"])
        )
    ):
        raise SourceIndexBuildError(
            f"correction audit {experiment_id} manifest binding is stale"
        )
    return path, observed


def build_source_index(
    *,
    root: Path = ROOT,
    program_manifest_path: Path = DEFAULT_PROGRAM_MANIFEST,
    program_root_path: Path = DEFAULT_PROGRAM_ROOT,
    invalid_context_audit_path: Path = DEFAULT_INVALID_AUDIT,
    correction_freeze_path: Path = DEFAULT_CORRECTION_FREEZE,
    correction_audit_path: Path = DEFAULT_CORRECTION_AUDIT,
    e9_manifest_path: Path | None = None,
    e14_manifest_path: Path | None = None,
    e16_manifest_path: Path = DEFAULT_E16_MANIFEST,
    invalid_e9_allowlist: Mapping[str, Mapping[str, str]] | None = None,
) -> dict[str, Any]:
    """构建并完整重新审计修正后的源索引载荷。"""

    root = root.resolve()
    program_manifest_path = _inside(program_manifest_path, root)
    program_root_path = _directory(program_root_path, root)
    program = _read_object(program_manifest_path, label="program manifest")
    if program.get("status") != "completed" or not isinstance(program.get("stages"), Mapping):
        raise SourceIndexBuildError("program manifest must be completed with a stage mapping")
    allowlist = invalid_e9_allowlist or e17.INVALID_V3_E9_MANIFEST_ALLOWLIST

    retained: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    seen_jobs: set[str] = set()
    for stage_name in e17.REQUIRED_PROGRAM_STAGES:
        stage = program["stages"].get(stage_name)
        if not isinstance(stage, Mapping) or stage.get("status") != "completed":
            raise SourceIndexBuildError(f"required program stage is incomplete: {stage_name}")
        jobs = stage.get("jobs")
        if not isinstance(jobs, list) or not jobs:
            raise SourceIndexBuildError(f"required program stage has no jobs: {stage_name}")
        for job in jobs:
            if not isinstance(job, Mapping) or job.get("status") != "completed":
                raise SourceIndexBuildError(f"incomplete program job in stage {stage_name}")
            job_id = str(job.get("job_id", ""))
            if not job_id or job_id in seen_jobs:
                raise SourceIndexBuildError(f"missing or duplicate program job_id: {job_id}")
            seen_jobs.add(job_id)
            raw = Path(str(job.get("result_manifest", "")))
            matrix = raw.resolve() if raw.is_absolute() else (root / raw).resolve()
            reference = _reference(matrix, root)
            if job_id in allowlist:
                expected = allowlist[job_id]
                if (
                    stage_name != "derived"
                    or reference["path"] != str(expected["path"])
                    or reference["sha256"] != str(expected["sha256"])
                ):
                    raise SourceIndexBuildError(
                        f"allowlisted invalid E9 matrix drifted: {job_id}"
                    )
                excluded.append(
                    {
                        **reference,
                        "job_id": job_id,
                        "stage": stage_name,
                        "reason": e17.INVALID_V3_E9_REASON,
                    }
                )
            else:
                retained.append(reference)
    if {item["job_id"] for item in excluded} != set(allowlist) or len(excluded) != 4:
        raise SourceIndexBuildError("program does not contain exactly the four allowlisted invalid E9 jobs")

    correction_audit_path = _inside(correction_audit_path, root)
    correction_audit = _read_object(correction_audit_path, label="context correction audit")
    audit_e9_path, audit_e9_reference = _audit_manifest_reference(
        correction_audit, experiment_id="E9", root=root
    )
    audit_e14_path, audit_e14_reference = _audit_manifest_reference(
        correction_audit, experiment_id="E14", root=root
    )
    if e9_manifest_path is not None and _inside(e9_manifest_path, root) != audit_e9_path:
        raise SourceIndexBuildError("--e9-manifest differs from the correction audit binding")
    if e14_manifest_path is not None and _inside(e14_manifest_path, root) != audit_e14_path:
        raise SourceIndexBuildError("--e14-manifest differs from the correction audit binding")

    payload: dict[str, Any] = {
        "schema_version": e17.SOURCE_INDEX_SCHEMA_VERSION,
        "experiment_id": e17.EXPERIMENT_ID,
        "source_mode": e17.SOURCE_MODE_FORMAL_CORRECTED,
        "status": "frozen",
        "generated_by": "scripts/build_e17_source_index.py",
        "secondary_disagreement_policy": e17.SECONDARY_DISAGREEMENT_POLICY,
        "required_program_stages": list(e17.REQUIRED_PROGRAM_STAGES),
        "program_root": program_root_path.relative_to(root).as_posix(),
        "program_manifest": _reference(program_manifest_path, root),
        "program_matrix_manifests": sorted(retained, key=lambda value: value["path"]),
        "excluded_program_matrix_manifests": sorted(
            excluded, key=lambda value: value["job_id"]
        ),
        "invalid_context_audit": _reference(invalid_context_audit_path, root),
        "correction_freeze": _reference(correction_freeze_path, root),
        "correction_audit": _reference(correction_audit_path, root),
        "corrected_e9_manifest": audit_e9_reference,
        "corrected_e14_manifest": audit_e14_reference,
        "e16_manifest": _reference(e16_manifest_path, root),
        "denominator_policy": {
            "retained_program": "all required V3 program matrices except the four hash-allowlisted invalid E9 matrices",
            "corrected_e9": "120 formal logical case-runs",
            "corrected_e14": "432 formal logical case-runs; 48 warmup logical case-runs retained in provenance and excluded",
            "e16": "retained completed adaptive-red-team evidence",
            "old_e14": "excluded; replaced by corrected E14 V2",
        },
    }
    # e17_review uses its repository root for strict path confinement.  Tests
    # patch that module constant; the production CLI always uses the real root.
    payload["coverage"] = e17.recompute_corrected_source_coverage(payload)
    return payload


def _json_text(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write_source_index(path: Path, payload: Mapping[str, Any], *, check: bool = False) -> Path:
    target = path.expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    expected = _json_text(payload)
    if check:
        if not target.is_file() or target.read_text(encoding="utf-8") != expected:
            raise SourceIndexBuildError(f"source index is missing or stale: {target}")
        e17.load_source_index(target)
        return target
    temporary = target.with_name(target.name + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(expected)
            handle.flush()
            os.fsync(handle.fileno())
        # Exercise the persisted loader before replacing a prior frozen index.
        e17.load_source_index(temporary)
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()
    return target


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--program-manifest", type=Path, default=DEFAULT_PROGRAM_MANIFEST)
    parser.add_argument("--program-root", type=Path, default=DEFAULT_PROGRAM_ROOT)
    parser.add_argument("--invalid-context-audit", type=Path, default=DEFAULT_INVALID_AUDIT)
    parser.add_argument("--correction-freeze", type=Path, default=DEFAULT_CORRECTION_FREEZE)
    parser.add_argument("--correction-audit", type=Path, default=DEFAULT_CORRECTION_AUDIT)
    parser.add_argument(
        "--e9-manifest",
        type=Path,
        help="Optional assertion; the authoritative path/hash comes from --correction-audit",
    )
    parser.add_argument(
        "--e14-manifest",
        type=Path,
        help="Optional assertion; the authoritative path/hash comes from --correction-audit",
    )
    parser.add_argument("--e16-manifest", type=Path, default=DEFAULT_E16_MANIFEST)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = build_source_index(
        program_manifest_path=args.program_manifest,
        program_root_path=args.program_root,
        invalid_context_audit_path=args.invalid_context_audit,
        correction_freeze_path=args.correction_freeze,
        correction_audit_path=args.correction_audit,
        e9_manifest_path=args.e9_manifest,
        e14_manifest_path=args.e14_manifest,
        e16_manifest_path=args.e16_manifest,
    )
    target = write_source_index(args.out, payload, check=args.check)
    print(
        json.dumps(
            {
                "status": "pass",
                "path": str(target),
                "sha256": e17._sha256_file(target),
                "coverage": payload["coverage"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
