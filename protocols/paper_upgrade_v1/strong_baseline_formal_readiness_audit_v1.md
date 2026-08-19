# Strong-baseline formal-readiness audit v1

Generated: 2026-07-22T10:49:22.168444+00:00

## Result

- Status: `completed`
- Passed checks: 7/7
- Q2 strong-baseline gate: `not_satisfied`
- Formal-ready strong baselines: agentdojo_tool_filter, promptguard
- Result eligible for formal tables: `False`
- Dependency snapshot status: `completed`
- Dependency snapshot SHA-256: `86a52679e35881941effbf0ea8b254d1c76e22ad4886c6dbd763977172469b24`

## Formal admission rows

| Baseline | Status | Formal admission | Failed requirements |
|---|---|---|---|
| `agentdojo_tool_filter` | `ready` | `formal_ready` | none |
| `agentdojo_transformers_pi_detector` | `source_backed_official_detector_resource_blocked_exact_formal` | `blocked_or_diagnostic` | `condition_marked_ready`, `condition_result_eligible_true`, `current_blockers_empty`, `formal_manifest_and_complete_logs_declared` |
| `camel_or_fides` | `source_smoke_completed_transport_mapping_hash_bound_formal_runner_ready_qualification_pending` | `blocked_or_diagnostic` | `condition_marked_ready`, `condition_result_eligible_true`, `current_blockers_empty`, `external_entries_result_eligible_true`, `formal_manifest_and_complete_logs_declared` |
| `ipiguard` | `source_backed_adapter_runtime_qualification_failed_model_dag_schema` | `blocked_or_diagnostic` | `condition_marked_ready`, `condition_result_eligible_true`, `current_blockers_empty`, `external_entries_result_eligible_true`, `formal_manifest_and_complete_logs_declared` |
| `progent` | `source_backed_v1_1_hash_bound_formal_protocol_import_preflight_completed_qualification_pending` | `blocked_or_diagnostic` | `condition_marked_ready`, `condition_result_eligible_true`, `current_blockers_empty`, `external_entries_result_eligible_true`, `formal_manifest_and_complete_logs_declared` |
| `promptguard` | `ready_detector_only_formal` | `formal_ready` | none |
| `task_shield` | `disclosed_paper_reproduction_v1_4_formal_running_failed_case_present` | `blocked_or_diagnostic` | `condition_marked_ready`, `condition_result_eligible_true`, `current_blockers_empty`, `external_entries_result_eligible_true`, `formal_manifest_and_complete_logs_declared` |

## Checks

| Check | Status | Severity | Detail |
|---|---|---|---|
| `all_required_strong_baselines_present` | `pass` | `error` | [] |
| `blocked_or_pending_strong_baselines_not_result_eligible` | `pass` | `error` | [] |
| `blocked_or_pending_strong_baselines_have_exclusion_rules` | `pass` | `error` | [] |
| `blocked_or_pending_strong_baselines_have_current_blockers` | `pass` | `error` | [] |
| `no_formal_ready_baseline_without_all_admission_requirements` | `pass` | `error` | ["agentdojo_tool_filter", "promptguard"] |
| `camel_or_fides_not_admitted_without_formal_adapter` | `pass` | `warning` | ["condition_marked_ready", "condition_result_eligible_true", "current_blockers_empty", "external_entries_result_eligible_true", "formal_manifest_and_complete_logs_declared"] |
| `q2_gate_matches_formal_ready_count` | `pass` | `warning` | {"expected_gate": "not_satisfied", "formal_ready": ["agentdojo_tool_filter", "promptguard"], "formal_ready_count": 2, "minimum_required": 5, "registry_gate": "not_satisfied"} |

## Boundary

Formal-admission audit only. A strong baseline may enter paper result tables only after source-backed adapters, frozen dependency snapshots, formal manifests, complete logs and no-label-leakage checks exist. Current stub preflights remain outside formal effect claims.
