# Task Shield correctness-first freeze v1.6

- Status: `completed_frozen_formal_protocol`
- Checks: `21/21`
- P3 preflight: `4` cases (2 utility + 2 attack)
- P4 expanded qualification: `12` cases (6 + 6)
- Runtime: `m3-taskshield-paper-runtime-1.6-correctness`
- SDK retries: `0`
- Logical attempts: `2`
- Request/case timeout: `120/600 seconds`
- Full 726-case run authorized: `False`
- Result eligible for formal tables: `False`
- Q2 score change: `0`

## P3 selection

- `agentdojo:v1:banking:user_task_0`
- `agentdojo:v1:banking:user_task_0:injection_task_0`
- `agentdojo:v1:banking:user_task_1`
- `agentdojo:v1:banking:user_task_1:injection_task_0`

## P4 selection

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

Prospective v1.6 P3/P4 qualification freeze. It supersedes no sealed evidence, authorizes only the exact 4-case preflight and 12-case expanded selections, and cannot authorize P5, P6, formal admission, failed-row retry, exclusion, or Q2 promotion.
