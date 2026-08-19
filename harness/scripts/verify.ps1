[CmdletBinding()]
param(
    [string]$PythonExe = "",
    [switch]$RequireExperimentsComplete
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location -LiteralPath $Root

if (-not $PythonExe) {
    $PythonExe = (Get-Command python -ErrorAction Stop).Source
}

$script:Failed = 0

function Invoke-External {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $FilePath $($Arguments -join ' ')"
    }
}

function Invoke-Check {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][scriptblock]$Action
    )
    Write-Host "`n== $Name =="
    try {
        & $Action
        Write-Host "PASS: $Name"
    }
    catch {
        Write-Host "FAIL: $Name"
        Write-Host $_.Exception.Message
        $script:Failed = 1
    }
}

Invoke-Check "Harness files" {
    # Windows PowerShell 5.1 decodes UTF-8-without-BOM scripts using the active
    # ANSI code page. Keep non-ASCII required paths representable in ASCII
    # source so this verification entry point is portable across hosts.
    $ProjectOverviewDoc = "docs/" + (-join @(
        [char]0x9879, [char]0x76EE, [char]0x5B8C, [char]0x6574,
        [char]0x7EFC, [char]0x8FF0
    )) + ".md"
    $ProjectHandoffDoc = "docs/" + (-join @(
        [char]0x9879, [char]0x76EE, [char]0x79FB, [char]0x4EA4,
        [char]0x62A5, [char]0x544A
    )) + ".md"
    $HarnessContextDoc = "harness/" + (-join @(
        [char]0x9879, [char]0x76EE, [char]0x4E0A, [char]0x4E0B,
        [char]0x6587
    )) + ".md"
    $Required = @(
        "AGENTS.md", "harness/README.md",
        "harness/docs/architecture.md", "harness/docs/development-rules.md",
        "harness/docs/decision-log.md", "harness/docs/agent-guide.md",
        "harness/state/progress.md", "harness/state/memory.md",
        "harness/state/current-task.md", "harness/state/session-handoff.md",
        "harness/state/task-history.md", "harness/state/failure-log.md",
        "harness/specs/product-spec.md", "harness/specs/technical-spec.md",
        "harness/specs/acceptance-criteria.md",
        "harness/features/feature_list.json", "experiments/registry.json",
        "harness/workspaces/runpro/10_analysis/approval-gate.md",
        "harness/workspaces/runpro/10_analysis/requirement-ledger.md",
        "harness/scripts/init.sh", "harness/scripts/verify.sh",
        "harness/scripts/test.sh", "harness/scripts/cleanup.sh",
        "harness/scripts/verify.ps1", "harness/scripts/test.ps1",
        "harness/scripts/run_full_verification.ps1",
        "harness/scripts/verify_with_receipt_v2.ps1",
        "harness/scripts/verify_with_receipt_v3.ps1",
        "harness/config/permissions.yaml", "harness/config/policies.md",
        "harness/config/workflow.md",
        "config/project.env.example", "config/README.md",
        "m3_core/project_config.py", "scripts/check_project_config.py",
        "scripts/promptguard_setup_from_config.py",
        "scripts/audit_project_conventions.py",
        "docs/README.md", $ProjectOverviewDoc,
        $ProjectHandoffDoc, $HarnessContextDoc,
        "docs/archive/README.md",
        "experiments/paper_v2/source_audit.py",
        "experiments/paper_v2/medium_case_selection.py",
        "experiments/paper_v2/provider_gate.py",
        "experiments/paper_v2/provider_budget.py",
        "experiments/paper_v2/official_provider_executor.py",
        "experiments/paper_v2/provider_execution_gate.py",
        "experiments/paper_v2/provider_live_qualification.py",
        "experiments/paper_v2/provider_live_qualification_v2.py",
        "experiments/paper_v2/provider_request_trace_candidate.py",
        "experiments/paper_v2/provider_request_trace_activation.py",
        "experiments/paper_v2/provider_trace_bundle.py",
        "experiments/paper_v2/provider_trace_runtime_qualification.py",
        "experiments/paper_v2/formal_execution_controller_v2.py",
        "experiments/paper_v2/formal_matrix_controller_v1.py",
        "experiments/paper_v2/deepseek_nonthinking_client_v1.py",
        "experiments/paper_v2/formal_matrix_controller_v2.py",
        "experiments/paper_v2/trusted_context_runtime_v2.py",
        "experiments/paper_v2/formal_matrix_controller_v3.py",
        "experiments/paper_v2/deepseek_json_client_v2.py",
        "experiments/paper_v2/formal_matrix_controller_v4.py",
        "experiments/paper_v2/boundary_rejection_runtime_v1.py",
        "experiments/paper_v2/formal_matrix_controller_v5.py",
        "experiments/paper_v2/formal_matrix_abort_review_v1.py",
        "experiments/paper_v2/boundary_rejection_runtime_v2.py",
        "experiments/paper_v2/formal_matrix_controller_v6.py",
        "experiments/paper_v2/formal_result_gate_v1.py",
        "experiments/paper_v2/formal_result_gate_v2.py",
        "experiments/paper_v2/formal_result_gate_v3.py",
        "experiments/paper_v2/formal_matrix_abort_review_v2.py",
        "experiments/paper_v2/boundary_rejection_runtime_v3.py",
        "experiments/paper_v2/formal_matrix_controller_v7.py",
        "experiments/paper_v2/formal_result_gate_v4.py",
        "experiments/paper_v2/formal_matrix_abort_review_v3.py",
        "experiments/paper_v2/formal_matrix_controller_v8.py",
        "experiments/paper_v2/formal_result_gate_v5.py",
        "experiments/paper_v2/formal_matrix_remainder_controller_v9.py",
        "experiments/paper_v2/formal_result_gate_v6.py",
        "experiments/paper_v2/medium_analysis_v4.py",
        "experiments/paper_v2/medium_analysis_v5.py",
        "experiments/paper_v2/formal_analysis_amendment_v7.py",
        "experiments/paper_v2/formal_analysis_amendment_v8.py",
        "experiments/paper_v2/gemini_evidence_store_v1.py",
        "experiments/paper_v2/gemini_fallback_controller_v1.py",
        "experiments/paper_v2/post_pilot_evidence_review.py",
        "experiments/paper_v2/gemini_quota_snapshot.py",
        "experiments/paper_v2/contracts_v2.py",
        "experiments/paper_v2/formal_condition_executors.py",
        "experiments/paper_v2/formal_record_store.py",
        "experiments/paper_v2/formal_record_store_v2.py",
        "experiments/paper_v2/live_condition_runtime.py",
        "experiments/paper_v2/promptguard_live_dependency.py",
        "experiments/paper_v2/agentdojo_live_dependency.py",
        "experiments/paper_v2/m3_offline_evaluator.py",
        "experiments/paper_v2/exact_gold_ablation.py",
        "experiments/paper_v2/vigil_live_dependency.py",
        "experiments/paper_v2/provider_attestation.py",
        "experiments/paper_v2/provider_safety.py",
        "experiments/paper_v2/citation_integrity.py",
        "experiments/paper_v2/medium_execution.py",
        "experiments/paper_v2/medium_runtime.py",
        "experiments/paper_v2/structural_baselines.py",
        "experiments/paper_v2/medium_analysis.py",
        "experiments/paper_v2/medium_analysis_v2.py",
        "experiments/paper_v2/medium_analysis_v3.py",
        "experiments/paper_v2/research_assets.py",
        "experiments/paper_v2/adaptive_runner.py",
        "experiments/paper_v2/adaptive_cost_canary_plan_v1.py",
        "experiments/paper_v2/adaptive_query_ledger_v1.py",
        "experiments/paper_v2/adaptive_cost_canary_controller_v1.py",
        "experiments/paper_v2/adaptive_result_gate_v1.py",
        "experiments/paper_v2/adaptive_cost_canary_abort_review_v1.py",
        "experiments/paper_v2/adaptive_cost_canary_controller_v2.py",
        "experiments/paper_v2/adaptive_result_gate_v2.py",
        "experiments/paper_v2/incremental_live_ledgers_v1.py",
        "experiments/paper_v2/adaptive_cost_canary_recovery_v3.py",
        "experiments/paper_v2/adaptive_recovery_technical_review_v1.py",
        "experiments/paper_v2/adaptive_canary_analysis_v1.py",
        "experiments/paper_v2/adaptive_canary_result_admission_v1.py",
        "experiments/paper_v2/adaptive_canary_analysis_review_v1.py",
        "experiments/paper_v2/experiment_closeout_freeze_v1.py",
        "experiments/paper_v2/experiment_closeout_day1_harness_review_v1.py",
        "experiments/paper_v2/experiment_closeout_day2_harness_failure_review_v1.py",
        "experiments/paper_v2/experiment_closeout_day2_harness_gate_v2.py",
        "experiments/paper_v2/experiment_closeout_interim_harness_failure_review_v3.py",
        "experiments/paper_v2/sandbox_git_safe_directory_qualification_v1.py",
        "experiments/paper_v2/experiment_closeout_fresh_harness_failure_review_v5.py",
        "experiments/paper_v2/experiment_closeout_fresh_harness_failure_review_v10.py",
        "experiments/paper_v2/experiment_closeout_harness_gate_v3.py",
        "experiments/paper_v2/experiment_closeout_harness_gate_v4.py",
        "experiments/paper_v2/experiment_closeout_harness_gate_v5.py",
        "experiments/paper_v2/experiment_closeout_harness_gate_v6.py",
        "experiments/paper_v2/adaptive_execution_order_gate_v2.py",
        "experiments/paper_v2/adaptive_formal_pro_controller_v2.py",
        "experiments/paper_v2/adaptive_formal_pro_200_host_timeout_review_v1.py",
        "experiments/paper_v2/experiment_closeout_harness_gate_v7.py",
        "experiments/paper_v2/adaptive_formal_pro_500_activation_gate_v1.py",
        "experiments/paper_v2/adaptive_formal_pro_500_guarded_runner_v1.py",
        "experiments/paper_v2/independent_blind_day1_acceptance_v1.py",
        "outputs/verification/start_experiment_closeout_day2_harness_v2.ps1",
        "outputs/verification/start_experiment_closeout_interim_harness_v3.ps1",
        "outputs/verification/start_experiment_closeout_fresh_harness_v4.ps1",
        "outputs/verification/start_experiment_closeout_fresh_harness_v5.ps1",
        "outputs/verification/start_experiment_closeout_fresh_harness_v6.ps1",
        "outputs/verification/start_experiment_closeout_fresh_harness_v7.ps1",
        "outputs/verification/start_experiment_closeout_fresh_harness_v8.ps1",
        "outputs/verification/start_experiment_closeout_fresh_harness_v9.ps1",
        "outputs/verification/run_deepseek_flash_public_canary_v4_guarded_v3.ps1",
        "outputs/verification/run_deepseek_flash_public_second_continuation_v2_guarded.ps1",
        "outputs/verification/run_deepseek_flash_public_second_recovery_v3_guarded.ps1",
        "outputs/verification/run_gemini_public_v4_segment_guarded.ps1",
        "outputs/verification/run_gemini_public_v5_segment_guarded.ps1",
        "outputs/verification/run_gemini_public_v5_recovery_segment_guarded_v2.ps1",
        "outputs/verification/run_adaptive_formal_pro_v2_guarded.ps1",
        "outputs/verification/run_adaptive_formal_pro_v2_guarded_v3.ps1",
        "outputs/verification/run_adaptive_formal_pro_v2_guarded_v4.ps1",
        "outputs/verification/watch_adaptive_formal_pro_200_execute_exit_v1.ps1",
        "outputs/verification/finalize_adaptive_formal_pro_200_host_timeout_v1.ps1",
        "outputs/verification/finalize_adaptive_formal_pro_200_host_timeout_v2.ps1",
        "outputs/verification/start_experiment_closeout_fresh_harness_v10.ps1",
        "outputs/verification/start_experiment_closeout_fresh_harness_v11.ps1",
        "outputs/verification/start_experiment_closeout_fresh_harness_v12.ps1",
        "outputs/verification/start_adaptive_formal_pro_500_guarded_v1.ps1",
        "experiments/paper_v2/gemini_daily_quota_ledger_v1.py",
        "experiments/paper_v2/gemini_free_tier_duration_qualification_v1.py",
        "experiments/paper_v2/gemini_public_controller_v4.py",
        "experiments/paper_v2/gemini_public_technical_review_v5.py",
        "experiments/paper_v2/gemini_public_v4_wrapper_recovery_v1.py",
        "experiments/paper_v2/gemini_public_continuation_plan_v1.py",
        "experiments/paper_v2/gemini_public_continuation_plan_v2.py",
        "experiments/paper_v2/gemini_public_continuation_controller_v1.py",
        "experiments/paper_v2/gemini_adaptive_quota_schedule_v1.py",
        "experiments/paper_v2/gemini_adaptive_query_store_v1.py",
        "experiments/paper_v2/gemini_adaptive_daily_controller_v1.py",
        "experiments/paper_v2/gemini_trace_attaching_runtime_v1.py",
        "experiments/paper_v2/gemini_trace_attaching_runtime_v2.py",
        "experiments/paper_v2/gemini_local_precommit_contract_v2_candidate.py",
        "experiments/paper_v2/gemini_public_controller_v5.py",
        "experiments/paper_v2/adaptive_formal_plan_v2.py",
        "experiments/paper_v2/adaptive_formal_second_plan_v1.py",
        "experiments/paper_v2/adaptive_formal_pro_controller_v1.py",
        "experiments/paper_v2/public_second_continuation_v2.py",
        "experiments/paper_v2/public_second_continuation_recovery_v3.py",
        "experiments/paper_v2/public_second_recovery_evidence_review_v4.py",
        "experiments/paper_v2/public_second_evidence_merge_v1.py",
        "experiments/paper_v2/adaptive_formal_deepseek_flash_controller_v1.py",
        "experiments/paper_v2/independent_blind_closeout_v1.py",
        "experiments/paper_v2/public_sharded_continuation_abort_review_v1.py",
        "experiments/paper_v2/public_sharded_continuation_v2.py",
        "experiments/paper_v2/public_sharded_continuation_recovery_v3.py",
        "experiments/paper_v2/public_primary_merge_review_v1.py",
        "docs/research/paper_v2/manuscript/methods_draft.md",
        "docs/research/paper_v2/manuscript/results_shell.md",
        "docs/research/paper_v2/manuscript/devils_advocate_review.md",
        "docs/research/paper_v2/manuscript/jisa_submission_checklist.md",
        "docs/research/paper_v2/manuscript/related_work_draft.md",
        "protocols/paper_upgrade_v2/provider_candidates_v1.json",
        "protocols/paper_upgrade_v2/provider_cost_decision_candidate_v1.json",
        "protocols/paper_upgrade_v2/provider_cost_preflight_v1.json",
        "protocols/paper_upgrade_v2/dual_provider_budget_policy_v1.json",
        "protocols/paper_upgrade_v2/dual_provider_budget_policy_v2.json",
        "protocols/paper_upgrade_v2/provider_budget_authorization_v3.json",
        "protocols/paper_upgrade_v2/dual_provider_budget_preflight_v1.json",
        "protocols/paper_upgrade_v2/provider_executor_qualification_v1.json",
        "protocols/paper_upgrade_v2/formal_matrix_controller_qualification_v1.json",
        "protocols/paper_upgrade_v2/deepseek_medium_matrix_candidate_v1.json",
        "protocols/paper_upgrade_v2/deepseek_nonthinking_client_qualification_v1.json",
        "protocols/paper_upgrade_v2/formal_matrix_controller_qualification_v2.json",
        "protocols/paper_upgrade_v2/deepseek_medium_matrix_candidate_v2.json",
        "protocols/paper_upgrade_v2/formal_matrix_controller_qualification_v3.json",
        "protocols/paper_upgrade_v2/deepseek_medium_matrix_candidate_v3.json",
        "protocols/paper_upgrade_v2/admissions/deepseek_medium_matrix_canary_admission_v3.json",
        "protocols/paper_upgrade_v2/deepseek_json_client_qualification_v2.json",
        "protocols/paper_upgrade_v2/formal_matrix_controller_qualification_v4.json",
        "protocols/paper_upgrade_v2/deepseek_medium_matrix_candidate_v4.json",
        "protocols/paper_upgrade_v2/admissions/deepseek_medium_matrix_canary_admission_v4.json",
        "protocols/paper_upgrade_v2/admissions/deepseek_medium_matrix_continuation_admission_v4.json",
        "outputs/paper_upgrade_v2/formal_medium/deepseek/dd794dd88eade41166bdafb7cb191898d7d19a5d8df737340f6acc3daac4504f/formal_result_technical_review_v1.json",
        "protocols/paper_upgrade_v2/formal_matrix_controller_qualification_v5.json",
        "protocols/paper_upgrade_v2/deepseek_medium_matrix_candidate_v5.json",
        "protocols/paper_upgrade_v2/admissions/deepseek_medium_matrix_canary_admission_v5.json",
        "protocols/paper_upgrade_v2/admissions/deepseek_medium_matrix_continuation_admission_v5.json",
        "outputs/paper_upgrade_v2/formal_medium/deepseek/62eb641043a2fc50cbaac439b047de5c433c38b20ff9c06d8ff6d92dd71f90ae/six_condition_canary_review_v5.json",
        "outputs/paper_upgrade_v2/formal_medium/deepseek/62eb641043a2fc50cbaac439b047de5c433c38b20ff9c06d8ff6d92dd71f90ae/formal_matrix_abort_review_v1.json",
        "protocols/paper_upgrade_v2/formal_matrix_controller_qualification_v6.json",
        "protocols/paper_upgrade_v2/deepseek_medium_matrix_candidate_v6.json",
        "protocols/paper_upgrade_v2/admissions/deepseek_medium_matrix_canary_admission_v6.json",
        "protocols/paper_upgrade_v2/admissions/deepseek_medium_matrix_continuation_admission_v6.json",
        "outputs/paper_upgrade_v2/formal_medium/deepseek/6c16117e0451a01dd20409f60395035c110e5eb7c0be078d386a0e138e4fb2f9/six_condition_canary_review_v6.json",
        "protocols/paper_upgrade_v2/formal_result_gate_qualification_v3.json",
        "protocols/paper_upgrade_v2/deepseek_medium_result_gate_candidate_v3.json",
        "outputs/paper_upgrade_v2/formal_medium/deepseek/6c16117e0451a01dd20409f60395035c110e5eb7c0be078d386a0e138e4fb2f9/formal_matrix_abort_review_v2.json",
        "protocols/paper_upgrade_v2/formal_matrix_controller_qualification_v7.json",
        "protocols/paper_upgrade_v2/deepseek_medium_matrix_candidate_v7.json",
        "protocols/paper_upgrade_v2/admissions/deepseek_medium_matrix_canary_admission_v7.json",
        "protocols/paper_upgrade_v2/formal_result_gate_qualification_v1.json",
        "protocols/paper_upgrade_v2/deepseek_medium_result_gate_candidate_v1.json",
        "protocols/paper_upgrade_v2/formal_result_gate_qualification_v2.json",
        "protocols/paper_upgrade_v2/deepseek_medium_result_gate_candidate_v2.json",
        "protocols/paper_upgrade_v2/superseded_result_gate_candidate_review_v1.json",
        "protocols/paper_upgrade_v2/superseded_result_gate_candidate_review_v2.json",
        "protocols/paper_upgrade_v2/superseded_result_gate_candidate_review_v3.json",
        "protocols/paper_upgrade_v2/superseded_result_gate_candidate_review_v4.json",
        "protocols/paper_upgrade_v2/superseded_result_gate_candidate_review_v5.json",
        "protocols/paper_upgrade_v2/formal_condition_executor_qualification_v1.json",
        "protocols/paper_upgrade_v2/formal_record_store_qualification_v1.json",
        "protocols/paper_upgrade_v2/formal_record_store_qualification_v2.json",
        "protocols/paper_upgrade_v2/live_condition_runtime_qualification_v1.json",
        "protocols/paper_upgrade_v2/promptguard_live_dependency_qualification_v1.json",
        "protocols/paper_upgrade_v2/agentdojo_live_dependency_qualification_v1.json",
        "protocols/paper_upgrade_v2/m3_offline_evaluator_qualification_v1.json",
        "protocols/paper_upgrade_v2/exact_gold_ablation_qualification_v1.json",
        "protocols/paper_upgrade_v2/vigil_live_dependency_qualification_v1.json",
        "protocols/paper_upgrade_v2/provider_live_qualification_v1.json",
        "protocols/paper_upgrade_v2/provider_live_qualification_v2.json",
        "outputs/paper_upgrade_v2/provider_identity/deepseek_request_trace_v2.jsonl",
        "protocols/paper_upgrade_v2/provider_request_trace_policy_v2_candidate.json",
        "protocols/paper_upgrade_v2/provider_request_trace_v2_qualification.json",
        "protocols/paper_upgrade_v2/provider_request_trace_activation_v2.json",
        "protocols/paper_upgrade_v2/gemini_quota_snapshot_v1.json",
        "protocols/paper_upgrade_v2/gemini_fallback_plan_v1.jsonl",
        "protocols/paper_upgrade_v2/gemini_fallback_budget_override_v1.json",
        "protocols/paper_upgrade_v2/gemini_fallback_controller_qualification_v1.json",
        "protocols/paper_upgrade_v2/gemini_fallback_candidate_v1.json",
        "protocols/paper_upgrade_v2/admissions/gemini_fallback_canary_admission_v1.json",
        "protocols/paper_upgrade_v2/provider_trace_runtime_qualification_v2.json",
        "protocols/paper_upgrade_v2/deepseek_pilot_admission_candidate_v2.json",
        "protocols/paper_upgrade_v2/formal_execution_controller_qualification_v2.json",
        "protocols/paper_upgrade_v2/post_pilot_review_qualification_v1.json",
        "protocols/paper_upgrade_v2/medium_execution_manifest_v3_preflight.json",
        "protocols/paper_upgrade_v2/formal_condition_executor_qualification_v1.json",
        "protocols/paper_upgrade_v2/formal_record_store_qualification_v1.json",
        "protocols/paper_upgrade_v2/formal_record_store_qualification_v2.json",
        "protocols/paper_upgrade_v2/medium_execution_plan_v1.jsonl",
        "protocols/paper_upgrade_v2/medium_execution_manifest_v1.json",
        "protocols/paper_upgrade_v2/provider_safety_policy_v1.json",
        "protocols/paper_upgrade_v2/citation_integrity_manifest_v1.json",
        "protocols/paper_upgrade_v2/evidence_80_execution_roadmap_v3.json",
        "protocols/paper_upgrade_v2/medium_execution_plan_v2.jsonl",
        "protocols/paper_upgrade_v2/medium_execution_manifest_v2.json",
        "protocols/paper_upgrade_v2/adaptive_cost_canary_candidate_v1.json",
        "protocols/paper_upgrade_v2/adaptive_result_gate_v1.json",
        "schemas/paper_v2/adaptive_cost_canary_admission_v1.schema.json",
        "protocols/paper_upgrade_v2/adaptive_cost_canary_abort_review_v1.json",
        "protocols/paper_upgrade_v2/adaptive_cost_canary_candidate_v2.json",
        "protocols/paper_upgrade_v2/admissions/adaptive_cost_canary_admission_v2.json",
        "protocols/paper_upgrade_v2/adaptive_result_gate_v2.json",
        "outputs/paper_upgrade_v2/adaptive_cost_canary_v2/primary/adaptive_v2_recovery_review_v3.json",
        "protocols/paper_upgrade_v2/adaptive_cost_canary_recovery_candidate_v3.json",
        "protocols/paper_upgrade_v2/admissions/adaptive_cost_canary_admission_v3.json",
        "outputs/paper_upgrade_v2/adaptive_cost_canary_v2/primary/technical_cost_review_v3.json",
        "outputs/paper_upgrade_v2/adaptive_cost_canary_v2/primary/technical_cost_review_v3_1.json",
        "protocols/paper_upgrade_v2/adaptive_canary_result_candidate_v1.json",
        "protocols/paper_upgrade_v2/admissions/adaptive_canary_result_admission_v1.json",
        "outputs/paper_upgrade_v2/adaptive_cost_canary_v2/analysis_v1/analysis_manifest.json",
        "outputs/paper_upgrade_v2/adaptive_cost_canary_v2/analysis_v1/summary.json",
        "outputs/paper_upgrade_v2/adaptive_cost_canary_v2/analysis_v1/analysis_review_v1.json",
        "outputs/paper_upgrade_v2/adaptive_cost_canary_v2/analysis_v1/task_results.csv",
        "outputs/paper_upgrade_v2/adaptive_cost_canary_v2/analysis_v1/adaptive_canary_asr.png",
        "schemas/paper_v2/adaptive_cost_canary_candidate_v2.schema.json",
        "schemas/paper_v2/adaptive_cost_canary_admission_v2.schema.json",
        "experiments/paper_v2/public_abort_review_v1.py",
        "experiments/paper_v2/public_abort_review_v2.py",
        "experiments/paper_v2/public_agentdojo_live_dependency_v2.py",
        "experiments/paper_v2/public_matrix_controller_v2.py",
        "experiments/paper_v2/public_live_controller_v2.py",
        "experiments/paper_v2/public_m3_live_dependency_v3.py",
        "experiments/paper_v2/public_matrix_controller_v3.py",
        "experiments/paper_v2/public_live_controller_v3.py",
        "experiments/paper_v2/public_abort_review_v3.py",
        "experiments/paper_v2/public_m3_live_dependency_v4.py",
        "experiments/paper_v2/public_matrix_controller_v4.py",
        "experiments/paper_v2/public_live_controller_v4.py",
        "experiments/paper_v2/public_sharded_continuation_v1.py",
        "experiments/paper_v2/public_single_shard_recovery_v3.py",
        "experiments/paper_v2/public_shard_evidence_review_v1.py",
        "experiments/paper_v2/public_primary_merge_review_v2.py",
        "experiments/paper_v2/public_primary_result_admission_v1.py",
        "experiments/paper_v2/public_primary_analysis_validation_correction_v2.py",
        "experiments/paper_v2/public_primary_analysis_validation_correction_v3.py",
        "experiments/paper_v2/public_primary_analysis_validation_correction_v4.py",
        "experiments/paper_v2/public_primary_analysis_validation_correction_v5.py",
        "experiments/paper_v2/public_primary_analysis_v5.py",
        "experiments/paper_v2/public_primary_analysis_review_v5.py",
        "experiments/paper_v2/build_bibliography_v1.py",
        "scripts/build_paper_v2_stage_report_20260730.py",
        "scripts/validate_paper_v2_stage_report_20260730.py",
        "protocols/paper_upgrade_v2/public_primary_continuation_abort_review_v1.json",
        "protocols/paper_upgrade_v2/public_primary_continuation_qualification_v2.json",
        "protocols/paper_upgrade_v2/public_primary_continuation_candidate_v2.json",
        "protocols/paper_upgrade_v2/admissions/deepseek_public_primary_continuation_s0_admission_v2.json",
        "protocols/paper_upgrade_v2/admissions/deepseek_public_primary_continuation_s1_admission_v2.json",
        "protocols/paper_upgrade_v2/admissions/deepseek_public_primary_continuation_s2_admission_v2.json",
        "protocols/paper_upgrade_v2/admissions/deepseek_public_primary_continuation_s3_admission_v2.json",
        "schemas/paper_v2/public_sharded_continuation_candidate_v2.schema.json",
        "schemas/paper_v2/public_sharded_continuation_admission_v2.schema.json",
        "schemas/paper_v2/public_primary_merge_review_v1.schema.json",
        "protocols/paper_upgrade_v2/public_primary_canary_abort_review_v1.json",
        "protocols/paper_upgrade_v2/public_primary_canary_abort_review_v2.json",
        "protocols/paper_upgrade_v2/admissions/deepseek_public_primary_canary_admission_v2.json",
        "protocols/paper_upgrade_v2/public_agentdojo_live_dependency_qualification_v2.json",
        "protocols/paper_upgrade_v2/public_matrix_controller_qualification_v2.json",
        "protocols/paper_upgrade_v2/public_matrix_candidate_v2.json",
        "protocols/paper_upgrade_v2/public_m3_live_dependency_qualification_v3.json",
        "protocols/paper_upgrade_v2/public_matrix_controller_qualification_v3.json",
        "protocols/paper_upgrade_v2/public_matrix_candidate_v3.json",
        "protocols/paper_upgrade_v2/public_primary_canary_abort_review_v3.json",
        "protocols/paper_upgrade_v2/public_m3_live_dependency_qualification_v4.json",
        "protocols/paper_upgrade_v2/public_matrix_controller_qualification_v4.json",
        "protocols/paper_upgrade_v2/public_matrix_candidate_v4.json",
        "protocols/paper_upgrade_v2/public_primary_continuation_candidate_v1.json",
        "protocols/paper_upgrade_v2/experiment_closeout_candidate_v1.json",
        "protocols/paper_upgrade_v2/formal_matrix_v7_immutable_audit_v1.json",
        "protocols/paper_upgrade_v2/experiment_closeout_day1_harness_review_v1.json",
        "protocols/paper_upgrade_v2/experiment_closeout_day2_harness_failure_review_v1.json",
        "protocols/paper_upgrade_v2/experiment_closeout_interim_harness_failure_review_v3.json",
        "protocols/paper_upgrade_v2/sandbox_git_safe_directory_qualification_v1.json",
        "protocols/paper_upgrade_v2/experiment_closeout_fresh_harness_failure_review_v5.json",
        "protocols/paper_upgrade_v2/experiment_closeout_fresh_harness_failure_review_v10.json",
        "protocols/paper_upgrade_v2/adaptive_execution_order_supersession_v2.json",
        "protocols/paper_upgrade_v2/adaptive_formal_pro_50_candidate_v2.json",
        "protocols/paper_upgrade_v2/admissions/adaptive_formal_pro_50_admission_v2.json",
        "protocols/paper_upgrade_v2/experiment_closeout_harness_gate_v5.json",
        "protocols/paper_upgrade_v2/adaptive_formal_pro_200_candidate_v2.json",
        "protocols/paper_upgrade_v2/admissions/adaptive_formal_pro_200_admission_v2.json",
        "protocols/paper_upgrade_v2/experiment_closeout_harness_gate_v6.json",
        "protocols/paper_upgrade_v2/adaptive_formal_pro_200_host_timeout_review_v1.json",
        "protocols/paper_upgrade_v2/adaptive_formal_pro_500_candidate_v2.json",
        "protocols/paper_upgrade_v2/admissions/adaptive_formal_pro_500_admission_v2.json",
        "protocols/paper_upgrade_v2/experiment_closeout_harness_gate_v7.json",
        "protocols/paper_upgrade_v2/independent_blind_day1_registration_acceptance_v1.json",
        "protocols/paper_upgrade_v2/gemini_public_canary_candidate_v4.json",
        "protocols/paper_upgrade_v2/gemini_free_tier_duration_qualification_v1.json",
        "protocols/paper_upgrade_v2/gemini_public_continuation_candidate_v1.json",
        "protocols/paper_upgrade_v2/gemini_public_continuation_candidate_v2.json",
        "protocols/paper_upgrade_v2/gemini_public_v4_s0_wrapper_recovery_v1.json",
        "protocols/paper_upgrade_v2/gemini_local_precommit_contract_v2_1_candidate.json",
        "protocols/paper_upgrade_v2/gemini_public_canary_recovery_candidate_v5.json",
        "protocols/paper_upgrade_v2/admissions/gemini_public_canary_v4_s0_2026-08-02_admission.json",
        "outputs/paper_upgrade_v2/formal_public/gemini/public-v4-canary-s0-ab5ec080f3b268d77f1dbe41db03601a49281cfc1bc602bcbce0395bdda530c5/technical_segment_review_v5.json",
        "protocols/paper_upgrade_v2/gemini_adaptive_quota_candidate_v1.json",
        "protocols/paper_upgrade_v2/public_second_continuation_candidate_v1.json",
        "protocols/paper_upgrade_v2/public_second_continuation_qualification_v2.json",
        "protocols/paper_upgrade_v2/public_second_continuation_candidate_v2.json",
        "protocols/paper_upgrade_v2/public_second_continuation_abort_review_v3.json",
        "protocols/paper_upgrade_v2/public_second_continuation_recovery_candidate_v3.json",
        "protocols/paper_upgrade_v2/public_second_evidence_merge_v1.json",
        "protocols/paper_upgrade_v2/admissions/deepseek_public_second_continuation_s0_admission_v2.json",
        "protocols/paper_upgrade_v2/admissions/deepseek_public_second_continuation_s1_admission_v2.json",
        "protocols/paper_upgrade_v2/public_primary_continuation_s0_candidate_v3.json",
        "protocols/paper_upgrade_v2/public_primary_continuation_s1_candidate_v3.json",
        "protocols/paper_upgrade_v2/public_primary_continuation_s2_candidate_v3.json",
        "protocols/paper_upgrade_v2/public_primary_continuation_s3_candidate_v3.json",
        "protocols/paper_upgrade_v2/admissions/deepseek_public_primary_continuation_s0_admission_v3.json",
        "protocols/paper_upgrade_v2/admissions/deepseek_public_primary_continuation_s1_admission_v3.json",
        "protocols/paper_upgrade_v2/admissions/deepseek_public_primary_continuation_s2_admission_v3.json",
        "protocols/paper_upgrade_v2/admissions/deepseek_public_primary_continuation_s3_admission_v3.json",
        "protocols/paper_upgrade_v2/public_primary_merge_review_v2.json",
        "protocols/paper_upgrade_v2/public_primary_result_candidate_v1.json",
        "protocols/paper_upgrade_v2/admissions/public_primary_result_admission_v1.json",
        "protocols/paper_upgrade_v2/public_primary_analysis_validation_correction_candidate_v2.json",
        "protocols/paper_upgrade_v2/public_primary_analysis_validation_correction_candidate_v3.json",
        "protocols/paper_upgrade_v2/public_primary_analysis_validation_correction_candidate_v4.json",
        "protocols/paper_upgrade_v2/public_primary_analysis_validation_correction_candidate_v5.json",
        "protocols/paper_upgrade_v2/admissions/public_primary_analysis_validation_correction_admission_v2.json",
        "protocols/paper_upgrade_v2/admissions/public_primary_analysis_validation_correction_admission_v3.json",
        "protocols/paper_upgrade_v2/admissions/public_primary_analysis_validation_correction_admission_v4.json",
        "protocols/paper_upgrade_v2/admissions/public_primary_analysis_validation_correction_admission_v5.json",
        "outputs/paper_upgrade_v2/formal_public/primary_analysis_v5/analysis_manifest.json",
        "outputs/paper_upgrade_v2/formal_public/primary_analysis_v5/public_primary_analysis_summary_v5.json",
        "outputs/paper_upgrade_v2/formal_public/primary_analysis_v5/public_primary_condition_summary_v5.csv",
        "outputs/paper_upgrade_v2/formal_public/primary_analysis_v5/independent_analysis_review_v5.json",
        "outputs/paper_upgrade_v2/formal_public/primary_analysis_v5/public_primary_security_v1.png",
        "outputs/paper_upgrade_v2/formal_public/primary_analysis_v5/public_primary_security_v1.svg",
        "outputs/paper_upgrade_v2/formal_public/primary_analysis_v5/public_primary_utility_v1.png",
        "outputs/paper_upgrade_v2/formal_public/primary_analysis_v5/public_primary_utility_v1.svg",
        "outputs/paper_upgrade_v2/formal_public/primary_analysis_v5/public_primary_diagnostics_v1.png",
        "outputs/paper_upgrade_v2/formal_public/primary_analysis_v5/public_primary_diagnostics_v1.svg",
        "docs/research/paper_v2/manuscript/references_v1.bib",
        "docs/research/paper_v2/manuscript/bibliography_build_v1.json",
        "docs/research/paper_v2/manuscript/completion_scorecard_v2.json",
        "schemas/paper_v2/public_matrix_candidate_v2.schema.json",
        "schemas/paper_v2/public_matrix_admission_v2.schema.json",
        "schemas/paper_v2/public_matrix_candidate_v3.schema.json",
        "schemas/paper_v2/public_matrix_admission_v3.schema.json",
        "schemas/paper_v2/public_matrix_candidate_v4.schema.json",
        "schemas/paper_v2/public_matrix_admission_v4.schema.json",
        "schemas/paper_v2/public_sharded_continuation_candidate_v1.schema.json",
        "schemas/paper_v2/public_sharded_continuation_admission_v1.schema.json"
    )
    $Missing = @($Required | Where-Object { -not (Test-Path -LiteralPath $_ -PathType Leaf) })
    if ($Missing.Count -gt 0) {
        throw "Missing Harness files: $($Missing -join ', ')"
    }
}

