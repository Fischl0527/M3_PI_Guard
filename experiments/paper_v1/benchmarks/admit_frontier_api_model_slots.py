"""Admit two frontier API model slots after a successful redacted smoke.

This command never reads API credentials and never performs network calls.  It
only consumes the smoke manifest, verifies the two-vendor qualification
evidence, and writes a new registry candidate.  It never mutates the input
registry and it never marks smoke evidence as a formal paper result.
"""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .common import portable_path, rows_sha256, sha256_file


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PROTOCOL_DIR = ROOT / "protocols" / "paper_upgrade_v1"
DEFAULT_BASE_REGISTRY = DEFAULT_PROTOCOL_DIR / "model_registry_v2.json"
DEFAULT_SMOKE_MANIFEST = (
    ROOT / "outputs" / "paper_upgrade_v1" / "frontier_api_smoke_v1" / "manifest.json"
)
DEFAULT_OUTPUT_REGISTRY = DEFAULT_PROTOCOL_DIR / "model_registry_v3_candidate.json"
DEFAULT_AUDIT = DEFAULT_PROTOCOL_DIR / "frontier_api_model_slot_registry_admission_v1.json"
ADMISSION_VERSION = "m3-paper-v1-frontier-api-registry-admission-1.0"
REQUIRED_PROVIDERS = {"openai", "anthropic"}


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _check(name: str, passed: bool, detail: Any = None) -> dict[str, Any]:
    return {"name": name, "status": "pass" if passed else "fail", "detail": detail}


def _path(path: Path) -> str:
    return portable_path(path, root=ROOT)


