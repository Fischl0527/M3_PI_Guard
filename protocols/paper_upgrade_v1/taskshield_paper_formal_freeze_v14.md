# Task Shield disclosed paper-reproduction freeze v1.4

- Status: `completed_frozen_formal_protocol`
- Checks: 16/16
- Cases: 726 (97 utility + 629 security)
- Model: `m3-paper-qwen3-8b-v1:latest`
- Runtime patch: `m3-taskshield-paper-runtime-1.4-timeout-retry`
- Timeout retry attempts: `2`
- Timeout retry backoff seconds: `1.0`
- Result eligible: `False` until fresh full-root formal admission.

## v1.4 change

v1.3 failed on agentdojo:v1:slack:user_task_18 with APITimeoutError during verifier instruction extraction; v1.4 freezes a bounded, trace-logged transport timeout retry while preserving full-root execution and zero-failure formal admission requirements.

The retry scope is verifier-model transport timeout only. Case-level retry, selective failed-row retry and failed-row exclusion remain forbidden.

## Evidence boundary

Protocol freeze only. This is a disclosed Task Shield paper reproduction, not official Task Shield source. v1.4 is a future full-root failure-recovery protocol after a v1.3 APITimeoutError; it does not repair, retry or exclude the v1.3 failed row and cannot enter tables before fresh qualification or full 726-case execution, complete traces, analysis and explicit admission.
