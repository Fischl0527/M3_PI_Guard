"""Build and verify the resumable paper-v2 medium-experiment execution ledger.

The generated plan contains 480 pending work items and no outcomes.  This module
does not call a model.  It binds later progress events to frozen inputs and
rejects duplicate terminal results, identity drift, and spend beyond the
pre-approved abort ceiling.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from experiments.paper_v2.contracts import canonical_json_bytes


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INDEX = (
    PROJECT_ROOT / "protocols/paper_upgrade_v2/medium_case_index_v1.jsonl"
)
DEFAULT_CASE_MANIFEST = (
    PROJECT_ROOT / "protocols/paper_upgrade_v2/medium_case_manifest_v1.json"
)
DEFAULT_PROVIDER_DECISION = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/provider_cost_decision_candidate_v1.json"
)
DEFAULT_PROVIDER_PREFLIGHT = (
    PROJECT_ROOT / "protocols/paper_upgrade_v2/provider_cost_preflight_v1.json"
)
DEFAULT_PLAN = (
    PROJECT_ROOT / "protocols/paper_upgrade_v2/medium_execution_plan_v1.jsonl"
)
DEFAULT_EXECUTION_MANIFEST = (
    PROJECT_ROOT / "protocols/paper_upgrade_v2/medium_execution_manifest_v1.json"
)

IDENTITY_INPUTS = (
    "protocols/paper_upgrade_v2/medium_case_index_v1.jsonl",
    "protocols/paper_upgrade_v2/medium_case_manifest_v1.json",
    "protocols/paper_upgrade_v2/provider_cost_decision_candidate_v1.json",
    "protocols/paper_upgrade_v2/provider_cost_preflight_v1.json",
    "protocols/paper_upgrade_v2/structural_baseline_registry_v1.json",
    "protocols/paper_upgrade_v2/online_state_audit_registry_v2.json",
    "protocols/paper_upgrade_v2/medium_gate_spec_v1.json",
    "schemas/paper_v2/experiment_record_v1.schema.json",
    "experiments/paper_v2/contracts.py",
)
TERMINAL_EVENT_TYPES = {"completed", "operational_failure"}
ALLOWED_EVENT_TYPES = {"started", *TERMINAL_EVENT_TYPES}


class MediumExecutionError(ValueError):
    """Raised when execution-plan or progress evidence violates the contract."""


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise MediumExecutionError(f"{path}: expected a JSON object")
    return value


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise MediumExecutionError(
                f"{path}:{line_number}: expected a JSON object"
            )
        rows.append(value)
    return rows


def _jsonl_bytes(rows: Iterable[dict[str, Any]]) -> bytes:
    return b"".join(canonical_json_bytes(row) + b"\n" for row in rows)


def _identity_inputs() -> dict[str, dict[str, Any]]:
    locked: dict[str, dict[str, Any]] = {}
    for relative in IDENTITY_INPUTS:
        path = PROJECT_ROOT / relative
        if not path.is_file():
            raise MediumExecutionError(f"missing execution identity input: {relative}")
        locked[relative] = {
            "bytes": path.stat().st_size,
            "sha256": _sha256_file(path),
        }
    return locked


def _execution_identity(
    locked_inputs: dict[str, dict[str, Any]],
    request_parameters: dict[str, Any],
) -> str:
    identity_payload = {
        "schema_version": "m3-paper-v2-medium-execution-identity-1.0",
        "locked_inputs": locked_inputs,
        "request_parameters": request_parameters,
    }
    return _sha256_bytes(canonical_json_bytes(identity_payload))


def _work_key(
    *,
    selection_id: str,
    condition_id: str,
    authorization_regime: str,
) -> str:
    return _sha256_bytes(
        f"{selection_id}\0{condition_id}\0{authorization_regime}".encode()
    )


def build_execution_plan(
    *,
    index_path: Path = DEFAULT_INDEX,
    case_manifest_path: Path = DEFAULT_CASE_MANIFEST,
    provider_decision_path: Path = DEFAULT_PROVIDER_DECISION,
    provider_preflight_path: Path = DEFAULT_PROVIDER_PREFLIGHT,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build the result-blind 480-item plan and its input identity manifest."""

    cases = _load_jsonl(index_path)
    case_manifest = _load_json(case_manifest_path)
    decision = _load_json(provider_decision_path)
    preflight = _load_json(provider_preflight_path)
    if len(cases) != 72 or case_manifest.get("case_count") != 72:
        raise MediumExecutionError("frozen medium set must contain 72 cases")
    if case_manifest.get("index_sha256") != _sha256_file(index_path):
        raise MediumExecutionError("medium index hash does not match case manifest")
    if preflight.get("decision_sha256") != _sha256_file(provider_decision_path):
        raise MediumExecutionError("provider decision hash does not match preflight")

    request_parameters = decision["request_parameters"]
    call_budgets = request_parameters["max_calls_per_condition"]
    locked_inputs = _identity_inputs()
    identity = _execution_identity(locked_inputs, request_parameters)
    work_items: list[dict[str, Any]] = []

    def append_item(
        case: dict[str, Any],
        *,
        condition: str,
        regime: str,
        analysis_tier: str,
    ) -> None:
        work_items.append(
            {
                "schema_version": "m3-paper-v2-medium-work-item-1.0",
                "sequence": len(work_items) + 1,
                "work_key": _work_key(
                    selection_id=case["selection_id"],
                    condition_id=condition,
                    authorization_regime=regime,
                ),
                "execution_identity": identity,
                "selection_id": case["selection_id"],
                "case_id": case["case_id"],
                "benchmark": case["benchmark"],
                "evaluation_case_type": case["evaluation_case_type"],
                "context_dependent": case["context_dependent"],
                "source_record_sha256": case["source_record_sha256"],
                "online_visible_field_digest": case[
                    "online_visible_field_digest"
                ],
                "condition_id": condition,
                "authorization_regime": regime,
                "analysis_tier": analysis_tier,
                "primary_endpoint_eligible": analysis_tier == "primary",
                "max_provider_calls": int(call_budgets[condition]),
                "status": "pending",
                "result_fields_present": False,
            }
        )

    for case in cases:
        for condition in case_manifest["core_conditions"]:
            append_item(
                case,
                condition=condition,
                regime=case["primary_authorization_regime"],
                analysis_tier="primary",
            )
        probe = case.get("regime_probe")
        if probe is not None:
            for condition in probe["condition_ids"]:
                append_item(
                    case,
                    condition=condition,
                    regime=probe["authorization_regime"],
                    analysis_tier="authorization_regime_probe",
                )

    if len(work_items) != 480:
        raise MediumExecutionError(f"expected 480 work items, got {len(work_items)}")
    keys = [item["work_key"] for item in work_items]
    if len(set(keys)) != len(keys):
        raise MediumExecutionError("execution plan contains duplicate work keys")
    plan_bytes = _jsonl_bytes(work_items)
    counts: dict[str, int] = {}
    for item in work_items:
        counts[item["analysis_tier"]] = counts.get(item["analysis_tier"], 0) + 1
    manifest = {
        "schema_version": "m3-paper-v2-medium-execution-manifest-1.0",
        "status": (
            "authorized_results_pending"
            if preflight["gate_pass"]
            else "blocked_provider_gate_results_pending"
        ),
        "generated_at": "2026-07-23T20:30:00+08:00",
        "execution_identity": identity,
        "execution_authorized": preflight["gate_pass"],
        "network_calls_made": 0,
        "results_present": False,
        "work_item_count": len(work_items),
        "work_item_counts": dict(sorted(counts.items())),
        "provider_calls_upper_bound": sum(
            item["max_provider_calls"] for item in work_items
        ),
        "plan_path": DEFAULT_PLAN.relative_to(PROJECT_ROOT).as_posix(),
        "plan_bytes": len(plan_bytes),
        "plan_sha256": _sha256_bytes(plan_bytes),
        "locked_inputs": locked_inputs,
        "provider_gate": {
            "path": provider_preflight_path.relative_to(PROJECT_ROOT).as_posix(),
            "sha256": _sha256_file(provider_preflight_path),
            "status": preflight["status"],
            "gate_pass": preflight["gate_pass"],
            "blockers": preflight["blockers"],
        },
        "resume_contract": {
            "ledger_format": "append_only_jsonl",
            "terminal_event_types": sorted(TERMINAL_EVENT_TYPES),
            "duplicate_terminal_event": "reject",
            "identity_drift": "reject",
            "started_without_terminal": "retry_same_work_key",
            "failure_denominator_rule": "retain_operational_failure_in_itt",
        },
    }
    return work_items, manifest


