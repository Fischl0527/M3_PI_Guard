# A04-agentdojo-case-loader entrypoints

- Artifact: AgentDojo
- Component: task and injection case loader
- Commit: `089ed468cf3ed0322acc66b0211f26d9d90dbf60`

## Online boundaries

- `external/benchmarks/agentdojo/src/agentdojo/agent_pipeline/agent_pipeline.py:182` — `AgentPipeline.query`; parameters: `self, query, runtime, env, messages, extra_args`

## Offline/evaluator boundaries

- `external/benchmarks/agentdojo/src/agentdojo/task_suite/task_suite.py:339` — `TaskSuite.run_task_with_pipeline`

## Scope note

TaskSuite owns task objects and evaluators, while AgentPipeline.query receives a prompt/runtime/environment projection.
