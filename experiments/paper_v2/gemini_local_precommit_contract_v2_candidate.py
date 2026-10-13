"""冻结前瞻性 Gemini 本地预提交证据契约。

在发起实际远程 API 调用前预先锁定本地请求参数、目标用例与预期动作结构。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import experiments.paper_v2.gemini_public_segment_abort_review_v1 as abort_v1
import experiments.paper_v2.gemini_trace_attaching_runtime_v2 as runtime_v2
from experiments.paper_v2.contracts import sha256_canonical_json


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SUPERSEDED_OUTPUT = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/gemini_local_precommit_contract_v2_candidate.json"
)
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/"
    "gemini_local_precommit_contract_v2_1_candidate.json"
)
SCHEMA_VERSION = "m3-paper-v2-gemini-local-precommit-contract-candidate-2.1"
GENERATED_AT = "2026-08-04T02:45:00+08:00"


class GeminiLocalPrecommitContractV2CandidateError(ValueError):
    """当预期契约或其固化输入发生漂移时抛出的异常。"""


def _display(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _lock(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise GeminiLocalPrecommitContractV2CandidateError(
            f"missing prospective contract input: {path}"
        )
    return {
        "path": _display(path),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def _verify_lock(value: Mapping[str, Any]) -> None:
    path = (PROJECT_ROOT / str(value.get("path", ""))).resolve()
    try:
        path.relative_to(PROJECT_ROOT.resolve())
    except ValueError as exc:
        raise GeminiLocalPrecommitContractV2CandidateError(
            "prospective contract lock escapes the project"
        ) from exc
    if (
        not path.is_file()
        or path.stat().st_size != value.get("bytes")
        or _sha256_file(path) != value.get("sha256")
    ):
        raise GeminiLocalPrecommitContractV2CandidateError(
            f"prospective contract lock drift: {path}"
        )


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GeminiLocalPrecommitContractV2CandidateError(
            f"{path}: invalid JSON"
        ) from exc
    if not isinstance(value, dict):
        raise GeminiLocalPrecommitContractV2CandidateError(
            f"{path}: expected object"
        )
    return value


def build_candidate() -> dict[str, Any]:
    abort = abort_v1.verify_review()
    superseded = _read(SUPERSEDED_OUTPUT)
    superseded_core = {
        key: child
        for key, child in superseded.items()
        if key != "manifest_sha256"
    }
    if (
        superseded.get("manifest_sha256")
        != sha256_canonical_json(superseded_core)
        or superseded.get("status") != "candidate_pending_fresh_full_harness"
        or superseded.get("authorization", {}).get(
            "provider_execution_authorized"
        )
        is not False
        or superseded.get("evidence_boundary", {}).get("network_calls_made")
        != 0
    ):
        raise GeminiLocalPrecommitContractV2CandidateError(
            "superseded v2.0 candidate boundary drift"
        )
    paths = [
        Path(__file__),
        Path(runtime_v2.__file__),
        PROJECT_ROOT
        / "tests/unit/test_paper_v2_gemini_trace_attaching_runtime_v2.py",
        PROJECT_ROOT / "experiments/paper_v2/gemini_public_trace_v1.py",
        PROJECT_ROOT
        / "experiments/paper_v2/gemini_public_execution_store_v1.py",
        PROJECT_ROOT / "experiments/paper_v2/gemini_json_client_v1.py",
        PROJECT_ROOT / "experiments/paper_v2/official_provider_executor.py",
        abort_v1.DEFAULT_OUTPUT,
        SUPERSEDED_OUTPUT,
    ]
    contract = {
        "contract_id": runtime_v2.CONTRACT_ID,
        "provider_id": "gemini",
        "upstream_provider": "Google",
        "model_id": "gemini-3.6-flash",
        "accepted_trace_mode": "precommitted_local_plus_provider_response",
        "provider_request_id": None,
        "provider_request_id_must_not_be_fabricated": True,
        "local_client_request_id_required": True,
        "canonical_payload_sha256_required": True,
        "official_response_id_required": True,
        "exact_returned_model_required": True,
        "append_flush_fsync_required": True,
        "complete_bundle_required": True,
        "open_request_count_required": 0,
        "automatic_retries": 0,
        "billing_tier": "free",
        "paid_ceiling_usd": 0.0,
        "provider_tools_enabled": False,
        "external_effects_enabled": False,
    }
    negative_probes = [
        "non_google_provider",
        "model_identity_drift",
        "response_id_drift_or_missing",
        "payload_sha256_drift",
        "prompt_rewrite_not_none",
        "identity_not_verified",
        "invented_provider_request_id",
        "trace_mode_request_id_mismatch",
        "trace_bundle_hash_tamper",
        "open_or_failed_trace",
        "paid_tier_or_nonzero_charge",
        "qualification_or_stub_tier",
        "conflicting_runtime_bundle",
        "secret_or_prompt_persistence",
    ]
    core = {
        "schema_version": SCHEMA_VERSION,
        "artifact_role": "non_executable_prospective_contract_candidate",
        "generated_at": GENERATED_AT,
        "status": "candidate_pending_fresh_full_harness",
        "supersedes_schema_version": superseded["schema_version"],
        "superseded_candidate_manifest_sha256": superseded[
            "manifest_sha256"
        ],
        "supersession_reason": (
            "add_complete_bundle_post_response_failure_attestation_path"
        ),
        "source_abort_review_manifest_sha256": abort["manifest_sha256"],
        "contract": contract,
        "contract_sha256": sha256_canonical_json(contract),
        "negative_probes": negative_probes,
        "negative_probes_sha256": sha256_canonical_json(negative_probes),
        "artifact_locks": [_lock(path) for path in paths],
        "authorization": {
            "candidate_only": True,
            "provider_execution_authorized": False,
            "historical_response_upgrade_authorized": False,
            "same_segment_retry_authorized": False,
            "result_admission_authorized": False,
        },
        "evidence_boundary": {
            "credentials_read": False,
            "network_calls_made": 0,
            "scientific_outcomes_read": 0,
            "historical_files_mutated": 0,
        },
    }
    return {**core, "manifest_sha256": sha256_canonical_json(core)}


def validate_candidate(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise GeminiLocalPrecommitContractV2CandidateError(
            "prospective contract candidate must be an object"
        )
    core = {key: child for key, child in value.items() if key != "manifest_sha256"}
    contract = value.get("contract")
    probes = value.get("negative_probes")
    authorization = value.get("authorization")
    boundary = value.get("evidence_boundary")
    if (
        value.get("schema_version") != SCHEMA_VERSION
        or value.get("manifest_sha256") != sha256_canonical_json(core)
        or not isinstance(contract, Mapping)
        or value.get("contract_sha256") != sha256_canonical_json(contract)
        or not isinstance(probes, list)
        or value.get("negative_probes_sha256")
        != sha256_canonical_json(probes)
        or contract.get("contract_id") != runtime_v2.CONTRACT_ID
        or contract.get("provider_request_id") is not None
        or contract.get("provider_request_id_must_not_be_fabricated") is not True
        or contract.get("automatic_retries") != 0
        or contract.get("billing_tier") != "free"
        or contract.get("paid_ceiling_usd") != 0.0
        or not isinstance(authorization, Mapping)
        or authorization.get("provider_execution_authorized") is not False
        or authorization.get("historical_response_upgrade_authorized") is not False
        or authorization.get("same_segment_retry_authorized") is not False
        or authorization.get("result_admission_authorized") is not False
        or boundary
        != {
            "credentials_read": False,
            "network_calls_made": 0,
            "scientific_outcomes_read": 0,
            "historical_files_mutated": 0,
        }
    ):
        raise GeminiLocalPrecommitContractV2CandidateError(
            "prospective Gemini contract candidate drift"
        )
    locks = value.get("artifact_locks")
    if not isinstance(locks, list) or len(locks) != 9:
        raise GeminiLocalPrecommitContractV2CandidateError(
            "prospective contract lock set drift"
        )
    for lock in locks:
        if not isinstance(lock, Mapping):
            raise GeminiLocalPrecommitContractV2CandidateError(
                "prospective contract lock is invalid"
            )
        _verify_lock(lock)
    return copy.deepcopy(dict(value))


def write_candidate(path: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    value = build_candidate()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return value


def verify_candidate(path: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    observed = validate_candidate(_read(path))
    expected = build_candidate()
    if observed != expected:
        raise GeminiLocalPrecommitContractV2CandidateError(
            "prospective Gemini contract candidate does not reproduce"
        )
    return observed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    value = write_candidate() if args.write else verify_candidate()
    print(
        json.dumps(
            {
                "status": value["status"],
                "manifest_sha256": value["manifest_sha256"],
                "provider_execution_authorized": value["authorization"][
                    "provider_execution_authorized"
                ],
                "network_calls_made": value["evidence_boundary"][
                    "network_calls_made"
                ],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
