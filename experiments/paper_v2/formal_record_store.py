"""面向 paper-v2 中等规模研究的仅追加、内容最小化实验记录存储器。

高效存储实验元数据与关键判定结果，自动计算每条记录的 SHA-256 校验和。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from experiments.paper_v2.contracts import (
    OPERATIONAL_FAILURE_STATUSES,
    canonical_json_bytes,
    sha256_canonical_json,
    validate_experiment_record,
)
from experiments.paper_v2.formal_condition_executors import (
    FORBIDDEN_EVENT_STORAGE_KEYS,
    ConditionProfile,
    OnlineExecutorContext,
    build_condition_dispatcher,
)
from experiments.paper_v2.medium_runtime import (
    CORE_CONDITIONS,
    DEFAULT_V2_PLAN,
    assemble_experiment_record,
    reconstruct_initial_online_state,
)
from experiments.paper_v2.official_provider_executor import (
    SECRET_TEXT_PATTERNS,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/formal_record_store_qualification_v1.json"
)
QUALIFICATION_RECORDED_AT = "2026-07-23T23:20:00+08:00"
ENTRY_SCHEMA_VERSION = "m3-paper-v2-formal-record-entry-1.0"
ENTRY_FIELDS = frozenset(
    {
        "schema_version",
        "ledger_sequence",
        "execution_identity",
        "work_key",
        "run_id",
        "record_id",
        "record_sha256",
        "runtime_visibility_events_sha256",
        "record",
        "runtime_visibility_events",
        "entry_sha256",
    }
)
SANITIZED_EVENT_FIELDS = frozenset(
    {
        "step",
        "parse_ok",
        "parse_error_code",
        "action_proposal",
        "guard_decision",
        "controller_evidence",
        "execution_attempted",
        "execution_succeeded",
        "response_text_sha256",
        "response_text_bytes",
        "observation_sha256",
        "observation_bytes",
        "provider_receipt_sha256",
    }
)
FORBIDDEN_LEDGER_KEYS = FORBIDDEN_EVENT_STORAGE_KEYS | frozenset(
    {
        "authorization_header",
        "credential",
        "credentials",
        "raw_event",
        "raw_trace",
        "response",
        "secret",
    }
)


class FormalRecordStoreError(ValueError):
    """当持久化的实验记录链违反其契约时抛出的异常。"""


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _assert_sha256(value: Any, *, path: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise FormalRecordStoreError(f"{path} must be lowercase SHA-256")
    return value


def _assert_no_secret_text(value: str, *, path: str) -> None:
    for pattern in SECRET_TEXT_PATTERNS:
        if pattern.search(value):
            raise FormalRecordStoreError(
                f"{path}: credential-like content cannot be persisted"
            )


def validate_persisted_ledger_value(
    value: Any,
    *,
    path: str = "$",
) -> None:
    """递归拒绝原始内容键和类机密字符串。"""

    if isinstance(value, Mapping):
        for key, child in value.items():
            lowered = str(key).casefold()
            if lowered in FORBIDDEN_LEDGER_KEYS:
                raise FormalRecordStoreError(
                    f"{path}.{key}: forbidden persisted ledger field"
                )
            validate_persisted_ledger_value(child, path=f"{path}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            validate_persisted_ledger_value(
                child,
                path=f"{path}[{index}]",
            )
        return
    if isinstance(value, str):
        _assert_no_secret_text(value, path=path)


def _validate_sanitized_events(events: Any) -> list[dict[str, Any]]:
    if not isinstance(events, list) or not events:
        raise FormalRecordStoreError(
            "runtime_visibility_events must be a non-empty list"
        )
    normalized: list[dict[str, Any]] = []
    for index, event in enumerate(events, start=1):
        if not isinstance(event, Mapping):
            raise FormalRecordStoreError(
                f"runtime event {index} must be an object"
            )
        if set(event) != SANITIZED_EVENT_FIELDS:
            raise FormalRecordStoreError(
                f"runtime event {index} fields do not match the sanitized contract"
            )
        row = dict(event)
        if row.get("step") != index:
            raise FormalRecordStoreError(
                "runtime event steps must be contiguous from one"
            )
        for boolean_field in (
            "parse_ok",
            "execution_attempted",
            "execution_succeeded",
        ):
            if not isinstance(row.get(boolean_field), bool):
                raise FormalRecordStoreError(
                    f"runtime event {index}.{boolean_field} must be boolean"
                )
        proposal = row.get("action_proposal")
        if not isinstance(proposal, Mapping) or set(proposal) != {
            "tool",
            "arguments",
            "arguments_sha256",
        }:
            raise FormalRecordStoreError(
                f"runtime event {index} action proposal is malformed"
            )
        if not isinstance(proposal.get("tool"), str) or not proposal["tool"]:
            raise FormalRecordStoreError(
                f"runtime event {index} tool is required"
            )
        arguments = proposal.get("arguments")
        if not isinstance(arguments, Mapping):
            raise FormalRecordStoreError(
                f"runtime event {index} arguments must be an object"
            )
        if proposal.get("arguments_sha256") != sha256_canonical_json(arguments):
            raise FormalRecordStoreError(
                f"runtime event {index} argument hash drift"
            )
        decision = row.get("guard_decision")
        if not isinstance(decision, Mapping) or set(decision) != {
            "decision",
            "reason_code",
            "violated_constraints",
        }:
            raise FormalRecordStoreError(
                f"runtime event {index} guard decision is malformed"
            )
        if decision.get("decision") not in {"ALLOW", "ASK", "DENY"}:
            raise FormalRecordStoreError(
                f"runtime event {index} guard decision is unsupported"
            )
        constraints = decision.get("violated_constraints")
        if not isinstance(constraints, list) or any(
            not isinstance(value, str) for value in constraints
        ):
            raise FormalRecordStoreError(
                f"runtime event {index} violated constraints must be text"
            )
        controller = row.get("controller_evidence")
        if not isinstance(controller, Mapping) or set(controller) != {
            "controller_id",
            "decision",
            "score",
            "threshold",
            "scan_count",
            "source_sha256",
            "details_sha256",
        }:
            raise FormalRecordStoreError(
                f"runtime event {index} controller evidence is malformed"
            )
        if (
            not isinstance(controller.get("controller_id"), str)
            or not controller["controller_id"]
        ):
            raise FormalRecordStoreError(
                f"runtime event {index} controller ID is required"
            )
        if controller.get("decision") != decision.get("decision"):
            raise FormalRecordStoreError(
                f"runtime event {index} controller decision drift"
            )
        for numeric_field in ("score", "threshold"):
            numeric = controller.get(numeric_field)
            if numeric is not None and (
                isinstance(numeric, bool)
                or not isinstance(numeric, (int, float))
            ):
                raise FormalRecordStoreError(
                    f"runtime event {index} controller {numeric_field} is invalid"
                )
        scan_count = controller.get("scan_count")
        if (
            isinstance(scan_count, bool)
            or not isinstance(scan_count, int)
            or scan_count < 0
        ):
            raise FormalRecordStoreError(
                f"runtime event {index} controller scan count is invalid"
            )
        source_digest = controller.get("source_sha256")
        if source_digest is not None:
            _assert_sha256(
                source_digest,
                path=f"runtime event {index}.controller_evidence.source_sha256",
            )
        _assert_sha256(
            controller.get("details_sha256"),
            path=f"runtime event {index}.controller_evidence.details_sha256",
        )
        _assert_sha256(
            row.get("response_text_sha256"),
            path=f"runtime event {index}.response_text_sha256",
        )
        _assert_sha256(
            row.get("observation_sha256"),
            path=f"runtime event {index}.observation_sha256",
        )
        for size_field in ("response_text_bytes", "observation_bytes"):
            size = row.get(size_field)
            if (
                isinstance(size, bool)
                or not isinstance(size, int)
                or size < 0
            ):
                raise FormalRecordStoreError(
                    f"runtime event {index}.{size_field} must be non-negative"
                )
        receipt_digest = row.get("provider_receipt_sha256")
        if receipt_digest is not None:
            _assert_sha256(
                receipt_digest,
                path=f"runtime event {index}.provider_receipt_sha256",
            )
        validate_persisted_ledger_value(
            row,
            path=f"$.runtime_visibility_events[{index - 1}]",
        )
        normalized.append(row)
    return normalized


def _work_item_map(
    work_items: Iterable[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    identities: set[str] = set()
    for item in work_items:
        work_key = item.get("work_key")
        if not isinstance(work_key, str) or not work_key:
            raise FormalRecordStoreError("work item has no work_key")
        if work_key in result:
            raise FormalRecordStoreError("work item set contains duplicate keys")
        result[work_key] = dict(item)
        identity = item.get("execution_identity")
        if not isinstance(identity, str) or not identity:
            raise FormalRecordStoreError("work item has no execution identity")
        identities.add(identity)
    if not result:
        raise FormalRecordStoreError("work item set must not be empty")
    if len(identities) != 1:
        raise FormalRecordStoreError("work item execution identities differ")
    return result


def _validate_record_tier(
    record: Mapping[str, Any],
    *,
    qualification_mode: bool,
) -> None:
    tier = record.get("result_tier")
    status = record.get("operational_status")
    if qualification_mode:
        if tier != "stub":
            raise FormalRecordStoreError(
                "qualification ledger accepts stub records only"
            )
        return
    if tier == "stub":
        raise FormalRecordStoreError(
            "live record ledger cannot persist stub evidence"
        )
    if status in OPERATIONAL_FAILURE_STATUSES:
        if tier not in {"diagnostic", "formal_candidate"}:
            raise FormalRecordStoreError(
                "operational failure must retain diagnostic or formal-candidate evidence"
            )
        return
    if tier != "formal_candidate":
        raise FormalRecordStoreError(
            "completed/refusal live records require formal-candidate evidence"
        )


def _expected_record_id(record: Mapping[str, Any], work_key: str) -> str:
    identity = {
        "run_id": record["run_id"],
        "work_key": work_key,
        "result_tier": record["result_tier"],
        "provider_request_id": record["provider_attestation"].get("request_id"),
        "provider_response_id": record["provider_attestation"].get("response_id"),
    }
    return "record-" + sha256_canonical_json(identity)[:24]


def _entry_without_digest(entry: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in entry.items()
        if key != "entry_sha256"
    }


def _validate_one_entry(
    entry: Mapping[str, Any],
    *,
    expected_sequence: int,
    execution_identity: str,
    run_id: str,
    work_items: Mapping[str, Mapping[str, Any]],
    qualification_mode: bool,
) -> tuple[str, str]:
    if set(entry) != ENTRY_FIELDS:
        raise FormalRecordStoreError(
            f"ledger entry {expected_sequence} fields do not match contract"
        )
    if entry.get("schema_version") != ENTRY_SCHEMA_VERSION:
        raise FormalRecordStoreError(
            f"ledger entry {expected_sequence} schema is unsupported"
        )
    if entry.get("ledger_sequence") != expected_sequence:
        raise FormalRecordStoreError("ledger sequence is not contiguous")
    if entry.get("execution_identity") != execution_identity:
        raise FormalRecordStoreError("ledger execution identity drift")
    if entry.get("run_id") != run_id:
        raise FormalRecordStoreError("ledger run ID drift")
    work_key = entry.get("work_key")
    if work_key not in work_items:
        raise FormalRecordStoreError("ledger references an unknown work key")
    record = entry.get("record")
    events = _validate_sanitized_events(
        entry.get("runtime_visibility_events")
    )
    if not isinstance(record, Mapping):
        raise FormalRecordStoreError("ledger entry record must be an object")
    validate_persisted_ledger_value(entry)
    if entry.get("record_sha256") != sha256_canonical_json(record):
        raise FormalRecordStoreError("experiment record hash drift")
    if entry.get("runtime_visibility_events_sha256") != (
        sha256_canonical_json(events)
    ):
        raise FormalRecordStoreError("runtime event hash drift")
    if entry.get("entry_sha256") != sha256_canonical_json(
        _entry_without_digest(entry)
    ):
        raise FormalRecordStoreError("ledger entry hash drift")

    item = work_items[str(work_key)]
    expected_metadata = {
        "run_id": run_id,
        "case_id": item["case_id"],
        "benchmark_id": item["benchmark"],
        "condition_id": item["condition_id"],
        "evaluation_case_type": item["evaluation_case_type"],
        "authorization_regime": item["authorization_regime"],
    }
    observed_metadata = {
        key: record.get(key) for key in expected_metadata
    }
    if observed_metadata != expected_metadata:
        raise FormalRecordStoreError("experiment record/work-item metadata drift")
    record_id = record.get("record_id")
    if entry.get("record_id") != record_id:
        raise FormalRecordStoreError("ledger record ID drift")
    if record_id != _expected_record_id(record, str(work_key)):
        raise FormalRecordStoreError("experiment record identity drift")
    _validate_record_tier(record, qualification_mode=qualification_mode)
    initial_state = reconstruct_initial_online_state(item)
    projection = {
        "initial_online_state": initial_state,
        "runtime_visibility_events": events,
    }
    validate_experiment_record(record, online_projection=projection)
    return str(work_key), str(record_id)


def validate_record_entries(
    entries: Sequence[Mapping[str, Any]],
    *,
    work_items: Iterable[Mapping[str, Any]],
    execution_identity: str,
    run_id: str,
    qualification_mode: bool = False,
) -> dict[str, Any]:
    """验证完整的终端记录链并返回恢复状态。"""

    if not isinstance(run_id, str) or not run_id:
        raise FormalRecordStoreError("run_id is required")
    by_key = _work_item_map(work_items)
    expected_identity = next(
        iter(item["execution_identity"] for item in by_key.values())
    )
    if execution_identity != expected_identity:
        raise FormalRecordStoreError(
            "requested execution identity does not match frozen work items"
        )
    seen_work_keys: set[str] = set()
    seen_record_ids: set[str] = set()
    status_counts: dict[str, int] = {}
    for sequence, entry in enumerate(entries, start=1):
        if not isinstance(entry, Mapping):
            raise FormalRecordStoreError(
                f"ledger entry {sequence} must be an object"
            )
        work_key, record_id = _validate_one_entry(
            entry,
            expected_sequence=sequence,
            execution_identity=execution_identity,
            run_id=run_id,
            work_items=by_key,
            qualification_mode=qualification_mode,
        )
        if work_key in seen_work_keys:
            raise FormalRecordStoreError("duplicate terminal work record")
        if record_id in seen_record_ids:
            raise FormalRecordStoreError("duplicate experiment record ID")
        seen_work_keys.add(work_key)
        seen_record_ids.add(record_id)
        status = str(entry["record"]["operational_status"])
        status_counts[status] = status_counts.get(status, 0) + 1
    return {
        "entry_count": len(entries),
        "terminal_work_keys": sorted(seen_work_keys),
        "remaining_work_items": len(by_key) - len(seen_work_keys),
        "operational_status_counts": dict(sorted(status_counts.items())),
        "qualification_mode": qualification_mode,
    }


def build_record_entry(
    *,
    work_item: Mapping[str, Any],
    initial_online_state: Mapping[str, Any],
    execution_result: Mapping[str, Any],
    run_id: str,
    ledger_sequence: int,
    qualification_mode: bool = False,
) -> dict[str, Any]:
    """组装单条记录及其脱敏的运行时事件证据包络。"""

    if (
        isinstance(ledger_sequence, bool)
        or not isinstance(ledger_sequence, int)
        or ledger_sequence < 1
    ):
        raise FormalRecordStoreError("ledger_sequence must be positive")
    events = _validate_sanitized_events(
        execution_result.get("runtime_visibility_events")
    )
    validate_persisted_ledger_value(execution_result)
    record = assemble_experiment_record(
        work_item,
        initial_online_state,
        execution_result,
        run_id=run_id,
    )
    _validate_record_tier(record, qualification_mode=qualification_mode)
    core = {
        "schema_version": ENTRY_SCHEMA_VERSION,
        "ledger_sequence": ledger_sequence,
        "execution_identity": work_item["execution_identity"],
        "work_key": work_item["work_key"],
        "run_id": run_id,
        "record_id": record["record_id"],
        "record_sha256": sha256_canonical_json(record),
        "runtime_visibility_events_sha256": sha256_canonical_json(events),
        "record": record,
        "runtime_visibility_events": events,
    }
    entry = {
        **core,
        "entry_sha256": sha256_canonical_json(core),
    }
    validate_persisted_ledger_value(entry)
    return entry


def load_record_entries(path: Path) -> list[dict[str, Any]]:
    """加载仅追加的 JSONL 账本，拒绝空白或畸形行。"""

    if not path.exists():
        return []
    entries: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                if not line.strip():
                    raise FormalRecordStoreError(
                        f"{path}:{line_number}: blank ledger row"
                    )
                try:
                    value = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise FormalRecordStoreError(
                        f"{path}:{line_number}: malformed JSON"
                    ) from exc
                if not isinstance(value, dict):
                    raise FormalRecordStoreError(
                        f"{path}:{line_number}: expected a JSON object"
                    )
                entries.append(value)
    except UnicodeDecodeError as exc:
        raise FormalRecordStoreError(
            f"{path}: ledger is not valid UTF-8"
        ) from exc
    return entries


def append_record_entry(
    path: Path,
    *,
    work_items: Sequence[Mapping[str, Any]],
    work_item: Mapping[str, Any],
    initial_online_state: Mapping[str, Any],
    execution_result: Mapping[str, Any],
    execution_identity: str,
    run_id: str,
    qualification_mode: bool = False,
) -> dict[str, Any]:
    """验证完整的候选账本，然后追加并 fsync 单行。"""

    prior = load_record_entries(path)
    validate_record_entries(
        prior,
        work_items=work_items,
        execution_identity=execution_identity,
        run_id=run_id,
        qualification_mode=qualification_mode,
    )
    entry = build_record_entry(
        work_item=work_item,
        initial_online_state=initial_online_state,
        execution_result=execution_result,
        run_id=run_id,
        ledger_sequence=len(prior) + 1,
        qualification_mode=qualification_mode,
    )
    candidate = [*prior, entry]
    summary = validate_record_entries(
        candidate,
        work_items=work_items,
        execution_identity=execution_identity,
        run_id=run_id,
        qualification_mode=qualification_mode,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(canonical_json_bytes(entry).decode("utf-8") + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    return summary


def pending_record_work_items(
    work_items: Sequence[Mapping[str, Any]],
    entries: Sequence[Mapping[str, Any]],
    *,
    execution_identity: str,
    run_id: str,
    qualification_mode: bool = False,
) -> list[dict[str, Any]]:
    summary = validate_record_entries(
        entries,
        work_items=work_items,
        execution_identity=execution_identity,
        run_id=run_id,
        qualification_mode=qualification_mode,
    )
    terminal = set(summary["terminal_work_keys"])
    return [
        dict(item)
        for item in work_items
        if item["work_key"] not in terminal
    ]


def _load_plan(path: Path = DEFAULT_V2_PLAN) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise FormalRecordStoreError(
                f"{path}:{line_number}: expected a JSON object"
            )
        rows.append(value)
    return rows


class _QualificationRuntime:
    def execute(
        self,
        context: OnlineExecutorContext,
        profile: ConditionProfile,
    ) -> Mapping[str, Any]:
        del context, profile
        return {
            "events": [
                {
                    "step": 1,
                    "parse_ok": True,
                    "parse_error_code": None,
                    "tool": "final",
                    "arguments": {"answer": "SAFE"},
                    "decision": "ALLOW",
                    "reason_code": "offline_record_store_qualification",
                    "violated_constraints": [],
                    "execution_attempted": True,
                    "execution_succeeded": True,
                    "response_text": "RAW_RESPONSE_MUST_NOT_PERSIST",
                    "observation": {
                        "detail": "RAW_OBSERVATION_MUST_NOT_PERSIST"
                    },
                    "provider_receipt_sha256": None,
                }
            ],
            "operational_status": "completed",
            "result_tier": "stub",
            "recorded_at": QUALIFICATION_RECORDED_AT,
        }


class _QualificationEvaluator:
    def evaluate(
        self,
        work_item: Mapping[str, Any],
        raw_trace: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        del work_item, raw_trace
        return {"unsafe_effect": False, "task_completion": False}


def build_record_store_qualification() -> dict[str, Any]:
    """在临时目录中以零调用演练磁盘追加/恢复。"""

    work_items = _load_plan()
    representatives: dict[tuple[str, str], dict[str, Any]] = {}
    for item in work_items:
        key = (str(item["benchmark"]), str(item["condition_id"]))
        representatives.setdefault(key, item)
    expected_pairs = {
        (benchmark, condition)
        for benchmark in ("m3-v2", "agentdojo-v1")
        for condition in CORE_CONDITIONS
    }
    if set(representatives) != expected_pairs:
        raise FormalRecordStoreError(
            "medium plan does not cover every benchmark/condition pair"
        )
    execution_identity = str(work_items[0]["execution_identity"])
    run_id = "offline-record-store-qualification-not-scientific"
    dispatcher = build_condition_dispatcher(
        runtime=_QualificationRuntime(),
        evaluator=_QualificationEvaluator(),
    )
    raw_markers_absent = False
    final_entries: list[dict[str, Any]] = []
    remaining = len(work_items)
    ledger_path: Path
    with tempfile.TemporaryDirectory(
        prefix="m3-paper-v2-record-store-"
    ) as temp_root:
        ledger_path = Path(temp_root) / "qualification_records.jsonl"
        for key in sorted(representatives):
            item = representatives[key]
            state = reconstruct_initial_online_state(item)
            result = dispatcher.execute(item, state)
            append_record_entry(
                ledger_path,
                work_items=work_items,
                work_item=item,
                initial_online_state=state,
                execution_result=result,
                execution_identity=execution_identity,
                run_id=run_id,
                qualification_mode=True,
            )
        rendered = ledger_path.read_text(encoding="utf-8")
        raw_markers_absent = all(
            marker not in rendered
            for marker in (
                "RAW_RESPONSE_MUST_NOT_PERSIST",
                "RAW_OBSERVATION_MUST_NOT_PERSIST",
            )
        )
        if not raw_markers_absent:
            raise FormalRecordStoreError(
                "raw qualification content entered the disk ledger"
            )
        final_entries = load_record_entries(ledger_path)
        summary = validate_record_entries(
            final_entries,
            work_items=work_items,
            execution_identity=execution_identity,
            run_id=run_id,
            qualification_mode=True,
        )
        remaining = len(
            pending_record_work_items(
                work_items,
                final_entries,
                execution_identity=execution_identity,
                run_id=run_id,
                qualification_mode=True,
            )
        )
        ledger_sha256 = _sha256_bytes(ledger_path.read_bytes())
    cleanup_verified = not ledger_path.exists()
    if not cleanup_verified:
        raise FormalRecordStoreError(
            "transient qualification ledger was not cleaned up"
        )
    report = {
        "schema_version": (
            "m3-paper-v2-formal-record-store-qualification-1.0"
        ),
        "generated_at": QUALIFICATION_RECORDED_AT,
        "status": (
            "offline_persistence_path_qualified_live_records_pending"
        ),
        "network_calls_made": 0,
        "model_calls_made": 0,
        "credentials_read": False,
        "project_experiment_records_persisted": 0,
        "formal_results_created": 0,
        "transient_qualification_entries_written": len(final_entries),
        "qualified_benchmark_condition_pairs": len(final_entries),
        "complete_chain_revalidated_after_each_append": True,
        "fsync_after_each_append": True,
        "transient_cleanup_verified": cleanup_verified,
        "raw_content_markers_absent": raw_markers_absent,
        "ledger_sha256": ledger_sha256,
        "record_set_sha256": sha256_canonical_json(
            [entry["record_sha256"] for entry in final_entries]
        ),
        "runtime_event_set_sha256": sha256_canonical_json(
            [
                entry["runtime_visibility_events_sha256"]
                for entry in final_entries
            ]
        ),
        "recovery_summary": summary,
        "remaining_full_plan_work_items": remaining,
        "persistence_contract": {
            "format": "append_only_jsonl",
            "successful_live_result_tier": "formal_candidate_only",
            "operational_failure_tiers": [
                "diagnostic",
                "formal_candidate",
            ],
            "stub_policy": "explicit_qualification_mode_only",
            "duplicate_terminal_work": "reject",
            "identity_or_run_drift": "reject",
            "corrupt_or_truncated_json": "reject",
            "raw_content_or_credential_pattern": "reject",
            "runtime_events": "sanitized_action_decision_and_hash_evidence",
        },
        "live_persistence_path_qualified": False,
        "interpretation": {
            "supported": [
                "The append-only disk path revalidates the complete ledger before every append and after recovery.",
                "Twelve benchmark-condition stub entries survive disk round-trip without raw response or observation content.",
                "No transient qualification file remains after the qualification scope exits.",
            ],
            "not_supported": [
                "Any live provider or baseline dependency execution.",
                "Any formal experiment record, effect estimate or model-quality conclusion.",
                "Formal medium-matrix execution authorization.",
            ],
        },
    }
    validate_persisted_ledger_value(report)
    return report


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise FormalRecordStoreError(f"{path}: expected a JSON object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    output = (
        args.output
        if args.output.is_absolute()
        else PROJECT_ROOT / args.output
    )
    current = build_record_store_qualification()
    if args.verify_only:
        if _load_json(output) != current:
            raise FormalRecordStoreError(
                f"{output}: frozen record-store qualification does not reproduce"
            )
        print(
            json.dumps(
                {
                    "status": "verified",
                    "transient_entries": current[
                        "transient_qualification_entries_written"
                    ],
                    "project_records": 0,
                    "network_calls_made": 0,
                },
                sort_keys=True,
            )
        )
        return 0
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(current, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
