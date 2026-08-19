"""Plan or execute one synthetic, redacted smoke per frontier API vendor.

Default behavior is plan-only and performs no network calls.  Real execution
requires both ``--execute`` and the exact consent value in the ignored local
configuration.  The smoke prompt is fixed synthetic text; no unpublished M3
case, tool output, experiment result or private data is uploaded.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from experiments.paper_v1.frontier_client import FrontierAPIClient
from m3_core.project_config import is_placeholder, parse_env_file, resolve_config_path

from .audit_frontier_api_model_slots import CONSENT_VALUE, PROVIDERS
from .common import portable_path, rows_sha256


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = ROOT / "outputs" / "paper_upgrade_v1" / "frontier_api_smoke_v1"
SMOKE_VERSION = "m3-paper-v1-frontier-api-smoke-1.0"
SMOKE_MESSAGES = [
    {
        "role": "system",
        "content": "Return exactly the word SAFE. This is a synthetic connectivity check.",
    },
    {
        "role": "user",
        "content": "Synthetic public smoke input: no project data is included.",
    },
]


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def build_smoke_plan(values: Mapping[str, str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for provider, fields in PROVIDERS.items():
        key_field = str(fields["api_key"])
        model_field = str(fields["model_id"])
        base_url_field = str(fields["base_url"])
        key_ready = not is_placeholder(values.get(key_field))
        model_ready = not is_placeholder(values.get(model_field))
        base_url_ready = not is_placeholder(values.get(base_url_field))
        rows.append(
            {
                "provider": provider,
                "api_key_status": "set_redacted" if key_ready else "missing_or_placeholder",
                "model_id": str(values.get(model_field, "")) if model_ready else "",
                "base_url_status": "configured" if base_url_ready else "official_default",
                "configured": key_ready and model_ready,
                "network_call_planned": key_ready and model_ready,
                "smoke_input_class": "fixed_synthetic_public_text_only",
            }
        )
    return rows


def execute_smokes(
    values: Mapping[str, str],
    *,
    output_dir: Path,
    execute: bool,
) -> dict[str, Any]:
    plan = build_smoke_plan(values)
    consent = str(values.get("M3_FRONTIER_API_CONSENT", "")).strip() == CONSENT_VALUE
    if execute and not consent:
        raise ValueError("frontier smoke execution requires explicit local network consent")
    if execute and not all(row["configured"] for row in plan):
        raise ValueError("frontier smoke execution requires both configured vendors")
    output_dir = output_dir.resolve()
    provider_results: list[dict[str, Any]] = []
    if execute:
        for row in plan:
            provider = str(row["provider"])
            fields = PROVIDERS[provider]
            model_id = str(values[str(fields["model_id"])])
            try:
                client = FrontierAPIClient(
                    provider=provider,
                    model=model_id,
                    api_key=str(values[str(fields["api_key"])]),
                    base_url=(
                        str(values.get(str(fields["base_url"]), ""))
                        if not is_placeholder(values.get(str(fields["base_url"])))
                        else ""
                    ),
                    temperature=0.0,
                    max_tokens=8,
                    timeout=60.0,
                    network_consent=True,
                )
                result = client.complete(SMOKE_MESSAGES)
                provider_results.append(
                    {
                        "provider": provider,
                        "model_id": client.model,
                        "status": "completed_network_smoke",
                        "response_text_sha256": hashlib.sha256(
                            result.text.encode("utf-8")
                        ).hexdigest(),
                        "response_exact_safe": result.text.strip() == "SAFE",
                        "model_latency_ms": result.model_latency_ms,
                        "prompt_tokens": result.prompt_tokens,
                        "completion_tokens": result.completion_tokens,
                        "total_tokens": result.total_tokens,
                        "request_metadata": client.last_request_metadata,
                        "provider_attempts": result.provider_attempts,
                    }
                )
            except Exception as exc:  # preserve one-attempt provider failure safely
                provider_results.append(
                    {
                        "provider": provider,
                        "model_id": model_id,
                        "status": "failed_network_smoke_preserved",
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                        "provider_attempts": 1,
                    }
                )
                continue
    completed_provider_count = sum(
        row.get("status") == "completed_network_smoke" for row in provider_results
    )
    status = (
        "completed_two_vendor_network_smoke"
        if execute and completed_provider_count == 2
        else "failed_network_smoke_preserved"
        if execute
        else "plan_only_no_network"
    )
    manifest = {
        "schema_version": "paper-frontier-api-smoke-manifest-1.0",
        "smoke_version": SMOKE_VERSION,
        "status": status,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "explicit_network_consent": consent,
        "network_calls_performed": bool(execute),
        "network_call_count": len(provider_results),
        "completed_provider_count": completed_provider_count,
        "result_eligible_for_formal_tables": False,
        "provider_plan": plan,
        "provider_plan_sha256": rows_sha256(plan),
        "provider_results": provider_results,
        "provider_results_sha256": rows_sha256(provider_results),
        "boundary": (
            "Connectivity/serialization qualification only. The fixed synthetic prompt contains "
            "no M3 cases or private data. Model slots require separate frozen formal runs and "
            "registry admission before entering paper tables."
        ),
    }
    _write_json(output_dir / "manifest.json", manifest)
    return manifest


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--execute", action="store_true")
    return parser


def main() -> int:
    args = _parser().parse_args()
    config_path = resolve_config_path(args.config)
    values = parse_env_file(config_path)
    manifest = execute_smokes(
        values,
        output_dir=args.output_dir,
        execute=bool(args.execute),
    )
    manifest["config_path"] = portable_path(config_path, root=ROOT)
    _write_json(args.output_dir.resolve() / "manifest.json", manifest)
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "network_calls_performed": manifest["network_calls_performed"],
                "network_call_count": manifest["network_call_count"],
                "configured_providers": [
                    row["provider"] for row in manifest["provider_plan"] if row["configured"]
                ],
                "output": portable_path(args.output_dir.resolve(), root=ROOT),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if manifest["status"] != "failed_network_smoke_preserved" else 1


if __name__ == "__main__":
    raise SystemExit(main())
