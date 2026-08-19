"""Index all AgentDojo v1 utility tasks and 629 security task pairs."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from .common import infer_side_effect, json_schema_value_type, rows_sha256


AGENTDOJO_VERSION = "v1"
EXPECTED_UTILITY_TASKS = 97
EXPECTED_SECURITY_CASES = 629


def _tool_schema(function: Any) -> dict[str, Any]:
    raw = function.parameters.model_json_schema()
    required = set(raw.get("required", []))
    properties = raw.get("properties", {})
    return {
        "description": str(function.description),
        "arguments": {
            name: {
                "type": json_schema_value_type(details),
                "required": name in required,
                "description": details.get("description", ""),
            }
            for name, details in sorted(properties.items())
        },
        "side_effect": infer_side_effect(function.name),
    }


def _load_suites(checkout: Path, version: str) -> dict[str, Any]:
    source = str((checkout / "src").resolve())
    if source not in sys.path:
        sys.path.insert(0, source)
    from agentdojo.task_suite.load_suites import get_suites

    return get_suites(version)


def build_agentdojo_index(
    checkout: Path,
    *,
    version: str = AGENTDOJO_VERSION,
) -> dict[str, Any]:
    """Return full compatibility indexes without reading task ground truths."""

    suites = _load_suites(checkout, version)
    utility_rows: list[dict[str, Any]] = []
    security_rows: list[dict[str, Any]] = []
    suite_counts: dict[str, dict[str, int]] = {}

    for suite_name, suite in sorted(suites.items()):
        schemas = {tool.name: _tool_schema(tool) for tool in suite.tools}
        suite_counts[suite_name] = {
            "utility_tasks": len(suite.user_tasks),
            "injection_tasks": len(suite.injection_tasks),
            "security_cases": len(suite.user_tasks) * len(suite.injection_tasks),
            "tools": len(schemas),
        }
        for task_id, task in sorted(suite.user_tasks.items()):
            prompt = str(task.PROMPT)
            utility_rows.append(
                {
                    "schema_version": "public-benchmark-adapter-1.0",
                    "benchmark": "agentdojo",
                    "benchmark_version": version,
                    "record_kind": "utility",
                    "benchmark_case_id": f"agentdojo:{version}:{suite_name}:{task_id}",
                    "suite": suite_name,
                    "user_task_id": task_id,
                    "online_inputs": {
                        "trusted_user_request": prompt,
                        "trusted_app_context": {
                            "benchmark": "agentdojo",
                            "suite": suite_name,
                            "user_task_id": task_id,
                        },
                        "tool_schemas": schemas,
                    },
                    "offline_evaluation": {
                        "offline_only": True,
                        "official_utility_checker": f"{task.__class__.__module__}.{task.__class__.__name__}",
                    },
                    "compatibility": {
                        "index": "compatible",
                        "native_environment": "required",
                        "policy_source": "trusted_prompt_and_tool_schema_only",
                        "ground_truth_used_online": False,
                    },
                }
            )
            for injection_id, injection_task in sorted(suite.injection_tasks.items()):
                security_rows.append(
                    {
                        "schema_version": "public-benchmark-adapter-1.0",
                        "benchmark": "agentdojo",
                        "benchmark_version": version,
                        "record_kind": "security",
                        "benchmark_case_id": (
                            f"agentdojo:{version}:{suite_name}:{task_id}:{injection_id}"
                        ),
                        "suite": suite_name,
                        "user_task_id": task_id,
                        "injection_task_id": injection_id,
                        "online_inputs": {
                            "trusted_user_request": prompt,
                            "trusted_app_context": {
                                "benchmark": "agentdojo",
                                "suite": suite_name,
                                "user_task_id": task_id,
                            },
                            "tool_schemas": schemas,
                            "untrusted_content_source": "official_attack_injection_at_runtime",
                        },
                        "offline_evaluation": {
                            "offline_only": True,
                            "official_security_checker": (
                                f"{injection_task.__class__.__module__}."
                                f"{injection_task.__class__.__name__}"
                            ),
                            "attack_goal": str(injection_task.GOAL),
                        },
                        "compatibility": {
                            "index": "compatible",
                            "native_environment": "required",
                            "policy_source": "trusted_prompt_and_tool_schema_only",
                            "injection_goal_used_online": False,
                            "ground_truth_used_online": False,
                        },
                    }
                )

    if len(utility_rows) != EXPECTED_UTILITY_TASKS:
        raise RuntimeError(
            f"AgentDojo utility count drift: {len(utility_rows)} != {EXPECTED_UTILITY_TASKS}"
        )
    if len(security_rows) != EXPECTED_SECURITY_CASES:
        raise RuntimeError(
            f"AgentDojo security count drift: {len(security_rows)} != {EXPECTED_SECURITY_CASES}"
        )
    return {
        "benchmark": "agentdojo",
        "version": version,
        "utility_rows": utility_rows,
        "security_rows": security_rows,
        "suite_counts": suite_counts,
        "utility_sha256": rows_sha256(utility_rows),
        "security_sha256": rows_sha256(security_rows),
    }
