"""Audit the pinned IPIGuard source checkout for official TDG wiring markers.

This audit is intentionally non-experimental.  It reads the pinned external
IPIGuard source checkout and verifies that the expected official source
structure is present:

* the evaluation entry point wires ``defense_name=ipiguard`` into AgentDojo;
* the AgentDojo fork registers an ``ipiguard`` pipeline branch;
* the branch constructs and traverses a directed tool graph;
* the traversal separates whitelist query functions from command functions;
* the bundled dataset universe matches the official public script counts.

It does not import the package, install dependencies, call APIs, execute a
model, run AgentDojo/InjecAgent/M3 cases or produce formal baseline results.
"""

from __future__ import annotations

import argparse
import ast
import json
import py_compile
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .common import portable_path, portable_value, rows_sha256, sha256_file


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PREFLIGHT = ROOT / "protocols" / "paper_upgrade_v1" / "ipiguard_tdg_adapter_preflight_v1.json"
DEFAULT_OUTPUT = ROOT / "protocols" / "paper_upgrade_v1"
DEFAULT_CHECKOUT = ROOT / "external" / "baselines" / "ipiguard"
AUDIT_STEM = "ipiguard_official_source_smoke_v1"
AUDIT_VERSION = "m3-paper-v1-ipiguard-official-source-smoke-1.0"
EXPECTED_USER_TASK_COUNTS = {
    "banking": 16,
    "workspace": 40,
    "slack": 21,
    "travel": 20,
}
EXPECTED_INJECTION_TASK_COUNTS = {
    "banking": 9,
    "workspace": 6,
    "slack": 5,
    "travel": 7,
}
REQUIRED_FILES = {
    "readme": "README.md",
    "eval_shell": "eval.sh",
    "run_eval": "run/eval.py",
    "run_data_module": "run/data_module.py",
    "agent_pipeline": "agentdojo/src/agentdojo/agent_pipeline/agent_pipeline.py",
    "tool_execution": "agentdojo/src/agentdojo/agent_pipeline/tool_execution.py",
    "ipiguard_llm": "agentdojo/src/agentdojo/agent_pipeline/llms/ipiguard_llm.py",
    "tool_whitelist": "agentdojo/src/agentdojo/default_suites/v1/tools/tool_white_list.py",
}
SYNTAX_COMPILE_KEYS = {
    "run_eval",
    "run_data_module",
    "agent_pipeline",
    "tool_execution",
    "ipiguard_llm",
    "tool_whitelist",
}
MARKER_GROUPS = {
    "evaluation_entrypoint": {
        "file": "run_eval",
        "markers": [
            "HfArgumentParser(ScriptArguments)",
            "defense=script_args.defense_name",
            "initialize_dataset",
            "save_result",
            "mode",
            "uid",
            "iid",
        ],
    },
    "ipiguard_pipeline_wiring": {
        "file": "agent_pipeline",
        "markers": [
            'config.defense == "ipiguard"',
            "OpenAIConstructLLM",
            "OpenAITraverseLLM",
            "DagToolsExecutor",
            "DagToolsExecutionLoop",
        ],
    },
    "dag_construction": {
        "file": "ipiguard_llm",
        "markers": [
            "class OpenAIConstructLLM",
            "def construct_dag",
            "nx.DiGraph()",
            "depends_on",
            "dag.add_edge",
            'extra_args["dag"]',
        ],
    },
    "dag_traversal_and_repair": {
        "file": "ipiguard_llm",
        "markers": [
            "class OpenAITraverseLLM",
            "def query_args_update",
            "def query_node_expansion",
            "def query_response",
            "def query_reflection",
            "topological_sort",
        ],
    },
    "dag_execution_loop": {
        "file": "tool_execution",
        "markers": [
            "class DagToolsExecutionLoop",
            "topological_sort(dag)",
            'extra_args["current_tool_call"]',
            "class DagToolsExecutor",
            "query_node_expansion",
        ],
    },
    "whitelist_command_split": {
        "file": "tool_execution",
        "markers": [
            "from agentdojo.default_suites.v1.tools.tool_white_list import whitelist",
            "current_tool_call.function in whitelist",
            "new_commands.append",
            "New tool call success",
        ],
    },
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _path(path: Path) -> str:
    return portable_path(path, root=ROOT)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(str(path) + " must contain a JSON object")
    return value


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _git_head(path: Path) -> str:
    if not (path / ".git").exists():
        return ""
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception:
        return ""
    return result.stdout.strip()


def _file_profile(checkout: Path, key: str, relative_path: str) -> dict[str, Any]:
    path = checkout / relative_path
    exists = path.exists()
    text = path.read_text(encoding="utf-8", errors="replace") if exists else ""
    return {
        "key": key,
        "relative_path": relative_path,
        "path": _path(path),
        "exists": exists,
        "sha256": sha256_file(path) if exists else "",
        "line_count": text.count("\n") + (1 if text else 0),
    }


def _syntax_compile(path: Path) -> dict[str, Any]:
    try:
        py_compile.compile(str(path), doraise=True)
    except Exception as exc:
        return {"path": _path(path), "syntax_ok": False, "error": str(exc)}
    return {"path": _path(path), "syntax_ok": True, "error": ""}


def _marker_scan(file_texts: Mapping[str, str]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for group_name, spec in MARKER_GROUPS.items():
        file_key = str(spec["file"])
        text = file_texts.get(file_key, "")
        markers = [str(item) for item in spec["markers"]]
        missing = [marker for marker in markers if marker not in text]
        result[group_name] = {
            "file": file_key,
            "markers": markers,
            "missing_markers": missing,
            "passed": not missing,
        }
    return result


def _literal_dict_assignments(path: Path) -> dict[str, Any]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    values: dict[str, Any] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in {
                "user_task_num",
                "injection_task_num",
            }:
                values[target.id] = ast.literal_eval(node.value)
    return values


def _dataset_universe(checkout: Path) -> dict[str, Any]:
    path = checkout / REQUIRED_FILES["run_data_module"]
    if not path.exists():
        return {
            "path": _path(path),
            "parsed": False,
            "user_task_num": {},
            "injection_task_num": {},
            "matches_expected_counts": False,
            "expected_case_counts": {},
            "total_benign_user_tasks": 0,
            "total_attack_pairs": 0,
            "error": "run/data_module.py missing",
        }
    try:
        assignments = _literal_dict_assignments(path)
    except Exception as exc:
        return {
            "path": _path(path),
            "parsed": False,
            "user_task_num": {},
            "injection_task_num": {},
            "matches_expected_counts": False,
            "expected_case_counts": {},
            "total_benign_user_tasks": 0,
            "total_attack_pairs": 0,
            "error": str(exc),
        }
    user_counts = {
        str(key): int(value)
        for key, value in dict(assignments.get("user_task_num", {})).items()
    }
    injection_counts = {
        str(key): int(value)
        for key, value in dict(assignments.get("injection_task_num", {})).items()
    }
    expected_case_counts = {
        suite: user_counts.get(suite, 0) * injection_counts.get(suite, 0)
        for suite in sorted(set(user_counts) | set(injection_counts))
    }
    return {
        "path": _path(path),
        "parsed": True,
        "user_task_num": user_counts,
        "injection_task_num": injection_counts,
        "matches_expected_counts": (
            user_counts == EXPECTED_USER_TASK_COUNTS
            and injection_counts == EXPECTED_INJECTION_TASK_COUNTS
        ),
        "expected_case_counts": expected_case_counts,
        "total_benign_user_tasks": sum(user_counts.values()),
        "total_attack_pairs": sum(expected_case_counts.values()),
        "error": "",
    }


def _check(name: str, passed: bool, *, detail: Any = None, severity: str = "error") -> dict[str, Any]:
    return {
        "name": name,
        "status": "pass" if passed else "fail",
        "severity": severity,
        "detail": detail,
    }


def _render_markdown(manifest: Mapping[str, Any]) -> str:
    checks = manifest.get("checks", [])
    source = manifest.get("source_checkout", {})
    files = manifest.get("required_files", {})
    marker_groups = manifest.get("marker_groups", {})
    dataset = manifest.get("dataset_universe", {})
    lines = [
        "# IPIGuard official source smoke v1",
        "",
        f"Generated: {manifest['created_at']}",
        "",
        "## Result",
        "",
        f"- Status: `{manifest['status']}`",
        f"- Formal result eligible: `{manifest['result_eligible_for_formal_tables']}`",
        f"- Checks passed: {manifest['summary']['passed_checks']}/{manifest['summary']['total_checks']}",
        "",
        "## Source checkout",
        "",
        f"- Path: `{source.get('checkout_path', '')}`",
        f"- Git HEAD: `{source.get('git_head', '')}`",
        f"- Expected commit: `{source.get('expected_commit', '')}`",
        f"- Matches expected: `{source.get('matches_expected_commit', False)}`",
        "",
        "## Required source files",
        "",
        "| Key | Exists | Lines | SHA-256 |",
        "|---|---:|---:|---|",
    ]
    for key, profile in files.items():
        lines.append(
            f"| `{key}` | `{profile['exists']}` | {profile['line_count']} | `{profile['sha256']}` |"
        )
    lines.extend(
        [
            "",
            "## Marker groups",
            "",
            "| Group | Source file | Passed | Missing markers |",
            "|---|---|---:|---|",
        ]
    )
    for group, scan in marker_groups.items():
        missing = ", ".join(f"`{item}`" for item in scan.get("missing_markers", [])) or "-"
        lines.append(
            f"| `{group}` | `{scan.get('file', '')}` | `{scan.get('passed', False)}` | {missing} |"
        )
    lines.extend(
        [
            "",
            "## Dataset universe parsed from official script",
            "",
            f"- Parsed: `{dataset.get('parsed', False)}`",
            f"- User task counts: `{dataset.get('user_task_num', {})}`",
            f"- Injection task counts: `{dataset.get('injection_task_num', {})}`",
            f"- Total benign user tasks: `{dataset.get('total_benign_user_tasks', 0)}`",
            f"- Total attack pairs: `{dataset.get('total_attack_pairs', 0)}`",
            "",
            "## Checks",
            "",
            "| Check | Status | Severity |",
            "|---|---|---|",
        ]
    )
    for check in checks:
        lines.append(f"| `{check['name']}` | `{check['status']}` | `{check['severity']}` |")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            str(manifest["boundary"]),
            "",
        ]
    )
    return "\n".join(lines)


