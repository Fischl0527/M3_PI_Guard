"""冻结并验证所有可能影响盲测证据链的代码与数据边界。

为全库关键代码和固定数据集计算防篡改 SHA-256 哈希树并持久化至清单文件。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
from typing import Iterable

from .manifest import REPO_ROOT, git_state, save_manifest, sha256_file, utc_now


DEFAULT_FREEZE_PATH = REPO_ROOT / "outputs" / "experiments" / "blind_freeze.json"

# Enumerated roots catch files added after the freeze.  ``experiments`` is a
# root (rather than a short file list) so a newly introduced runner/scorer
# cannot silently escape the blind boundary.
PROTECTED_ROOTS = (
    "m3_core",
    "m3_guard",
    "m3_attacks",
    "m3_eval",
    "schemas",
    "fixtures",
    "experiments",
)

# These files are both protected and mandatory.  Root enumeration alone would
# not notice that a critical file had already been deleted before create.
REQUIRED_FILES = (
    "m3_core/agent_runner.py",
    "m3_core/case_views.py",
    "m3_core/llm_client.py",
    "m3_core/run_batch.py",
    "m3_core/run_matrix.py",
    "m3_core/tool_sandbox.py",
    "m3_guard/config.py",
    "m3_guard/dataflow.py",
    "m3_guard/detector.py",
    "m3_guard/guard_engine.py",
    "m3_guard/policy_engine.py",
    "m3_attacks/attackgen.py",
    "m3_attacks/cases/all_cases.jsonl",
    "m3_eval/metrics.py",
    "m3_eval/statistics.py",
    "m3_eval/figure_manifest.py",
    "schemas/attack_case.schema.json",
    "schemas/run_log.schema.json",
    "schemas/tool_call.schema.json",
    "experiments/catalog.py",
    "experiments/run_program.py",
    "experiments/derived_cases.py",
    "experiments/model_manager.py",
    "experiments/manifest.py",
    "experiments/freeze.py",
    "experiments/analyze_program.py",
    "experiments/e13_calibration.py",
    "experiments/e14_performance.py",
    "experiments/e16_adaptive_redteam.py",
    "experiments/e17_review.py",
    # Although stored under outputs, this is the immutable calibration input
    # consumed by post-calibration blind stages. No other runtime output is in
    # the boundary.
    "outputs/experiments/E13/frozen_thresholds.json",
    "experiments/fixtures/smoke_cases.jsonl",
    "experiments/fixtures/derived/e7_cases.jsonl",
    "experiments/fixtures/derived/e8_cases.jsonl",
    "experiments/fixtures/derived/e9_cases.jsonl",
    "experiments/fixtures/derived/e10_cases.jsonl",
    "experiments/fixtures/derived/e11_cases.jsonl",
    "experiments/fixtures/derived/e15_cases.jsonl",
)

# Compatibility alias retained for callers that imported the old constant.
PROTECTED_FILES = REQUIRED_FILES

INCLUDED_SUFFIXES = {
    ".py",
    ".json",
    ".jsonl",
    ".yaml",
    ".yml",
    ".toml",
    ".csv",
    ".tsv",
    ".txt",
}

# Exact generated/mutable files.  They are evidence or orchestration state,
# not inputs to model execution or scoring.
EXCLUDED_FILES = frozenset(
    {
        "experiments/registry.json",
        "m3_attacks/cases/dataset_audit.json",
        "m3_attacks/cases/dataset_stats.json",
        "experiments/fixtures/derived/derived_cases_audit.json",
    }
)
IMMUTABLE_INPUT_ARTIFACTS = frozenset(
    {"outputs/experiments/E13/frozen_thresholds.json"}
)
EXCLUDED_DIRECTORY_NAMES = frozenset(
    {
        "__pycache__",
        ".git",
        "outputs",
        "reports",
        ".state",
        "analysis_state",
        "runtime_state",
    }
)


def _resolved_root(repo_root: Path) -> Path:
    root = Path(repo_root).resolve()
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError(f"blind freeze repository root is missing: {root}")
    return root


def _inside_repo(path: Path, root: Path, *, label: str) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"{label} is outside repository root {root}: {resolved}") from exc
    return resolved


def _relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root).as_posix()


def _excluded(relative: str) -> bool:
    if relative in IMMUTABLE_INPUT_ARTIFACTS:
        return False
    pure = PurePosixPath(relative)
    return relative in EXCLUDED_FILES or bool(set(pure.parts) & EXCLUDED_DIRECTORY_NAMES)


def boundary_missing(repo_root: Path = REPO_ROOT) -> dict[str, list[str]]:
    """返回缺失的必选根目录/文件，且不抛出异常。"""

    root = _resolved_root(repo_root)
    missing_roots: list[str] = []
    for relative in PROTECTED_ROOTS:
        path = root / PurePosixPath(relative)
        if not path.exists() or not path.is_dir():
            missing_roots.append(relative)
    missing_files: list[str] = []
    for relative in REQUIRED_FILES:
        path = root / PurePosixPath(relative)
        if not path.exists() or not path.is_file():
            missing_files.append(relative)
    return {
        "roots": sorted(missing_roots),
        "files": sorted(missing_files),
    }


def _format_boundary_error(missing: dict[str, list[str]]) -> str:
    details: list[str] = []
    if missing["roots"]:
        details.append("missing required root(s): " + ", ".join(missing["roots"]))
    if missing["files"]:
        details.append("missing required file(s): " + ", ".join(missing["files"]))
    return "blind freeze boundary is incomplete; " + "; ".join(details)


def protected_paths(
    repo_root: Path = REPO_ROOT,
    *,
    require_complete: bool = True,
) -> list[Path]:
    """枚举 ``repo_root`` 内当前受保护的常规文件。

    校验使用 ``require_complete=False``，使得文件删除成为返回的待办问题，而非在报告所有修改/新增/缺失路径之前提前中断校验。
    """

    root = _resolved_root(repo_root)
    missing = boundary_missing(root)
    if require_complete and (missing["roots"] or missing["files"]):
        raise FileNotFoundError(_format_boundary_error(missing))

    paths: set[Path] = set()
    for relative_root in PROTECTED_ROOTS:
        source_root = root / PurePosixPath(relative_root)
        if not source_root.exists() or not source_root.is_dir():
            continue
        _inside_repo(source_root, root, label=f"protected root {relative_root!r}")
        for candidate in source_root.rglob("*"):
            if not candidate.is_file() or candidate.suffix.lower() not in INCLUDED_SUFFIXES:
                continue
            resolved = _inside_repo(candidate, root, label="protected file")
            relative = _relative(resolved, root)
            if not _excluded(relative):
                paths.add(resolved)

    # Explicit files are added even if a future suffix policy changes.  Missing
    # ones are skipped only in verification mode and reported separately.
    for relative in REQUIRED_FILES:
        candidate = root / PurePosixPath(relative)
        if candidate.exists() and candidate.is_file():
            resolved = _inside_repo(candidate, root, label=f"required file {relative!r}")
            if _excluded(_relative(resolved, root)):
                raise ValueError(f"required freeze file is also excluded: {relative}")
            paths.add(resolved)
    return sorted(paths, key=lambda path: _relative(path, root))


def _resolve_user_path(value: str | Path, root: Path, *, label: str) -> Path:
    path = Path(value)
    candidate = path if path.is_absolute() else root / path
    return _inside_repo(candidate, root, label=label)


def _manifest_relative(value: object, root: Path) -> tuple[str | None, Path | None, str | None]:
    """验证单个可移植、规范且相对于仓库根目录的固化条目。"""

    relative = str(value)
    pure = PurePosixPath(relative)
    if (
        not relative
        or "\\" in relative
        or pure.is_absolute()
        or any(part in {"", ".", ".."} for part in pure.parts)
    ):
        return None, None, f"invalid path in freeze manifest: {relative!r}"
    candidate = root.joinpath(*pure.parts)
    try:
        resolved = _inside_repo(candidate, root, label="freeze manifest entry")
    except ValueError as exc:
        return None, None, str(exc)
    canonical = _relative(resolved, root)
    if canonical != relative:
        return None, None, f"non-canonical path in freeze manifest: {relative!r} -> {canonical!r}"
    return relative, resolved, None


def create_freeze(
    path: str | Path = DEFAULT_FREEZE_PATH,
    *,
    repo_root: Path = REPO_ROOT,
    extra_paths: Iterable[str | Path] = (),
) -> dict:
    root = _resolved_root(repo_root)
    freeze_path = _resolve_user_path(path, root, label="freeze manifest path")
    files = protected_paths(root, require_complete=True)
    resolved_extras: list[Path] = []
    for value in extra_paths:
        item = _resolve_user_path(value, root, label="extra freeze path")
        if not item.exists() or not item.is_file():
            raise FileNotFoundError(f"cannot freeze missing/non-file extra path: {item}")
        relative = _relative(item, root)
        if _excluded(relative):
            raise ValueError(f"cannot freeze excluded mutable/generated path: {relative}")
        resolved_extras.append(item)
    files.extend(resolved_extras)
    files = sorted(set(files), key=lambda item: _relative(item, root))
    hashes = {_relative(item, root): sha256_file(item) for item in files}
    payload = {
        "schema_version": "2.0",
        "created_at": utc_now(),
        "git": git_state(),
        "boundary": {
            "protected_roots": list(PROTECTED_ROOTS),
            "required_files": list(REQUIRED_FILES),
            "included_suffixes": sorted(INCLUDED_SUFFIXES),
            "excluded_files": sorted(EXCLUDED_FILES),
            "excluded_directory_names": sorted(EXCLUDED_DIRECTORY_NAMES),
            "immutable_input_artifacts": sorted(IMMUTABLE_INPUT_ARTIFACTS),
            "extra_files": sorted(_relative(item, root) for item in resolved_extras),
        },
        "file_count": len(hashes),
        "files": hashes,
    }
    save_manifest(payload, freeze_path)
    return payload


def verify_freeze(
    path: str | Path = DEFAULT_FREEZE_PATH,
    *,
    repo_root: Path = REPO_ROOT,
) -> list[str]:
    root = _resolved_root(repo_root)
    freeze_path = _resolve_user_path(path, root, label="freeze manifest path")
    if not freeze_path.exists() or not freeze_path.is_file():
        raise FileNotFoundError(f"blind freeze manifest is missing: {freeze_path}")
    try:
        payload = json.loads(freeze_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid blind freeze JSON: {freeze_path}: {exc.msg}") from exc
    expected_files = payload.get("files")
    if not isinstance(expected_files, dict):
        raise ValueError("blind freeze manifest 'files' must be an object")

    problems: list[str] = []
    validated_expected: dict[str, tuple[Path, object]] = {}
    for raw_relative, expected_hash in sorted(expected_files.items(), key=lambda item: str(item[0])):
        relative, current, error = _manifest_relative(raw_relative, root)
        if error:
            problems.append(error)
            continue
        assert relative is not None and current is not None
        if not isinstance(expected_hash, str) or len(expected_hash) != 64:
            problems.append(f"invalid SHA-256 for {relative}")
            continue
        validated_expected[relative] = (current, expected_hash)

    for relative in sorted(REQUIRED_FILES):
        if relative not in expected_files:
            problems.append(f"freeze missing required entry: {relative}")

    missing_boundary = boundary_missing(root)
    for relative in missing_boundary["roots"]:
        problems.append(f"missing required root: {relative}")
    for relative in missing_boundary["files"]:
        if relative not in validated_expected:
            problems.append(f"missing required file: {relative}")

    for relative, (current, expected_hash) in validated_expected.items():
        if not current.exists() or not current.is_file():
            problems.append(f"missing: {relative}")
        elif sha256_file(current) != expected_hash:
            problems.append(f"changed: {relative}")

    try:
        current_set = {
            _relative(item, root)
            for item in protected_paths(root, require_complete=False)
        }
    except (FileNotFoundError, ValueError) as exc:
        problems.append(f"boundary enumeration error: {exc}")
        current_set = set()
    additions = current_set - set(validated_expected)
    problems.extend(f"added: {relative}" for relative in sorted(additions))
    return sorted(set(problems))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["create", "verify"])
    parser.add_argument("--path", default=str(DEFAULT_FREEZE_PATH))
    args = parser.parse_args(argv)
    if args.action == "create":
        payload = create_freeze(args.path)
        print(f"blind freeze created: {args.path} ({payload['file_count']} files)")
        return 0
    problems = verify_freeze(args.path)
    if problems:
        for problem in problems:
            print("FAIL:", problem)
        return 1
    print("blind freeze verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
