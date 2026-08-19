# Baseline registry audit v1

Generated: 2026-07-22T09:39:07.142265+00:00

## Result

- Status: `completed`
- Passed checks: 11/11
- Q2 strong-baseline gate: `not_satisfied`
- Registry SHA-256: `7c0c117b0d18094ec69fc4156470330de7679ee92ae34d409143437f0b6fa346`

## Summary

- Condition count: 21
- Result-eligible by registry: agentdojo_tool_filter, m3_full, m3_full_normal_prompt, m3_no_confirmation, m3_no_dataflow, m3_no_provenance, m3_no_temporal, m3_policy_confirmation, m3_policy_only, no_defense, prompt_sandwich, promptguard, safe_prompt, spotlighting
- Blocked or pending: agentdojo_transformers_pi_detector, ipiguard

## Dependency probe

- `agentdojo_checkout_exists`: True
- `agentdojo_pipeline_sha256`: 0de07a163216b996b42da3db2032236ba15065a5a781ff2cdde206fbf8306ad9
- `openai_api_key_present`: False
- `transformers_installed`: False
- `torch_installed`: True
- `protectai_detector_cached`: True
- `protectai_detector_cache_path`: E:\ai_cache\huggingface\hub\models--protectai--deberta-v3-base-prompt-injection-v2
- `hf_hub_cache`: E:\ai_cache\huggingface\hub
- `transformers_runtime_smoke_manifest`: outputs/paper_upgrade_v1/baselines/agentdojo_transformers_pi_detector_smoke_v1/smoke_manifest.json
- `transformers_runtime_smoke_status`: completed_official_detector_smoke_only
- `transformers_long_output_direct_smoke_manifest`: outputs/paper_upgrade_v1/baselines/agentdojo_transformers_pi_detector_long_output_direct_smoke_v1/smoke_manifest.json
- `transformers_long_output_direct_smoke_status`: failed_long_output_direct_smoke
- `transformers_long_output_direct_smoke_chars`: 27697
- `transformers_long_output_resource_blocked`: True
- `transformers_runtime_smoke_required_passed`: 3
- `transformers_runtime_smoke_required_total`: 3
- `transformers_runtime_ready`: True
- `tool_filter_freeze`: protocols/paper_upgrade_v1/agentdojo_tool_filter_formal_freeze_v1.json
- `tool_filter_freeze_sha256`: 801f9a690aedd67ad93442a4f46f2d217f409f2a4d050005a8f1a67ee9473f1f
- `tool_filter_freeze_status`: completed_frozen_formal_protocol
- `tool_filter_freeze_model_id`: m3-paper-qwen3-8b-v1:latest
- `tool_filter_transport_provider`: openai-compatible
- `tool_filter_transport_ready`: True
- `tool_filter_qualification_manifest`: outputs/paper_upgrade_v1/baselines/agentdojo_tool_filter_official_qualification_v1/run_manifest.json
- `tool_filter_qualification_sha256`: f9e40da7f4a8ab56b5325f9939042563e2a37076407f06c97625c36f463c2c12
- `tool_filter_qualification_status`: completed_diagnostic_partial
- `tool_filter_qualification_completed`: True
- `tool_filter_qualification_cases`: {'attack_successes': 0, 'case_manifests': 2, 'completed_cases': 2, 'detector_redacted_cases': 0, 'expected_cases': 2, 'failed_cases': 0, 'missing_cases': 0, 'security_cases': 0, 'status_counts': {'completed': 2}, 'utility_cases': 2, 'utility_successes': 1}
- `tool_filter_openai_compatible_binding`: {'algorithm_changed': False, 'prompt_changed': False, 'reason': 'upstream tool_filter receives provider name as llm_name for openai-compatible local transports', 'rebound_elements': [{'class': 'OpenAILLMToolFilter', 'element_index': 2, 'model_after': 'm3-paper-qwen3-8b-v1:latest', 'model_before': 'openai-compatible'}], 'selection_rule_changed': False, 'shim': 'openai_compatible_tool_filter_model_binding'}
- `tool_filter_security_qualification_manifest`: outputs/paper_upgrade_v1/baselines/agentdojo_tool_filter_official_security_qualification_v1/run_manifest.json
- `tool_filter_security_qualification_sha256`: e463c2f30a1d1412f9783b43a5e97b497c82f072d84dd263192d03cab0c552d0
- `tool_filter_security_qualification_status`: completed_diagnostic_partial
- `tool_filter_security_qualification_completed`: True
- `tool_filter_security_qualification_cases`: {'attack_successes': 1, 'case_manifests': 2, 'completed_cases': 2, 'detector_redacted_cases': 0, 'expected_cases': 2, 'failed_cases': 0, 'missing_cases': 0, 'security_cases': 1, 'status_counts': {'completed': 2}, 'utility_cases': 1, 'utility_successes': 1}
- `tool_filter_security_openai_compatible_binding`: {'algorithm_changed': False, 'prompt_changed': False, 'reason': 'upstream tool_filter receives provider name as llm_name for openai-compatible local transports', 'rebound_elements': [{'class': 'OpenAILLMToolFilter', 'element_index': 2, 'model_after': 'm3-paper-qwen3-8b-v1:latest', 'model_before': 'openai-compatible'}], 'selection_rule_changed': False, 'shim': 'openai_compatible_tool_filter_model_binding'}
- `tool_filter_formal_run_manifest`: outputs/paper_upgrade_v1/baselines/agentdojo_tool_filter_official_formal_v1/run_manifest.json
- `tool_filter_formal_run_sha256`: 8f014192c9309b7f32129fe2dd39e9cf0f94b5976031c4352b3706facefb0225
- `tool_filter_formal_run_status`: completed_formal
- `tool_filter_formal_completed`: True
- `tool_filter_formal_analysis_manifest`: outputs/paper_upgrade_v1/baselines/agentdojo_tool_filter_official_formal_v1/analysis/analysis_manifest.json
- `tool_filter_formal_analysis_sha256`: ab170cd9e63c4f205a9ef334d4597a0be0121da58426541177c4c04dc6c08bbf
- `tool_filter_formal_analysis_status`: completed_formal_analysis
- `tool_filter_formal_analysis_completed`: True
- `agentdojo_defenses`: tool_filter, transformers_pi_detector, spotlighting_with_delimiting, repeat_user_prompt

