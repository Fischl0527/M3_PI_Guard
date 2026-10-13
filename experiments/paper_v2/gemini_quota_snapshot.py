"""创建并验证无内容泄露的 Gemini AI Studio 配额快照。

捕获当前 API Key 的层级、RPM/RPD 上限与历史用量统计。
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from experiments.paper_v2.official_provider_executor import (
    DEFAULT_BUDGET_POLICY,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/gemini_quota_snapshot_v1.json"
)
SCHEMA_VERSION = "m3-paper-v2-gemini-quota-snapshot-1.0"
SOURCE_URL = "https://ai.dev/usage?tab=rate-limit"
MODEL_ID = "gemini-3.6-flash"


class GeminiQuotaSnapshotError(ValueError):
    """当 Gemini 配额快照不完整或不安全时抛出的异常。"""


def _load_budget_policy(
    path: Path = DEFAULT_BUDGET_POLICY,
) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise GeminiQuotaSnapshotError("budget policy must be an object")
    return value


def _base_snapshot() -> dict[str, Any]:
    policy = _load_budget_policy()
    return {
        "schema_version": SCHEMA_VERSION,
        "provider_id": "gemini",
        "provider_name": "Google",
        "model_id": MODEL_ID,
        "source_type": "ai_studio_active_project_rate_limits",
        "source_url": SOURCE_URL,
        "capture_method": "manual_transcription_by_project_owner",
        "limit_values_source": "user_submitted_ai_studio_screenshot",
        "billing_tier_source": "project_owner_declaration",
        "captured_at_semantics": (
            "user_submission_observed_at_not_provider_console_event_time"
        ),
        "billing_tier": "free",
        "paid_tier_allowed": False,
        "monetary_hard_limit_usd": 0.0,
        "chargeable_features_enabled": False,
        "active_limits": {
            "rpm": None,
            "tpm": None,
            "rpd": None,
        },
        "captured_at": None,
        "user_attested": False,
        "source_screenshot_sha256": None,
        "source_screenshot_stored_in_repository": False,
        "project_identifier_stored": False,
        "api_key_or_credential_stored": False,
        "local_batch_caps": dict(
            policy["gemini"]["local_batch_caps"]
        ),
        "execution_must_recheck_age_hours": 24,
        "quota_gate_satisfied": False,
        "formal_execution_authorized": False,
        "network_calls_made": 0,
        "formal_results_created": 0,
    }


def build_pending_template() -> dict[str, Any]:
    return {
        **_base_snapshot(),
        "status": "pending_manual_ai_studio_capture",
    }


def build_active_snapshot(
    *,
    rpm: int,
    tpm: int,
    rpd: int,
    captured_at: str,
    source_screenshot_sha256: str | None = None,
) -> dict[str, Any]:
    value = {
        **_base_snapshot(),
        "status": "active_project_quota_captured",
        "active_limits": {
            "rpm": rpm,
            "tpm": tpm,
            "rpd": rpd,
        },
        "captured_at": captured_at,
        "user_attested": True,
        "source_screenshot_sha256": source_screenshot_sha256,
        "quota_gate_satisfied": True,
    }
    return validate_snapshot(value)


def _positive_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise GeminiQuotaSnapshotError(f"{field} must be a positive integer")
    return value


def _valid_datetime(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise GeminiQuotaSnapshotError("captured_at is required")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise GeminiQuotaSnapshotError(
            "captured_at must be an ISO-8601 datetime"
        ) from exc
    return value


def validate_snapshot(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise GeminiQuotaSnapshotError("quota snapshot must be an object")
    expected = _base_snapshot()
    for field in (
        "schema_version",
        "provider_id",
        "provider_name",
        "model_id",
        "source_type",
        "source_url",
        "capture_method",
        "limit_values_source",
        "billing_tier_source",
        "captured_at_semantics",
        "billing_tier",
        "paid_tier_allowed",
        "monetary_hard_limit_usd",
        "chargeable_features_enabled",
        "source_screenshot_stored_in_repository",
        "project_identifier_stored",
        "api_key_or_credential_stored",
        "local_batch_caps",
        "execution_must_recheck_age_hours",
        "formal_execution_authorized",
        "network_calls_made",
        "formal_results_created",
    ):
        if value.get(field) != expected[field]:
            raise GeminiQuotaSnapshotError(
                f"quota snapshot safety field drift: {field}"
            )
    limits = value.get("active_limits")
    if not isinstance(limits, Mapping) or set(limits) != {
        "rpm",
        "tpm",
        "rpd",
    }:
        raise GeminiQuotaSnapshotError(
            "active limits must contain exactly RPM, TPM and RPD"
        )
    screenshot = value.get("source_screenshot_sha256")
    if screenshot is not None and (
        not isinstance(screenshot, str)
        or len(screenshot) != 64
        or any(character not in "0123456789abcdef" for character in screenshot)
    ):
        raise GeminiQuotaSnapshotError(
            "screenshot digest must be lowercase SHA-256"
        )
    status = value.get("status")
    if status == "pending_manual_ai_studio_capture":
        if (
            dict(limits) != {"rpm": None, "tpm": None, "rpd": None}
            or value.get("captured_at") is not None
            or value.get("user_attested") is not False
            or value.get("quota_gate_satisfied") is not False
            or screenshot is not None
        ):
            raise GeminiQuotaSnapshotError(
                "pending quota template contains active evidence"
            )
    elif status == "active_project_quota_captured":
        _positive_int(limits["rpm"], field="RPM")
        _positive_int(limits["tpm"], field="TPM")
        _positive_int(limits["rpd"], field="RPD")
        _valid_datetime(value.get("captured_at"))
        if (
            value.get("user_attested") is not True
            or value.get("quota_gate_satisfied") is not True
        ):
            raise GeminiQuotaSnapshotError(
                "active quota snapshot requires user attestation"
            )
    else:
        raise GeminiQuotaSnapshotError("unsupported quota snapshot status")
    if value.get("formal_execution_authorized") is not False:
        raise GeminiQuotaSnapshotError(
            "quota evidence cannot authorize formal execution"
        )
    return dict(value)


def write_pending_template(path: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    value = build_pending_template()
    validate_snapshot(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return value


def write_active_snapshot(
    *,
    rpm: int,
    tpm: int,
    rpd: int,
    captured_at: str,
    source_screenshot_sha256: str,
    path: Path = DEFAULT_OUTPUT,
) -> dict[str, Any]:
    value = build_active_snapshot(
        rpm=rpm,
        tpm=tpm,
        rpd=rpd,
        captured_at=captured_at,
        source_screenshot_sha256=source_screenshot_sha256,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return value


def verify_snapshot(path: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    return validate_snapshot(value)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--write-template", action="store_true")
    parser.add_argument("--write-active", action="store_true")
    parser.add_argument("--require-active", action="store_true")
    parser.add_argument("--rpm", type=int)
    parser.add_argument("--tpm", type=int)
    parser.add_argument("--rpd", type=int)
    parser.add_argument("--captured-at")
    parser.add_argument("--screenshot-sha256")
    args = parser.parse_args()
    selected_modes = sum(
        bool(value)
        for value in (
            args.verify_only,
            args.write_template,
            args.write_active,
        )
    )
    if selected_modes != 1:
        raise GeminiQuotaSnapshotError(
            "choose exactly one write or verification mode"
        )
    output = (
        args.output
        if args.output.is_absolute()
        else PROJECT_ROOT / args.output
    )
    if args.verify_only:
        value = verify_snapshot(output)
    elif args.write_template:
        value = write_pending_template(output)
    else:
        required = {
            "--rpm": args.rpm,
            "--tpm": args.tpm,
            "--rpd": args.rpd,
            "--captured-at": args.captured_at,
            "--screenshot-sha256": args.screenshot_sha256,
        }
        missing = [name for name, value in required.items() if value is None]
        if missing:
            raise GeminiQuotaSnapshotError(
                "active snapshot requires " + ", ".join(missing)
            )
        value = write_active_snapshot(
            rpm=args.rpm,
            tpm=args.tpm,
            rpd=args.rpd,
            captured_at=args.captured_at,
            source_screenshot_sha256=args.screenshot_sha256,
            path=output,
        )
    print(
        json.dumps(
            {
                "status": value["status"],
                "quota_gate_satisfied": value["quota_gate_satisfied"],
                "formal_execution_authorized": False,
                "network_calls_made": 0,
            },
            sort_keys=True,
        )
    )
    if args.require_active and value["quota_gate_satisfied"] is not True:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
