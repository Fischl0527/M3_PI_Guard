"""整条动作规则及受信任后端延迟绑定，不升级普通观察的来源。"""

from __future__ import annotations

from dataclasses import replace
import json
from typing import Any, Mapping

from m3_guard.provenance import UNTRUSTED_SOURCES, provenance_uses_instruction_field
from m3_guard.provenance_corrected_v1 import TrustedDataLabelTracker
from m3_guard.runtime_monitor import FULL_RUNTIME_MODULES, ActionProposal, GuardDecision, _make_decision
from m3_guard.runtime_monitor_corrected_v2 import RuntimeMonitorCorrectedV2
from m3_guard.runtime_monitor_corrected_v1 import _matches
from m3_guard.task_contract_v1 import (
    UNTRUSTED_OBJECT_FIELDS, BindingResolution, ContractAction, TaskContractV1,
    TrustedBindingResolver, VerifiedObject,
)
from m3_guard.task_policy import ParameterConstraint, ToolRule


class TaskContractMonitorV1(RuntimeMonitorCorrectedV2):
    """实例仅属于一个运行；decide只求值，成功执行回调才推进依赖。"""

    def __init__(self, contract: TaskContractV1, *, resolver: TrustedBindingResolver | None = None,
                 modules: frozenset[str] = FULL_RUNTIME_MODULES, tracker: TrustedDataLabelTracker,
                 tool_schemas: Mapping[str, Mapping[str, Any]] | None = None,
                 ablation_profile: str | None = None) -> None:
        if not isinstance(contract, TaskContractV1):
            raise TypeError("contract must be compiler-created TaskContractV1")
        if ablation_profile not in {None, "lexical_contract", "static_binding", "whole_call_source"}:
            raise ValueError("unknown task-contract ablation")
        super().__init__(contract.static_manifest, modules=modules, tracker=tracker, tool_schemas=tool_schemas)
        self.contract, self.resolver, self.ablation_profile = contract, resolver, ablation_profile
        self._successful_actions: list[str] = []
        self._allowed: dict[str, tuple[str, str, tuple[ContractAction, ...], dict[str, dict[str, tuple[Any, ...]]]]] = {}
        self._recorded: dict[str, tuple[str, tuple[str, ...]]] = {}
        self._required_values: dict[str, dict[str, tuple[Any, ...]]] = {}
        self._seen_values: dict[str, dict[str, list[Any]]] = {}
        self.last_binding_diagnostics: tuple[dict[str, Any], ...] = ()
        self.last_role_certificates: tuple[dict[str, Any], ...] = ()

    @property
    def successful_actions(self) -> tuple[str, ...]:
        return tuple(self._successful_actions)

    def _decision(self, proposal: ActionProposal, name: str, code: str) -> GuardDecision:
        return _make_decision(proposal, self.contract.static_manifest, name, violated=(code,),
                              reason="Task-contract authorization is not complete: " + code,
                              recovery="Supply the missing trusted scope or resolve the explicit conflict; do not expand from tool text.")

    def _resolve(self, action: ContractAction, name: str, candidate: Any) -> tuple[str, tuple[Any, ...], tuple[VerifiedObject, ...]]:
        binding = action.bindings[name]
        if self.ablation_profile == "static_binding":
            return "static_binding_unresolved", (), ()
        if self.resolver is None:
            return "binding_resolver_missing", (), ()
        if binding.from_action not in self._successful_actions:
            return "binding_discovery_missing", (), ()
        needed_fields = binding.predicate.fields | {binding.value_field}
        if action.when and action.when[0] == name:
            needed_fields |= action.when[1].fields
        if needed_fields & UNTRUSTED_OBJECT_FIELDS:
            return "binding_untrusted_predicate_field", (), ()
        try:
            trusted_fields = self.resolver.trusted_fields(binding.object_type)
            if not isinstance(trusted_fields, frozenset) or not needed_fields <= trusted_fields:
                return "binding_attribute_unverifiable", (), ()
            result = self.resolver.resolve(binding, candidate_value=candidate, successful_actions=self.successful_actions)
        except Exception:
            # 后端错误不变成开放许可；不输出异常正文中的数据。
            return "binding_backend_failure", (), ()
        if not isinstance(result, BindingResolution) or type(result.complete) is not bool:
            return "binding_metadata_untrusted", (), ()
        if result.status != "resolved":
            allowed_statuses = {"missing", "ambiguous", "conflict", "stale", "unsupported"}
            return "binding_" + (result.status if result.status in allowed_statuses else "metadata_untrusted"), (), ()
        if not result.complete:
            return "binding_incomplete_candidate_set", (), ()
        if not isinstance(result.objects, tuple) or any(not isinstance(obj, VerifiedObject) for obj in result.objects):
            return "binding_metadata_untrusted", (), ()
        selected = []
        for obj in result.objects:
            if type(obj.current) is not bool or not obj.current:
                return "binding_stale", (), ()
            if obj.object_type != binding.object_type or not isinstance(obj.object_id, str) or not obj.object_id:
                return "binding_object_type_conflict", (), ()
            if not needed_fields <= obj.verified_fields:
                return "binding_attribute_unverifiable", (), ()
            if binding.predicate.matches_object(obj):
                selected.append(obj)
        if len({obj.object_id for obj in selected}) != len(selected):
            return "binding_metadata_untrusted", (), ()
        if not selected:
            return "binding_missing", (), ()
        if action.when and action.when[0] == name:
            selected = [obj for obj in selected if action.when[1].matches_object(obj)]
            if not selected:
                return "branch_condition_false", (), ()
        if binding.cardinality == "one" and len(selected) != 1:
            return "binding_ambiguous", (), ()
        values = tuple(obj.object_id if binding.value_field in {"id", "object_id"} else obj.attributes.get(binding.value_field) for obj in selected)
        if any(value is None or type(value) not in {str, int, float, bool} for value in values):
            return "binding_attribute_unverifiable", (), ()
        if binding.value_format == "json_filter":
            unique = sorted(set(values), key=lambda value: (type(value).__name__, str(value)))
            expected = {**dict(binding.static_filter), binding.filter_field: {"in": unique}}
            try:
                actual = json.loads(candidate) if isinstance(candidate, str) else None
            except (ValueError, TypeError):
                actual = None
            if actual != expected:
                return "binding_target_conflict", (), ()
            return "resolved", (candidate,), tuple(selected)
        requested = candidate if isinstance(candidate, list) else [candidate]
        if not requested or any(not any(type(value) is type(actual) and value == actual for actual in values) for value in requested):
            return "binding_target_conflict", (), ()
        return "resolved", values, tuple(selected)

    def _match(self, action: ContractAction, proposal: ActionProposal) -> tuple[str, dict[str, tuple[Any, ...]], frozenset[str]]:
        if self.contract.application_scope is not None and not any(rule.tool == proposal.tool and _matches(proposal, rule) for rule in self.contract.application_scope):
            return "application_scope_conflict", {}, frozenset()
        for name, predicate in self.contract.application_constraints.get(proposal.tool, {}).items():
            if name not in proposal.arguments or not predicate.matches(proposal.arguments[name]):
                return "application_argument_scope_conflict", {}, frozenset()
        if any(previous not in self._successful_actions for previous in action.depends_on):
            return "action_dependency_missing", {}, frozenset()
        for name, predicate in action.constraints.items():
            if name not in proposal.arguments:
                if self.tool_schemas and self.tool_schemas[action.tool]["arguments"][name].get("required", False):
                    return "required_argument_missing", {}, frozenset()
                continue
            if not predicate.matches(proposal.arguments[name]):
                return "argument_constraint_mismatch", {}, frozenset()
        # 未声明可选字段不能携带新的目标/数量；仅省略或可信schema默认值。
        if self.tool_schemas:
            for name, value in proposal.arguments.items():
                if name not in action.constraints and name not in action.bindings:
                    detail = self.tool_schemas[action.tool]["arguments"].get(name, {})
                    if "default" not in detail or type(value) is not type(detail["default"]) or value != detail["default"]:
                        return "optional_argument_scope_missing", {}, frozenset()
        resolved = {}
        relational_rows: dict[tuple[str, str], set[str]] = {}
        for name in action.bindings:
            if name not in proposal.arguments:
                return "required_binding_argument_missing", {}, frozenset()
            code, values, objects = self._resolve(action, name, proposal.arguments[name])
            if code != "resolved":
                return code, {}, frozenset()
            resolved[name] = values
            binding = action.bindings[name]
            if binding.value_format == "json_filter":
                continue  # 字段关系已由完整、经认证的发现集合生成JSON过滤器。
            proposed = proposal.arguments[name]
            proposed = proposed if isinstance(proposed, list) else [proposed]
            rows = {obj.object_id for obj in objects if any(
                type(value) is type(actual) and value == actual
                for value in proposed
                for actual in (obj.object_id if binding.value_field in {"id", "object_id"} else obj.attributes.get(binding.value_field),)
            )}
            group = (binding.from_action, binding.object_type)
            relational_rows[group] = relational_rows.get(group, rows) & rows
            if not relational_rows[group]:
                return "binding_relationship_conflict", {}, frozenset()
        return "matched", resolved, frozenset(resolved)

    def _sources(self, proposal: ActionProposal, matches: tuple[ContractAction, ...], certified: frozenset[str]) -> GuardDecision | None:
        side_effect = any(action.role not in {"discover", "read"} for action in matches)
        if self.ablation_profile == "whole_call_source" and side_effect:
            if any(event.source_type in UNTRUSTED_SOURCES for event in proposal.provenance):
                return self._decision(proposal, "DENY", "whole_call_untrusted_source")
            if not proposal.provenance or any(event.trust_level not in {"trusted", "model_generated", "untrusted"} for event in proposal.provenance):
                return self._decision(proposal, "ASK", "whole_call_source_unknown")
        if "provenance" not in self.modules:
            return None
        sources = set(matches[0].permitted_argument_sources)
        for action in matches[1:]:
            sources.intersection_update(action.permitted_argument_sources)
        for event in proposal.provenance:
            name = event.argument_path.removeprefix("arguments.").split(".", 1)[0].split("[", 1)[0]
            roles = {action.argument_roles.get(name, "value") for action in matches}
            untrusted = event.source_type in UNTRUSTED_SOURCES
            if roles & {"target", "query"} and untrusted:
                if provenance_uses_instruction_field(event):
                    return self._decision(proposal, "DENY", "instruction_field_cannot_drive_action_selector")
                if name not in certified:
                    return self._decision(proposal, "DENY", "untrusted_target_introduction")
            if event.source_type not in sources:
                return self._decision(proposal, "DENY" if untrusted else "ASK", "argument_source_not_permitted")
        return None

    def decide(self, proposal: ActionProposal) -> GuardDecision:
        self.last_binding_diagnostics = ()
        self.last_role_certificates = ()
        if proposal.tool == "final":
            decision = super().decide(proposal)
            if decision.decision == "ALLOW":
                self._allowed[proposal.proposal_id] = (proposal.proposal_sha256, decision.decision_id, (), {})
            return decision
        for prohibition in self.contract.prohibitions:
            if prohibition.tool == proposal.tool and all(name in proposal.arguments and predicate.matches(proposal.arguments[name]) for name, predicate in prohibition.constraints.items()):
                return self._decision(proposal, "DENY", "trusted_user_prohibition")
        if self.contract.status != "ready":
            return self._decision(proposal, "DENY" if self.contract.status == "conflict" else "ASK", "contract_" + self.contract.status)
        lexical = self.ablation_profile == "lexical_contract"
        if lexical:
            original = self.manifest
            self.manifest = self.contract.lexical_manifest or original
            try:
                lexical_decision = super().decide(proposal)
            finally:
                self.manifest = original
            if lexical_decision.decision != "ALLOW":
                return lexical_decision
        candidates = tuple(action for action in self.contract.actions if action.tool == proposal.tool)
        matches, requirements, certificates, failures = [], {}, set(), []
        for action in candidates:
            code, values, certified = self._match(action, proposal)
            if code == "matched":
                matches.append(action)
                requirements[action.action_id] = values
                certificates.update(certified)
            else:
                failures.append(code)
            self.last_binding_diagnostics += ({"action_id": action.action_id, "status": code},)
        if not matches:
            code = failures[0] if failures else "tool_outside_task_contract"
            decision = "DENY" if code in {"branch_condition_false", "application_scope_conflict", "application_argument_scope_conflict", "binding_target_conflict", "binding_relationship_conflict", "binding_object_type_conflict", "binding_stale", "binding_metadata_untrusted", "binding_untrusted_predicate_field"} else "ASK"
            return self._decision(proposal, decision, code)
        matches = tuple(matches)
        if self.contract.prohibit_external_recipients and proposal.tool in {"send_message", "send_email"}:
            checker = getattr(self.resolver, "recipient_is_internal", None)
            internal = checker(proposal) if callable(checker) else None
            if internal is not True:
                return self._decision(proposal, "DENY" if internal is False else "ASK", "external_recipient_forbidden" if internal is False else "recipient_authority_unverified")
        if "dataflow" in self.modules and self.contract.data_flow_policy:
            labels = {label for event in proposal.provenance for label in event.data_labels}
            if labels & {"private", "confidential", "restricted"}:
                checker = getattr(self.resolver, "protected_sink_allowed", None)
                permitted = checker(proposal) if callable(checker) else None
                if permitted is not True:
                    return self._decision(proposal, "DENY" if permitted is False else "ASK", "protected_data_sink_forbidden" if permitted is False else "protected_sink_unverified")
        source_error = self._sources(proposal, matches, frozenset(certificates))
        if source_error is not None:
            return source_error
        self.last_role_certificates = tuple({"argument": name, "role": "target", "scope": "current_backend_binding", "origin_preserved": True} for name in sorted(certificates))
        if any(action.requires_confirmation for action in matches):
            return self._decision(proposal, "ASK", "independent_confirmation_required")
        if lexical:
            decision = lexical_decision
        else:
            effective = tuple(ToolRule("contract-" + action.action_id, action.tool,
                                      {name: ParameterConstraint("exact", value) for name, value in proposal.arguments.items()},
                                      action.permitted_argument_sources, action.requires_confirmation,
                                      bool(self.tool_schemas and self.tool_schemas[action.tool].get("side_effect", False))) for action in matches)
            original_manifest, original_modules = self.manifest, self.modules
            self.manifest = replace(original_manifest, rules=effective, manifest_sha256="")
            # 仅角色级来源检查看新证书；原proposal及其data_labels不变。
            self.modules = self.modules - {"provenance"}
            try:
                decision = super().decide(proposal)
            finally:
                self.manifest, self.modules = original_manifest, original_modules
        if decision.decision == "ALLOW":
            self._allowed[proposal.proposal_id] = (proposal.proposal_sha256, decision.decision_id, matches, requirements)
        return decision

    def record_execution(self, proposal: ActionProposal, decision: GuardDecision) -> None:
        allowed = self._allowed.get(proposal.proposal_id)
        if allowed is None or decision.decision != "ALLOW" or allowed[:2] != (proposal.proposal_sha256, decision.decision_id):
            raise ValueError("only the exact authorized successful proposal can advance dependencies")
        if proposal.proposal_id in self._recorded:
            raise ValueError("execution was already recorded")
        completed = []
        for action in allowed[2]:
            needed = self._required_values.setdefault(action.action_id, allowed[3][action.action_id])
            seen = self._seen_values.setdefault(action.action_id, {})
            for name in needed:
                values = proposal.arguments[name]
                values = values if isinstance(values, list) else [values]
                seen.setdefault(name, []).extend(value for value in values if value not in seen.get(name, []))
            if all(all(value in seen.get(name, []) for value in values) for name, values in needed.items()):
                if action.action_id not in self._successful_actions:
                    self._successful_actions.append(action.action_id)
                completed.append(action.action_id)
        self._recorded[proposal.proposal_id] = (proposal.proposal_sha256, tuple(completed))
        super().record_execution(proposal, decision)

    def observe_success(self, proposal: ActionProposal, observation: Any) -> None:
        recorded = self._recorded.get(proposal.proposal_id)
        if recorded is None or recorded[0] != proposal.proposal_sha256:
            raise ValueError("observation requires the exact recorded successful action")
        observer = getattr(self.resolver, "observe_success", None)
        if callable(observer):
            observer(proposal, observation, action_ids=recorded[1])
