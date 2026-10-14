"""v4显式编译装配；五条件复用原有模拟工具、提示和评分路径。"""
from __future__ import annotations

import copy
import threading
from pathlib import Path
from typing import Any, Mapping

from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.task_contract_runtime_v1 import (
    TaskContractNativeRuntime, TaskContractSyntheticRuntime,
    _new_monitor,
)
from m3_guard.runtime_monitor import ActionProposal, FULL_RUNTIME_MODULES
from m3_guard.task_contract_monitor_v4 import ReferenceValueV4, TaskContractMonitorV4
from m3_guard.task_contract_v1 import BindingResolution, VerifiedObject

CONDITIONS_V4 = ("no_defense", "v3_policy", "v3_full", "v4_policy", "v4_full")


def build_runtime_tool_catalog(inputs: Mapping[str, Any]) -> dict[str, Any]:
    """编译提示与执行物化共用固定后端目录，不从工具正文认领能力。"""
    from m3_core.policy_compiler_corrected_v4 import build_trusted_tool_catalog
    from experiments.paper_v2.task_contract_synthetic_v1 import KINDS, METADATA_FIELDS, tool_schemas
    schemas = inputs["tool_schemas"]
    capabilities: dict[str, Any] = {}
    # 完整schema一致才装配此受信内存后端；仅工具名字相同不授予创建收据等能力。
    if schemas == tool_schemas():
        object_types = set(KINDS.values()) | {"file", "group", "contact", "report", "calendar_summary"}
        capabilities = {"created_object_receipts": ["create_object"],
            "objects": {kind: {"verified_fields": sorted(METADATA_FIELDS | {"title"})} for kind in object_types},
            "tools": {"lookup_objects": {"output_object_type": "$kind", "content_fields": ["body"]},
                      "read_object": {"output_object_type": "$input_object", "content_fields": ["body"]}}}
    return build_trusted_tool_catalog(schemas, adapter_capabilities=capabilities)