Invoke-Check "Harness and project source boundary" {
    $LegacyHarnessPaths = @(
        "README_AGENT.md",
        ".agent",
        "features",
        "specs",
        "tasks",
        "runpro_workspace",
        "agent/current-task.md",
        "agent/failure-log.md",
        "agent/memory.md",
        "agent/progress.md",
        "agent/session-handoff.md",
        "agent/task-history.md"
    )
    $LegacyFound = @($LegacyHarnessPaths | Where-Object { Test-Path -LiteralPath $_ })
    if ($LegacyFound.Count -gt 0) {
        throw "Legacy Harness paths remain mixed with project source: $($LegacyFound -join ', ')"
    }
    foreach ($ProjectPath in @(
        "m3_core", "m3_guard", "m3_eval", "m3_attacks",
        "experiments", "protocols", "schemas", "fixtures", "tests", "scripts",
        "config"
    )) {
        if (-not (Test-Path -LiteralPath $ProjectPath -PathType Container)) {
            throw "Project source directory is missing from repository root: $ProjectPath"
        }
    }
}

Invoke-Check "Project layout and naming conventions" {
    Invoke-External $PythonExe @("scripts/audit_project_conventions.py", "--check")
}

Invoke-Check "JSON contracts" {
    foreach ($Path in @(
        "harness/features/feature_list.json",
        "experiments/registry.json",
        "protocols/paper_upgrade_v2/medium_falsification_gate_v1.json",
        "protocols/paper_upgrade_v2/medium_falsification_gate_v2.json",
        "protocols/paper_upgrade_v2/provider_cost_gate_template_v1.json",
        "protocols/paper_upgrade_v2/provider_candidates_v1.json",
        "protocols/paper_upgrade_v2/provider_cost_decision_candidate_v1.json",
        "protocols/paper_upgrade_v2/provider_cost_preflight_v1.json",
        "protocols/paper_upgrade_v2/dual_provider_budget_policy_v1.json",
        "protocols/paper_upgrade_v2/dual_provider_budget_policy_v2.json",
        "protocols/paper_upgrade_v2/provider_budget_authorization_v3.json",
        "protocols/paper_upgrade_v2/dual_provider_budget_preflight_v1.json",
        "protocols/paper_upgrade_v2/provider_executor_qualification_v1.json",
        "protocols/paper_upgrade_v2/formal_condition_executor_qualification_v1.json",
        "protocols/paper_upgrade_v2/formal_record_store_qualification_v1.json",
        "protocols/paper_upgrade_v2/live_condition_runtime_qualification_v1.json",
        "protocols/paper_upgrade_v2/promptguard_live_dependency_qualification_v1.json",
        "protocols/paper_upgrade_v2/agentdojo_live_dependency_qualification_v1.json",
        "protocols/paper_upgrade_v2/m3_offline_evaluator_qualification_v1.json",
        "protocols/paper_upgrade_v2/exact_gold_ablation_qualification_v1.json",
        "protocols/paper_upgrade_v2/vigil_live_dependency_qualification_v1.json",
        "protocols/paper_upgrade_v2/provider_live_qualification_v1.json",
        "protocols/paper_upgrade_v2/provider_live_qualification_v2.json",
        "protocols/paper_upgrade_v2/provider_request_trace_policy_v2_candidate.json",
        "protocols/paper_upgrade_v2/provider_request_trace_v2_qualification.json",
        "protocols/paper_upgrade_v2/provider_request_trace_activation_v2.json",
        "protocols/paper_upgrade_v2/gemini_quota_snapshot_v1.json",
        "protocols/paper_upgrade_v2/gemini_fallback_budget_override_v1.json",
        "protocols/paper_upgrade_v2/gemini_fallback_controller_qualification_v1.json",
        "protocols/paper_upgrade_v2/gemini_fallback_candidate_v1.json",
        "protocols/paper_upgrade_v2/admissions/gemini_fallback_canary_admission_v1.json",
        "protocols/paper_upgrade_v2/provider_trace_runtime_qualification_v2.json",
        "protocols/paper_upgrade_v2/deepseek_pilot_admission_candidate_v2.json",
        "protocols/paper_upgrade_v2/formal_execution_controller_qualification_v2.json",
        "protocols/paper_upgrade_v2/post_pilot_review_qualification_v1.json",
        "protocols/paper_upgrade_v2/medium_execution_manifest_v3_preflight.json",
        "protocols/paper_upgrade_v2/medium_execution_manifest_v1.json",
        "protocols/paper_upgrade_v2/provider_safety_policy_v1.json",
        "protocols/paper_upgrade_v2/citation_integrity_manifest_v1.json",
        "protocols/paper_upgrade_v2/evidence_80_execution_roadmap_v3.json",
        "protocols/paper_upgrade_v2/medium_execution_manifest_v2.json",
        "protocols/paper_upgrade_v2/medium_selection_spec_v1.json",
        "protocols/paper_upgrade_v2/medium_case_manifest_v1.json",
        "protocols/paper_upgrade_v2/medium_gate_spec_v1.json",
        "protocols/paper_upgrade_v2/medium_gate_spec_v2.json",
        "protocols/paper_upgrade_v2/online_state_audit_specs_v1.json",
        "protocols/paper_upgrade_v2/online_state_audit_registry_v1.json",
        "protocols/paper_upgrade_v2/online_state_audit_registry_v2.json",
        "protocols/paper_upgrade_v2/preregistration_v1.json",
        "protocols/paper_upgrade_v2/structural_baseline_registry_v1.json",
        "protocols/paper_upgrade_v2/public_benchmark_freeze_v1.json",
        "protocols/paper_upgrade_v2/adaptive_attack_freeze_v1.json",
        "protocols/paper_upgrade_v2/formal_matrix_controller_qualification_v5.json",
        "protocols/paper_upgrade_v2/deepseek_medium_matrix_candidate_v5.json",
        "protocols/paper_upgrade_v2/admissions/deepseek_medium_matrix_canary_admission_v5.json",
        "protocols/paper_upgrade_v2/admissions/deepseek_medium_matrix_continuation_admission_v5.json",
        "outputs/paper_upgrade_v2/formal_medium/deepseek/62eb641043a2fc50cbaac439b047de5c433c38b20ff9c06d8ff6d92dd71f90ae/six_condition_canary_review_v5.json",
        "outputs/paper_upgrade_v2/formal_medium/deepseek/62eb641043a2fc50cbaac439b047de5c433c38b20ff9c06d8ff6d92dd71f90ae/formal_matrix_abort_review_v1.json",
        "protocols/paper_upgrade_v2/formal_matrix_controller_qualification_v6.json",
        "protocols/paper_upgrade_v2/deepseek_medium_matrix_candidate_v6.json",
        "protocols/paper_upgrade_v2/admissions/deepseek_medium_matrix_canary_admission_v6.json",
        "protocols/paper_upgrade_v2/admissions/deepseek_medium_matrix_continuation_admission_v6.json",
        "outputs/paper_upgrade_v2/formal_medium/deepseek/6c16117e0451a01dd20409f60395035c110e5eb7c0be078d386a0e138e4fb2f9/six_condition_canary_review_v6.json",
        "protocols/paper_upgrade_v2/formal_result_gate_qualification_v3.json",
        "protocols/paper_upgrade_v2/deepseek_medium_result_gate_candidate_v3.json",
        "outputs/paper_upgrade_v2/formal_medium/deepseek/6c16117e0451a01dd20409f60395035c110e5eb7c0be078d386a0e138e4fb2f9/formal_matrix_abort_review_v2.json",
        "protocols/paper_upgrade_v2/formal_matrix_controller_qualification_v7.json",
        "protocols/paper_upgrade_v2/deepseek_medium_matrix_candidate_v7.json",
        "protocols/paper_upgrade_v2/admissions/deepseek_medium_matrix_canary_admission_v7.json",
        "protocols/paper_upgrade_v2/formal_result_gate_qualification_v4.json",
        "outputs/paper_upgrade_v2/formal_medium/deepseek/a34fe5b87607cb48144b0d36da282accc25d33cd18706351eb39dd25ebe04c75/formal_matrix_abort_review_v3.json",
        "protocols/paper_upgrade_v2/formal_matrix_controller_qualification_v8.json",
        "protocols/paper_upgrade_v2/deepseek_medium_matrix_candidate_v8.json",
        "protocols/paper_upgrade_v2/admissions/deepseek_medium_matrix_canary_admission_v8.json",
        "protocols/paper_upgrade_v2/formal_result_gate_qualification_v5.json",
        "outputs/paper_upgrade_v2/formal_medium/deepseek/8d08cab3febccdf5a4360d208766c39cef851fa9ec8b9c15799ee30171a213bf/six_condition_canary_review_v8.json",
        "protocols/paper_upgrade_v2/deepseek_medium_result_gate_candidate_v5.json",
        "protocols/paper_upgrade_v2/admissions/deepseek_medium_matrix_continuation_admission_v8.json",
        "protocols/paper_upgrade_v2/formal_matrix_remainder_qualification_v9.json",
        "protocols/paper_upgrade_v2/deepseek_medium_remainder_candidate_v9.json",
        "protocols/paper_upgrade_v2/admissions/deepseek_medium_remainder_admission_v9.json",
        "protocols/paper_upgrade_v2/formal_result_gate_qualification_v6.json",
        "protocols/paper_upgrade_v2/deepseek_medium_combined_result_gate_candidate_v6.json",
        "protocols/paper_upgrade_v2/admissions/deepseek_medium_combined_result_admission_v6.json",
        "protocols/paper_upgrade_v2/formal_analysis_amendment_qualification_v7.json",
        "protocols/paper_upgrade_v2/deepseek_medium_analysis_amendment_candidate_v7.json",
        "protocols/paper_upgrade_v2/formal_analysis_amendment_qualification_v8.json",
        "protocols/paper_upgrade_v2/deepseek_medium_analysis_amendment_candidate_v8.json",
        "outputs/paper_upgrade_v2/formal_medium/deepseek/ba9c7937d08b68e088faf8586e0dd96d2052a398fd0a77889fd6a62e503f2373/formal_result_technical_review_v6.json",
        "outputs/paper_upgrade_v2/formal_medium/deepseek/ba9c7937d08b68e088faf8586e0dd96d2052a398fd0a77889fd6a62e503f2373/admitted_medium_analysis_v8.json",
        "protocols/paper_upgrade_v2/formal_result_gate_qualification_v2.json",
        "protocols/paper_upgrade_v2/deepseek_medium_result_gate_candidate_v2.json",
        "outputs/paper_upgrade_v2/formal_medium/deepseek/dd794dd88eade41166bdafb7cb191898d7d19a5d8df737340f6acc3daac4504f/formal_result_technical_review_v1.json",
        "protocols/paper_upgrade_v2/research_assets_manifest_v1.json",
        "protocols/paper_upgrade_v2/independent_blind_authoring_kit_v1/status.json",
        "docs/research/paper_v2/manuscript/claim_evidence_ledger_v1.json",
        "docs/research/paper_v2/manuscript/completion_scorecard_v1.json",
        "outputs/paper_upgrade_v2/medium/analysis_v1.json",
        "schemas/attack_case.schema.json",
        "schemas/paper_v2/experiment_record_v1.schema.json",
        "schemas/paper_v2/experiment_record_v2.schema.json",
        "schemas/paper_v2/provider_trace_attestation_v2.schema.json",
        "schemas/paper_v2/provider_trace_bundle_v2.schema.json",
        "schemas/paper_v2/pilot_admission_manifest_v2.schema.json",
        "schemas/paper_v2/formal_matrix_admission_v1.schema.json",
        "schemas/paper_v2/formal_matrix_admission_v2.schema.json",
        "schemas/paper_v2/formal_matrix_admission_v3.schema.json",
        "schemas/paper_v2/formal_matrix_admission_v4.schema.json",
        "schemas/paper_v2/formal_matrix_admission_v5.schema.json",
        "schemas/paper_v2/formal_matrix_admission_v6.schema.json",
        "schemas/paper_v2/formal_result_gate_v1.schema.json",
        "schemas/paper_v2/formal_result_gate_v2.schema.json",
        "schemas/paper_v2/formal_result_gate_v3.schema.json",
        "schemas/paper_v2/formal_result_gate_v4.schema.json",
        "schemas/paper_v2/formal_matrix_admission_v7.schema.json",
        "schemas/paper_v2/formal_matrix_admission_v8.schema.json",
        "schemas/paper_v2/formal_result_gate_v5.schema.json",
        "schemas/paper_v2/formal_matrix_remainder_admission_v9.schema.json",
        "schemas/paper_v2/formal_result_gate_v6.schema.json",
        "schemas/paper_v2/formal_analysis_amendment_v7.schema.json",
        "schemas/paper_v2/formal_analysis_amendment_v8.schema.json",
        "schemas/paper_v2/gemini_fallback_admission_v1.schema.json",
        "schemas/paper_v2/adaptive_cost_canary_admission_v1.schema.json",
        "protocols/paper_upgrade_v2/adaptive_cost_canary_candidate_v1.json",
        "protocols/paper_upgrade_v2/adaptive_result_gate_v1.json",
        "protocols/paper_upgrade_v2/adaptive_cost_canary_abort_review_v1.json",
        "protocols/paper_upgrade_v2/adaptive_cost_canary_candidate_v2.json",
        "protocols/paper_upgrade_v2/admissions/adaptive_cost_canary_admission_v2.json",
        "protocols/paper_upgrade_v2/adaptive_result_gate_v2.json",
        "outputs/paper_upgrade_v2/adaptive_cost_canary_v2/primary/adaptive_v2_recovery_review_v3.json",
        "protocols/paper_upgrade_v2/adaptive_cost_canary_recovery_candidate_v3.json",
        "protocols/paper_upgrade_v2/admissions/adaptive_cost_canary_admission_v3.json",
        "outputs/paper_upgrade_v2/adaptive_cost_canary_v2/primary/technical_cost_review_v3.json",
        "outputs/paper_upgrade_v2/adaptive_cost_canary_v2/primary/technical_cost_review_v3_1.json",
        "protocols/paper_upgrade_v2/adaptive_canary_result_candidate_v1.json",
        "protocols/paper_upgrade_v2/admissions/adaptive_canary_result_admission_v1.json",
        "outputs/paper_upgrade_v2/adaptive_cost_canary_v2/analysis_v1/analysis_manifest.json",
        "outputs/paper_upgrade_v2/adaptive_cost_canary_v2/analysis_v1/summary.json",
        "outputs/paper_upgrade_v2/adaptive_cost_canary_v2/analysis_v1/analysis_review_v1.json",
        "schemas/paper_v2/adaptive_cost_canary_candidate_v2.schema.json",
        "schemas/paper_v2/adaptive_cost_canary_admission_v2.schema.json",
        "protocols/paper_upgrade_v2/public_primary_canary_abort_review_v1.json",
        "protocols/paper_upgrade_v2/public_primary_canary_abort_review_v2.json",
        "protocols/paper_upgrade_v2/admissions/deepseek_public_primary_canary_admission_v2.json",
        "protocols/paper_upgrade_v2/public_agentdojo_live_dependency_qualification_v2.json",
        "protocols/paper_upgrade_v2/public_matrix_controller_qualification_v2.json",
        "protocols/paper_upgrade_v2/public_matrix_candidate_v2.json",
        "protocols/paper_upgrade_v2/public_m3_live_dependency_qualification_v3.json",
        "protocols/paper_upgrade_v2/public_matrix_controller_qualification_v3.json",
        "protocols/paper_upgrade_v2/public_matrix_candidate_v3.json",
        "protocols/paper_upgrade_v2/public_primary_canary_abort_review_v3.json",
        "protocols/paper_upgrade_v2/public_m3_live_dependency_qualification_v4.json",
        "protocols/paper_upgrade_v2/public_matrix_controller_qualification_v4.json",
        "protocols/paper_upgrade_v2/public_matrix_candidate_v4.json",
        "protocols/paper_upgrade_v2/public_primary_continuation_candidate_v1.json",
        "protocols/paper_upgrade_v2/experiment_closeout_candidate_v1.json",
        "protocols/paper_upgrade_v2/formal_matrix_v7_immutable_audit_v1.json",
        "protocols/paper_upgrade_v2/experiment_closeout_day1_harness_review_v1.json",
        "protocols/paper_upgrade_v2/experiment_closeout_day2_harness_failure_review_v1.json",
        "protocols/paper_upgrade_v2/experiment_closeout_interim_harness_failure_review_v3.json",
        "protocols/paper_upgrade_v2/sandbox_git_safe_directory_qualification_v1.json",
        "protocols/paper_upgrade_v2/experiment_closeout_fresh_harness_failure_review_v5.json",
        "protocols/paper_upgrade_v2/experiment_closeout_fresh_harness_failure_review_v10.json",
        "protocols/paper_upgrade_v2/adaptive_execution_order_supersession_v2.json",
        "protocols/paper_upgrade_v2/independent_blind_day1_registration_acceptance_v1.json",
        "protocols/paper_upgrade_v2/gemini_public_canary_candidate_v4.json",
        "protocols/paper_upgrade_v2/gemini_free_tier_duration_qualification_v1.json",
        "protocols/paper_upgrade_v2/gemini_public_continuation_candidate_v1.json",
        "protocols/paper_upgrade_v2/gemini_public_continuation_candidate_v2.json",
        "protocols/paper_upgrade_v2/gemini_public_v4_s0_wrapper_recovery_v1.json",
        "protocols/paper_upgrade_v2/gemini_local_precommit_contract_v2_1_candidate.json",
        "protocols/paper_upgrade_v2/gemini_public_canary_recovery_candidate_v5.json",
        "outputs/paper_upgrade_v2/formal_public/gemini/public-v4-canary-s0-ab5ec080f3b268d77f1dbe41db03601a49281cfc1bc602bcbce0395bdda530c5/technical_segment_review_v5.json",
        "protocols/paper_upgrade_v2/gemini_adaptive_quota_candidate_v1.json",
        "protocols/paper_upgrade_v2/public_second_continuation_abort_review_v3.json",
        "protocols/paper_upgrade_v2/public_second_continuation_recovery_candidate_v3.json",
        "protocols/paper_upgrade_v2/public_second_evidence_merge_v1.json",
        "schemas/paper_v2/public_matrix_candidate_v2.schema.json",
        "schemas/paper_v2/public_matrix_admission_v2.schema.json",
        "schemas/paper_v2/public_matrix_candidate_v3.schema.json",
        "schemas/paper_v2/public_matrix_admission_v3.schema.json",
        "schemas/paper_v2/public_matrix_candidate_v4.schema.json",
        "schemas/paper_v2/public_matrix_admission_v4.schema.json",
        "schemas/paper_v2/public_sharded_continuation_candidate_v1.schema.json",
        "protocols/paper_upgrade_v2/public_primary_continuation_abort_review_v1.json",
        "protocols/paper_upgrade_v2/public_primary_continuation_qualification_v2.json",
        "protocols/paper_upgrade_v2/public_primary_continuation_candidate_v2.json",
        "protocols/paper_upgrade_v2/admissions/deepseek_public_primary_continuation_s0_admission_v2.json",
        "protocols/paper_upgrade_v2/admissions/deepseek_public_primary_continuation_s1_admission_v2.json",
        "protocols/paper_upgrade_v2/admissions/deepseek_public_primary_continuation_s2_admission_v2.json",
        "protocols/paper_upgrade_v2/admissions/deepseek_public_primary_continuation_s3_admission_v2.json",
        "protocols/paper_upgrade_v2/public_primary_continuation_s0_candidate_v3.json",
        "protocols/paper_upgrade_v2/public_primary_continuation_s1_candidate_v3.json",
        "protocols/paper_upgrade_v2/public_primary_continuation_s2_candidate_v3.json",
        "protocols/paper_upgrade_v2/public_primary_continuation_s3_candidate_v3.json",
        "protocols/paper_upgrade_v2/admissions/deepseek_public_primary_continuation_s0_admission_v3.json",
        "protocols/paper_upgrade_v2/admissions/deepseek_public_primary_continuation_s1_admission_v3.json",
        "protocols/paper_upgrade_v2/admissions/deepseek_public_primary_continuation_s2_admission_v3.json",
        "protocols/paper_upgrade_v2/admissions/deepseek_public_primary_continuation_s3_admission_v3.json",
        "protocols/paper_upgrade_v2/public_primary_merge_review_v2.json",
        "protocols/paper_upgrade_v2/public_primary_result_candidate_v1.json",
        "protocols/paper_upgrade_v2/admissions/public_primary_result_admission_v1.json",
        "protocols/paper_upgrade_v2/public_primary_analysis_validation_correction_candidate_v2.json",
        "protocols/paper_upgrade_v2/public_primary_analysis_validation_correction_candidate_v3.json",
        "protocols/paper_upgrade_v2/public_primary_analysis_validation_correction_candidate_v4.json",
        "protocols/paper_upgrade_v2/public_primary_analysis_validation_correction_candidate_v5.json",
        "protocols/paper_upgrade_v2/admissions/public_primary_analysis_validation_correction_admission_v2.json",
        "protocols/paper_upgrade_v2/admissions/public_primary_analysis_validation_correction_admission_v3.json",
        "protocols/paper_upgrade_v2/admissions/public_primary_analysis_validation_correction_admission_v4.json",
        "protocols/paper_upgrade_v2/admissions/public_primary_analysis_validation_correction_admission_v5.json",
        "outputs/paper_upgrade_v2/formal_public/primary_analysis_v5/analysis_manifest.json",
        "outputs/paper_upgrade_v2/formal_public/primary_analysis_v5/public_primary_analysis_summary_v5.json",
        "outputs/paper_upgrade_v2/formal_public/primary_analysis_v5/independent_analysis_review_v5.json",
        "docs/research/paper_v2/manuscript/bibliography_build_v1.json",
        "docs/research/paper_v2/manuscript/completion_scorecard_v2.json",
        "schemas/paper_v2/public_sharded_continuation_candidate_v2.schema.json",
        "schemas/paper_v2/public_sharded_continuation_admission_v2.schema.json",
        "schemas/paper_v2/public_primary_merge_review_v1.schema.json",
        "schemas/paper_v2/public_sharded_continuation_admission_v1.schema.json",
        "schemas/paper_v2/provider_safety_receipt_v1.schema.json",
        "schemas/paper_v2/post_pilot_review_v1.schema.json",
        "schemas/run_log.schema.json",
        "schemas/tool_call.schema.json"
    )) {
        Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json | Out-Null
        Write-Host "parsed $Path"
    }
}

