"""新权限编译研究的数据切分、输入投影和公开元数据资产。

不读取模型结果，不复制历史结果。原生任务沿用源行引用；合成在线输入
和离线评分标签分别保存，编译器入口只接收可信请求、上下文、工具目录。
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Sequence

from experiments.paper_v2.task_contract_synthetic_v1 import (
    SEED, SyntheticTaskBackend, build_synthetic_cases, load_synthetic_case,
)


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "outputs/experiments/task_contract_compiler_v3_validation_v1"
AGENT_UTILITY = ROOT / "outputs/paper_upgrade_v1/public_benchmarks/agentdojo_v1_utility_index.jsonl"
AGENT_SECURITY = ROOT / "outputs/paper_upgrade_v1/public_benchmarks/agentdojo_v1_security_index.jsonl"
AGENT_SOURCE = ROOT / "external/benchmarks/agentdojo/src/agentdojo/default_suites/v1"
DEV_GROUP_QUOTAS = {"banking": 2, "slack": 3, "travel": 4, "workspace": 6}
SENSITIVE_KEYS = frozenset({"offline_evaluation", "expected_graph", "expected_effects", "gold", "evaluator", "response_body", "api_key", "authorization"})


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _digest(value: object) -> str:
    return hashlib.sha256(_json(value).encode()).hexdigest()


@lru_cache(maxsize=12)
def _read_rows(path: Path) -> tuple[dict[str, Any], ...]:
    return tuple(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def _reference(path: Path, line: int, row: Mapping[str, Any]) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(), "line": line, "sha256": _digest(row)}


def _group_rank(group_id: str) -> str:
    return hashlib.sha256((SEED + "\0" + group_id).encode()).hexdigest()


def agentdojo_groups(utility_rows: Sequence[Mapping[str, Any]] | None = None) -> dict[str, list[dict[str, Any]]]:
    """将组合任务与全部原子子任务置于同一连通组。"""
    rows = _read_rows(AGENT_UTILITY) if utility_rows is None else utility_rows
    result: dict[str, list[dict[str, Any]]] = {}
    for suite in DEV_GROUP_QUOTAS:
        nodes = {str(row["user_task_id"]): set() for row in rows if row["suite"] == suite}
        source = (AGENT_SOURCE / suite / "user_tasks.py").read_text(encoding="utf-8")
        pattern = r'create_combined_task\(\s*"UserTask(\d+)".*?user_tasks\["user_task_(\d+)"\].*?user_tasks\["user_task_(\d+)"\]'
        for outer, first, second in re.findall(pattern, source, re.DOTALL):
            for inner in ("user_task_" + first, "user_task_" + second):
                parent = "user_task_" + outer
                if parent not in nodes or inner not in nodes:
                    raise ValueError("native combined task refers to missing indexed task")
                nodes[parent].add(inner)
                nodes[inner].add(parent)
        visited: set[str] = set()
        groups: list[dict[str, Any]] = []
        for node in sorted(nodes):
            if node in visited:
                continue
            pending, members = [node], []
            while pending:
                current = pending.pop()
                if current in visited:
                    continue
                visited.add(current)
                members.append(f"agentdojo:v1:{suite}:{current}")
                pending.extend(nodes[current] - visited)
            members.sort()
            group_id = "|".join(members)
            groups.append({"suite": suite, "cluster_id": group_id, "task_ids": members, "rank": _group_rank(group_id)})
        result[suite] = sorted(groups, key=lambda group: group["rank"])
    if {suite: len(groups) for suite, groups in result.items()} != {"banking": 16, "slack": 13, "travel": 20, "workspace": 26}:
        raise ValueError("native connected-group counts drifted")
    return result


def _native_cases() -> dict[str, list[dict[str, Any]]]:
    utility, security = _read_rows(AGENT_UTILITY), _read_rows(AGENT_SECURITY)
    source_by_id = {row["benchmark_case_id"]: (line, row) for line, row in enumerate(utility, 1)}
    attacks = {row["benchmark_case_id"]: (line, row) for line, row in enumerate(security, 1) if row["compatibility"]["index"] == "compatible"}
    cohorts: dict[str, list[dict[str, Any]]] = {"development": [], "evaluation": []}
    groups = agentdojo_groups(utility)
    for suite, suite_groups in groups.items():
        for split, selected_groups in (
            ("development", suite_groups[:DEV_GROUP_QUOTAS[suite]]),
            ("evaluation", suite_groups[DEV_GROUP_QUOTAS[suite]:]),
        ):
            task_ids = sorted(task for group in selected_groups for task in group["task_ids"])
            selected_attack: dict[str, tuple[int, Mapping[str, Any]]] = {}
            goals = sorted({row["injection_task_id"] for _, row in attacks.values() if row["suite"] == suite})
            # 先覆盖官方注入目标，每目标选择不同底层任务；绝不读结果富集。
            for goal in goals:
                candidates = sorted((case_id, item) for case_id, item in attacks.items()
                                    if item[1]["suite"] == suite and item[1]["injection_task_id"] == goal
                                    and ":".join(case_id.split(":")[:-1]) in task_ids
                                    and ":".join(case_id.split(":")[:-1]) not in selected_attack)
                if candidates:
                    case_id, item = candidates[0]
                    selected_attack[":".join(case_id.split(":")[:-1])] = item
            for task_id in task_ids:
                if task_id not in selected_attack:
                    choices = sorted((case_id, item) for case_id, item in attacks.items() if ":".join(case_id.split(":")[:-1]) == task_id)
                    if not choices:
                        raise ValueError(f"no compatible native attack for {task_id}")
                    selected_attack[task_id] = choices[0][1]
                line, row = source_by_id[task_id]
                attack_line, attack = selected_attack[task_id]
                cluster = next(group["cluster_id"] for group in selected_groups if task_id in group["task_ids"])
                cohorts[split].append({"benchmark": "agentdojo-v1", "base_task_id": task_id,
                    "underlying_task_id": task_id, "case_id": task_id, "split": split,
                    "cluster_id": cluster, "suite": suite, "family": "native_task", "language": "en",
                    "source_reference": _reference(AGENT_UTILITY, line, row),
                    "attack_reference": _reference(AGENT_SECURITY, attack_line, attack),
                    "attack_case_id": attack["benchmark_case_id"], "attack_goal_id": attack["injection_task_id"],
                    "attack_selection": "official_compatible_goal_cover_then_case_id_without_outcomes",
                    "evidence_scope": "previously_exposed_native_version_regression"})
    if (len(cohorts["development"]), len(cohorts["evaluation"])) != (17, 80):
        raise ValueError("expected AgentDojo development17/evaluation80")
    return cohorts


def _m3_cases() -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {"development": [], "evaluation": []}
    for split, original_split in (("development", "validation"), ("evaluation", "sealed_holdout")):
        path = ROOT / f"m3_attacks/cases/paper_v1/m3_v2_{original_split}.jsonl"
        rows = _read_rows(path)
        by_template: dict[str, dict[str, tuple[int, Mapping[str, Any]]]] = {}
        for line, row in enumerate(rows, 1):
            by_template.setdefault(str(row["template_id"]), {})[str(row["case_id"]).rsplit("-", 1)[1]] = (line, row)
        for template_id, members in sorted(by_template.items()):
            line, benign = members["BT"]
            attack_line, attack = members["A2"]
            if attack["scenario_type"] != "legal_tool_under_attack":
                raise ValueError("M3 primary attack must preserve the legal tool task")
            result[split].append({"benchmark": "m3-v2", "base_task_id": template_id,
                "underlying_task_id": template_id, "cluster_id": template_id,
                "case_id": benign["case_id"], "attack_case_id": attack["case_id"],
                "split": split, "original_split": original_split, "family": benign["authorization_profile"],
                "language": benign["language"], "attack_family": attack["attack_family"],
                "source_reference": _reference(path, line, benign), "attack_reference": _reference(path, attack_line, attack),
                "evidence_scope": "automated_parameterized_template_regression_not_independent_blind"})
    if (len(result["development"]), len(result["evaluation"])) != (60, 120):
        raise ValueError("expected M3 development60/evaluation120 templates")
    return result


def build_case_cohorts() -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {"development": [], "evaluation": []}
    for collection in (_native_cases(), _m3_cases()):
        for split in result:
            result[split].extend(collection[split])
    for line, case in enumerate(build_synthetic_cases(), 1):
        result[case["split"]].append({"benchmark": "task-contract-synthetic-v1",
            "base_task_id": case["base_task_id"], "underlying_task_id": case["base_task_id"],
            "case_id": case["base_task_id"], "split": case["split"], "cluster_id": case["base_task_id"],
            "family": case["family"], "language": case["language"],
            "semantic_graph_id": case["semantic_graph_id"],
            "structural_variation": {"selector_fields": case["selector_fields"],
                                     "effect_tool": case["effect_tool"],
                                     "source_read_required": case["needs_read"],
                                     "variation_changes_actual_matching_set": True},
            "action_nodes": len(case["offline_evaluation"]["expected_graph"]["nodes"]),
            "source_reference": {"path": (OUTPUT / "assets/synthetic_online_v1.jsonl").relative_to(ROOT).as_posix(), "line": line},
            "offline_reference": {"path": (OUTPUT / "assets/synthetic_offline_v1.jsonl").relative_to(ROOT).as_posix(), "line": line},
            "attack_selection": "paired_body_injection_same_trusted_task_and_metadata",
            "evidence_scope": "structurally_distinct_programmatic_tasks_eight_shared_generative_families"})
    for split, expected in (("development", 157), ("evaluation", 600)):
        if len(result[split]) != expected:
            raise ValueError(f"{split} task count mismatch")
        if len({row["base_task_id"] for row in result[split]}) != expected:
            raise ValueError("duplicate base task identifier")
    if set(row["base_task_id"] for row in result["development"]) & set(row["base_task_id"] for row in result["evaluation"]):
        raise ValueError("base task development/evaluation overlap")
    return result


def _source_row(reference: Mapping[str, Any]) -> dict[str, Any]:
    path = (ROOT / str(reference["path"])).resolve()
    if not path.is_relative_to(ROOT.resolve()):
        raise ValueError("source reference escapes repository")
    row = copy.deepcopy(_read_rows(path)[int(reference["line"]) - 1])
    if reference.get("sha256") and _digest(row) != reference["sha256"]:
        raise ValueError("source row content differs from selected input")
    return row


def annotate_tool_schemas(schemas: Mapping[str, Any]) -> dict[str, Any]:
    """为原生目录补固定操作与参数角色；不改变既有工具实现。"""
    result = copy.deepcopy(dict(schemas))
    content = {"body", "content", "message", "text", "file_content"}
    targets = {"object_id", "recipient", "recipient_id", "recipients", "to", "channel", "user", "user_id", "member_id", "owner_id", "parent_id", "file_id", "file_path", "path", "source_id", "id", "transaction_id", "reservation_id", "event_id", "email_id", "iban", "endpoint", "url", "user_email"}
    for name, schema in result.items():
        if name.startswith(("search", "list", "lookup")) or name in {"get_all_channels", "get_channel_info"}:
            operation = "discover"
        elif not schema.get("side_effect"):
            operation = "read"
        elif name.startswith(("delete", "remove", "cancel")):
            operation = "delete"
        elif name.startswith(("send", "post")):
            operation = "send"
        elif name.startswith(("create", "book", "schedule", "invite")):
            operation = "create"
        else:
            operation = "modify"
        schema["operation"] = operation
        roles = {}
        for field, argument in schema.get("arguments", {}).items():
            role = "target" if field in targets else "content" if field in content else "query" if operation == "discover" and field in {"query", "query_string", "search_term"} else "value"
            roles[field] = role
            if role in {"content", "query"}:
                argument["allow_generated"] = True
        schema["argument_roles"] = roles
    return result


def load_task_contract_case(base: Mapping[str, Any], scenario: str = "benign") -> dict[str, Any]:
    if scenario not in {"benign", "attack"}:
        raise ValueError("invalid scenario")
    if base["benchmark"] == "task-contract-synthetic-v1":
        reference = base.get("source_reference")
        if reference and (ROOT / str(reference["path"])).exists():
            frozen = _source_row(reference)
            scoring = _source_row(base["offline_reference"])
            if frozen["base_task_id"] != base["base_task_id"] or scoring["base_task_id"] != base["base_task_id"]:
                raise ValueError("frozen synthetic task identity differs")
            online, offline = copy.deepcopy(frozen[scenario]), copy.deepcopy(scoring["offline_evaluation"])
        else:
            online, offline = load_synthetic_case(str(base["base_task_id"]), scenario)
        from experiments.paper_v2.task_contract_synthetic_v1 import corrected_semantic_metadata_v2
        offline = corrected_semantic_metadata_v2(offline)
        return {"live_case": online, "offline_evaluation": offline, "backend": SyntheticTaskBackend(online)}
    source = _source_row(base["attack_reference"] if scenario == "attack" else base["source_reference"])
    offline = copy.deepcopy(source.pop("offline_evaluation", {}))
    if base["benchmark"] == "agentdojo-v1":
        online = copy.deepcopy(source["online_inputs"])
    else:
        from m3_core.policy_compiler import DEFAULT_TOOL_SCHEMAS
        online = {field: copy.deepcopy(source.get(field, [] if field == "untrusted_memory" else {} if field == "trusted_app_context" else ""))
                  for field in ("trusted_user_request", "trusted_app_context", "untrusted_content", "untrusted_memory")}
        online["tool_schemas"] = copy.deepcopy(DEFAULT_TOOL_SCHEMAS)
    online["tool_schemas"] = annotate_tool_schemas(online["tool_schemas"])
    return {"live_case": online, "offline_evaluation": offline, "backend": None,
            "native_source_case": source}


def load_compiler_inputs(base: Mapping[str, Any]) -> dict[str, Any]:
    compile_base = copy.deepcopy(dict(base))
    compile_base["source_reference"] = copy.deepcopy(base.get("compile_source_reference", base.get("benign_source_reference", base["source_reference"])))
    compile_base["case_id"] = base.get("compile_case_id", base["case_id"])
    online = load_task_contract_case(compile_base, "benign")["live_case"]
    result = {field: copy.deepcopy(online[field]) for field in ("trusted_user_request", "trusted_app_context", "tool_schemas")}
    if contains_sensitive_fields(result):
        raise ValueError("offline fields cannot enter compiler inputs")
    return result


def contains_sensitive_fields(value: object) -> bool:
    if isinstance(value, Mapping):
        return any(str(key) in SENSITIVE_KEYS or contains_sensitive_fields(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return any(contains_sensitive_fields(item) for item in value)
    return False


def _write_new_or_same(path: Path, content: str) -> None:
    if path.exists():
        if path.read_text(encoding="utf-8") != content:
            raise FileExistsError(f"refusing to overwrite existing research asset: {path.name}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(content)


def write_case_assets(output: Path = OUTPUT) -> dict[str, Any]:
    output = Path(output).resolve()
    if output != OUTPUT.resolve():
        raise ValueError("study assets must use the approved isolated output directory")
    cohorts = build_case_cohorts()
    online_rows, offline_rows = [], []
    for case in build_synthetic_cases():
        benign, offline = load_synthetic_case(case["base_task_id"], "benign")
        attack, _ = load_synthetic_case(case["base_task_id"], "attack")
        online_rows.append({"base_task_id": case["base_task_id"], "benign": benign, "attack": attack})
        offline_rows.append({"base_task_id": case["base_task_id"], "offline_evaluation": offline})
    files = {"synthetic_online_v1.jsonl": online_rows, "synthetic_offline_v1.jsonl": offline_rows,
             "cases_development_v1.jsonl": cohorts["development"], "cases_evaluation_v1.jsonl": cohorts["evaluation"]}
    for name, rows in files.items():
        _write_new_or_same(output / "assets" / name, "".join(_json(row) + "\n" for row in rows))
    summary = {"schema_version": "task-contract-cases-1.0", "selection_seed": SEED,
        "development_base_tasks": len(cohorts["development"]), "evaluation_base_tasks": len(cohorts["evaluation"]),
        "counts": {split: dict(Counter(row["benchmark"] for row in rows)) for split, rows in cohorts.items()},
        "agentdojo_development_groups": 15, "agentdojo_evaluation_groups": 60,
        "agentdojo_evaluation_compatible_attack_combinations": 522,
        "agentdojo_selected_evaluation_attack_goals": len({(row["suite"], row["attack_goal_id"]) for row in cohorts["evaluation"] if row["benchmark"] == "agentdojo-v1"}),
        "synthetic_unique_semantic_graphs": len({row["semantic_graph_id"] for rows in cohorts.values() for row in rows if "semantic_graph_id" in row}),
        "synthetic_unique_semantic_graphs_by_split": {split: len({row["semantic_graph_id"] for row in rows if "semantic_graph_id" in row}) for split, rows in cohorts.items()},
        "m3_primary_attack": "A2 legal_tool_under_attack; three attack families only",
        "independence_note": "Task IDs, structural uniqueness and independent authorship are distinct; M3 parameter templates and eight shared synthetic generators do not prove population independence.",
        "old_results_read": False, "model_calls": 0, "raw_results_created": False}
    _write_new_or_same(output / "assets/dataset_summary_v1.json", _json(summary) + "\n")
    return summary


def write_semantic_metadata_v2(output: Path = OUTPUT) -> dict[str, Any]:
    """追加经实体join核对的结构元数据；不改v1选择、动作或在线输入。"""
    from experiments.paper_v2.task_contract_synthetic_v1 import corrected_semantic_metadata_v2, semantic_graph, semantic_graph_id
    if Path(output).resolve() != OUTPUT.resolve():
        raise ValueError("semantic metadata must remain in the approved study output")
    rows = []
    for split, cases in build_case_cohorts().items():
        for base in cases:
            if base["benchmark"] != "task-contract-synthetic-v1":
                continue
            frozen = _source_row(base["offline_reference"])["offline_evaluation"]
            repaired = corrected_semantic_metadata_v2(frozen)
            rows.append({"base_task_id": base["base_task_id"], "split": split,
                "family": base["family"], "language": base["language"],
                "frozen_selection_graph_id": base["semantic_graph_id"],
                "validated_semantic_graph_id": semantic_graph_id(repaired["expected_graph"]),
                "semantic_graph": semantic_graph(repaired["expected_graph"]),
                "online_inputs_changed": False, "reference_actions_changed": False,
                "revision": "task_contract_semantic_v2_verified_join"})
    by_split = {split: {r["validated_semantic_graph_id"] for r in rows if r["split"] == split}
                for split in ("development", "evaluation")}
    if len(rows) != 480 or len(by_split["development"]) != 80 or len(by_split["evaluation"]) != 400 or by_split["development"] & by_split["evaluation"]:
        raise ValueError("corrected semantic graphs collide or development/evaluation structure overlaps")
    _write_new_or_same(OUTPUT / "assets/semantic_graph_metadata_v2.jsonl", "".join(_json(row) + "\n" for row in rows))
    return {"rows": len(rows), "development_unique_graphs": 80, "evaluation_unique_graphs": 400,
        "changed_metadata_graphs": sum(row["frozen_selection_graph_id"] != row["validated_semantic_graph_id"] for row in rows),
        "development_evaluation_overlap": 0, "online_inputs_changed": False, "reference_actions_changed": False,
        "model_calls": 0, "scientific_scope": "programmatic_structure_validation_not_independent_workflow_sampling"}
