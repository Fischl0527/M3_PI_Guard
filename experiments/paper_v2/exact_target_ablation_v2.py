"""Explicit exact-target oracle control; historical exact_gold is unchanged.

Only declared content fields may vary. All other supplied fields must match the
derived scope or an explicit tool default. Unsupported field roles fail visibly.
This is not a deployed non-oracle authorization mechanism.
"""

from __future__ import annotations

import copy
import json
from dataclasses import replace
from typing import Any, Mapping

from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.exact_gold_ablation import ExactGoldAblationError, ExactGoldAblationMonitor
from m3_guard.runtime_monitor import ActionProposal, GuardDecision
from m3_guard.task_policy import ParameterConstraint, TaskPolicyManifest, ToolRule
from m3_guard.tool_contracts_v2 import argument_contract_error


MONITOR_VERSION = "m3-exact-target-v2"
# 环境/实现声明的字段角色，绝不由模型或攻击文本指定。
TOOL_ARGUMENT_ROLES = {
    "read_file": {"path": "target", "file_path": "target"},
    "write_file": {"path": "target", "content": "content"},
    "send_email": {
        "to": "target", "recipients": "target", "cc": "security", "bcc": "security",
        "subject": "content", "body": "content", "attachments": "security",
    },
    "call_api": {"endpoint": "target", "params": "security"},
    "send_message": {"channel": "target", "recipient": "target", "content": "content", "body": "content"},
    "send_channel_message": {"channel": "target", "body": "content"},
    "send_direct_message": {"recipient": "target", "body": "content"},
    "append_to_file": {"file_id": "target", "content": "content"},
    "create_file": {"filename": "target", "content": "content"},
    "post_webpage": {"url": "target", "content": "content"},
    "create_calendar_event": {
        "title": "content", "description": "content", "participants": "target",
        "start_time": "security", "end_time": "security", "location": "security",
    },
}
# 当前固定AgentDojo工具中的安全/选择参数逐个声明；新增字段不会自动被分类。
_SECURITY_FIELDS = {
    "add_calendar_event_participants": ("event_id", "participants"),
    "add_user_to_channel": ("channel", "user"),
    "cancel_calendar_event": ("event_id",),
    "check_restaurant_opening_hours": ("restaurant_names",),
    "delete_email": ("email_id",), "delete_file": ("file_id",),
    "get_all_car_rental_companies_in_city": ("city",),
    "get_all_hotels_in_city": ("city",), "get_all_restaurants_in_city": ("city",),
    "get_car_fuel_options": ("company_name",), "get_car_price_per_day": ("company_name",),
    "get_car_rental_address": ("company_name",), "get_car_types_available": ("company_name",),
    "get_contact_information_for_restaurants": ("restaurant_names",),
    "get_cuisine_type_for_restaurants": ("restaurant_names",),
    "get_day_calendar_events": ("day",),
    "get_dietary_restrictions_for_all_restaurants": ("restaurant_names",),
    "get_file_by_id": ("file_id",), "get_flight_information": ("arrival_city", "departure_city"),
    "get_hotels_address": ("hotel_name",), "get_hotels_prices": ("hotel_names",),
    "get_most_recent_transactions": ("n",), "get_price_for_restaurants": ("restaurant_names",),
    "get_rating_reviews_for_car_rental": ("company_name",),
    "get_rating_reviews_for_hotels": ("hotel_names",),
    "get_rating_reviews_for_restaurants": ("restaurant_names",),
    "get_restaurants_address": ("restaurant_names",), "get_users_in_channel": ("channel",),
    "get_webpage": ("url",), "invite_user_to_slack": ("user", "user_email"),
    "read_channel_messages": ("channel",), "read_inbox": ("user",),
    "remove_user_from_slack": ("user",),
    "reschedule_calendar_event": ("event_id", "new_end_time", "new_start_time"),
    "reserve_car_rental": ("company", "end_time", "start_time"),
    "reserve_hotel": ("hotel", "end_day", "start_day"),
    "reserve_restaurant": ("restaurant", "start_time"),
    "schedule_transaction": ("recipient", "amount", "subject", "date", "recurring"),
    "search_calendar_events": ("date", "query"), "search_contacts_by_email": ("query",),
    "search_contacts_by_name": ("query",), "search_emails": ("query", "sender"),
    "search_files": ("query",), "search_files_by_filename": ("filename",),
    "send_money": ("recipient", "amount", "subject", "date"),
    "share_file": ("file_id", "email", "permission"),
    "update_password": ("password",),
    "update_scheduled_transaction": ("id", "recipient", "amount", "subject", "date", "recurring"),
    "update_user_info": ("city", "first_name", "last_name", "street"),
}
TOOL_ARGUMENT_ROLES.update({tool: dict.fromkeys(fields, "security") for tool, fields in _SECURITY_FIELDS.items()})
TOOL_ARGUMENT_ROLES.update(dict.fromkeys((
    "get_balance", "get_channels", "get_current_day", "get_draft_emails", "get_iban",
    "get_received_emails", "get_scheduled_transactions", "get_sent_emails",
    "get_unread_emails", "get_user_info", "get_user_information", "list_files",
), {}))


