# Public benchmark formal freeze v1

Generated: 2026-07-18T13:23:22.853153+00:00

## Result

- Status: `completed`
- Formal freeze gate: `local_ready_matrix_declared_q2_gate_not_satisfied`
- Q2 public-benchmark gate: `not_satisfied`
- Ready local matrix case-runs: 53400
- Result eligible for formal tables: `False`

## Benchmark universe

| Benchmark | Utility | Security | Total | Case universe hash |
|---|---:|---:|---:|---|
| `agentdojo` | 97 | 629 | 726 | `204a0225433f955e7fc212999d8b05277e68481db638f9cae7e32c586588c4f5` |
| `injecagent` | 0 | 1054 | 1054 | `c5f78447210ccbf5c10f1a38f678b775d1fd517b1932b8a39ae0087aa9d43ad3` |

## Conditions

- Ready formal main conditions: `no_defense`, `safe_prompt`, `spotlighting`, `prompt_sandwich`, `m3_policy_only`, `m3_full`
- Blocked/pending formal main conditions: `promptguard`, `task_shield`, `ipiguard`, `progent`, `camel_or_fides`
- Diagnostic conditions excluded: `agentdojo_repeat_user_prompt`, `agentdojo_spotlighting_with_delimiting`

## Model gate

- Q2 model gate: `not_satisfied`
- Missing Q2 model slots: `{"frontier_api_vendor": 2, "open_source_7b_14b": 2}`

## Checks

| Check | Status | Severity | Detail |
|---|---|---|---|
| `benchmark_lock_artifacts_match` | `pass` | `error` | {"agentdojo_security": {"actual_sha256": "bf3434bd99dd681a87c49e9a00aa79747339d10ccd4efc54bffc277c2345c293", "exists": true, "expected_sha256": "bf3434bd99dd681a87c49e9a00aa79747339d10ccd4efc54bffc277c2345c293", "matc... |
| `agentdojo_full_case_universe_declared` | `pass` | `error` | {"security": 629, "total": 726, "utility": 97} |
| `injecagent_full_case_universe_declared` | `pass` | `error` | {"security": 1054, "total": 1054} |
| `no_favorable_case_filtering_declared` | `pass` | `error` | {"agentdojo_security_cases": 629, "agentdojo_utility_tasks": 97, "agentdojo_version": "v1", "gold_authorization_used_online": false, "injecagent_security_cases": 1054, "no_favorable_case_filtering": true} |
| `ready_job_matrix_uses_only_ready_formal_conditions` | `pass` | `error` | {"matrix_conditions": ["m3_full", "m3_policy_only", "no_defense", "prompt_sandwich", "safe_prompt", "spotlighting"], "ready": ["m3_full", "m3_policy_only", "no_defense", "prompt_sandwich", "safe_prompt", "spotlighting"]} |
| `blocked_strong_baselines_excluded_from_ready_job_matrix` | `pass` | `error` | {"blocked": ["camel_or_fides", "ipiguard", "progent", "promptguard", "task_shield"], "matrix_conditions": ["m3_full", "m3_policy_only", "no_defense", "prompt_sandwich", "safe_prompt", "spotlighting"]} |
| `diagnostic_conditions_excluded_from_ready_job_matrix` | `pass` | `error` | {"diagnostic": ["agentdojo_repeat_user_prompt", "agentdojo_spotlighting_with_delimiting"], "matrix_conditions": ["m3_full", "m3_policy_only", "no_defense", "prompt_sandwich", "safe_prompt", "spotlighting"]} |
| `q2_gate_not_satisfied_until_strong_baselines_ready` | `pass` | `warning` | {"blocked_agentdojo_official": ["agentdojo_tool_filter", "agentdojo_transformers_pi_detector"], "blocked_main": ["promptguard", "task_shield", "ipiguard", "progent", "camel_or_fides"], "q2_gate": "not_satisfied"} |
| `q2_model_gate_not_satisfied_until_7b14b_and_api_slots_ready` | `pass` | `warning` | {"frontier_api_vendor": 2, "open_source_7b_14b": 2} |

## Boundary

This file freezes the public-benchmark case universe and ready local execution matrix. It is not a result manifest. Q2-grade paper claims still require the declared formal jobs to be run, strong baselines to become source-backed/formal-ready, modern 7B-14B and API model slots to be configured, and complete logs plus statistical outputs to be generated from frozen manifests.
