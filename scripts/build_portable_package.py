"""构建限定范围的源码与数据交付包（仅打包指定依赖与公开数据，绝不复制密钥或全库）。

仅打包指定运行入口的源码闭包依赖与公开输入/结果，严格执行路径边界与安全过滤，
杜绝凭据文件（.env、密钥）、内部跟踪信息或宿主系统私有文件外泄。
"""

from __future__ import annotations

# 只打包指定运行入口的源码依赖与公开输入/结果，不复制整个仓库或本地环境。
# 路径校验和复制边界保护凭据、内部追踪及宿主文件；已有包不会证明新改动已验证。
import argparse
import ast
import importlib.util
import json
import shutil
import subprocess
import tarfile
from collections import defaultdict
from pathlib import Path, PurePosixPath, PureWindowsPath

ROOT = Path(__file__).resolve().parents[1]
TEST_NODES = (
    "tests/unit/test_portable_demo.py",
    "tests/unit/test_portable_verify.py",
    "tests/unit/test_corrected_v1_policy.py",
    "tests/unit/test_provenance_corrected_v1.py",
    "tests/unit/test_generic_policy_corrected_v2.py",
    "tests/unit/test_correctness_runtime_v1.py",
    "tests/unit/test_claude_revision_v1.py::test_new_synthetic_pipeline",
)
SOURCE_ROOTS = {"scripts", "m3_core", "m3_guard", "m3_eval", "m3_attacks", "experiments", "tests"}
RAW_FILES = (
    "outputs/experiments/claude_revision_v1/deepseek_pro_raw.jsonl",
    "outputs/experiments/claude_revision_v1/synthetic_regression_raw.jsonl",
    "outputs/experiments/research_followup_20261006_v1/calibration/raw_records.jsonl",
)
RUNTIME_ASSETS = (
    "protocols/paper_upgrade_v2/provider_safety_policy_v1.json",
    "protocols/paper_upgrade_v2/public_budget_policy_v1.json",
    "protocols/paper_upgrade_v2/e6_cross_provider_calibration_v1/cases_deepseek_v1.jsonl",
)


def resolve_module(root: Path, module: str) -> Path | None:
    if module.split(".")[0] not in SOURCE_ROOTS:
        return None
    base = root.joinpath(*module.split("."))
    for candidate in (base.with_suffix(".py"), base / "__init__.py"):
        if candidate.is_file():
            return candidate.relative_to(root)
    return None


def source_closure(root: Path, seeds: list[str]) -> set[Path]:
    """执行静态导入闭包分析，自动递归提取包括包初始化器与函数级导入在内的全部源码依赖树。"""
    queue = [Path(name) for name in seeds]
    found = set()
    while queue:
        relative = queue.pop()
        if relative in found:
            continue
        source = root / relative
        if not source.is_file() or relative.suffix != ".py":
            raise ValueError(f"missing selected source: {relative}")
        found.add(relative)
        for parent in relative.parents:
            if str(parent) != "." and (root / parent / "__init__.py").is_file():
                queue.append(parent / "__init__.py")
        package = list(relative.parent.parts)
        for node in ast.walk(ast.parse(source.read_text(encoding="utf-8-sig"))):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                base = ".".join(package[:len(package) - node.level + 1]) if node.level else ""
                if node.module:
                    base = ".".join(filter(None, (base, node.module)))
                names = [base] + [".".join(filter(None, (base, alias.name))) for alias in node.names if alias.name != "*"]
            for name in names:
                dependency = resolve_module(root, name)
                if dependency is not None:
                    queue.append(dependency)
    return found


def checked_relative(value: str | Path) -> Path:
    relative = PurePosixPath(str(value).replace("\\", "/"))
    if (relative.is_absolute() or PureWindowsPath(str(value)).drive
            or ".." in relative.parts or not relative.parts):
        raise ValueError("package path must stay under the project root")
    if any(part in {"internal", ".git", ".venv", "__pycache__"} for part in relative.parts):
        raise ValueError("private or generated directory excluded from package")
    if relative.name.endswith((".env", ".pem", ".key")) or relative.name.startswith("id_rsa"):
        raise ValueError("credential file excluded from package")
    return Path(*relative.parts)


def copy_public(root: Path, target: Path, relative: str | Path) -> None:
    relative = checked_relative(relative)
    source = root / relative
    if source.is_symlink() or not source.is_file():
        raise ValueError(f"selected file is absent or a symlink: {relative}")
    destination = target / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def export_selected_source_rows(root: Path, target: Path, cases: list[dict]) -> int:
    """在原始行号处保留选定的离线记录，而非导出整个数据集。

    未选中的行保留为空 JSON 对象。现有的单条记录身份与摘要校验保持不变；这些文件是限定范围的摘录，绝不可表述为完整的历史数据集。
    """
    from experiments.paper_v2.contracts import sha256_canonical_json

    selected: dict[Path, dict[int, dict]] = defaultdict(dict)
    for case in cases:
        reference = case["source_reference"]
        relative = checked_relative(reference["path"])
        number = reference["line"]
        if isinstance(number, bool) or not isinstance(number, int) or number < 1:
            raise ValueError("selected source line must be a positive integer")
        selected[relative][number] = reference
    count = 0
    for relative, references in selected.items():
        original = (root / relative).read_text(encoding="utf-8").splitlines()
        lines = ["{}"] * max(references)
        for number, reference in references.items():
            record = json.loads(original[number - 1])
            if sha256_canonical_json(record) != reference["sha256"]:
                raise ValueError("selected source record differs from its existing reference")
            lines[number - 1] = json.dumps(record, ensure_ascii=False)
            count += 1
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return count