Invoke-Check "PowerShell syntax" {
    foreach ($Path in @(
        "harness/scripts/verify.ps1",
        "harness/scripts/test.ps1",
        "harness/scripts/run_full_verification.ps1",
        "scripts/run_final_dashboard.ps1",
        "outputs/verification/start_experiment_closeout_fresh_harness_v4.ps1",
        "outputs/verification/start_experiment_closeout_fresh_harness_v5.ps1",
        "outputs/verification/start_experiment_closeout_fresh_harness_v6.ps1",
        "outputs/verification/start_experiment_closeout_fresh_harness_v11.ps1",
        "outputs/verification/start_experiment_closeout_fresh_harness_v12.ps1",
        "harness/scripts/verify_with_receipt_v3.ps1",
        "outputs/verification/run_deepseek_flash_public_second_recovery_v3_guarded.ps1",
        "outputs/verification/run_gemini_public_v5_segment_guarded.ps1"
    )) {
        $Tokens = $null
        $Errors = $null
        [System.Management.Automation.Language.Parser]::ParseFile(
            (Resolve-Path -LiteralPath $Path).Path,
            [ref]$Tokens,
            [ref]$Errors
        ) | Out-Null
        if ($Errors.Count -gt 0) {
            throw "$Path parse errors: $($Errors.Message -join '; ')"
        }
    }
}

