"""进程内交互式确认边界实验会话（仅供研究实验使用，非生产授权）。

模拟在遇到不确定敏感动作（ASK）时的人机协同确认逻辑与状态机变迁。
"""

from __future__ import annotations

# ASK 的独立确认模拟：不是生产认证，也不是模型自己说“用户已批准”就有效。
# 票据绑定任务、可信请求、完整动作和权限清单，且过期后失效、只能消费一次。

import copy
from dataclasses import dataclass, replace
from typing import Any, Callable
from uuid import uuid4

from m3_guard.runtime_monitor import ActionProposal, RuntimeMonitor
from m3_guard.task_policy import TaskPolicyManifest


@dataclass(frozen=True)
class ConfirmationOutcome:
    status: str
    reason_codes: tuple[str, ...] = ()
    ticket_id: str | None = None


@dataclass
class _Pending:
    task_id: str
    request_digest: str
    proposal_digest: str
    manifest_digest: str
    expires: float
    vote: str = "absent"
    consumed: bool = False


class ConfirmationSession:
    """用于 NEW 策略/完整实验配置的通用确认包装器。"""

    def __init__(self, *, clock: Callable[[], float], ttl_seconds: float = 120):
        if ttl_seconds <= 0 or ttl_seconds > 3600:
            raise ValueError("confirmation TTL out of bounds")
        self._clock, self._ttl = clock, ttl_seconds
        self._pending: dict[str, _Pending] = {}

    def request(
        self,
        *,
        task_id: str,
        request_digest: str,
        proposal: ActionProposal,
        manifest: TaskPolicyManifest,
        modules: frozenset[str],
        monitor: RuntimeMonitor | None = None,
    ) -> ConfirmationOutcome:
        if not task_id or not request_digest:
            raise ValueError("task and trusted request identity are mandatory")
        # 历史批准记录不能冒充本次独立会话的批准。
        clean = replace(manifest, approvals=(), manifest_sha256="")
        if monitor is None:
            decision = RuntimeMonitor(clean, modules=modules).decide(proposal)
        else:
            if monitor.manifest != manifest or monitor.modules != modules:
                raise ValueError("confirmation monitor/manifest/modules binding mismatch")
            if manifest.approvals:
                raise ValueError("corrected confirmation does not accept legacy approvals")
            decision = monitor.decide(proposal)
        if decision.decision == "DENY":
            return ConfirmationOutcome("denied_by_guard", decision.violated_rules)
        if decision.decision == "ASK" and decision.violated_rules != (
            "independent_confirmation_required",
        ):
            return ConfirmationOutcome(
                "blocked_scope_not_expandable", decision.violated_rules
            )
        # 本实验封装对 policy-only 也请求确认，以保持对照一致。
        # 这里只创建待确认资格，不自动执行，也不能用确认扩大现有权限。
        ticket = str(uuid4())
        self._pending[ticket] = _Pending(
            task_id,
            request_digest,
            proposal.proposal_sha256,
            manifest.manifest_sha256,
            self._clock() + self._ttl,
        )
        return ConfirmationOutcome("awaiting_confirmation", (), ticket)

    def receive_untrusted(self, payload: Any) -> ConfirmationOutcome:
        # 不解析不可信文本中的批准，不从中推断身份，也不修改任务。
        del payload
        return ConfirmationOutcome("untrusted_confirmation_rejected")

    def controller_respond(self, ticket_id: str, *, vote: str) -> ConfirmationOutcome:
        """受信任的模拟控制器入口点，绝不向提供商暴露。"""
        if vote not in {"approved", "denied"}:
            raise ValueError("invalid controller vote")
        pending = self._pending.get(ticket_id)
        if pending is None:
            return ConfirmationOutcome("unknown_ticket")
        if pending.consumed or pending.vote != "absent":
            return ConfirmationOutcome("decision_already_terminal")
        if self._clock() >= pending.expires:
            return ConfirmationOutcome("expired")
        pending.vote = vote
        return ConfirmationOutcome(vote)

    def consume(
        self,
        ticket_id: str,
        *,
        task_id: str,
        request_digest: str,
        proposal: ActionProposal,
        manifest: TaskPolicyManifest,
    ) -> ConfirmationOutcome:
        pending = self._pending.get(ticket_id)
        if pending is None:
            return ConfirmationOutcome("unknown_ticket")
        if pending.consumed:
            return ConfirmationOutcome("replay_rejected")
        if self._clock() >= pending.expires:
            return ConfirmationOutcome("expired")
        if (
            task_id,
            request_digest,
            proposal.proposal_sha256,
            manifest.manifest_sha256,
        ) != (
            pending.task_id,
            pending.request_digest,
            pending.proposal_digest,
            pending.manifest_digest,
        ):
            return ConfirmationOutcome("binding_mismatch")
        if pending.vote != "approved":
            return ConfirmationOutcome(
                "denied" if pending.vote == "denied" else "confirmation_absent"
            )
        pending.consumed = True
        # 先标记已使用再返回资格，后续重复消费必须拒绝。
        return ConfirmationOutcome("allow_simulated_effect_once")


def without_legacy_approvals(manifest: TaskPolicyManifest) -> TaskPolicyManifest:
    """为持有可变嵌套映射的调用方提供独立副本。"""
    return replace(copy.deepcopy(manifest), approvals=(), manifest_sha256="")
