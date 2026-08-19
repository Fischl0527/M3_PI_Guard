# A22-task-shield-runtime entrypoints

- Artifact: Task Shield
- Component: paper-disclosed task alignment and local reproduction boundary
- Commit: `d74cef2739551591a49c722c5c6273bac6edf91e`

## Online boundaries

- `experiments/paper_v1/benchmarks/taskshield_paper_runtime.py:205` — `TaskShieldPaperVerifier.initialize`; parameters: `self, query`
- `experiments/paper_v1/benchmarks/taskshield_paper_runtime.py:257` — `TaskShieldPaperVerifier.check_tool_call`; parameters: `self, call_id, tool, arguments, history`
- `experiments/paper_v1/benchmarks/taskshield_paper_runtime.py:287` — `TaskShieldPaperVerifier.check_content`; parameters: `self, content, source, history`

## Offline/evaluator boundaries

- None identified for this audit unit.

## Scope note

ACL Anthology and the paper contain no official code link. The inspected Python is this project's explicitly disclosed paper reproduction, hash-bound separately from the official PDF; it is not represented as author code.
