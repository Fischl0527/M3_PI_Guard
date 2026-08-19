# Progent source-backed formal freeze v1

- Status: `completed_frozen_formal_protocol`
- Condition: `progent_source_backed`
- Model: `m3-paper-qwen3-8b-v1:latest`
- Common cases: `726` (`97` utility + `629` security)
- Progent commit: `8a8eb894b9d568a32b4e58252fea85b47f789c77`
- AgentDojo commit: `089ed468cf3ed0322acc66b0211f26d9d90dbf60`
- Checks: 13/13
- Result eligible: `False` until complete execution and formal admission.

## Compatibility finding

- The official Progent checkout bundles only `686` v1 cases: `97` utility + `589` security.
- It is missing exactly `40` common cases, all travel injection tasks 2 and 6.
- Therefore the formal comparison uses the pinned official Progent policy engine on the project's common 726-case AgentDojo checkout through a source-hashed lifecycle/transport port.

## Frozen semantics

- Initial policy and policy updates use the official Progent prompts and JSON-schema enforcement.
- Upstream run.sh behavior is retained: automatic updates are enabled, update errors are ignored, and automatic policy expansion is allowed.
- Agent and policy generation both use the same frozen local Qwen3 8B alias; this is a disclosed compatibility evaluation, not reproduction of the paper's GPT-4o numbers.
- The Slack injection-task-5 trace-checker issue is pre-registered: raw official and execution-grounded corrected metrics must both be reported.

## Evidence boundary

Frozen protocol only. This is not the upstream Progent CLI byte-for-byte: the official policy engine is ported to the common newer AgentDojo checkout and both agent and policy generation use the frozen local Qwen model through Ollama. The official checkout's 686-case universe and exact 40-case gap are retained in this manifest. No result is formal before full 726-case execution, raw traces, failure audit and explicit admission.
