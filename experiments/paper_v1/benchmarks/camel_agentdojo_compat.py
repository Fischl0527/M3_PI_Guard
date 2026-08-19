"""Source-backed AgentDojo import compatibility helpers for CaMeL.

CaMeL imports several AgentDojo ``default_suites.v1`` task-suite modules at
module import time.  The pinned AgentDojo package used by the isolated CaMeL
runtime registers default-suite tasks from ``agentdojo.task_suite.__init__`` and
from each suite package ``__init__``.  In a fresh process, importing
``agentdojo.default_suites.v1.banking.task_suite`` can therefore execute
registration modules before ``task_suite.py`` has finished defining
``BankingEnvironment``.  That is a pure import-order cycle, not a CaMeL policy
algorithm.

This module installs a narrow, process-local compatibility preloader:

* do not modify site-packages or the pinned external checkout;
* load official AgentDojo ``task_suite.py`` files from their package paths;
* expose the same public package attributes the upstream ``__init__`` would
  expose;
* then import official registration modules so AgentDojo tasks are still
  registered by their original decorators.

It must be called at the very beginning of a fresh CaMeL runner process, before
``agentdojo.task_suite`` or ``agentdojo.default_suites.v1.<suite>`` are imported
through their regular packages.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
import types
from pathlib import Path
from typing import Any, Iterable

from .common import sha256_file


DEFAULT_SUITES = ("banking", "travel", "workspace", "slack")
DEFAULT_BENCHMARK_VERSIONS = ("v1", "v1.1.1", "v1.1.2", "v1.2")
PRELOAD_VERSION = "m3-paper-v1-camel-agentdojo-suite-import-compat-1.0"
EARLY_IMPORT_BLOCKLIST = (
    "agentdojo.task_suite",
    "agentdojo.default_suites.v1.banking",
    "agentdojo.default_suites.v1.travel",
    "agentdojo.default_suites.v1.workspace",
    "agentdojo.default_suites.v1.slack",
)


def _module_search_root(package: str) -> Path:
    spec = importlib.util.find_spec(package)
    if spec is None or not spec.submodule_search_locations:
        raise ImportError(f"cannot find package search root for {package}")
    return Path(list(spec.submodule_search_locations)[0])


def _load_module_from_path(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot build import spec for {name} at {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _make_package(name: str, path: Path) -> types.ModuleType:
    package = types.ModuleType(name)
    package.__path__ = [str(path)]  # type: ignore[attr-defined]
    package.__package__ = name
    package.__file__ = str(path / "__init__.py")
    return package


def _early_imports_present() -> list[str]:
    return [name for name in EARLY_IMPORT_BLOCKLIST if name in sys.modules]


def install_agentdojo_suite_import_compat(
    *,
    suites: Iterable[str] = DEFAULT_SUITES,
    benchmark_versions: Iterable[str] = DEFAULT_BENCHMARK_VERSIONS,
    allow_already_imported: bool = False,
) -> dict[str, Any]:
    """Install the AgentDojo v1 suite import-order compatibility layer.

    Returns an audit dictionary.  Raises ``RuntimeError`` if the process already
    imported modules that make deterministic preloading unsafe, unless
    ``allow_already_imported`` is explicitly set for diagnostic use.
    """

    suites = tuple(suites)
    benchmark_versions = tuple(benchmark_versions)
    early_imports = _early_imports_present()
    if early_imports and not allow_already_imported:
        raise RuntimeError(
            "CaMeL/AgentDojo compatibility preloader must run before these modules: "
            + ", ".join(early_imports)
        )

    rows: list[dict[str, Any]] = []
    import agentdojo  # noqa: PLC0415

    agentdojo_root = _module_search_root("agentdojo")
    task_suite_pkg_name = "agentdojo.task_suite"
    task_suite_pkg = _make_package(task_suite_pkg_name, agentdojo_root / "task_suite")
    sys.modules[task_suite_pkg_name] = task_suite_pkg
    setattr(agentdojo, "task_suite", task_suite_pkg)

    base_tasks = importlib.import_module("agentdojo.base_tasks")
    task_suite_module = _load_module_from_path(
        "agentdojo.task_suite.task_suite",
        agentdojo_root / "task_suite" / "task_suite.py",
    )
    for attr in ("BaseInjectionTask", "BaseUserTask", "TaskDifficulty"):
        setattr(task_suite_pkg, attr, getattr(base_tasks, attr))
    setattr(task_suite_pkg, "TaskSuite", task_suite_module.TaskSuite)
    setattr(task_suite_pkg, "task_suite", task_suite_module)
    rows.append(
        {
            "kind": "preloaded_module",
            "module": "agentdojo.task_suite.task_suite",
            "path": str(agentdojo_root / "task_suite" / "task_suite.py"),
            "sha256": sha256_file(agentdojo_root / "task_suite" / "task_suite.py"),
            "ok": True,
        }
    )

    import agentdojo.default_suites.v1 as v1  # noqa: PLC0415

    v1_root = _module_search_root("agentdojo.default_suites.v1")
    for suite in suites:
        suite_root = v1_root / suite
        package_name = f"agentdojo.default_suites.v1.{suite}"
        package = _make_package(package_name, suite_root)
        sys.modules[package_name] = package
        setattr(v1, suite, package)

        module_name = f"{package_name}.task_suite"
        module_path = suite_root / "task_suite.py"
        module = _load_module_from_path(module_name, module_path)
        setattr(package, "task_suite", module)
        setattr(package, f"{suite}_task_suite", module.task_suite)
        rows.append(
            {
                "kind": "preloaded_module",
                "module": module_name,
                "path": str(module_path),
                "sha256": sha256_file(module_path),
                "ok": True,
                "tools": len(getattr(module.task_suite, "tools", [])),
            }
        )

    registration_modules = []
    for suite in suites:
        for child in ("injection_tasks", "user_tasks"):
            registration_modules.append(f"agentdojo.default_suites.v1.{suite}.{child}")

    for module_name in registration_modules:
        try:
            module = importlib.import_module(module_name)
            rows.append(
                {
                    "kind": "registration_module",
                    "module": module_name,
                    "path": str(getattr(module, "__file__", "")),
                    "ok": True,
                }
            )
        except Exception as exc:  # pragma: no cover - captured in audit manifest
            rows.append(
                {
                    "kind": "registration_module",
                    "module": module_name,
                    "ok": False,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )

    load_suites = importlib.import_module("agentdojo.task_suite.load_suites")
    setattr(task_suite_pkg, "get_suite", load_suites.get_suite)
    setattr(task_suite_pkg, "get_suites", load_suites.get_suites)
    setattr(task_suite_pkg, "register_suite", load_suites.register_suite)
    rows.append(
        {
            "kind": "preloaded_module",
            "module": "agentdojo.task_suite.load_suites",
            "path": str(getattr(load_suites, "__file__", "")),
            "sha256": sha256_file(Path(str(getattr(load_suites, "__file__", "")))),
            "ok": True,
        }
    )

    suite_counts: dict[str, dict[str, dict[str, int]]] = {}
    for version in benchmark_versions:
        suite_counts[version] = {}
        for suite in suites:
            loaded_suite = load_suites.get_suite(version, suite)
            suite_counts[version][suite] = {
                "user_tasks": len(loaded_suite.user_tasks),
                "injection_tasks": len(loaded_suite.injection_tasks),
                "tools": len(loaded_suite.tools),
            }

    return {
        "compat_version": PRELOAD_VERSION,
        "ok": all(bool(row.get("ok")) for row in rows),
        "early_imports_present": early_imports,
        "suites": list(suites),
        "benchmark_versions": list(benchmark_versions),
        "agentdojo_root": str(agentdojo_root),
        "rows": rows,
        "suite_counts": suite_counts,
    }

