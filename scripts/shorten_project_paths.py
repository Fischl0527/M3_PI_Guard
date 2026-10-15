"""本次长路径整理：整目录/整文件改名，不改实验内容，不覆盖目标。"""

from __future__ import annotations

import csv
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "outputs/maintenance/path_names/moves.csv"
APPLY_CHANGES = True
PACKAGE_NAMES = {
    "M3_PI_Guard_Blind_Custodian_Review_Package_v3_1_python_final": "review_v3_1",
    "M3_PI_Guard_Blind_Custodian_Review_Package_v3_2_python_final": "review_v3_2",
    "M3_PI_Guard_Blind_Custodian_Review_Package_v3_3_python_final": "review_v3_3",
    "M3_PI_Guard_Blind_Custodian_Review_Package_v3_4_python_final": "review_v3_4",
    "M3_PI_Guard_Blind_Custodian_Review_Package_v3_python_final": "review_v3",
    "M3_PI_Guard_Blind_Custodian_Toolkit_v2": "toolkit_v2",
    "M3_PI_Guard_Blind_Custodian_Toolkit_v2_final": "toolkit_v2_final",
}


def build_moves(root: Path, files: list[str]) -> list[tuple[Path, Path, str]]:
    moves = []
    archives = root / "release/archive/blind_custodian_toolkits"
    for old, new in PACKAGE_NAMES.items():
        source = archives / old
        if source.is_dir():
            moves.append((source, archives / new, "历史工具包去除重复项目名；保留类型和版本"))
    partials: set[Path] = set()
    for value in files:
        source = root / value
        parts = source.relative_to(root).parts
        if parts[:2] != ("outputs", "experiments") and parts[:2] != ("outputs", "verification"):
            continue
        if len(str(source).encode("utf-16-le")) // 2 < 240:
            continue
        for parent in source.parents:
            if parent == root:
                break
            if parent.name.startswith(".") and parent.name.endswith(".parts"):
                partials.add(parent)
                break
    for source in sorted(partials):
        siblings = list(source.parent.glob(".*.parts"))
        # 仅处理一条件一目录的已结束分片；多条件共享目录不猜测对应关系。
        if len(siblings) == 1:
            moves.append((source, source.parent / "partial_results", "已结束批次的临时分片去除重复运行名"))
    for name in ("program_final_v3", "program_final", "program_v3", "program_v2"):
        directory = root / "outputs/experiments" / name / "ablation"
        if not directory.is_dir():
            continue
        for job in directory.iterdir():
            if not job.is_dir():
                continue
            for source in job.iterdir():
                if source.is_file() and source.name.startswith(job.name + "_"):
                    target = {".jsonl": "records.jsonl", ".csv": "metrics.csv"}.get(source.suffix)
                    if target:
                        moves.append((source, source.with_name(target), "条件已由目录表达，文件只标明用途"))
    old_tests = root / "outputs/verification/experiment_closeout_fresh_harness_v12_20260819/pytest-temp/pytest-of-gaohang/pytest-0"
    if old_tests.is_dir():
        moves.append((old_tests, root / "outputs/archived_tests/20260819",
                      "旧测试临时目录按日期归档；验证报告保留原位"))
    return moves


def inventory(path: Path) -> dict[str, tuple[int, int, int]]:
    files = [path] if path.is_file() else [p for p in path.rglob("*") if p.is_file()]
    result = {}
    for child in files:
        info = child.stat()
        key = "" if path.is_file() else child.relative_to(path).as_posix()
        result[key] = info.st_size, info.st_mtime_ns, info.st_ino
    return result


def move_preserving_files(source: Path, target: Path, root: Path) -> int:
    # 在同一文件系统内改名；不递归删除、不读取正文、不跟随外部联接。
    for path in (source, target):
        path.resolve().relative_to(root.resolve())
        for parent in (path, *path.parents):
            if parent == root:
                break
            if parent.is_symlink() or (hasattr(parent, "is_junction") and parent.is_junction()):
                raise ValueError(f"目录联接保留原位：{parent}")
    if target.exists():
        raise FileExistsError(f"目标已存在，不覆盖：{target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.parent.stat().st_dev != target.parent.stat().st_dev:
        raise ValueError("本工具只执行同盘改名")
    before = inventory(source)
    source.rename(target)
    if inventory(target) != before:
        target.rename(source)
        raise RuntimeError("改名后文件元数据不一致，已尝试恢复原名")
    return len(before)


def main() -> None:
    listing = subprocess.run(
        ["rg", "--files", "--hidden", "--no-ignore", "--null", "-g", "!.git/**", "-g", "!**/.git/**"],
        cwd=ROOT, capture_output=True, check=True,
    )
    files = [s.decode("utf-8").replace(os.sep, "/") for s in listing.stdout.split(b"\0") if s]
    moves = build_moves(ROOT, files)
    # 所有目标先检查，再开始改名；发现任何同名项不会启动这轮迁移。
    targets = set()
    for _, target, _ in moves:
        folded = str(target).casefold()
        if target.exists() or folded in targets:
            raise FileExistsError(f"迁移目标冲突：{target}")
        targets.add(folded)
    if not APPLY_CHANGES:
        print(json.dumps({"planned_moves": len(moves)}, ensure_ascii=False))
        return
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with REPORT.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        if handle.tell() == 0:
            writer.writerow(["original_path", "current_path", "file_count", "reason"])
        for source, target, reason in moves:
            amount = move_preserving_files(source, target, ROOT)
            writer.writerow([source.relative_to(ROOT).as_posix(), target.relative_to(ROOT).as_posix(), amount, reason])
            handle.flush()
            count += amount
    print(json.dumps({"moves": len(moves), "files_preserved": count, "report": str(REPORT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
