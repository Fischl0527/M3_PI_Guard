"""v4引用侧车检查：结果、授权和正文引用不互相升级权限。"""
from __future__ import annotations

import itertools
import json
import math
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any, Mapping

from m3_guard.provenance import ProvenanceEvent
from m3_guard.runtime_monitor import ActionProposal, FULL_RUNTIME_MODULES
from m3_guard.task_contract_monitor_v1 import TaskContractMonitorV1
from m3_guard.task_contract_v1 import TaskContractV1


@dataclass(frozen=True)
class ReferenceValueV4:
    value: Any
    from_action: str
    object_id: str | None = None
    object_type: str | None = None
    attributes: Mapping[str, Any] | None = None
    data_labels: tuple[str, ...] = ()
    classification_known: bool = True


def _same(left: Any, right: Any) -> bool:
    return type(left) is type(right) and left == right


class TaskContractMonitorV4(TaskContractMonitorV1):
    """只能以编译器输出及实际成功观察物化引用，不读取评价答案。"""

    def __init__(self, compilation: Any, *, resolver: Any, tracker: Any,
                 tool_schemas: Mapping[str, Any], modules: frozenset[str] = FULL_RUNTIME_MODULES) -> None:
        contract = compilation.contract
        if not isinstance(contract, TaskContractV1) or compilation.status != "ready":
            raise ValueError("v4 monitor requires a ready compiler result")
        plans = compilation.reference_plan
        if not isinstance(plans, (tuple, list)) or resolver is None:
            raise ValueError("v4 typed reference sidecar/resolver missing")
        by_action = {action.action_id: action for action in contract.actions}
        self.reference_plan = tuple(dict(ref) for ref in plans)
        for ref in self.reference_plan:
            action = by_action.get(ref.get("action_id"))
            if action is None or ref.get("argument") not in tool_schemas[action.tool]["arguments"]:
                raise ValueError("v4 reference points outside the contract")
            if ref.get("kind") not in {"result_ref", "authority_binding", "data_ref", "derived"}:
                raise ValueError("unknown v4 reference kind")
            if ref.get("kind") == "data_ref" and action.argument_roles.get(ref["argument"]) != "content":
                raise ValueError("data reference cannot authorize a target or operation")
            if ref.get("kind") == "result_ref" and (action.argument_roles.get(ref["argument"]) != "value"
                    or tool_schemas[action.tool]["arguments"][ref["argument"]].get("allow_backend_binding") is not True):
                raise ValueError("result reference does not imply target authority")
            if ref.get("kind") == "authority_binding" and action.argument_roles.get(ref["argument"]) != "target" \
                    and not (ref.get("query_binding") is True and action.argument_roles.get(ref["argument"]) == "query"):
                raise ValueError("authority reference requires an explicit target or declared query binding")
        if contract.status not in {"ready", "runtime_references_required"}:
            raise ValueError("v4 contract has unresolved compile diagnostics")
        # 仅此显式侧车路径提升运行状态；旧v3监视器面对同一契约仍ASK。
        super().__init__(replace(contract, status="ready"), resolver=resolver, modules=modules,
                         tracker=tracker, tool_schemas=tool_schemas)
        self.last_reference_diagnostics: tuple[dict[str, Any], ...] = ()
        self._consumed: set[tuple[str, str]] = set()
        self._pending_units: dict[str, dict[str, str]] = {}
        self._ordered_seen: dict[tuple[str, str], list[Any]] = {}

    def _decision(self, proposal: ActionProposal, name: str, code: str):
        if code in {"v4_reference_value_conflict", "v4_reference_relationship_conflict", "v4_duplicate_effect", "v4_reference_order_conflict"}:
            name = "DENY"
        return super()._decision(proposal, name, code)

    def _values(self, ref: Mapping[str, Any]) -> tuple[ReferenceValueV4, ...]:
        source = ref.get("from_action")
        if source not in self.successful_actions:
            return ()
        getter = getattr(self.resolver, "reference_values", None)
        if not callable(getter):
            return ()
        try:
            values = getter(ref, successful_actions=self.successful_actions)
        except Exception:
            return ()  # 后端异常不能转成开放权限。
        if not isinstance(values, tuple) or any(not isinstance(v, ReferenceValueV4) for v in values):
            return ()
        return values

    def _material(self, ref: Mapping[str, Any]) -> tuple[ReferenceValueV4, ...]:
        values = self._values(ref)
        transform = ref.get("transform", "copy")
        if transform == "copy":
            return values
        if transform == "summarize":
            return values
        if transform == "facts_line":
            prefix = ref.get("prefix", "Facts: ")
            if not isinstance(prefix, str) or not prefix:
                return ()
            return tuple(replace(value, value=value.value.splitlines()[0][len(prefix):])
                         for value in values if isinstance(value.value, str)
                         and value.value.splitlines() and value.value.splitlines()[0].startswith(prefix))
        return ()

    def _concat(self, ref: Mapping[str, Any]) -> tuple[ReferenceValueV4, ...]:
        parts = ref.get("parts")
        if not isinstance(parts, (list, tuple)) or not 1 <= len(parts) <= 16:
            return ()
        choices = []
        for part in parts:
            if not isinstance(part, Mapping):
                return ()
            if part.get("kind") == "literal" and isinstance(part.get("value"), str):
                choices.append((ReferenceValueV4(part["value"], "literal"),))
            elif part.get("kind") in {"result_ref", "authority_binding", "data_ref"}:
                values = self._material(part) if part["kind"] == "data_ref" else self._values(part)
                if not values or len(values) > 64:
                    return ()
                choices.append(values)
            else:
                return ()
        if any(not isinstance(value.value, (str, int, float, bool)) for values in choices for value in values):
            return ()
        if math.prod(len(values) for values in choices) > 4096:
            return ()
        joined = []
        checker = getattr(self.resolver, "references_related", None)
        for combination in itertools.product(*choices):
            if not callable(checker) or not checker(combination, self.reference_plan):
                continue
            joined.append(ReferenceValueV4("".join(str(v.value) for v in combination),
                str(ref.get("from_action", "concat")),
                object_id="|".join(sorted({v.object_id for v in combination if v.object_id})),
                data_labels=tuple(sorted({label for v in combination for label in v.data_labels})),
                classification_known=all(v.classification_known for v in combination)))
        return tuple(joined)

    def _reference_check(self, action: Any, proposal: ActionProposal) -> tuple[str, tuple[str, ...]]:
        labels: set[str] = set()
        related: list[tuple[ReferenceValueV4, ...]] = []
        for ref in self.reference_plan:
            if ref["action_id"] != action.action_id:
                continue
            argument = ref["argument"]
            if argument not in proposal.arguments:
                return "v4_reference_argument_missing", ()
            if ref.get("query_binding") is True and argument in action.bindings:
                continue  # v1用完整查找集合核验JSON查询，不能逐标量匹配。
            kind = ref["kind"]
            concat = kind == "derived" and ref.get("operation", ref.get("transform")) == "concat"
            values = self._concat(ref) if concat else self._material(ref) if kind == "data_ref" else self._values(ref)
            if kind == "derived" and ref.get("operation", ref.get("transform")) == "duration_minutes":
                fields = ref.get("fields", ())
                if not isinstance(fields, (list, tuple)) or len(fields) != 2:
                    return "v4_reference_capability_missing", ()
                duration = []
                for value in values:
                    attrs = value.attributes or {}
                    try:
                        start, end = (datetime.fromisoformat(attrs[field]) for field in fields)
                        if start.tzinfo is None or end.tzinfo is None or end <= start:
                            continue
                        duration.append(replace(value, value=(end - start).total_seconds() / 60))
                    except (KeyError, ValueError, TypeError):
                        continue
                values = tuple(duration)
            if not values:
                return "v4_reference_source_missing", ()
            candidate = proposal.arguments[argument]
            if kind == "data_ref" and ref.get("transform") == "summarize":
                matching = values if isinstance(candidate, str) else ()
            else:
                matching = tuple(v for v in values if _same(v.value, candidate)
                                 or type(v.value) in {int, float} and type(candidate) in {int, float}
                                 and v.value == candidate)
            if not matching:
                return "v4_reference_value_conflict", ()
            if ref.get("iteration_order") is True:
                seen = self._ordered_seen.get((action.action_id, argument), ())
                pending = [value.value for value in values if not any(_same(value.value, item) for item in seen)]
                if not pending or not _same(candidate, pending[0]):
                    return "v4_reference_order_conflict", ()
            if "dataflow" in self.modules and self.contract.data_flow_policy and any(not v.classification_known for v in matching):
                return "v4_reference_classification_missing", ()
            labels.update(label for value in matching for label in value.data_labels)
            related.append(matching)
        checker = getattr(self.resolver, "references_related", None)
        if related:
            if math.prod(len(values) for values in related) > 4096 or not callable(checker):
                return "v4_reference_capability_missing", ()
            if not any(checker(tuple(values), self.reference_plan) for values in itertools.product(*related)):
                return "v4_reference_relationship_conflict", ()
        return "matched", tuple(sorted(labels))

    def _match(self, action: Any, proposal: ActionProposal):
        code, resolved, certified = super()._match(action, proposal)
        if code != "matched":
            return code, resolved, certified
        code, _ = self._reference_check(action, proposal)
        self.last_reference_diagnostics += ({"action_id": action.action_id, "status": code},)
        if code != "matched":
            return code, {}, frozenset()
        if action.role not in {"discover", "read"}:
            # 内容改变不能重复操作同一目标；concat逐记录交付另以已核验正文区分。
            args = {name: value for name, value in proposal.arguments.items()
                    if action.argument_roles.get(name) != "content"}
            for ref in self.reference_plan:
                if ref["action_id"] == action.action_id and ref.get("operation", ref.get("transform")) == "concat":
                    args[ref["argument"]] = proposal.arguments[ref["argument"]]
            unit = json.dumps(args, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            if (action.action_id, unit) in self._consumed:
                return "v4_duplicate_effect", {}, frozenset()
            self._pending_units.setdefault(proposal.proposal_id, {})[action.action_id] = unit
        return "matched", resolved, certified

    def decide(self, proposal: ActionProposal):
        self.last_reference_diagnostics = ()
        # 传递已声明数据引用的保密标签，不把其来源升级为用户/应用授权。
        labels_by_arg: dict[str, set[str]] = {}
        for action in self.contract.actions:
            if action.tool != proposal.tool:
                continue
            code, labels = self._reference_check(action, proposal)
            if code == "matched":
                for ref in self.reference_plan:
                    if ref["action_id"] == action.action_id and ref["kind"] in {"data_ref", "derived"}:
                        labels_by_arg.setdefault(ref["argument"], set()).update(labels)
        events = list(proposal.provenance)
        for argument, labels in labels_by_arg.items():
            if not labels:
                continue
            index = next((i for i, event in enumerate(events) if event.argument_path.removeprefix("arguments.") == argument), None)
            if index is None:
                events.append(ProvenanceEvent(event_id=proposal.proposal_id + ":v4:" + argument,
                    proposal_id=proposal.proposal_id, argument_path="arguments." + argument,
                    source_type="untrusted_tool_output", trust_level="untrusted",
                    value_sha256=proposal.proposal_sha256, data_labels=tuple(sorted(labels)),
                    evidence="Declared data reference retains backend labels."))
            else:
                event = events[index]
                events[index] = replace(event, data_labels=tuple(sorted(set(event.data_labels) | labels)))
        return super().decide(replace(proposal, provenance=tuple(events)))

    def record_execution(self, proposal: ActionProposal, decision: Any) -> None:
        allowed = self._allowed.get(proposal.proposal_id)
        matched_ids = {action.action_id for action in allowed[2]} if allowed is not None else set()
        super().record_execution(proposal, decision)
        for action_id, unit in self._pending_units.pop(proposal.proposal_id, {}).items():
            if action_id in matched_ids:
                self._consumed.add((action_id, unit))
        for ref in self.reference_plan:
            if ref["action_id"] in matched_ids and ref.get("iteration_order") is True:
                self._ordered_seen.setdefault((ref["action_id"], ref["argument"]), []).append(proposal.arguments[ref["argument"]])

    def observe_success(self, proposal: ActionProposal, observation: Any) -> None:
        recorded = self._recorded.get(proposal.proposal_id)
        allowed = self._allowed.get(proposal.proposal_id)
        if recorded is None or recorded[0] != proposal.proposal_sha256 or allowed is None:
            raise ValueError("observation requires the exact recorded successful action")
        observer = getattr(self.resolver, "observe_success", None)
        if callable(observer):
            # 每个实际成功对象都保留；整个动作完成后才可供后续引用。
            # v1回调只给最后完成的动作，过去会丢失批量读取的前几条记录。
            observer(proposal, observation, action_ids=tuple(action.action_id for action in allowed[2]))