if (Get-Command bash -ErrorAction SilentlyContinue) {
    Invoke-Check "Shell syntax" {
        Invoke-External "bash" @(
            "-n",
            "harness/scripts/init.sh",
            "harness/scripts/verify.sh",
            "harness/scripts/test.sh",
            "harness/scripts/cleanup.sh"
        )
    }
}

Invoke-Check "Python compile" {
    Invoke-External $PythonExe @("-m", "compileall", "-q", "m3_core", "m3_guard", "m3_attacks", "m3_eval", "experiments", "tests", "scripts")
}

Invoke-Check "Unit and integration tests" {
    Invoke-External "powershell" @(
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
        "harness/scripts/test.ps1", "-PythonExe", $PythonExe
    )
}

Invoke-Check "Experiment registry structure" {
    Invoke-External $PythonExe @("-m", "experiments.validate_registry")
}

Invoke-Check "Paper-v2 source-audit evidence" {
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.source_audit",
        "--spec", "protocols/paper_upgrade_v2/online_state_audit_specs_v1.json",
        "--verify-only"
    )
}

Invoke-Check "Paper-v2 frozen study assets" {
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.medium_case_selection",
        "--spec", "protocols/paper_upgrade_v2/medium_selection_spec_v1.json",
        "--verify-only"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.provider_gate",
        "--verify-only"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.provider_budget",
        "--verify-only"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.provider_execution_gate",
        "--verify-only"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.provider_live_qualification",
        "--verify-only"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.provider_live_qualification_v2",
        "--verify-only"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.provider_request_trace_candidate",
        "--verify-only"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.provider_request_trace_activation",
        "--verify-only"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.provider_trace_runtime_qualification",
        "--verify-only"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.formal_execution_controller_v2",
        "--verify-candidate"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.formal_execution_controller_v2",
        "--verify-qualification"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.formal_matrix_controller_v1",
        "--verify-qualification"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.formal_matrix_controller_v1",
        "--verify-candidate"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.deepseek_nonthinking_client_v1",
        "--verify-only"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.formal_matrix_controller_v2",
        "--verify-qualification"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.formal_matrix_controller_v2",
        "--verify-candidate"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.formal_matrix_controller_v3",
        "--verify-qualification"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.formal_matrix_controller_v3",
        "--verify-candidate"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.formal_matrix_controller_v3",
        "--verify-canary-admission"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.deepseek_json_client_v2",
        "--verify-only"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.formal_matrix_controller_v4",
        "--verify-qualification"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.formal_matrix_controller_v4",
        "--verify-candidate"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.formal_matrix_controller_v4",
        "--verify-canary-admission"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.formal_matrix_controller_v4",
        "--verify-continuation-admission"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.formal_matrix_controller_v5",
        "--verify-qualification"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.formal_matrix_controller_v5",
        "--verify-candidate"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.formal_matrix_controller_v5",
        "--verify-canary-admission"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.formal_matrix_controller_v5",
        "--verify-continuation-admission"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.formal_matrix_abort_review_v1"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.formal_matrix_controller_v6",
        "--verify-qualification"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.formal_matrix_controller_v6",
        "--verify-candidate"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.formal_matrix_controller_v6",
        "--verify-canary-admission"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.formal_matrix_controller_v6",
        "--verify-continuation-admission"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.formal_result_gate_v1",
        "--verify-qualification"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.formal_result_gate_v1",
        "--verify-candidate"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.formal_result_gate_v2",
        "--verify-qualification"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.formal_result_gate_v2",
        "--verify-candidate"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.formal_result_gate_v3",
        "--verify-qualification"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.formal_result_gate_v3",
        "--verify-candidate"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.formal_matrix_abort_review_v2"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.formal_matrix_controller_v7",
        "--verify-qualification"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.formal_matrix_controller_v7",
        "--verify-candidate"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.formal_matrix_controller_v7",
        "--verify-canary-admission"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.formal_result_gate_v4",
        "--verify-qualification"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.formal_matrix_abort_review_v3"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.formal_matrix_controller_v8",
        "--verify-qualification"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.formal_matrix_controller_v8",
        "--verify-candidate"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.formal_matrix_controller_v8",
        "--verify-canary-admission"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.formal_result_gate_v5",
        "--verify-qualification"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.formal_matrix_controller_v8",
        "--verify-continuation-admission"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.formal_result_gate_v5",
        "--verify-candidate"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.formal_matrix_remainder_controller_v9",
        "--verify-qualification"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.formal_matrix_remainder_controller_v9",
        "--verify-candidate"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.formal_matrix_remainder_controller_v9",
        "--verify-admission"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.formal_result_gate_v6",
        "--verify-qualification"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.formal_result_gate_v6",
        "--verify-candidate"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.formal_analysis_amendment_v8",
        "--verify-analysis"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.gemini_fallback_controller_v1",
        "--verify-frozen"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.post_pilot_evidence_review",
        "--verify-qualification"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.gemini_quota_snapshot",
        "--verify-only"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.formal_condition_executors",
        "--verify-only"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.formal_record_store",
        "--verify-only"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.formal_record_store_v2",
        "--verify-only"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.live_condition_runtime",
        "--verify-only"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.promptguard_live_dependency",
        "--verify-only"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.agentdojo_live_dependency",
        "--verify-only"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.m3_offline_evaluator",
        "--verify-only"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.exact_gold_ablation",
        "--verify-only"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.vigil_live_dependency",
        "--verify-only"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.medium_execution",
        "--verify-only"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.medium_runtime",
        "--verify-only"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.citation_integrity",
        "--verify-only"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.structural_baselines",
        "--verify-only"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.research_assets",
        "--verify-only"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.medium_analysis",
        "--verify-only"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.adaptive_cost_canary_controller_v1",
        "--verify-candidate"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.adaptive_result_gate_v1",
        "--verify"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.adaptive_cost_canary_abort_review_v1",
        "--verify"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.adaptive_cost_canary_controller_v2",
        "--verify-candidate"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.adaptive_cost_canary_controller_v2",
        "--verify-admission"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.adaptive_result_gate_v2",
        "--verify-gate"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.adaptive_cost_canary_recovery_v3",
        "--verify-candidate"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.adaptive_cost_canary_recovery_v3",
        "--verify-admission"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.adaptive_recovery_technical_review_v1",
        "--verify"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.adaptive_canary_result_admission_v1",
        "--verify-candidate"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.adaptive_canary_result_admission_v1",
        "--verify-admission"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.adaptive_canary_analysis_review_v1",
        "--verify"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.public_abort_review_v1",
        "--verify"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.public_abort_review_v2",
        "--verify"
    )
    Invoke-External $PythonExe @(
        "-m",
        "experiments.paper_v2.public_sharded_continuation_abort_review_v1",
        "--verify"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.public_sharded_continuation_v2",
        "--verify-qualification"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.public_sharded_continuation_v2",
        "--verify-candidate"
    )
    foreach ($ShardIndex in 0..3) {
        Invoke-External $PythonExe @(
            "-m", "experiments.paper_v2.public_sharded_continuation_v2",
            "--verify-admission",
            "--shard-index", "$ShardIndex"
        )
    }
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.public_agentdojo_live_dependency_v2",
        "--verify"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.public_matrix_controller_v2",
        "--verify-stage-a"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.public_m3_live_dependency_v3",
        "--verify"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.public_matrix_controller_v3",
        "--verify-stage-a"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.public_abort_review_v3",
        "--verify"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.public_m3_live_dependency_v4",
        "--verify"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.public_matrix_controller_v4",
        "--verify-stage-a"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.public_sharded_continuation_v1",
        "--verify-candidate", "--model-role", "primary"
    )
    foreach ($ShardIndex in 0..3) {
        Invoke-External $PythonExe @(
            "-m", "experiments.paper_v2.public_single_shard_recovery_v3",
            "--verify-candidate", "--shard-index", "$ShardIndex"
        )
        Invoke-External $PythonExe @(
            "-m", "experiments.paper_v2.public_single_shard_recovery_v3",
            "--verify-admission", "--shard-index", "$ShardIndex"
        )
        Invoke-External $PythonExe @(
            "-m", "experiments.paper_v2.public_shard_evidence_review_v1",
            "--verify", "--shard-index", "$ShardIndex"
        )
    }
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.public_primary_merge_review_v2",
        "--verify"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.public_primary_result_admission_v1",
        "--verify-candidate"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.public_primary_result_admission_v1",
        "--verify-admission"
    )
    foreach ($CorrectionVersion in 2..5) {
        $CorrectionModule = (
            "experiments.paper_v2.public_primary_analysis_" +
            "validation_correction_v$CorrectionVersion"
        )
        Invoke-External $PythonExe @(
            "-m", $CorrectionModule, "--verify-candidate"
        )
        Invoke-External $PythonExe @(
            "-m", $CorrectionModule, "--verify-admission"
        )
    }
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.public_primary_analysis_v5",
        "--verify",
        "--admission",
        "protocols/paper_upgrade_v2/admissions/public_primary_analysis_validation_correction_admission_v5.json"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.public_primary_analysis_review_v5",
        "--verify"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.build_bibliography_v1",
        "--verify"
    )
}

