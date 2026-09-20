"""Experimental in-process confirmation boundary; NOT production authentication.

Only the out-of-band simulation controller calls ``controller_respond``.
Model/tool text has no route to it. Tickets are task/request/proposal/manifest
bound, expire, and are single-use. Confirmation cannot widen policy or overturn
DENY. Historical m3_guard and E1--E6 remain unchanged.
"""

from __future__ import annotations

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
    """A common confirmation wrapper for NEW policy/full experimental profiles."""

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
        # Legacy approvals cannot satisfy the new independent session.
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
        # The common wrapper deliberately requests confirmation even for policy-only.
        # No control is auto-executed here; an allow is only a simulation eligibility.
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
        # No deserialization, authority inference or task mutation from tool/model text.
        del payload
        return ConfirmationOutcome("untrusted_confirmation_rejected")

    def controller_respond(self, ticket_id: str, *, vote: str) -> ConfirmationOutcome:
        """Trusted simulation-controller entry point, never exposed to the provider."""
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
        return ConfirmationOutcome("allow_simulated_effect_once")


def without_legacy_approvals(manifest: TaskPolicyManifest) -> TaskPolicyManifest:
    """Independent copy for callers holding mutable nested mappings."""
    return replace(copy.deepcopy(manifest), approvals=(), manifest_sha256="")
