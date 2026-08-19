"""Public-matrix DeepSeek JSON client with exact Pro/Flash role binding."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Mapping

from experiments.paper_v2.deepseek_json_client_v2 import (
    DeepSeekJsonOfficialClient,
)
from experiments.paper_v2.official_provider_executor import (
    ProviderConsentError,
    ProviderPayloadError,
    _provider_endpoint,
    validate_messages,
)
from experiments.paper_v2.public_provider_budget_v1 import (
    ROLE_IDENTITIES,
    PublicProviderBudgetState,
)


@dataclass
class PublicDeepSeekJsonOfficialClient(DeepSeekJsonOfficialClient):
    """Reuse the admitted JSON payload while replacing medium-only validation."""

    model_role: str = "primary"
    budget_state: PublicProviderBudgetState = field(repr=False)

    def __post_init__(self) -> None:
        self.provider_id = self.provider_id.casefold().strip()
        if self.provider_id != "deepseek":
            raise ProviderPayloadError(
                "public DeepSeek client requires provider_id=deepseek"
            )
        if self.model_role not in ROLE_IDENTITIES:
            raise ProviderPayloadError("unsupported public model role")
        active = copy.deepcopy(dict(self.policy or {}))
        if (
            active.get("schema_version")
            != "m3-paper-v2-public-role-budget-policy-1.0"
            or active.get("public_model_role") != self.model_role
            or active.get("deepseek", {}).get("model_id")
            != ROLE_IDENTITIES[self.model_role]
        ):
            raise ProviderPayloadError("public role policy/client identity drift")
        self.policy = active
        if (
            self.budget_state.provider_id != self.provider_id
            or dict(self.budget_state.policy) != active
            or self.budget_state.role != self.model_role
        ):
            raise ProviderPayloadError("public budget state/client drift")
        if not isinstance(self.api_key, str) or not self.api_key.strip():
            raise ProviderPayloadError("api_key is required at execution time")
        if "\r" in self.api_key or "\n" in self.api_key:
            raise ProviderPayloadError(
                "api_key contains invalid control characters"
            )
        if self.temperature != 0:
            raise ProviderPayloadError(
                "formal provider temperature must be zero"
            )
        output_bound = int(
            active["deepseek"]["dynamic_fuse"][
                "next_request_output_tokens_upper_bound"
            ]
        )
        if self.max_tokens < 1 or self.max_tokens > output_bound:
            raise ProviderPayloadError("max_tokens exceeds the public bound")
        if self.timeout <= 0:
            raise ProviderPayloadError("timeout must be positive")
        if self.transport is None and not self.network_consent:
            raise ProviderConsentError(
                "real official transport requires explicit network consent"
            )
        _provider_endpoint(active, self.provider_id)
        validate_messages(
            [{"role": "user", "content": "qualification placeholder"}],
            content_class=self.content_class,
            policy=active,
        )

    @property
    def public_identity(self) -> Mapping[str, Any]:
        return {
            "provider_id": self.provider_id,
            "model_role": self.model_role,
            "model_id": self.model,
            "endpoint": self.endpoint,
        }

