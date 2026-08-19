# A08-progent-runtime entrypoints

- Artifact: Progent
- Component: policy generator and deterministic privilege enforcement
- Commit: `8a8eb894b9d568a32b4e58252fea85b47f789c77`

## Online boundaries

- `external/baselines/progent/secagent/tool.py:375` — `generate_security_policy`; parameters: `query, manual_check`
- `external/baselines/progent/secagent/tool.py:435` — `generate_update_security_policy`; parameters: `tool_call_param, tool_call_result, manual_check`
- `external/baselines/progent/secagent/tool.py:573` — `check_tool_call`; parameters: `tool_name, kwargs`

## Offline/evaluator boundaries

- None identified for this audit unit.

## Scope note

Policy generation consumes user query/tool schemas; updates may consume tool outputs, and enforcement consumes tool name/kwargs.
