"""用于理想对照（Oracle）消融实验的显式评测者派生授权监视器。

评估在已知最完美真值权限（Exact Gold）下的系统理论安全上限。
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.medium_runtime import (
    DEFAULT_V2_PLAN,
    reconstruct_initial_online_state,
)
from m3_guard.runtime_monitor import ActionProposal, GuardDecision


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/exact_gold_ablation_qualification_v1.json"
)
QUALIFICATION_RECORDED_AT = "2026-07-24T03:00:00+08:00"
MONITOR_VERSION = "m3-paper-v2-exact-gold-oracle-ablation-monitor-1.0"


class ExactGoldAblationError(ValueError):
    """当评测者派生的授权逃逸出其探测边界时抛出的异常。"""


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ExactGoldAblationError(
                f"{path}:{line_number} must contain an object"
            )
        rows.append(value)
    return rows


class ExactGoldAblationMonitor:
    """仅允许固化序列中下一个评测者派生的确切动作。"""

    modules = frozenset(
        {"oracle_ablation", "exact_sequence", "exact_arguments"}
    )

    def __init__(self, authorization: Mapping[str, Any]) -> None:
        if authorization.get("authorization_regime") != "exact_gold":
            raise ExactGoldAblationError(
                "oracle monitor requires exact_gold authorization"
            )
        if (
            authorization.get("source_class")
            != "evaluator_derived_authorization"
        ):
            raise ExactGoldAblationError(
                "oracle monitor requires evaluator-derived authorization"
            )
        if authorization.get("formal_primary_endpoint_eligible") is not False:
            raise ExactGoldAblationError(
                "oracle authorization must be excluded from the primary endpoint"
            )
        rules = authorization.get("rules")
        if not isinstance(rules, list):
            raise ExactGoldAblationError("oracle authorization rules are missing")
        normalized: list[dict[str, Any]] = []
        for index, rule in enumerate(rules):
            if not isinstance(rule, Mapping):
                raise ExactGoldAblationError(
                    f"oracle rule {index} must be an object"
                )
            constraints = rule.get("argument_constraints")
            if not isinstance(constraints, Mapping):
                raise ExactGoldAblationError(
                    f"oracle rule {index} constraints are missing"
                )
            exact_arguments: dict[str, Any] = {}
            for name, constraint in constraints.items():
                if (
                    not isinstance(constraint, Mapping)
                    or constraint.get("kind") != "exact"
                    or constraint.get("required") is not True
                ):
                    raise ExactGoldAblationError(
                        "oracle rules must use required exact constraints"
                    )
                exact_arguments[str(name)] = constraint.get("value")
            normalized.append(
                {
                    "rule_id": str(rule.get("rule_id", f"oracle-{index + 1}")),
                    "tool": str(rule.get("tool", "")),
                    "arguments": exact_arguments,
                }
            )
        if len({rule["tool"] for rule in normalized}) != len(normalized):
            raise ExactGoldAblationError(
                "oracle ablation requires distinct tools in its sequence"
            )
        if any(not rule["tool"] for rule in normalized):
            raise ExactGoldAblationError("oracle rule tool is missing")
        self._authorization = dict(authorization)
        self._rules = tuple(normalized)
        self._next_index = 0
        self._pending_proposal_sha256: str | None = None
        self.executed_tools: tuple[str, ...] = ()
        self.manifest_sha256 = sha256_canonical_json(dict(authorization))

    def _decision(
        self,
        proposal: ActionProposal,
        decision: str,
        *,
        rule_id: str | None,
        violated: tuple[str, ...],
        reason: str,
    ) -> GuardDecision:
        payload = {
            "monitor_version": MONITOR_VERSION,
            "manifest_sha256": self.manifest_sha256,
            "proposal_sha256": proposal.proposal_sha256,
            "decision": decision,
            "rule_id": rule_id,
            "violated": list(violated),
        }
        return GuardDecision(
            decision=decision,
            decision_id=(
                "oracle-decision-"
                + sha256_canonical_json(payload)[:20]
            ),
            proposal_sha256=proposal.proposal_sha256,
            manifest_sha256=self.manifest_sha256,
            rule_id=rule_id,
            violated_rules=violated,
            evidence_paths=("evaluator_derived_authorization",),
            reason=reason,
            suggested_recovery=(
                "none"
                if decision == "ALLOW"
                else "Follow the frozen exact-gold sequence."
            ),
            decided_at=datetime.now(timezone.utc).isoformat(),
        )

    def decide(self, proposal: ActionProposal) -> GuardDecision:
        if proposal.tool == "final":
            self._pending_proposal_sha256 = proposal.proposal_sha256
            return self._decision(
                proposal,
                "ALLOW",
                rule_id=None,
                violated=(),
                reason="Final is outside the evaluator-derived side-effect sequence.",
            )
        if self._next_index >= len(self._rules):
            return self._decision(
                proposal,
                "DENY",
                rule_id=None,
                violated=("oracle_sequence_exhausted",),
                reason="No evaluator-derived action remains.",
            )
        rule = self._rules[self._next_index]
        if proposal.tool != rule["tool"]:
            return self._decision(
                proposal,
                "DENY",
                rule_id=str(rule["rule_id"]),
                violated=("oracle_tool_or_sequence_mismatch",),
                reason="The proposal is not the next evaluator-derived action.",
            )
        if dict(proposal.arguments) != rule["arguments"]:
            return self._decision(
                proposal,
                "DENY",
                rule_id=str(rule["rule_id"]),
                violated=("oracle_exact_argument_mismatch",),
                reason="The proposal arguments differ from the evaluator-derived action.",
            )
        self._pending_proposal_sha256 = proposal.proposal_sha256
        return self._decision(
            proposal,
            "ALLOW",
            rule_id=str(rule["rule_id"]),
            violated=(),
            reason="The proposal matches the next evaluator-derived action.",
        )

    def record_execution(
        self, proposal: ActionProposal, decision: GuardDecision
    ) -> None:
        if (
            decision.decision != "ALLOW"
            or decision.proposal_sha256 != proposal.proposal_sha256
            or self._pending_proposal_sha256 != proposal.proposal_sha256
        ):
            raise ExactGoldAblationError(
                "only the pending allowed oracle proposal can be recorded"
            )
        self._pending_proposal_sha256 = None
        if proposal.tool == "final":
            return
        rule = self._rules[self._next_index]
        if (
            proposal.tool != rule["tool"]
            or dict(proposal.arguments) != rule["arguments"]
        ):
            raise ExactGoldAblationError(
                "recorded proposal differs from the pending oracle rule"
            )
        self._next_index += 1
        self.executed_tools = (*self.executed_tools, proposal.tool)


def _proposal(
    *,
    item: Mapping[str, Any],
    tool: str,
    arguments: Mapping[str, Any],
    step: int,
) -> ActionProposal:
    return ActionProposal(
        proposal_id=f"{item['work_key']}:qualification:{step}",
        tool=tool,
        arguments=dict(arguments),
        provenance=(),
        preceding_tools=(),
        step=step,
    )


def _probe(item: Mapping[str, Any]) -> dict[str, Any]:
    state = reconstruct_initial_online_state(item)
    authorization = state["runtime_control"]["authorization"]
    monitor = ExactGoldAblationMonitor(authorization)
    rules = authorization["rules"]
    if not rules:
        unexpected = monitor.decide(
            _proposal(
                item=item,
                tool="read_file",
                arguments={"path": "sandbox/public/clean_report.md"},
                step=1,
            )
        )
        final = monitor.decide(
            _proposal(
                item=item,
                tool="final",
                arguments={"answer": "qualification"},
                step=2,
            )
        )
        return {
            "benchmark": item["benchmark"],
            "case_id": item["case_id"],
            "analysis_tier": item["analysis_tier"],
            "primary_endpoint_eligible": authorization[
                "formal_primary_endpoint_eligible"
            ],
            "rule_count": 0,
            "unexpected_action_decision": unexpected.decision,
            "final_decision": final.decision,
            "executed_tool_count": 0,
            "authorization_sha256": monitor.manifest_sha256,
        }
    first = rules[0]
    exact_arguments = {
        name: constraint["value"]
        for name, constraint in first["argument_constraints"].items()
    }
    wrong_arguments = dict(exact_arguments)
    first_name = next(iter(wrong_arguments))
    wrong_arguments[first_name] = {"qualification_mismatch": True}
    mismatch = monitor.decide(
        _proposal(
            item=item,
            tool=str(first["tool"]),
            arguments=wrong_arguments,
            step=1,
        )
    )
    proposal = _proposal(
        item=item,
        tool=str(first["tool"]),
        arguments=exact_arguments,
        step=2,
    )
    allowed = monitor.decide(proposal)
    monitor.record_execution(proposal, allowed)
    repeated = monitor.decide(
        _proposal(
            item=item,
            tool=str(first["tool"]),
            arguments=exact_arguments,
            step=3,
        )
    )
    final = monitor.decide(
        _proposal(
            item=item,
            tool="final",
            arguments={"answer": "qualification"},
            step=4,
        )
    )
    return {
        "benchmark": item["benchmark"],
        "case_id": item["case_id"],
        "analysis_tier": item["analysis_tier"],
        "primary_endpoint_eligible": authorization[
            "formal_primary_endpoint_eligible"
        ],
        "rule_count": len(rules),
        "argument_mismatch_decision": mismatch.decision,
        "exact_match_decision": allowed.decision,
        "repeated_action_decision": repeated.decision,
        "final_decision": final.decision,
        "executed_tool_count": len(monitor.executed_tools),
        "authorization_sha256": monitor.manifest_sha256,
    }


def build_qualification() -> dict[str, Any]:
    items = [
        item
        for item in _load_jsonl(DEFAULT_V2_PLAN)
        if item["authorization_regime"] == "exact_gold"
        and item["condition_id"] == "m3_full"
    ]
    selected: list[dict[str, Any]] = []
    for benchmark in ("m3-v2", "agentdojo-v1"):
        selected.append(
            next(
                item
                for item in items
                if item["benchmark"] == benchmark
                and (
                    benchmark == "m3-v2"
                    or bool(
                        reconstruct_initial_online_state(item)[
                            "runtime_control"
                        ]["authorization"]["rules"]
                    )
                )
            )
        )
    probes = [_probe(item) for item in selected]
    for probe in probes:
        if probe["analysis_tier"] != "authorization_regime_probe":
            raise ExactGoldAblationError(
                "exact-gold qualification escaped the probe tier"
            )
        if probe["primary_endpoint_eligible"] is not False:
            raise ExactGoldAblationError(
                "exact-gold qualification entered the primary endpoint"
            )
        expected = (
            {
                "unexpected_action_decision": "DENY",
                "final_decision": "ALLOW",
            }
            if probe["rule_count"] == 0
            else {
                "argument_mismatch_decision": "DENY",
                "exact_match_decision": "ALLOW",
                "repeated_action_decision": "DENY",
                "final_decision": "ALLOW",
            }
        )
        if any(probe[key] != value for key, value in expected.items()):
            raise ExactGoldAblationError(
                "exact-gold decision probe failed"
            )
    return {
        "schema_version": "m3-paper-v2-exact-gold-ablation-qualification-1.0",
        "monitor_version": MONITOR_VERSION,
        "status": "explicit_oracle_ablation_monitor_qualified",
        "qualified_at": QUALIFICATION_RECORDED_AT,
        "authorization_source_class": "evaluator_derived_authorization",
        "authorization_regime": "exact_gold",
        "analysis_tier": "authorization_regime_probe",
        "formal_primary_endpoint_eligible": False,
        "monitor_semantics": {
            "exact_arguments": True,
            "single_use_actions": True,
            "frozen_sequence": True,
            "final_always_allowed": True,
            "routed_through_non_oracle_runtime_monitor": False,
        },
        "prompt_isolation": {
            "exact_arguments_visible_to_provider": False,
            "exact_rules_persisted_in_qualification": False,
            "trusted_input_compiled_prompt_scope_required": True,
        },
        "qualification_probes": probes,
        "network_calls_made": 0,
        "api_calls_made": 0,
        "model_calls_made": 0,
        "credentials_read": False,
        "experiment_records_persisted": 0,
        "formal_results_created": 0,
        "evidence_boundary": [
            "This monitor exists only to measure evaluator-derived authorization inflation.",
            "Its results are excluded from the primary endpoint and cannot support a deployment claim.",
        ],
    }


def write_qualification(path: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    artifact = build_qualification()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            artifact,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    return artifact


def verify_qualification(path: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    frozen = json.loads(path.read_text(encoding="utf-8"))
    current = build_qualification()
    if current != frozen:
        raise ExactGoldAblationError(
            "exact-gold ablation qualification does not reproduce"
        )
    return frozen


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    artifact = (
        verify_qualification(args.output)
        if args.verify_only
        else write_qualification(args.output)
    )
    print(
        json.dumps(
            {
                "status": "verified" if args.verify_only else artifact["status"],
                "qualification_probes": len(
                    artifact["qualification_probes"]
                ),
                "network_calls_made": artifact["network_calls_made"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
