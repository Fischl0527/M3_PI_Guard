"""Freeze a source-backed IPIGuard run over the AgentDojo case universe.

The builder is non-executing.  It pins the public 97 utility / 629 security
case universe, the local paper model, the exact IPIGuard checkout, the source
files used by the runtime adapter, and the disclosed optional-provider import
isolation.  No model service or benchmark case is started here.
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


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PUBLIC_FREEZE = (
    ROOT / "protocols" / "paper_upgrade_v1" / "public_benchmark_formal_freeze_v2.json"
)
DEFAULT_MODEL_REGISTRY = ROOT / "protocols" / "paper_upgrade_v1" / "model_registry_v2.json"
DEFAULT_CHECKOUT = ROOT / "external" / "baselines" / "ipiguard"
DEFAULT_OUTPUT = (
    ROOT / "protocols" / "paper_upgrade_v1" / "ipiguard_source_backed_formal_freeze_v1.json"
)
FREEZE_VERSION = "m3-paper-v1-ipiguard-source-backed-freeze-1.1"
CONDITION_ID = "ipiguard_source_backed"
EXPECTED_GOOGLE_EMPTY_FUNCTION_NAME = "<empty-function-name>"


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


def _package_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "missing"


def _git_head(checkout: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=checkout,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


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


def _check(name: str, passed: bool, detail: Any) -> dict[str, Any]:
    return {"name": name, "status": "pass" if passed else "fail", "detail": detail}


def build_freeze(
    *,
    public_freeze_path: Path,
    model_registry_path: Path,
    checkout: Path,
    model_id: str,
) -> dict[str, Any]:
    public_freeze = _read_json(public_freeze_path)
    model_registry = _read_json(model_registry_path)
    benchmark = public_freeze.get("benchmarks", {}).get("agentdojo", {})
    if not isinstance(benchmark, Mapping):
        raise ValueError("public freeze does not contain an AgentDojo universe")
    model = _model_row(model_registry, model_id)
    cases = _case_rows(benchmark)
    utility_count = sum(row["case_kind"] == "utility" for row in cases)
    security_count = sum(row["case_kind"] == "security" for row in cases)

    source_relpaths = [
        "run/eval.py",
        "run/data_module.py",
        "agentdojo/src/agentdojo/agent_pipeline/basic_elements.py",
        "agentdojo/src/agentdojo/agent_pipeline/llms/ipiguard_llm.py",
        "agentdojo/src/agentdojo/agent_pipeline/llms/openai_llm.py",
        "agentdojo/src/agentdojo/agent_pipeline/llms/google_llm.py",
        "agentdojo/src/agentdojo/agent_pipeline/tool_execution.py",
        "agentdojo/src/agentdojo/attacks/baseline_attacks.py",
        "agentdojo/src/agentdojo/task_suite/task_suite.py",
        "agentdojo/src/agentdojo/data/system_messages.yaml",
        "agentdojo/src/agentdojo/default_suites/v1/tools/tool_white_list.py",
    ]
    source_paths = [checkout / relpath for relpath in source_relpaths]
    source_hashes = {
        relpath: sha256_file(path) if path.exists() else ""
        for relpath, path in zip(source_relpaths, source_paths)
    }
    ipiguard_source = (checkout / source_relpaths[3]).read_text(encoding="utf-8")
    execution_source = (checkout / source_relpaths[6]).read_text(encoding="utf-8")
    google_source = (checkout / source_relpaths[5]).read_text(encoding="utf-8")
    empty_constant_marker = (
        f'EMPTY_FUNCTION_NAME = "{EXPECTED_GOOGLE_EMPTY_FUNCTION_NAME}"'
    )
    adapter_paths = {
        "runner": ROOT
        / "experiments"
        / "paper_v1"
        / "benchmarks"
        / "run_ipiguard_source_backed_formal.py",
        "analyzer": ROOT
        / "experiments"
        / "paper_v1"
        / "benchmarks"
        / "analyze_ipiguard_source_backed_formal.py",
        "protocol": ROOT
        / "protocols"
        / "paper_upgrade_v1"
        / "ipiguard_source_backed_formal_protocol_v1.md",
    }
    adapter_hashes = {
        name: sha256_file(path) if path.exists() else ""
        for name, path in adapter_paths.items()
    }

    checks = [
        _check(
            "public_freeze_completed",
            public_freeze.get("status") == "completed",
            public_freeze.get("status"),
        ),
        _check(
            "agentdojo_universe_97_629",
            utility_count == 97 and security_count == 629,
            {"utility": utility_count, "security": security_count},
        ),
        _check("agentdojo_total_726", len(cases) == 726, len(cases)),
        _check(
            "case_ids_unique",
            len({row["benchmark_case_id"] for row in cases}) == len(cases),
            len(cases),
        ),
        _check("model_role_modern_open", model.get("role") == "modern_open_7b_14b", model.get("role")),
        _check("all_source_files_present", all(source_hashes.values()), source_hashes),
        _check(
            "official_ipiguard_components_present",
            all(
                marker in ipiguard_source
                for marker in ["class OpenAIConstructLLM", "class OpenAITraverseLLM", "def construct_dag"]
            )
            and all(
                marker in execution_source
                for marker in ["class DagToolsExecutionLoop", "class DagToolsExecutor", "topological_sort"]
            ),
            "construct/traverse/DAG executor markers",
        ),
        _check(
            "optional_google_constant_exactly_pinned",
            empty_constant_marker in google_source,
            EXPECTED_GOOGLE_EMPTY_FUNCTION_NAME,
        ),
        _check(
            "local_adapter_files_hash_bound",
            all(adapter_hashes.values()),
            adapter_hashes,
        ),
    ]
    failed = [row["name"] for row in checks if row["status"] != "pass"]
    return {
        "schema_version": "paper-ipiguard-source-backed-formal-freeze-1.1",
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
        "model": model,
        "model_id": model_id,
        "transport": {
            "provider": "openai-compatible",
            "base_url": "http://127.0.0.1:11434/v1",
            "api_key_class": "non_secret_local_placeholder",
            "ollama_models": r"E:\Ollama\models",
        },
        "ipiguard": {
            "checkout": str(checkout.resolve()),
            "git_head": _git_head(checkout),
            "source_hashes": source_hashes,
            "source_components": [
                "OpenAIConstructLLM",
                "OpenAITraverseLLM",
                "DagToolsExecutor",
                "DagToolsExecutionLoop",
            ],
            "source_native_attack": "important_instructions",
            "comparison_attack": "direct",
            "adapter_classification": "source_backed_disclosed_transport_and_import_isolation",
        },
        "optional_provider_import_isolation": {
            "reason": (
                "The pinned fork imports the unused Vertex AI provider at package import time. "
                "The runner bypasses that package initializer and supplies only the exact "
                "EMPTY_FUNCTION_NAME constant imported by tool_execution.py. The OpenAI-compatible "
                "IPIGuard construct/traverse and DAG execution source files remain unchanged."
            ),
            "stubbed_module": "agentdojo.agent_pipeline.llms.google_llm",
            "stubbed_symbol": "EMPTY_FUNCTION_NAME",
            "stubbed_value": EXPECTED_GOOGLE_EMPTY_FUNCTION_NAME,
            "pinned_google_source_sha256": source_hashes[
                "agentdojo/src/agentdojo/agent_pipeline/llms/google_llm.py"
            ],
            "algorithm_change": False,
        },
        "local_adapter": {
            "files": {name: str(path.resolve()) for name, path in adapter_paths.items()},
            "sha256": adapter_hashes,
            "raw_construct_output_capture": True,
            "raw_capture_changes_dag_parser": False,
            "raw_capture_changes_prompt": False,
            "raw_capture_changes_selection_rule": False,
        },
        "runtime": {
            "python_executable": sys.executable,
            "python_version": sys.version,
            "packages": {
                name: _package_version(name)
                for name in [
                    "openai",
                    "networkx",
                    "matplotlib",
                    "python-dotenv",
                    "pydantic",
                    "PyYAML",
                ]
            },
        },
        "source_freezes": {
            "public_benchmark_freeze": str(public_freeze_path.resolve()),
            "public_benchmark_freeze_sha256": sha256_file(public_freeze_path),
            "model_registry": str(model_registry_path.resolve()),
            "model_registry_sha256": sha256_file(model_registry_path),
            "agentdojo_case_universe_sha256": benchmark.get("case_universe_sha256", ""),
        },
        "case_counts": {
            "utility": utility_count,
            "security": security_count,
            "total": len(cases),
        },
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
            "This freeze declares a source-backed IPIGuard adapter over the frozen 726-case "
            "AgentDojo universe. It is not the upstream CLI byte-for-byte because the unused "
            "Vertex provider import is isolated and Ollama supplies the OpenAI-compatible model. "
            "The local runner/analyzer/protocol are hash-bound and the runner records raw DAG JSON "
            "before delegating to the unchanged upstream parser. No result is formal until a complete "
            "explicitly admitted run has zero unexplained failures."
        ),
    }


def write_markdown(path: Path, manifest: Mapping[str, Any]) -> None:
    counts = manifest["case_counts"]
    lines = [
        "# IPIGuard source-backed formal freeze v1",
        "",
        f"- Status: `{manifest['status']}`",
        f"- Condition: `{manifest['condition_id']}`",
        f"- Model: `{manifest['model_id']}`",
        f"- Cases: {counts['total']} ({counts['utility']} utility + {counts['security']} security)",
        f"- Attack: `{manifest['attack_name']}`",
        f"- IPIGuard commit: `{manifest['ipiguard']['git_head']}`",
        f"- Checks: {manifest['passed_checks']}/{manifest['total_checks']}",
        "- Result eligible: `False` until complete execution and analysis are admitted.",
        "",
        "## Disclosed compatibility boundary",
        "",
        "- The construct, traverse and DAG executor classes are loaded from the pinned IPIGuard source without editing that checkout.",
        "- The unused Vertex provider package initializer is isolated; the exact upstream empty-function sentinel is pinned and reproduced.",
        "- The agent model is the frozen local Qwen3 8B paper alias through Ollama's OpenAI-compatible endpoint.",
        "- The direct AgentDojo attack is used so this cell matches the other frozen official-baseline cells; the IPIGuard repository's native default is recorded separately.",
        "- All 726 cases must have unique manifests and complete raw traces; qualification and partial runs remain diagnostic.",
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
    parser.add_argument("--checkout", type=Path, default=DEFAULT_CHECKOUT)
    parser.add_argument("--model-id", default="m3-paper-qwen3-8b-v1:latest")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = build_freeze(
        public_freeze_path=args.public_freeze.resolve(),
        model_registry_path=args.model_registry.resolve(),
        checkout=args.checkout.resolve(),
        model_id=args.model_id,
    )
    _write_json(args.output, manifest)
    write_markdown(args.output.with_suffix(".md"), manifest)
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "cases": manifest["case_counts"],
                "checks": f"{manifest['passed_checks']}/{manifest['total_checks']}",
                "output": str(args.output.resolve()),
            },
            ensure_ascii=False,
        )
    )
    return 0 if manifest["status"] == "completed_frozen_formal_protocol" else 1


if __name__ == "__main__":
    raise SystemExit(main())
