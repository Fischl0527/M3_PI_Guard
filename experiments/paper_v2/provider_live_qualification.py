"""Run one fixed, no-effect official identity request per paper-v2 provider.

The default mode is static verification and never performs a request.  Live
execution requires both ``--execute`` and the exact consent value in the
ignored local project configuration.  Prompt and response text are never
persisted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Mapping

from experiments.paper_v2.official_provider_executor import (
    OfficialProviderClient,
    ProviderBudgetState,
    provider_receipt_to_attestation,
    validate_provider_receipt,
)
from m3_core.project_config import (
    is_placeholder,
    parse_env_file,
    resolve_config_path,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/provider_live_qualification_v1.json"
)
DEFAULT_POLICY = (
    PROJECT_ROOT / "protocols/paper_upgrade_v2/dual_provider_budget_policy_v1.json"
)
QUALIFICATION_VERSION = "m3-paper-v2-provider-live-qualification-1.0"
CONSENT_VALUE = "yes_for_network_smoke"
SMOKE_MESSAGES = [
    {
        "role": "system",
        "content": (
            "Return exactly SAFE. This is a fixed synthetic connectivity and "
            "model-identity check. Do not call tools."
        ),
    },
    {
        "role": "user",
        "content": "Synthetic public input only. Return exactly SAFE.",
    },
]
PROVIDER_CONFIG = {
    "deepseek": {
        "api_key": "DEEPSEEK_API_KEY",
        "model_id": "FRONTIER_DEEPSEEK_MODEL_ID",
        "base_url": "FRONTIER_DEEPSEEK_BASE_URL",
        "content_class": "synthetic_m3_case",
    },
    "gemini": {
        "api_key": "GEMINI_API_KEY",
        "model_id": "FRONTIER_GEMINI_MODEL_ID",
        "base_url": "FRONTIER_GEMINI_BASE_URL",
        "content_class": "public_benchmark_case",
    },
}
ClientFactory = Callable[
    [str, str, Mapping[str, Any]], OfficialProviderClient
]


class ProviderLiveQualificationError(ValueError):
    """Raised when live identity evidence is unsafe or cannot be verified."""


def _load_policy(path: Path = DEFAULT_POLICY) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ProviderLiveQualificationError(
            "dual-provider policy must be an object"
        )
    return value


def _validate_config(
    values: Mapping[str, str], policy: Mapping[str, Any]
) -> None:
    if values.get("M3_FRONTIER_API_CONSENT") != CONSENT_VALUE:
        raise ProviderLiveQualificationError(
            "live provider qualification requires explicit local consent"
        )
    for provider_id, fields in PROVIDER_CONFIG.items():
        api_key = values.get(fields["api_key"])
        model_id = values.get(fields["model_id"])
        base_url = values.get(fields["base_url"])
        if is_placeholder(api_key):
            raise ProviderLiveQualificationError(
                f"{provider_id} API key is missing or a placeholder"
            )
        if model_id != policy[provider_id]["model_id"]:
            raise ProviderLiveQualificationError(
                f"{provider_id} configured model differs from the frozen policy"
            )
        if str(base_url).rstrip("/") != str(
            policy[provider_id]["base_url"]
        ).rstrip("/"):
            raise ProviderLiveQualificationError(
                f"{provider_id} base URL differs from the frozen policy"
            )


def _real_client_factory(
    provider_id: str,
    api_key: str,
    policy: Mapping[str, Any],
) -> OfficialProviderClient:
    return OfficialProviderClient(
        provider_id=provider_id,
        api_key=api_key,
        content_class=str(
            PROVIDER_CONFIG[provider_id]["content_class"]
        ),
        budget_state=ProviderBudgetState(
            provider_id=provider_id, policy=policy
        ),
        policy=policy,
        temperature=0.0,
        max_tokens=16,
        timeout=60.0,
        network_consent=True,
    )


def execute_live_qualification(
    values: Mapping[str, str],
    *,
    client_factory: ClientFactory = _real_client_factory,
    policy_path: Path = DEFAULT_POLICY,
) -> dict[str, Any]:
    """Perform exactly one no-effect request for each configured provider."""

    policy = _load_policy(policy_path)
    _validate_config(values, policy)
    results: dict[str, dict[str, Any]] = {}
    network_call_attempts = 0
    for provider_id in ("deepseek", "gemini"):
        api_key = str(
            values[PROVIDER_CONFIG[provider_id]["api_key"]]
        )
        provider_attempts = 0
        try:
            client = client_factory(provider_id, api_key, policy)
            provider_attempts = 1
            network_call_attempts += 1
            completion = client.complete(SMOKE_MESSAGES, step=1)
            receipt = dict(completion.receipt)
            validate_provider_receipt(receipt)
            attestation = provider_receipt_to_attestation(receipt)
            results[provider_id] = {
                "status": (
                    "formal_candidate_identity_qualified"
                    if attestation["evidence_level"] == "formal_candidate"
                    else "diagnostic_identity_only"
                ),
                "response_exact_safe": completion.text.strip() == "SAFE",
                "response_text_sha256": hashlib.sha256(
                    completion.text.encode("utf-8")
                ).hexdigest(),
                "response_text_bytes": len(
                    completion.text.encode("utf-8")
                ),
                "provider_attempts": completion.provider_attempts,
                "prompt_tokens": completion.prompt_tokens,
                "completion_tokens": completion.completion_tokens,
                "total_tokens": completion.total_tokens,
                "model_latency_ms": completion.model_latency_ms,
                "attestation": attestation,
                "receipt": receipt,
            }
        except Exception as exc:
            results[provider_id] = {
                "status": "failed_single_attempt_preserved",
                "error_type": type(exc).__name__,
                "provider_attempts": provider_attempts,
                "response_text_persisted": False,
            }
    qualified = sum(
        result["status"] == "formal_candidate_identity_qualified"
        for result in results.values()
    )
    return {
        "schema_version": QUALIFICATION_VERSION,
        "status": (
            "two_provider_live_identity_qualified"
            if qualified == 2
            else "live_identity_qualification_incomplete"
        ),
        "execution_boundary": {
            "fixed_synthetic_public_prompt_only": True,
            "provider_managed_tools": False,
            "external_effects": False,
            "temperature": 0.0,
            "max_tokens": 16,
            "automatic_retries": 0,
            "cross_provider_fallback": False,
        },
        "providers": results,
        "qualified_provider_count": qualified,
        "network_call_attempts": network_call_attempts,
        "network_call_attempts_per_provider": 1,
        "credentials_stored": False,
        "prompt_or_response_content_stored": False,
        "formal_results_created": 0,
        "result_eligible_for_effect_tables": False,
        "gemini_quota_snapshot": {
            "status": "active_project_limits_require_ai_studio_evidence",
            "rpm": None,
            "tpm": None,
            "rpd": None,
            "billing_tier": "user_declared_free",
            "charged_usd": 0.0,
        },
        "evidence_boundary": [
            "This artifact qualifies connectivity and exact returned model identity only.",
            "It is excluded from security and utility effect denominators.",
            "Gemini active RPM, TPM and RPD must be copied from the owning project's AI Studio rate-limit page.",
        ],
    }


def validate_artifact(
    artifact: Mapping[str, Any],
    *,
    policy_path: Path = DEFAULT_POLICY,
) -> dict[str, Any]:
    if artifact.get("schema_version") != QUALIFICATION_VERSION:
        raise ProviderLiveQualificationError(
            "unsupported live qualification schema"
        )
    if artifact.get("network_call_attempts") != 2:
        raise ProviderLiveQualificationError(
            "live qualification must record two call attempts"
        )
    boundary = artifact.get("execution_boundary")
    if (
        not isinstance(boundary, Mapping)
        or boundary.get("fixed_synthetic_public_prompt_only") is not True
        or boundary.get("provider_managed_tools") is not False
        or boundary.get("external_effects") is not False
        or boundary.get("automatic_retries") != 0
    ):
        raise ProviderLiveQualificationError(
            "live qualification safety boundary drift"
        )
    providers = artifact.get("providers")
    if not isinstance(providers, Mapping) or set(providers) != {
        "deepseek",
        "gemini",
    }:
        raise ProviderLiveQualificationError(
            "live qualification provider set drift"
        )
    policy = _load_policy(policy_path)
    qualified = 0
    for provider_id, result in providers.items():
        if not isinstance(result, Mapping):
            raise ProviderLiveQualificationError(
                f"{provider_id} live result must be an object"
            )
        if result.get("status") != "formal_candidate_identity_qualified":
            continue
        receipt = result.get("receipt")
        if not isinstance(receipt, Mapping):
            raise ProviderLiveQualificationError(
                f"{provider_id} receipt is missing"
            )
        validate_provider_receipt(receipt)
        attestation = provider_receipt_to_attestation(receipt)
        if (
            attestation.get("evidence_level") != "formal_candidate"
            or attestation.get("model_id")
            != policy[provider_id]["model_id"]
            or not attestation.get("request_id")
            or not attestation.get("response_id")
        ):
            raise ProviderLiveQualificationError(
                f"{provider_id} exact identity trace is incomplete"
            )
        if result.get("provider_attempts") != 1:
            raise ProviderLiveQualificationError(
                f"{provider_id} used more than one attempt"
            )
        qualified += 1
    if artifact.get("qualified_provider_count") != qualified:
        raise ProviderLiveQualificationError(
            "qualified provider count is inconsistent"
        )
    expected_status = (
        "two_provider_live_identity_qualified"
        if qualified == 2
        else "live_identity_qualification_incomplete"
    )
    if artifact.get("status") != expected_status:
        raise ProviderLiveQualificationError(
            "live qualification status is inconsistent"
        )
    return dict(artifact)


def write_live_qualification(
    values: Mapping[str, str],
    *,
    output: Path = DEFAULT_OUTPUT,
    client_factory: ClientFactory = _real_client_factory,
) -> dict[str, Any]:
    artifact = execute_live_qualification(
        values, client_factory=client_factory
    )
    validate_artifact(artifact)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            artifact,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return artifact


def verify_live_qualification(
    path: Path = DEFAULT_OUTPUT,
) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ProviderLiveQualificationError(
            "live qualification artifact must be an object"
        )
    return validate_artifact(value)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.execute == args.verify_only:
        raise ProviderLiveQualificationError(
            "choose exactly one of --execute or --verify-only"
        )
    output = (
        args.output
        if args.output.is_absolute()
        else PROJECT_ROOT / args.output
    )
    if args.verify_only:
        artifact = verify_live_qualification(output)
    else:
        config_path = resolve_config_path(args.config)
        values = parse_env_file(config_path)
        artifact = write_live_qualification(values, output=output)
    print(
        json.dumps(
            {
                "status": artifact["status"],
                "qualified_provider_count": artifact[
                    "qualified_provider_count"
                ],
                "network_call_attempts": (
                    0
                    if args.verify_only
                    else artifact["network_call_attempts"]
                ),
                "output": output.relative_to(PROJECT_ROOT).as_posix(),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    if args.verify_only:
        return 0
    return (
        0
        if artifact["status"] == "two_provider_live_identity_qualified"
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
