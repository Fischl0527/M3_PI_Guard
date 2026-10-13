"""在不发起付费调用的前提下冻结 paper-v2 官方提供商传输身份。

前置验证 API 密钥配置有效性与网络端点可达性。
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from experiments.paper_v2.agentdojo_live_dependency import (
    verify_qualification as verify_agentdojo_qualification,
)
from experiments.paper_v2.contracts import sha256_canonical_json
from experiments.paper_v2.exact_gold_ablation import (
    verify_qualification as verify_exact_gold_qualification,
)
from experiments.paper_v2.formal_condition_executors import (
    build_condition_executor_qualification,
)
from experiments.paper_v2.formal_record_store import (
    build_record_store_qualification,
)
from experiments.paper_v2.formal_record_store_v2 import (
    verify_qualification as verify_record_store_v2_qualification,
)
from experiments.paper_v2.gemini_quota_snapshot import (
    verify_snapshot as verify_gemini_quota_snapshot,
)
from experiments.paper_v2.live_condition_runtime import (
    build_live_runtime_qualification,
)
from experiments.paper_v2.m3_offline_evaluator import (
    verify_qualification as verify_m3_evaluator_qualification,
)
from experiments.paper_v2.official_provider_executor import (
    build_offline_transport_qualification,
)
from experiments.paper_v2.post_pilot_evidence_review import (
    verify_reviewer_qualification,
)
from experiments.paper_v2.promptguard_live_dependency import (
    verify_qualification_artifact as verify_promptguard_qualification,
)
from experiments.paper_v2.provider_live_qualification import (
    verify_live_qualification as verify_provider_live_qualification,
)
from experiments.paper_v2.provider_live_qualification_v2 import (
    verify_live_qualification as verify_provider_live_qualification_v2,
)
from experiments.paper_v2.provider_request_trace_candidate import (
    validate_policy_candidate as validate_trace_policy_candidate,
    validate_qualification as validate_trace_qualification,
)
from experiments.paper_v2.provider_request_trace_activation import (
    verify_activation as verify_trace_activation,
)
from experiments.paper_v2.provider_trace_runtime_qualification import (
    verify_qualification as verify_trace_runtime_qualification,
)
from experiments.paper_v2.vigil_live_dependency import (
    verify_qualification as verify_vigil_qualification,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_ROOT = PROJECT_ROOT / "protocols/paper_upgrade_v2"
DEFAULT_QUALIFICATION = (
    PROTOCOL_ROOT / "provider_executor_qualification_v1.json"
)
DEFAULT_CONDITION_QUALIFICATION = (
    PROTOCOL_ROOT / "formal_condition_executor_qualification_v1.json"
)
DEFAULT_RECORD_STORE_QUALIFICATION = (
    PROTOCOL_ROOT / "formal_record_store_qualification_v1.json"
)
DEFAULT_RECORD_STORE_V2_QUALIFICATION = (
    PROTOCOL_ROOT / "formal_record_store_qualification_v2.json"
)
DEFAULT_LIVE_RUNTIME_QUALIFICATION = (
    PROTOCOL_ROOT / "live_condition_runtime_qualification_v1.json"
)
DEFAULT_PROMPTGUARD_QUALIFICATION = (
    PROTOCOL_ROOT / "promptguard_live_dependency_qualification_v1.json"
)
DEFAULT_AGENTDOJO_QUALIFICATION = (
    PROTOCOL_ROOT / "agentdojo_live_dependency_qualification_v1.json"
)
DEFAULT_M3_EVALUATOR_QUALIFICATION = (
    PROTOCOL_ROOT / "m3_offline_evaluator_qualification_v1.json"
)
DEFAULT_EXACT_GOLD_QUALIFICATION = (
    PROTOCOL_ROOT / "exact_gold_ablation_qualification_v1.json"
)
DEFAULT_VIGIL_QUALIFICATION = (
    PROTOCOL_ROOT / "vigil_live_dependency_qualification_v1.json"
)
DEFAULT_PROVIDER_LIVE_QUALIFICATION = (
    PROTOCOL_ROOT / "provider_live_qualification_v1.json"
)
DEFAULT_PROVIDER_LIVE_QUALIFICATION_V2 = (
    PROTOCOL_ROOT / "provider_live_qualification_v2.json"
)
DEFAULT_PROVIDER_TRACE_POLICY = (
    PROTOCOL_ROOT / "provider_request_trace_policy_v2_candidate.json"
)
DEFAULT_PROVIDER_TRACE_QUALIFICATION = (
    PROTOCOL_ROOT / "provider_request_trace_v2_qualification.json"
)
DEFAULT_PROVIDER_TRACE_ACTIVATION = (
    PROTOCOL_ROOT / "provider_request_trace_activation_v2.json"
)
DEFAULT_GEMINI_QUOTA_SNAPSHOT = (
    PROTOCOL_ROOT / "gemini_quota_snapshot_v1.json"
)
DEFAULT_PROVIDER_TRACE_RUNTIME_QUALIFICATION = (
    PROTOCOL_ROOT / "provider_trace_runtime_qualification_v2.json"
)
DEFAULT_POST_PILOT_REVIEW_QUALIFICATION = (
    PROTOCOL_ROOT / "post_pilot_review_qualification_v1.json"
)
DEFAULT_OUTPUT = PROTOCOL_ROOT / "medium_execution_manifest_v3_preflight.json"
LOCKED_INPUTS = (
    PROJECT_ROOT / "protocols/paper_upgrade_v2/medium_execution_plan_v2.jsonl",
    PROJECT_ROOT / "protocols/paper_upgrade_v2/medium_execution_manifest_v2.json",
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/dual_provider_budget_policy_v1.json",
    PROJECT_ROOT
    / "protocols/paper_upgrade_v2/dual_provider_budget_preflight_v1.json",
    PROJECT_ROOT / "protocols/paper_upgrade_v2/provider_safety_policy_v1.json",
    PROJECT_ROOT / "experiments/paper_v2/official_provider_executor.py",
    PROJECT_ROOT / "experiments/paper_v2/provider_execution_gate.py",
    PROJECT_ROOT / "experiments/paper_v2/provider_live_qualification.py",
    PROJECT_ROOT / "experiments/paper_v2/provider_live_qualification_v2.py",
    PROJECT_ROOT
    / "experiments/paper_v2/provider_request_trace_candidate.py",
    PROJECT_ROOT
    / "experiments/paper_v2/provider_request_trace_activation.py",
    PROJECT_ROOT / "experiments/paper_v2/provider_trace_bundle.py",
    PROJECT_ROOT
    / "experiments/paper_v2/provider_trace_runtime_qualification.py",
    PROJECT_ROOT / "experiments/paper_v2/gemini_quota_snapshot.py",
    PROJECT_ROOT / "experiments/paper_v2/provider_budget.py",
    PROJECT_ROOT / "experiments/paper_v2/provider_safety.py",
    PROJECT_ROOT / "experiments/paper_v2/contracts.py",
    PROJECT_ROOT / "experiments/paper_v2/contracts_v2.py",
    PROJECT_ROOT / "experiments/paper_v2/formal_condition_executors.py",
    PROJECT_ROOT / "experiments/paper_v2/formal_record_store.py",
    PROJECT_ROOT / "experiments/paper_v2/formal_record_store_v2.py",
    PROJECT_ROOT / "experiments/paper_v2/live_condition_runtime.py",
    PROJECT_ROOT / "experiments/paper_v2/promptguard_live_dependency.py",
    PROJECT_ROOT / "experiments/paper_v2/agentdojo_live_dependency.py",
    PROJECT_ROOT / "experiments/paper_v2/m3_offline_evaluator.py",
    PROJECT_ROOT / "experiments/paper_v2/exact_gold_ablation.py",
    PROJECT_ROOT / "experiments/paper_v2/vigil_live_dependency.py",
    PROJECT_ROOT / "experiments/paper_v2/structural_baselines.py",
    PROJECT_ROOT / "experiments/paper_v2/post_pilot_evidence_review.py",
    PROJECT_ROOT / "schemas/paper_v2/experiment_record_v1.schema.json",
    PROJECT_ROOT / "schemas/paper_v2/experiment_record_v2.schema.json",
    PROJECT_ROOT
    / "schemas/paper_v2/provider_trace_attestation_v2.schema.json",
    PROJECT_ROOT
    / "schemas/paper_v2/provider_trace_bundle_v2.schema.json",
    PROJECT_ROOT
    / "schemas/paper_v2/provider_safety_receipt_v1.schema.json",
    PROJECT_ROOT / "schemas/paper_v2/post_pilot_review_v1.schema.json",
    DEFAULT_CONDITION_QUALIFICATION,
    DEFAULT_RECORD_STORE_QUALIFICATION,
    DEFAULT_RECORD_STORE_V2_QUALIFICATION,
    DEFAULT_LIVE_RUNTIME_QUALIFICATION,
    DEFAULT_PROMPTGUARD_QUALIFICATION,
    DEFAULT_AGENTDOJO_QUALIFICATION,
    DEFAULT_M3_EVALUATOR_QUALIFICATION,
    DEFAULT_EXACT_GOLD_QUALIFICATION,
    DEFAULT_VIGIL_QUALIFICATION,
    DEFAULT_PROVIDER_LIVE_QUALIFICATION,
    DEFAULT_PROVIDER_LIVE_QUALIFICATION_V2,
    DEFAULT_PROVIDER_TRACE_POLICY,
    DEFAULT_PROVIDER_TRACE_QUALIFICATION,
    DEFAULT_PROVIDER_TRACE_ACTIVATION,
    DEFAULT_GEMINI_QUOTA_SNAPSHOT,
    DEFAULT_PROVIDER_TRACE_RUNTIME_QUALIFICATION,
    DEFAULT_POST_PILOT_REVIEW_QUALIFICATION,
)


class ProviderExecutionGateError(ValueError):
    """当 v3 提供商执行预检发生漂移时抛出的异常。"""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _display_path(path: Path) -> str:
    try:
        return path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ProviderExecutionGateError(f"{path}: expected a JSON object")
    return value


def build_execution_preflight(
    *,
    qualification_path: Path = DEFAULT_QUALIFICATION,
    condition_qualification_path: Path = DEFAULT_CONDITION_QUALIFICATION,
    record_store_qualification_path: Path = DEFAULT_RECORD_STORE_QUALIFICATION,
    record_store_v2_qualification_path: Path = (
        DEFAULT_RECORD_STORE_V2_QUALIFICATION
    ),
    live_runtime_qualification_path: Path = DEFAULT_LIVE_RUNTIME_QUALIFICATION,
    promptguard_qualification_path: Path = DEFAULT_PROMPTGUARD_QUALIFICATION,
    agentdojo_qualification_path: Path = DEFAULT_AGENTDOJO_QUALIFICATION,
    m3_evaluator_qualification_path: Path = DEFAULT_M3_EVALUATOR_QUALIFICATION,
    exact_gold_qualification_path: Path = DEFAULT_EXACT_GOLD_QUALIFICATION,
    vigil_qualification_path: Path = DEFAULT_VIGIL_QUALIFICATION,
    provider_live_qualification_path: Path = (
        DEFAULT_PROVIDER_LIVE_QUALIFICATION
    ),
    provider_live_qualification_v2_path: Path = (
        DEFAULT_PROVIDER_LIVE_QUALIFICATION_V2
    ),
    provider_trace_policy_path: Path = DEFAULT_PROVIDER_TRACE_POLICY,
    provider_trace_qualification_path: Path = (
        DEFAULT_PROVIDER_TRACE_QUALIFICATION
    ),
    provider_trace_activation_path: Path = (
        DEFAULT_PROVIDER_TRACE_ACTIVATION
    ),
    gemini_quota_snapshot_path: Path = DEFAULT_GEMINI_QUOTA_SNAPSHOT,
    provider_trace_runtime_qualification_path: Path = (
        DEFAULT_PROVIDER_TRACE_RUNTIME_QUALIFICATION
    ),
    post_pilot_review_qualification_path: Path = (
        DEFAULT_POST_PILOT_REVIEW_QUALIFICATION
    ),
) -> dict[str, Any]:
    """绑定确切的传输输入，同时保留所有科学阻断器。"""

    qualification = build_offline_transport_qualification()
    if _load_json(qualification_path) != qualification:
        raise ProviderExecutionGateError(
            "frozen provider executor qualification does not reproduce"
        )
    condition_qualification = build_condition_executor_qualification()
    if _load_json(condition_qualification_path) != condition_qualification:
        raise ProviderExecutionGateError(
            "frozen condition executor qualification does not reproduce"
        )
    record_store_qualification = build_record_store_qualification()
    if _load_json(record_store_qualification_path) != (
        record_store_qualification
    ):
        raise ProviderExecutionGateError(
            "frozen record-store qualification does not reproduce"
        )
    record_store_v2_qualification = verify_record_store_v2_qualification(
        record_store_v2_qualification_path
    )
    live_runtime_qualification = build_live_runtime_qualification()
    if _load_json(live_runtime_qualification_path) != (
        live_runtime_qualification
    ):
        raise ProviderExecutionGateError(
            "frozen live-runtime qualification does not reproduce"
        )
    promptguard_qualification = verify_promptguard_qualification(
        artifact_path=promptguard_qualification_path
    )
    agentdojo_qualification = verify_agentdojo_qualification(
        path=agentdojo_qualification_path
    )
    m3_evaluator_qualification = verify_m3_evaluator_qualification(
        path=m3_evaluator_qualification_path
    )
    exact_gold_qualification = verify_exact_gold_qualification(
        path=exact_gold_qualification_path
    )
    vigil_qualification = verify_vigil_qualification(
        path=vigil_qualification_path
    )
    provider_live_qualification = verify_provider_live_qualification(
        path=provider_live_qualification_path
    )
    provider_live_qualification_v2 = verify_provider_live_qualification_v2(
        path=provider_live_qualification_v2_path
    )
    provider_trace_policy = validate_trace_policy_candidate(
        _load_json(provider_trace_policy_path)
    )
    provider_trace_qualification = validate_trace_qualification(
        _load_json(provider_trace_qualification_path)
    )
    gemini_quota_snapshot = verify_gemini_quota_snapshot(
        gemini_quota_snapshot_path
    )
    provider_trace_activation = verify_trace_activation(
        provider_trace_activation_path
    )
    provider_trace_runtime_qualification = (
        verify_trace_runtime_qualification(
            provider_trace_runtime_qualification_path
        )
    )
    post_pilot_review_qualification = verify_reviewer_qualification(
        post_pilot_review_qualification_path
    )
    locked = {
        _display_path(path): {
            "bytes": path.stat().st_size,
            "sha256": _sha256_file(path),
        }
        for path in LOCKED_INPUTS
    }
    identity_payload = {
        "schema_version": "m3-paper-v2-provider-execution-identity-1.0",
        "locked_inputs": locked,
        "qualification_sha256": _sha256_file(qualification_path),
        "condition_qualification_sha256": _sha256_file(
            condition_qualification_path
        ),
        "record_store_qualification_sha256": _sha256_file(
            record_store_qualification_path
        ),
        "record_store_v2_qualification_sha256": _sha256_file(
            record_store_v2_qualification_path
        ),
        "live_runtime_qualification_sha256": _sha256_file(
            live_runtime_qualification_path
        ),
        "promptguard_qualification_sha256": _sha256_file(
            promptguard_qualification_path
        ),
        "agentdojo_qualification_sha256": _sha256_file(
            agentdojo_qualification_path
        ),
        "m3_evaluator_qualification_sha256": _sha256_file(
            m3_evaluator_qualification_path
        ),
        "exact_gold_qualification_sha256": _sha256_file(
            exact_gold_qualification_path
        ),
        "vigil_qualification_sha256": _sha256_file(
            vigil_qualification_path
        ),
        "provider_live_qualification_sha256": _sha256_file(
            provider_live_qualification_path
        ),
        "provider_live_qualification_v2_sha256": _sha256_file(
            provider_live_qualification_v2_path
        ),
        "provider_trace_policy_sha256": _sha256_file(
            provider_trace_policy_path
        ),
        "provider_trace_qualification_sha256": _sha256_file(
            provider_trace_qualification_path
        ),
        "provider_trace_activation_sha256": _sha256_file(
            provider_trace_activation_path
        ),
        "gemini_quota_snapshot_sha256": _sha256_file(
            gemini_quota_snapshot_path
        ),
        "provider_trace_runtime_qualification_sha256": _sha256_file(
            provider_trace_runtime_qualification_path
        ),
        "post_pilot_review_qualification_sha256": _sha256_file(
            post_pilot_review_qualification_path
        ),
        "provider_models": {
            provider_id: data["configured_model"]
            for provider_id, data in qualification["providers"].items()
        },
        "full_matrix_work_items_per_model": 480,
        "maximum_calls_per_model": 4416,
    }
    blockers = [
        (
            "Per-call DeepSeek v2 tracing and ITT persistence are qualified "
            "offline, but a run-specific admission manifest and pilot "
            "acceptance decision have not been frozen. Formal matrix "
            "execution remains closed."
        )
    ]
    return {
        "schema_version": "m3-paper-v2-medium-execution-manifest-3.0-preflight",
        "generated_at": "2026-07-24T01:30:00+08:00",
        "status": (
            "deepseek_v2_runtime_wiring_qualified_admission_manifest_required"
        ),
        "execution_identity": sha256_canonical_json(identity_payload),
        "execution_authorized": False,
        "formal_execution_authorized": False,
        "network_calls_made": 0,
        "credentials_read": False,
        "formal_results_created": 0,
        "transport_adapters_qualified": 2,
        "formal_condition_executors_registered": condition_qualification[
            "registered_condition_count"
        ],
        "qualified_benchmark_condition_pairs": condition_qualification[
            "qualified_benchmark_condition_pairs"
        ],
        "formal_record_store_offline_qualified": True,
        "formal_record_store_v2_offline_qualified": True,
        "experiment_record_v2_schema_qualified": True,
        "live_formal_records_persisted": 0,
        "live_condition_dependencies_qualified": True,
        "live_condition_composition_offline_qualified": True,
        "promptguard_live_inference_qualified": True,
        "agentdojo_environment_and_evaluator_qualified": True,
        "offline_outcome_evaluators_qualified": True,
        "exact_gold_ablation_monitor_qualified": True,
        "vigil_provider_bridge_qualified": True,
        "live_provider_identity_qualified": True,
        "deepseek_live_v2_trace_qualified": True,
        "provider_trace_v2_candidate_qualified": True,
        "provider_trace_v2_activated": True,
        "live_runtime_per_call_v2_qualified": True,
        "gemini_quota_snapshot_bound": True,
        "gemini_quota_gate_satisfied": True,
        "work_items_per_provider_model": 480,
        "provider_calls_upper_bound_per_model": 4416,
        "provider_models_are_independent_matrices": True,
        "cross_provider_fallback": False,
        "automatic_retries": 0,
        "offline_qualification": {
            "path": _display_path(qualification_path),
            "sha256": _sha256_file(qualification_path),
            "status": qualification["status"],
            "formal_identity_attested": qualification[
                "formal_identity_attested"
            ],
            "formal_result_created": qualification["formal_result_created"],
        },
        "condition_shell_qualification": {
            "path": _display_path(condition_qualification_path),
            "sha256": _sha256_file(condition_qualification_path),
            "status": condition_qualification["status"],
            "registered_conditions": condition_qualification[
                "registered_condition_count"
            ],
            "qualified_pairs": condition_qualification[
                "qualified_benchmark_condition_pairs"
            ],
            "event_redaction_status": condition_qualification[
                "event_redaction_contract"
            ]["status"],
            "live_dependencies_qualified": condition_qualification[
                "live_dependencies_qualified"
            ],
        },
        "record_store_qualification": {
            "path": _display_path(record_store_qualification_path),
            "sha256": _sha256_file(record_store_qualification_path),
            "status": record_store_qualification["status"],
            "transient_entries": record_store_qualification[
                "transient_qualification_entries_written"
            ],
            "complete_chain_revalidated": record_store_qualification[
                "complete_chain_revalidated_after_each_append"
            ],
            "transient_cleanup_verified": record_store_qualification[
                "transient_cleanup_verified"
            ],
            "raw_content_markers_absent": record_store_qualification[
                "raw_content_markers_absent"
            ],
            "project_experiment_records_persisted": 0,
            "live_persistence_path_qualified": False,
        },
        "record_store_v2_qualification": {
            "path": _display_path(record_store_v2_qualification_path),
            "sha256": _sha256_file(record_store_v2_qualification_path),
            "status": record_store_v2_qualification["status"],
            "transient_entries": record_store_v2_qualification[
                "transient_entries_written"
            ],
            "hash_chain_complete": record_store_v2_qualification[
                "hash_chain_complete"
            ],
            "append_flush_fsync": record_store_v2_qualification[
                "append_flush_fsync"
            ],
            "negative_cases_rejected": record_store_v2_qualification[
                "negative_cases_rejected"
            ],
            "v1_record_contract_modified": False,
            "v1_record_store_modified": False,
            "live_runtime_v2_wiring_qualified": False,
            "project_experiment_records_persisted": 0,
            "network_calls_made": 0,
        },
        "provider_trace_runtime_qualification": {
            "path": _display_path(
                provider_trace_runtime_qualification_path
            ),
            "sha256": _sha256_file(
                provider_trace_runtime_qualification_path
            ),
            "status": provider_trace_runtime_qualification["status"],
            "scenario_count": provider_trace_runtime_qualification[
                "scenario_count"
            ],
            "formal_candidate_records": (
                provider_trace_runtime_qualification[
                    "formal_candidate_records"
                ]
            ),
            "diagnostic_itt_failure_records": (
                provider_trace_runtime_qualification[
                    "diagnostic_itt_failure_records"
                ]
            ),
            "vigil_success_request_count": (
                provider_trace_runtime_qualification[
                    "vigil_success_request_count"
                ]
            ),
            "append_flush_fsync_before_every_transport": (
                provider_trace_runtime_qualification[
                    "append_flush_fsync_before_every_transport"
                ]
            ),
            "automatic_retry": False,
            "network_calls_made": 0,
            "formal_results_created": 0,
        },
        "post_pilot_review_qualification": {
            "path": _display_path(post_pilot_review_qualification_path),
            "sha256": _sha256_file(post_pilot_review_qualification_path),
            "status": post_pilot_review_qualification["status"],
            "experiment_record_schema_version": (
                post_pilot_review_qualification[
                    "experiment_record_schema_version"
                ]
            ),
            "provider_safety_receipt_persisted": (
                post_pilot_review_qualification[
                    "provider_safety_receipt_persisted"
                ]
            ),
            "negative_cases_rejected": (
                post_pilot_review_qualification[
                    "negative_case_count"
                ]
            ),
            "official_evidence_gate_passed": False,
            "ready_for_owner_matrix_review": False,
            "network_calls_made": 0,
            "formal_matrix_authorized": False,
        },
        "live_runtime_qualification": {
            "path": _display_path(live_runtime_qualification_path),
            "sha256": _sha256_file(live_runtime_qualification_path),
            "status": live_runtime_qualification["status"],
            "qualified_pairs": live_runtime_qualification[
                "qualified_benchmark_condition_pairs"
            ],
            "strict_parser_negative_cases_rejected": (
                live_runtime_qualification[
                    "strict_parser_negative_cases_rejected"
                ]
            ),
            "call_cap_probes": live_runtime_qualification[
                "provider_call_caps_enforced_by_loop"
            ]["observed_probe_calls"],
            "in_memory_contract_records_validated": (
                live_runtime_qualification[
                    "in_memory_contract_records_validated"
                ]
            ),
            "live_dependencies_fully_qualified": (
                live_runtime_qualification[
                    "live_dependencies_fully_qualified"
                ]
            ),
            "exact_gold_integration_routes": live_runtime_qualification[
                "qualified_exact_gold_integration_routes"
            ],
        },
        "promptguard_qualification": {
            "path": _display_path(promptguard_qualification_path),
            "sha256": _sha256_file(promptguard_qualification_path),
            "status": promptguard_qualification["status"],
            "model_id": promptguard_qualification["pinned_identity"][
                "model_id"
            ],
            "revision": promptguard_qualification["pinned_identity"][
                "revision"
            ],
            "inference_cases": promptguard_qualification[
                "inference_case_count"
            ],
            "decision_matches": promptguard_qualification[
                "decision_matches"
            ],
            "input_text_persisted": promptguard_qualification[
                "input_text_persisted"
            ],
            "network_calls_made": 0,
        },
        "agentdojo_qualification": {
            "path": _display_path(agentdojo_qualification_path),
            "sha256": _sha256_file(agentdojo_qualification_path),
            "status": agentdojo_qualification["status"],
            "commit": agentdojo_qualification["source_lock"]["commit"],
            "worktree_clean": agentdojo_qualification["source_lock"][
                "worktree_clean"
            ],
            "attack_name": agentdojo_qualification[
                "attack_construction"
            ]["attack_name"],
            "official_utility_checker": agentdojo_qualification[
                "offline_evaluator"
            ]["official_utility_checker"],
            "official_security_checker": agentdojo_qualification[
                "offline_evaluator"
            ]["official_security_checker"],
            "qualification_probes": len(
                agentdojo_qualification["qualification_probes"]
            ),
            "network_calls_made": 0,
        },
        "m3_evaluator_qualification": {
            "path": _display_path(m3_evaluator_qualification_path),
            "sha256": _sha256_file(m3_evaluator_qualification_path),
            "status": m3_evaluator_qualification["status"],
            "qualified_benchmarks": m3_evaluator_qualification[
                "composite_evaluator"
            ]["benchmarks"],
            "qualification_probes": len(
                m3_evaluator_qualification["qualification_probes"]
            ),
            "labels_visible_online": m3_evaluator_qualification[
                "evaluator_labels_visible_online"
            ],
            "network_calls_made": 0,
        },
        "exact_gold_qualification": {
            "path": _display_path(exact_gold_qualification_path),
            "sha256": _sha256_file(exact_gold_qualification_path),
            "status": exact_gold_qualification["status"],
            "analysis_tier": exact_gold_qualification["analysis_tier"],
            "formal_primary_endpoint_eligible": exact_gold_qualification[
                "formal_primary_endpoint_eligible"
            ],
            "qualification_probes": len(
                exact_gold_qualification["qualification_probes"]
            ),
            "network_calls_made": 0,
        },
        "vigil_qualification": {
            "path": _display_path(vigil_qualification_path),
            "sha256": _sha256_file(vigil_qualification_path),
            "status": vigil_qualification["status"],
            "commit": vigil_qualification["source_lock"]["commit"],
            "provider_calls_consumed": vigil_qualification[
                "provider_bridge"
            ]["provider_calls_consumed"],
            "silent_default_fallback_accepted": vigil_qualification[
                "provider_bridge"
            ]["silent_default_fallback_accepted"],
            "network_calls_made": 0,
        },
        "provider_live_qualification": {
            "path": _display_path(provider_live_qualification_path),
            "sha256": _sha256_file(provider_live_qualification_path),
            "status": provider_live_qualification["status"],
            "qualified_provider_count": provider_live_qualification[
                "qualified_provider_count"
            ],
            "network_call_attempts": provider_live_qualification[
                "network_call_attempts"
            ],
            "deepseek_status": provider_live_qualification["providers"][
                "deepseek"
            ]["status"],
            "gemini_status": provider_live_qualification["providers"][
                "gemini"
            ]["status"],
            "credentials_stored": provider_live_qualification[
                "credentials_stored"
            ],
            "prompt_or_response_content_stored": (
                provider_live_qualification[
                    "prompt_or_response_content_stored"
                ]
            ),
            "formal_results_created": provider_live_qualification[
                "formal_results_created"
            ],
        },
        "provider_live_qualification_v2": {
            "path": _display_path(provider_live_qualification_v2_path),
            "sha256": _sha256_file(provider_live_qualification_v2_path),
            "status": provider_live_qualification_v2["status"],
            "provider_id": provider_live_qualification_v2["provider_id"],
            "identity_qualification_satisfied": (
                provider_live_qualification_v2[
                    "identity_qualification_satisfied"
                ]
            ),
            "network_call_attempts": provider_live_qualification_v2[
                "network_call_attempts"
            ],
            "trace_ledger": provider_live_qualification_v2[
                "trace_ledger"
            ],
            "response_exact_safe": provider_live_qualification_v2[
                "response_exact_safe"
            ],
            "provider_receipt_persisted": (
                provider_live_qualification_v2["provider_receipt"] is not None
            ),
            "prompt_or_response_content_stored": (
                provider_live_qualification_v2[
                    "prompt_or_response_content_stored"
                ]
            ),
            "result_eligible_for_effect_tables": False,
            "formal_matrix_authorized": False,
        },
        "provider_trace_v2_candidate": {
            "policy_path": _display_path(provider_trace_policy_path),
            "policy_sha256": _sha256_file(provider_trace_policy_path),
            "qualification_path": _display_path(
                provider_trace_qualification_path
            ),
            "qualification_sha256": _sha256_file(
                provider_trace_qualification_path
            ),
            "status": provider_trace_qualification["status"],
            "qualified_provider_count": provider_trace_qualification[
                "qualified_provider_count"
            ],
            "negative_cases_rejected": provider_trace_qualification[
                "negative_cases_rejected"
            ],
            "append_flush_fsync": provider_trace_qualification[
                "append_flush_fsync"
            ],
            "old_smoke_retroactive_upgrade": provider_trace_qualification[
                "old_smoke_retroactive_upgrade"
            ],
            "v1_contract_unchanged": provider_trace_policy[
                "v1_contract_unchanged"
            ],
            "v2_schema_activated": provider_trace_qualification[
                "v2_schema_activated"
            ],
            "formal_results_created": 0,
            "network_calls_made": 0,
        },
        "provider_trace_v2_activation": {
            "path": _display_path(provider_trace_activation_path),
            "sha256": _sha256_file(provider_trace_activation_path),
            "status": provider_trace_activation["status"],
            "approved_provider_ids": provider_trace_activation[
                "approval_scope"
            ]["provider_ids"],
            "request_trace_protocol_activated": (
                provider_trace_activation[
                    "request_trace_protocol_activated"
                ]
            ),
            "fresh_prospective_requests_only": provider_trace_activation[
                "fresh_prospective_requests_only"
            ],
            "v1_contract_unchanged": provider_trace_activation[
                "v1_contract_unchanged"
            ],
            "historical_artifacts_retroactively_eligible": (
                provider_trace_activation[
                    "historical_artifacts_retroactively_eligible"
                ]
            ),
            "formal_matrix_authorized": False,
            "network_calls_made": 0,
        },
        "gemini_quota_snapshot": {
            "path": _display_path(gemini_quota_snapshot_path),
            "sha256": _sha256_file(gemini_quota_snapshot_path),
            "status": gemini_quota_snapshot["status"],
            "quota_gate_satisfied": gemini_quota_snapshot[
                "quota_gate_satisfied"
            ],
            "active_limits": gemini_quota_snapshot["active_limits"],
            "captured_at": gemini_quota_snapshot["captured_at"],
            "captured_at_semantics": gemini_quota_snapshot[
                "captured_at_semantics"
            ],
            "source_screenshot_sha256": gemini_quota_snapshot[
                "source_screenshot_sha256"
            ],
            "billing_tier": gemini_quota_snapshot["billing_tier"],
            "paid_tier_allowed": gemini_quota_snapshot[
                "paid_tier_allowed"
            ],
            "project_identifier_stored": gemini_quota_snapshot[
                "project_identifier_stored"
            ],
            "api_key_or_credential_stored": gemini_quota_snapshot[
                "api_key_or_credential_stored"
            ],
            "formal_execution_authorized": False,
            "network_calls_made": 0,
        },
        "identity_payload": identity_payload,
        "blockers": blockers,
        "gate_pass": False,
        "next_gate": (
            "Freeze a run-specific admission manifest, execute one bounded "
            "DeepSeek pilot work item through the qualified v2 path, and "
            "review its cost, identity and evidence before authorizing a "
            "larger matrix."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--qualification", type=Path, default=DEFAULT_QUALIFICATION
    )
    parser.add_argument(
        "--condition-qualification",
        type=Path,
        default=DEFAULT_CONDITION_QUALIFICATION,
    )
    parser.add_argument(
        "--record-store-qualification",
        type=Path,
        default=DEFAULT_RECORD_STORE_QUALIFICATION,
    )
    parser.add_argument(
        "--record-store-v2-qualification",
        type=Path,
        default=DEFAULT_RECORD_STORE_V2_QUALIFICATION,
    )
    parser.add_argument(
        "--live-runtime-qualification",
        type=Path,
        default=DEFAULT_LIVE_RUNTIME_QUALIFICATION,
    )
    parser.add_argument(
        "--promptguard-qualification",
        type=Path,
        default=DEFAULT_PROMPTGUARD_QUALIFICATION,
    )
    parser.add_argument(
        "--agentdojo-qualification",
        type=Path,
        default=DEFAULT_AGENTDOJO_QUALIFICATION,
    )
    parser.add_argument(
        "--m3-evaluator-qualification",
        type=Path,
        default=DEFAULT_M3_EVALUATOR_QUALIFICATION,
    )
    parser.add_argument(
        "--exact-gold-qualification",
        type=Path,
        default=DEFAULT_EXACT_GOLD_QUALIFICATION,
    )
    parser.add_argument(
        "--vigil-qualification",
        type=Path,
        default=DEFAULT_VIGIL_QUALIFICATION,
    )
    parser.add_argument(
        "--provider-live-qualification",
        type=Path,
        default=DEFAULT_PROVIDER_LIVE_QUALIFICATION,
    )
    parser.add_argument(
        "--provider-live-qualification-v2",
        type=Path,
        default=DEFAULT_PROVIDER_LIVE_QUALIFICATION_V2,
    )
    parser.add_argument(
        "--provider-trace-policy",
        type=Path,
        default=DEFAULT_PROVIDER_TRACE_POLICY,
    )
    parser.add_argument(
        "--provider-trace-qualification",
        type=Path,
        default=DEFAULT_PROVIDER_TRACE_QUALIFICATION,
    )
    parser.add_argument(
        "--provider-trace-activation",
        type=Path,
        default=DEFAULT_PROVIDER_TRACE_ACTIVATION,
    )
    parser.add_argument(
        "--gemini-quota-snapshot",
        type=Path,
        default=DEFAULT_GEMINI_QUOTA_SNAPSHOT,
    )
    parser.add_argument(
        "--provider-trace-runtime-qualification",
        type=Path,
        default=DEFAULT_PROVIDER_TRACE_RUNTIME_QUALIFICATION,
    )
    parser.add_argument(
        "--post-pilot-review-qualification",
        type=Path,
        default=DEFAULT_POST_PILOT_REVIEW_QUALIFICATION,
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    qualification_path = (
        args.qualification
        if args.qualification.is_absolute()
        else PROJECT_ROOT / args.qualification
    )
    condition_qualification_path = (
        args.condition_qualification
        if args.condition_qualification.is_absolute()
        else PROJECT_ROOT / args.condition_qualification
    )
    record_store_qualification_path = (
        args.record_store_qualification
        if args.record_store_qualification.is_absolute()
        else PROJECT_ROOT / args.record_store_qualification
    )
    record_store_v2_qualification_path = (
        args.record_store_v2_qualification
        if args.record_store_v2_qualification.is_absolute()
        else PROJECT_ROOT / args.record_store_v2_qualification
    )
    live_runtime_qualification_path = (
        args.live_runtime_qualification
        if args.live_runtime_qualification.is_absolute()
        else PROJECT_ROOT / args.live_runtime_qualification
    )
    promptguard_qualification_path = (
        args.promptguard_qualification
        if args.promptguard_qualification.is_absolute()
        else PROJECT_ROOT / args.promptguard_qualification
    )
    agentdojo_qualification_path = (
        args.agentdojo_qualification
        if args.agentdojo_qualification.is_absolute()
        else PROJECT_ROOT / args.agentdojo_qualification
    )
    m3_evaluator_qualification_path = (
        args.m3_evaluator_qualification
        if args.m3_evaluator_qualification.is_absolute()
        else PROJECT_ROOT / args.m3_evaluator_qualification
    )
    exact_gold_qualification_path = (
        args.exact_gold_qualification
        if args.exact_gold_qualification.is_absolute()
        else PROJECT_ROOT / args.exact_gold_qualification
    )
    vigil_qualification_path = (
        args.vigil_qualification
        if args.vigil_qualification.is_absolute()
        else PROJECT_ROOT / args.vigil_qualification
    )
    provider_live_qualification_path = (
        args.provider_live_qualification
        if args.provider_live_qualification.is_absolute()
        else PROJECT_ROOT / args.provider_live_qualification
    )
    provider_live_qualification_v2_path = (
        args.provider_live_qualification_v2
        if args.provider_live_qualification_v2.is_absolute()
        else PROJECT_ROOT / args.provider_live_qualification_v2
    )
    provider_trace_policy_path = (
        args.provider_trace_policy
        if args.provider_trace_policy.is_absolute()
        else PROJECT_ROOT / args.provider_trace_policy
    )
    provider_trace_qualification_path = (
        args.provider_trace_qualification
        if args.provider_trace_qualification.is_absolute()
        else PROJECT_ROOT / args.provider_trace_qualification
    )
    provider_trace_activation_path = (
        args.provider_trace_activation
        if args.provider_trace_activation.is_absolute()
        else PROJECT_ROOT / args.provider_trace_activation
    )
    gemini_quota_snapshot_path = (
        args.gemini_quota_snapshot
        if args.gemini_quota_snapshot.is_absolute()
        else PROJECT_ROOT / args.gemini_quota_snapshot
    )
    provider_trace_runtime_qualification_path = (
        args.provider_trace_runtime_qualification
        if args.provider_trace_runtime_qualification.is_absolute()
        else PROJECT_ROOT / args.provider_trace_runtime_qualification
    )
    post_pilot_review_qualification_path = (
        args.post_pilot_review_qualification
        if args.post_pilot_review_qualification.is_absolute()
        else PROJECT_ROOT / args.post_pilot_review_qualification
    )
    output_path = (
        args.output if args.output.is_absolute() else PROJECT_ROOT / args.output
    )
    current_qualification = build_offline_transport_qualification()
    if not args.verify_only:
        qualification_path.parent.mkdir(parents=True, exist_ok=True)
        qualification_path.write_text(
            json.dumps(current_qualification, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        condition_qualification_path.parent.mkdir(
            parents=True, exist_ok=True
        )
        condition_qualification_path.write_text(
            json.dumps(
                build_condition_executor_qualification(),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        record_store_qualification_path.parent.mkdir(
            parents=True, exist_ok=True
        )
        record_store_qualification_path.write_text(
            json.dumps(
                build_record_store_qualification(),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        live_runtime_qualification_path.parent.mkdir(
            parents=True, exist_ok=True
        )
        live_runtime_qualification_path.write_text(
            json.dumps(
                build_live_runtime_qualification(),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    current = build_execution_preflight(
        qualification_path=qualification_path,
        condition_qualification_path=condition_qualification_path,
        record_store_qualification_path=record_store_qualification_path,
        record_store_v2_qualification_path=(
            record_store_v2_qualification_path
        ),
        live_runtime_qualification_path=live_runtime_qualification_path,
        promptguard_qualification_path=promptguard_qualification_path,
        agentdojo_qualification_path=agentdojo_qualification_path,
        m3_evaluator_qualification_path=m3_evaluator_qualification_path,
        exact_gold_qualification_path=exact_gold_qualification_path,
        vigil_qualification_path=vigil_qualification_path,
        provider_live_qualification_path=provider_live_qualification_path,
        provider_live_qualification_v2_path=(
            provider_live_qualification_v2_path
        ),
        provider_trace_policy_path=provider_trace_policy_path,
        provider_trace_qualification_path=(
            provider_trace_qualification_path
        ),
        provider_trace_activation_path=provider_trace_activation_path,
        gemini_quota_snapshot_path=gemini_quota_snapshot_path,
        provider_trace_runtime_qualification_path=(
            provider_trace_runtime_qualification_path
        ),
        post_pilot_review_qualification_path=(
            post_pilot_review_qualification_path
        ),
    )
    if args.verify_only:
        if _load_json(output_path) != current:
            raise ProviderExecutionGateError(
                f"{output_path}: frozen execution preflight does not reproduce"
            )
        print(
            json.dumps(
                {
                    "status": "verified",
                    "gate_pass": current["gate_pass"],
                    "network_calls_made": 0,
                },
                sort_keys=True,
            )
        )
        return 0
    output_path.write_text(
        json.dumps(current, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
