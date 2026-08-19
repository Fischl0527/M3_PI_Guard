# A13-injecagent-evaluator entrypoints

- Artifact: InjecAgent
- Component: attack and utility evaluator
- Commit: `f19c9f2c79a41046eb13c03c51a24c567a8ffa07`

## Online boundaries

- None identified for this audit unit.

## Offline/evaluator boundaries

- `external/benchmarks/injecagent/src/output_parsing.py:58` — `evaluate_output_prompted`
- `external/benchmarks/injecagent/src/output_parsing.py:189` — `evaluate_output_finetuned`

## Scope note

The evaluator explicitly receives target_tool and attacker metadata after the model output is produced.