Invoke-Check "Paper-v2 experiment closeout prospective evidence" {
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.experiment_closeout_freeze_v1"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.experiment_closeout_day1_harness_review_v1",
        "--verify-review"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.experiment_closeout_day2_harness_failure_review_v1",
        "--verify-review"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.experiment_closeout_interim_harness_failure_review_v3",
        "--verify-review"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.sandbox_git_safe_directory_qualification_v1",
        "--verify-qualification"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.experiment_closeout_fresh_harness_failure_review_v5",
        "--verify-review"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.experiment_closeout_fresh_harness_failure_review_v10",
        "--verify-review"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.adaptive_execution_order_gate_v2",
        "--verify-review"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.adaptive_formal_pro_controller_v2",
        "--verify-candidate", "--stage", "pro_50"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.adaptive_formal_pro_controller_v2",
        "--verify-admission", "--stage", "pro_50"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.adaptive_formal_pro_200_host_timeout_review_v1",
        "--verify-review"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.adaptive_formal_pro_controller_v2",
        "--verify-candidate", "--stage", "pro_500"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.adaptive_formal_pro_controller_v2",
        "--verify-admission", "--stage", "pro_500"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.experiment_closeout_harness_gate_v7",
        "--verify-gate"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.independent_blind_day1_acceptance_v1",
        "--verify-acceptance"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.gemini_free_tier_duration_qualification_v1",
        "--verify"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.gemini_public_controller_v4",
        "--verify-candidate"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.gemini_public_controller_v4",
        "--verify-admission", "--segment-index", "0",
        "--quota-day", "2026-08-02"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.gemini_public_technical_review_v5",
        "--verify-segment-review", "--segment-index", "0",
        "--quota-day", "2026-08-02"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.gemini_public_v4_wrapper_recovery_v1",
        "--verify-recovery"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.gemini_public_continuation_plan_v1",
        "--verify-candidate"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.gemini_public_continuation_plan_v2",
        "--verify-candidate"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.gemini_local_precommit_contract_v2_candidate",
        "--verify"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.gemini_public_controller_v5",
        "--verify-candidate"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.gemini_adaptive_quota_schedule_v1",
        "--verify-candidate"
    )
    foreach ($ModelKey in @("deepseek_flash", "gemini_flash")) {
        Invoke-External $PythonExe @(
            "-m", "experiments.paper_v2.adaptive_formal_second_plan_v1",
            "--verify-candidate", "--model-key", $ModelKey
        )
    }
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.adaptive_formal_pro_controller_v1",
        "--verify-candidate", "--stage", "pro_50"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.adaptive_formal_deepseek_flash_controller_v1",
        "--verify-candidate", "--stage", "flash_50"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.public_second_continuation_v2",
        "--verify-qualification"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.public_second_continuation_v2",
        "--verify-candidate"
    )
    foreach ($ShardIndex in @(0, 1)) {
        Invoke-External $PythonExe @(
            "-m", "experiments.paper_v2.public_second_continuation_v2",
            "--verify-admission", "--shard-index", "$ShardIndex"
        )
    }
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.public_second_continuation_recovery_v3",
        "--verify-abort-review"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.public_second_continuation_recovery_v3",
        "--verify-candidate"
    )
    foreach ($ShardIndex in @(0, 1)) {
        Invoke-External $PythonExe @(
            "-m", "experiments.paper_v2.public_second_recovery_evidence_review_v4",
            "--verify", "--shard-index", "$ShardIndex"
        )
    }
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.public_second_evidence_merge_v1",
        "--verify"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.experiment_closeout_harness_gate_v4",
        "--verify-gate"
    )
    Invoke-External $PythonExe @(
        "-m", "experiments.paper_v2.experiment_closeout_harness_gate_v5",
        "--verify-gate"
    )
    # Gate v6 was a prospective single-use Pro-200 gate.  After Pro-200
    # completed, replaying its untouched-output precondition must fail closed.
    # The immutable Pro-200 host-timeout review and gate v7 now bind that
    # historical gate and the completed execution chain.
}

if (Test-Path -LiteralPath "outputs/experiments/e17_source_index_corrected_v2.json" -PathType Leaf) {
    Invoke-Check "Historical evidence and current V2 freeze" {
        Invoke-External $PythonExe @("scripts/verify_historical_evidence.py")
    }
}

if ($RequireExperimentsComplete) {
    Invoke-Check "Experiment registry complete" {
        Invoke-External $PythonExe @("-m", "experiments.validate_registry", "--require-complete")
    }
}

Write-Host "`nVerification failed=$script:Failed"
exit $script:Failed
