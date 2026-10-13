"""通过单次安全在线测试检验获批的 DeepSeek v2 请求追踪链。

验证追踪链在长会话中的标识一致性与时间戳准确性。
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.official_provider_executor import (
    OfficialProviderClient,
    ProviderBudgetState,
    validate_provider_receipt,
)
from experiments.paper_v2.provider_live_qualification import (
    CONSENT_VALUE,
    PROVIDER_CONFIG,
    SMOKE_MESSAGES,
    _load_policy,
)
from experiments.paper_v2.provider_request_trace_activation import (
    DEFAULT_OUTPUT as DEFAULT_ACTIVATION,
    activate_trace_attestation,
    verify_activation,
)
from experiments.paper_v2.provider_request_trace_candidate import (
    _load_trace_rows,
    append_completed_trace,
    append_started_trace,
    build_request_commitment,
    validate_trace_rows,
)
from m3_core.project_config import (
    is_placeholder,
    parse_env_file,
    resolve_config_path,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_ROOT = PROJECT_ROOT / "protocols/paper_upgrade_v2"
DEFAULT_OUTPUT = PROTOCOL_ROOT / "provider_live_qualification_v2.json"
DEFAULT_TRACE_LEDGER = (
    PROJECT_ROOT
    / "outputs/paper_upgrade_v2/provider_identity/"
    "deepseek_request_trace_v2.jsonl"
)
DEFAULT_POLICY = (
    PROTOCOL_ROOT / "dual_provider_budget_policy_v1.json"
)
SCHEMA_VERSION = "m3-paper-v2-provider-live-qualification-2.0"
EXECUTION_IDENTITY = "provider-live-qualification-v2-deepseek-20260724"
WORK_KEY = "deepseek-fixed-safe-identity"
ATTEMPT_ID = "deepseek-fixed-safe-attempt-1"
SAFE_SHA256 = hashlib.sha256(b"SAFE").hexdigest()
COMMON_ARTIFACT_FIELDS = frozenset(
    {
        "schema_version",
        "provider_id",
        "execution_identity",
        "work_key",
        "attempt_id",
        "execution_boundary",
        "trace_ledger",
        "network_call_attempts",
        "network_call_attempts_per_provider",
        "credentials_stored",
        "prompt_or_response_content_stored",
        "formal_results_created",
        "result_eligible_for_effect_tables",
        "formal_matrix_authorized",
        "identity_qualification_satisfied",
        "status",
        "response_exact_safe",
        "activated_trace_attestation",
        "provider_receipt",
    }
)
SUCCESS_ONLY_FIELDS = frozenset(
    {
        "response_text_sha256",
        "response_text_bytes",
        "provider_attempts",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "model_latency_ms",
    }
)
FAILURE_ONLY_FIELDS = frozenset({"error_type"})
RECOVERY_ONLY_FIELDS = frozenset(
    {
        "provider_receipt_sha256",
        "recovery_reason",
    }
)
ClientFactory = Callable[
    [str, Mapping[str, Any]], OfficialProviderClient
]


class ProviderLiveQualificationV2Error(ValueError):
    """当前瞻性 v2 身份论据不完整时抛出的异常。"""


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _display_path(path: Path) -> str:
    try:
        return path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _validate_deepseek_config(
    values: Mapping[str, str],
    policy: Mapping[str, Any],
) -> None:
    fields = PROVIDER_CONFIG["deepseek"]
    if values.get("M3_FRONTIER_API_CONSENT") != CONSENT_VALUE:
        raise ProviderLiveQualificationV2Error(
            "live qualification requires explicit local network consent"
        )
    if is_placeholder(values.get(fields["api_key"])):
        raise ProviderLiveQualificationV2Error(
            "DeepSeek API key is missing or a placeholder"
        )
    if values.get(fields["model_id"]) != policy["deepseek"]["model_id"]:
        raise ProviderLiveQualificationV2Error(
            "DeepSeek model differs from the frozen policy"
        )
    if str(values.get(fields["base_url"])).rstrip("/") != str(
        policy["deepseek"]["base_url"]
    ).rstrip("/"):
        raise ProviderLiveQualificationV2Error(
            "DeepSeek base URL differs from the frozen policy"
        )


def _real_client_factory(
    api_key: str,
    policy: Mapping[str, Any],
) -> OfficialProviderClient:
    return OfficialProviderClient(
        provider_id="deepseek",
        api_key=api_key,
        content_class="synthetic_m3_case",
        budget_state=ProviderBudgetState(
            provider_id="deepseek",
            policy=policy,
        ),
        policy=policy,
        temperature=0.0,
        max_tokens=16,
        timeout=60.0,
        network_consent=True,
    )


def _artifact_base(
    *,
    trace_ledger: Path,
    trace_status: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "provider_id": "deepseek",
        "execution_identity": EXECUTION_IDENTITY,
        "work_key": WORK_KEY,
        "attempt_id": ATTEMPT_ID,
        "execution_boundary": {
            "fixed_synthetic_public_prompt_only": True,
            "provider_managed_tools": False,
            "external_effects": False,
            "temperature": 0.0,
            "max_tokens": 16,
            "automatic_retries": 0,
            "cross_provider_fallback": False,
        },
        "trace_ledger": {
            "path": _display_path(trace_ledger),
            "sha256": _sha256_file(trace_ledger),
            "event_count": trace_status["event_count"],
            "completed_requests": trace_status["completed_requests"],
            "open_requests": trace_status["open_requests"],
            "tail_sha256": trace_status["tail_sha256"],
            "append_flush_fsync": True,
        },
        "network_call_attempts": 1,
        "network_call_attempts_per_provider": 1,
        "credentials_stored": False,
        "prompt_or_response_content_stored": False,
        "formal_results_created": 0,
        "result_eligible_for_effect_tables": False,
        "formal_matrix_authorized": False,
    }


def execute_live_qualification(
    values: Mapping[str, str],
    *,
    trace_ledger: Path = DEFAULT_TRACE_LEDGER,
    client_factory: ClientFactory = _real_client_factory,
    policy_path: Path = DEFAULT_POLICY,
    activation_path: Path = DEFAULT_ACTIVATION,
) -> dict[str, Any]:
    policy = _load_policy(policy_path)
    _validate_deepseek_config(values, policy)
    activation = verify_activation(activation_path)
    if activation["approval_scope"]["provider_ids"] != ["deepseek"]:
        raise ProviderLiveQualificationV2Error(
            "DeepSeek is not the sole approved provider scope"
        )
    if trace_ledger.exists():
        raise ProviderLiveQualificationV2Error(
            "trace ledger already exists; live qualification is single-use"
        )
    api_key = str(values[PROVIDER_CONFIG["deepseek"]["api_key"]])
    client = client_factory(api_key, policy)
    commitment = build_request_commitment(
        client,
        SMOKE_MESSAGES,
        execution_identity=EXECUTION_IDENTITY,
        work_key=WORK_KEY,
        call_index=1,
        attempt_id=ATTEMPT_ID,
        precommitted_at=_now(),
    )
    append_started_trace(trace_ledger, commitment)
    try:
        completion = client.complete(SMOKE_MESSAGES, step=1)
    except Exception as exc:
        trace_status = validate_trace_rows(_load_trace_rows(trace_ledger))
        return {
            **_artifact_base(
                trace_ledger=trace_ledger,
                trace_status=trace_status,
            ),
            "status": "failed_single_attempt_preserved",
            "identity_qualification_satisfied": False,
            "error_type": type(exc).__name__,
            "response_exact_safe": False,
            "activated_trace_attestation": None,
            "provider_receipt": None,
        }
    receipt = dict(completion.receipt)
    validate_provider_receipt(receipt)
    terminal = append_completed_trace(
        trace_ledger,
        client_request_id=commitment["client_request_id"],
        receipt=receipt,
    )
    activated = activate_trace_attestation(
        terminal["event"]["attestation"],
        activation_path=activation_path,
    )
    trace_status = validate_trace_rows(_load_trace_rows(trace_ledger))
    normalized_response = completion.text.strip()
    return {
        **_artifact_base(
            trace_ledger=trace_ledger,
            trace_status=trace_status,
        ),
        "status": "deepseek_live_v2_trace_qualified",
        "identity_qualification_satisfied": True,
        "response_exact_safe": normalized_response == "SAFE",
        "response_text_sha256": hashlib.sha256(
            normalized_response.encode("utf-8")
        ).hexdigest(),
        "response_text_bytes": len(normalized_response.encode("utf-8")),
        "provider_attempts": completion.provider_attempts,
        "prompt_tokens": completion.prompt_tokens,
        "completion_tokens": completion.completion_tokens,
        "total_tokens": completion.total_tokens,
        "model_latency_ms": completion.model_latency_ms,
        "activated_trace_attestation": activated,
        "provider_receipt": receipt,
    }


def recover_completed_trace(
    *,
    trace_ledger: Path = DEFAULT_TRACE_LEDGER,
    activation_path: Path = DEFAULT_ACTIVATION,
) -> dict[str, Any]:
    """在传输后本地写入失败后恢复身份论据。

    恢复仅使用已 fsync 的追踪。它绝不重建响应内容、用量或延迟，且绝不执行另一次请求。
    """

    rows = _load_trace_rows(trace_ledger)
    trace_status = validate_trace_rows(rows)
    if (
        trace_status["event_count"] != 2
        or trace_status["completed_requests"] != 1
        or trace_status["open_requests"] != 0
    ):
        raise ProviderLiveQualificationV2Error(
            "recovery requires exactly one completed durable trace"
        )
    terminal = rows[-1]["event"]
    activated = activate_trace_attestation(
        terminal["attestation"],
        activation_path=activation_path,
    )
    return {
        **_artifact_base(
            trace_ledger=trace_ledger,
            trace_status=trace_status,
        ),
        "status": "deepseek_live_v2_trace_qualified_recovered",
        "identity_qualification_satisfied": True,
        "response_exact_safe": None,
        "activated_trace_attestation": activated,
        "provider_receipt": None,
        "provider_receipt_sha256": terminal[
            "provider_receipt_sha256"
        ],
        "recovery_reason": (
            "post_transport_local_response_normalization_validator_rejected_"
            "before_qualification_artifact_write"
        ),
    }


def _resolve_ledger_path(artifact: Mapping[str, Any]) -> Path:
    value = artifact.get("trace_ledger")
    if not isinstance(value, Mapping):
        raise ProviderLiveQualificationV2Error(
            "trace ledger metadata is required"
        )
    raw = value.get("path")
    if not isinstance(raw, str) or not raw:
        raise ProviderLiveQualificationV2Error(
            "trace ledger path is required"
        )
    path = Path(raw)
    return path if path.is_absolute() else PROJECT_ROOT / path


def validate_artifact(
    artifact: Any,
    *,
    activation_path: Path = DEFAULT_ACTIVATION,
) -> dict[str, Any]:
    if not isinstance(artifact, Mapping):
        raise ProviderLiveQualificationV2Error(
            "live v2 qualification must be an object"
        )
    if artifact.get("schema_version") != SCHEMA_VERSION:
        raise ProviderLiveQualificationV2Error(
            "unsupported live v2 qualification schema"
        )
    status_value = artifact.get("status")
    if status_value == "failed_single_attempt_preserved":
        expected_fields = COMMON_ARTIFACT_FIELDS | FAILURE_ONLY_FIELDS
    elif status_value == "deepseek_live_v2_trace_qualified_recovered":
        expected_fields = COMMON_ARTIFACT_FIELDS | RECOVERY_ONLY_FIELDS
    else:
        expected_fields = COMMON_ARTIFACT_FIELDS | SUCCESS_ONLY_FIELDS
    if set(artifact) != expected_fields:
        raise ProviderLiveQualificationV2Error(
            "live v2 artifact fields drift"
        )
    if (
        artifact.get("provider_id") != "deepseek"
        or artifact.get("execution_identity") != EXECUTION_IDENTITY
        or artifact.get("work_key") != WORK_KEY
        or artifact.get("attempt_id") != ATTEMPT_ID
        or artifact.get("network_call_attempts") != 1
        or artifact.get("network_call_attempts_per_provider") != 1
    ):
        raise ProviderLiveQualificationV2Error(
            "live v2 execution identity drift"
        )
    boundary = artifact.get("execution_boundary")
    if (
        not isinstance(boundary, Mapping)
        or boundary.get("fixed_synthetic_public_prompt_only") is not True
        or boundary.get("provider_managed_tools") is not False
        or boundary.get("external_effects") is not False
        or boundary.get("automatic_retries") != 0
        or boundary.get("cross_provider_fallback") is not False
    ):
        raise ProviderLiveQualificationV2Error(
            "live v2 safety boundary drift"
        )
    if (
        artifact.get("credentials_stored") is not False
        or artifact.get("prompt_or_response_content_stored") is not False
        or artifact.get("formal_results_created") != 0
        or artifact.get("result_eligible_for_effect_tables") is not False
        or artifact.get("formal_matrix_authorized") is not False
    ):
        raise ProviderLiveQualificationV2Error(
            "live v2 evidence boundary drift"
        )
    ledger_path = _resolve_ledger_path(artifact)
    ledger_meta = artifact["trace_ledger"]
    if (
        not ledger_path.is_file()
        or ledger_meta.get("sha256") != _sha256_file(ledger_path)
        or ledger_meta.get("append_flush_fsync") is not True
    ):
        raise ProviderLiveQualificationV2Error(
            "live v2 trace ledger identity drift"
        )
    rows = _load_trace_rows(ledger_path)
    status = validate_trace_rows(rows)
    for field in (
        "event_count",
        "completed_requests",
        "open_requests",
        "tail_sha256",
    ):
        if ledger_meta.get(field) != status[field]:
            raise ProviderLiveQualificationV2Error(
                f"trace ledger {field} drift"
            )
    if artifact.get("status") == "failed_single_attempt_preserved":
        if (
            status["event_count"] != 1
            or status["completed_requests"] != 0
            or status["open_requests"] != 1
            or not isinstance(artifact.get("error_type"), str)
            or artifact.get("activated_trace_attestation") is not None
            or artifact.get("provider_receipt") is not None
            or artifact.get("identity_qualification_satisfied") is not False
        ):
            raise ProviderLiveQualificationV2Error(
                "failed v2 trace is not preserved transparently"
            )
        return dict(artifact)
    if artifact.get("status") == "deepseek_live_v2_trace_qualified_recovered":
        terminal = rows[-1]["event"]
        expected = activate_trace_attestation(
            terminal["attestation"],
            activation_path=activation_path,
        )
        if (
            status["event_count"] != 2
            or status["completed_requests"] != 1
            or status["open_requests"] != 0
            or artifact.get("identity_qualification_satisfied") is not True
            or artifact.get("response_exact_safe") is not None
            or artifact.get("provider_receipt") is not None
            or artifact.get("provider_receipt_sha256")
            != terminal.get("provider_receipt_sha256")
            or artifact.get("activated_trace_attestation") != expected
            or artifact.get("recovery_reason")
            != (
                "post_transport_local_response_normalization_validator_"
                "rejected_before_qualification_artifact_write"
            )
        ):
            raise ProviderLiveQualificationV2Error(
                "recovered v2 trace qualification is incomplete"
            )
        return dict(artifact)
    if artifact.get("status") != "deepseek_live_v2_trace_qualified":
        raise ProviderLiveQualificationV2Error(
            "unsupported live v2 qualification status"
        )
    if (
        status["event_count"] != 2
        or status["completed_requests"] != 1
        or status["open_requests"] != 0
        or artifact.get("response_exact_safe") is not True
        or artifact.get("response_text_sha256") != SAFE_SHA256
        or artifact.get("response_text_bytes") != 4
        or artifact.get("provider_attempts") != 1
        or artifact.get("identity_qualification_satisfied") is not True
    ):
        raise ProviderLiveQualificationV2Error(
            "successful v2 trace qualification is incomplete"
        )
    receipt = artifact.get("provider_receipt")
    if not isinstance(receipt, Mapping):
        raise ProviderLiveQualificationV2Error(
            "provider receipt is required"
        )
    validate_provider_receipt(receipt)
    terminal = rows[-1]["event"]
    if (
        terminal.get("provider_receipt_sha256")
        != sha256_canonical_json(receipt)
    ):
        raise ProviderLiveQualificationV2Error(
            "provider receipt digest drift"
        )
    expected = activate_trace_attestation(
        terminal["attestation"],
        activation_path=activation_path,
    )
    if artifact.get("activated_trace_attestation") != expected:
        raise ProviderLiveQualificationV2Error(
            "activated v2 attestation drift"
        )
    return dict(artifact)


def write_live_qualification(
    values: Mapping[str, str],
    *,
    output: Path = DEFAULT_OUTPUT,
    trace_ledger: Path = DEFAULT_TRACE_LEDGER,
    client_factory: ClientFactory = _real_client_factory,
) -> dict[str, Any]:
    artifact = execute_live_qualification(
        values,
        trace_ledger=trace_ledger,
        client_factory=client_factory,
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


def write_recovered_qualification(
    *,
    output: Path = DEFAULT_OUTPUT,
    trace_ledger: Path = DEFAULT_TRACE_LEDGER,
) -> dict[str, Any]:
    artifact = recover_completed_trace(trace_ledger=trace_ledger)
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
    return validate_artifact(value)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--trace-ledger",
        type=Path,
        default=DEFAULT_TRACE_LEDGER,
    )
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--recover-completed-trace", action="store_true")
    args = parser.parse_args()
    selected_modes = sum(
        bool(value)
        for value in (
            args.execute,
            args.verify_only,
            args.recover_completed_trace,
        )
    )
    if selected_modes != 1:
        raise ProviderLiveQualificationV2Error(
            "choose exactly one execution, recovery or verification mode"
        )
    output = (
        args.output
        if args.output.is_absolute()
        else PROJECT_ROOT / args.output
    )
    trace_ledger = (
        args.trace_ledger
        if args.trace_ledger.is_absolute()
        else PROJECT_ROOT / args.trace_ledger
    )
    if args.verify_only:
        artifact = verify_live_qualification(output)
    elif args.recover_completed_trace:
        artifact = write_recovered_qualification(
            output=output,
            trace_ledger=trace_ledger,
        )
    else:
        values = parse_env_file(resolve_config_path(args.config))
        artifact = write_live_qualification(
            values,
            output=output,
            trace_ledger=trace_ledger,
        )
    print(
        json.dumps(
            {
                "status": artifact["status"],
                "provider_id": "deepseek",
                "network_call_attempts": (
                    0
                    if args.verify_only or args.recover_completed_trace
                    else artifact["network_call_attempts"]
                ),
                "trace_ledger_sha256": artifact["trace_ledger"]["sha256"],
                "prompt_or_response_content_stored": False,
                "formal_matrix_authorized": False,
            },
            sort_keys=True,
        )
    )
    if args.verify_only or args.recover_completed_trace:
        return 0
    return (
        0
        if artifact["identity_qualification_satisfied"] is True
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