class RuntimeReferenceResolverV4:
    """只记录Guard已许可且后端实际成功的结果；公共输出不含原文。"""

    def __init__(self, delegate: Any, *, backend: Any = None) -> None:
        self.delegate = delegate
        self.backend = backend if backend is not None else getattr(delegate, "backend", None)
        self._observations: dict[str, list[tuple[Any, ActionProposal, tuple[str, ...], bool]]] = {}
        self._created: dict[str, dict[str, dict[str, Any]]] = {}
        self._discoveries: dict[str, tuple[str, ...]] = {}
        self._complete: dict[str, bool] = {}

    def __getattr__(self, name: str) -> Any:
        if self.delegate is None:
            raise AttributeError(name)
        return getattr(self.delegate, name)

    def trusted_fields(self, object_type: str) -> frozenset[str]:
        getter = getattr(self.delegate, "trusted_fields", None)
        result = getter(object_type) if callable(getter) else frozenset()
        if any(object_type in {"object", receipt.get("kind")} for receipts in self._created.values() for receipt in receipts.values()):
            result |= {"title"}
        return result

    def observe_success(self, proposal: ActionProposal, observation: Any, *, action_ids: tuple[str, ...]) -> None:
        observer = getattr(self.delegate, "observe_success", None)
        if callable(observer):
            observer(proposal, observation, action_ids=action_ids)
        classifier = getattr(self.backend, "classified_observations", None)
        values = classifier(proposal.tool, proposal.arguments, observation) if callable(classifier) else []
        native_classifier = getattr(self.backend, "trusted_observation_metadata", None)
        if callable(native_classifier):
            metadata = native_classifier(proposal.tool, proposal.arguments, observation)
            values = [(observation, metadata)]
        labels = tuple(sorted({label for _, meta in values if meta is not None
                               and meta.execution_succeeded and meta.observation_is_data
                               for label in meta.data_labels}))
        known = bool(values) and all(meta is not None for _, meta in values)
        for action_id in action_ids:
            self._observations.setdefault(action_id, []).append((copy.deepcopy(observation), proposal, labels, known))
            discovery = getattr(self.backend, "discovery_ids", None)
            proof = getattr(self.backend, "discovery_complete", None)
            if callable(discovery) and callable(proof):
                ids = discovery(proposal.tool, proposal.arguments)
                complete = proof(proposal.tool, proposal.arguments)
                if isinstance(ids, tuple) and all(isinstance(value, str) for value in ids) and type(complete) is bool and complete:
                    self._discoveries[action_id] = tuple(dict.fromkeys((*self._discoveries.get(action_id, ()), *ids)))
                    self._complete[action_id] = self._complete.get(action_id, True) and complete
                elif ids:
                    self._complete[action_id] = False
            if proposal.tool == "create_object" and isinstance(observation, Mapping):
                created = observation.get("created")
                # 收据编号还须与真实后台已应用事件和当前对象一致，正文不能伪造。
                events = getattr(self.backend, "events", ())
                getter = getattr(self.backend, "trusted_metadata", None)
                applied = bool(events) and events[-1].get("applied") is True and events[-1].get("tool") == proposal.tool \
                    and events[-1].get("arguments") == dict(proposal.arguments)
                metadata = getter("object", created) if callable(getter) and isinstance(created, str) else None
                args = dict(proposal.arguments)
                attributes = metadata.get("attributes", {}) if isinstance(metadata, Mapping) else {}
                expected = {"kind": args.get("kind"), "title": args.get("title"),
                            "owner": args.get("owner_id"), "parent_id": args.get("parent_id")}
                # 当前metadata通道未声明title可核验时，创建事件及内存状态双重核验。
                state = getattr(self.backend, "state", {})
                current = state.get("objects", {}).get(created) if isinstance(state, Mapping) else None
                if applied and isinstance(metadata, Mapping) and metadata.get("current") is True \
                        and isinstance(current, Mapping) and all(type(current.get(k)) is type(v) and current.get(k) == v for k, v in expected.items()) \
                        and all(attributes.get(k) == v for k, v in expected.items() if k in metadata.get("verified_fields", ())):
                    self._created.setdefault(action_id, {})[created] = expected

    def _verified(self, action_id: str, object_type: str) -> tuple[VerifiedObject, ...]:
        if action_id in self._created:
            getter = getattr(self.backend, "trusted_metadata", None)
            objects = []
            for object_id, expected in self._created[action_id].items():
                metadata = getter(object_type, object_id) if callable(getter) else None
                if not isinstance(metadata, Mapping) or metadata.get("current") is not True or metadata.get("complete") is not True:
                    return ()
                actual_type = metadata.get("object_type")
                if object_type not in {"object", actual_type}:
                    return ()
                attrs = metadata.get("attributes", {})
                state = getattr(self.backend, "state", {})
                present = state.get("objects", {}).get(object_id) if isinstance(state, Mapping) else None
                if not isinstance(present, Mapping) or any(type(present.get(k)) is not type(v) or present.get(k) != v for k, v in expected.items()):
                    return ()
                attrs = {**dict(attrs), **expected, "id": object_id}
                objects.append(VerifiedObject(object_type, object_id, attrs,
                    frozenset(metadata.get("verified_fields", ())) | frozenset(expected) | {"id"}, current=True))
            return tuple(objects)
        if action_id in self._discoveries:
            return self._discovered_objects(action_id, object_type)
        from m3_guard.task_contract_v1 import DeferredBinding, Predicate
        delegate = getattr(self.delegate, "resolve", None)
        # 只枚举该来源动作真正发现的记录，不让模型候选缩小范围。
        if not callable(delegate):
            return ()
        binding = DeferredBinding(action_id, object_type, Predicate("type", value="string", field="id"), cardinality="many")
        result = delegate(binding, candidate_value=None, successful_actions=(action_id,))
        if not isinstance(result, BindingResolution) or result.status != "resolved" or result.complete is not True:
            return ()
        return tuple(obj for obj in result.objects if obj.current and obj.object_type == object_type)

    def _discovered_objects(self, action_id: str, object_type: str) -> tuple[VerifiedObject, ...]:
        getter = getattr(self.backend, "trusted_metadata", None)
        fields = self.trusted_fields(object_type)
        if not callable(getter) or self._complete.get(action_id) is not True:
            return ()
        objects = []
        for object_id in self._discoveries[action_id]:
            metadata = getter(object_type, object_id)
            if not isinstance(metadata, Mapping) or metadata.get("current") is not True or metadata.get("complete") is not True \
                    or metadata.get("object_id") != object_id or metadata.get("object_type") != object_type:
                return ()
            attrs = {k: copy.deepcopy(v) for k, v in metadata.get("attributes", {}).items() if k in fields}
            objects.append(VerifiedObject(object_type, object_id, attrs,
                frozenset(metadata.get("verified_fields", ())) & frozenset(attrs), current=True))
        return tuple(objects)

    def resolve(self, binding: Any, *, candidate_value: Any, successful_actions: tuple[str, ...]) -> Any:
        if binding.from_action not in self._created and binding.from_action not in self._discoveries:
            getter = getattr(self.delegate, "resolve", None)
            return getter(binding, candidate_value=candidate_value, successful_actions=successful_actions) if callable(getter) \
                else BindingResolution("unsupported", (), complete=False)
        if binding.from_action not in successful_actions:
            return BindingResolution("pending", (), complete=False)
        objects = self._verified(binding.from_action, binding.object_type)
        return BindingResolution("resolved" if objects else "unsupported", objects, complete=bool(objects))

    def reference_values(self, ref: Mapping[str, Any], *, successful_actions: tuple[str, ...]) -> tuple[ReferenceValueV4, ...]:
        action_id = ref.get("from_action")
        if action_id not in successful_actions or action_id not in self._observations:
            return ()
        field = ref.get("field", ref.get("value_field"))
        kind = ref.get("kind")
        if kind in {"authority_binding", "result_ref", "derived"}:
            object_type = ref.get("object_type")
            if not isinstance(object_type, str):
                return ()
            objects = self._verified(action_id, object_type)
            selected = []
            for obj in objects:
                if field is not None and field not in obj.verified_fields:
                    continue
                value = obj.object_id if field in {"id", "object_id"} else obj.attributes.get(field)
                selected.append(ReferenceValueV4(value, action_id, obj.object_id, obj.object_type, obj.attributes))
            return tuple(selected)
        if kind != "data_ref":
            return ()
        result = []
        for observation, proposal, labels, known in self._observations[action_id]:
            if isinstance(observation, Mapping) and "result" in observation:
                observation = observation["result"]
            records = observation.get("objects") if isinstance(observation, Mapping) and "objects" in observation else observation
            records = records if isinstance(records, (list, tuple)) else [records]
            for record in records:
                value = record.get(field) if isinstance(record, Mapping) else record if field in {None, "text", "content", "body"} else None
                if value is None:
                    continue
                object_id = record.get("id", record.get("id_", record.get("object_id"))) if isinstance(record, Mapping) else None
                if not isinstance(object_id, str):
                    object_id = proposal.arguments.get("object_id") if isinstance(proposal.arguments.get("object_id"), str) else None
                attrs, obj_type = {}, None
                getter = getattr(self.backend, "trusted_metadata", None)
                metadata = getter("object", object_id) if callable(getter) and object_id else None
                if isinstance(metadata, Mapping) and metadata.get("current") is True:
                    obj_type = metadata.get("object_type")
                    attrs = {k: copy.deepcopy(v) for k, v in metadata.get("attributes", {}).items() if k in metadata.get("verified_fields", ())}
                result.append(ReferenceValueV4(copy.deepcopy(value), action_id, object_id, obj_type, attrs,
                    data_labels=labels, classification_known=known))
        return tuple(result)

    def references_related(self, values: tuple[ReferenceValueV4, ...], plans: tuple[Mapping[str, Any], ...]) -> bool:
        real = [value for value in values if value.from_action != "literal"]
        # 同一返回记录的两个字段不能交叉组合。
        for left in real:
            for right in real:
                if left.from_action == right.from_action and left.object_id and right.object_id and left.object_id != right.object_id:
                    return False
        for plan in plans:
            join = plan.get("join")
            if not isinstance(join, Mapping):
                continue
            source = [value for value in real if value.from_action == join.get("from_action")]
            # selector侧车action_id指向查找动作；普通引用侧车则显式记录关系目标动作。
            destination_id = join.get("target_action", plan["action_id"])
            destination = [value for value in real if value.from_action == destination_id]
            for left in source:
                for right in destination:
                    attrs_l, attrs_r = left.attributes or {}, right.attributes or {}
                    wanted = left.object_id if join.get("source_field") in {"id", "object_id"} else attrs_l.get(join.get("source_field"))
                    actual = right.object_id if join.get("target_field") in {"id", "object_id"} else attrs_r.get(join.get("target_field"))
                    if wanted is None or type(wanted) is not type(actual) or wanted != actual:
                        return False
        # 后续读取同一发现集合时，正文与操作目标还须经已声明绑定保持关联。
        # 仅同一action内部比对不足：read动作可能一次读多个不同对象。
        for plan in plans:
            if plan.get("kind") != "authority_binding" or plan.get("query_binding") is True:
                continue
            source = [value for value in real if value.from_action == plan.get("from_action")]
            destination = [value for value in real if value.from_action == plan.get("action_id")]
            field = plan.get("value_field", plan.get("field", "id"))
            for left in source:
                for right in destination:
                    wanted = left.object_id if field in {"id", "object_id"} else (left.attributes or {}).get(field)
                    if right.object_id and (wanted is None or type(wanted) is not type(right.object_id) or wanted != right.object_id):
                        return False
        return True


