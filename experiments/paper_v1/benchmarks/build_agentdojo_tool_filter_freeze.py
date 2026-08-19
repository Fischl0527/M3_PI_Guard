"""Freeze the official AgentDojo tool_filter strong-baseline experiment."""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Mapping

from .common import rows_sha256, sha256_bytes, sha256_file


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PUBLIC_FREEZE = (
    ROOT / "protocols" / "paper_upgrade_v1" / "public_benchmark_formal_freeze_v2.json"
)
DEFAULT_MODEL_REGISTRY = ROOT / "protocols" / "paper_upgrade_v1" / "model_registry_v2.json"
DEFAULT_AGENTDOJO = ROOT / "external" / "benchmarks" / "agentdojo"
DEFAULT_OUTPUT = (
    ROOT / "protocols" / "paper_upgrade_v1" / "agentdojo_tool_filter_formal_freeze_v1.json"
)
FREEZE_VERSION = "m3-paper-v1-agentdojo-official-tool-filter-freeze-1.0"
CONDITION_ID = "agentdojo_tool_filter_official"


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
    rows = registry.get("models", [])
    if not isinstance(rows, list):
        raise ValueError("model registry must contain a models list")
    for row in rows:
        if isinstance(row, Mapping) and str(row.get("id", "")) == model_id:
            return dict(row)
    raise ValueError("model not found in registry: " + model_id)


def _case_rows(benchmark: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        *[
            {"case_kind": "utility", "benchmark_case_id": str(case_id)}
            for case_id in benchmark.get("utility_case_ids", [])
        ],
        *[
            {"case_kind": "security", "benchmark_case_id": str(case_id)}
            for case_id in benchmark.get("security_case_ids", [])
        ],
    ]


def _constant_string(source: str, name: str) -> str:
    module = ast.parse(source)
    for node in module.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            value = ast.literal_eval(node.value)
            if isinstance(value, str):
                return value
    raise ValueError("string constant not found: " + name)


def _check(name: str, passed: bool, detail: Any) -> dict[str, Any]:
    return {"name": name, "status": "pass" if passed else "fail", "detail": detail}


def build_freeze(
    *,
    public_freeze_path: Path,
    model_registry_path: Path,
    agentdojo_checkout: Path,
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
    pipeline_path = (
        agentdojo_checkout / "src" / "agentdojo" / "agent_pipeline" / "agent_pipeline.py"
    )
    model_path = agentdojo_checkout / "src" / "agentdojo" / "models.py"
    benchmark_path = agentdojo_checkout / "src" / "agentdojo" / "benchmark.py"
    openai_path = (
        agentdojo_checkout
        / "src"
        / "agentdojo"
        / "agent_pipeline"
        / "llms"
        / "openai_llm.py"
    )
    source_paths = [pipeline_path, model_path, benchmark_path, openai_path]
    source_hashes = {
        str(path.relative_to(agentdojo_checkout)).replace("\\", "/"): sha256_file(path)
        for path in source_paths
    }
    pipeline_text = pipeline_path.read_text(encoding="utf-8")
    model_text = model_path.read_text(encoding="utf-8")
    tool_filter_prompt = _constant_string(pipeline_text, "TOOL_FILTER_PROMPT")
    marker_results = {
        "defense_registered": '"tool_filter"' in pipeline_text,
        "openai_llm_type_guard": "if not isinstance(llm, OpenAILLM)" in pipeline_text,
        "official_filter_component": "OpenAILLMToolFilter(TOOL_FILTER_PROMPT" in pipeline_text,
        "openai_compatible_provider": 'elif provider == "openai-compatible"' in pipeline_text,
        "openai_compatible_model_enum": "OPENAI_COMPATIBLE" in model_text,
    }
    checks = [
        _check("public_freeze_completed", public_freeze.get("status") == "completed", public_freeze.get("status")),
        _check("agentdojo_universe_97_629", utility_count == 97 and security_count == 629, {"utility": utility_count, "security": security_count}),
        _check("agentdojo_total_726", len(cases) == 726, len(cases)),
        _check("case_ids_unique", len({row["benchmark_case_id"] for row in cases}) == len(cases), len(cases)),
        _check("model_role_modern_open", model.get("role") == "modern_open_7b_14b", model.get("role")),
        _check("all_source_files_hashed", all(source_hashes.values()), source_hashes),
        _check("official_tool_filter_markers_present", all(marker_results.values()), marker_results),
        _check("official_prompt_frozen", bool(tool_filter_prompt), sha256_bytes(tool_filter_prompt.encode("utf-8"))),
    ]
    failed = [row["name"] for row in checks if row["status"] != "pass"]
    return {
        "schema_version": "paper-agentdojo-official-tool-filter-formal-freeze-1.0",
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
        },
        "tool_filter": {
            "class": "agentdojo.agent_pipeline.llms.openai_llm.OpenAILLMToolFilter",
            "prompt": tool_filter_prompt,
            "prompt_sha256": sha256_bytes(tool_filter_prompt.encode("utf-8")),
            "filter_model_id": model_id,
            "temperature": 0.0,
            "selection_rule": "retain an official runtime tool when its exact name occurs in the filter-model response",
        },
        "agentdojo": {
            "checkout": str(agentdojo_checkout.resolve()),
            "git_head": _git_head(agentdojo_checkout),
            "source_hashes": source_hashes,
            "official_markers": marker_results,
            "official_pipeline_config": {
                "llm": "OPENAI_COMPATIBLE",
                "defense": "tool_filter",
                "system_message_name": None,
                "tool_output_format": "yaml",
            },
        },
        "runtime": {
            "python_executable": sys.executable,
            "python_version": sys.version,
            "packages": {
                name: _package_version(name)
                for name in ["agentdojo", "openai", "pydantic"]
            },
        },
        "source_freezes": {
            "public_benchmark_freeze": str(public_freeze_path.resolve()),
            "public_benchmark_freeze_sha256": sha256_file(public_freeze_path),
            "model_registry": str(model_registry_path.resolve()),
            "model_registry_sha256": sha256_file(model_registry_path),
            "agentdojo_case_universe_sha256": benchmark.get("case_universe_sha256", ""),
        },
        "case_counts": {"utility": utility_count, "security": security_count, "total": len(cases)},
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
            "This freezes AgentDojo's official tool_filter pipeline over the 726-case "
            "v1 universe using the local OpenAI-compatible model transport. It is not "
            "a result; qualification and full execution remain mandatory."
        ),
    }


def write_markdown(path: Path, manifest: Mapping[str, Any]) -> None:
    counts = manifest["case_counts"]
    lines = [
        "# AgentDojo official tool_filter formal freeze v1",
        "",
        f"- Status: `{manifest['status']}`",
        f"- Condition: `{manifest['condition_id']}`",
        f"- Model/filter model: `{manifest['model_id']}`",
        f"- Cases: {counts['total']} ({counts['utility']} utility + {counts['security']} security)",
        f"- Prompt SHA-256: `{manifest['tool_filter']['prompt_sha256']}`",
        f"- AgentDojo commit: `{manifest['agentdojo']['git_head']}`",
        f"- Checks: {manifest['passed_checks']}/{manifest['total_checks']}",
        "- Result eligible: `False` until qualification, complete execution and analysis pass.",
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
    parser.add_argument("--model-id", default="m3-paper-qwen3-8b-v1:latest")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = build_freeze(
        public_freeze_path=args.public_freeze.resolve(),
        model_registry_path=args.model_registry.resolve(),
        agentdojo_checkout=args.agentdojo_checkout.resolve(),
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
