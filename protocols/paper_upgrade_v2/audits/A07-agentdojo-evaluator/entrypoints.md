# A07-agentdojo-evaluator entrypoints

- Artifact: AgentDojo
- Component: utility and security evaluators
- Commit: `089ed468cf3ed0322acc66b0211f26d9d90dbf60`

## Online boundaries

- None identified for this audit unit.

## Offline/evaluator boundaries

- `external/benchmarks/agentdojo/src/agentdojo/task_suite/task_suite.py:281` — `TaskSuite._check_user_task_utility`
- `external/benchmarks/agentdojo/src/agentdojo/task_suite/task_suite.py:297` — `TaskSuite._check_injection_task_security`

## Scope note

These functions evaluate completed traces/environments and are not inserted as guard inputs.
