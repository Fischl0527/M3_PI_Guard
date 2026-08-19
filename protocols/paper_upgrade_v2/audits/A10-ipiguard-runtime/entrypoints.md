# A10-ipiguard-runtime entrypoints

- Artifact: IPIGuard
- Component: tool dependency graph planner and executor
- Commit: `4e686ed2f62c135cb12564a4466daa95f3ace878`

## Online boundaries

- `external/baselines/ipiguard/agentdojo/src/agentdojo/agent_pipeline/llms/ipiguard_llm.py:212` — `OpenAIConstructLLM.query`; parameters: `self, query, runtime, env, messages, extra_args`
- `external/baselines/ipiguard/agentdojo/src/agentdojo/agent_pipeline/llms/ipiguard_llm.py:445` — `OpenAITraverseLLM.query_args_update`; parameters: `self, query, runtime, env, messages, extra_args`
- `external/baselines/ipiguard/agentdojo/src/agentdojo/agent_pipeline/llms/ipiguard_llm.py:490` — `OpenAITraverseLLM.query_node_expansion`; parameters: `self, query, runtime, env, messages, extra_args`

## Offline/evaluator boundaries

- `external/baselines/ipiguard/run/eval.py:63` — `AgentTask.run`

## Scope note

The DAG constructor receives user query and runtime tool documentation; benchmark task objects remain in run/eval.py.
