"""审计 M3-PI Guard 仓库的目录布局、命名规范和文档可迁移性。

深度校验仓库根目录文件白名单、模块源码布局、相对链接有效性以及跨平台路径规范。
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]

PROJECT_DIRECTORIES = (
    "m3_core",
    "m3_guard",
    "m3_eval",
    "m3_attacks",
    "experiments",
    "protocols",
    "schemas",
    "fixtures",
    "tests",
    "scripts",
    "config",
    "sandbox",
    "outputs",
    "external",
    "release",
    "docs",
    "harness",
    "agent",
    "文档资料",
)

ACTIVE_PYTHON_ROOTS = (
    "m3_core",
    "m3_guard",
    "m3_eval",
    "m3_attacks",
    "experiments",
    "scripts",
    "tests",
)

ALLOWED_ROOT_FILES = {
    ".gitattributes",
    ".gitignore",
    "AGENTS.md",
    "Modelfile.qwen25-7b-8k",
    "README.md",
    "jsonl_to_csv.py",
    "pytest.ini",
    "requirements-core.txt",
    "requirements-dashboard.txt",
    "文件夹说明.md",
}

REQUIRED_RENAMED_FILES = {
    "docs/项目移交报告.md",
    "docs/项目完整综述.md",
    "docs/系统架构.md",
    "docs/运行手册.md",
    "docs/数据集说明.md",
    "docs/伦理与适用范围.md",
    "docs/证据索引.md",
    "docs/移交与论文检查清单.md",
    "docs/research/Task_Shield_v1_6_失败分析.md",
    "docs/LLM的千层诱惑.md",
    "docs/比赛材料归档说明_2026-10-06.md",
    "experiments/e17_source_index.md",
    "harness/项目上下文.md",
    "harness/tasks/m3-expansion-001.md",
}

FORBIDDEN_EXACT_NAMES = {
    "docs": {
        "PROJECT_HANDOFF.md",
        "PROJECT_OVERVIEW.md",
        "SYSTEM_ARCHITECTURE.md",
        "RUNBOOK.md",
        "DATASET_CARD.md",
        "ETHICS_AND_SCOPE.md",
        "SUBMISSION_EVIDENCE_INDEX.md",
        "RELEASE_CHECKLIST.md",
        "PPT_result_notes.md",
        "report_v0.3.md",
    },
    "docs/research": {"taskshield_v16_failure_analysis.md"},
    "experiments": {"E17_SOURCE_INDEX.md"},
    "harness": {"PROJECT_CONTEXT.md"},
    "harness/tasks": {"M3-EXPANSION-001.md"},
}

LEGACY_ACTIVE_REFERENCES = (
    "docs/PROJECT_HANDOFF.md",
    "docs\\PROJECT_HANDOFF.md",
    "docs/PROJECT_OVERVIEW.md",
    "docs\\PROJECT_OVERVIEW.md",
    "docs/SYSTEM_ARCHITECTURE.md",
    "docs\\SYSTEM_ARCHITECTURE.md",
    "docs/RUNBOOK.md",
    "docs\\RUNBOOK.md",
    "docs/DATASET_CARD.md",
    "docs\\DATASET_CARD.md",
    "docs/ETHICS_AND_SCOPE.md",
    "docs\\ETHICS_AND_SCOPE.md",
    "docs/SUBMISSION_EVIDENCE_INDEX.md",
    "docs\\SUBMISSION_EVIDENCE_INDEX.md",
    "docs/RELEASE_CHECKLIST.md",
    "docs\\RELEASE_CHECKLIST.md",
    "harness/PROJECT_CONTEXT.md",
    "harness\\PROJECT_CONTEXT.md",
    "taskshield_v16_failure_analysis.md",
    "docs/PPT_result_notes.md",
    "docs\\PPT_result_notes.md",
    "docs/report_v0.3.md",
    "docs\\report_v0.3.md",
    "experiments/E17_SOURCE_INDEX.md",
    "experiments\\E17_SOURCE_INDEX.md",
    "harness/tasks/M3-EXPANSION-001.md",
    "harness\\tasks\\M3-EXPANSION-001.md",
)

SNAKE_NAME = re.compile(r"^_*(?:[a-z][a-z0-9_]*|_+)$")
CONSTANT_NAME = re.compile(r"^_*[A-Z][A-Z0-9_]*$")
CLASS_NAME = re.compile(r"^_*[A-Z][A-Za-z0-9]*$")
UNITTEST_HOOKS = {"setUp", "tearDown", "setUpClass", "tearDownClass"}
ACTIVE_INDEX_DOCUMENTS = (
    "README.md",
    "docs/README.md",
    "docs/项目完整综述.md",
    "文件夹说明.md",
)
ACTIVE_PORTABLE_ARTIFACTS = (
    "protocols/paper_upgrade_v1/agentdojo_official_strong_baseline_capability_audit_v1.json",
    "protocols/paper_upgrade_v1/agentdojo_official_strong_baseline_capability_audit_v1.md",
    "protocols/paper_upgrade_v1/baseline_registry_audit_v1.json",
    "protocols/paper_upgrade_v1/baseline_registry_audit_v1.md",
    "protocols/paper_upgrade_v1/camel_fides_ifc_adapter_preflight_v1.json",
    "protocols/paper_upgrade_v1/camel_fides_ifc_adapter_preflight_v1.md",
    "protocols/paper_upgrade_v1/camel_official_source_smoke_v1.json",
    "protocols/paper_upgrade_v1/camel_official_source_smoke_v1.md",
    "protocols/paper_upgrade_v1/external_strong_baseline_source_audit_v1.json",
    "protocols/paper_upgrade_v1/external_strong_baseline_source_audit_v1.md",
    "protocols/paper_upgrade_v1/injecagent_official_compatibility_audit_v1.json",
    "protocols/paper_upgrade_v1/injecagent_official_compatibility_audit_v1.md",
    "protocols/paper_upgrade_v1/ipiguard_official_source_smoke_v1.json",
    "protocols/paper_upgrade_v1/ipiguard_official_source_smoke_v1.md",
    "protocols/paper_upgrade_v1/ipiguard_source_backed_import_preflight_v1.json",
    "protocols/paper_upgrade_v1/ipiguard_source_backed_import_preflight_v1.md",
    "protocols/paper_upgrade_v1/ipiguard_tdg_adapter_preflight_v1.json",
    "protocols/paper_upgrade_v1/ipiguard_tdg_adapter_preflight_v1.md",
    "protocols/paper_upgrade_v1/progent_official_source_smoke_v1.json",
    "protocols/paper_upgrade_v1/progent_official_source_smoke_v1.md",
    "protocols/paper_upgrade_v1/progent_policy_adapter_preflight_v1.json",
    "protocols/paper_upgrade_v1/progent_policy_adapter_preflight_v1.md",
    "protocols/paper_upgrade_v1/progent_source_backed_import_preflight_v1.json",
    "protocols/paper_upgrade_v1/progent_source_backed_import_preflight_v1.md",
    "protocols/paper_upgrade_v1/promptguard_detector_adapter_preflight_v1.json",
    "protocols/paper_upgrade_v1/promptguard_detector_adapter_preflight_v1.md",
    "protocols/paper_upgrade_v1/strong_baseline_dependency_snapshot_v1.json",
    "protocols/paper_upgrade_v1/strong_baseline_dependency_snapshot_v1.md",
    "protocols/paper_upgrade_v1/strong_baseline_source_checkout_manifest_v1.json",
    "protocols/paper_upgrade_v1/strong_baseline_source_checkout_manifest_v1.md",
    "protocols/paper_upgrade_v1/taskshield_alignment_adapter_preflight_v1.json",
    "protocols/paper_upgrade_v1/taskshield_alignment_adapter_preflight_v1.md",
    "protocols/paper_upgrade_v1/q2_readiness_audit_v1.json",
    "protocols/paper_upgrade_v1/q2_readiness_audit_v1.md",
    "protocols/paper_upgrade_v1/strong_baseline_formal_readiness_audit_v1.json",
    "protocols/paper_upgrade_v1/strong_baseline_formal_readiness_audit_v1.md",
    "protocols/paper_upgrade_v1/public_benchmark_result_completeness_audit_v2.json",
    "protocols/paper_upgrade_v1/public_benchmark_result_completeness_audit_v2.md",
    "protocols/paper_upgrade_v1/public_benchmark_formal_run_plan_v1.json",
    "protocols/paper_upgrade_v1/public_benchmark_formal_run_plan_v1.md",
    "protocols/paper_upgrade_v1/public_benchmark_formal_run_plan_v2.json",
    "protocols/paper_upgrade_v1/public_benchmark_formal_run_plan_v2.md",
    "protocols/paper_upgrade_v1/m3_v2_independent_blind_admission_audit_v2.json",
    "protocols/paper_upgrade_v1/m3_v2_independent_blind_admission_audit_v2.md",
    "protocols/paper_upgrade_v1/m3_v2_independent_blind_formal_admission_v1.json",
    "protocols/paper_upgrade_v1/paper_v1_evidence_index_v1.json",
    "protocols/paper_upgrade_v1/execution/q2_formal_execution_plan_v1.json",
    "protocols/paper_upgrade_v1/execution/q2_formal_execution_plan_v1.md",
    "protocols/paper_upgrade_v1/execution/q2_to_80_action_audit_v1.json",
    "protocols/paper_upgrade_v1/execution/q2_to_80_action_audit_v1.md",
    (
        "protocols/paper_upgrade_v1/monitors/tool_filter_formal_v1/"
        "agentdojo_official_formal_run_monitor_v1.json"
    ),
    (
        "protocols/paper_upgrade_v1/monitors/tool_filter_formal_v1/"
        "agentdojo_official_formal_run_monitor_v1.md"
    ),
    "protocols/paper_upgrade_v1/agentdojo_official_formal_run_monitor_v1.json",
    (
        "protocols/paper_upgrade_v1/monitors/transformers_pi_detector_formal_v2/"
        "agentdojo_official_formal_run_monitor_v1.json"
    ),
    (
        "protocols/paper_upgrade_v1/monitors/adaptive_mcts_budget_v1/"
        "adaptive_mcts_budget_formal_monitor_v1.json"
    ),
    (
        "protocols/paper_upgrade_v1/diagnostics/agentdojo_transformers_detector_failure_v1/"
        "failure_diagnostic.json"
    ),
    "protocols/paper_upgrade_v1/agentdojo_tool_filter_formal_admission_v1.json",
    "protocols/paper_upgrade_v1/admissions/task_shield_formal_admission_v1.json",
    "protocols/paper_upgrade_v1/admissions/progent_formal_admission_v1.json",
    "protocols/paper_upgrade_v1/admissions/camel_or_fides_formal_admission_v1.json",
    "protocols/paper_upgrade_v1/admissions/ipiguard_formal_admission_v1.json",
    (
        "outputs/paper_upgrade_v1/baselines/agentdojo_tool_filter_official_formal_v1/"
        "analysis/analysis_manifest.json"
    ),
    "outputs/paper_upgrade_v1/public_benchmark_formal_runs/run_plan_manifest.json",
    "outputs/paper_upgrade_v1/public_benchmark_formal_runs/formal_cell_queue.jsonl",
    "outputs/paper_upgrade_v1/public_benchmark_formal_runs_v2/run_plan_manifest.json",
    "outputs/paper_upgrade_v1/public_benchmark_formal_runs_v2/formal_cell_queue.jsonl",
)

CURRENT_FORMAL_IDENTITY_SHA256 = (
    "c89a3f7a51becdf1c6809d206a2c3a57bca5d53c51ec084ce18176714a328ef9"
)
LEGACY_FORMAL_IDENTITY_SHA256 = (
    "a785085cbf0aa904ddbf7a924926dae1834e40795755c547640f0892abe48432"
)

# 共享的正式运行身份辅助文件有意保持为活跃代码。较早冻结的失败/诊断根绑定旧版本，
# Progent v1.3 则绑定当前版本。不得原地改写这些历史冻结；这里只允许已知的精确
# “期望值/观察值”组合，使未来再次发生辅助文件漂移时审计仍会失败。
HASH_BOUND_IDENTITY_DRIFT_EXCEPTIONS = {
    (
        "protocols/paper_upgrade_v1/camel_source_backed_formal_freeze_v1.json:formal_analyzer",
        "experiments/paper_v1/benchmarks/analyze_camel_source_backed_formal.py",
        "ee92ba26b5fbd6fdef83fa9f84d91a10ec070af7a499a9ccfe33b3ced7f66e87",
        "78eb4ff717a8128d14baf1ac79cc4c5d16129cb113b1125f570a32a97c23bbf4",
    ),
    (
        "protocols/paper_upgrade_v1/camel_source_backed_formal_freeze_v1.json:formal_runner",
        "experiments/paper_v1/benchmarks/run_camel_source_backed_formal.py",
        "532a27638acab64ff85296222bc35fe7ceede11be068e93bcf09872fc1c4f658",
        "dd644394c4d7ca16a0a7379afcdce54d5bc483b176c79651a20b7b4f5c6cd25a",
    ),
    (
        "protocols/paper_upgrade_v1/camel_source_backed_formal_freeze_v1.json:shared_identity",
        "experiments/paper_v1/benchmarks/formal_run_identity.py",
        LEGACY_FORMAL_IDENTITY_SHA256,
        CURRENT_FORMAL_IDENTITY_SHA256,
    ),
    (
        "protocols/paper_upgrade_v1/progent_source_backed_formal_freeze_v1.json:shared_identity",
        "experiments/paper_v1/benchmarks/formal_run_identity.py",
        LEGACY_FORMAL_IDENTITY_SHA256,
        CURRENT_FORMAL_IDENTITY_SHA256,
    ),
    (
        "protocols/paper_upgrade_v1/taskshield_paper_formal_freeze_v1.json:resume_identity_helper",
        "experiments/paper_v1/benchmarks/formal_run_identity.py",
        LEGACY_FORMAL_IDENTITY_SHA256,
        CURRENT_FORMAL_IDENTITY_SHA256,
    ),
    (
        "protocols/paper_upgrade_v1/taskshield_paper_formal_freeze_v13.json:resume_identity_helper",
        "experiments/paper_v1/benchmarks/formal_run_identity.py",
        LEGACY_FORMAL_IDENTITY_SHA256,
        CURRENT_FORMAL_IDENTITY_SHA256,
    ),
    (
        "protocols/paper_upgrade_v1/taskshield_paper_formal_freeze_v14.json:resume_identity_helper",
        "experiments/paper_v1/benchmarks/formal_run_identity.py",
        LEGACY_FORMAL_IDENTITY_SHA256,
        CURRENT_FORMAL_IDENTITY_SHA256,
    ),
    (
        "protocols/paper_upgrade_v1/taskshield_paper_formal_freeze_v15.json:resume_identity_helper",
        "experiments/paper_v1/benchmarks/formal_run_identity.py",
        LEGACY_FORMAL_IDENTITY_SHA256,
        CURRENT_FORMAL_IDENTITY_SHA256,
    ),
    (
        "protocols/paper_upgrade_v1/taskshield_paper_formal_freeze_v16.json:resume_identity_helper",
        "experiments/paper_v1/benchmarks/formal_run_identity.py",
        LEGACY_FORMAL_IDENTITY_SHA256,
        CURRENT_FORMAL_IDENTITY_SHA256,
    ),
}
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
CHECKOUT_SPECIFIC_ABSOLUTE_PATH = re.compile(
    r"(?i)\b[A-Z]:[\\/][^\r\n]{0,200}M3_PI_Guard_test(?:[\\/]|(?=[`'\"\s;,.]))"
)


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    details: list[str]


def _relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _result(name: str, details: Iterable[str]) -> CheckResult:
    detail_list = sorted(set(details))
    return CheckResult(name=name, passed=not detail_list, details=detail_list)


def check_top_level_directories() -> CheckResult:
    missing = [name for name in PROJECT_DIRECTORIES if not (ROOT / name).is_dir()]
    return _result("top_level_directories", missing)


def check_root_files() -> CheckResult:
    observed = {path.name for path in ROOT.iterdir() if path.is_file()}
    unexpected = sorted(observed - ALLOWED_ROOT_FILES)
    missing = sorted(ALLOWED_ROOT_FILES - observed)
    details = [f"unexpected:{name}" for name in unexpected]
    details.extend(f"missing:{name}" for name in missing)
    return _result("root_file_allowlist", details)


def check_renamed_files() -> CheckResult:
    details: list[str] = []
    for relative in REQUIRED_RENAMED_FILES:
        if not (ROOT / relative).is_file():
            details.append(f"missing_new_path:{relative}")
    for directory, forbidden_names in FORBIDDEN_EXACT_NAMES.items():
        actual_names = {path.name for path in (ROOT / directory).iterdir()}
        for name in sorted(actual_names & forbidden_names):
            details.append(f"legacy_exact_name:{directory}/{name}")
    return _result("approved_file_renames", details)


def _python_files() -> Iterable[Path]:
    for root_name in ACTIVE_PYTHON_ROOTS:
        yield from (ROOT / root_name).rglob("*.py")
    yield ROOT / "jsonl_to_csv.py"


def check_python_filenames() -> CheckResult:
    details: list[str] = []
    for path in _python_files():
        stem = path.stem
        if stem == "__init__":
            continue
        if not SNAKE_NAME.fullmatch(stem):
            details.append(_relative(path))
    return _result("python_filenames", details)


def check_python_identifiers() -> CheckResult:
    details: list[str] = []
    for path in _python_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError, UnicodeDecodeError) as exc:
            details.append(f"parse_error:{_relative(path)}:{exc}")
            continue
        module_aliases: set[tuple[int, str]] = set()
        for statement in tree.body:
            targets: list[ast.expr] = []
            if isinstance(statement, ast.Assign):
                targets.extend(statement.targets)
            elif isinstance(statement, ast.AnnAssign):
                targets.append(statement.target)
            for target in targets:
                if isinstance(target, ast.Name) and CLASS_NAME.fullmatch(target.id):
                    module_aliases.add((target.lineno, target.id))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name not in UNITTEST_HOOKS and not SNAKE_NAME.fullmatch(node.name):
                    details.append(f"function:{_relative(path)}:{node.lineno}:{node.name}")
            elif isinstance(node, ast.ClassDef):
                if not CLASS_NAME.fullmatch(node.name):
                    details.append(f"class:{_relative(path)}:{node.lineno}:{node.name}")
            elif isinstance(node, ast.arg):
                if not SNAKE_NAME.fullmatch(node.arg):
                    details.append(f"argument:{_relative(path)}:{node.lineno}:{node.arg}")
            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                valid_assignment = bool(
                    SNAKE_NAME.fullmatch(node.id)
                    or CONSTANT_NAME.fullmatch(node.id)
                    or (node.lineno, node.id) in module_aliases
                )
                if not valid_assignment:
                    details.append(f"variable:{_relative(path)}:{node.lineno}:{node.id}")
    return _result("python_identifiers", details)


def _active_reference_files() -> Iterable[Path]:
    fixed_files = (ROOT / "README.md", ROOT / "文件夹说明.md")
    yield from fixed_files
    scan_roots = (
        ROOT / "docs",
        ROOT / "experiments",
        ROOT / "scripts",
        ROOT / "tests",
        ROOT / "harness" / "scripts",
        ROOT / "harness" / "docs",
        ROOT / "harness" / "specs",
        ROOT / "harness" / "tasks",
    )
    for scan_root in scan_roots:
        for path in scan_root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {".md", ".py", ".ps1", ".sh", ".json", ".yaml"}:
                continue
            relative = _relative(path)
            if relative.startswith("docs/archive/") or relative.startswith("harness/workspaces/"):
                continue
            if relative == "scripts/audit_project_conventions.py":
                continue
            yield path


def check_legacy_references() -> CheckResult:
    details: list[str] = []
    for path in _active_reference_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for legacy in LEGACY_ACTIVE_REFERENCES:
            if legacy in text:
                details.append(f"{_relative(path)}:{legacy}")
    return _result("legacy_active_references", details)


def check_overview_coverage() -> CheckResult:
    overview = ROOT / "docs" / "项目完整综述.md"
    if not overview.is_file():
        return _result("overview_directory_coverage", ["missing:docs/项目完整综述.md"])
    text = overview.read_text(encoding="utf-8")
    missing = [name for name in PROJECT_DIRECTORIES if f"`{name}/`" not in text]
    return _result("overview_directory_coverage", missing)


def check_active_document_links() -> CheckResult:
    details: list[str] = []
    for relative in ACTIVE_INDEX_DOCUMENTS:
        document = ROOT / relative
        if not document.is_file():
            details.append(f"missing_document:{relative}")
            continue
        text = document.read_text(encoding="utf-8")
        for raw_target in MARKDOWN_LINK.findall(text):
            target = raw_target.strip().strip("<>")
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc or target.startswith("#"):
                continue
            target_path = unquote(parsed.path)
            if not target_path:
                continue
            resolved = document.parent.joinpath(*PurePosixPath(target_path).parts).resolve()
            if not resolved.exists():
                details.append(f"{relative}:{target}")
    return _result("active_document_links", details)


def _portability_files() -> Iterable[Path]:
    fixed_files = (
        ROOT / "README.md",
        ROOT / "文件夹说明.md",
        ROOT / "harness" / "README.md",
        ROOT / "harness" / "state" / "current-task.md",
    )
    yield from fixed_files
    yield from (ROOT / relative for relative in ACTIVE_PORTABLE_ARTIFACTS)
    scan_roots = (
        ROOT / "docs",
        ROOT / "m3_core",
        ROOT / "m3_guard",
        ROOT / "m3_eval",
        ROOT / "m3_attacks",
        ROOT / "experiments",
        ROOT / "scripts",
        ROOT / "tests",
        ROOT / "config",
        ROOT / "harness" / "docs",
        ROOT / "harness" / "specs",
        ROOT / "harness" / "tasks",
    )
    frozen_files = _frozen_file_paths() | _hash_bound_file_paths()
    for scan_root in scan_roots:
        for path in scan_root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {
                ".md", ".py", ".ps1", ".sh", ".json", ".jsonl", ".yaml", ".yml"
            }:
                continue
            relative = _relative(path)
            if relative.startswith("docs/archive/") or relative == "config/project.local.env":
                continue
            if relative in frozen_files or relative == "scripts/audit_project_conventions.py":
                continue
            yield path


def check_checkout_path_portability() -> CheckResult:
    details: list[str] = []
    for path in _portability_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for match in CHECKOUT_SPECIFIC_ABSOLUTE_PATH.finditer(text):
            line_number = text.count("\n", 0, match.start()) + 1
            details.append(f"{_relative(path)}:{line_number}")
    return _result("checkout_path_portability", details)


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )


def check_local_config_boundary() -> CheckResult:
    details: list[str] = []
    tracked = _git("ls-files", "--error-unmatch", "config/project.local.env")
    if tracked.returncode == 0:
        details.append("config/project.local.env_is_tracked")
    ignored = _git("check-ignore", "config/project.local.env")
    if ignored.returncode != 0:
        details.append("config/project.local.env_is_not_ignored")
    model_files = _git("ls-files", "models", "ollama_models").stdout.splitlines()
    details.extend(f"tracked_model:{path}" for path in model_files if path.strip())
    return _result("local_config_and_model_boundary", details)


def _frozen_file_paths() -> set[str]:
    paths: set[str] = set()
    attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8").splitlines()
    for line in attributes:
        stripped = line.strip()
        if not stripped.startswith("/") or " -text" not in stripped:
            continue
        pattern = stripped.split()[0].lstrip("/")
        if not pattern.endswith("/**") and "*" not in pattern:
            paths.add(pattern)
    return paths


def _hash_bound_file_paths() -> set[str]:
    """发现由不可变固化清单按哈希绑定的活跃文件路径。"""

    paths: set[str] = set()
    for _, candidate, _ in _hash_bound_file_bindings():
        try:
            paths.add(candidate.resolve().relative_to(ROOT.resolve()).as_posix())
        except ValueError:
            continue
    return paths


def _resolve_hash_bound_candidate(raw_path: object) -> Path:
    candidate = Path(str(raw_path))
    if not candidate.is_absolute():
        return (ROOT / candidate).resolve()
    try:
        candidate.resolve().relative_to(ROOT.resolve())
        return candidate.resolve()
    except ValueError:
        pass
    known_roots = {name.casefold() for name in PROJECT_DIRECTORIES}
    for index, part in enumerate(candidate.parts):
        if part.casefold() not in known_roots:
            continue
        relocated = ROOT.joinpath(*candidate.parts[index:]).resolve()
        if relocated.exists():
            return relocated
    return candidate.resolve()


def _hash_bound_file_bindings() -> list[tuple[str, Path, str]]:
    """从每个固化清单中返回标签、当前候选路径和预期的哈希值。"""

    bindings: list[tuple[str, Path, str]] = []
    freeze_root = ROOT / "protocols" / "paper_upgrade_v1"
    if not freeze_root.is_dir():
        return bindings
    for manifest_path in freeze_root.rglob("*freeze*.json"):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(manifest, dict):
            continue
        adapter = manifest.get("local_adapter", {})
        files = adapter.get("files", {}) if isinstance(adapter, dict) else {}
        hashes = adapter.get("sha256", {}) if isinstance(adapter, dict) else {}
        if not isinstance(files, dict):
            continue
        if not isinstance(hashes, dict):
            hashes = {}
        manifest_label = manifest_path.relative_to(ROOT).as_posix()
        for name, raw_path in files.items():
            label = f"{manifest_label}:{name}"
            bindings.append(
                (label, _resolve_hash_bound_candidate(raw_path), str(hashes.get(name, "")))
            )
    return bindings


def check_hash_bound_file_identity() -> CheckResult:
    details: list[str] = []
    for label, path, expected_sha256 in _hash_bound_file_bindings():
        display = _relative(path) if path.is_relative_to(ROOT) else str(path)
        if not path.is_file():
            details.append(f"missing:{display}:{label}")
            continue
        if not expected_sha256:
            details.append(f"missing_expected_sha256:{display}:{label}")
            continue
        observed = hashlib.sha256(path.read_bytes()).hexdigest()
        if observed != expected_sha256:
            exception_key = (label, display, expected_sha256, observed)
            if exception_key in HASH_BOUND_IDENTITY_DRIFT_EXCEPTIONS:
                continue
            details.append(f"sha256_mismatch:{display}:{label}")
    return _result("hash_bound_file_identity", details)


def check_frozen_paths_exist() -> CheckResult:
    details: list[str] = []
    attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8").splitlines()
    for line in attributes:
        stripped = line.strip()
        if not stripped.startswith("/") or " -text" not in stripped:
            continue
        pattern = stripped.split()[0].lstrip("/")
        if pattern.endswith("/**"):
            path = ROOT / pattern[:-3]
            if not path.is_dir():
                details.append(f"missing_frozen_directory:{pattern[:-3]}")
        elif "*" not in pattern and not (ROOT / pattern).is_file():
            details.append(f"missing_frozen_file:{pattern}")
    return _result("frozen_paths_exist", details)


def run_audit() -> dict[str, object]:
    checks = [
        check_top_level_directories(),
        check_root_files(),
        check_renamed_files(),
        check_python_filenames(),
        check_python_identifiers(),
        check_legacy_references(),
        check_overview_coverage(),
        check_active_document_links(),
        check_checkout_path_portability(),
        check_local_config_boundary(),
        check_frozen_paths_exist(),
        check_hash_bound_file_identity(),
    ]
    failed = [check.name for check in checks if not check.passed]
    return {
        "schema_version": "m3-project-conventions-audit-1.0",
        "status": "pass" if not failed else "fail",
        "passed_checks": len(checks) - len(failed),
        "total_checks": len(checks),
        "failed_checks": failed,
        "checks": [asdict(check) for check in checks],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Run the audit and return nonzero on failure.")
    parser.parse_args(argv)

    report = run_audit()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
