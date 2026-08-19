# A12-injecagent-loader entrypoints

- Artifact: InjecAgent
- Component: benchmark loader and online prompt construction
- Commit: `f19c9f2c79a41046eb13c03c51a24c567a8ffa07`

## Online boundaries

- `external/benchmarks/injecagent/src/evaluate_prompted_agent.py:12` — `predict_one_case`; parameters: `system_prompt, user_prompt, params, item, model_class, tool_dict, step_2`

## Offline/evaluator boundaries

- None identified for this audit unit.

## Scope note

The prompted agent receives the user instruction, all available tool descriptions and a scratchpad built from tool observations.
