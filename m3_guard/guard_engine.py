"""面向 M3_PI_Guard 实验的公共模块化 Guard 防护引擎接口。

本模块汇聚了策略检查、数据流审计与各类提示注入检测器，对外暴露统一的
evaluate_guard 与 guard_decide 函数，输出包含决策、风险分数、违规理由和审计追踪的 GuardResult。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter_ns
from typing import Any, Callable

from .config import GuardConfig
from .dataflow import analyze_dataflow, extract_data_labels
from .detector import (
    detect_instruction_like_text,
    detect_intent_action_mismatch,
    detect_multilingual_obfuscation,
    detect_structured_injection,
    detect_tool_lure,
)
from .policy_engine import VALID_DECISIONS, decision_rank, decide, is_authorized_action


@dataclass(frozen=True)
class GuardResult:
    decision: str
    risk: float
    reasons: list[str]
    trace: list[dict[str, Any]] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)

    def as_tuple(self) -> tuple[str, float, list[str]]:
        return self.decision, self.risk, list(self.reasons)


def guard_decide(
    context: dict[str, Any],
    tool_call: dict[str, Any],
    mode: str = "full_guard",
    *,
    config: GuardConfig | dict[str, Any] | None = None,
) -> tuple[str, float, list[str]]:
    """兼容性 API，返回决策元组 ``(decision, risk, reasons)``。"""

    return evaluate_guard(context, tool_call, mode=mode, config=config).as_tuple()


def evaluate_guard(
    context: dict[str, Any],
    tool_call: dict[str, Any],
    mode: str = "full_guard",
    *,
    config: GuardConfig | dict[str, Any] | None = None,
) -> GuardResult:
    """严格评估一次所有已启用的防御子模块，并保留完整的审计追踪日志（Trace）。

    参数:
        context: 包含当前任务、观测历史与元数据的上下文环境。
        tool_call: 包含目标工具名与参数的拟议调用字典。
        mode: 防护模式名称（默认 'full_guard'）。
        config: 可选的显式 GuardConfig 配置对象。

    返回:
        GuardResult: 综合各防御子模块结果所生成的不可变防护决策凭单。
    """

    context = context if isinstance(context, dict) else {}
    if not isinstance(tool_call, dict):
        return GuardResult("deny", 0.85, ["invalid_tool_call"])

    resolved = _resolve_config(mode, config)
    if resolved.mode == "off":
        return GuardResult(
            "allow",
            0.0,
            ["guard_disabled"],
            config=resolved.as_dict(),
        )

    tool = str(tool_call.get("tool", "")).strip()
    arguments = tool_call.get("arguments")
    if not isinstance(arguments, dict):
        arguments = {}
    normalized_call = {"tool": tool, "arguments": arguments}

    case = context.get("case", {})
    case = case if isinstance(case, dict) else {}
    runtime_texts = [case.get("user_task", ""), case.get("document_content", "")]

    risk = 0.0
    reasons: list[str] = []
    trace: list[dict[str, Any]] = []
    forced_decisions: list[str] = []
    policy_decision = "allow"

    dataflow = None
    if resolved.enabled("dataflow"):
        started = perf_counter_ns()
        dataflow = analyze_dataflow(context, normalized_call)
        module_reasons = _unique(dataflow.reasons + dataflow.labels)
        module_risk = float(dataflow.risk_delta)
        module_decision = "allow"
        if dataflow.exfiltration or (
            tool == "write_file" and dataflow.contains_sensitive
        ):
            module_risk = max(module_risk, 0.95)
            module_decision = "deny"
            forced_decisions.append("deny")
            module_reasons.append("dataflow_policy_violation")
        risk = max(risk, module_risk)
        reasons.extend(module_reasons)
        trace.append(
            _trace(
                "dataflow",
                module_risk,
                module_decision,
                module_reasons,
                started,
            )
        )

    if resolved.enabled("policy"):
        started = perf_counter_ns()
        # Dataflow is an independent module.  The policy call must never invoke
        # it implicitly, otherwise policy_only/no_dataflow ablations are false.
        policy = decide(context, normalized_call, enable_dataflow=False)
        policy_decision = policy.decision if policy.decision in VALID_DECISIONS else "deny"
        risk = max(risk, float(policy.risk))
        reasons.extend(policy.reasons)
        if policy.forced:
            forced_decisions.append(policy_decision)
        trace.append(
            _trace(
                "policy",
                float(policy.risk),
                policy_decision,
                policy.reasons,
                started,
            )
        )

    detector_specs: tuple[tuple[str, Callable[[Any], list[str]], float], ...] = (
        ("instruction_detector", detect_instruction_like_text, 0.30),
        ("tool_lure_detector", detect_tool_lure, 0.25),
        ("structured_detector", detect_structured_injection, 0.20),
        ("multilingual_detector", detect_multilingual_obfuscation, 0.10),
    )
    authorized_action = bool(
        tool != "final" and is_authorized_action(context, tool, arguments)
    )
    for module, detector, base_delta in detector_specs:
        # A safe final answer should not be blocked merely because its source
        # document contained an injection. Final output is handled by DLP.
        if tool == "final" or not resolved.enabled(module):
            continue
        started = perf_counter_ns()
        module_reasons: list[str] = []
        # Document detectors describe the untrusted carrier, not the semantic
        # safety of an exact trusted action. Penalizing a positively authorized
        # first step because its source document contains an injection creates
        # false positives and prevents the Agent from reaching the later unsafe
        # proposal that Guard must inspect. Dataflow and policy still run first
        # and can deny sensitive content, off-targets, or forbidden effects.
        if not authorized_action:
            for text in runtime_texts:
                if text:
                    module_reasons.extend(detector(text))
        module_reasons = _unique(module_reasons)
        module_risk = base_delta if module_reasons else 0.0
        if module == "structured_detector" and "json_rpc_injection" in module_reasons:
            module_risk += 0.20
        risk += module_risk
        reasons.extend(module_reasons)
        trace.append(_trace(module, module_risk, "allow", module_reasons, started))

    if tool != "final" and resolved.enabled("intent_action"):
        started = perf_counter_ns()
        # Exact positive authorization is the strongest available statement of
        # trusted intent. Re-applying a keyword-only mismatch to the same call
        # double-counts risk and can turn a legitimate side effect into ASK.
        mismatch = (
            detect_intent_action_mismatch(case.get("user_task", ""), tool)
            if not authorized_action
            else None
        )
        module_risk = 0.0 if mismatch is None else float(mismatch.risk_delta)
        module_reasons = [] if mismatch is None else mismatch.reasons
        risk += module_risk
        reasons.extend(module_reasons)
        trace.append(
            _trace(
                "intent_action",
                module_risk,
                "allow",
                module_reasons,
                started,
            )
        )

    if resolved.enabled("output_dlp") and tool == "final":
        started = perf_counter_ns()
        output_labels = extract_data_labels(arguments.get("answer", ""))
        module_reasons = [f"output_{label}" for label in output_labels]
        module_risk = 0.95 if output_labels else 0.0
        module_decision = "deny" if output_labels else "allow"
        if output_labels:
            module_reasons.append("sensitive_final_output")
            forced_decisions.append("deny")
        risk = max(risk, module_risk)
        reasons.extend(module_reasons)
        trace.append(
            _trace(
                "output_dlp",
                module_risk,
                module_decision,
                module_reasons,
                started,
            )
        )

    risk = _clamp(risk)
    threshold_decision = _decision_from_risk(risk, resolved)
    decision = _max_decision(policy_decision, threshold_decision)
    for forced in forced_decisions:
        decision = _max_decision(decision, forced)
    if decision not in VALID_DECISIONS:
        decision = "deny"

    return GuardResult(
        decision=decision,
        risk=risk,
        reasons=_unique(reasons) or ["guard_modules_no_signal"],
        trace=trace,
        config=resolved.as_dict(),
    )


def _resolve_config(
    mode: str,
    config: GuardConfig | dict[str, Any] | None,
) -> GuardConfig:
    if isinstance(config, GuardConfig):
        return config
    if isinstance(config, dict):
        return GuardConfig.resolve(
            config.get("mode", mode),
            modules=config.get("modules"),
            ask_threshold=float(config.get("ask_threshold", 0.35)),
            deny_threshold=float(config.get("deny_threshold", 0.65)),
        )
    return GuardConfig.resolve(mode)


def _decision_from_risk(risk: float, config: GuardConfig) -> str:
    if risk >= config.deny_threshold:
        return "deny"
    if risk >= config.ask_threshold:
        return "ask"
    return "allow"


def _max_decision(left: str, right: str) -> str:
    return left if decision_rank(left) >= decision_rank(right) else right


def _trace(
    module: str,
    risk: float,
    decision: str,
    reasons: list[str],
    started_ns: int,
) -> dict[str, Any]:
    return {
        "module": module,
        "risk": _clamp(risk),
        "decision": decision,
        "reasons": _unique(list(reasons)),
        "latency_ms": round((perf_counter_ns() - started_ns) / 1_000_000, 6),
    }


def _clamp(value: float) -> float:
    return round(max(0.0, min(1.0, float(value))), 4)


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result
