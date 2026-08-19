# CaMeL Source-Backed Compatibility Preflight v1

- Status: `completed_compat_preflight_only`
- Formal result admitted: `False`
- Result eligible for formal tables: `False`
- Checks: `8/8`
- Import rows SHA-256: `97cd9c39f9e3c98f3248fd42778c9e42bb6892c7cbd52aa492687b961e7c694c`
- Suite counts SHA-256: `e4c9be9e7744a569440eaa9277ce5921b420948a575d527a05b9f2f29e5f4764`

## Boundary

Compatibility import preflight only. The process-local preloader resolves the pinned AgentDojo suite import-order cycle without editing external source, but this manifest does not execute CaMeL on any benchmark case, call an LLM/API, start Ollama, or admit a formal result.

## Qualification blockers

- `camel_interpreter_benchmark_runner_not_implemented`
- `model_or_api_transport_for_privileged_llm_not_frozen`
- `label_capability_mapping_not_validated_on_public_benchmarks`
- `complete_formal_logs_absent`

## Required imports after compatibility preload

- `PASS` `agentdojo.default_suites.v1.banking.task_suite` — E:\M3_PI_Guard_runtime\camel\.venv\lib\site-packages\agentdojo\default_suites\v1\banking\task_suite.py
- `PASS` `agentdojo.default_suites.v1.travel.task_suite` — E:\M3_PI_Guard_runtime\camel\.venv\lib\site-packages\agentdojo\default_suites\v1\travel\task_suite.py
- `PASS` `agentdojo.default_suites.v1.workspace.task_suite` — E:\M3_PI_Guard_runtime\camel\.venv\lib\site-packages\agentdojo\default_suites\v1\workspace\task_suite.py
- `PASS` `agentdojo.default_suites.v1.slack.task_suite` — E:\M3_PI_Guard_runtime\camel\.venv\lib\site-packages\agentdojo\default_suites\v1\slack\task_suite.py
- `PASS` `agentdojo.task_suite.load_suites` — E:\M3_PI_Guard_runtime\camel\.venv\lib\site-packages\agentdojo\task_suite\load_suites.py
- `PASS` `camel.models` — E:\M3_PI_Guard_test\external\baselines\camel-prompt-injection\src\camel\models.py
- `PASS` `camel.pipeline_elements.privileged_llm` — E:\M3_PI_Guard_test\external\baselines\camel-prompt-injection\src\camel\pipeline_elements\privileged_llm.py
- `PASS` `camel.pipeline_elements.security_policies.agentdojo_security_policies` — E:\M3_PI_Guard_test\external\baselines\camel-prompt-injection\src\camel\pipeline_elements\security_policies\agentdojo_security_policies.py
- `PASS` `camel.pipeline_elements.security_policies.workspace` — E:\M3_PI_Guard_test\external\baselines\camel-prompt-injection\src\camel\pipeline_elements\security_policies\workspace.py
- `PASS` `camel.pipeline_elements.security_policies.travel` — E:\M3_PI_Guard_test\external\baselines\camel-prompt-injection\src\camel\pipeline_elements\security_policies\travel.py
- `PASS` `camel.pipeline_elements.security_policies.banking` — E:\M3_PI_Guard_test\external\baselines\camel-prompt-injection\src\camel\pipeline_elements\security_policies\banking.py
- `PASS` `camel.pipeline_elements.security_policies.slack` — E:\M3_PI_Guard_test\external\baselines\camel-prompt-injection\src\camel\pipeline_elements\security_policies\slack.py

## Next required work

- Freeze a source-backed CaMeL runner that calls the compatibility preloader before importing CaMeL pipeline modules.
- Freeze privileged/quarantined model transport and cost policy.
- Validate label/capability mapping on public benchmark online inputs.
- Run a two-case qualification before any full 726-case AgentDojo run.
