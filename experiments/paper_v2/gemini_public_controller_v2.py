"""使用精确 JSON 输出承诺的版本化 Gemini 公开矩阵控制器。

保障多工具调用场景下参数解析的严密性与确定性。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Mapping

import experiments.paper_v2.gemini_public_controller_v1 as v1
from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.experiment_closeout_freeze_v1 import GEMINI_MODEL_ID
from experiments.paper_v2.gemini_json_client_v1 import (
    DEFAULT_QUALIFICATION as JSON_QUALIFICATION,
    GeminiJsonOfficialClient,
    GeminiJsonTracedProviderClient,
    verify_qualification as verify_json_qualification,
)
from experiments.paper_v2.official_provider_executor import (
    ProviderBudgetState,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_ROOT = PROJECT_ROOT / "protocols/paper_upgrade_v2"
DEFAULT_QUALIFICATION = (
    PROTOCOL_ROOT / "gemini_public_controller_qualification_v2.json"
)
DEFAULT_CANDIDATE = PROTOCOL_ROOT / "gemini_public_canary_candidate_v2.json"
DEFAULT_ADMISSION = (
    PROTOCOL_ROOT / "admissions/gemini_public_canary_admission_v2.json"
)
SUPERSESSION_REVIEW = (
    PROTOCOL_ROOT / "gemini_public_canary_v1_supersession_review.json"
)
RUN_ID = "paper-v2-public-gemini-canary-v2-20260802"
OUTPUT_ROOT = (
    PROJECT_ROOT
    / "outputs/paper_upgrade_v2/formal_public/gemini/public-v2-canary"
)
CANARY_SIZE = v1.CANARY_SIZE
OWNER_APPROVAL_STATEMENT = (
    "The project owner approved the frozen Gemini 3.6 Flash public canary "
    "and pending-only continuation under the official free tier, USD 0 paid "
    "ceiling, zero automatic retries, no provider tools, and no real effects."
)
OWNER_STATEMENT_SHA256 = hashlib.sha256(
    OWNER_APPROVAL_STATEMENT.encode("utf-8")
).hexdigest()


class GeminiPublicControllerV2Error(RuntimeError):
    """当版本化 Gemini 金丝雀无法保持安全闭合时抛出的异常。"""


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manifest_sha(value: Mapping[str, Any]) -> str:
    return sha256_canonical_json(
        {key: item for key, item in value.items() if key != "manifest_sha256"}
    )


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise GeminiPublicControllerV2Error(f"{path}: expected object")
    return value


def build_v1_supersession_review() -> dict[str, Any]:
    """封存未执行的 v1 准入，且不删除历史文件。"""

    candidate = v1.verify_canary_candidate()
    admission = v1.validate_canary_admission(
        v1._read_json(v1.DEFAULT_ADMISSION)
    )
    files = []
    if v1.OUTPUT_ROOT.exists():
        files = [
            path
            for path in v1.OUTPUT_ROOT.rglob("*")
            if path.is_file() and path.stat().st_size
        ]
    if files:
        raise GeminiPublicControllerV2Error(
            "Gemini v1 canary has evidence and cannot be superseded as unexecuted"
        )
    core = {
        "schema_version": "m3-paper-v2-gemini-public-supersession-review-1.0",
        "status": "v1_superseded_before_execution",
        "reason": "json_output_control_missing_from_payload_commitment",
        "v1_run_id": v1.RUN_ID,
        "v1_candidate_manifest_sha256": candidate["manifest_sha256"],
        "v1_candidate_file_sha256": _sha256_file(v1.DEFAULT_CANDIDATE),
        "v1_admission_manifest_sha256": admission["manifest_sha256"],
        "v1_admission_file_sha256": _sha256_file(v1.DEFAULT_ADMISSION),
        "v1_nonempty_output_files": 0,
        "network_calls_made": 0,
        "provider_calls_made": 0,
        "scientific_outcomes_read": 0,
        "deletion_performed": False,
        "replacement_run_id": RUN_ID,
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def verify_v1_supersession_review() -> dict[str, Any]:
    observed = _read_json(SUPERSESSION_REVIEW)
    expected = build_v1_supersession_review()
    if observed != expected:
        raise GeminiPublicControllerV2Error("Gemini v1 supersession drift")
    return observed


def build_offline_qualification() -> dict[str, Any]:
    base = v1.verify_offline_qualification()
    json_qualification = verify_json_qualification()
    supersession = verify_v1_supersession_review()
    rows = v1._canary_rows()
    core = {
        "schema_version": "m3-paper-v2-gemini-public-controller-qualification-2.0",
        "status": "offline_gemini_json_public_canary_qualified",
        "provider_id": "gemini",
        "model_id": GEMINI_MODEL_ID,
        "plan_manifest_sha256": base["plan_manifest_sha256"],
        "plan_records": base["plan_records"],
        "canary_records": len(rows),
        "canary_work_key_sequence_sha256": sha256_canonical_json(
            [row["work_key"] for row in rows]
        ),
        "base_controller_qualification_sha256": _sha256_file(
            v1.DEFAULT_QUALIFICATION
        ),
        "json_client_qualification_sha256": _sha256_file(JSON_QUALIFICATION),
        "json_payload_sha256": json_qualification[
            "observed_payload_sha256"
        ],
        "vigil_constraint_set_sha256": json_qualification[
            "vigil_constraint_set_sha256"
        ],
        "v1_supersession_manifest_sha256": supersession["manifest_sha256"],
        "controls": copy.deepcopy(base["controls"]),
        "network_calls_made": 0,
        "credentials_read": False,
        "scientific_outcomes_read": 0,
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def write_offline_qualification() -> dict[str, Any]:
    value = build_offline_qualification()
    _write_json(DEFAULT_QUALIFICATION, value)
    return value


def verify_offline_qualification() -> dict[str, Any]:
    observed = _read_json(DEFAULT_QUALIFICATION)
    expected = build_offline_qualification()
    if observed != expected:
        raise GeminiPublicControllerV2Error(
            "Gemini public v2 qualification drift"
        )
    return observed


def canonical_canary_command() -> str:
    return (
        r"F:\robot\Anaconda3\python.exe -m "
        "experiments.paper_v2.gemini_public_controller_v2 "
        "--execute-canary --admission "
        "protocols\\paper_upgrade_v2\\admissions\\"
        "gemini_public_canary_admission_v2.json "
        r"--config config\project.local.env"
    )


def build_canary_candidate() -> dict[str, Any]:
    _, manifest = v1._verify_frozen_plan()
    qualification = verify_offline_qualification()
    rows = v1._canary_rows()
    execution_identity = sha256_canonical_json(
        {
            "schema_version": "m3-paper-v2-gemini-public-canary-identity-2.0",
            "plan_manifest_sha256": manifest["manifest_sha256"],
            "run_id": RUN_ID,
            "work_keys": [row["work_key"] for row in rows],
            "json_client_qualification_sha256": qualification[
                "json_client_qualification_sha256"
            ],
        }
    )
    core = {
        "schema_version": "m3-paper-v2-gemini-public-canary-candidate-2.0",
        "status": "candidate_pending_exact_command_admission",
        "run_id": RUN_ID,
        "execution_identity": execution_identity,
        "provider_id": "gemini",
        "model_id": GEMINI_MODEL_ID,
        "model_role": "second",
        "plan_manifest_sha256": manifest["manifest_sha256"],
        "qualification_sha256": _sha256_file(DEFAULT_QUALIFICATION),
        "canary_records": CANARY_SIZE,
        "canary_source_work_keys": [row["work_key"] for row in rows],
        "canary_work_key_sequence_sha256": sha256_canonical_json(
            [row["work_key"] for row in rows]
        ),
        "output_root": OUTPUT_ROOT.relative_to(PROJECT_ROOT).as_posix(),
        "max_tokens": 512,
        "timeout_seconds": 120.0,
        "controls": copy.deepcopy(qualification["controls"]),
        "exact_command": canonical_canary_command(),
        "result_admission_authorized": False,
        "scientific_outcomes_read": 0,
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def write_canary_candidate() -> dict[str, Any]:
    value = build_canary_candidate()
    _write_json(DEFAULT_CANDIDATE, value)
    return value


def verify_canary_candidate() -> dict[str, Any]:
    observed = _read_json(DEFAULT_CANDIDATE)
    expected = build_canary_candidate()
    if observed != expected:
        raise GeminiPublicControllerV2Error("Gemini public v2 candidate drift")
    return observed


def build_canary_admission(
    *, owner_statement_sha256: str, approved_at: str
) -> dict[str, Any]:
    candidate = verify_canary_candidate()
    if owner_statement_sha256 != OWNER_STATEMENT_SHA256:
        raise GeminiPublicControllerV2Error(
            "Gemini public v2 owner authorization digest drift"
        )
    core = {
        "schema_version": "m3-paper-v2-gemini-public-canary-admission-2.0",
        "status": "activated_for_one_technical_canary",
        "approved_at": approved_at,
        "candidate_manifest_sha256": candidate["manifest_sha256"],
        "owner_statement_sha256": owner_statement_sha256,
        "exact_command": candidate["exact_command"],
        "exact_command_sha256": hashlib.sha256(
            candidate["exact_command"].encode("utf-8")
        ).hexdigest(),
        "run_id": candidate["run_id"],
        "execution_identity": candidate["execution_identity"],
        "canary_records": candidate["canary_records"],
        "canary_work_key_sequence_sha256": candidate[
            "canary_work_key_sequence_sha256"
        ],
        "authorization": {
            "canary_execution_authorized": True,
            "matrix_continuation_authorized": False,
            "result_admission_authorized": False,
        },
        "controls": copy.deepcopy(candidate["controls"]),
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def write_canary_admission(
    *, owner_statement_sha256: str, approved_at: str
) -> dict[str, Any]:
    value = build_canary_admission(
        owner_statement_sha256=owner_statement_sha256,
        approved_at=approved_at,
    )
    _write_json(DEFAULT_ADMISSION, value)
    return value


def validate_canary_admission(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise GeminiPublicControllerV2Error("Gemini v2 admission must be object")
    expected = build_canary_admission(
        owner_statement_sha256=str(value.get("owner_statement_sha256", "")),
        approved_at=str(value.get("approved_at", "")),
    )
    if dict(value) != expected:
        raise GeminiPublicControllerV2Error("Gemini v2 admission drift")
    controls = value["controls"]
    if (
        controls["billing_tier"] != "free"
        or controls["paid_ceiling_usd"] != 0.0
        or controls["automatic_retries"] != 0
        or controls["provider_managed_tools_enabled"] is not False
        or controls["external_effects_enabled"] is not False
    ):
        raise GeminiPublicControllerV2Error("Gemini v2 controls widened")
    return copy.deepcopy(dict(value))


def _permit(admission_path: Path) -> v1.GeminiPublicPermit:
    candidate = verify_canary_candidate()
    admission = validate_canary_admission(_read_json(admission_path))
    identity = str(candidate["execution_identity"])
    rows = v1._canary_rows()
    for row in rows:
        row["execution_identity"] = identity
    return v1.GeminiPublicPermit(
        run_id=RUN_ID,
        execution_identity=identity,
        work_items=tuple(rows),
        output_root=OUTPUT_ROOT,
        record_ledger_path=OUTPUT_ROOT / "experiment_records_v1.jsonl",
        attempt_ledger_path=OUTPUT_ROOT / "attempt_events_v1.jsonl",
        call_ledger_path=OUTPUT_ROOT / "provider_call_events_v1.jsonl",
        trace_root=OUTPUT_ROOT / "provider_traces",
        admission_file_sha256=_sha256_file(admission_path),
        max_tokens=int(candidate["max_tokens"]),
        timeout_seconds=float(candidate["timeout_seconds"]),
        candidate=copy.deepcopy(candidate),
        admission=copy.deepcopy(admission),
    )


def _build_dispatcher(
    permit: v1.GeminiPublicPermit,
    *,
    api_key: str,
    policy: Mapping[str, Any],
    call_sink: Any,
    budget_state: ProviderBudgetState,
) -> Any:
    return v1._build_dispatcher(
        permit,
        api_key=api_key,
        policy=policy,
        call_sink=call_sink,
        budget_state=budget_state,
        official_client_class=GeminiJsonOfficialClient,
        traced_client_class=GeminiJsonTracedProviderClient,
    )


def execute_canary(
    *,
    admission_path: Path,
    config_path: Path | None = None,
    credential_loader: Callable[[], Mapping[str, str]] | None = None,
    dispatcher_factory: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    if (
        SUPERSESSION_REVIEW.with_name(
            "gemini_public_canary_v2_supersession_review.json"
        ).is_file()
    ):
        raise GeminiPublicControllerV2Error(
            "Gemini public-v2 was superseded before execution"
        )
    value = v1.execute_canary(
        admission_path=admission_path,
        config_path=config_path,
        credential_loader=credential_loader,
        dispatcher_factory=dispatcher_factory or _build_dispatcher,
        permit_loader=_permit,
    )
    value["status"] = str(value["status"]).replace(
        "gemini_public_canary", "gemini_public_v2_canary"
    )
    return value


def build_technical_review() -> dict[str, Any]:
    permit = _permit(DEFAULT_ADMISSION)
    state = v1._state(permit)
    records = state["records"]
    bundles = [entry["record"]["provider_trace_bundle"] for entry in records]
    checks = {
        "exact_record_count": len(records) == CANARY_SIZE,
        "all_attempts_terminal": not state["attempt_status"]["open_work_keys"],
        "all_call_attempts_terminal": state["call_status"]["open_attempts"] == 0,
        "all_records_formal_candidates": all(
            entry["record"]["result_tier"] == "formal_candidate"
            for entry in records
        ),
        "all_trace_bundles_complete": all(
            bundle["bundle_status"] == "completed"
            and bundle["result_tier_ceiling"] == "formal_candidate"
            and bundle["provider_id"] == "gemini"
            and bundle["model_id"] == GEMINI_MODEL_ID
            for bundle in bundles
        ),
        "all_free_tier_zero_charge": all(
            bundle["usage_summary"]["billing_tier"] == "free"
            and bundle["usage_summary"]["charged_usd"] == 0.0
            and bundle["usage_summary"]["paid_ceiling_usd"] == 0.0
            for bundle in bundles
        ),
        "all_pretransport_payload_bindings_complete": all(
            {
                row["event"]["commitment"]["payload_sha256"]
                for row in bundle["trace_rows"]
                if row["event"]["event_type"] == "started"
            }
            == {
                attestation["payload_sha256"]
                for attestation in bundle["activated_attestations"]
            }
            for bundle in bundles
        )
        if records
        else False,
        "all_effects_isolated": all(
            entry["record"]["provider_safety_receipt"]["evidence"][
                "external_connectors_enabled"
            ]
            is False
            for entry in records
        ),
    }
    passed = all(checks.values())
    return {
        "schema_version": "m3-paper-v2-gemini-public-technical-review-2.0",
        "generated_at": v1._now(),
        "status": (
            "gemini_public_v2_canary_technical_gate_pass"
            if passed
            else "gemini_public_v2_canary_technical_gate_fail"
        ),
        "run_id": permit.run_id,
        "expected_records": CANARY_SIZE,
        "observed_records": len(records),
        "provider_calls_completed": state["call_status"]["completed_calls"],
        "checks": checks,
        "matrix_continuation_eligible": passed,
        "review_boundary": {
            "scientific_outcomes_accessed": False,
            "unsafe_effect_aggregated": False,
            "task_completion_aggregated": False,
            "condition_effects_compared": False,
            "result_admission_authorized": False,
        },
    }


def write_technical_review() -> dict[str, Any]:
    value = build_technical_review()
    _write_json(OUTPUT_ROOT / "technical_canary_review_v2.json", value)
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--write-supersession", action="store_true")
    actions.add_argument("--write-qualification", action="store_true")
    actions.add_argument("--verify-qualification", action="store_true")
    actions.add_argument("--write-candidate", action="store_true")
    actions.add_argument("--verify-candidate", action="store_true")
    actions.add_argument("--write-admission", action="store_true")
    actions.add_argument("--verify-admission", action="store_true")
    actions.add_argument("--execute-canary", action="store_true")
    actions.add_argument("--write-technical-review", action="store_true")
    parser.add_argument("--admission", type=Path, default=DEFAULT_ADMISSION)
    parser.add_argument("--owner-statement-sha256")
    parser.add_argument("--approved-at")
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()
    if args.write_supersession:
        value = build_v1_supersession_review()
        _write_json(SUPERSESSION_REVIEW, value)
    elif args.write_qualification:
        value = write_offline_qualification()
    elif args.verify_qualification:
        value = verify_offline_qualification()
    elif args.write_candidate:
        value = write_canary_candidate()
    elif args.verify_candidate:
        value = verify_canary_candidate()
    elif args.write_admission:
        if not args.owner_statement_sha256 or not args.approved_at:
            parser.error(
                "--write-admission requires --owner-statement-sha256 and --approved-at"
            )
        value = write_canary_admission(
            owner_statement_sha256=args.owner_statement_sha256,
            approved_at=args.approved_at,
        )
    elif args.verify_admission:
        value = validate_canary_admission(_read_json(args.admission))
    elif args.execute_canary:
        value = execute_canary(
            admission_path=args.admission,
            config_path=args.config,
        )
    else:
        value = write_technical_review()
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
