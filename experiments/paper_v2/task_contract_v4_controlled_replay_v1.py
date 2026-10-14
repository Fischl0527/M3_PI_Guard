"""同一受控提案交给四配置；只调用真实内存后端，不调用模型。"""
from __future__ import annotations

import argparse
import copy
import json
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping

from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.correctness_plan_v1 import read_jsonl
from experiments.paper_v2.task_contract_cases_v1 import load_task_contract_case
from experiments.paper_v2.task_contract_runtime_v1 import TaskContractSyntheticRuntime
from experiments.paper_v2.task_contract_runtime_v4 import TaskContractV4Runtime
from experiments.paper_v2.task_contract_synthetic_v1 import SyntheticTaskBackend, score_synthetic
from experiments.paper_v2.task_contract_v4_development_v1 import OUTPUT, fixed_compilations

CONDITIONS = ("v3_policy", "v3_full", "v4_policy", "v4_full")


def fixtures(online: Mapping[str, Any], offline: Mapping[str, Any]) -> dict[str, tuple[dict[str, Any], list[dict[str, Any]]]]:
    """原规范链和三个可明确控制的动作扰动；不伪造缺失参考链。"""
    actions = [{"tool": node["tool"], "arguments": copy.deepcopy(node["arguments"])}
               for node in offline["expected_graph"]["nodes"]]
    result = {"reference_chain": (copy.deepcopy(dict(online)), actions)}
    if len(actions) > 1:
        result["reversed_chain"] = (copy.deepcopy(dict(online)), list(reversed(copy.deepcopy(actions))))
    if actions:
        result["duplicate_first_action"] = (copy.deepcopy(dict(online)), [copy.deepcopy(actions[0])]+copy.deepcopy(actions))
    mutated = copy.deepcopy(actions)
    target = next((node for node in mutated if "object_id" in node["arguments"]), None)
    if target is not None:
        target["arguments"]["object_id"] = "outside-authorized-reference-scope"
        result["wrong_object"] = (copy.deepcopy(dict(online)), mutated)
    # 对象缺失是状态变化，不把原合法动作改称攻击，也不声称TCR规范仍适用。
    nodes = online.get("environment", {}).get("objects", [])
    wanted = next((n["arguments"].get("object_id") for n in actions if "object_id" in n["arguments"]), None)
    if wanted is not None and any(obj.get("id") == wanted for obj in nodes):
        missing = copy.deepcopy(dict(online))
        missing["environment"]["objects"] = [obj for obj in missing["environment"]["objects"] if obj.get("id") != wanted]
        result["missing_object_state"] = (missing, copy.deepcopy(actions))
    return result


class OfflineProposalClient:
    """固定提案流；没有HTTP传输、密钥或官方响应身份。"""
    provider_id = "deepseek"  # 只满足已存在的隔离receipt接口，不代表官方推理。
    endpoint = "https://api.deepseek.com/chat/completions"

    def __init__(self, actions: list[dict[str, Any]]) -> None:
        self.actions = actions
        self.max_provider_calls = min(len(actions)+1, 12)

    def complete(self, _messages: Any, *, step: int) -> Any:
        value = self.actions[step-1] if step <= len(self.actions) else {"tool": "final", "arguments": {"answer": "controlled replay finished"}}
        return SimpleNamespace(text=json.dumps(value, ensure_ascii=False))


def controlled_outcome(base: Mapping[str, Any], condition: str, compiled: Mapping[str, Any], online: Mapping[str, Any],
                       offline: Mapping[str, Any], actions: list[dict[str, Any]]) -> dict[str, Any]:
    """每次新建环境及监视器；评价规范仅传给本地scorer。"""
    version = condition.split("_", 1)[0]
    runtime = TaskContractV4Runtime.__new__(TaskContractV4Runtime)
    import threading
    runtime._local = threading.local()
    runtime.contracts_by_version = {version: {base["base_task_id"]: compiled}}
    synthetic = TaskContractSyntheticRuntime(contracts=runtime.contracts_by_version[version],
        case_loader=lambda row: (copy.deepcopy(dict(online)), copy.deepcopy(dict(offline))),
        backend_factory=SyntheticTaskBackend, scorer=score_synthetic,
        contract_monitor_factory=runtime._factory(version))
    result = synthetic.execute({**base, "condition_id": "new_policy" if condition.endswith("policy") else "new_full",
                                "work_key": "offline:"+condition+":"+base["base_task_id"]}, OfflineProposalClient(actions))
    return {key: result.get(key) for key in ("unsafe_effect", "task_completion", "operational_status", "ask_count", "deny_count",
                                            "events", "data_label_tracker", "effect_evidence")}


def run(output: Path = OUTPUT) -> dict[str, Any]:
    bases = [row for cohort in ("debug", "qualification") for row in read_jsonl(output / f"assets/cases_{cohort}_v1.jsonl")]
    if len(bases) != 32 or len({row["base_task_id"] for row in bases}) != 32:
        raise ValueError("32 fixed bases required")
    compiled = fixed_compilations(read_jsonl(output / "compilation/raw_records_v1.jsonl"))
    if any(base["base_task_id"] not in compiled[version] for base in bases for version in ("v3", "v4")):
        raise ValueError("all actual fixed compilation outcomes required, not a count-only replay")
    path = output / "controlled_decisions_v1.jsonl"
    if path.exists():
        raise ValueError("controlled replay already exists; do not overwrite")
    records = []
    for base in bases:
        identity = {key: base[key] for key in ("base_task_id", "development_cohort", "benchmark", "family")}
        if base["benchmark"] != "task-contract-synthetic-v1":
            records.append({**identity, "status": "not_applicable", "reason": "m3_frozen_source_has_no_complete_reference_chain",
                            "guard_calls": 0, "api_calls": 0})
            continue
        loaded = load_task_contract_case(base, "benign")
        for variant, (online, proposals) in fixtures(loaded["live_case"], loaded["offline_evaluation"]).items():
            for condition in CONDITIONS:
                fixed = compiled[condition.split("_", 1)[0]][base["base_task_id"]]
                row = {**identity, "variant": variant, "condition_id": condition, "api_calls": 0,
                       "proposal_digests": [sha256_canonical_json(proposal) for proposal in proposals],
                       "analysis_scope": "offline_program_control_not_end_to_end_model_result"}
                if fixed["compile_status"] != "compiled":
                    row.update(status="compiler_unavailable", compiler_status=fixed["compiler_status"], guard_calls=0,
                               unsafe_effect=None, task_completion=None)
                else:
                    outcome = controlled_outcome(base, condition, fixed, online, loaded["offline_evaluation"], proposals)
                    row.update(status="replayed", **outcome)
                    row["guard_calls"] = sum(event.get("parse_ok") is True and event.get("guard_decision") is not None
                                             for event in outcome.get("events", []))
                    # 缺失状态不能沿用正常场景的TCR规范；这里只保留程序及效果观察。
                    if variant == "missing_object_state":
                        row["task_completion"] = None
                        row["completion_scoring"] = "not_applicable_for_mutated_state"
                records.append(row)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        for row in records:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True)+"\n")
    summary = dict(base_tasks=32, records=len(records), actual_guard_calls=sum(row["guard_calls"] for row in records),
                   api_calls=0, statuses=dict(Counter(row["status"] for row in records)))
    (output / "controlled_summary_v1.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    print(json.dumps(run(parser.parse_args().output), ensure_ascii=False))


if __name__ == "__main__":
    main()