## Checks

| Check | Status | Severity | Detail |
|---|---|---|---|
| `unique_condition_ids` | `pass` | `error` | ["no_defense", "safe_prompt", "spotlighting", "prompt_sandwich", "agentdojo_repeat_user_prompt", "agentdojo_spotlighting_with_delimiting", "m3_policy_only", "m3_policy_confirmation", "m3_full_normal_prompt", "m3_full"... |
| `required_external_baselines_represented` | `pass` | `error` | {"missing": []} |
| `required_agentdojo_official_baselines_represented` | `pass` | `error` | {"missing": []} |
| `ready_and_diagnostic_local_conditions_have_runtime_entries` | `pass` | `error` | {"missing_runtime_entries": []} |
| `blocked_or_pending_rows_not_result_eligible` | `pass` | `error` | [] |
| `blocked_or_pending_rows_have_exclusion_rules` | `pass` | `error` | [] |
| `blocked_or_pending_rows_have_blockers_and_plans` | `pass` | `error` | [] |
| `agentdojo_official_defenses_present_upstream` | `pass` | `error` | {"agentdojo_defenses": ["repeat_user_prompt", "spotlighting_with_delimiting", "tool_filter", "transformers_pi_detector"]} |
| `agentdojo_tool_filter_blocker_matches_probe` | `pass` | `warning` | {"openai_api_key_present": false, "registry_status": "ready", "tool_filter_formal_analysis_completed": true, "tool_filter_formal_analysis_status": "completed_formal_analysis", "tool_filter_formal_completed": true, "to... |
| `agentdojo_transformers_detector_blocker_matches_probe` | `pass` | `warning` | {"protectai_detector_cached": true, "registry_status": "source_backed_official_detector_resource_blocked_exact_formal", "transformers_installed": false, "transformers_long_output_direct_smoke_chars": 27697, "transform... |
| `q2_gate_not_satisfied_until_strong_baselines_ready` | `pass` | `warning` | {"current_gate_status": "not_satisfied", "formal_ready_count": 2, "formal_ready_strong_baselines": ["agentdojo_tool_filter", "promptguard"], "minimum_exact_or_disclosed_exclusion_count": 5, "required_named_methods": [... |

## Boundary

This audit is a readiness/exclusion gate. It does not convert blocked or pending strong baselines into formal comparison results.
