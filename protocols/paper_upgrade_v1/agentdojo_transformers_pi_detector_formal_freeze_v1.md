# AgentDojo official transformers_pi_detector formal freeze v1

- Status: `completed_frozen_formal_protocol`
- Condition: `agentdojo_transformers_pi_detector_official`
- Model: `m3-paper-qwen3-8b-v1:latest`
- Cases: 726 (97 utility + 629 security)
- Attack: `direct`
- Detector revision: `90c9989b1a342275dd0d1a95aad283c04e075671`
- AgentDojo commit: `089ed468cf3ed0322acc66b0211f26d9d90dbf60`
- Checks: 8/8
- Result eligible: `False` until the complete execution manifest is admitted.

## Fixed execution policy

- Official AgentDojo `AgentPipeline.from_config` is used with `OPENAI_COMPATIBLE` transport.
- The defense is the upstream `transformers_pi_detector` implementation; no M3 detector adapter is substituted.
- Temperature is 0, repeat count is 1, tool output format is YAML, and the direct attack is fixed.
- All 726 cases must produce a case manifest; failures remain in the original denominator.
- A partial run, case-limited run, smoke, or transport probe cannot enter formal tables.

## Evidence boundary

This freeze declares one official AgentDojo transformers_pi_detector condition over the frozen 726-case AgentDojo v1 universe. It is not a result. Partial runs and qualification cases are diagnostic only.
