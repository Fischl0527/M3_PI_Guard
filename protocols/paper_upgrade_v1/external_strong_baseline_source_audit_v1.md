# External strong-baseline source audit v1

Generated: 2026-07-22T10:49:21.884385+00:00

## Result

- Status: `completed`
- Passed checks: 11/11
- Q2 strong-baseline gate: `not_satisfied`
- Formal result eligible: `False`
- Source checkout manifest status: `completed`

## Baselines covered

| Registry key | Entries |
|---|---|
| `camel_or_fides` | `camel_google_research`, `fides_microsoft` |
| `ipiguard` | `ipiguard_github_emnlp2025` |
| `progent` | `progent_arxiv2025` |
| `promptguard` | `promptguard_llama_prompt_guard_2` |
| `task_shield` | `task_shield_acl2025` |

## Dependency probe

- `python_executable`: F:\robot\Anaconda3\python.exe
- `python_version`: 3.13.5
- `transformers_installed`: False
- `torch_installed`: True
- `huggingface_hub_installed`: True
- `openai_installed`: True
- `uv_executable`: 
- `promptguard_model_cache`: {"meta-llama/Llama-Prompt-Guard-2-22M": {"complete_snapshot_revisions": [], "hub_cache_root": "E:\\ai_cache\\huggingface\\hub", "model_cache_complete": false, "model_cache_exists": false, "model_cache_path": "E:\\ai_cache\\huggingface\\hub\\models--meta-llama--Llama-Prompt-Guard-2-22M", "model_id": "meta-llama/Llama-Prompt-Guard-2-22M", "snapshot_count": 0, "snapshots": []}, "meta-llama/Llama-Prompt-Guard-2-86M": {"complete_snapshot_revisions": ["a8ded8e697ce7c355e395a0df51f94adb4a2fd27"], "hub_cache_root": "E:\\ai_cache\\huggingface\\hub", "model_cache_complete": true, "model_cache_exists": true, "model_cache_path": "E:\\ai_cache\\huggingface\\hub\\models--meta-llama--Llama-Prompt-Guard-2-86M", "model_id": "meta-llama/Llama-Prompt-Guard-2-86M", "snapshot_count": 1, "snapshots": [{"complete": true, "file_count": 10, "has_config": true, "has_tokenizer": true, "has_weights": true, "path": "E:\\ai_cache\\huggingface\\hub\\models--meta-llama--Llama-Prompt-Guard-2-86M\\snapshots\\a8ded8e697ce7c355e395a0df51f94adb4a2fd27", "revision": "a8ded8e697ce7c355e395a0df51f94adb4a2fd27"}]}}
- `external_baseline_checkouts`: {"camel": true, "fides": true, "ipiguard": true, "progent": true, "promptguard_purplellama": true}

## Entry statuses

| Entry | Status | Primary reference | Result eligible |
|---|---|---|---|
| `promptguard_llama_prompt_guard_2` | `completed_source_backed_formal_detector_baseline` | https://huggingface.co/meta-llama/Llama-Prompt-Guard-2-86M | `True` |
| `task_shield_acl2025` | `disclosed_paper_reproduction_v1_4_formal_running_failed_case_present` | https://aclanthology.org/2025.acl-long.1435/ | `False` |
| `ipiguard_github_emnlp2025` | `source_backed_v1_qualification_failed_v1_1_instrumented_requalification_pending` | https://aclanthology.org/2025.emnlp-main.53/ | `False` |
| `progent_arxiv2025` | `source_backed_v1_1_hash_bound_runner_analyzer_implemented_qualification_pending` | https://arxiv.org/abs/2504.11703 | `False` |
| `camel_google_research` | `official_source_smoke_completed_transport_mapping_hash_bound_formal_runner_ready_qualification_pending` | https://arxiv.org/abs/2503.18813 | `False` |
| `fides_microsoft` | `source_checkout_ready_not_selected` | https://www.microsoft.com/en-us/research/publication/securing-ai-agents-with-information-flow-control/ | `False` |

## Checks

| Check | Status | Severity | Detail |
|---|---|---|---|
| `unique_entry_ids` | `pass` | `error` | ["promptguard_llama_prompt_guard_2", "task_shield_acl2025", "ipiguard_github_emnlp2025", "progent_arxiv2025", "camel_google_research", "fides_microsoft"] |
| `required_registry_keys_covered` | `pass` | `error` | {"missing": [], "present": ["camel_or_fides", "ipiguard", "progent", "promptguard", "task_shield"]} |
| `entry_required_fields_present` | `pass` | `error` | {} |
| `all_entries_have_primary_reference_url` | `pass` | `error` | {"camel_google_research": ["https://arxiv.org/abs/2503.18813", "https://github.com/google-research/camel-prompt-injection"], "fides_microsoft": ["https://www.microsoft.com/en-us/research/publication/securing-ai-agents... |
| `all_entries_have_blockers_plans_and_exclusion_rules` | `pass` | `error` | [] |
| `blocked_entries_not_result_eligible` | `pass` | `error` | {"camel_google_research": false, "fides_microsoft": false, "ipiguard_github_emnlp2025": false, "progent_arxiv2025": false, "task_shield_acl2025": false} |
| `formal_entries_have_detector_scope_and_artifacts` | `pass` | `error` | {"promptguard_llama_prompt_guard_2": {"analysis_manifest": "outputs/paper_upgrade_v1/baselines/promptguard_detector_formal_v1/analysis/analysis_manifest.json", "complete_logs": ["outputs/paper_upgrade_v1/baselines/pro... |
| `promptguard_dependency_blockers_match_probe` | `pass` | `warning` | {"dependencies_ready": false, "promptguard_model_cache": {"meta-llama/Llama-Prompt-Guard-2-22M": {"complete_snapshot_revisions": [], "hub_cache_root": "E:\\ai_cache\\huggingface\\hub", "model_cache_complete": false, "... |
| `camel_or_fides_has_two_candidates` | `pass` | `warning` | ["camel_google_research", "fides_microsoft"] |
| `code_candidates_have_remote_head_or_are_declared_paper_only` | `pass` | `error` | {"camel_google_research": true, "fides_microsoft": true, "ipiguard_github_emnlp2025": true, "progent_arxiv2025": true, "promptguard_llama_prompt_guard_2": true, "task_shield_acl2025": false} |
| `local_checkouts_absent_or_recorded_in_source_manifest` | `pass` | `warning` | {"present_checkouts": {"camel": true, "fides": true, "ipiguard": true, "progent": true, "promptguard_purplellama": true}, "ready_entries": ["camel_google_research", "fides_microsoft", "ipiguard_github_emnlp2025", "pro... |

## Boundary

Source/readiness audit only. External baselines remain blocked or diagnostic until exact source, dependencies, adapters, frozen manifests and complete logs exist; entries with a declared formal result are eligible only for their explicitly recorded table scope.
