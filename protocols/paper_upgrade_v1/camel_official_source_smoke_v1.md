# CaMeL official source smoke v1

Generated: 2026-07-22T08:12:08.589110+00:00

## Result

- Status: `completed_source_smoke_only`
- Source commit: `f083b6b396399d3b3c7f2ddaf613a5945eaf32d8`
- Offline policy smoke: `True`
- Network calls performed: `False`
- Formal result eligible: `False`

## Checks

| Check | Status | Severity | Detail |
|---|---|---|---|
| `checkout_exists` | `pass` | `error` | "external/baselines/camel-prompt-injection" |
| `checkout_matches_expected_commit` | `pass` | `error` | {"actual": "f083b6b396399d3b3c7f2ddaf613a5945eaf32d8", "expected": "f083b6b396399d3b3c7f2ddaf613a5945eaf32d8"} |
| `registry_repository_matches_expected` | `pass` | `error` | {"kind": "repository", "remote_head_observed_at": "2026-07-18", "remote_head_sha": "f083b6b396399d3b3c7f2ddaf613a5945eaf32d8", "url": "https://github.com/google-research/camel-prompt-injection"} |
| `preflight_selects_camel_source` | `pass` | `error` | {"selected_candidate": "camel", "source_checkout_ready": true, "status": "selected_source_ready_dependency_blocked_stub_preflight_only"} |
| `required_source_paths_present` | `pass` | `error` | {"LICENSE": true, "README.md": true, "pyproject.toml": true, "src/camel/__init__.py": true, "src/camel/capabilities/capabilities.py": true, "src/camel/capabilities/readers.py": true, "src/camel/capabilities/sources.py... |
| `official_source_marker_groups_present` | `pass` | `error` | {"capability_metadata": {"markers": ["class Capabilities", "sources_set", "readers_set"], "missing_markers": [], "passed": true}, "security_policy_engine": {"markers": ["class SecurityPolicyEngine", "def base_security... |
| `offline_policy_smoke_passed` | `pass` | `error` | {"base_policy_allows_private_no_side_effect": "Allowed", "base_policy_denies_private_side_effect": "Denied", "network_guard_active": true, "slack_allows_channel_members": "Allowed", "slack_allows_trusted_direct_recipi... |
| `source_smoke_not_formal_effect_evidence` | `pass` | `warning` | false |

## Boundary

Official-source and offline deterministic policy qualification only. It uses import isolation only for AgentDojo environment type names. It does not validate CaMeL interpreter generation, execute AgentDojo cases, measure ASR or utility, or admit CaMeL into formal tables.