def build_ipiguard_source_smoke(
    *,
    preflight_path: Path = DEFAULT_PREFLIGHT,
    checkout_path: Path = DEFAULT_CHECKOUT,
    output_dir: Path = DEFAULT_OUTPUT,
) -> dict[str, Any]:
    preflight = _read_json(preflight_path)
    expected_commit = str(preflight.get("config", {}).get("expected_commit", ""))
    git_head = _git_head(checkout_path)
    file_profiles = {
        key: _file_profile(checkout_path, key, relative)
        for key, relative in REQUIRED_FILES.items()
    }
    file_texts = {
        key: (checkout_path / REQUIRED_FILES[key]).read_text(
            encoding="utf-8",
            errors="replace",
        )
        for key, profile in file_profiles.items()
        if profile["exists"]
    }
    syntax_results = {
        key: _syntax_compile(checkout_path / REQUIRED_FILES[key])
        for key in sorted(SYNTAX_COMPILE_KEYS)
        if file_profiles[key]["exists"]
    }
    marker_groups = _marker_scan(file_texts)
    dataset = _dataset_universe(checkout_path)

    checks = [
        _check("preflight_manifest_present", preflight_path.exists(), detail=_path(preflight_path)),
        _check(
            "preflight_source_ready",
            bool(preflight.get("source_checkout_ready")),
            detail=preflight.get("status"),
        ),
        _check(
            "source_checkout_matches_expected_commit",
            bool(git_head and expected_commit and git_head == expected_commit),
            detail={"git_head": git_head, "expected_commit": expected_commit},
        ),
        _check(
            "required_source_files_present",
            all(profile["exists"] for profile in file_profiles.values()),
            detail={
                key: profile["exists"]
                for key, profile in file_profiles.items()
            },
        ),
        _check(
            "required_source_files_syntax_compile",
            len(syntax_results) == len(SYNTAX_COMPILE_KEYS)
            and all(item["syntax_ok"] for item in syntax_results.values()),
            detail=syntax_results,
        ),
        _check(
            "official_source_marker_groups_present",
            all(scan["passed"] for scan in marker_groups.values()),
            detail=marker_groups,
        ),
        _check(
            "dataset_universe_counts_match_expected_public_script",
            bool(dataset.get("matches_expected_counts")),
            detail=dataset,
        ),
        _check(
            "formal_result_eligibility_remains_false",
            not bool(preflight.get("result_eligible_for_formal_tables")),
            detail=preflight.get("result_eligible_for_formal_tables"),
        ),
    ]
    passed = sum(1 for check in checks if check["status"] == "pass")
    manifest: dict[str, Any] = {
        "schema_version": "paper-ipiguard-official-source-smoke-1.0",
        "audit_version": AUDIT_VERSION,
        "created_at": _utc_now(),
        "status": "completed_source_smoke_only"
        if passed == len(checks)
        else "failed_source_smoke",
        "boundary": (
            "Source smoke only. It verifies pinned IPIGuard code structure and "
            "official TDG wiring markers without importing dependencies, calling "
            "APIs, executing models or scoring any benchmark case. Formal result "
            "eligibility remains false until an accepted source-backed adapter "
            "runs complete cells with raw logs and materializer admission."
        ),
        "result_eligible_for_formal_tables": False,
        "preflight_manifest": {
            "path": _path(preflight_path),
            "sha256": sha256_file(preflight_path) if preflight_path.exists() else "",
            "status": preflight.get("status", "missing"),
        },
        "source_checkout": {
            "checkout_path": _path(checkout_path),
            "expected_commit": expected_commit,
            "git_head": git_head,
            "matches_expected_commit": bool(git_head and expected_commit and git_head == expected_commit),
            "python_executable": sys.executable,
            "python_version": sys.version.split()[0],
        },
        "required_files": file_profiles,
        "syntax_compile": syntax_results,
        "marker_groups": marker_groups,
        "dataset_universe": dataset,
        "checks": checks,
        "checks_sha256": rows_sha256(checks),
        "summary": {
            "total_checks": len(checks),
            "passed_checks": passed,
            "failed_checks": len(checks) - passed,
            "required_file_count": len(file_profiles),
            "marker_group_count": len(marker_groups),
            "syntax_compiled_file_count": len(syntax_results),
        },
        "next_required_for_formal_results": [
            "install/freeze IPIGuard AgentDojo fork dependencies in an isolated environment",
            "build a source-backed adapter that maps frozen M3/AgentDojo/InjecAgent tools into the official TDG flow",
            "run complete formal cells with raw official logs and zero silent skips",
            "materialize results only through the public-benchmark formal-cell gate",
        ],
    }
    manifest = portable_value(manifest, root=ROOT)
    manifest["checks_sha256"] = rows_sha256(manifest["checks"])
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{AUDIT_STEM}.json"
    md_path = output_dir / f"{AUDIT_STEM}.md"
    _write_json(json_path, manifest)
    md_path.write_text(_render_markdown(manifest), encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight", type=Path, default=DEFAULT_PREFLIGHT)
    parser.add_argument("--checkout", type=Path, default=DEFAULT_CHECKOUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    manifest = build_ipiguard_source_smoke(
        preflight_path=args.preflight,
        checkout_path=args.checkout,
        output_dir=args.output_dir,
    )
    print(json.dumps(manifest["summary"], ensure_ascii=False, sort_keys=True))
    return 0 if manifest["status"] == "completed_source_smoke_only" else 1


if __name__ == "__main__":
    raise SystemExit(main())
