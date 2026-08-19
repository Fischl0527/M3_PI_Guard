"""Zero-model correctness gate for Progent v1.4.

The audit is deliberately offline: it does not start Ollama, does not call an
API and does not execute any AgentDojo case.  It validates the corrected metric
contract, staged freeze identity and historical evidence boundary before P3.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .build_progent_source_backed_formal_freeze_v14 import DEFAULT_OUTPUT as DEFAULT_FREEZE
from .common import portable_path, resolve_artifact_path, rows_sha256, sha256_file
from .formal_run_identity import validate_hash_bound_files
from .progent_policy_contract import PolicySchemaValidationError, validate_generated_policy_shape
from .progent_source_backed_runtime_v14 import runtime_contract
from .strong_baseline_metric_semantics_v2 import METRIC_SEMANTICS_VERSION


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_G0 = (
    ROOT
    / "protocols"
    / "paper_upgrade_v1"
    / "execution"
    / "progent_v12_p0_metric_semantics_v1"
    / "gate_g0.json"
)
DEFAULT_OUTPUT_DIR = (
    ROOT
    / "protocols"
    / "paper_upgrade_v1"
    / "execution"
    / "progent_v14_p2_correctness_v1"
)
AUDIT_VERSION = "m3-paper-v1-progent-v14-correctness-audit-1.0"


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(str(path) + " must contain a JSON object")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _source(freeze: Mapping[str, Any], name: str) -> str:
    raw = freeze.get("local_adapter", {}).get("files", {}).get(name, "")
    path = resolve_artifact_path(str(raw), root=ROOT)
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _protected_hashes_current(audit: Mapping[str, Any]) -> dict[str, str]:
    current: dict[str, str] = {}
    for row in audit.get("adapter_inventory", []):
        if not isinstance(row, Mapping):
            continue
        path = resolve_artifact_path(str(row.get("path", "")), root=ROOT)
        current[str(row.get("adapter"))] = sha256_file(path) if path.exists() else ""
    for name, row in audit.get("historical_recalculation", {}).items():
        if not isinstance(row, Mapping):
            continue
        path = resolve_artifact_path(str(row.get("path", "")), root=ROOT)
        current[str(name)] = sha256_file(path) if path.exists() else ""
    return current


def _history_hashes_unchanged(audit: Mapping[str, Any]) -> bool:
    before = audit.get("protected_hashes_before", {})
    after = audit.get("protected_hashes_after", {})
    if not isinstance(before, Mapping) or not isinstance(after, Mapping):
        return False
    if dict(before) != dict(after):
        return False
    current = _protected_hashes_current(audit)
    for key, digest in before.items():
        if current.get(str(key)) != digest:
            return False
    return True


def _check(name: str, passed: bool, detail: Any) -> dict[str, Any]:
    return {"name": name, "status": "pass" if passed else "fail", "detail": detail}


def audit(*, freeze_path: Path, g0_path: Path, output_dir: Path) -> dict[str, Any]:
    freeze = _read_json(freeze_path)
    g0 = _read_json(g0_path)
    p0_audit = _read_json(resolve_artifact_path(str(g0.get("audit_path", "")), root=ROOT))
    local_hashes: dict[str, str] = {}
    local_hash_error = ""
    try:
        local_hashes = validate_hash_bound_files(freeze.get("local_adapter", {}))
    except Exception as exc:  # noqa: BLE001 - audit must record, not mask, failures.
        local_hash_error = f"{type(exc).__name__}: {exc}"
    runner_source = _source(freeze, "runner")
    worker_source = _source(freeze, "worker")
    analyzer_source = _source(freeze, "analyzer")
    runtime_source = _source(freeze, "runtime")
    policy_contract_source = _source(freeze, "policy_contract")
    contract = runtime_contract()
    selections = freeze.get("selections", {})
    policy_contract_fixture: dict[str, Any] = {}
    try:
        validated = validate_generated_policy_shape(
            [{"name": "send_email", "args": {"recipient": "alice@example.test"}}],
            available_tool_names={"send_email"},
        )
        try:
            validate_generated_policy_shape([{"args": {}}], available_tool_names={"send_email"})
            invalid_rejected = False
            invalid_error = ""
        except PolicySchemaValidationError as exc:
            invalid_rejected = True
            invalid_error = str(exc)
        policy_contract_fixture = {
            "valid_item_count": len(validated),
            "invalid_missing_name_rejected": invalid_rejected,
            "invalid_error": invalid_error,
        }
    except Exception as exc:  # noqa: BLE001 - audit reports fixture failures as gate failures.
        policy_contract_fixture = {
            "fixture_error": f"{type(exc).__name__}: {exc}",
        }
    checks = [
        _check(
            "freeze_schema_and_status",
            freeze.get("schema_version") == "paper-progent-source-backed-freeze-1.4"
            and freeze.get("status") == "completed_frozen_formal_protocol",
            {"schema": freeze.get("schema_version"), "status": freeze.get("status")},
        ),
        _check(
            "g0_metric_semantics_still_passes",
            g0.get("status") == "passed"
            and g0.get("audit_sha256")
            == sha256_file(resolve_artifact_path(str(g0.get("audit_path", "")), root=ROOT)),
            {"g0_status": g0.get("status"), "audit_path": g0.get("audit_path")},
        ),
        _check("protected_historical_hashes_unchanged", _history_hashes_unchanged(p0_audit), "P0 protected hashes"),
        _check("local_adapter_hashes_valid", not local_hash_error, local_hash_error or local_hashes),
        _check(
            "runtime_contract_zero_retry",
            contract == freeze.get("runtime_contract")
            and contract["agent_sdk_max_retries"] == 0
            and contract["policy_sdk_max_retries"] == 0
            and contract["request_timeout_seconds"] == 120.0,
            contract,
        ),
        _check(
            "agent_client_identity_dedup_contract",
            contract.get("agent_client_replacement_deduplicates_object_identity") is True
            and "agent_client_binding" in runtime_source
            and "unique_client_object_count" in runtime_source
            and "duplicate_position_count" in runtime_source,
            "runtime records reused OpenAILLM positions and unique client objects",
        ),
        _check(
            "policy_contract_validator_enabled",
            contract.get("policy_contract_validator_enabled") is True
            and contract.get("policy_contract_validator_changes_prompts") is False
            and contract.get("policy_contract_validator_changes_policy_enforcement") is False
            and "validate_generated_policy_shape" in runtime_source
            and "PolicySchemaValidationError" in policy_contract_source,
            contract,
        ),
        _check(
            "policy_contract_fixtures_pass",
            policy_contract_fixture.get("valid_item_count") == 1
            and policy_contract_fixture.get("invalid_missing_name_rejected") is True,
            policy_contract_fixture,
        ),
        _check(
            "upstream_policy_retry_loop_preserved",
            contract["policy_temperature_sequence"] == [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
            and "upstream_secagent_six_attempt_loop" in runtime_source,
            contract["policy_temperature_sequence"],
        ),
        _check(
            "child_watchdog_and_failure_trace_present",
            "subprocess.Popen" in runner_source
            and "CaseWatchdogTimeout" in runner_source
            and "trace_sealed" in runner_source
            and "parent_terminal_failure" in runner_source,
            "runner parent failure contract",
        ),
        _check(
            "no_retry_failed_interface",
            "--retry-failed" not in runner_source and "retry_failed\": False" in runner_source,
            "qualification runner has no failed-row retry option",
        ),
        _check(
            "canonical_metric_semantics_used",
            METRIC_SEMANTICS_VERSION == freeze.get("metric_semantics_version")
            and "metric_fields(" in worker_source
            and "attack_success = not" not in worker_source
            and "validate_metric_row" in analyzer_source,
            freeze.get("metric_semantics_version"),
        ),
        _check(
            "failed_cases_unresolved_not_safe",
            freeze.get("failure_policy", {}).get(
                "security_operational_failure_scored_as_unresolved"
            )
            is True
            and freeze.get("failure_policy", {}).get(
                "timeout_parser_transport_runtime_failures_never_scored_as_safety"
            )
            is True,
            freeze.get("failure_policy", {}),
        ),
        _check(
            "selections_exact_and_hash_bound",
            selections.get("p3", {}).get("case_counts") == {"utility": 4, "security": 4, "total": 8}
            and selections.get("p4", {}).get("case_counts") == {"utility": 8, "security": 8, "total": 16}
            and selections.get("p5", {}).get("case_counts") == {"utility": 16, "security": 16, "total": 32}
            and selections.get("formal", {}).get("case_counts") == {"utility": 97, "security": 629, "total": 726}
            and rows_sha256(freeze.get("case_rows", [])) == freeze.get("case_rows_sha256"),
            {name: row.get("case_counts") for name, row in selections.items() if isinstance(row, Mapping)},
        ),
        _check(
            "formal_execution_blocked_until_separate_authorization",
            freeze.get("formal_execution_authorized") is False,
            freeze.get("formal_execution_authorized"),
        ),
    ]
    failed = [row["name"] for row in checks if row["status"] != "pass"]
    result = {
        "schema_version": "paper-progent-v14-correctness-audit-1.0",
        "audit_version": AUDIT_VERSION,
        "status": "completed_pass" if not failed else "completed_fail",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model_calls": 0,
        "api_calls": 0,
        "ollama_probe_performed": False,
        "benchmark_cases_executed": 0,
        "freeze_path": portable_path(freeze_path, root=ROOT),
        "freeze_sha256": sha256_file(freeze_path),
        "g0_path": portable_path(g0_path, root=ROOT),
        "checks": checks,
        "passed_checks": len(checks) - len(failed),
        "total_checks": len(checks),
        "failed_checks": failed,
        "next_action": "run_fresh_progent_v14_p3" if not failed else "fix_progent_v14_correctness",
        "boundary": (
            "Zero-model P2 audit only. A pass permits fresh v1.4 P3 qualification, not P6 formal execution."
        ),
    }
    _write_json(output_dir / "correctness_audit.json", result)
    gate = {
        "schema_version": "paper-progent-v14-gate-1.0",
        "gate": "G1_progent_v14_zero_model_correctness",
        "status": "passed" if not failed else "failed",
        "passed": not failed,
        "created_at": result["created_at"],
        "audit_path": portable_path(output_dir / "correctness_audit.json", root=ROOT),
        "audit_sha256": sha256_file(output_dir / "correctness_audit.json"),
        "checks": {row["name"]: row["status"] == "pass" for row in checks},
        "next_action": result["next_action"],
    }
    _write_json(output_dir / "gate_g1.json", gate)
    _write_markdown(output_dir / "gate_g1.md", gate, result)
    return result


def _write_markdown(path: Path, gate: Mapping[str, Any], result: Mapping[str, Any]) -> None:
    lines = [
        "# Progent v1.4 G1 zero-model correctness gate",
        "",
        f"- Status: `{gate['status']}`",
        f"- Checks: `{result['passed_checks']}/{result['total_checks']}`",
        f"- Audit: `{gate['audit_path']}`",
        f"- Next action: `{gate['next_action']}`",
        "- Model/API calls: `0`",
        "",
        "## Boundary",
        "",
        str(result["boundary"]),
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", type=Path, default=DEFAULT_FREEZE)
    parser.add_argument("--g0", type=Path, default=DEFAULT_G0)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = audit(
        freeze_path=args.freeze.resolve(),
        g0_path=args.g0.resolve(),
        output_dir=args.output_dir.resolve(),
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "checks": f"{result['passed_checks']}/{result['total_checks']}",
                "next_action": result["next_action"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if result["status"] == "completed_pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
