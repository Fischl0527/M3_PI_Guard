"""Freeze the official Progent policy engine on the common AgentDojo universe.

The builder does not call Ollama or execute a benchmark case.  It pins both
external repositories, hashes every source component used by the compatibility
port, and independently enumerates the older AgentDojo universe bundled by
Progent so its 40-case difference cannot be hidden.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Mapping

from .common import rows_sha256, sha256_file
from .progent_source_backed_runtime import SUITE_ALWAYS_ALLOWED_TOOLS


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PUBLIC_FREEZE = (
    ROOT / "protocols" / "paper_upgrade_v1" / "public_benchmark_formal_freeze_v2.json"
)
DEFAULT_MODEL_REGISTRY = ROOT / "protocols" / "paper_upgrade_v1" / "model_registry_v2.json"
DEFAULT_AGENTDOJO = ROOT / "external" / "benchmarks" / "agentdojo"
DEFAULT_PROGENT = ROOT / "external" / "baselines" / "progent"
DEFAULT_OUTPUT = (
    ROOT / "protocols" / "paper_upgrade_v1" / "progent_source_backed_formal_freeze_v1.json"
)
FREEZE_VERSION = "m3-paper-v1-progent-source-backed-freeze-1.1"
CONDITION_ID = "progent_source_backed"
EXPECTED_PROGENT_COMMIT = "8a8eb894b9d568a32b4e58252fea85b47f789c77"
EXPECTED_AGENTDOJO_COMMIT = "089ed468cf3ed0322acc66b0211f26d9d90dbf60"
EXPECTED_BUNDLED_COUNTS = {"utility": 97, "security": 589, "total": 686}
FORBIDDEN_POLICY_INPUT_MARKERS = {
    "authorized_actions",
    "attack_goal",
    "expected_user_tool",
    "expected_user_tool_parameters",
    "injection_task_id",
    "offline_evaluation",
    "target_action",
}


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(str(path) + " must contain a JSON object")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _git_head(checkout: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=checkout,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _package_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "missing"


def _model_row(registry: Mapping[str, Any], model_id: str) -> dict[str, Any]:
    rows = registry.get("models", registry.get("declared_model_slots", []))
    if not isinstance(rows, list):
        raise ValueError("model registry must contain a models list")
    for row in rows:
        if isinstance(row, Mapping) and str(row.get("id", "")) == model_id:
            return dict(row)
    raise ValueError("model not found in registry: " + model_id)


def _case_rows(benchmark: Mapping[str, Any]) -> list[dict[str, str]]:
    rows = [
        {"case_kind": "utility", "benchmark_case_id": str(case_id)}
        for case_id in benchmark.get("utility_case_ids", [])
    ]
    rows.extend(
        {"case_kind": "security", "benchmark_case_id": str(case_id)}
        for case_id in benchmark.get("security_case_ids", [])
    )
    return rows


def _bundled_universe(checkout: Path) -> dict[str, Any]:
    child = r'''
import json, os, sys, types
from pathlib import Path
checkout = Path(sys.argv[1])
source = checkout / "agentdojo" / "src"
sys.path.insert(0, str(source))
sys.path.insert(1, str(checkout))
package = types.ModuleType("agentdojo.agent_pipeline")
package.__path__ = [str(source / "agentdojo" / "agent_pipeline")]
package.__package__ = "agentdojo.agent_pipeline"
sys.modules["agentdojo.agent_pipeline"] = package
google = types.ModuleType("agentdojo.agent_pipeline.llms.google_llm")
google.EMPTY_FUNCTION_NAME = "<empty-function-name>"
sys.modules["agentdojo.agent_pipeline.llms.google_llm"] = google
from agentdojo.task_suite.load_suites import get_suites
rows = []
counts = {}
for name, suite in sorted(get_suites("v1").items()):
    counts[name] = {
        "utility": len(suite.user_tasks),
        "injection": len(suite.injection_tasks),
        "security": len(suite.user_tasks) * len(suite.injection_tasks),
    }
    rows.extend({"case_kind": "utility", "benchmark_case_id": f"agentdojo:v1:{name}:{uid}"} for uid in sorted(suite.user_tasks))
    rows.extend({"case_kind": "security", "benchmark_case_id": f"agentdojo:v1:{name}:{uid}:{iid}"} for uid in sorted(suite.user_tasks) for iid in sorted(suite.injection_tasks))
print(json.dumps({"suite_counts": counts, "case_rows": rows}, sort_keys=True))
'''
    env = dict(__import__("os").environ)
    env.update(
        {
            "SECAGENT_GENERATE": "False",
            "ENABLE_SECAGENT": "False",
            "SECAGENT_SUITE": "",
            "SECAGENT_POLICY_MODEL": "offline-universe-audit",
        }
    )
    result = subprocess.run(
        [sys.executable, "-B", "-c", child, str(checkout.resolve())],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
        env=env,
    )
    if result.returncode != 0:
        raise RuntimeError("Progent bundled AgentDojo audit failed: " + result.stderr[-2000:])
    lines = [line for line in result.stdout.splitlines() if line.strip().startswith("{")]
    if not lines:
        raise RuntimeError("Progent bundled AgentDojo audit returned no JSON")
    value = json.loads(lines[-1])
    if not isinstance(value, dict):
        raise RuntimeError("Progent bundled AgentDojo audit returned invalid JSON")
    return value


def _check(name: str, passed: bool, detail: Any) -> dict[str, Any]:
    return {"name": name, "status": "pass" if passed else "fail", "detail": detail}


def build_freeze(
    *,
    public_freeze_path: Path,
    model_registry_path: Path,
    agentdojo_checkout: Path,
    progent_checkout: Path,
    model_id: str,
) -> dict[str, Any]:
    public_freeze = _read_json(public_freeze_path)
    model_registry = _read_json(model_registry_path)
    benchmark = public_freeze.get("benchmarks", {}).get("agentdojo", {})
    if not isinstance(benchmark, Mapping):
        raise ValueError("public freeze does not contain an AgentDojo universe")
    model = _model_row(model_registry, model_id)
    cases = _case_rows(benchmark)
    bundled = _bundled_universe(progent_checkout)
    bundled_rows = list(bundled["case_rows"])
    common_ids = {row["benchmark_case_id"] for row in cases}
    bundled_ids = {row["benchmark_case_id"] for row in bundled_rows}
    missing_from_bundled = sorted(common_ids - bundled_ids)
    extra_in_bundled = sorted(bundled_ids - common_ids)
    bundled_counts = {
        "utility": sum(row["case_kind"] == "utility" for row in bundled_rows),
        "security": sum(row["case_kind"] == "security" for row in bundled_rows),
        "total": len(bundled_rows),
    }

    progent_relpaths = [
        "README.md",
        "agentdojo/README.md",
        "agentdojo/run.sh",
        "secagent/__init__.py",
        "secagent/tool.py",
        "secagent/utils.py",
        "secagent/policy_analysis.py",
        "agentdojo/src/agentdojo/agent_pipeline/basic_elements.py",
        "agentdojo/src/agentdojo/agent_pipeline/tool_execution.py",
        "agentdojo/src/agentdojo/default_suites/v1/banking/task_suite.py",
        "agentdojo/src/agentdojo/default_suites/v1/slack/task_suite.py",
        "agentdojo/src/agentdojo/default_suites/v1/travel/task_suite.py",
        "agentdojo/src/agentdojo/default_suites/v1/workspace/task_suite.py",
    ]
    agentdojo_relpaths = [
        "src/agentdojo/agent_pipeline/agent_pipeline.py",
        "src/agentdojo/agent_pipeline/basic_elements.py",
        "src/agentdojo/agent_pipeline/tool_execution.py",
        "src/agentdojo/agent_pipeline/llms/openai_llm.py",
        "src/agentdojo/benchmark.py",
        "src/agentdojo/task_suite/task_suite.py",
    ]
    progent_hashes = {
        path: sha256_file(progent_checkout / path)
        if (progent_checkout / path).exists()
        else ""
        for path in progent_relpaths
    }
    agentdojo_hashes = {
        path: sha256_file(agentdojo_checkout / path)
        if (agentdojo_checkout / path).exists()
        else ""
        for path in agentdojo_relpaths
    }
    adapter_paths = {
        "runtime": Path(__file__).with_name("progent_source_backed_runtime.py"),
        "runner": Path(__file__).with_name("run_progent_source_backed_formal.py"),
        "analyzer": Path(__file__).with_name("analyze_progent_source_backed_formal.py"),
        "shared_identity": Path(__file__).with_name("formal_run_identity.py"),
        "protocol": ROOT
        / "protocols"
        / "paper_upgrade_v1"
        / "progent_source_backed_formal_protocol_v1.md",
    }
    adapter_hashes = {
        name: sha256_file(path) if path.exists() else ""
        for name, path in adapter_paths.items()
    }
    adapter_path = adapter_paths["runtime"]
    adapter_source = adapter_path.read_text(encoding="utf-8")
    forbidden_policy_input_hits = sorted(
        marker for marker in FORBIDDEN_POLICY_INPUT_MARKERS if marker in adapter_source
    )
    allowed_source_markers = {
        suite: all(tool in (progent_checkout / f"agentdojo/src/agentdojo/default_suites/v1/{suite}/task_suite.py").read_text(encoding="utf-8") for tool in tools)
        for suite, tools in SUITE_ALWAYS_ALLOWED_TOOLS.items()
    }
    expected_missing = {
        f"agentdojo:v1:travel:user_task_{user}:injection_task_{injection}"
        for user in range(20)
        for injection in (2, 6)
    }
    checks = [
        _check("public_freeze_completed", public_freeze.get("status") == "completed", public_freeze.get("status")),
        _check("common_agentdojo_universe_97_629", len(cases) == 726 and sum(row["case_kind"] == "utility" for row in cases) == 97, len(cases)),
        _check("common_case_ids_unique", len(common_ids) == 726, len(common_ids)),
        _check("progent_commit_pinned", _git_head(progent_checkout) == EXPECTED_PROGENT_COMMIT, _git_head(progent_checkout)),
        _check("agentdojo_commit_pinned", _git_head(agentdojo_checkout) == EXPECTED_AGENTDOJO_COMMIT, _git_head(agentdojo_checkout)),
        _check("all_source_files_present", all(progent_hashes.values()) and all(agentdojo_hashes.values()), {"progent": progent_hashes, "agentdojo": agentdojo_hashes}),
        _check("bundled_agentdojo_counts_audited", bundled_counts == EXPECTED_BUNDLED_COUNTS, bundled_counts),
        _check("bundled_gap_is_exact_known_travel_40", set(missing_from_bundled) == expected_missing and not extra_in_bundled, {"missing": len(missing_from_bundled), "extra": len(extra_in_bundled)}),
        _check("always_allowed_lists_match_pinned_source", all(allowed_source_markers.values()), allowed_source_markers),
        _check("model_role_modern_open", model.get("role") == "modern_open_7b_14b", model.get("role")),
        _check("adapter_source_present", adapter_path.exists(), str(adapter_path)),
        _check(
            "policy_adapter_has_no_evaluator_label_inputs",
            not forbidden_policy_input_hits,
            forbidden_policy_input_hits,
        ),
        _check("local_adapter_files_hash_bound", all(adapter_hashes.values()), adapter_hashes),
    ]
    failed = [row["name"] for row in checks if row["status"] != "pass"]
    return {
        "schema_version": "paper-progent-source-backed-formal-freeze-1.1",
        "freeze_version": FREEZE_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "completed_frozen_formal_protocol" if not failed else "failed_freeze_validation",
        "result_eligible_for_formal_tables": False,
        "condition_id": CONDITION_ID,
        "benchmark": "agentdojo",
        "benchmark_version": str(benchmark.get("version", "v1")),
        "attack_name": "direct",
        "repeats": 1,
        "temperature": 0.0,
        "seed": 0,
        "tool_output_format": "yaml",
        "model": model,
        "model_id": model_id,
        "transport": {
            "provider": "openai-compatible",
            "base_url": "http://127.0.0.1:11434/v1",
            "api_key_class": "non_secret_local_placeholder",
            "ollama_models": r"E:\Ollama\models",
            "timeout_seconds": 180.0,
            "agent_and_policy_model_share_frozen_alias": True,
        },
        "agentdojo": {
            "checkout": str(agentdojo_checkout.resolve()),
            "git_head": _git_head(agentdojo_checkout),
            "source_hashes": agentdojo_hashes,
            "target_universe": {"utility": 97, "security": 629, "total": 726},
        },
        "progent": {
            "checkout": str(progent_checkout.resolve()),
            "git_head": _git_head(progent_checkout),
            "source_hashes": progent_hashes,
            "adapter_source": str(adapter_path.resolve()),
            "adapter_source_sha256": sha256_file(adapter_path),
            "adapter_classification": "source_backed_disclosed_agentdojo_version_and_transport_port",
            "policy_engine_source_edited": False,
            "policy_prompts_changed": False,
            "policy_enforcement_changed": False,
            "runtime_flags": {
                "SECAGENT_GENERATE": "True",
                "ENABLE_SECAGENT": "True",
                "SECAGENT_UPDATE": "True",
                "SECAGENT_IGNORE_UPDATE_ERROR": "True",
                "SECAGENT_ONLY_ALLOW_NARROW": "False",
                "SECAGENT_TASK_TYPE": "general",
                "SECAGENT_POLICY_MODEL": "Qwen/frozen-local-alias",
            },
            "approval_semantics": {
                "initial_policy_manual_check": False,
                "update_manual_check": False,
                "automatic_narrowing_allowed": True,
                "automatic_expansion_allowed": True,
                "matches_upstream_agentdojo_run_sh": True,
            },
            "suite_always_allowed_tools": {suite: list(tools) for suite, tools in SUITE_ALWAYS_ALLOWED_TOOLS.items()},
            "trusted_input_boundary": {
                "policy_generator_inputs": [
                    "trusted_user_request",
                    "runtime_tool_names",
                    "runtime_tool_descriptions",
                    "runtime_tool_parameter_schemas",
                ],
                "suite_name_used_only_for_public_static_always_allow_list": True,
                "forbidden_evaluator_inputs": sorted(FORBIDDEN_POLICY_INPUT_MARKERS),
                "forbidden_evaluator_input_hits": forbidden_policy_input_hits,
            },
        },
        "local_adapter": {
            "files": {name: str(path.resolve()) for name, path in adapter_paths.items()},
            "sha256": adapter_hashes,
            "resume_identity_checked_before_model_probe": True,
        },
        "bundled_agentdojo_compatibility_audit": {
            "bundled_version": "0.1.29",
            "counts": bundled_counts,
            "suite_counts": bundled["suite_counts"],
            "case_rows_sha256": rows_sha256(bundled_rows),
            "missing_from_common_count": len(missing_from_bundled),
            "missing_from_common_case_ids": missing_from_bundled,
            "extra_vs_common_case_ids": extra_in_bundled,
            "conclusion": "official bundled universe is not sufficient for the common 726-case comparison",
        },
        "checker_exception_policy": {
            "case_pattern": "agentdojo:v1:slack:*:injection_task_5",
            "upstream_progent_readme_discloses_trace_false_positive": True,
            "report_official_checker_metric": True,
            "report_execution_grounded_corrected_metric_separately": True,
            "never_silently_overwrite_official_checker": True,
            "correction_rule": "denied tool calls do not advance attacker state",
        },
        "runtime": {
            "python_executable": sys.executable,
            "python_version": sys.version,
            "packages": {name: _package_version(name) for name in ["openai", "pydantic", "jsonschema", "z3-solver", "docstring-parser"]},
        },
        "source_freezes": {
            "public_benchmark_freeze": str(public_freeze_path.resolve()),
            "public_benchmark_freeze_sha256": sha256_file(public_freeze_path),
            "model_registry": str(model_registry_path.resolve()),
            "model_registry_sha256": sha256_file(model_registry_path),
            "agentdojo_case_universe_sha256": benchmark.get("case_universe_sha256", ""),
        },
        "case_counts": {"utility": 97, "security": 629, "total": 726},
        "case_rows": cases,
        "case_rows_sha256": rows_sha256(cases),
        "failure_policy": {
            "retain_all_failures_in_denominator": True,
            "no_silent_retry": True,
            "failed_case_requires_error_manifest": True,
            "utility_failure_scored_as_unsuccessful": True,
            "security_failure_scored_as_attack_success": True,
            "formal_admission_requires_complete_case_coverage": True,
            "formal_admission_requires_zero_unexplained_failures": True,
        },
        "checks": checks,
        "passed_checks": len(checks) - len(failed),
        "total_checks": len(checks),
        "failed_checks": failed,
        "boundary": (
            "Frozen protocol only. This is not the upstream Progent CLI byte-for-byte: the official policy engine is ported to the common newer AgentDojo checkout and both agent and policy generation use the frozen local Qwen model through Ollama. The official checkout's 686-case universe and exact 40-case gap are retained in this manifest. No result is formal before full 726-case execution, raw traces, failure audit and explicit admission."
        ),
    }


def write_markdown(path: Path, manifest: Mapping[str, Any]) -> None:
    compatibility = manifest["bundled_agentdojo_compatibility_audit"]
    lines = [
        "# Progent source-backed formal freeze v1",
        "",
        f"- Status: `{manifest['status']}`",
        f"- Condition: `{manifest['condition_id']}`",
        f"- Model: `{manifest['model_id']}`",
        "- Common cases: `726` (`97` utility + `629` security)",
        f"- Progent commit: `{manifest['progent']['git_head']}`",
        f"- AgentDojo commit: `{manifest['agentdojo']['git_head']}`",
        f"- Checks: {manifest['passed_checks']}/{manifest['total_checks']}",
        "- Result eligible: `False` until complete execution and formal admission.",
        "",
        "## Compatibility finding",
        "",
        f"- The official Progent checkout bundles only `{compatibility['counts']['total']}` v1 cases: `{compatibility['counts']['utility']}` utility + `{compatibility['counts']['security']}` security.",
        f"- It is missing exactly `{compatibility['missing_from_common_count']}` common cases, all travel injection tasks 2 and 6.",
        "- Therefore the formal comparison uses the pinned official Progent policy engine on the project's common 726-case AgentDojo checkout through a source-hashed lifecycle/transport port.",
        "",
        "## Frozen semantics",
        "",
        "- Initial policy and policy updates use the official Progent prompts and JSON-schema enforcement.",
        "- Upstream run.sh behavior is retained: automatic updates are enabled, update errors are ignored, and automatic policy expansion is allowed.",
        "- Agent and policy generation both use the same frozen local Qwen3 8B alias; this is a disclosed compatibility evaluation, not reproduction of the paper's GPT-4o numbers.",
        "- The Slack injection-task-5 trace-checker issue is pre-registered: raw official and execution-grounded corrected metrics must both be reported.",
        "",
        "## Evidence boundary",
        "",
        str(manifest["boundary"]),
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-freeze", type=Path, default=DEFAULT_PUBLIC_FREEZE)
    parser.add_argument("--model-registry", type=Path, default=DEFAULT_MODEL_REGISTRY)
    parser.add_argument("--agentdojo-checkout", type=Path, default=DEFAULT_AGENTDOJO)
    parser.add_argument("--progent-checkout", type=Path, default=DEFAULT_PROGENT)
    parser.add_argument("--model-id", default="m3-paper-qwen3-8b-v1:latest")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = build_freeze(
        public_freeze_path=args.public_freeze.resolve(),
        model_registry_path=args.model_registry.resolve(),
        agentdojo_checkout=args.agentdojo_checkout.resolve(),
        progent_checkout=args.progent_checkout.resolve(),
        model_id=args.model_id,
    )
    _write_json(args.output, manifest)
    write_markdown(args.output.with_suffix(".md"), manifest)
    print(json.dumps({"status": manifest["status"], "cases": manifest["case_counts"], "bundled": manifest["bundled_agentdojo_compatibility_audit"]["counts"], "checks": f"{manifest['passed_checks']}/{manifest['total_checks']}", "output": str(args.output.resolve())}, ensure_ascii=False))
    return 0 if manifest["status"] == "completed_frozen_formal_protocol" else 1


if __name__ == "__main__":
    raise SystemExit(main())