def export_agentdojo(target: Path) -> None:
    """对公开固化代码执行全新的浅层克隆，而非直接使用原始 Git 配置。

    现有的原生评测器需要真实的签出目录；绝不可使用伪造标记替换提交检查，也不可为可移植性而削弱该检查。
    """
    from experiments.paper_v2.medium_runtime import (
        DEFAULT_AGENTDOJO_CHECKOUT, FROZEN_AGENTDOJO_COMMIT, _assert_agentdojo_identity,
    )

    _assert_agentdojo_identity()
    destination = target / "external/benchmarks/agentdojo"
    destination.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "clone", "--no-checkout", "--depth", "1", "--no-hardlinks",
                    DEFAULT_AGENTDOJO_CHECKOUT.resolve().as_uri(), str(destination)], check=True)
    subprocess.run(["git", "-C", str(destination), "config", "core.autocrlf", "false"], check=True)
    subprocess.run(["git", "-C", str(destination), "checkout", "--detach", FROZEN_AGENTDOJO_COMMIT], check=True)
    subprocess.run(["git", "-C", str(destination), "remote", "remove", "origin"], check=True)
    _assert_agentdojo_identity(destination)


def write_test_list(target: Path) -> None:
    # Bash word splitting does not discard CR: force portable LF on Windows.
    (target / "pytest-portable.txt").write_text("\n".join(TEST_NODES) + "\n", encoding="utf-8", newline="\n")


def export_compiler_inputs(target: Path) -> None:
    from experiments.paper_v2.correctness_runtime_v1 import _compiler
    from experiments.paper_v2.contracts import compute_online_visible_field_digest
    from experiments.paper_v2.medium_runtime import FROZEN_GENERATED_AT, _runtime_inputs, _source_projection
    from experiments.paper_v2.public_matrix_plan_v1 import _read_source_record

    cases = [json.loads(line) for line in (ROOT / "protocols/paper_upgrade_v2/lean_empirical_case_selection_v1.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    projected = []
    for case in cases:
        reference = case["source_reference"]
        record = _read_source_record({"benchmark": case["benchmark"], "case_id": case["case_id"],
                                      "source_path": reference["path"], "source_line": reference["line"],
                                      "source_record_sha256": reference["sha256"]})
        inputs = _source_projection(record, case["benchmark"])
        if compute_online_visible_field_digest({"agent_input": inputs})["forbidden_fields_present"]:
            raise ValueError("cannot export evaluator fields as online inputs")
        request, context, schemas = _runtime_inputs(inputs, case["benchmark"])
        manifest = _compiler(case["benchmark"], "corrected_v2")(
            trusted_user_request=request, trusted_app_context=context,
            tool_schemas=schemas, generated_at=FROZEN_GENERATED_AT,
        )
        projected.append({"case_id": case["case_id"], "benchmark": case["benchmark"],
                          "online_inputs": inputs, "reference_manifest": manifest.to_dict()})
    path = target / "fixtures/portability/current_online_inputs.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in projected), encoding="utf-8")


def build(output: Path) -> Path:
    if output.exists():
        raise ValueError("select a fresh output directory; never overwrite a previous delivery")
    output.mkdir(parents=True)
    target = output / "M3_PI_Guard_portable"
    target.mkdir()
    seeds = ["scripts/portable_demo.py", "scripts/portable_verify.py",
             "harness/scripts/check_paths.py"] + [node.split("::")[0] for node in TEST_NODES]
    sources = source_closure(ROOT, seeds)
    for relative in sorted(sources):
        copy_public(ROOT, target, relative)
    assets = ["scripts/assets/portable_demo.html", "requirements-portable.txt",
              "protocols/paper_upgrade_v2/lean_empirical_case_selection_v1.jsonl",
              "protocols/paper_upgrade_v2/dual_provider_budget_policy_v1.json",
              "docs/演示与跨环境运行指南.md"]
    for relative in sorted((ROOT / "schemas/paper_v2").rglob("*.json")):
        assets.append(relative.relative_to(ROOT).as_posix())
    for relative in assets + list(RUNTIME_ASSETS) + list(RAW_FILES):
        copy_public(ROOT, target, relative)
    for name in ("LICENSE", "LICENSE.md", "LICENSE.txt"):
        if (ROOT / name).is_file():
            copy_public(ROOT, target, name)
    export_compiler_inputs(target)
    from experiments.paper_v2.correctness_plan_v1 import select_cases

    cases = [json.loads(line) for line in (ROOT / "protocols/paper_upgrade_v2/lean_empirical_case_selection_v1.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    selected_source_records = export_selected_source_rows(ROOT, target, cases + select_cases())
    export_agentdojo(target)
    # Load the verifier's pure functions without relying on package installation.
    spec = importlib.util.spec_from_file_location("portable_counts", ROOT / "scripts/portable_verify.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    reference = module.verify_raw(ROOT)
    (target / "fixtures/portability/reference_counts.json").write_text(json.dumps(reference, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (target / "README.md").write_text((ROOT / "docs/演示与跨环境运行指南.md").read_text(encoding="utf-8"), encoding="utf-8")
    write_test_list(target)
    archive = output / "M3_PI_Guard_portable.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        for file in sorted(target.rglob("*")):
            if file.is_file():
                bundle.add(file, arcname=(Path(target.name) / file.relative_to(target)).as_posix(), recursive=False)
    print(json.dumps({"package": str(target.resolve()), "archive": str(archive.resolve()),
                      "python_sources": len(sources), "api_calls": 0,
                      "selected_source_records": selected_source_records,
                      "scope": "corrected_runtime_selected_tests_inputs_and_raw_counts"}, ensure_ascii=False))
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    build(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