def _unavailable(status: str, code: str) -> dict[str, Any]:
    return {"unsafe_effect": None, "task_completion": None,
        "unsafe_effect_observed": False, "task_completion_observed": False,
        "operational_status": status, "events": [], "ask_count": 0, "deny_count": 0,
        "online_forbidden_fields_present": [], "online_visible_field_digest": {"forbidden_fields_present": []},
        "latency_ms": None, "observation_complete": False,
        "provider_tools_enabled": False, "real_external_effects": 0,
        "effect_evidence": {"isolated_material_observed": False, "unsafe_scored": False, "completion_scored": False},
        "evaluation_details": {"unknown_reasons": [code]}}


def build_versioned_contract_monitor(version: str, fixed: Mapping[str, Any], inputs: Mapping[str, Any],
        manifest: Any, tracker: Any, schemas: Mapping[str, Any], resolver: Any, condition: str) -> Any:
    """在线及同提案离线回放共用的显式装配入口；不加载标签或评分目标。"""
    if fixed.get("compiler_input_sha256") != sha256_canonical_json(inputs):
        raise ValueError("fixed compiler inputs drift")
    if condition not in {"new_policy", "new_full"}:
        raise ValueError("unknown v4 monitor module condition")
    if version == "v3":
        return _new_monitor({**fixed, "draft_index": 1}, inputs, manifest, tracker, schemas, resolver, condition)
    if version != "v4":
        raise ValueError("unknown explicit compiler version")
    from m3_core.policy_compiler_corrected_v4 import compile_task_intent_v4
    result = compile_task_intent_v4(**inputs, intent=fixed["intent"], base_manifest=manifest,
        catalog=build_runtime_tool_catalog(inputs))
    if result.status != "ready":
        raise ValueError("fixed v4 compilation no longer ready")
    return TaskContractMonitorV4(result, resolver=RuntimeReferenceResolverV4(resolver), tracker=tracker,
        tool_schemas=schemas, modules=frozenset({"policy"}) if condition == "new_policy" else FULL_RUNTIME_MODULES)


