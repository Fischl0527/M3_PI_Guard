# A05-agentdojo-tool-filter entrypoints

- Artifact: AgentDojo
- Component: ToolFilter defense
- Commit: `089ed468cf3ed0322acc66b0211f26d9d90dbf60`

## Online boundaries

- `external/benchmarks/agentdojo/src/agentdojo/agent_pipeline/llms/openai_llm.py:213` — `OpenAILLMToolFilter.query`; parameters: `self, query, runtime, env, messages, extra_args`

## Offline/evaluator boundaries

- None identified for this audit unit.

## Scope note

ToolFilter asks a model to select from runtime tools using the current conversation and a fixed filtering prompt.