def build_exact_target_authorization_v2(record: Mapping[str, Any], benchmark: str) -> dict[str, Any]:
    """Offline derivation for the explicit control only; preserve repeated calls."""
    from experiments.paper_v2.medium_runtime import _agentdojo_exact_calls, _m3_exact_calls

    if benchmark not in {"m3-v2", "agentdojo-v1"}:
        raise ExactGoldAblationError("unsupported exact-target benchmark")
    calls = _m3_exact_calls(record) if benchmark == "m3-v2" else _agentdojo_exact_calls(record)
    return {
        "schema_version": "m3-paper-v2-authorization-envelope-1.0",
        "authorization_regime": "exact_target_v2",
        "source_class": "evaluator_derived_authorization",
        "formal_primary_endpoint_eligible": False,
        "rules": [{
            "rule_id": f"oracle-target-v2-{index + 1}", "tool": call["tool"],
            "argument_constraints": {
                name: {"kind": "exact", "required": True, "value": copy.deepcopy(value)}
                for name, value in call["arguments"].items()
            },
        } for index, call in enumerate(calls)],
    }


class ExactTargetMonitorV2(ExactGoldAblationMonitor):
    """Schema-complete proposals, exact security scope and single-use order."""

    modules = frozenset({"oracle_ablation", "exact_sequence", "exact_target_v2", "tool_contract"})

    def __init__(
        self, authorization: Mapping[str, Any], *,
        tool_schemas: Mapping[str, Mapping[str, Any]],
        argument_roles: Mapping[str, Mapping[str, str]] | None = None,
    ) -> None:
        if (
            authorization.get("authorization_regime") != "exact_target_v2"
            or authorization.get("source_class") != "evaluator_derived_authorization"
            or authorization.get("formal_primary_endpoint_eligible") is not False
        ):
            raise ExactGoldAblationError("exact_target_v2 requires an explicit excluded oracle control")
        self._schemas = copy.deepcopy(dict(tool_schemas))
        self._schemas["final"] = {"arguments": {"answer": {"type": "string", "required": True}}}
        self._roles = copy.deepcopy(dict(TOOL_ARGUMENT_ROLES if argument_roles is None else argument_roles))
        rules = authorization.get("rules")
        if not isinstance(rules, list):
            raise ExactGoldAblationError("exact target rules are missing")
        normalized = []
        for index, rule in enumerate(rules):
            if not isinstance(rule, Mapping):
                raise ExactGoldAblationError("exact target rule must be an object")
            tool = rule.get("tool")
            fields = self._schemas.get(tool, {}).get("arguments", {})
            roles = self._roles.get(tool, {})
            if tool not in self._schemas or tool not in self._roles or not isinstance(fields, Mapping) or set(fields) - set(roles):
                raise ExactGoldAblationError("tool argument roles are unsupported; do not infer them")
            if any(roles[name] not in {"target", "security", "content"} for name in fields):
                raise ExactGoldAblationError("invalid tool argument role")
            constraints = rule.get("argument_constraints")
            if not isinstance(constraints, Mapping) or set(constraints) - set(fields):
                raise ExactGoldAblationError("exact target names undeclared arguments")
            arguments = {}
            for name, constraint in constraints.items():
                if not isinstance(constraint, Mapping) or constraint.get("kind") != "exact" or constraint.get("required") is not True:
                    raise ExactGoldAblationError("exact target requires explicit exact constraints")
                arguments[name] = copy.deepcopy(constraint.get("value"))
            for name, detail in fields.items():
                if roles[name] != "content" and detail.get("required") is True and name not in arguments:
                    raise ExactGoldAblationError("required security scope is unconstrained")
            normalized.append({"rule_id": str(rule.get("rule_id", f"target-{index + 1}")), "tool": tool, "arguments": arguments})
        self._authorization = copy.deepcopy(dict(authorization))
        self._rules = tuple(normalized)
        self._next_index = 0
        self._pending: tuple[str, str] | None = None
        self._decisions_started = False
        self.executed_tools: tuple[str, ...] = ()
        self.manifest_sha256 = sha256_canonical_json(self._authorization)
        self.restriction_monitor = None
        self._restriction_decision = None

    def attach_runtime_restrictions(self, template: TaskPolicyManifest, *, modules, tracker) -> None:
        """Derived oracle scope goes to Guard only; the provider keeps template."""
        from m3_guard.runtime_monitor_corrected_v2 import RuntimeMonitorCorrectedV2

        if self.restriction_monitor is not None or self._decisions_started:
            raise ExactGoldAblationError("runtime restrictions must be attached exactly once before decisions or execution")
        rules = []
        for item in self._rules:
            constraints = {}
            for name, detail in self._schemas[item["tool"]]["arguments"].items():
                role = self._roles[item["tool"]][name]
                if role == "content":
                    constraint = ParameterConstraint("type", detail["type"], required=detail.get("required") is True)
                elif name in item["arguments"]:
                    constraint = ParameterConstraint("exact", item["arguments"][name])
                else:
                    constraint = ParameterConstraint("exact", detail["default"], required=False) if "default" in detail else ParameterConstraint("enum", (), required=False)
                constraints[name] = constraint
            rules.append(ToolRule(item["rule_id"], item["tool"], constraints, description="Explicit evaluator-derived exact_target_v2 oracle control, never deployed authorization."))
        guard_manifest = replace(template, manifest_id="oracle-target-v2-" + template.manifest_id, rules=tuple(rules), approvals=(), manifest_sha256="")
        self.restriction_monitor = RuntimeMonitorCorrectedV2(guard_manifest, modules=modules, tracker=tracker, tool_schemas=self._schemas)
        self.modules = self.modules | modules

    def _decision(self, proposal, decision, *, rule_id, violated, reason):
        old = super()._decision(proposal, decision, rule_id=rule_id, violated=violated, reason=reason)
        return replace(
            old, decision_id="target-v2-" + sha256_canonical_json({"version": MONITOR_VERSION, "decision": old.decision_id})[:20],
            suggested_recovery="none" if decision == "ALLOW" else "Follow the declared schema and exact-target sequence.",
        )

    def _match_error(self, proposal: ActionProposal, rule: Mapping[str, Any]) -> str | None:
        if proposal.tool != rule["tool"]:
            return "target_tool_or_sequence_mismatch"
        error = argument_contract_error(proposal.tool, proposal.arguments, self._schemas)
        if error:
            return error
        fields, roles = self._schemas[proposal.tool]["arguments"], self._roles[proposal.tool]
        for name in set(rule["arguments"]) | set(proposal.arguments):
            if roles[name] == "content":
                continue
            if name in rule["arguments"]:
                if name not in proposal.arguments:
                    return "target_argument_missing"
                expected = rule["arguments"][name]
            elif "default" in fields[name]:
                expected = fields[name]["default"]
            else:
                return "unconstrained_security_argument"
            if json.dumps(proposal.arguments[name], sort_keys=True) != json.dumps(expected, sort_keys=True):
                return "target_argument_mismatch"
        return None

    def decide(self, proposal: ActionProposal) -> GuardDecision:
        self._decisions_started = True
        self._pending = None
        self._restriction_decision = None
        if proposal.tool == "final":
            error, rule_id = argument_contract_error("final", proposal.arguments, self._schemas), None
        elif self._next_index >= len(self._rules):
            error, rule_id = "target_sequence_exhausted", None
        else:
            rule = self._rules[self._next_index]
            error, rule_id = self._match_error(proposal, rule), rule["rule_id"]
        decision = self._decision(
            proposal, "DENY" if error else "ALLOW", rule_id=rule_id,
            violated=(error,) if error else (),
            reason="Exact target or tool contract mismatch." if error else "Schema-complete action matches the declared exact security scope.",
        )
        if not error:
            if self.restriction_monitor is not None:
                guard = self.restriction_monitor.decide(proposal)
                if guard.decision != "ALLOW":
                    return replace(guard, manifest_sha256=self.manifest_sha256)
                self._restriction_decision = guard
            self._pending = (proposal.proposal_sha256, decision.decision_id)
        return decision

    def record_execution(self, proposal: ActionProposal, decision: GuardDecision) -> None:
        if (
            decision.decision != "ALLOW" or decision.manifest_sha256 != self.manifest_sha256
            or decision.proposal_sha256 != proposal.proposal_sha256
            or self._pending != (proposal.proposal_sha256, decision.decision_id)
        ):
            raise ExactGoldAblationError("only the pending exact-target decision can be recorded")
        error = argument_contract_error("final", proposal.arguments, self._schemas) if proposal.tool == "final" else self._match_error(proposal, self._rules[self._next_index])
        if error:
            raise ExactGoldAblationError("recorded action no longer matches exact-target scope")
        self._pending = None
        if self.restriction_monitor is not None:
            if self._restriction_decision is None:
                raise ExactGoldAblationError("runtime restriction decision is missing")
            self.restriction_monitor.record_execution(proposal, self._restriction_decision)
            self._restriction_decision = None
        if proposal.tool != "final":
            self._next_index += 1
            self.executed_tools = (*self.executed_tools, proposal.tool)
