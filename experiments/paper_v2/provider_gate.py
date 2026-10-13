"""验证 paper-v2 提供商决策并估算保守的成本上限。

基于静态用例特征提前预估整个矩阵的最大调用规模与耗时。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DECISION = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/provider_cost_decision_candidate_v1.json"
)
DEFAULT_CASE_INDEX = (
    PROJECT_ROOT / "protocols/paper_upgrade_v2/medium_case_index_v1.jsonl"
)
DEFAULT_CASE_MANIFEST = (
    PROJECT_ROOT / "protocols/paper_upgrade_v2/medium_case_manifest_v1.json"
)
DEFAULT_OUTPUT = (
    PROJECT_ROOT / "protocols/paper_upgrade_v2/provider_cost_preflight_v1.json"
)

ALLOWED_ENDPOINT_TYPES = {"official_api", "auditable_gateway"}
REQUIRED_PROMPT_REWRITE_DECLARATION = "none_declared"
SECRET_KEY_PATTERN = re.compile(
    r"(?:api[_-]?key|access[_-]?token|secret|password|credential)",
    re.IGNORECASE,
)
SECRET_VALUE_PATTERN = re.compile(
    r"^(?:sk-[A-Za-z0-9_-]{12,}|Bearer\s+\S+|[A-Za-z0-9+/]{40,}={0,2})$",
    re.IGNORECASE,
)
PLACEHOLDER_PATTERN = re.compile(r"^<[^>]+>$")


class ProviderGateError(ValueError):
    """当提供商/成本决策畸形或不安全时抛出的异常。"""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _display_path(path: Path) -> str:
    try:
        return path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ProviderGateError(f"{path}: expected a JSON object")
    return value


def _walk(value: Any, path: str = "$") -> list[tuple[str, Any]]:
    values = [(path, value)]
    if isinstance(value, dict):
        for key, child in value.items():
            values.extend(_walk(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            values.extend(_walk(child, f"{path}[{index}]"))
    return values


def _reject_secrets_and_placeholders(decision: dict[str, Any]) -> None:
    for path, value in _walk(decision):
        key = path.rsplit(".", maxsplit=1)[-1]
        if SECRET_KEY_PATTERN.search(key) and key != "credentials_stored":
            raise ProviderGateError(
                f"{path}: credential-like fields are forbidden in provider decisions"
            )
        if isinstance(value, str):
            if SECRET_VALUE_PATTERN.fullmatch(value.strip()):
                raise ProviderGateError(
                    f"{path}: credential-like values are forbidden in provider decisions"
                )
            if PLACEHOLDER_PATTERN.fullmatch(value.strip()):
                raise ProviderGateError(f"{path}: unresolved placeholder")


def _required_mapping(
    parent: dict[str, Any], key: str, *, path: str
) -> dict[str, Any]:
    value = parent.get(key)
    if not isinstance(value, dict):
        raise ProviderGateError(f"{path}.{key}: expected an object")
    return value


def _required_nonempty_string(
    parent: dict[str, Any], key: str, *, path: str
) -> str:
    value = parent.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ProviderGateError(f"{path}.{key}: expected a non-empty string")
    return value.strip()


def _required_number(
    parent: dict[str, Any],
    key: str,
    *,
    path: str,
    minimum: float = 0.0,
    integer: bool = False,
) -> float:
    value = parent.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProviderGateError(f"{path}.{key}: expected a number")
    number = float(value)
    if not math.isfinite(number) or number < minimum:
        raise ProviderGateError(f"{path}.{key}: must be >= {minimum}")
    if integer and not number.is_integer():
        raise ProviderGateError(f"{path}.{key}: expected an integer")
    return number


def validate_decision(decision: dict[str, Any]) -> dict[str, Any]:
    """验证提供商决策中离线安全的部分。"""

    _reject_secrets_and_placeholders(decision)
    if decision.get("schema_version") != "m3-paper-v2-provider-cost-decision-2.0":
        raise ProviderGateError("unsupported provider decision schema")

    attestation = _required_mapping(
        decision, "provider_attestation", path="$"
    )
    endpoint_type = _required_nonempty_string(
        attestation, "endpoint_type", path="$.provider_attestation"
    )
    if endpoint_type not in ALLOWED_ENDPOINT_TYPES:
        raise ProviderGateError(
            "$.provider_attestation.endpoint_type: unsupported endpoint type"
        )
    for key in (
        "provider_name",
        "upstream_provider",
        "model_id",
        "identity_evidence",
        "pricing_source_url",
        "pricing_verified_at",
    ):
        _required_nonempty_string(attestation, key, path="$.provider_attestation")
    if (
        attestation.get("prompt_rewrite_declaration")
        != REQUIRED_PROMPT_REWRITE_DECLARATION
    ):
        raise ProviderGateError(
            "$.provider_attestation.prompt_rewrite_declaration must be none_declared"
        )
    for key in (
        "identity_verified",
        "request_id_available",
        "response_id_available",
    ):
        if not isinstance(attestation.get(key), bool):
            raise ProviderGateError(
                f"$.provider_attestation.{key}: expected a boolean"
            )

    request = _required_mapping(decision, "request_parameters", path="$")
    if _required_number(
        request, "temperature", path="$.request_parameters"
    ) != 0:
        raise ProviderGateError("$.request_parameters.temperature must be zero")
    _required_number(
        request,
        "max_output_tokens",
        path="$.request_parameters",
        minimum=1,
        integer=True,
    )
    _required_number(
        request,
        "max_agent_steps",
        path="$.request_parameters",
        minimum=1,
        integer=True,
    )
    _required_number(
        request,
        "fixed_input_token_allowance_per_call",
        path="$.request_parameters",
        minimum=0,
        integer=True,
    )
    _required_nonempty_string(
        request, "seed_support", path="$.request_parameters"
    )

    call_budgets = _required_mapping(
        request, "max_calls_per_condition", path="$.request_parameters"
    )
    required_conditions = {
        "no_defense",
        "safe_prompt_or_spotlighting",
        "promptguard_detector_only",
        "strongest_peer_reviewed_structural_baseline",
        "m3_policy_only",
        "m3_full",
    }
    if set(call_budgets) != required_conditions:
        raise ProviderGateError(
            "$.request_parameters.max_calls_per_condition must exactly match "
            f"{sorted(required_conditions)}"
        )
    for condition in required_conditions:
        _required_number(
            call_budgets,
            condition,
            path="$.request_parameters.max_calls_per_condition",
            minimum=1,
            integer=True,
        )

    cost = _required_mapping(decision, "cost", path="$")
    if cost.get("currency") != "USD":
        raise ProviderGateError("$.cost.currency must be USD")
    _required_number(
        cost, "input_price_per_million_tokens", path="$.cost", minimum=0
    )
    _required_number(
        cost, "output_price_per_million_tokens", path="$.cost", minimum=0
    )
    hard_limit = cost.get("hard_spend_limit_usd")
    if hard_limit is not None:
        _required_number(
            cost, "hard_spend_limit_usd", path="$.cost", minimum=0.01
        )
    abort_fraction = _required_number(
        cost, "abort_at_fraction", path="$.cost", minimum=0.01
    )
    if abort_fraction > 0.9:
        raise ProviderGateError("$.cost.abort_at_fraction must be <= 0.9")

    logging = _required_mapping(decision, "logging", path="$")
    required_true = (
        "prompts_stored",
        "responses_stored",
        "request_and_response_ids_stored",
    )
    for key in required_true:
        if logging.get(key) is not True:
            raise ProviderGateError(f"$.logging.{key} must be true")
    if logging.get("credentials_stored") is not False:
        raise ProviderGateError("$.logging.credentials_stored must be false")
    if not isinstance(logging.get("redaction_reviewed"), bool):
        raise ProviderGateError("$.logging.redaction_reviewed must be boolean")
    if not isinstance(decision.get("approved_by_user"), bool):
        raise ProviderGateError("$.approved_by_user must be boolean")
    return decision


def _read_index(path: Path) -> list[dict[str, Any]]:
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(rows) != 72 or len({row["case_id"] for row in rows}) != 72:
        raise ProviderGateError("medium index must contain 72 unique cases")
    return rows


def _source_line_size(row: dict[str, Any]) -> int:
    source_path = PROJECT_ROOT / row["source_path"]
    lines = source_path.read_bytes().splitlines()
    line_number = row["source_line"]
    if (
        isinstance(line_number, bool)
        or not isinstance(line_number, int)
        or line_number < 1
        or line_number > len(lines)
    ):
        raise ProviderGateError(
            f"{row['case_id']}: invalid source line {line_number}"
        )
    return len(lines[line_number - 1])


def estimate_cost(
    decision: dict[str, Any],
    *,
    index_path: Path = DEFAULT_CASE_INDEX,
    manifest_path: Path = DEFAULT_CASE_MANIFEST,
) -> dict[str, Any]:
    """为 480 条记录返回字节保守的 Token 和调用上限。"""

    validate_decision(decision)
    rows = _read_index(index_path)
    manifest = _load_json(manifest_path)
    if manifest.get("index_sha256") != _sha256_file(index_path):
        raise ProviderGateError("medium index does not match its frozen manifest")
    conditions = manifest.get("core_conditions")
    request = decision["request_parameters"]
    call_budgets = request["max_calls_per_condition"]
    fixed_allowance = int(request["fixed_input_token_allowance_per_call"])
    max_output_tokens = int(request["max_output_tokens"])

    source_sizes = {row["case_id"]: _source_line_size(row) for row in rows}
    call_count_by_condition: Counter[str] = Counter()
    input_tokens = 0
    output_tokens = 0
    work_items = 0

    for row in rows:
        per_call_input = source_sizes[row["case_id"]] + fixed_allowance
        for condition in conditions:
            calls = int(call_budgets[condition])
            call_count_by_condition[condition] += calls
            input_tokens += per_call_input * calls
            output_tokens += max_output_tokens * calls
            work_items += 1
        probe = row.get("regime_probe")
        if probe is not None:
            for condition in probe["condition_ids"]:
                calls = int(call_budgets[condition])
                call_count_by_condition[f"probe:{condition}"] += calls
                input_tokens += per_call_input * calls
                output_tokens += max_output_tokens * calls
                work_items += 1

    if work_items != 480:
        raise ProviderGateError(f"expected 480 work items, got {work_items}")
    call_count = sum(call_count_by_condition.values())
    cost = decision["cost"]
    input_cost = (
        input_tokens * float(cost["input_price_per_million_tokens"]) / 1_000_000
    )
    output_cost = (
        output_tokens
        * float(cost["output_price_per_million_tokens"])
        / 1_000_000
    )
    return {
        "estimation_method": (
            "utf8_source_bytes_plus_fixed_allowance_as_token_upper_bound"
        ),
        "conservative_assumptions": [
            "Each UTF-8 source byte is counted as at most one input token.",
            "Every work item consumes its condition-specific maximum call count.",
            "Every provider call consumes max_output_tokens.",
            "Cached-input and batch discounts are ignored.",
        ],
        "work_items": work_items,
        "case_count": len(rows),
        "provider_calls_upper_bound": call_count,
        "calls_by_condition": dict(sorted(call_count_by_condition.items())),
        "input_tokens_upper_bound": input_tokens,
        "output_tokens_upper_bound": output_tokens,
        "input_cost_upper_bound_usd": round(input_cost, 6),
        "output_cost_upper_bound_usd": round(output_cost, 6),
        "total_cost_upper_bound_usd": round(input_cost + output_cost, 6),
        "source_record_bytes": {
            "minimum": min(source_sizes.values()),
            "median": sorted(source_sizes.values())[len(source_sizes) // 2],
            "maximum": max(source_sizes.values()),
            "total_unique_cases": sum(source_sizes.values()),
        },
    }


def build_preflight(
    decision_path: Path = DEFAULT_DECISION,
    *,
    index_path: Path = DEFAULT_CASE_INDEX,
    manifest_path: Path = DEFAULT_CASE_MANIFEST,
) -> dict[str, Any]:
    decision = validate_decision(_load_json(decision_path))
    estimate = estimate_cost(
        decision,
        index_path=index_path,
        manifest_path=manifest_path,
    )
    attestation = decision["provider_attestation"]
    cost = decision["cost"]
    blockers: list[str] = []
    if not attestation["identity_verified"]:
        blockers.append(
            "A real smoke response has not yet attested the exact upstream model."
        )
    if not attestation["request_id_available"]:
        blockers.append("Request-ID availability has not been attested.")
    if not attestation["response_id_available"]:
        blockers.append("Response-ID availability has not been attested.")
    if not decision["logging"]["redaction_reviewed"]:
        blockers.append("The formal logging redaction review is pending.")
    if not decision["approved_by_user"]:
        blockers.append("The user has not approved this provider/cost decision.")
    hard_limit = cost["hard_spend_limit_usd"]
    if hard_limit is None:
        blockers.append("No hard USD spend limit has been approved.")
    elif (
        estimate["total_cost_upper_bound_usd"]
        > float(hard_limit) * float(cost["abort_at_fraction"])
    ):
        blockers.append(
            "The conservative cost upper bound exceeds the configured abort ceiling."
        )

    gate_pass = not blockers
    if gate_pass:
        status = "pass"
    elif blockers == [
        "The user has not approved this provider/cost decision.",
        "No hard USD spend limit has been approved.",
    ]:
        status = "ready_for_user_approval"
    else:
        status = "blocked_runtime_attestation_and_user_approval"
    return {
        "schema_version": "m3-paper-v2-provider-cost-preflight-1.0",
        "status": status,
        "generated_at": "2026-07-23T20:00:00+08:00",
        "network_calls_made": 0,
        "credentials_read": False,
        "decision_path": _display_path(decision_path),
        "decision_sha256": _sha256_file(decision_path),
        "medium_case_index": {
            "path": _display_path(index_path),
            "sha256": _sha256_file(index_path),
        },
        "medium_case_manifest": {
            "path": _display_path(manifest_path),
            "sha256": _sha256_file(manifest_path),
        },
        "provider_attestation": attestation,
        "cost_estimate": estimate,
        "hard_spend_limit_usd": hard_limit,
        "abort_at_fraction": cost["abort_at_fraction"],
        "blockers": blockers,
        "gate_pass": gate_pass,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decision", type=Path, default=DEFAULT_DECISION)
    parser.add_argument("--index", type=Path, default=DEFAULT_CASE_INDEX)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_CASE_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    def resolve(path: Path) -> Path:
        return path if path.is_absolute() else PROJECT_ROOT / path

    preflight = build_preflight(
        resolve(args.decision),
        index_path=resolve(args.index),
        manifest_path=resolve(args.manifest),
    )
    output = resolve(args.output)
    if args.verify_only:
        observed = _load_json(output)
        if observed != preflight:
            raise ProviderGateError("frozen provider preflight does not reproduce")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(preflight, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
    print(json.dumps(preflight, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
