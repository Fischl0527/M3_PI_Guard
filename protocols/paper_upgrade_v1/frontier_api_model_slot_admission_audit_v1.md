# Frontier API model-slot admission audit v1

Generated: 2026-07-22T08:51:01.055651+00:00

## Result

- Status: `blocked_missing_or_unsafe_local_config`
- Configured vendors: 0
- Registered frontier API slots: 0
- Explicit network smoke consent: `False`
- Network calls performed: `False`
- Result eligible for formal tables: `False`

## Provider readiness

| Provider | Key | Model | Status | Missing fields |
|---|---|---|---|---|
| `openai` | `missing_or_placeholder` | `` | `blocked_missing_local_config` | OPENAI_API_KEY, FRONTIER_OPENAI_MODEL_ID |
| `anthropic` | `missing_or_placeholder` | `` | `blocked_missing_local_config` | ANTHROPIC_API_KEY, FRONTIER_ANTHROPIC_MODEL_ID |

## Checks

| Check | Status | Severity | Detail |
|---|---|---|---|
| `local_config_exists` | `pass` | `error` | "config/project.local.env" |
| `local_config_ignored_and_untracked` | `pass` | `error` | {"ignored": true, "inside_repository": true, "tracked": false} |
| `tracked_files_do_not_contain_configured_secrets` | `pass` | `error` | [] |
| `two_distinct_vendors_configured_for_network_smoke` | `fail` | `error` | [] |
| `explicit_network_smoke_consent_recorded` | `fail` | `warning` | {"current_status": "missing_or_placeholder", "expected_value": "yes_for_network_smoke", "field": "M3_FRONTIER_API_CONSENT"} |
| `model_registry_has_two_frontier_api_vendor_slots` | `fail` | `error` | {"registered_vendor_ids": [], "selection_reason": "base_registry_no_admitted_frontier_candidate"} |
| `redacted_transport_and_plan_only_smoke_are_safe` | `pass` | `warning` | {"formal_result_eligible": false, "frontier_client_present": true, "network_call_count": 0, "network_calls_performed": false, "smoke_manifest": "outputs/paper_upgrade_v1/frontier_api_smoke_v1/manifest.json", "smoke_st... |

## Boundary

This is a local configuration admission audit only. It never calls frontier APIs and never prints credentials. API providers can be registered as paper model slots only after explicit consent, network smoke, exact model identifiers, cost/log disclosure and frozen formal run manifests exist.
