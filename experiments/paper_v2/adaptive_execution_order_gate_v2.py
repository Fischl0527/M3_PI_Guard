"""Zero-call supersession and predecessor gate for the closeout adaptive panel.

The existing Pro-50 and Flash-50 v1 candidates/admissions are immutable
historical artifacts.  They were never started, but their admissions no longer
bind their current candidates and they do not encode the closeout-wide stage
order.  This module seals those exact bytes and provides the fail-closed gate
that every replacement candidate and admission must use.

This module has no provider client, credential loader, or execution command.
It can only build/verify the order review and validate hash-locked technical
reviews/candidate prerequisites.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from experiments.paper_v2.contracts import (
    canonical_json_bytes,
    sha256_canonical_json,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_ROOT = PROJECT_ROOT / "protocols/paper_upgrade_v2"
REVIEW_PATH = PROTOCOL_ROOT / "adaptive_execution_order_supersession_v2.json"
SCHEMA_VERSION = "m3-paper-v2-adaptive-execution-order-supersession-2.0"

STAGE_ORDER: tuple[dict[str, Any], ...] = (
    {
        "index": 0,
        "stage": "pro_50",
        "predecessor": None,
        "provider_id": "deepseek",
        "model_role": "primary",
        "target_budget": 50,
    },
    {
        "index": 1,
        "stage": "pro_200",
        "predecessor": "pro_50",
        "provider_id": "deepseek",
        "model_role": "primary",
        "target_budget": 200,
    },
    {
        "index": 2,
        "stage": "pro_500",
        "predecessor": "pro_200",
        "provider_id": "deepseek",
        "model_role": "primary",
        "target_budget": 500,
    },
    {
        "index": 3,
        "stage": "pro_hardest_2000",
        "predecessor": "pro_500",
        "provider_id": "deepseek",
        "model_role": "primary",
        "target_budget": 2000,
    },
    {
        "index": 4,
        "stage": "flash_50",
        "predecessor": "pro_hardest_2000",
        "provider_id": "deepseek",
        "model_role": "second",
        "target_budget": 50,
    },
    {
        "index": 5,
        "stage": "flash_200",
        "predecessor": "flash_50",
        "provider_id": "deepseek",
        "model_role": "second",
        "target_budget": 200,
    },
    {
        "index": 6,
        "stage": "gemini_day_0",
        "predecessor": "flash_200",
        "provider_id": "gemini",
        "model_role": "second",
        "target_budget": "50_then_200",
    },
)

EXPECTED_V1_ASSET_LOCKS: dict[str, dict[str, dict[str, Any]]] = {
    "pro_50": {
        "candidate": {
            "path": "protocols/paper_upgrade_v2/adaptive_formal_pro_50_candidate_v1.json",
            "bytes": 2715,
            "sha256": "f38bc56040f1236cfa091d005858cb785f3e7b7fb6d34ae4cd0a767ad4f13120",
        },
        "admission": {
            "path": "protocols/paper_upgrade_v2/admissions/adaptive_formal_pro_50_admission_v1.json",
            "bytes": 1758,
            "sha256": "813ab74e105aa7abd99472beaf24ec80934037651c4c19bc26aee153dfa6bc3a",
        },
    },
    "flash_50": {
        "candidate": {
            "path": "protocols/paper_upgrade_v2/adaptive_formal_flash_50_candidate_v1.json",
            "bytes": 9440,
            "sha256": "55c7520b66bc7c566de7e231b6d806ce64c145cec9eaef61a633ab7a24c9dc64",
        },
        "admission": {
            "path": "protocols/paper_upgrade_v2/admissions/adaptive_formal_flash_50_admission_v1.json",
            "bytes": 1601,
            "sha256": "02af94e1f7580289041113440301cc79a54aa219a972f4502d138c5f693d2459",
        },
    },
}

EXPECTED_V1_OUTPUT_ROOTS = {
    "pro_50": (
        "outputs/paper_upgrade_v2/adaptive_formal_pro/"
        "pro_50-2d339b969d0616a8092968738d247ce5e062ef16f1f1c35ff8e976b2fa9cb257"
    ),
    "flash_50": (
        "outputs/paper_upgrade_v2/adaptive_formal_second/deepseek_flash/"
        "flash_50-12cd0e17781723ac31e720403624eaa1a84bcd3dd371af626d5d7ea2f6c077fc"
    ),
}

EXPECTED_REVIEW_CONTRACTS = {
    "pro_50": (
        "m3-paper-v2-adaptive-formal-pro-review-1.0",
        "adaptive_formal_stage_technical_gate_pass",
    ),
    "pro_200": (
        "m3-paper-v2-adaptive-formal-pro-review-1.0",
        "adaptive_formal_stage_technical_gate_pass",
    ),
    "pro_500": (
        "m3-paper-v2-adaptive-formal-pro-review-1.0",
        "adaptive_formal_stage_technical_gate_pass",
    ),
    "pro_hardest_2000": (
        "m3-paper-v2-adaptive-formal-pro-review-1.0",
        "adaptive_formal_stage_technical_gate_pass",
    ),
    "flash_50": (
        "m3-paper-v2-adaptive-formal-deepseek-flash-review-1.0",
        "adaptive_formal_flash_stage_technical_gate_pass",
    ),
    "flash_200": (
        "m3-paper-v2-adaptive-formal-deepseek-flash-review-1.0",
        "adaptive_formal_flash_stage_technical_gate_pass",
    ),
}

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class AdaptiveExecutionOrderGateV2Error(ValueError):
    """Raised when adaptive supersession or predecessor evidence drifts."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest_sha(value: Mapping[str, Any]) -> str:
    return sha256_canonical_json(
        {key: child for key, child in value.items() if key != "manifest_sha256"}
    )


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError as exc:
        raise AdaptiveExecutionOrderGateV2Error(
            "adaptive evidence path escapes project"
        ) from exc