def verify_execution_plan(
    *,
    plan_path: Path = DEFAULT_PLAN,
    manifest_path: Path = DEFAULT_EXECUTION_MANIFEST,
) -> dict[str, Any]:
    work_items, expected = build_execution_plan()
    if plan_path.read_bytes() != _jsonl_bytes(work_items):
        raise MediumExecutionError("frozen medium execution plan does not reproduce")
    if _load_json(manifest_path) != expected:
        raise MediumExecutionError(
            "frozen medium execution manifest does not reproduce"
        )
    return expected


def validate_progress_events(
    events: Iterable[dict[str, Any]],
    *,
    execution_identity: str,
    known_work_keys: set[str],
) -> dict[str, str]:
    """Validate append-only progress and return terminal status by work key."""

    started: set[str] = set()
    terminal: dict[str, str] = {}
    for event_number, event in enumerate(events, start=1):
        if event.get("schema_version") != "m3-paper-v2-progress-event-1.0":
            raise MediumExecutionError(
                f"progress event {event_number}: unsupported schema"
            )
        if event.get("execution_identity") != execution_identity:
            raise MediumExecutionError(
                f"progress event {event_number}: execution identity drift"
            )
        key = event.get("work_key")
        if key not in known_work_keys:
            raise MediumExecutionError(
                f"progress event {event_number}: unknown work key"
            )
        event_type = event.get("event_type")
        if event_type not in ALLOWED_EVENT_TYPES:
            raise MediumExecutionError(
                f"progress event {event_number}: unsupported event type"
            )
        if event_type == "started":
            if key in terminal:
                raise MediumExecutionError(
                    f"progress event {event_number}: terminal work cannot restart"
                )
            started.add(key)
            continue
        if key in terminal:
            raise MediumExecutionError(
                f"progress event {event_number}: duplicate terminal event"
            )
        if key not in started:
            raise MediumExecutionError(
                f"progress event {event_number}: terminal event without start"
            )
        terminal[key] = event_type
    return terminal


