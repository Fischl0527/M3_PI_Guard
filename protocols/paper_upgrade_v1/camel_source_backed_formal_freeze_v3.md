# CaMeL source-backed formal freeze v3

- Status: `completed_frozen_formal_protocol`
- Condition: `camel_or_fides`
- Selected method: `camel_google_research`
- Model slot: `m3-paper-qwen3-8b-v1:latest`
- Common cases: `726` (`97` utility + `629` security)
- CaMeL commit: `f083b6b396399d3b3c7f2ddaf613a5945eaf32d8`
- AgentDojo commit: `089ed468cf3ed0322acc66b0211f26d9d90dbf60`
- Metric semantics: `agentdojo_official_v2`
- v3 correction: UTF-8 stdio guard for upstream CaMeL debug prints; operational failures remain unresolved.
- Source-smoke: `completed_source_smoke_only` (8/8)
- Import preflight: `completed_dependency_import_preflight_blocked`
- Compatibility preflight: `completed_compat_preflight_only`
- Runner-wiring preflight: `completed_runner_wiring_preflight_only`
- Transport/mapping preflight: `completed_transport_and_mapping_preflight_only`
- Checks: 17/17
- Result eligible: `False` until the benchmark real-model qualification, complete logs and formal admission exist.

## Frozen source and assumptions

- Official CaMeL source files are hash-pinned in the JSON manifest.
- The common AgentDojo v1 universe is fixed to 97 utility and 629 security cases.
- The upstream README/pyproject requirement for `uv`, `.env` and provider/API configuration is recorded; the isolated uv runtime and loopback OpenAI-compatible transports are referenced but this freeze still does not execute benchmark cases.
- The source-backed runner and analyzer are implemented separately; this freeze is the immutable protocol input for qualification and full runs, not a result artifact.

## Qualification blockers

- `real_model_two_case_qualification_not_completed`
- `formal_runner_execution_not_started`
- `complete_formal_logs_absent`

## Evidence boundary

Frozen adapter protocol only. This manifest records the pinned CaMeL source, source-smoke and common AgentDojo universe, but it does not install dependencies, invoke a model/API, run cases, measure ASR/utility, or admit CaMeL into formal result tables.
