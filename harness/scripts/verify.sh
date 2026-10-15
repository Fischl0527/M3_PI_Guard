#!/usr/bin/env bash
set -eu

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-}"
REQUIRE_EXPERIMENTS_COMPLETE="${REQUIRE_EXPERIMENTS_COMPLETE:-0}"
FAILED=0

resolve_python() {
  if [ -n "$PYTHON_BIN" ]; then
    if command -v "$PYTHON_BIN" >/dev/null 2>&1 || [ -x "$PYTHON_BIN" ]; then
      return 0
    fi
    printf 'configured PYTHON_BIN is unavailable: %s\n' "$PYTHON_BIN" >&2
    return 1
  fi

  if command -v python >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python)"
  elif command -v where.exe >/dev/null 2>&1 && command -v wslpath >/dev/null 2>&1; then
    windows_python="$(where.exe python 2>/dev/null | sed -n '1{s/\r$//;p;}')"
    [ -n "$windows_python" ] || return 1
    PYTHON_BIN="$(wslpath -u "$windows_python")"
  elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
  else
    return 1
  fi

  [ -x "$PYTHON_BIN" ] || command -v "$PYTHON_BIN" >/dev/null 2>&1
}

if ! resolve_python; then
  printf '%s\n' "FAIL: unable to resolve a Python interpreter" >&2
  exit 1
fi
export PYTHON_BIN

# The focused command is also usable alone; no full verification is required.
"$PYTHON_BIN" -X utf8 -B harness/scripts/check_paths.py || exit 1

run_check() {
  name="$1"
  shift
  printf '\n== %s ==\n' "$name"
  if "$@"; then
    printf 'PASS: %s\n' "$name"
  else
    printf 'FAIL: %s\n' "$name"
    FAILED=1
  fi
}