def build_frontier_registry_admission(
    *,
    base_registry_path: Path = DEFAULT_BASE_REGISTRY,
    smoke_manifest_path: Path = DEFAULT_SMOKE_MANIFEST,
    output_registry_path: Path = DEFAULT_OUTPUT_REGISTRY,
    audit_path: Path = DEFAULT_AUDIT,
) -> dict[str, Any]:
    base_registry_path = base_registry_path.resolve()
    smoke_manifest_path = smoke_manifest_path.resolve()
    output_registry_path = output_registry_path.resolve()
    audit_path = audit_path.resolve()
    base_registry = _read_object(base_registry_path)
    smoke = _read_object(smoke_manifest_path)
    raw_results = smoke.get("provider_results", [])
    results = [dict(row) for row in raw_results if isinstance(row, Mapping)]
    completed = [row for row in results if row.get("status") == "completed_network_smoke"]
    completed_providers = {str(row.get("provider", "")) for row in completed}
    model_ids = [str(row.get("model_id", "")).strip() for row in completed]
    checks = [
        _check(
            "base_registry_schema_supported",
            base_registry.get("schema_version") == "paper-model-registry-2.0"
            and isinstance(base_registry.get("models"), list),
            base_registry.get("schema_version"),
        ),
        _check(
            "smoke_status_completed_two_vendors",
            smoke.get("status") == "completed_two_vendor_network_smoke",
            smoke.get("status"),
        ),
        _check(
            "smoke_performed_exactly_two_network_calls",
            smoke.get("network_calls_performed") is True
            and smoke.get("network_call_count") == 2
            and smoke.get("completed_provider_count") == 2,
            {
                "network_calls_performed": smoke.get("network_calls_performed"),
                "network_call_count": smoke.get("network_call_count"),
                "completed_provider_count": smoke.get("completed_provider_count"),
            },
        ),
        _check(
            "exact_required_provider_set_completed",
            completed_providers == REQUIRED_PROVIDERS and len(completed) == 2,
            sorted(completed_providers),
        ),
        _check(
            "model_ids_are_exact_nonempty_and_unique",
            len(model_ids) == 2 and all(model_ids) and len(set(model_ids)) == 2,
            model_ids,
        ),
        _check(
            "each_provider_used_one_attempt_and_followed_smoke_instruction",
            len(completed) == 2
            and all(row.get("provider_attempts") == 1 for row in completed)
            and all(row.get("response_exact_safe") is True for row in completed),
            [
                {
                    "provider": row.get("provider"),
                    "provider_attempts": row.get("provider_attempts"),
                    "response_exact_safe": row.get("response_exact_safe"),
                }
                for row in completed
            ],
        ),
        _check(
            "smoke_remains_non_formal",
            smoke.get("result_eligible_for_formal_tables") is False,
            smoke.get("result_eligible_for_formal_tables"),
        ),
    ]
    failures = [check for check in checks if check["status"] == "fail"]
    registry_written = False
    if not failures:
        registry = deepcopy(base_registry)
        existing = [
            dict(row)
            for row in registry.get("models", [])
            if isinstance(row, Mapping) and row.get("role") != "frontier_api_vendor"
        ]
        smoke_sha256 = sha256_file(smoke_manifest_path)
        for row in sorted(completed, key=lambda item: str(item.get("provider", ""))):
            provider = str(row["provider"])
            model_id = str(row["model_id"])
            existing.append(
                {
                    "id": f"api:{provider}:{model_id}",
                    "provider": provider,
                    "provider_model_id": model_id,
                    "family": provider,
                    "role": "frontier_api_vendor",
                    "formal_slot_status": "network_smoke_qualified_pending_formal_matrix",
                    "smoke_evidence": _path(smoke_manifest_path),
                    "smoke_manifest_sha256": smoke_sha256,
                    "smoke_provider_attempts": 1,
                    "result_eligible_for_formal_tables": False,
                }
            )
        registry.update(
            {
                "schema_version": "paper-model-registry-3.0-candidate",
                "registry_version": "m3-paper-v1-model-registry-3.0-candidate",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "status": "completed_two_frontier_slots_pending_formal_matrix_freeze",
                "models": existing,
                "summary": {
                    "total_model_slots": len(existing),
                    "frontier_api_vendor_slots": 2,
                    "frontier_provider_ids": sorted(completed_providers),
                },
                "boundary": (
                    "Frontier slots passed synthetic connectivity smoke only. They remain "
                    "ineligible for effect tables until a separate formal benchmark freeze, "
                    "complete run manifests, cost logs and analysis are complete."
                ),
            }
        )
        output_registry_path.parent.mkdir(parents=True, exist_ok=True)
        output_registry_path.write_text(
            json.dumps(registry, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        registry_written = True
    else:
        output_registry_path.unlink(missing_ok=True)

    audit = {
        "schema_version": "paper-frontier-api-registry-admission-1.0",
        "admission_version": ADMISSION_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "admitted_registry_candidate" if registry_written else "blocked_smoke_not_qualified",
        "base_registry_path": _path(base_registry_path),
        "base_registry_sha256": sha256_file(base_registry_path),
        "smoke_manifest_path": _path(smoke_manifest_path),
        "smoke_manifest_sha256": sha256_file(smoke_manifest_path),
        "output_registry_path": _path(output_registry_path),
        "output_registry_written": registry_written,
        "output_registry_sha256": sha256_file(output_registry_path) if registry_written else "",
        "checks": checks,
        "checks_sha256": rows_sha256(checks),
        "passed_checks": sum(check["status"] == "pass" for check in checks),
        "total_checks": len(checks),
        "failures": failures,
        "network_calls_performed_by_admission": False,
        "result_eligible_for_formal_tables": False,
        "boundary": (
            "Offline registry admission only. It consumes redacted smoke metadata, never "
            "credentials, and does not make a model a formal paper result."
        ),
    }
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return audit


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-registry", type=Path, default=DEFAULT_BASE_REGISTRY)
    parser.add_argument("--smoke-manifest", type=Path, default=DEFAULT_SMOKE_MANIFEST)
    parser.add_argument("--output-registry", type=Path, default=DEFAULT_OUTPUT_REGISTRY)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    return parser


def main() -> int:
    args = _parser().parse_args()
    audit = build_frontier_registry_admission(
        base_registry_path=args.base_registry,
        smoke_manifest_path=args.smoke_manifest,
        output_registry_path=args.output_registry,
        audit_path=args.audit,
    )
    print(json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if audit["status"] == "admitted_registry_candidate" else 2


if __name__ == "__main__":
    raise SystemExit(main())
