"""Bridge VIGIL's official constraint generator to the frozen provider client.

The pinned VIGIL parser and generator remain unchanged.  Only its OpenAI client
construction is dependency-injected so the same single-attempt provider,
identity, budget and receipt controls used by M3 also govern the baseline.
Silent VIGIL default-constraint fallback is rejected.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping

from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.official_provider_executor import (
    HTTPResponseEnvelope,
    OfficialProviderClient,
    OfficialProviderCompletion,
    ProviderBudgetState,
    provider_receipt_to_attestation,
)
from experiments.paper_v2.structural_baselines import (
    VIGIL_COMMIT,
    VIGIL_ROOT,
    VigilRuntimeAdapter,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/vigil_live_dependency_qualification_v1.json"
)
DEFAULT_BUDGET_POLICY = (
    PROJECT_ROOT / "protocols/paper_upgrade_v2/dual_provider_budget_policy_v1.json"
)
QUALIFICATION_RECORDED_AT = "2026-07-24T04:00:00+08:00"
DEPENDENCY_VERSION = "m3-paper-v2-vigil-official-provider-bridge-1.0"
_GENERATOR_LOCK = threading.RLock()


class VigilLiveDependencyError(ValueError):
    """Raised when the provider bridge or official generator falls back."""


@dataclass(frozen=True)
class VigilPreparation:
    adapter: VigilRuntimeAdapter
    completions: tuple[OfficialProviderCompletion, ...]
    constraint_count: int
    constraint_set_sha256: str

    @property
    def provider_calls_consumed(self) -> int:
        return len(self.completions)


class _OfficialProviderOpenAIFacade:
    """Expose only the OpenAI call shape used by ConstraintGenerator."""

    def __init__(self, client: OfficialProviderClient) -> None:
        self._client = client
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create)
        )
        self.completions: list[OfficialProviderCompletion] = []

    def _create(self, **kwargs: Any) -> Any:
        allowed = {
            "model",
            "messages",
            "temperature",
            "response_format",
        }
        if set(kwargs) != allowed:
            raise VigilLiveDependencyError(
                "VIGIL used an unexpected provider parameter set"
            )
        if kwargs["model"] != self._client.model:
            raise VigilLiveDependencyError(
                "VIGIL generator model differs from the frozen provider model"
            )
        if float(kwargs["temperature"]) != 0.0:
            raise VigilLiveDependencyError(
                "VIGIL constraint temperature must be zero"
            )
        if kwargs["response_format"] != {"type": "json_object"}:
            raise VigilLiveDependencyError(
                "VIGIL constraint output must request a JSON object"
            )
        messages = kwargs["messages"]
        if not isinstance(messages, list) or not all(
            isinstance(message, Mapping) for message in messages
        ):
            raise VigilLiveDependencyError(
                "VIGIL generator messages are malformed"
            )
        normalized = [
            {
                "role": str(message.get("role", "")),
                "content": str(message.get("content", "")),
            }
            for message in messages
        ]
        completion = self._client.complete(
            normalized,
            step=len(self.completions) + 1,
        )
        self.completions.append(completion)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=completion.text)
                )
            ]
        )


def _vigil_modules() -> tuple[Any, Any]:
    source = str(VIGIL_ROOT.resolve())
    if source not in sys.path:
        sys.path.insert(0, source)
    return (
        importlib.import_module("vigil.client_utils"),
        importlib.import_module("vigil.constraint_generator"),
    )


class VigilOfficialConstraintFactory:
    """Prepare a source-pinned VIGIL auditor using one controlled model call."""

    provider_calls_consumed = 1

    def __call__(
        self,
        context: Any,
        trusted_user_request: str,
        client: OfficialProviderClient,
    ) -> VigilPreparation:
        del context
        adapter = VigilRuntimeAdapter(
            allow_provider_calls=False,
            constraint_generator_model=client.model,
        )
        facade = _OfficialProviderOpenAIFacade(client)
        client_utils, generator_module = _vigil_modules()
        original = client_utils.create_openai_client_for_model
        with _GENERATOR_LOCK:
            try:
                client_utils.create_openai_client_for_model = (
                    lambda model_name: (
                        facade
                        if model_name == client.model
                        else (_raise_model_drift(model_name))
                    )
                )
                generator = generator_module.ConstraintGenerator(
                    adapter.config
                )
                constraint_set = generator.generate_constraints(
                    trusted_user_request
                )
            finally:
                client_utils.create_openai_client_for_model = original
        metadata = constraint_set.metadata
        if (
            not isinstance(metadata, Mapping)
            or metadata.get("model") != client.model
            or not isinstance(metadata.get("raw_response"), Mapping)
        ):
            raise VigilLiveDependencyError(
                "VIGIL silently fell back instead of returning model-backed constraints"
            )
        if len(facade.completions) != 1:
            raise VigilLiveDependencyError(
                "VIGIL constraint generation must consume exactly one provider call"
            )
        adapter.prepare_from_official_constraint_set(constraint_set)
        constraint_payload = {
            "user_query_sha256": sha256_canonical_json(
                {"trusted_user_request": trusted_user_request}
            ),
            "constraints": [
                constraint.model_dump(mode="json")
                for constraint in constraint_set.constraints
            ],
            "global_rules": constraint_set.global_rules,
            "model": metadata["model"],
        }
        return VigilPreparation(
            adapter=adapter,
            completions=tuple(facade.completions),
            constraint_count=len(constraint_set.constraints),
            constraint_set_sha256=sha256_canonical_json(
                constraint_payload
            ),
        )


def _raise_model_drift(model_name: str) -> Any:
    raise VigilLiveDependencyError(
        f"VIGIL requested an unfrozen generator model: {model_name}"
    )


def _fixture_response(
    model: str, constraint_json: str
) -> HTTPResponseEnvelope:
    return HTTPResponseEnvelope(
        status_code=200,
        headers={"x-request-id": "vigil-qualification-request"},
        body={
            "id": "vigil-qualification-response",
            "model": model,
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": constraint_json,
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 300,
                "completion_tokens": 120,
                "total_tokens": 420,
                "prompt_cache_hit_tokens": 270,
                "prompt_cache_miss_tokens": 30,
            },
        },
    )


def build_qualification() -> dict[str, Any]:
    policy = json.loads(DEFAULT_BUDGET_POLICY.read_text(encoding="utf-8"))
    calls: list[int] = []
    response = json.dumps(
        {
            "constraints": [
                {
                    "constraint_id": "confirm_send",
                    "constraint_type": "require_confirmation",
                    "description": "Confirm sending the report.",
                    "tool_name": "send_report",
                    "priority": 1,
                },
                {
                    "constraint_id": "forbid_delete",
                    "constraint_type": "forbid",
                    "description": "Forbid deleting records.",
                    "tool_name": "delete_record",
                    "priority": 1,
                },
            ],
            "global_rules": ["Keep read-only inspection available."],
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )

    def transport(endpoint, headers, payload, timeout):
        del endpoint, headers, timeout
        calls.append(1)
        return _fixture_response(str(payload["model"]), response)

    client = OfficialProviderClient(
        provider_id="deepseek",
        api_key="fixture-key-for-vigil-live-dependency",
        content_class="public_benchmark_case",
        budget_state=ProviderBudgetState(
            provider_id="deepseek", policy=policy
        ),
        policy=policy,
        transport=transport,
    )
    preparation = VigilOfficialConstraintFactory()(
        None,
        "Send the report only after confirmation.",
        client,
    )
    decisions = {
        tool: preparation.adapter.decide(
            tool_name=tool,
            arguments={},
            tool_call_id=f"qualification-{tool}",
        ).decision
        for tool in ("read_report", "send_report", "delete_record")
    }
    if decisions != {
        "read_report": "ALLOW",
        "send_report": "ASK",
        "delete_record": "DENY",
    }:
        raise VigilLiveDependencyError(
            "source-backed VIGIL decision qualification failed"
        )
    completion = preparation.completions[0]
    attestation = provider_receipt_to_attestation(completion.receipt)
    if (
        calls != [1]
        or preparation.provider_calls_consumed != 1
        or attestation["evidence_level"] != "local_qualification"
    ):
        raise VigilLiveDependencyError(
            "VIGIL provider-call qualification drift"
        )
    return {
        "schema_version": "m3-paper-v2-vigil-live-dependency-qualification-1.0",
        "dependency_version": DEPENDENCY_VERSION,
        "status": "source_pinned_vigil_provider_bridge_qualified",
        "qualified_at": QUALIFICATION_RECORDED_AT,
        "source_lock": {
            "checkout": VIGIL_ROOT.relative_to(PROJECT_ROOT).as_posix(),
            "commit": VIGIL_COMMIT,
            "constraint_generator_sha256": _sha256_file(
                VIGIL_ROOT / "vigil/constraint_generator.py"
            ),
            "runtime_auditor_sha256": _sha256_file(
                VIGIL_ROOT / "vigil/runtime_auditor.py"
            ),
        },
        "provider_bridge": {
            "official_provider_client": True,
            "single_attempt": True,
            "provider_managed_tools": False,
            "temperature": 0.0,
            "response_format": "json_object",
            "provider_calls_consumed": preparation.provider_calls_consumed,
            "automatic_retries": 0,
            "silent_default_fallback_accepted": False,
        },
        "constraint_generation": {
            "constraint_count": preparation.constraint_count,
            "constraint_set_sha256": preparation.constraint_set_sha256,
            "raw_response_persisted": False,
            "trusted_query_persisted": False,
        },
        "runtime_decisions": decisions,
        "fixture_attestation": {
            "endpoint_type": attestation["endpoint_type"],
            "model_id": attestation["model_id"],
            "evidence_level": attestation["evidence_level"],
            "identity_verified": attestation["identity_verified"],
            "request_id": attestation["request_id"],
            "response_id": attestation["response_id"],
        },
        "network_calls_made": 0,
        "api_calls_made": 0,
        "model_calls_made": 0,
        "credentials_read": False,
        "experiment_records_persisted": 0,
        "formal_results_created": 0,
        "evidence_boundary": [
            "This qualifies VIGIL's official generator and RuntimeAuditor through an injected provider transport.",
            "A live official exact-model request/response-ID trace remains required before formal execution.",
        ],
    }


def _sha256_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


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
        raise VigilLiveDependencyError(
            "VIGIL live-dependency qualification does not reproduce"
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
                "provider_calls_consumed": artifact["provider_bridge"][
                    "provider_calls_consumed"
                ],
                "network_calls_made": artifact["network_calls_made"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
