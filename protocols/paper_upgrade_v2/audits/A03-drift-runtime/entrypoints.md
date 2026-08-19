# A03-drift-runtime entrypoints

- Artifact: DRIFT
- Component: planner, dynamic validator, and injection isolator
- Commit: `6fd3df4763fad77398c3c273c2a4fe14dd50f7ea`

## Online boundaries

- `external/paper_v2_audits/drift/DRIFTLLM.py:579` — `DRIFTLLM.query`; parameters: `self, query, runtime, env, messages, extra_args`
- `external/paper_v2_audits/drift/DRIFTLLM.py:440` — `DRIFTLLM.trajectory_constraint_validation`; parameters: `self, to_call_function, output, query, messages`
- `external/paper_v2_audits/drift/DRIFTLLM.py:525` — `DRIFTLLM.checklist_constraint_validation`; parameters: `self, json_tool_calls, output, query, messages`

## Offline/evaluator boundaries

- `external/paper_v2_audits/drift/DRIFTTaskSuite.py:129` — `DRIFTTaskSuite.run_task_with_pipeline`

## Scope note

The DRIFT guard receives the original query, tool definitions, trajectory/checklist state and tool messages; the task suite computes utility/security after the pipeline returns.
