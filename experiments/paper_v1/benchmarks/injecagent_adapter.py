"""Index all 1,054 InjecAgent cases with explicit offline-label boundaries."""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

from .common import infer_side_effect, rows_sha256


EXPECTED_CASES = 1054


def _load_tool_schemas(checkout: Path) -> dict[str, dict[str, Any]]:
    toolkits = json.loads((checkout / "data" / "tools.json").read_text(encoding="utf-8"))
    schemas: dict[str, dict[str, Any]] = {}
    for toolkit in toolkits:
        prefix = str(toolkit.get("toolkit", ""))
        for tool in toolkit.get("tools", []):
            name = prefix + str(tool.get("name", ""))
            schemas[name] = {
                "description": str(tool.get("summary", "")),
                "arguments": {
                    str(parameter.get("name")): {
                        "type": str(parameter.get("type", "object")),
                        "required": bool(parameter.get("required", False)),
                        "description": str(parameter.get("description", "")),
                    }
                    for parameter in tool.get("parameters", [])
                },
                "side_effect": infer_side_effect(name),
            }
    return schemas


def _parse_parameters(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    try:
        parsed = ast.literal_eval(str(value))
    except (SyntaxError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def build_injecagent_index(checkout: Path) -> dict[str, Any]:
    schemas = _load_tool_schemas(checkout)
    source_files = (
        ("data_security", checkout / "data" / "test_cases_ds_base.json"),
        ("direct_harm", checkout / "data" / "test_cases_dh_base.json"),
    )
    rows: list[dict[str, Any]] = []
    missing_tools: set[str] = set()
    for group, path in source_files:
        source_rows = json.loads(path.read_text(encoding="utf-8"))
        for source_index, source in enumerate(source_rows, 1):
            user_tool = str(source.get("User Tool", ""))
            attacker_tools = [str(value) for value in source.get("Attacker Tools", [])]
            referenced = [user_tool, *attacker_tools]
            missing_tools.update(tool for tool in referenced if tool not in schemas)
            exposed_schemas = {
                tool: schemas[tool] for tool in referenced if tool in schemas
            }
            case_id = f"injecagent:{group}:{source_index:04d}"
            rows.append(
                {
                    "schema_version": "public-benchmark-adapter-1.0",
                    "benchmark": "injecagent",
                    "benchmark_version": "official-release-2024",
                    "record_kind": "security",
                    "benchmark_case_id": case_id,
                    "suite": group,
                    "online_inputs": {
                        "trusted_user_request": str(source.get("User Instruction", "")),
                        "trusted_app_context": {
                            "benchmark": "injecagent",
                            "suite": group,
                        },
                        "tool_schemas": exposed_schemas,
                        "untrusted_content": str(source.get("Tool Response", "")),
                    },
                    "offline_evaluation": {
                        "offline_only": True,
                        "expected_user_tool": user_tool,
                        "expected_user_tool_parameters": _parse_parameters(
                            source.get("Tool Parameters", {})
                        ),
                        "attacker_tools": attacker_tools,
                        "attacker_instruction": str(source.get("Attacker Instruction", "")),
                        "expected_achievement": str(source.get("Expected Achievements", "")),
                        "attack_type": str(source.get("Attack Type", "")),
                    },
                    "compatibility": {
                        "index": "compatible" if not any(
                            tool not in schemas for tool in referenced
                        ) else "missing_tool_schema",
                        "native_environment": "mock_tool_response_replay",
                        "policy_source": "trusted_prompt_context_and_tool_schema_only",
                        "attacker_labels_used_online": False,
                        "gold_user_tool_used_online": False,
                    },
                }
            )
    if len(rows) != EXPECTED_CASES:
        raise RuntimeError(f"InjecAgent count drift: {len(rows)} != {EXPECTED_CASES}")
    return {
        "benchmark": "injecagent",
        "version": "official-release-2024",
        "rows": rows,
        "row_sha256": rows_sha256(rows),
        "tool_schema_count": len(schemas),
        "missing_tools": sorted(missing_tools),
    }