class TaskContractV4Runtime:
    """显式v3/v4分派；非ready编译状态保留ITT且不发模型请求。"""

    def __init__(self, plan_path: Path, execution_identity: str, *, contracts_by_version: Mapping[str, Any], input_loader: Any) -> None:
        from experiments.paper_v2.task_contract_cases_v1 import load_task_contract_case
        from experiments.paper_v2.task_contract_synthetic_v1 import SyntheticTaskBackend, score_synthetic
        from experiments.paper_v2.correctness_plan_v1 import read_jsonl
        self.contracts_by_version = contracts_by_version
        self.input_loader = input_loader
        self._local = threading.local()
        plans = read_jsonl(plan_path)
        self.native, self.synthetic = {}, {}
        for version in ("v3", "v4"):
            contracts = contracts_by_version.get(version, {})
            factory = self._factory(version)
            if any(row["benchmark"] in {"agentdojo-v1", "m3-v2"} for row in plans):
                self.native[version] = TaskContractNativeRuntime(plan_path, execution_identity, contracts=contracts,
                    input_loader=input_loader, contract_monitor_factory=factory)
            self.synthetic[version] = TaskContractSyntheticRuntime(contracts=contracts, backend_factory=SyntheticTaskBackend,
                scorer=score_synthetic, case_loader=lambda row: self._synthetic_case(load_task_contract_case, row),
                contract_monitor_factory=factory)

    @staticmethod
    def _synthetic_case(loader: Any, row: Mapping[str, Any]):
        case = loader(row, scenario=row["scenario"])
        return case["live_case"], case["offline_evaluation"]

    def _factory(self, version: str):
        def build(fixed: Any, inputs: Any, manifest: Any, tracker: Any, schemas: Any, resolver: Any,
                  condition: str, ablation_profile: Any = None):
            if ablation_profile is not None:
                raise ValueError("v4 development study has no ablation fallback")
            monitor = build_versioned_contract_monitor(version, fixed, inputs, manifest, tracker, schemas, resolver, condition)
            self._local.monitor = monitor
            return monitor
        return build

    def execute(self, row: Mapping[str, Any], client: Any) -> dict[str, Any]:
        condition = str(row["condition_id"])
        if condition not in CONDITIONS_V4:
            raise ValueError("unknown explicit v4 study condition")
        version = condition.split("_", 1)[0] if condition != "no_defense" else "v3"
        declared = row.get("compiler_version")
        if declared is not None and condition != "no_defense" and declared not in {version, "corrected_" + version}:
            raise ValueError("condition/compiler version mismatch")
        fixed = self.contracts_by_version.get(version, {}).get(row["base_task_id"])
        if condition != "no_defense":
            if fixed is None:
                return _unavailable("compile_failure", "fixed_compilation_missing")
            status = fixed.get("compile_status", fixed.get("status"))
            if status not in {"compiled", "ready"}:
                return _unavailable("clarification_required" if status in {"clarification_required", "needs_clarification", "missing", "unsupported"}
                                    else "compile_failure", "fixed_" + str(status))
        mapped = {**row, "condition_id": "no_defense" if condition == "no_defense" else
            "new_policy" if condition.endswith("policy") else "new_full"}
        runtime = self.native.get(version) if row["benchmark"] in {"agentdojo-v1", "m3-v2"} else self.synthetic[version]
        if runtime is None:
            raise ValueError("native runtime unavailable")
        self._local.monitor = None
        result = dict(runtime.execute(mapped, client))
        monitor = self._local.monitor
        # 计划身份不能被运行时修订名称覆盖；续跑按相同身份读取已有行。
        result["compiler_version"] = row.get("compiler_version")
        result["compiler_revision"] = "not_enforced" if condition == "no_defense" else "corrected_" + version
        result["runtime_revision"] = "task_contract_runtime_v4"
        result["reference_diagnostics"] = list(getattr(monitor, "last_reference_diagnostics", ()))
        return result
