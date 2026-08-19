# AgentDojo official strong-baseline capability audit v1

Generated: 2026-07-22T07:42:48.434913+00:00

## Result

- Status: `completed`
- Passed checks: 9/9
- Formal result eligible: `False`
- Q2 strong-baseline gate: `not_satisfied`

## Official defenses found

- repeat_user_prompt, spotlighting_with_delimiting, tool_filter, transformers_pi_detector

## Baseline capability summary

| Baseline | Official defense | Status | Main blockers |
|---|---|---|---|
| `agentdojo_tool_filter` | `tool_filter` | `ready_official_tool_filter_qualification_completed_formal_run_pending` | none recorded |
| `agentdojo_transformers_pi_detector` | `transformers_pi_detector` | `ready_for_official_smoke_pending_run` | none recorded |

## Dependency probe

- `python_executable`: F:\robot\Anaconda3\python.exe
- `agentdojo_checkout_exists`: True
- `agentdojo_source_layout_present`: True
- `agentdojo_defenses`: tool_filter, transformers_pi_detector, spotlighting_with_delimiting, repeat_user_prompt
- `openai_api_key_present`: False
- `openai_compatible_base_url_present`: False
- `openai_package_installed`: True
- `transformers_installed`: False
- `torch_installed`: True
- `huggingface_hub_installed`: True
- `protectai_detector_cached`: True
- `protectai_detector_cache_path`: E:\ai_cache\huggingface\hub\models--protectai--deberta-v3-base-prompt-injection-v2
- `protectai_detector_refs_main`: 90c9989b1a342275dd0d1a95aad283c04e075671
- `hf_hub_cache`: E:\ai_cache\huggingface\hub
- `transformers_runtime_smoke_manifest`: outputs/paper_upgrade_v1/baselines/agentdojo_transformers_pi_detector_smoke_v1/smoke_manifest.json
- `transformers_runtime_smoke_sha256`: e57b93751f36b8c3b50d16a981f96da84946ff3a2e9287a3f2091ff117ea34cf
- `transformers_runtime_smoke_status`: completed_official_detector_smoke_only
- `transformers_runtime_smoke_required_passed`: 3
- `transformers_runtime_smoke_required_total`: 3
- `transformers_runtime_smoke_python`: E:\M3_PI_Guard_runtime\promptguard\Scripts\python.exe
- `transformers_runtime_ready`: True
- `tool_filter_freeze`: protocols/paper_upgrade_v1/agentdojo_tool_filter_formal_freeze_v1.json
- `tool_filter_freeze_sha256`: 801f9a690aedd67ad93442a4f46f2d217f409f2a4d050005a8f1a67ee9473f1f
- `tool_filter_freeze_status`: completed_frozen_formal_protocol
- `tool_filter_freeze_model_id`: m3-paper-qwen3-8b-v1:latest
- `tool_filter_freeze_prompt_sha256`: 30f4d1f2bd19f7d867ef322ad3faa0767bbf34e5dd5052b360a48a578c68f27f
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

## Official run command templates

### agentdojo_tool_filter

```powershell
cd external\benchmarks\agentdojo
python -m agentdojo.scripts.benchmark --model gpt-4o-2024-05-13 --defense tool_filter --attack tool_knowledge
```

### agentdojo_transformers_pi_detector

```powershell
cd external\benchmarks\agentdojo
python -m agentdojo.scripts.benchmark --model gpt-4o-2024-05-13 --defense transformers_pi_detector --attack tool_knowledge
```

## Checks

| Check | Status | Severity | Detail |
|---|---|---|---|
| `official_source_files_exist` | `pass` | `error` | {"benchmark_script": true, "pi_detector": true, "pipeline": true, "readme": true, "results_docs": true} |
| `official_defenses_list_contains_required_strong_baselines` | `pass` | `error` | {"official_defenses": ["repeat_user_prompt", "spotlighting_with_delimiting", "tool_filter", "transformers_pi_detector"]} |
| `pipeline_markers_present` | `pass` | `error` | {"defenses_constant": {"marker": "DEFENSES = [", "present": true}, "defenses_tool_filter": {"marker": "\"tool_filter\"", "present": true}, "defenses_transformers_pi_detector": {"marker": "\"transformers_pi_detector\""... |
| `pi_detector_markers_present` | `pass` | `error` | {"detector_class": {"marker": "class TransformersBasedPIDetector", "present": true}, "detector_decision_rule": {"marker": "safety_score < self.threshold", "present": true}, "detector_default_mode": {"marker": "mode: L... |
| `readme_benchmark_command_markers_present` | `pass` | `error` | {"benchmark_module_command": {"marker": "python -m agentdojo.scripts.benchmark", "present": true}, "tool_filter_example": {"marker": "--defense tool_filter", "present": true}, "tool_knowledge_attack_example": {"marker... |
| `dependency_probe_completed` | `pass` | `error` | {"agentdojo_checkout_exists": true, "agentdojo_defenses": ["tool_filter", "transformers_pi_detector", "spotlighting_with_delimiting", "repeat_user_prompt"], "agentdojo_source_layout_present": true, "hf_hub_cache": "E:... |
| `blocked_or_pending_baselines_not_result_eligible` | `pass` | `error` | {"agentdojo_tool_filter": false, "agentdojo_transformers_pi_detector": false} |
| `official_command_templates_recorded` | `pass` | `error` | {"agentdojo_tool_filter": "cd external\\benchmarks\\agentdojo\npython -m agentdojo.scripts.benchmark --model gpt-4o-2024-05-13 --defense tool_filter --attack tool_knowledge", "agentdojo_transformers_pi_detector": "cd ... |
| `official_strong_baselines_not_mixed_into_m3_local_runner` | `pass` | `error` | {"m3_runner_condition_ids": ["agentdojo_repeat_user_prompt", "agentdojo_spotlighting_with_delimiting", "m3_full", "m3_full_normal_prompt", "m3_no_confirmation", "m3_no_dataflow", "m3_no_provenance", "m3_no_temporal", ... |

## Boundary

Capability audit only. It confirms pinned official source markers and local blockers for AgentDojo's tool_filter and transformers_pi_detector. It is not a benchmark result and must not be included in formal ASR/TCR effect tables.