check_files() {
  for required in \
    AGENTS.md harness/README.md \
    harness/docs/architecture.md harness/docs/development-rules.md \
    harness/docs/decision-log.md harness/docs/agent-guide.md \
    harness/state/progress.md harness/state/memory.md harness/state/current-task.md \
    harness/state/session-handoff.md harness/state/task-history.md harness/state/failure-log.md \
    harness/specs/product-spec.md harness/specs/technical-spec.md \
    harness/specs/acceptance-criteria.md harness/features/feature_list.json \
    experiments/registry.json harness/workspaces/runpro/10_analysis/approval-gate.md \
    harness/workspaces/runpro/10_analysis/requirement-ledger.md \
    harness/scripts/init.sh harness/scripts/verify.sh harness/scripts/test.sh \
    harness/scripts/cleanup.sh harness/scripts/verify.ps1 harness/scripts/test.ps1 \
    harness/config/permissions.yaml harness/config/policies.md harness/config/workflow.md \
    experiments/paper_v2/provider_safety.py experiments/paper_v2/provider_budget.py \
    experiments/paper_v2/official_provider_executor.py \
    experiments/paper_v2/provider_execution_gate.py \
    experiments/paper_v2/provider_live_qualification.py \
    experiments/paper_v2/provider_live_qualification_v2.py \
    experiments/paper_v2/provider_request_trace_candidate.py \
    experiments/paper_v2/provider_request_trace_activation.py \
    experiments/paper_v2/provider_trace_bundle.py \
    experiments/paper_v2/provider_trace_runtime_qualification.py \
    experiments/paper_v2/formal_execution_controller_v2.py \
    experiments/paper_v2/formal_matrix_controller_v1.py \
    experiments/paper_v2/deepseek_nonthinking_client_v1.py \
    experiments/paper_v2/formal_matrix_controller_v2.py \
    experiments/paper_v2/trusted_context_runtime_v2.py \
    experiments/paper_v2/formal_matrix_controller_v3.py \
    experiments/paper_v2/deepseek_json_client_v2.py \
    experiments/paper_v2/formal_matrix_controller_v4.py \
    experiments/paper_v2/boundary_rejection_runtime_v1.py \
    experiments/paper_v2/formal_matrix_controller_v5.py \
    experiments/paper_v2/formal_matrix_abort_review_v1.py \
    experiments/paper_v2/boundary_rejection_runtime_v2.py \
    experiments/paper_v2/formal_matrix_controller_v6.py \
    experiments/paper_v2/formal_result_gate_v1.py \
    experiments/paper_v2/formal_result_gate_v2.py \
    experiments/paper_v2/formal_result_gate_v3.py \
    experiments/paper_v2/formal_matrix_abort_review_v2.py \
    experiments/paper_v2/boundary_rejection_runtime_v3.py \
    experiments/paper_v2/formal_matrix_controller_v7.py \
    experiments/paper_v2/formal_result_gate_v4.py \
    experiments/paper_v2/formal_matrix_abort_review_v3.py \
    experiments/paper_v2/formal_matrix_controller_v8.py \
    experiments/paper_v2/formal_result_gate_v5.py \
    experiments/paper_v2/formal_matrix_remainder_controller_v9.py \
    experiments/paper_v2/formal_result_gate_v6.py \
    experiments/paper_v2/medium_analysis_v4.py \
    experiments/paper_v2/medium_analysis_v5.py \
    experiments/paper_v2/formal_analysis_amendment_v7.py \
    experiments/paper_v2/formal_analysis_amendment_v8.py \
    experiments/paper_v2/gemini_evidence_store_v1.py \
    experiments/paper_v2/gemini_fallback_controller_v1.py \
    experiments/paper_v2/experiment_closeout_freeze_v1.py \
    experiments/paper_v2/experiment_closeout_day1_harness_review_v1.py \
    experiments/paper_v2/gemini_daily_quota_ledger_v1.py \
    experiments/paper_v2/gemini_free_tier_duration_qualification_v1.py \
    experiments/paper_v2/gemini_public_controller_v4.py \
    experiments/paper_v2/gemini_public_continuation_plan_v1.py \
    experiments/paper_v2/gemini_public_continuation_controller_v1.py \
    experiments/paper_v2/gemini_adaptive_quota_schedule_v1.py \
    experiments/paper_v2/gemini_adaptive_query_store_v1.py \
    experiments/paper_v2/gemini_adaptive_daily_controller_v1.py \
    experiments/paper_v2/gemini_trace_attaching_runtime_v1.py \
    experiments/paper_v2/adaptive_formal_plan_v2.py \
    experiments/paper_v2/adaptive_formal_second_plan_v1.py \
    experiments/paper_v2/adaptive_formal_pro_controller_v1.py \
    experiments/paper_v2/adaptive_formal_deepseek_flash_controller_v1.py \
    experiments/paper_v2/independent_blind_closeout_v1.py \
    experiments/paper_v2/medium_analysis_v2.py \
    experiments/paper_v2/medium_analysis_v3.py \
    experiments/paper_v2/gemini_quota_snapshot.py \
    experiments/paper_v2/contracts_v2.py \
    experiments/paper_v2/formal_condition_executors.py \
    experiments/paper_v2/formal_record_store.py \
    experiments/paper_v2/formal_record_store_v2.py \
    experiments/paper_v2/live_condition_runtime.py \
    experiments/paper_v2/promptguard_live_dependency.py \
    experiments/paper_v2/agentdojo_live_dependency.py \
    experiments/paper_v2/m3_offline_evaluator.py \
    experiments/paper_v2/exact_gold_ablation.py \
    experiments/paper_v2/vigil_live_dependency.py \
    experiments/paper_v2/medium_runtime.py \
    experiments/paper_v2/citation_integrity.py \
    protocols/paper_upgrade_v2/provider_safety_policy_v1.json \
    protocols/paper_upgrade_v2/dual_provider_budget_policy_v1.json \
    protocols/paper_upgrade_v2/dual_provider_budget_policy_v2.json \
    protocols/paper_upgrade_v2/gemini_fallback_plan_v1.jsonl \
    protocols/paper_upgrade_v2/gemini_fallback_budget_override_v1.json \
    protocols/paper_upgrade_v2/gemini_fallback_controller_qualification_v1.json \
    protocols/paper_upgrade_v2/gemini_fallback_candidate_v1.json \
    protocols/paper_upgrade_v2/admissions/gemini_fallback_canary_admission_v1.json \
    protocols/paper_upgrade_v2/provider_budget_authorization_v3.json \
    protocols/paper_upgrade_v2/dual_provider_budget_preflight_v1.json \
    protocols/paper_upgrade_v2/provider_executor_qualification_v1.json \
    protocols/paper_upgrade_v2/formal_matrix_controller_qualification_v1.json \
    protocols/paper_upgrade_v2/deepseek_medium_matrix_candidate_v1.json \
    protocols/paper_upgrade_v2/deepseek_nonthinking_client_qualification_v1.json \
    protocols/paper_upgrade_v2/formal_matrix_controller_qualification_v2.json \
    protocols/paper_upgrade_v2/deepseek_medium_matrix_candidate_v2.json \
    protocols/paper_upgrade_v2/formal_matrix_controller_qualification_v3.json \
    protocols/paper_upgrade_v2/deepseek_medium_matrix_candidate_v3.json \
    protocols/paper_upgrade_v2/admissions/deepseek_medium_matrix_canary_admission_v3.json \
    protocols/paper_upgrade_v2/deepseek_json_client_qualification_v2.json \
    protocols/paper_upgrade_v2/formal_matrix_controller_qualification_v4.json \
    protocols/paper_upgrade_v2/deepseek_medium_matrix_candidate_v4.json \
    protocols/paper_upgrade_v2/admissions/deepseek_medium_matrix_canary_admission_v4.json \
    protocols/paper_upgrade_v2/admissions/deepseek_medium_matrix_continuation_admission_v4.json \
    outputs/paper_upgrade_v2/formal_medium/deepseek/dd794dd88eade41166bdafb7cb191898d7d19a5d8df737340f6acc3daac4504f/formal_result_technical_review_v1.json \
    protocols/paper_upgrade_v2/formal_matrix_controller_qualification_v5.json \
    protocols/paper_upgrade_v2/deepseek_medium_matrix_candidate_v5.json \
    protocols/paper_upgrade_v2/admissions/deepseek_medium_matrix_canary_admission_v5.json \
    protocols/paper_upgrade_v2/admissions/deepseek_medium_matrix_continuation_admission_v5.json \
    outputs/paper_upgrade_v2/formal_medium/deepseek/62eb641043a2fc50cbaac439b047de5c433c38b20ff9c06d8ff6d92dd71f90ae/six_condition_canary_review_v5.json \
    outputs/paper_upgrade_v2/formal_medium/deepseek/62eb641043a2fc50cbaac439b047de5c433c38b20ff9c06d8ff6d92dd71f90ae/formal_matrix_abort_review_v1.json \
    protocols/paper_upgrade_v2/formal_matrix_controller_qualification_v6.json \
    protocols/paper_upgrade_v2/deepseek_medium_matrix_candidate_v6.json \
    protocols/paper_upgrade_v2/admissions/deepseek_medium_matrix_canary_admission_v6.json \
    protocols/paper_upgrade_v2/admissions/deepseek_medium_matrix_continuation_admission_v6.json \
    outputs/paper_upgrade_v2/formal_medium/deepseek/6c16117e0451a01dd20409f60395035c110e5eb7c0be078d386a0e138e4fb2f9/six_condition_canary_review_v6.json \
    protocols/paper_upgrade_v2/formal_result_gate_qualification_v3.json \
    protocols/paper_upgrade_v2/deepseek_medium_result_gate_candidate_v3.json \
    outputs/paper_upgrade_v2/formal_medium/deepseek/6c16117e0451a01dd20409f60395035c110e5eb7c0be078d386a0e138e4fb2f9/formal_matrix_abort_review_v2.json \
    protocols/paper_upgrade_v2/formal_matrix_controller_qualification_v7.json \
    protocols/paper_upgrade_v2/deepseek_medium_matrix_candidate_v7.json \
    protocols/paper_upgrade_v2/admissions/deepseek_medium_matrix_canary_admission_v7.json \
    outputs/paper_upgrade_v2/formal_medium/deepseek/a34fe5b87607cb48144b0d36da282accc25d33cd18706351eb39dd25ebe04c75/formal_matrix_abort_review_v3.json \
    protocols/paper_upgrade_v2/formal_matrix_controller_qualification_v8.json \
    protocols/paper_upgrade_v2/deepseek_medium_matrix_candidate_v8.json \
    protocols/paper_upgrade_v2/admissions/deepseek_medium_matrix_canary_admission_v8.json \
    protocols/paper_upgrade_v2/formal_result_gate_qualification_v5.json \
    outputs/paper_upgrade_v2/formal_medium/deepseek/8d08cab3febccdf5a4360d208766c39cef851fa9ec8b9c15799ee30171a213bf/six_condition_canary_review_v8.json \
    protocols/paper_upgrade_v2/deepseek_medium_result_gate_candidate_v5.json \
    protocols/paper_upgrade_v2/admissions/deepseek_medium_matrix_continuation_admission_v8.json \
    protocols/paper_upgrade_v2/formal_matrix_remainder_qualification_v9.json \
    protocols/paper_upgrade_v2/deepseek_medium_remainder_candidate_v9.json \
    protocols/paper_upgrade_v2/admissions/deepseek_medium_remainder_admission_v9.json \
    protocols/paper_upgrade_v2/formal_result_gate_qualification_v6.json \
    protocols/paper_upgrade_v2/deepseek_medium_combined_result_gate_candidate_v6.json \
    protocols/paper_upgrade_v2/admissions/deepseek_medium_combined_result_admission_v6.json \
    protocols/paper_upgrade_v2/formal_analysis_amendment_qualification_v7.json \
    protocols/paper_upgrade_v2/deepseek_medium_analysis_amendment_candidate_v7.json \
    protocols/paper_upgrade_v2/formal_analysis_amendment_qualification_v8.json \
    protocols/paper_upgrade_v2/deepseek_medium_analysis_amendment_candidate_v8.json \
    outputs/paper_upgrade_v2/formal_medium/deepseek/ba9c7937d08b68e088faf8586e0dd96d2052a398fd0a77889fd6a62e503f2373/formal_result_technical_review_v6.json \
    outputs/paper_upgrade_v2/formal_medium/deepseek/ba9c7937d08b68e088faf8586e0dd96d2052a398fd0a77889fd6a62e503f2373/admitted_medium_analysis_v8.json \
    protocols/paper_upgrade_v2/formal_result_gate_qualification_v1.json \
    protocols/paper_upgrade_v2/deepseek_medium_result_gate_candidate_v1.json \
    protocols/paper_upgrade_v2/formal_result_gate_qualification_v2.json \
    protocols/paper_upgrade_v2/deepseek_medium_result_gate_candidate_v2.json \
    protocols/paper_upgrade_v2/superseded_result_gate_candidate_review_v1.json \
    protocols/paper_upgrade_v2/superseded_result_gate_candidate_review_v2.json \
    protocols/paper_upgrade_v2/superseded_result_gate_candidate_review_v3.json \
    protocols/paper_upgrade_v2/superseded_result_gate_candidate_review_v4.json \
    protocols/paper_upgrade_v2/superseded_result_gate_candidate_review_v5.json \
    protocols/paper_upgrade_v2/medium_execution_manifest_v3_preflight.json \
    protocols/paper_upgrade_v2/formal_condition_executor_qualification_v1.json \
    protocols/paper_upgrade_v2/formal_record_store_qualification_v1.json \
    protocols/paper_upgrade_v2/formal_record_store_qualification_v2.json \
    protocols/paper_upgrade_v2/live_condition_runtime_qualification_v1.json \
    protocols/paper_upgrade_v2/promptguard_live_dependency_qualification_v1.json \
    protocols/paper_upgrade_v2/agentdojo_live_dependency_qualification_v1.json \
    protocols/paper_upgrade_v2/m3_offline_evaluator_qualification_v1.json \
    protocols/paper_upgrade_v2/exact_gold_ablation_qualification_v1.json \
    protocols/paper_upgrade_v2/vigil_live_dependency_qualification_v1.json \
    protocols/paper_upgrade_v2/provider_live_qualification_v1.json \
    protocols/paper_upgrade_v2/provider_live_qualification_v2.json \
    outputs/paper_upgrade_v2/provider_identity/deepseek_request_trace_v2.jsonl \
    protocols/paper_upgrade_v2/provider_request_trace_policy_v2_candidate.json \
    protocols/paper_upgrade_v2/provider_request_trace_v2_qualification.json \
    protocols/paper_upgrade_v2/provider_request_trace_activation_v2.json \
    protocols/paper_upgrade_v2/gemini_quota_snapshot_v1.json \
    protocols/paper_upgrade_v2/provider_trace_runtime_qualification_v2.json \
    protocols/paper_upgrade_v2/deepseek_pilot_admission_candidate_v2.json \
    protocols/paper_upgrade_v2/formal_execution_controller_qualification_v2.json \
    protocols/paper_upgrade_v2/medium_execution_manifest_v2.json \
    protocols/paper_upgrade_v2/medium_execution_plan_v2.jsonl \
    protocols/paper_upgrade_v2/citation_integrity_manifest_v1.json \
    protocols/paper_upgrade_v2/evidence_80_execution_roadmap_v3.json \
    experiments/paper_v2/public_abort_review_v1.py \
    experiments/paper_v2/public_abort_review_v2.py \
    experiments/paper_v2/public_agentdojo_live_dependency_v2.py \
    experiments/paper_v2/public_matrix_controller_v2.py \
    experiments/paper_v2/public_live_controller_v2.py \
    experiments/paper_v2/public_m3_live_dependency_v3.py \
    experiments/paper_v2/public_matrix_controller_v3.py \
    experiments/paper_v2/public_live_controller_v3.py \
    experiments/paper_v2/public_abort_review_v3.py \
    experiments/paper_v2/public_m3_live_dependency_v4.py \
    experiments/paper_v2/public_matrix_controller_v4.py \
    experiments/paper_v2/public_live_controller_v4.py \
    experiments/paper_v2/public_sharded_continuation_v1.py \
    protocols/paper_upgrade_v2/public_primary_canary_abort_review_v1.json \
    protocols/paper_upgrade_v2/public_primary_canary_abort_review_v2.json \
    protocols/paper_upgrade_v2/admissions/deepseek_public_primary_canary_admission_v2.json \
    protocols/paper_upgrade_v2/public_agentdojo_live_dependency_qualification_v2.json \
    protocols/paper_upgrade_v2/public_matrix_controller_qualification_v2.json \
    protocols/paper_upgrade_v2/public_matrix_candidate_v2.json \
    protocols/paper_upgrade_v2/public_m3_live_dependency_qualification_v3.json \
    protocols/paper_upgrade_v2/public_matrix_controller_qualification_v3.json \
    protocols/paper_upgrade_v2/public_matrix_candidate_v3.json \
    protocols/paper_upgrade_v2/public_primary_canary_abort_review_v3.json \
    protocols/paper_upgrade_v2/public_m3_live_dependency_qualification_v4.json \
    protocols/paper_upgrade_v2/public_matrix_controller_qualification_v4.json \
    protocols/paper_upgrade_v2/public_matrix_candidate_v4.json \
    protocols/paper_upgrade_v2/public_primary_continuation_candidate_v1.json \
    protocols/paper_upgrade_v2/experiment_closeout_candidate_v1.json \
    protocols/paper_upgrade_v2/formal_matrix_v7_immutable_audit_v1.json \
    protocols/paper_upgrade_v2/experiment_closeout_day1_harness_review_v1.json \
    protocols/paper_upgrade_v2/gemini_public_canary_candidate_v4.json \
    protocols/paper_upgrade_v2/gemini_free_tier_duration_qualification_v1.json \
    protocols/paper_upgrade_v2/gemini_public_continuation_candidate_v1.json \
    protocols/paper_upgrade_v2/gemini_adaptive_quota_candidate_v1.json \
    schemas/paper_v2/public_matrix_candidate_v2.schema.json \
    schemas/paper_v2/public_matrix_admission_v2.schema.json \
    schemas/paper_v2/public_matrix_candidate_v3.schema.json \
    schemas/paper_v2/public_matrix_admission_v3.schema.json \
    schemas/paper_v2/public_matrix_candidate_v4.schema.json \
    schemas/paper_v2/public_matrix_admission_v4.schema.json \
    schemas/paper_v2/public_sharded_continuation_candidate_v1.schema.json \
    schemas/paper_v2/public_sharded_continuation_admission_v1.schema.json
  do
    [ -f "$required" ] || { printf 'missing %s\n' "$required"; return 1; }
  done
}

