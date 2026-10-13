"""面向 paper-v2 实验的故障安全提供商与工具效应边界隔离机制。

工具效应仅限合成沙箱或 AgentDojo 内存副本；允许隔离沙箱内的临时文件写入，
禁止真实外部连接、真实发信及沙箱外文件写入。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

from experiments.paper_v2.contracts import sha256_canonical_json


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY = (
    PROJECT_ROOT / "protocols/paper_upgrade_v2/provider_safety_policy_v1.json"
)
SAFE_BACKENDS = frozenset(
    {"no_effect", "m3_sandbox_fixture", "agentdojo_in_memory_copy"}
)
HOST_EXECUTION_TOOLS = frozenset(
    {
        "bash",
        "cmd",
        "computer",
        "computer_use",
        "exec",
        "powershell",
        "run_code",
        "shell",
        "terminal",
    }
)


class ProviderSafetyError(ValueError):
    """当提供商流量或建议的副作用越过边界时抛出的异常。"""


def load_safety_policy(path: Path = DEFAULT_POLICY) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ProviderSafetyError("provider safety policy must be an object")
    if value.get("schema_version") != (
        "m3-paper-v2-provider-safety-policy-1.0"
    ):
        raise ProviderSafetyError("unsupported provider safety policy")
    enforcement = value.get("enforcement")
    if not isinstance(enforcement, Mapping):
        raise ProviderSafetyError("provider safety enforcement is missing")
    required_true = (
        "model_output_is_untrusted_proposal",
        "all_effects_require_local_boundary_validation",
    )
    if any(enforcement.get(key) is not True for key in required_true):
        raise ProviderSafetyError("provider safety policy weakens required controls")
    if enforcement.get("external_connectors_enabled") is not False:
        raise ProviderSafetyError("external connectors must be disabled")
    if enforcement.get("provider_managed_tools_enabled") is not False:
        raise ProviderSafetyError("provider-managed tools must be disabled")
    if enforcement.get("unsafe_or_unknown_effect") != "DENY":
        raise ProviderSafetyError("unknown effects must fail closed")
    return value


def validate_provider_endpoint(
    provider_id: str,
    endpoint_url: str,
    *,
    policy: Mapping[str, Any] | None = None,
) -> None:
    """仅允许固化的官方推理端点。"""

    active = dict(policy or load_safety_policy())
    providers = active.get("official_provider_endpoints")
    if not isinstance(providers, Mapping):
        raise ProviderSafetyError("official provider endpoint map is missing")
    provider = providers.get(str(provider_id).casefold())
    if not isinstance(provider, Mapping):
        raise ProviderSafetyError("provider is not admitted by the safety policy")
    parsed = urlparse(str(endpoint_url))
    origin = f"{parsed.scheme}://{parsed.netloc}"
    if origin != provider.get("origin"):
        raise ProviderSafetyError("provider endpoint is not the frozen official origin")
    allowed_paths = provider.get("allowed_paths")
    if not isinstance(allowed_paths, list) or parsed.path not in allowed_paths:
        raise ProviderSafetyError("provider endpoint path is not inference-only")
    if parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise ProviderSafetyError("provider endpoint must not contain extra authority data")


def _sandbox_path(value: Any) -> bool:
    normalized = str(value).strip().replace("\\", "/").casefold()
    return normalized == "sandbox/public" or normalized.startswith(
        "sandbox/public/"
    )


def _example_recipient(value: Any) -> bool:
    recipient = str(value).strip().casefold()
    return recipient.endswith("@example.test")


def _mock_endpoint(value: Any) -> bool:
    return str(value).strip().startswith("/mock/")


def validate_tool_effect(
    *,
    effect_backend: str,
    tool: str,
    arguments: Mapping[str, Any],
    external_connectors_enabled: bool = False,
) -> None:
    """在施加任何模拟副作用之前验证单个本地提案。"""

    load_safety_policy()
    backend = str(effect_backend)
    tool_name = str(tool).strip()
    lowered = tool_name.casefold()
    if backend not in SAFE_BACKENDS:
        raise ProviderSafetyError("effect backend is not isolated")
    if external_connectors_enabled:
        raise ProviderSafetyError("external connectors must remain disabled")
    if lowered in HOST_EXECUTION_TOOLS:
        raise ProviderSafetyError("host or provider code execution is forbidden")
    if backend == "no_effect":
        if lowered != "final":
            raise ProviderSafetyError("text-only backend cannot apply a tool effect")
        return
    if backend == "agentdojo_in_memory_copy":
        # AgentDojo tools mutate a copied Pydantic environment. The executor
        # must not supply a network-capable runtime or an external connector.
        return
    if lowered == "final":
        return
    if lowered in {"read_file", "write_file"}:
        path = arguments.get("path", arguments.get("file_path"))
        if path is None or not _sandbox_path(path):
            raise ProviderSafetyError("fixture file path escapes sandbox/public")
        return
    if lowered == "send_email":
        if not _example_recipient(arguments.get("to")):
            raise ProviderSafetyError("fixture email must target example.test")
        return
    if lowered == "call_api":
        if not _mock_endpoint(arguments.get("endpoint")):
            raise ProviderSafetyError("fixture API call must target /mock/")
        return
    raise ProviderSafetyError("unknown M3 fixture tool is denied")


def build_safety_receipt(
    *,
    provider_id: str,
    endpoint_url: str,
    effect_backend: str,
    tool: str,
    arguments: Mapping[str, Any],
) -> dict[str, Any]:
    """在两个边界均通过后返回无凭据的收据。"""

    validate_provider_endpoint(provider_id, endpoint_url)
    validate_tool_effect(
        effect_backend=effect_backend,
        tool=tool,
        arguments=arguments,
        external_connectors_enabled=False,
    )
    evidence = {
        "provider_id": str(provider_id).casefold(),
        "endpoint_origin_and_path": (
            f"{urlparse(endpoint_url).scheme}://"
            f"{urlparse(endpoint_url).netloc}{urlparse(endpoint_url).path}"
        ),
        "effect_backend": effect_backend,
        "tool": tool,
        "arguments_sha256": sha256_canonical_json(dict(arguments)),
        "external_connectors_enabled": False,
        "provider_managed_tools_enabled": False,
        "decision": "ALLOW_ISOLATED_SIMULATION_ONLY",
    }
    return {
        "schema_version": "m3-paper-v2-provider-safety-receipt-1.0",
        "credentials_stored": False,
        "evidence": evidence,
        "evidence_sha256": sha256_canonical_json(evidence),
    }


def validate_safety_receipt(receipt: Mapping[str, Any]) -> None:
    if set(receipt) != {
        "schema_version",
        "credentials_stored",
        "evidence",
        "evidence_sha256",
    }:
        raise ProviderSafetyError("provider safety receipt fields drift")
    if receipt.get("schema_version") != (
        "m3-paper-v2-provider-safety-receipt-1.0"
    ):
        raise ProviderSafetyError("unsupported provider safety receipt")
    if receipt.get("credentials_stored") is not False:
        raise ProviderSafetyError("safety receipt must not store credentials")
    evidence = receipt.get("evidence")
    if not isinstance(evidence, Mapping):
        raise ProviderSafetyError("safety receipt evidence is missing")
    if set(evidence) != {
        "provider_id",
        "endpoint_origin_and_path",
        "effect_backend",
        "tool",
        "arguments_sha256",
        "external_connectors_enabled",
        "provider_managed_tools_enabled",
        "decision",
    }:
        raise ProviderSafetyError("provider safety evidence fields drift")
    if receipt.get("evidence_sha256") != sha256_canonical_json(evidence):
        raise ProviderSafetyError("safety receipt hash mismatch")
    provider_id = str(evidence.get("provider_id", "")).casefold()
    endpoint = str(evidence.get("endpoint_origin_and_path", ""))
    validate_provider_endpoint(provider_id, endpoint)
    if (
        evidence.get("effect_backend") not in SAFE_BACKENDS
        or str(evidence.get("tool", "")).casefold() in HOST_EXECUTION_TOOLS
        or not isinstance(evidence.get("arguments_sha256"), str)
        or len(str(evidence["arguments_sha256"])) != 64
        or evidence.get("external_connectors_enabled") is not False
        or evidence.get("provider_managed_tools_enabled") is not False
        or evidence.get("decision") != "ALLOW_ISOLATED_SIMULATION_ONLY"
    ):
        raise ProviderSafetyError(
            "provider safety receipt weakens the isolated-effect boundary"
        )
