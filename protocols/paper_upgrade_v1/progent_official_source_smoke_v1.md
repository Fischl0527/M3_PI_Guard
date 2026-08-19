# Progent official source smoke v1

Generated: 2026-07-22T08:05:54.546453+00:00

## Result

- Status: `completed_source_smoke_only`
- Source commit: `8a8eb894b9d568a32b4e58252fea85b47f789c77`
- Offline runtime smoke: `True`
- Network calls performed: `False`
- Formal result eligible: `False`

## Checks

| Check | Status | Severity | Detail |
|---|---|---|---|
| `checkout_exists` | `pass` | `error` | "external/baselines/progent" |
| `checkout_matches_expected_commit` | `pass` | `error` | {"actual": "8a8eb894b9d568a32b4e58252fea85b47f789c77", "expected": "8a8eb894b9d568a32b4e58252fea85b47f789c77"} |
| `registry_repository_matches_expected` | `pass` | `error` | {"kind": "repository", "relevant_path": "secagent/tool.py", "remote_head_observed_at": "2026-07-21", "remote_head_sha": "8a8eb894b9d568a32b4e58252fea85b47f789c77", "url": "https://github.com/sunblaze-ucb/progent"} |
| `required_source_paths_present` | `pass` | `error` | {"README.md": true, "agentdojo/README.md": true, "agentdojo/run.sh": true, "agentdojo/src/agentdojo/agent_pipeline/basic_elements.py": true, "agentdojo/src/agentdojo/agent_pipeline/tool_execution.py": true, "pyproject... |
| `offline_runtime_smoke_passed` | `pass` | `error` | {"allow_exact": "allow", "deny_bad_recipient": {"decision": "deny", "exception": "ValidationError"}, "deny_missing_tool": {"decision": "deny", "exception": "ValidationError"}, "expand_is_subset": false, "narrow_is_sub... |
| `top_level_license_present` | `fail` | `warning` | ["external/baselines/progent/LICENSE", "external/baselines/progent/LICENSE.txt", "external/baselines/progent/COPYING"] |
| `source_smoke_not_formal_effect_evidence` | `pass` | `warning` | false |

## Boundary

Official-source and offline deterministic-runtime qualification only. It does not validate policy-generation quality, execute AgentDojo, measure ASR or utility, or admit Progent into formal result tables.
