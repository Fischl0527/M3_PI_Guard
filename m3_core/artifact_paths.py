"""可读产物名称与Windows路径预算；长度按UTF-16单位计算。"""

from __future__ import annotations

from pathlib import Path

MAX_FILE_NAME = 80
MAX_DIRECTORY_NAME = 64
MAX_RELATIVE_PATH = 180
MAX_ABSOLUTE_PATH = 240


def path_units(value: str) -> int:
    return len(value.encode("utf-16-le")) // 2


def path_issues(path: Path, root: Path) -> list[str]:
    """原版参考文献保留题名，但仍须满足目录及完整路径预算。"""
    absolute = path.absolute()
    try:
        relative = absolute.relative_to(root.absolute())
    except ValueError:
        relative = Path(*absolute.parts[1:])
    issues = []
    reference_title = (relative.parts[:2] == ("docs", "文档资料")
                       or relative.parts[:1] == ("文档资料",))
    if not reference_title and path_units(path.name) > MAX_FILE_NAME:
        issues.append(f"文件名超过{MAX_FILE_NAME}：{path.name}")
    for part in relative.parts[:-1]:
        if path_units(part) > MAX_DIRECTORY_NAME:
            issues.append(f"单级目录超过{MAX_DIRECTORY_NAME}：{part}")
    if path_units(relative.as_posix()) > MAX_RELATIVE_PATH:
        issues.append(f"相对路径超过{MAX_RELATIVE_PATH}：{relative.as_posix()}")
    if path_units(str(absolute)) > MAX_ABSOLUTE_PATH:
        issues.append(f"完整路径超过{MAX_ABSOLUTE_PATH}：{absolute}")
    return issues


def require_short_path(path: Path, root: Path) -> None:
    problems = path_issues(path, root)
    if problems:
        raise ValueError("路径过长；请删除重复信息或减少层级，保留可读名称：" + "; ".join(problems))


def resolve_artifact(path: Path) -> Path:
    """只识别本次迁移的重复消融产物，不修改冻结清单及结果正文。"""
    if path.exists():
        return path
    if (path.parent.name.startswith("ablation__")
            and path.name.startswith(path.parent.name + "_")
            and path.suffix in {".jsonl", ".csv"}):
        name = "records.jsonl" if path.suffix == ".jsonl" else "metrics.csv"
        candidate = path.with_name(name)
        if candidate.is_file():
            return candidate
    return path


def matrix_output_paths(directory: Path, prefix: str, suffix: str, *, single: bool) -> tuple[Path, Path]:
    """兼容普通短名称，去掉条件目录中重复的长前缀；不做截断或编号化。"""
    original = directory / f"{prefix}_{suffix}.jsonl"
    resolved = resolve_artifact(original)
    if resolved.is_file():
        return resolved, resolve_artifact(original.with_suffix(".csv"))
    if single and (prefix.endswith(suffix) or path_units(original.name) > MAX_FILE_NAME):
        return directory / "records.jsonl", directory / "metrics.csv"
    if path_units(original.name) > MAX_FILE_NAME:
        return directory / f"{suffix}.jsonl", directory / f"{suffix}.csv"
    return original, original.with_suffix(".csv")