def _resolve_project_path(raw: Any) -> Path:
    if not isinstance(raw, str) or not raw:
        raise AdaptiveExecutionOrderGateV2Error("adaptive evidence path missing")
    candidate = Path(raw)
    path = candidate.resolve() if candidate.is_absolute() else (PROJECT_ROOT / candidate).resolve()
    try:
        path.relative_to(PROJECT_ROOT.resolve())
    except ValueError as exc:
        raise AdaptiveExecutionOrderGateV2Error(
            "adaptive evidence path escapes project"
        ) from exc
    return path


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AdaptiveExecutionOrderGateV2Error(f"{path}: invalid JSON") from exc
    if not isinstance(value, dict):
        raise AdaptiveExecutionOrderGateV2Error(f"{path}: expected object")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value) + b"\n")


def _validate_literal_file_lock(lock: Mapping[str, Any]) -> Path:
    path = _resolve_project_path(lock.get("path"))
    size = lock.get("bytes")
    digest = lock.get("sha256")
    if (
        isinstance(size, bool)
        or not isinstance(size, int)
        or size < 1
        or not isinstance(digest, str)
        or not _HEX64.fullmatch(digest)
        or not path.is_file()
        or path.stat().st_size != size
        or _sha256_file(path) != digest
    ):
        raise AdaptiveExecutionOrderGateV2Error(
            f"hash-locked adaptive artifact drift: {path}"
        )
    return path


