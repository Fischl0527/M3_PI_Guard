# Task Shield disclosed paper-reproduction freeze v1.5

- Status: `completed_frozen_formal_protocol`
- Checks: `19/19`
- Frozen benchmark cases: `726`
- Expanded qualification cases: `12`
- Runtime patch: `m3-taskshield-paper-runtime-1.5-contract-recovery`
- Full 726-case run authorized: `False`
- Result eligible for formal tables: `False`
- Q2 score change: `0`

## v1.5 change

The sealed v1.4 root retained two invalid-JSON failures during assistant content instruction extraction and did not retain their raw verifier output. v1.5 prospectively logs raw output before parsing, adds bounded contract recovery, and suppresses exhausted untrusted content fail-closed.

## Expanded qualification

- `agentdojo:v1:banking:user_task_0`
- `agentdojo:v1:banking:user_task_0:injection_task_0`
- `agentdojo:v1:banking:user_task_1`
- `agentdojo:v1:banking:user_task_1:injection_task_0`
- `agentdojo:v1:banking:user_task_6`
- `agentdojo:v1:banking:user_task_6:injection_task_0`
- `agentdojo:v1:slack:user_task_18`
- `agentdojo:v1:slack:user_task_18:injection_task_1`
- `agentdojo:v1:workspace:user_task_0`
- `agentdojo:v1:workspace:user_task_0:injection_task_0`
- `agentdojo:v1:travel:user_task_0`
- `agentdojo:v1:travel:user_task_0:injection_task_0`

## Evidence boundary

Post-hoc failure-recovery protocol freeze only. v1.5 supersedes v1.4 for future qualification without modifying or retrying v1.4 evidence. This freeze authorizes only the exact fresh 12-case operational qualification, never a 726-case formal run, formal admission, failed-row exclusion or Q2 score increase.