check_boundary() {
  for legacy in \
    README_AGENT.md .agent features specs tasks runpro_workspace \
    agent/current-task.md agent/failure-log.md agent/memory.md agent/progress.md \
    agent/session-handoff.md agent/task-history.md
  do
    [ ! -e "$legacy" ] || { printf 'legacy Harness path remains: %s\n' "$legacy"; return 1; }
  done
  for project_dir in \
    m3_core m3_guard m3_eval m3_attacks experiments protocols schemas fixtures tests scripts
  do
    [ -d "$project_dir" ] || { printf 'missing project source directory: %s\n' "$project_dir"; return 1; }
  done
}

validate_json() {
  "$PYTHON_BIN" - <<'PY'
import json
from pathlib import Path

for path in [
    Path("harness/features/feature_list.json"),
    Path("experiments/registry.json"),
    Path("protocols/paper_upgrade_v2/provider_safety_policy_v1.json"),
    Path("protocols/paper_upgrade_v2/dual_provider_budget_policy_v1.json"),
    Path("protocols/paper_upgrade_v2/dual_provider_budget_policy_v2.json"),
    Path("protocols/paper_upgrade_v2/provider_budget_authorization_v3.json"),
    Path("protocols/paper_upgrade_v2/formal_matrix_controller_qualification_v5.json"),
    Path("protocols/paper_upgrade_v2/deepseek_medium_matrix_candidate_v5.json"),
    Path("protocols/paper_upgrade_v2/admissions/deepseek_medium_matrix_canary_admission_v5.json"),
    Path("protocols/paper_upgrade_v2/admissions/deepseek_medium_matrix_continuation_admission_v5.json"),
    Path("outputs/paper_upgrade_v2/formal_medium/deepseek/62eb641043a2fc50cbaac439b047de5c433c38b20ff9c06d8ff6d92dd71f90ae/six_condition_canary_review_v5.json"),
    Path("outputs/paper_upgrade_v2/formal_medium/deepseek/62eb641043a2fc50cbaac439b047de5c433c38b20ff9c06d8ff6d92dd71f90ae/formal_matrix_abort_review_v1.json"),
    Path("protocols/paper_upgrade_v2/formal_matrix_controller_qualification_v6.json"),
    Path("protocols/paper_upgrade_v2/deepseek_medium_matrix_candidate_v6.json"),
    Path("protocols/paper_upgrade_v2/admissions/deepseek_medium_matrix_canary_admission_v6.json"),
    Path("protocols/paper_upgrade_v2/admissions/deepseek_medium_matrix_continuation_admission_v6.json"),
    Path("outputs/paper_upgrade_v2/formal_medium/deepseek/6c16117e0451a01dd20409f60395035c110e5eb7c0be078d386a0e138e4fb2f9/six_condition_canary_review_v6.json"),
    Path("protocols/paper_upgrade_v2/formal_result_gate_qualification_v3.json"),
    Path("protocols/paper_upgrade_v2/deepseek_medium_result_gate_candidate_v3.json"),
    Path("outputs/paper_upgrade_v2/formal_medium/deepseek/6c16117e0451a01dd20409f60395035c110e5eb7c0be078d386a0e138e4fb2f9/formal_matrix_abort_review_v2.json"),
    Path("protocols/paper_upgrade_v2/formal_matrix_controller_qualification_v7.json"),
    Path("protocols/paper_upgrade_v2/deepseek_medium_matrix_candidate_v7.json"),
    Path("protocols/paper_upgrade_v2/admissions/deepseek_medium_matrix_canary_admission_v7.json"),
    Path("protocols/paper_upgrade_v2/formal_result_gate_qualification_v4.json"),
    Path("outputs/paper_upgrade_v2/formal_medium/deepseek/a34fe5b87607cb48144b0d36da282accc25d33cd18706351eb39dd25ebe04c75/formal_matrix_abort_review_v3.json"),
    Path("protocols/paper_upgrade_v2/formal_matrix_controller_qualification_v8.json"),
    Path("protocols/paper_upgrade_v2/deepseek_medium_matrix_candidate_v8.json"),
    Path("protocols/paper_upgrade_v2/admissions/deepseek_medium_matrix_canary_admission_v8.json"),
    Path("protocols/paper_upgrade_v2/formal_result_gate_qualification_v5.json"),
    Path("outputs/paper_upgrade_v2/formal_medium/deepseek/8d08cab3febccdf5a4360d208766c39cef851fa9ec8b9c15799ee30171a213bf/six_condition_canary_review_v8.json"),
    Path("protocols/paper_upgrade_v2/deepseek_medium_result_gate_candidate_v5.json"),
    Path("protocols/paper_upgrade_v2/admissions/deepseek_medium_matrix_continuation_admission_v8.json"),
    Path("protocols/paper_upgrade_v2/formal_matrix_remainder_qualification_v9.json"),
    Path("protocols/paper_upgrade_v2/deepseek_medium_remainder_candidate_v9.json"),
    Path("protocols/paper_upgrade_v2/admissions/deepseek_medium_remainder_admission_v9.json"),
    Path("protocols/paper_upgrade_v2/formal_result_gate_qualification_v6.json"),
    Path("protocols/paper_upgrade_v2/deepseek_medium_combined_result_gate_candidate_v6.json"),
    Path("protocols/paper_upgrade_v2/admissions/deepseek_medium_combined_result_admission_v6.json"),
    Path("protocols/paper_upgrade_v2/formal_analysis_amendment_qualification_v7.json"),
    Path("protocols/paper_upgrade_v2/deepseek_medium_analysis_amendment_candidate_v7.json"),
    Path("protocols/paper_upgrade_v2/formal_analysis_amendment_qualification_v8.json"),
    Path("protocols/paper_upgrade_v2/deepseek_medium_analysis_amendment_candidate_v8.json"),
    Path("outputs/paper_upgrade_v2/formal_medium/deepseek/ba9c7937d08b68e088faf8586e0dd96d2052a398fd0a77889fd6a62e503f2373/formal_result_technical_review_v6.json"),
    Path("outputs/paper_upgrade_v2/formal_medium/deepseek/ba9c7937d08b68e088faf8586e0dd96d2052a398fd0a77889fd6a62e503f2373/admitted_medium_analysis_v8.json"),
    Path("protocols/paper_upgrade_v2/formal_result_gate_qualification_v2.json"),
    Path("protocols/paper_upgrade_v2/deepseek_medium_result_gate_candidate_v2.json"),
    Path("protocols/paper_upgrade_v2/medium_gate_spec_v2.json"),
    Path("outputs/paper_upgrade_v2/formal_medium/deepseek/dd794dd88eade41166bdafb7cb191898d7d19a5d8df737340f6acc3daac4504f/formal_result_technical_review_v1.json"),
    Path("protocols/paper_upgrade_v2/dual_provider_budget_preflight_v1.json"),
    Path("protocols/paper_upgrade_v2/provider_executor_qualification_v1.json"),
    Path("protocols/paper_upgrade_v2/formal_condition_executor_qualification_v1.json"),
    Path("protocols/paper_upgrade_v2/formal_record_store_qualification_v1.json"),
    Path("protocols/paper_upgrade_v2/formal_record_store_qualification_v2.json"),
    Path("protocols/paper_upgrade_v2/live_condition_runtime_qualification_v1.json"),
    Path("protocols/paper_upgrade_v2/promptguard_live_dependency_qualification_v1.json"),
    Path("protocols/paper_upgrade_v2/agentdojo_live_dependency_qualification_v1.json"),
    Path("protocols/paper_upgrade_v2/m3_offline_evaluator_qualification_v1.json"),
    Path("protocols/paper_upgrade_v2/exact_gold_ablation_qualification_v1.json"),
    Path("protocols/paper_upgrade_v2/vigil_live_dependency_qualification_v1.json"),
    Path("protocols/paper_upgrade_v2/provider_live_qualification_v1.json"),
    Path("protocols/paper_upgrade_v2/provider_live_qualification_v2.json"),
    Path("protocols/paper_upgrade_v2/provider_request_trace_policy_v2_candidate.json"),
    Path("protocols/paper_upgrade_v2/provider_request_trace_v2_qualification.json"),
    Path("protocols/paper_upgrade_v2/provider_request_trace_activation_v2.json"),
    Path("protocols/paper_upgrade_v2/gemini_quota_snapshot_v1.json"),
    Path("protocols/paper_upgrade_v2/provider_trace_runtime_qualification_v2.json"),
    Path("protocols/paper_upgrade_v2/deepseek_pilot_admission_candidate_v2.json"),
    Path("protocols/paper_upgrade_v2/formal_execution_controller_qualification_v2.json"),
    Path("protocols/paper_upgrade_v2/medium_execution_manifest_v3_preflight.json"),
    Path("protocols/paper_upgrade_v2/medium_execution_manifest_v2.json"),
    Path("protocols/paper_upgrade_v2/citation_integrity_manifest_v1.json"),
    Path("protocols/paper_upgrade_v2/evidence_80_execution_roadmap_v3.json"),
    Path("schemas/attack_case.schema.json"),
    Path("schemas/run_log.schema.json"),
    Path("schemas/tool_call.schema.json"),
    Path("schemas/paper_v2/provider_trace_attestation_v2.schema.json"),
    Path("schemas/paper_v2/provider_trace_bundle_v2.schema.json"),
    Path("schemas/paper_v2/pilot_admission_manifest_v2.schema.json"),
    Path("schemas/paper_v2/formal_matrix_admission_v1.schema.json"),
    Path("schemas/paper_v2/formal_matrix_admission_v2.schema.json"),
    Path("schemas/paper_v2/formal_matrix_admission_v3.schema.json"),
    Path("schemas/paper_v2/formal_matrix_admission_v4.schema.json"),
    Path("schemas/paper_v2/formal_matrix_admission_v5.schema.json"),
    Path("schemas/paper_v2/formal_matrix_admission_v6.schema.json"),
    Path("schemas/paper_v2/formal_result_gate_v1.schema.json"),
    Path("schemas/paper_v2/formal_result_gate_v2.schema.json"),
    Path("schemas/paper_v2/formal_result_gate_v3.schema.json"),
    Path("schemas/paper_v2/formal_result_gate_v4.schema.json"),
    Path("schemas/paper_v2/formal_matrix_admission_v7.schema.json"),
    Path("schemas/paper_v2/formal_matrix_admission_v8.schema.json"),
    Path("schemas/paper_v2/formal_result_gate_v5.schema.json"),
    Path("schemas/paper_v2/formal_matrix_remainder_admission_v9.schema.json"),
    Path("schemas/paper_v2/formal_result_gate_v6.schema.json"),
    Path("schemas/paper_v2/formal_analysis_amendment_v7.schema.json"),
    Path("schemas/paper_v2/formal_analysis_amendment_v8.schema.json"),
    Path("schemas/paper_v2/gemini_fallback_admission_v1.schema.json"),
    Path("schemas/paper_v2/experiment_record_v2.schema.json"),
    Path("protocols/paper_upgrade_v2/public_primary_canary_abort_review_v1.json"),
    Path("protocols/paper_upgrade_v2/public_primary_canary_abort_review_v2.json"),
    Path("protocols/paper_upgrade_v2/admissions/deepseek_public_primary_canary_admission_v2.json"),
    Path("protocols/paper_upgrade_v2/public_agentdojo_live_dependency_qualification_v2.json"),
    Path("protocols/paper_upgrade_v2/public_matrix_controller_qualification_v2.json"),
    Path("protocols/paper_upgrade_v2/public_matrix_candidate_v2.json"),
    Path("protocols/paper_upgrade_v2/public_m3_live_dependency_qualification_v3.json"),
    Path("protocols/paper_upgrade_v2/public_matrix_controller_qualification_v3.json"),
    Path("protocols/paper_upgrade_v2/public_matrix_candidate_v3.json"),
    Path("protocols/paper_upgrade_v2/public_primary_canary_abort_review_v3.json"),
    Path("protocols/paper_upgrade_v2/public_m3_live_dependency_qualification_v4.json"),
    Path("protocols/paper_upgrade_v2/public_matrix_controller_qualification_v4.json"),
    Path("protocols/paper_upgrade_v2/public_matrix_candidate_v4.json"),
    Path("protocols/paper_upgrade_v2/public_primary_continuation_candidate_v1.json"),
    Path("protocols/paper_upgrade_v2/experiment_closeout_candidate_v1.json"),
    Path("protocols/paper_upgrade_v2/formal_matrix_v7_immutable_audit_v1.json"),
    Path("protocols/paper_upgrade_v2/experiment_closeout_day1_harness_review_v1.json"),
    Path("protocols/paper_upgrade_v2/gemini_public_canary_candidate_v4.json"),
    Path("protocols/paper_upgrade_v2/gemini_free_tier_duration_qualification_v1.json"),
    Path("protocols/paper_upgrade_v2/gemini_public_continuation_candidate_v1.json"),
    Path("protocols/paper_upgrade_v2/gemini_adaptive_quota_candidate_v1.json"),
    Path("schemas/paper_v2/public_matrix_candidate_v2.schema.json"),
    Path("schemas/paper_v2/public_matrix_admission_v2.schema.json"),
    Path("schemas/paper_v2/public_matrix_candidate_v3.schema.json"),
    Path("schemas/paper_v2/public_matrix_admission_v3.schema.json"),
    Path("schemas/paper_v2/public_matrix_candidate_v4.schema.json"),
    Path("schemas/paper_v2/public_matrix_admission_v4.schema.json"),
    Path("schemas/paper_v2/public_sharded_continuation_candidate_v1.schema.json"),
    Path("schemas/paper_v2/public_sharded_continuation_admission_v1.schema.json"),
]:
    json.loads(path.read_text(encoding="utf-8"))
    print(f"parsed {path}")
PY
}

