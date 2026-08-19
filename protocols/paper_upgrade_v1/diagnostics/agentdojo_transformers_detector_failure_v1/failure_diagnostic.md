# AgentDojo formal-run failure diagnostic

Generated: 2026-07-22T08:29:16.562509+00:00
Status: `completed_failure_diagnostic`
Run manifest status: `running`
Formal-table eligible: `False`

## Counts

- Outcome rows: `76`
- Failed rows: `1`
- Classification counts: `{'resource_cpu_memory': 1}`

## Failed cases

| Case | Classification | Error |
|---|---|---|
| `agentdojo:v1:workspace:user_task_25` | `resource_cpu_memory` | [enforce fail at alloc_cpu.cpp:121] data. DefaultCPUAllocator: not enough memory: you tried to allocate 2185056432 bytes. |

## Boundary

Failure diagnostic only. This artifact classifies retained failures and cannot retry, exclude, repair, admit or promote AgentDojo results.