def pending_work_items(
    work_items: list[dict[str, Any]],
    events: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not work_items:
        return []
    identity = work_items[0]["execution_identity"]
    keys = {item["work_key"] for item in work_items}
    terminal = validate_progress_events(
        events,
        execution_identity=identity,
        known_work_keys=keys,
    )
    return [item for item in work_items if item["work_key"] not in terminal]


def assert_spend_headroom(
    preflight: dict[str, Any],
    *,
    spent_usd: float,
    next_work_item_upper_bound_usd: float,
) -> None:
    """Fail closed before a call would cross the approved abort ceiling."""

    if not preflight.get("gate_pass"):
        raise MediumExecutionError("provider/cost gate is not approved")
    hard_limit = preflight.get("hard_spend_limit_usd")
    if not isinstance(hard_limit, (int, float)) or isinstance(hard_limit, bool):
        raise MediumExecutionError("approved preflight lacks a hard spend limit")
    abort_fraction = preflight.get("abort_at_fraction")
    if not isinstance(abort_fraction, (int, float)) or isinstance(
        abort_fraction, bool
    ):
        raise MediumExecutionError("approved preflight lacks abort fraction")
    ceiling = float(hard_limit) * float(abort_fraction)
    if spent_usd + next_work_item_upper_bound_usd > ceiling:
        raise MediumExecutionError("next work item would cross the abort ceiling")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument(
        "--manifest", type=Path, default=DEFAULT_EXECUTION_MANIFEST
    )
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    def resolve(path: Path) -> Path:
        return path if path.is_absolute() else PROJECT_ROOT / path

    plan_path = resolve(args.plan)
    manifest_path = resolve(args.manifest)
    if args.verify_only:
        manifest = verify_execution_plan(
            plan_path=plan_path,
            manifest_path=manifest_path,
        )
    else:
        work_items, manifest = build_execution_plan()
        plan_path.write_bytes(_jsonl_bytes(work_items))
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