run_check "Harness files" check_files
run_check "Harness and project source boundary" check_boundary
run_check "JSON contracts" validate_json
run_check "Shell syntax" bash -n harness/scripts/init.sh harness/scripts/verify.sh harness/scripts/test.sh harness/scripts/cleanup.sh
run_check "Python compile" "$PYTHON_BIN" -m compileall -q m3_core m3_guard m3_attacks m3_eval experiments tests
run_check "Unit and integration tests" bash harness/scripts/test.sh
run_check "Experiment registry structure" "$PYTHON_BIN" -m experiments.validate_registry
run_check "Paper-v2 dual-provider budget fuse" "$PYTHON_BIN" -m experiments.paper_v2.provider_budget --verify-only
run_check "Paper-v2 official-provider execution preflight" "$PYTHON_BIN" -m experiments.paper_v2.provider_execution_gate --verify-only
run_check "Paper-v2 live provider identity evidence" "$PYTHON_BIN" -m experiments.paper_v2.provider_live_qualification --verify-only
run_check "Paper-v2 DeepSeek live v2 trace evidence" "$PYTHON_BIN" -m experiments.paper_v2.provider_live_qualification_v2 --verify-only
run_check "Paper-v2 provider request-trace candidate" "$PYTHON_BIN" -m experiments.paper_v2.provider_request_trace_candidate --verify-only
run_check "Paper-v2 provider request-trace activation" "$PYTHON_BIN" -m experiments.paper_v2.provider_request_trace_activation --verify-only
run_check "Paper-v2 live per-call request-trace v2" "$PYTHON_BIN" -m experiments.paper_v2.provider_trace_runtime_qualification --verify-only
run_check "Paper-v2 DeepSeek pilot admission candidate" "$PYTHON_BIN" -m experiments.paper_v2.formal_execution_controller_v2 --verify-candidate
run_check "Paper-v2 single-pilot execution controller" "$PYTHON_BIN" -m experiments.paper_v2.formal_execution_controller_v2 --verify-qualification
run_check "Paper-v2 medium-matrix execution controller" "$PYTHON_BIN" -m experiments.paper_v2.formal_matrix_controller_v1 --verify-qualification
run_check "Paper-v2 medium-matrix admission candidate" "$PYTHON_BIN" -m experiments.paper_v2.formal_matrix_controller_v1 --verify-candidate
run_check "Paper-v2 DeepSeek non-thinking client" "$PYTHON_BIN" -m experiments.paper_v2.deepseek_nonthinking_client_v1 --verify-only
run_check "Paper-v2 replacement matrix controller" "$PYTHON_BIN" -m experiments.paper_v2.formal_matrix_controller_v2 --verify-qualification
run_check "Paper-v2 replacement matrix candidate" "$PYTHON_BIN" -m experiments.paper_v2.formal_matrix_controller_v2 --verify-candidate
run_check "Paper-v2 trusted-context matrix controller" "$PYTHON_BIN" -m experiments.paper_v2.formal_matrix_controller_v3 --verify-qualification
run_check "Paper-v2 trusted-context matrix candidate" "$PYTHON_BIN" -m experiments.paper_v2.formal_matrix_controller_v3 --verify-candidate
run_check "Paper-v2 trusted-context canary admission" "$PYTHON_BIN" -m experiments.paper_v2.formal_matrix_controller_v3 --verify-canary-admission
run_check "Paper-v2 DeepSeek JSON Output client" "$PYTHON_BIN" -m experiments.paper_v2.deepseek_json_client_v2 --verify-only
run_check "Paper-v2 JSON Output matrix controller" "$PYTHON_BIN" -m experiments.paper_v2.formal_matrix_controller_v4 --verify-qualification
run_check "Paper-v2 JSON Output matrix candidate" "$PYTHON_BIN" -m experiments.paper_v2.formal_matrix_controller_v4 --verify-candidate
run_check "Paper-v2 JSON Output canary admission" "$PYTHON_BIN" -m experiments.paper_v2.formal_matrix_controller_v4 --verify-canary-admission
run_check "Paper-v2 JSON Output continuation admission" "$PYTHON_BIN" -m experiments.paper_v2.formal_matrix_controller_v4 --verify-continuation-admission
run_check "Paper-v2 boundary-aware matrix controller" "$PYTHON_BIN" -m experiments.paper_v2.formal_matrix_controller_v5 --verify-qualification
run_check "Paper-v2 boundary-aware matrix candidate" "$PYTHON_BIN" -m experiments.paper_v2.formal_matrix_controller_v5 --verify-candidate
run_check "Paper-v2 boundary-aware canary admission" "$PYTHON_BIN" -m experiments.paper_v2.formal_matrix_controller_v5 --verify-canary-admission
run_check "Paper-v2 boundary-aware continuation admission" "$PYTHON_BIN" -m experiments.paper_v2.formal_matrix_controller_v5 --verify-continuation-admission
run_check "Paper-v2 aborted v5 technical review" "$PYTHON_BIN" -m experiments.paper_v2.formal_matrix_abort_review_v1
run_check "Paper-v2 proposal-effect matrix controller" "$PYTHON_BIN" -m experiments.paper_v2.formal_matrix_controller_v6 --verify-qualification
run_check "Paper-v2 proposal-effect matrix candidate" "$PYTHON_BIN" -m experiments.paper_v2.formal_matrix_controller_v6 --verify-candidate
run_check "Paper-v2 proposal-effect canary admission" "$PYTHON_BIN" -m experiments.paper_v2.formal_matrix_controller_v6 --verify-canary-admission
run_check "Paper-v2 proposal-effect continuation admission" "$PYTHON_BIN" -m experiments.paper_v2.formal_matrix_controller_v6 --verify-continuation-admission
run_check "Paper-v2 formal result gate qualification" "$PYTHON_BIN" -m experiments.paper_v2.formal_result_gate_v1 --verify-qualification
run_check "Paper-v2 prospective formal result gate" "$PYTHON_BIN" -m experiments.paper_v2.formal_result_gate_v1 --verify-candidate
run_check "Paper-v2 formal result gate v2 qualification" "$PYTHON_BIN" -m experiments.paper_v2.formal_result_gate_v2 --verify-qualification
run_check "Paper-v2 prospective formal result gate v2" "$PYTHON_BIN" -m experiments.paper_v2.formal_result_gate_v2 --verify-candidate
run_check "Paper-v2 formal result gate v3 qualification" "$PYTHON_BIN" -m experiments.paper_v2.formal_result_gate_v3 --verify-qualification
run_check "Paper-v2 prospective formal result gate v3" "$PYTHON_BIN" -m experiments.paper_v2.formal_result_gate_v3 --verify-candidate
run_check "Paper-v2 aborted v6 technical review" "$PYTHON_BIN" -m experiments.paper_v2.formal_matrix_abort_review_v2
run_check "Paper-v2 end-to-end boundary controller" "$PYTHON_BIN" -m experiments.paper_v2.formal_matrix_controller_v7 --verify-qualification
run_check "Paper-v2 end-to-end boundary candidate" "$PYTHON_BIN" -m experiments.paper_v2.formal_matrix_controller_v7 --verify-candidate
run_check "Paper-v2 end-to-end boundary canary admission" "$PYTHON_BIN" -m experiments.paper_v2.formal_matrix_controller_v7 --verify-canary-admission
run_check "Paper-v2 formal result gate v4 pre-canary freeze" "$PYTHON_BIN" -m experiments.paper_v2.formal_result_gate_v4 --verify-qualification
run_check "Paper-v2 aborted v7 technical review" "$PYTHON_BIN" -m experiments.paper_v2.formal_matrix_abort_review_v3
run_check "Paper-v2 lifecycle-bound boundary controller" "$PYTHON_BIN" -m experiments.paper_v2.formal_matrix_controller_v8 --verify-qualification
run_check "Paper-v2 lifecycle-bound boundary candidate" "$PYTHON_BIN" -m experiments.paper_v2.formal_matrix_controller_v8 --verify-candidate
run_check "Paper-v2 lifecycle-bound boundary canary admission" "$PYTHON_BIN" -m experiments.paper_v2.formal_matrix_controller_v8 --verify-canary-admission
run_check "Paper-v2 formal result gate v5 pre-canary freeze" "$PYTHON_BIN" -m experiments.paper_v2.formal_result_gate_v5 --verify-qualification
run_check "Paper-v2 lifecycle-bound continuation admission" "$PYTHON_BIN" -m experiments.paper_v2.formal_matrix_controller_v8 --verify-continuation-admission
run_check "Paper-v2 prospective formal result gate v5" "$PYTHON_BIN" -m experiments.paper_v2.formal_result_gate_v5 --verify-candidate
run_check "Paper-v2 pending-only remainder controller v9" "$PYTHON_BIN" -m experiments.paper_v2.formal_matrix_remainder_controller_v9 --verify-qualification
run_check "Paper-v2 pending-only remainder candidate v9" "$PYTHON_BIN" -m experiments.paper_v2.formal_matrix_remainder_controller_v9 --verify-candidate
run_check "Paper-v2 pending-only remainder admission v9" "$PYTHON_BIN" -m experiments.paper_v2.formal_matrix_remainder_controller_v9 --verify-admission
run_check "Paper-v2 combined result gate v6 qualification" "$PYTHON_BIN" -m experiments.paper_v2.formal_result_gate_v6 --verify-qualification
run_check "Paper-v2 prospective combined result gate v6" "$PYTHON_BIN" -m experiments.paper_v2.formal_result_gate_v6 --verify-candidate
run_check "Paper-v2 admitted medium analysis v8" "$PYTHON_BIN" -m experiments.paper_v2.formal_analysis_amendment_v8 --verify-analysis
run_check "Paper-v2 Gemini fallback frozen canary chain" "$PYTHON_BIN" -m experiments.paper_v2.gemini_fallback_controller_v1 --verify-frozen
run_check "Paper-v2 Gemini quota snapshot" "$PYTHON_BIN" -m experiments.paper_v2.gemini_quota_snapshot --verify-only
run_check "Paper-v2 six-condition executor shells" "$PYTHON_BIN" -m experiments.paper_v2.formal_condition_executors --verify-only
run_check "Paper-v2 append-only formal record store" "$PYTHON_BIN" -m experiments.paper_v2.formal_record_store --verify-only
run_check "Paper-v2 append-only formal record store v2" "$PYTHON_BIN" -m experiments.paper_v2.formal_record_store_v2 --verify-only
run_check "Paper-v2 live condition composition" "$PYTHON_BIN" -m experiments.paper_v2.live_condition_runtime --verify-only
run_check "Paper-v2 pinned PromptGuard live dependency" "$PYTHON_BIN" -m experiments.paper_v2.promptguard_live_dependency --verify-only
run_check "Paper-v2 official AgentDojo live dependency" "$PYTHON_BIN" -m experiments.paper_v2.agentdojo_live_dependency --verify-only
run_check "Paper-v2 offline outcome evaluators" "$PYTHON_BIN" -m experiments.paper_v2.m3_offline_evaluator --verify-only
run_check "Paper-v2 exact-gold oracle ablation" "$PYTHON_BIN" -m experiments.paper_v2.exact_gold_ablation --verify-only
run_check "Paper-v2 VIGIL provider bridge" "$PYTHON_BIN" -m experiments.paper_v2.vigil_live_dependency --verify-only
run_check "Paper-v2 condition-specific runtime freeze" "$PYTHON_BIN" -m experiments.paper_v2.medium_runtime --verify-only
run_check "Paper-v2 citation integrity" "$PYTHON_BIN" -m experiments.paper_v2.citation_integrity --verify-only
run_check "Paper-v2 Public-v1 zero-call abort review" "$PYTHON_BIN" -m experiments.paper_v2.public_abort_review_v1 --verify
run_check "Paper-v2 Public-v2 partial abort review" "$PYTHON_BIN" -m experiments.paper_v2.public_abort_review_v2 --verify
run_check "Paper-v2 Public-v2 AgentDojo resolver" "$PYTHON_BIN" -m experiments.paper_v2.public_agentdojo_live_dependency_v2 --verify
run_check "Paper-v2 Public-v2 Stage A" "$PYTHON_BIN" -m experiments.paper_v2.public_matrix_controller_v2 --verify-stage-a
run_check "Paper-v2 Public-v3 M3 resolver" "$PYTHON_BIN" -m experiments.paper_v2.public_m3_live_dependency_v3 --verify
run_check "Paper-v2 Public-v3 Stage A" "$PYTHON_BIN" -m experiments.paper_v2.public_matrix_controller_v3 --verify-stage-a
run_check "Paper-v2 Public-v3 partial abort review" "$PYTHON_BIN" -m experiments.paper_v2.public_abort_review_v3 --verify
run_check "Paper-v2 Public-v4 M3 evaluator" "$PYTHON_BIN" -m experiments.paper_v2.public_m3_live_dependency_v4 --verify
run_check "Paper-v2 Public-v4 Stage A" "$PYTHON_BIN" -m experiments.paper_v2.public_matrix_controller_v4 --verify-stage-a
run_check "Paper-v2 Public-v4 primary sharded continuation" "$PYTHON_BIN" -m experiments.paper_v2.public_sharded_continuation_v1 --verify-candidate --model-role primary
run_check "Paper-v2 experiment closeout freeze" "$PYTHON_BIN" -m experiments.paper_v2.experiment_closeout_freeze_v1
run_check "Paper-v2 Day-1 Harness interruption review" "$PYTHON_BIN" -m experiments.paper_v2.experiment_closeout_day1_harness_review_v1 --verify-review
run_check "Paper-v2 Gemini free-tier duration qualification" "$PYTHON_BIN" -m experiments.paper_v2.gemini_free_tier_duration_qualification_v1 --verify
run_check "Paper-v2 Gemini Public-v4 canary candidate" "$PYTHON_BIN" -m experiments.paper_v2.gemini_public_controller_v4 --verify-candidate
run_check "Paper-v2 Gemini public continuation candidate" "$PYTHON_BIN" -m experiments.paper_v2.gemini_public_continuation_plan_v1 --verify-candidate
run_check "Paper-v2 Gemini adaptive quota candidate" "$PYTHON_BIN" -m experiments.paper_v2.gemini_adaptive_quota_schedule_v1 --verify-candidate
run_check "Paper-v2 DeepSeek Flash adaptive second plan" "$PYTHON_BIN" -m experiments.paper_v2.adaptive_formal_second_plan_v1 --verify-candidate --model-key deepseek_flash
run_check "Paper-v2 Gemini adaptive second plan" "$PYTHON_BIN" -m experiments.paper_v2.adaptive_formal_second_plan_v1 --verify-candidate --model-key gemini_flash
run_check "Paper-v2 Pro adaptive-50 candidate" "$PYTHON_BIN" -m experiments.paper_v2.adaptive_formal_pro_controller_v1 --verify-candidate --stage pro_50
run_check "Paper-v2 Pro adaptive-50 admission" "$PYTHON_BIN" -m experiments.paper_v2.adaptive_formal_pro_controller_v1 --verify-admission --stage pro_50
run_check "Paper-v2 DeepSeek Flash adaptive-50 candidate" "$PYTHON_BIN" -m experiments.paper_v2.adaptive_formal_deepseek_flash_controller_v1 --verify-candidate --stage flash_50
run_check "Paper-v2 DeepSeek Flash adaptive-50 admission" "$PYTHON_BIN" -m experiments.paper_v2.adaptive_formal_deepseek_flash_controller_v1 --verify-admission --stage flash_50

if [ -f scripts/build_e17_source_index.py ] && [ -f outputs/experiments/e17_source_index_corrected_v2.json ]; then
  run_check "Corrected E17 source index" "$PYTHON_BIN" scripts/build_e17_source_index.py --check
fi

if [ "$REQUIRE_EXPERIMENTS_COMPLETE" = "1" ]; then
  run_check "Experiment registry complete" "$PYTHON_BIN" -m experiments.validate_registry --require-complete
fi

printf '\nVerification failed=%s\n' "$FAILED"
[ "$FAILED" -eq 0 ]
