# Strong-baseline dependency snapshot v1

Generated: 2026-07-22T09:39:14.121701+00:00

## Result

- Status: `completed`
- Q2 strong-baseline gate: `not_satisfied`
- Result eligible for formal tables: `False`

## Readiness by registry key

| Registry key | Snapshot ready | Blockers |
|---|---:|---|
| `camel_or_fides` | `True` | none |
| `ipiguard` | `True` | none |
| `progent` | `True` | none |
| `promptguard` | `True` | none |
| `task_shield` | `True` | none |

## Source checkouts

| Entry | Status | Expected HEAD | Local HEAD |
|---|---|---|---|
| `promptguard_llama_prompt_guard_2` | `source_checkout_matched` | `b71c6350a2acf2fb62c2328a734cbf440ecac386` | `b71c6350a2acf2fb62c2328a734cbf440ecac386` |
| `task_shield_acl2025` | `paper_or_model_card_only_no_checkout_expected` | `` | `` |
| `ipiguard_github_emnlp2025` | `source_checkout_matched` | `4e686ed2f62c135cb12564a4466daa95f3ace878` | `4e686ed2f62c135cb12564a4466daa95f3ace878` |
| `progent_arxiv2025` | `source_checkout_matched` | `8a8eb894b9d568a32b4e58252fea85b47f789c77` | `8a8eb894b9d568a32b4e58252fea85b47f789c77` |
| `camel_google_research` | `source_checkout_matched` | `f083b6b396399d3b3c7f2ddaf613a5945eaf32d8` | `f083b6b396399d3b3c7f2ddaf613a5945eaf32d8` |
| `fides_microsoft` | `source_checkout_matched` | `669c046c4adbc56ee49c9672fdd30c54937ea062` | `669c046c4adbc56ee49c9672fdd30c54937ea062` |

## Checks

| Check | Status | Severity | Detail |
|---|---|---|---|
| `external_registry_loaded` | `pass` | `error` | {"entries": 6, "path": "protocols/paper_upgrade_v1/external_strong_baselines_v1.json"} |
| `all_required_keys_have_entries` | `pass` | `error` | {"missing": [], "present": ["camel_or_fides", "ipiguard", "progent", "promptguard", "task_shield"]} |
| `repository_entries_record_expected_remote_heads` | `pass` | `error` | {"camel_google_research": "f083b6b396399d3b3c7f2ddaf613a5945eaf32d8", "fides_microsoft": "669c046c4adbc56ee49c9672fdd30c54937ea062", "ipiguard_github_emnlp2025": "4e686ed2f62c135cb12564a4466daa95f3ace878", "progent_ar... |
| `ready_keys_have_no_unresolved_blockers` | `pass` | `warning` | {"camel_or_fides": [], "ipiguard": [], "progent": [], "promptguard": [], "task_shield": []} |
| `snapshot_not_result_eligible` | `pass` | `warning` | false |

## Boundary

Dependency/source snapshot only. It records local environment and source-checkout state for required strong baselines, but it does not run baselines or create formal effect evidence.
