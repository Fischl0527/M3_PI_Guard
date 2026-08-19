"""Prospective pending-only DeepSeek remainder shard after frozen v8.

The v8 run is immutable and contains 303 terminal work items.  This controller
creates a separate run identity for the 177 work items that were never started.
It never copies, rewrites, retries, or excludes a terminal v8 item.  A closed
diagnostic pauses the current process; a later operator invocation may continue
only with still-pending work items under the same prospective admission.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from functools import lru_cache
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Callable, Mapping

from jsonschema import Draft202012Validator, FormatChecker

import experiments.paper_v2.formal_matrix_controller_v1 as v1
import experiments.paper_v2.formal_matrix_controller_v8 as source
import experiments.paper_v2.formal_result_gate_v2 as gate_base
from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.official_provider_executor import ProviderPausedError
from m3_core.project_config import parse_env_file, resolve_config_path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_ROOT = PROJECT_ROOT / "protocols/paper_upgrade_v2"
DEFAULT_SCHEMA = (
    PROJECT_ROOT
    / "schemas/paper_v2/formal_matrix_remainder_admission_v9.schema.json"
)
DEFAULT_QUALIFICATION = (
    PROTOCOL_ROOT / "formal_matrix_remainder_qualification_v9.json"
)
DEFAULT_CANDIDATE = (
    PROTOCOL_ROOT / "deepseek_medium_remainder_candidate_v9.json"
)
DEFAULT_ADMISSION = (
    PROTOCOL_ROOT
    / "admissions/deepseek_medium_remainder_admission_v9.json"
)
DEFAULT_BUDGET_POLICY = source.DEFAULT_BUDGET_POLICY
DEFAULT_PLAN = v1.DEFAULT_PLAN

RUN_ID = "paper-v2-deepseek-medium-v9-remainder-20260726"
SCHEMA_VERSION = "m3-paper-v2-formal-matrix-remainder-admission-9.0"
QUALIFICATION_RECORDED_AT = "2026-07-26T17:05:00+08:00"
CANDIDATE_RECORDED_AT = "2026-07-26T17:10:00+08:00"
ADMISSION_APPROVED_AT = "2026-07-26T17:15:00+08:00"
CANDIDATE_STATUS = "remainder_shard_candidate_frozen"
ACTIVE_STATUS = "activated_for_pending_only_remainder_shard"
OWNER_STATEMENT_SHA256 = source.OWNER_STATEMENT_SHA256
SOURCE_EXPECTED_RECORDS = 303
SOURCE_EXPECTED_COMPLETED = 302
SOURCE_EXPECTED_DIAGNOSTICS = 1
SOURCE_EXPECTED_OPERATIONAL_FAILURES = 1
REMAINDER_EXPECTED_RECORDS = 177
COMBINED_EXPECTED_RECORDS = 480
MAXIMUM_COMBINED_DIAGNOSTICS = 4
PRIOR_PROJECT_USAGE = {
    "completion_tokens": 99884,
    "prompt_cache_hit_tokens": 687616,
    "prompt_cache_miss_tokens": 196815,
    "prompt_tokens": 884431,
}
PRIOR_PROJECT_COST_CNY = 1.2069394


class FormalMatrixRemainderV9Error(RuntimeError):
    """Raised when the pending-only v9 shard cannot preserve its contract."""


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise FormalMatrixRemainderV9Error(f"{path}: expected an object")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _display_path(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()


def _resolve_project_path(value: str) -> Path:
    path = (PROJECT_ROOT / value).resolve()
    try:
        path.relative_to(PROJECT_ROOT.resolve())
    except ValueError as exc:
        raise FormalMatrixRemainderV9Error(
            "remainder-shard path escapes the project root"
        ) from exc
    return path


def _manifest_sha(value: Mapping[str, Any]) -> str:
    return sha256_canonical_json(
        {key: item for key, item in value.items() if key != "manifest_sha256"}
    )


def _artifact_lock(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FormalMatrixRemainderV9Error(
            f"missing remainder-shard input: {_display_path(path)}"
        )
    return {
        "path": _display_path(path),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def _rows_sha256(rows: list[Mapping[str, Any]]) -> str:
    return sha256_canonical_json([copy.deepcopy(dict(row)) for row in rows])


def _keys_sha256(keys: set[str] | list[str]) -> str:
    return sha256_canonical_json(sorted(str(key) for key in keys))


def _source_authorization() -> Any:
    return source.authorize_matrix(
        source.DEFAULT_CONTINUATION_ADMISSION,
        required_scope="continuation",
    )


@lru_cache(maxsize=1)
def _source_snapshot_cached() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    authorization = _source_authorization()
    state = source._state_from_paths(authorization.permit)
    entries = state["record_entries"]
    records = [entry["record"] for entry in entries]
    terminal_keys = {
        str(key) for key in state["record_status"]["terminal_work_keys"]
    }
    pending_rows = [
        copy.deepcopy(dict(row)) for row in state["pending_work_items"]
    ]
    pending_keys = {str(row["work_key"]) for row in pending_rows}
    all_rows = v1._plan_rows()
    all_keys = {str(row["work_key"]) for row in all_rows}
    completed = sum(
        record["result_tier"] == "formal_candidate" for record in records
    )
    diagnostics = sum(
        record["result_tier"] == "diagnostic" for record in records
    )
    failures = sum(
        record["operational_status"]
        in source.previous.previous.base.v2.FAILURE_STATUSES
        for record in records
    )
    diagnostic_records = [
        record for record in records if record["result_tier"] == "diagnostic"
    ]
    technical_checks = {
        "record_count": len(entries) == SOURCE_EXPECTED_RECORDS,
        "completed_count": completed == SOURCE_EXPECTED_COMPLETED,
        "diagnostic_count": diagnostics == SOURCE_EXPECTED_DIAGNOSTICS,
        "operational_failure_count": (
            failures == SOURCE_EXPECTED_OPERATIONAL_FAILURES
        ),
        "pending_count": len(pending_rows) == REMAINDER_EXPECTED_RECORDS,
        "open_attempts": not state["attempt_status"]["open_work_keys"],
        "budget_unpaused": state["budget_status"]["paused"] is False,
        "terminal_pending_disjoint": not (terminal_keys & pending_keys),
        "full_plan_coverage": terminal_keys | pending_keys == all_keys,
        "diagnostic_is_closed_transport_failure": all(
            record["operational_status"] in {"provider_failure", "timeout"}
            and record["provider_trace_bundle"]["result_tier_ceiling"]
            == "diagnostic"
            and record["provider_trace_bundle"]["automatic_retry"] is False
            and record["provider_trace_bundle"]["provider_tools_declared"]
            is False
            and record["provider_trace_bundle"]["external_effects_enabled"]
            is False
            and record["provider_trace_bundle"][
                "prompt_or_response_content_stored"
            ]
            is False
            for record in diagnostic_records
        ),
        "no_record_declares_external_effects": all(
            record["provider_trace_bundle"]["external_effects_enabled"] is False
            for record in records
        ),
        "no_record_declares_provider_tools": all(
            record["provider_trace_bundle"]["provider_tools_declared"] is False
            for record in records
        ),
        "no_record_declares_automatic_retry": all(
            record["provider_trace_bundle"]["automatic_retry"] is False
            for record in records
        ),
        "usage_matches_frozen_process_summary": (
            state["budget_status"]["project_cumulative_usage"]
            == PRIOR_PROJECT_USAGE
            and state["budget_status"]["project_cumulative_cost_cny"]
            == PRIOR_PROJECT_COST_CNY
        ),
    }
    if not all(technical_checks.values()):
        failed = sorted(
            name for name, passed in technical_checks.items() if not passed
        )
        raise FormalMatrixRemainderV9Error(
            f"v8 source snapshot failed technical checks: {failed}"
        )
    source_locks = {
        "record_ledger": _artifact_lock(authorization.permit.record_ledger_path),
        "attempt_ledger": _artifact_lock(
            authorization.permit.attempt_ledger_path
        ),
        "budget_ledger": _artifact_lock(authorization.permit.budget_ledger_path),
        "provider_traces": gate_base._trace_inventory(
            authorization.permit.trace_root
        ),
    }
    candidate = source._load_json(source.DEFAULT_CANDIDATE)
    snapshot = {
        "run_id": source.RUN_ID,
        "matrix_identity": candidate["scope"]["matrix_identity"],
        "candidate_manifest_sha256": candidate["manifest_sha256"],
        "continuation_admission_sha256": _sha256_file(
            source.DEFAULT_CONTINUATION_ADMISSION
        ),
        "record_count": len(entries),
        "formal_candidate_records": completed,
        "diagnostic_records": diagnostics,
        "operational_failures": failures,
        "pending_work_items": len(pending_rows),
        "open_attempts": 0,
        "provider_calls_completed": state["budget_status"]["event_count"],
        "project_cumulative_usage": copy.deepcopy(
            state["budget_status"]["project_cumulative_usage"]
        ),
        "project_cumulative_cost_cny": state["budget_status"][
            "project_cumulative_cost_cny"
        ],
        "budget_paused": False,
        "terminal_work_keys_sha256": _keys_sha256(terminal_keys),
        "pending_work_keys_sha256": _keys_sha256(pending_keys),
        "pending_rows_sha256": _rows_sha256(pending_rows),
        "source_run_resumable": False,
        "terminal_items_retryable": False,
        "scientific_outcomes_reviewed": False,
        "technical_checks": technical_checks,
        "evidence_locks": source_locks,
    }
    snapshot["technical_snapshot_sha256"] = sha256_canonical_json(snapshot)
    return snapshot, pending_rows


def _source_snapshot() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    snapshot, rows = _source_snapshot_cached()
    return copy.deepcopy(snapshot), copy.deepcopy(rows)


def build_controller_qualification() -> dict[str, Any]:
    snapshot, pending_rows = _source_snapshot()
    all_rows = v1._plan_rows()
    terminal_count = len(all_rows) - len(pending_rows)
    if (
        terminal_count != SOURCE_EXPECTED_RECORDS
        or len(pending_rows) != REMAINDER_EXPECTED_RECORDS
    ):
        raise FormalMatrixRemainderV9Error(
            "remainder qualification selection drift"
        )
    rows = copy.deepcopy(all_rows[:2])
    with TemporaryDirectory(
        prefix="m3-matrix-remainder-v9-qualification-"
    ) as directory:
        root = Path(directory)
        permit = v1.MatrixExecutionPermit(
            admission_file_sha256="9" * 64,
            run_id="offline-matrix-remainder-v9-qualification",
            execution_identity=str(rows[0]["execution_identity"]),
            work_items=tuple(rows),
            output_root=root,
            record_ledger_path=root / "records.jsonl",
            attempt_ledger_path=root / "attempts.jsonl",
            budget_ledger_path=root / "budget.jsonl",
            trace_root=root / "traces",
            max_tokens=256,
            timeout_seconds=30.0,
            scope={
                "budget": {
                    "prior_project_usage": copy.deepcopy(
                        PRIOR_PROJECT_USAGE
                    )
                }
            },
        )
        result = source._execute(
            source.previous.previous.base.V5Authorization(
                permit=permit,
                authorization_scope="qualification",
                active_manifest={},
            ),
            values={},
            dispatcher_factory=(
                source.previous.previous.base._qualification_dispatcher_factory
            ),
            max_new_items=None,
        )
        if (
            result["record_count"] != 2
            or result["diagnostic_records"] != 0
            or result["remaining_work_items"] != 0
        ):
            raise FormalMatrixRemainderV9Error(
                "remainder v9 offline execution qualification failed"
            )
    return {
        "schema_version": (
            "m3-paper-v2-formal-matrix-remainder-qualification-9.0"
        ),
        "generated_at": QUALIFICATION_RECORDED_AT,
        "status": "pending_only_remainder_shard_qualified_offline",
        "source_technical_snapshot_sha256": snapshot[
            "technical_snapshot_sha256"
        ],
        "source_terminal_records": SOURCE_EXPECTED_RECORDS,
        "selected_pending_work_items": REMAINDER_EXPECTED_RECORDS,
        "combined_work_items": COMBINED_EXPECTED_RECORDS,
        "selection_intersection_count": 0,
        "offline_fixture_records": 2,
        "offline_fixture_diagnostics": 0,
        "pending_only_manual_resume": True,
        "terminal_source_items_retryable": False,
        "network_calls_made": 0,
        "credentials_read": 0,
        "scientific_outcomes_read": 0,
        "formal_results_created": 0,
        "source_v8_mutated": False,
        "automatic_retries": 0,
        "provider_tools_enabled": False,
        "external_effects_enabled": False,
        "result_admission_authorized": False,
    }


def write_controller_qualification(
    path: Path = DEFAULT_QUALIFICATION,
) -> dict[str, Any]:
    value = build_controller_qualification()
    _write_json(path, value)
    return value


def verify_controller_qualification(
    path: Path = DEFAULT_QUALIFICATION,
) -> dict[str, Any]:
    observed = _load_json(path)
    expected = build_controller_qualification()
    if observed != expected:
        raise FormalMatrixRemainderV9Error(
            "remainder v9 qualification drift"
        )
    return observed


def _locked_inputs() -> list[dict[str, Any]]:
    paths = (
        Path(__file__),
        DEFAULT_SCHEMA,
        DEFAULT_QUALIFICATION,
        PROJECT_ROOT / "experiments/paper_v2/formal_matrix_controller_v8.py",
        source.DEFAULT_CANDIDATE,
        source.DEFAULT_CONTINUATION_ADMISSION,
        PROJECT_ROOT / "experiments/paper_v2/formal_result_gate_v5.py",
        PROJECT_ROOT
        / "protocols/paper_upgrade_v2/deepseek_medium_result_gate_candidate_v5.json",
        DEFAULT_PLAN,
        DEFAULT_BUDGET_POLICY,
    )
    return [_artifact_lock(path) for path in paths]


def _assert_locked_inputs(scope: Mapping[str, Any]) -> None:
    for item in scope["locked_inputs"]:
        path = _resolve_project_path(str(item["path"]))
        if (
            not path.is_file()
            or path.stat().st_size != item["bytes"]
            or _sha256_file(path) != item["sha256"]
        ):
            raise FormalMatrixRemainderV9Error(
                f"remainder v9 locked input drift: {item['path']}"
            )


def _validate_manifest(
    value: Mapping[str, Any],
    *,
    expected_role: str,
) -> dict[str, Any]:
    Draft202012Validator(
        _load_json(DEFAULT_SCHEMA),
        format_checker=FormatChecker(),
    ).validate(dict(value))
    if value["artifact_role"] != expected_role:
        raise FormalMatrixRemainderV9Error(
            f"expected remainder artifact role {expected_role!r}"
        )
    if value["manifest_sha256"] != _manifest_sha(value):
        raise FormalMatrixRemainderV9Error(
            "remainder manifest digest drift"
        )
    if value["scope_sha256"] != sha256_canonical_json(value["scope"]):
        raise FormalMatrixRemainderV9Error("remainder scope digest drift")
    authorization = value["authorization"]
    if expected_role == "owner_review_candidate":
        checks = (
            value["status"] == CANDIDATE_STATUS,
            authorization["candidate_only"] is True,
            authorization["remainder_shard_execution_authorized"] is False,
            authorization["candidate_manifest_sha256"] is None,
            authorization["owner_approval"] is None,
        )
    else:
        approval = authorization["owner_approval"]
        checks = (
            value["status"] == ACTIVE_STATUS,
            authorization["candidate_only"] is False,
            authorization["remainder_shard_execution_authorized"] is True,
            isinstance(authorization["candidate_manifest_sha256"], str),
            isinstance(approval, Mapping),
            approval.get("statement_sha256") == OWNER_STATEMENT_SHA256,
        )
    if not all(checks):
        raise FormalMatrixRemainderV9Error(
            "remainder authorization semantics drift"
        )
    return copy.deepcopy(dict(value))


def build_matrix_candidate() -> dict[str, Any]:
    qualification = verify_controller_qualification()
    source_snapshot, pending_rows = _source_snapshot()
    locked_inputs = _locked_inputs()
    identity = sha256_canonical_json(
        {
            "run_id": RUN_ID,
            "source_technical_snapshot_sha256": source_snapshot[
                "technical_snapshot_sha256"
            ],
            "pending_rows_sha256": source_snapshot["pending_rows_sha256"],
            "qualification_sha256": _sha256_file(DEFAULT_QUALIFICATION),
            "controller_sha256": _sha256_file(Path(__file__)),
            "schema_sha256": _sha256_file(DEFAULT_SCHEMA),
        }
    )
    output_root = (
        PROJECT_ROOT
        / "outputs/paper_upgrade_v2/formal_medium/deepseek"
        / identity
    )
    source_candidate = source.verify_matrix_candidate()
    scope = {
        "run_id": RUN_ID,
        "matrix_identity": identity,
        "execution_identity": str(pending_rows[0]["execution_identity"]),
        "source_v8": source_snapshot,
        "selection": {
            "selection_kind": "v8_never_started_work_items_only",
            "work_items": len(pending_rows),
            "pending_work_keys_sha256": source_snapshot[
                "pending_work_keys_sha256"
            ],
            "pending_rows_sha256": source_snapshot["pending_rows_sha256"],
            "combined_expected_records": COMBINED_EXPECTED_RECORDS,
            "source_terminal_items_retryable": False,
            "pending_only_manual_resume": True,
        },
        "provider": copy.deepcopy(source_candidate["scope"]["provider"]),
        "budget": {
            **copy.deepcopy(source_candidate["scope"]["budget"]),
            "prior_project_usage": copy.deepcopy(PRIOR_PROJECT_USAGE),
            "prior_project_cost_cny": PRIOR_PROJECT_COST_CNY,
            "maximum_combined_diagnostic_records": (
                MAXIMUM_COMBINED_DIAGNOSTICS
            ),
        },
        "outputs": {
            "root": _display_path(output_root),
            "record_ledger_path": _display_path(
                output_root / "experiment_records_v2.jsonl"
            ),
            "attempt_ledger_path": _display_path(
                output_root / "matrix_attempts_v1.jsonl"
            ),
            "budget_ledger_path": _display_path(
                output_root / "matrix_budget_v1.jsonl"
            ),
            "trace_root": _display_path(output_root / "provider_traces"),
            "single_trace_per_work_item": True,
            "automatic_retry": False,
        },
        "locked_inputs": locked_inputs,
        "qualification": qualification,
        "result_boundary": {
            "result_admission_authorized": False,
            "combined_gate_required": True,
            "scientific_outcomes_reviewed": False,
        },
    }
    core = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": CANDIDATE_RECORDED_AT,
        "status": CANDIDATE_STATUS,
        "artifact_role": "owner_review_candidate",
        "scope": scope,
        "scope_sha256": sha256_canonical_json(scope),
        "authorization": {
            "candidate_only": True,
            "remainder_shard_execution_authorized": False,
            "result_admission_authorized": False,
            "candidate_manifest_sha256": None,
            "owner_approval": None,
        },
        "evidence_boundary": {
            "credentials_read_while_building": False,
            "network_calls_while_building": 0,
            "formal_results_created": 0,
            "candidate_is_executable": False,
            "source_v8_mutated": False,
            "terminal_source_item_retried": False,
            "scientific_outcomes_reviewed": False,
        },
        "next_gate": (
            "Write and verify a separate owner-approved pending-only shard "
            "admission, then freeze combined result gate v6 before API use."
        ),
    }
    value = {**core, "manifest_sha256": sha256_canonical_json(core)}
    return _validate_manifest(
        value,
        expected_role="owner_review_candidate",
    )


def write_matrix_candidate(
    path: Path = DEFAULT_CANDIDATE,
) -> dict[str, Any]:
    value = build_matrix_candidate()
    _write_json(path, value)
    return value


def verify_matrix_candidate(
    path: Path = DEFAULT_CANDIDATE,
) -> dict[str, Any]:
    observed = _validate_manifest(
        _load_json(path),
        expected_role="owner_review_candidate",
    )
    if observed != build_matrix_candidate():
        raise FormalMatrixRemainderV9Error(
            "remainder v9 candidate drift"
        )
    return observed


def build_remainder_admission(
    candidate_path: Path = DEFAULT_CANDIDATE,
) -> dict[str, Any]:
    candidate = verify_matrix_candidate(candidate_path)
    scope = {
        "run_id": RUN_ID,
        "candidate_scope_sha256": candidate["scope_sha256"],
        "pending_work_keys_sha256": candidate["scope"]["selection"][
            "pending_work_keys_sha256"
        ],
    }
    core = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": ADMISSION_APPROVED_AT,
        "status": ACTIVE_STATUS,
        "artifact_role": "remainder_shard_execution_authorization",
        "scope": scope,
        "scope_sha256": sha256_canonical_json(scope),
        "authorization": {
            "candidate_only": False,
            "remainder_shard_execution_authorized": True,
            "result_admission_authorized": False,
            "candidate_manifest_sha256": candidate["manifest_sha256"],
            "owner_approval": {
                "approval_kind": "delegated_safe_api_iteration",
                "approved_by_role": "project_owner",
                "approved_at": ADMISSION_APPROVED_AT,
                "approval_scope": (
                    "deepseek_v9_pending_only_remainder_shard"
                ),
                "statement_sha256": OWNER_STATEMENT_SHA256,
            },
        },
        "evidence_boundary": {
            "credentials_read_while_building": False,
            "network_calls_while_building": 0,
            "formal_results_created": 0,
            "candidate_is_executable": False,
            "source_v8_mutated": False,
            "terminal_source_item_retried": False,
            "scientific_outcomes_reviewed": False,
        },
        "next_gate": (
            "Execute only never-started v8 work items. A diagnostic pauses "
            "the process; a manual pending-only segment may continue without "
            "retrying terminal items. Combined gate v6 remains separate."
        ),
    }
    value = {**core, "manifest_sha256": sha256_canonical_json(core)}
    return _validate_manifest(
        value,
        expected_role="remainder_shard_execution_authorization",
    )


def write_remainder_admission(
    path: Path = DEFAULT_ADMISSION,
) -> dict[str, Any]:
    value = build_remainder_admission()
    _write_json(path, value)
    return value


def verify_remainder_admission(
    path: Path = DEFAULT_ADMISSION,
) -> dict[str, Any]:
    observed = _validate_manifest(
        _load_json(path),
        expected_role="remainder_shard_execution_authorization",
    )
    if observed != build_remainder_admission():
        raise FormalMatrixRemainderV9Error(
            "remainder v9 admission drift"
        )
    return observed


def _state_from_paths(permit: v1.MatrixExecutionPermit) -> dict[str, Any]:
    try:
        return source._state_from_paths(permit)
    except Exception as exc:
        raise FormalMatrixRemainderV9Error(str(exc)) from exc


def authorize_remainder_shard(
    admission_path: Path = DEFAULT_ADMISSION,
    *,
    candidate_path: Path = DEFAULT_CANDIDATE,
) -> source.previous.previous.base.V5Authorization:
    candidate = verify_matrix_candidate(candidate_path)
    admission = verify_remainder_admission(admission_path)
    if (
        admission["authorization"]["candidate_manifest_sha256"]
        != candidate["manifest_sha256"]
        or admission["scope"]["candidate_scope_sha256"]
        != candidate["scope_sha256"]
    ):
        raise FormalMatrixRemainderV9Error(
            "remainder admission does not bind the candidate"
        )
    scope = candidate["scope"]
    _assert_locked_inputs(scope)
    current_snapshot, pending_rows = _source_snapshot()
    if current_snapshot != scope["source_v8"]:
        raise FormalMatrixRemainderV9Error(
            "immutable v8 source snapshot drift"
        )
    if (
        _rows_sha256(pending_rows)
        != scope["selection"]["pending_rows_sha256"]
        or _keys_sha256({str(row["work_key"]) for row in pending_rows})
        != scope["selection"]["pending_work_keys_sha256"]
    ):
        raise FormalMatrixRemainderV9Error(
            "pending-only remainder selection drift"
        )
    outputs = scope["outputs"]
    permit = v1.MatrixExecutionPermit(
        admission_file_sha256=_sha256_file(admission_path),
        run_id=RUN_ID,
        execution_identity=str(pending_rows[0]["execution_identity"]),
        work_items=tuple(copy.deepcopy(pending_rows)),
        output_root=_resolve_project_path(str(outputs["root"])),
        record_ledger_path=_resolve_project_path(
            str(outputs["record_ledger_path"])
        ),
        attempt_ledger_path=_resolve_project_path(
            str(outputs["attempt_ledger_path"])
        ),
        budget_ledger_path=_resolve_project_path(
            str(outputs["budget_ledger_path"])
        ),
        trace_root=_resolve_project_path(str(outputs["trace_root"])),
        max_tokens=int(scope["provider"]["max_tokens"]),
        timeout_seconds=float(scope["provider"]["timeout_seconds"]),
        scope=copy.deepcopy(scope),
    )
    _state_from_paths(permit)
    return source.previous.previous.base.V5Authorization(
        permit=permit,
        authorization_scope="remainder",
        active_manifest=admission,
    )


def _real_dispatcher_factory(
    permit: v1.MatrixExecutionPermit,
    values: Mapping[str, str],
    tracker: v1.MatrixBudgetTracker,
) -> Any:
    return source._real_dispatcher_factory(permit, values, tracker)


def execute_pending_segment(
    *,
    config_path: Path | None = None,
    credential_loader: Callable[[], Mapping[str, str]] | None = None,
    dispatcher_factory: Callable[..., Any] = _real_dispatcher_factory,
) -> dict[str, Any]:
    authorization = authorize_remainder_shard()
    initial = _state_from_paths(authorization.permit)
    if not initial["pending_work_items"]:
        raise FormalMatrixRemainderV9Error(
            "remainder shard is already complete"
        )
    if initial["budget_status"]["paused"]:
        raise ProviderPausedError(
            "remainder shard budget is paused before the next request"
        )
    shard_diagnostics = sum(
        entry["record"]["result_tier"] == "diagnostic"
        for entry in initial["record_entries"]
    )
    source_diagnostics = int(
        authorization.permit.scope["source_v8"]["diagnostic_records"]
    )
    if (
        source_diagnostics + shard_diagnostics
        > MAXIMUM_COMBINED_DIAGNOSTICS
    ):
        raise FormalMatrixRemainderV9Error(
            "combined diagnostic ceiling already exceeded"
        )
    loader = credential_loader or (
        lambda: parse_env_file(resolve_config_path(config_path))
    )
    result = source._execute(
        authorization,
        values=loader(),
        dispatcher_factory=dispatcher_factory,
        max_new_items=None,
    )
    final = _state_from_paths(authorization.permit)
    combined_records = SOURCE_EXPECTED_RECORDS + len(
        final["record_entries"]
    )
    combined_remaining = len(final["pending_work_items"])
    result["controller_version"] = "v9-remainder"
    result["source_v8_record_count"] = SOURCE_EXPECTED_RECORDS
    result["remainder_record_count"] = len(final["record_entries"])
    result["combined_record_count"] = combined_records
    result["combined_remaining_work_items"] = combined_remaining
    result["terminal_source_items_retried"] = 0
    result["pending_only_manual_resume"] = True
    result["result_admission_authorized"] = False
    result["status"] = (
        "remainder_shard_complete_candidate_records_unadmitted"
        if combined_remaining == 0
        else "remainder_shard_paused_manual_resume_required"
    )
    return result


def remainder_status() -> dict[str, Any]:
    authorization = authorize_remainder_shard()
    state = _state_from_paths(authorization.permit)
    diagnostics = sum(
        entry["record"]["result_tier"] == "diagnostic"
        for entry in state["record_entries"]
    )
    return {
        "status": "remainder_v9_status_verified_no_network",
        "run_id": RUN_ID,
        "source_v8_records": SOURCE_EXPECTED_RECORDS,
        "remainder_records": len(state["record_entries"]),
        "combined_records": SOURCE_EXPECTED_RECORDS
        + len(state["record_entries"]),
        "remaining_work_items": len(state["pending_work_items"]),
        "open_attempts": len(state["attempt_status"]["open_work_keys"]),
        "shard_diagnostic_records": diagnostics,
        "combined_diagnostic_records": SOURCE_EXPECTED_DIAGNOSTICS
        + diagnostics,
        "budget_paused": state["budget_status"]["paused"],
        "project_cumulative_usage": state["budget_status"][
            "project_cumulative_usage"
        ],
        "project_cumulative_cost_cny": state["budget_status"][
            "project_cumulative_cost_cny"
        ],
        "network_calls_made_by_status": 0,
        "terminal_source_items_retried": 0,
        "result_admission_authorized": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write-qualification", action="store_true")
    action.add_argument("--verify-qualification", action="store_true")
    action.add_argument("--write-candidate", action="store_true")
    action.add_argument("--verify-candidate", action="store_true")
    action.add_argument("--write-admission", action="store_true")
    action.add_argument("--verify-admission", action="store_true")
    action.add_argument("--execute-pending-segment", action="store_true")
    action.add_argument("--status", action="store_true")
    args = parser.parse_args()

    if args.write_qualification:
        value = write_controller_qualification()
    elif args.verify_qualification:
        value = verify_controller_qualification()
    elif args.write_candidate:
        value = write_matrix_candidate()
    elif args.verify_candidate:
        value = verify_matrix_candidate()
    elif args.write_admission:
        value = write_remainder_admission()
    elif args.verify_admission:
        value = verify_remainder_admission()
    elif args.execute_pending_segment:
        value = execute_pending_segment()
    else:
        value = remainder_status()
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