def validate_stage_order(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise AdaptiveExecutionOrderGateV2Error("adaptive stage order missing")
    observed = [dict(row) for row in value if isinstance(row, Mapping)]
    expected = [copy.deepcopy(row) for row in STAGE_ORDER]
    if len(observed) != len(value) or observed != expected:
        raise AdaptiveExecutionOrderGateV2Error("adaptive stage order drift")
    for index, row in enumerate(observed):
        if row["index"] != index:
            raise AdaptiveExecutionOrderGateV2Error("adaptive order index drift")
        expected_predecessor = None if index == 0 else observed[index - 1]["stage"]
        if row["predecessor"] != expected_predecessor:
            raise AdaptiveExecutionOrderGateV2Error(
                "adaptive predecessor chain is not contiguous"
            )
    if observed[-1] != {
        "index": 6,
        "stage": "gemini_day_0",
        "predecessor": "flash_200",
        "provider_id": "gemini",
        "model_role": "second",
        "target_budget": "50_then_200",
    }:
        raise AdaptiveExecutionOrderGateV2Error(
            "Gemini day-0 predecessor must be Flash-200"
        )
    return observed


def predecessor_for(stage: str) -> str | None:
    validate_stage_order(STAGE_ORDER)
    for row in STAGE_ORDER:
        if row["stage"] == stage:
            predecessor = row["predecessor"]
            return None if predecessor is None else str(predecessor)
    raise AdaptiveExecutionOrderGateV2Error(f"unknown adaptive stage: {stage}")


def _expected_absence_rows(output_root: str) -> list[dict[str, Any]]:
    children = (
        ("output_root", ""),
        ("query_ledger", "query_ledger.jsonl"),
        ("provider_budget_ledger", "provider_budget_ledger.jsonl"),
        ("task_ledger", "task_events_v1.jsonl"),
        ("provider_trace_root", "provider_traces"),
        ("checkpoint_root", "search_checkpoints"),
        ("technical_review", "technical_review_v1.json"),
    )
    root = _resolve_project_path(output_root)
    rows: list[dict[str, Any]] = []
    for kind, child in children:
        path = root if not child else root / child
        exists = path.exists()
        rows.append({"kind": kind, "path": _display_path(path), "exists": exists})
        if exists:
            raise AdaptiveExecutionOrderGateV2Error(
                f"v1 adaptive execution evidence exists: {path}"
            )
    return rows


def _seal_v1_stage(stage: str) -> dict[str, Any]:
    locks = EXPECTED_V1_ASSET_LOCKS[stage]
    candidate_path = _validate_literal_file_lock(locks["candidate"])
    admission_path = _validate_literal_file_lock(locks["admission"])
    candidate = _read_json(candidate_path)
    admission = _read_json(admission_path)
    if (
        candidate.get("manifest_sha256") != _manifest_sha(candidate)
        or admission.get("manifest_sha256") != _manifest_sha(admission)
        or candidate.get("scope", {}).get("stage") != stage
        or admission.get("stage") != stage
        or candidate.get("scope", {}).get("output_root")
        != EXPECTED_V1_OUTPUT_ROOTS[stage]
    ):
        raise AdaptiveExecutionOrderGateV2Error(f"{stage}: malformed v1 asset")
    candidate_manifest = str(candidate["manifest_sha256"])
    admission_binding = str(admission.get("candidate_manifest_sha256", ""))
    if admission_binding == candidate_manifest:
        raise AdaptiveExecutionOrderGateV2Error(
            f"{stage}: expected historical candidate/admission mismatch is absent"
        )
    reasons = [
        "admission_candidate_manifest_does_not_match_hash_locked_candidate",
        "v1_admission_does_not_bind_adaptive_execution_order_gate_v2",
    ]
    if stage == "flash_50":
        if candidate.get("scope", {}).get("prior_review_manifest_sha256") is not None:
            raise AdaptiveExecutionOrderGateV2Error(
                "Flash-50 v1 unexpectedly binds a predecessor review"
            )
        reasons.append(
            "flash_50_v1_omits_required_pro_hardest_2000_predecessor_review"
        )
    else:
        reasons.append("pro_50_v1_is_replaced_by_versioned_order_gate_candidate")
    return {
        "stage": stage,
        "status": "v1_superseded_before_execution",
        "candidate_file_lock": copy.deepcopy(locks["candidate"]),
        "candidate_manifest_sha256": candidate_manifest,
        "admission_file_lock": copy.deepcopy(locks["admission"]),
        "admission_manifest_sha256": admission["manifest_sha256"],
        "admission_candidate_manifest_sha256": admission_binding,
        "candidate_admission_binding_matches": False,
        "output_root": EXPECTED_V1_OUTPUT_ROOTS[stage],
        "absence_evidence": _expected_absence_rows(EXPECTED_V1_OUTPUT_ROOTS[stage]),
        "nonempty_output_files": 0,
        "execution_forbidden_reasons": reasons,
        "v1_execution_authorized": False,
        "deletion_performed": False,
    }


def build_supersession_order_review() -> dict[str, Any]:
    """Rebuild the zero-call v1 seal and exact adaptive stage order."""

    order = validate_stage_order(STAGE_ORDER)
    v1_seals = [_seal_v1_stage(stage) for stage in ("pro_50", "flash_50")]
    core = {
        "schema_version": SCHEMA_VERSION,
        "artifact_role": "zero_call_v1_supersession_and_adaptive_order_gate",
        "status": "v1_stages_superseded_before_execution_order_v2_frozen",
        "implementation_lock": {
            "path": _display_path(Path(__file__)),
            "bytes": Path(__file__).stat().st_size,
            "sha256": _sha256_file(Path(__file__)),
        },
        "stage_order": order,
        "stage_order_sha256": sha256_canonical_json(order),
        "gemini_day_0_predecessor": "flash_200",
        "v1_seals": v1_seals,
        "controls": {
            "v1_execution_authorized": False,
            "v2_execution_admissions_created_by_this_gate": 0,
            "provider_clients_constructed": 0,
            "credentials_read": False,
            "network_calls_made": 0,
            "provider_calls_made": 0,
            "scientific_outcomes_read": 0,
            "historical_assets_modified": False,
            "real_external_effects": 0,
        },
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def validate_supersession_order_review(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise AdaptiveExecutionOrderGateV2Error("adaptive order review missing")
    expected = build_supersession_order_review()
    if dict(value) != expected:
        raise AdaptiveExecutionOrderGateV2Error(
            "adaptive supersession/order review drift"
        )
    return copy.deepcopy(dict(value))


def write_supersession_order_review() -> dict[str, Any]:
    value = build_supersession_order_review()
    _write_json(REVIEW_PATH, value)
    return value


def verify_supersession_order_review() -> dict[str, Any]:
    return validate_supersession_order_review(_read_json(REVIEW_PATH))


def _validate_technical_review_payload(
    value: Mapping[str, Any], *, expected_stage: str
) -> dict[str, Any]:
    try:
        expected_schema, expected_status = EXPECTED_REVIEW_CONTRACTS[expected_stage]
    except KeyError as exc:
        raise AdaptiveExecutionOrderGateV2Error(
            f"{expected_stage}: no predecessor review contract"
        ) from exc
    checks = value.get("checks")
    required_digests = (
        "candidate_manifest_sha256",
        "admission_file_sha256",
        "execution_identity",
        "query_ledger_tail_sha256",
        "budget_ledger_tail_sha256",
        "task_ledger_tail_sha256",
    )
    digest_values_valid = all(
        isinstance(value.get(field), str)
        and bool(_HEX64.fullmatch(str(value[field])))
        for field in required_digests
    )
    if (
        value.get("schema_version") != expected_schema
        or value.get("status") != expected_status
        or value.get("stage") != expected_stage
        or value.get("manifest_sha256") != _manifest_sha(value)
        or value.get("technical_gate_passed") is not True
        or value.get("result_admission_authorized") is not False
        or not isinstance(checks, Mapping)
        or not checks
        or any(not isinstance(child, bool) for child in checks.values())
        or not all(checks.values())
        or checks.get("scientific_outcomes_not_aggregated") is not True
        or "scientific_outcomes_aggregated" in checks
        or not digest_values_valid
        or not isinstance(value.get("run_id"), str)
        or not value.get("run_id")
        or value.get("terminal_task_count") != value.get("authorized_task_count")
        or not isinstance(value.get("final_checkpoint_locks"), list)
    ):
        raise AdaptiveExecutionOrderGateV2Error(
            f"{expected_stage}: predecessor technical review did not pass"
        )
    return copy.deepcopy(dict(value))


def build_predecessor_review_lock(
    review_path: Path, *, expected_stage: str
) -> dict[str, Any]:
    """Validate a review first, then return the exact lock a successor must bind."""

    path = _resolve_project_path(str(review_path))
    review = _validate_technical_review_payload(
        _read_json(path), expected_stage=expected_stage
    )
    return {
        "path": _display_path(path),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
        "manifest_sha256": review["manifest_sha256"],
        "stage": expected_stage,
    }


def validate_predecessor_review_lock(
    successor_stage: str, lock: Any
) -> dict[str, Any]:
    """Require the exact passing review immediately before ``successor_stage``."""

    predecessor = predecessor_for(successor_stage)
    if predecessor is None:
        raise AdaptiveExecutionOrderGateV2Error(
            "Pro-50 is the root stage and has no predecessor review"
        )
    if not isinstance(lock, Mapping):
        raise AdaptiveExecutionOrderGateV2Error(
            f"{successor_stage}: predecessor review lock is required"
        )
    if lock.get("stage") != predecessor:
        raise AdaptiveExecutionOrderGateV2Error(
            f"{successor_stage}: predecessor must be {predecessor}"
        )
    path = _validate_literal_file_lock(lock)
    review = _validate_technical_review_payload(
        _read_json(path), expected_stage=predecessor
    )
    if review["manifest_sha256"] != lock.get("manifest_sha256"):
        raise AdaptiveExecutionOrderGateV2Error(
            f"{successor_stage}: predecessor manifest lock drift"
        )
    return {
        "successor_stage": successor_stage,
        "predecessor_stage": predecessor,
        "review_lock": copy.deepcopy(dict(lock)),
        "technical_gate_passed": True,
        "scientific_outcomes_read_by_gate": 0,
    }


def require_predecessor_before_candidate_build(
    successor_stage: str, predecessor_review_lock: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """Return a candidate-build prerequisite; never create or execute a candidate."""

    order_review = verify_supersession_order_review()
    predecessor = predecessor_for(successor_stage)
    if predecessor is None:
        if predecessor_review_lock is not None:
            raise AdaptiveExecutionOrderGateV2Error(
                "Pro-50 root stage must not claim a predecessor"
            )
        predecessor_context: dict[str, Any] | None = None
    else:
        predecessor_context = validate_predecessor_review_lock(
            successor_stage, predecessor_review_lock
        )
    return {
        "successor_stage": successor_stage,
        "predecessor_stage": predecessor,
        "order_gate_manifest_sha256": order_review["manifest_sha256"],
        "predecessor_context": predecessor_context,
        "candidate_build_prerequisite_passed": True,
        "execution_admission_created": False,
        "execution_authorized": False,
        "credentials_read": False,
        "network_calls_made": 0,
    }


def require_predecessor_before_admission(
    successor_stage: str,
    *,
    successor_candidate_lock: Mapping[str, Any],
    predecessor_review_lock: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate a replacement candidate's order binding before admission creation."""

    context = require_predecessor_before_candidate_build(
        successor_stage, predecessor_review_lock
    )
    candidate_path = _validate_literal_file_lock(successor_candidate_lock)
    old_candidate_paths = {
        str(stage["candidate"]["path"])
        for stage in EXPECTED_V1_ASSET_LOCKS.values()
    }
    candidate_display = _display_path(candidate_path)
    if candidate_display in old_candidate_paths:
        raise AdaptiveExecutionOrderGateV2Error(
            "v1 adaptive candidate is superseded and cannot be admitted"
        )
    candidate = _read_json(candidate_path)
    scope = candidate.get("scope")
    predecessor_manifest = (
        None
        if context["predecessor_context"] is None
        else context["predecessor_context"]["review_lock"]["manifest_sha256"]
    )
    if (
        candidate.get("manifest_sha256") != _manifest_sha(candidate)
        or successor_candidate_lock.get("manifest_sha256")
        != candidate.get("manifest_sha256")
        or not isinstance(scope, Mapping)
        or scope.get("stage") != successor_stage
        or "prior_review_manifest_sha256" not in scope
        or scope.get("prior_review_manifest_sha256") != predecessor_manifest
        or candidate.get("order_gate_schema_version") != SCHEMA_VERSION
        or candidate.get("order_gate_manifest_sha256")
        != context["order_gate_manifest_sha256"]
        or candidate.get("authorization", {}).get("stage_execution_authorized")
        is not False
        or candidate.get("evidence_boundary", {}).get("network_calls_made") != 0
        or candidate.get("evidence_boundary", {}).get("credentials_read") is not False
    ):
        raise AdaptiveExecutionOrderGateV2Error(
            f"{successor_stage}: replacement candidate order binding invalid"
        )
    return {
        **context,
        "successor_candidate_lock": copy.deepcopy(dict(successor_candidate_lock)),
        "admission_prerequisite_passed": True,
        "execution_admission_created": False,
        "execution_authorized": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write-review", action="store_true")
    action.add_argument("--verify-review", action="store_true")
    args = parser.parse_args()
    value = (
        write_supersession_order_review()
        if args.write_review
        else verify_supersession_order_review()
    )
    print(
        json.dumps(
            {
                "status": value["status"],
                "manifest_sha256": value["manifest_sha256"],
                "network_calls_made": value["controls"]["network_calls_made"],
                "execution_admissions_created": value["controls"][
                    "v2_execution_admissions_created_by_this_gate"
                ],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
