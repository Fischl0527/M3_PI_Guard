# A01-vigil-runtime entrypoints

- Artifact: VIGIL
- Component: verify-before-commit runtime guard
- Commit: `af8eb9c70d32f8a3cc07b308e823c813b2285772`

## Online boundaries

- `external/paper_v2_audits/vigil/vigil/constraint_generator.py:230` — `ConstraintGenerator.generate_constraints`; parameters: `self, user_query, abstract_sketch`
- `external/paper_v2_audits/vigil/vigil/runtime_auditor.py:35` — `RuntimeAuditor.audit_tool_call`; parameters: `self, tool_call_info`
- `external/paper_v2_audits/vigil/vigil/vigil_executor.py:35` — `VIGILToolsExecutor.query`; parameters: `self, query, runtime, env, messages, extra_args`

## Offline/evaluator boundaries

- None identified for this audit unit.

## Scope note

The traced path compiles constraints from the user query and audits proposed tool name/arguments before runtime execution.
