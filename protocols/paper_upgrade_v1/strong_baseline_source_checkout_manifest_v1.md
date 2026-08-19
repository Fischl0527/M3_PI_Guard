# Strong-baseline source checkout manifest v1

Generated: 2026-07-22T07:45:19.996789+00:00

## Result

- Status: `completed`
- Execute mode: `False`
- Checkout root: `external/baselines`
- Source-ready entries: `['camel_google_research', 'fides_microsoft', 'ipiguard_github_emnlp2025', 'progent_arxiv2025', 'promptguard_llama_prompt_guard_2']`
- Result eligible for formal tables: `False`

## Entries

| Entry | Action/status | Expected HEAD | Local HEAD | Ready | Size MiB |
|---|---|---|---|---:|---:|
| `promptguard_llama_prompt_guard_2` | `source_checkout_ready` | `b71c6350a2acf2fb62c2328a734cbf440ecac386` | `b71c6350a2acf2fb62c2328a734cbf440ecac386` | `True` | 142.72 |
| `task_shield_acl2025` | `skip_not_repository_entry` | `` | `` | `False` | 0.0 |
| `ipiguard_github_emnlp2025` | `source_checkout_ready` | `4e686ed2f62c135cb12564a4466daa95f3ace878` | `4e686ed2f62c135cb12564a4466daa95f3ace878` | `True` | 7.0 |
| `progent_arxiv2025` | `source_checkout_ready` | `8a8eb894b9d568a32b4e58252fea85b47f789c77` | `8a8eb894b9d568a32b4e58252fea85b47f789c77` | `True` | 87.84 |
| `camel_google_research` | `source_checkout_ready` | `f083b6b396399d3b3c7f2ddaf613a5945eaf32d8` | `f083b6b396399d3b3c7f2ddaf613a5945eaf32d8` | `True` | 3.65 |
| `fides_microsoft` | `source_checkout_ready` | `669c046c4adbc56ee49c9672fdd30c54937ea062` | `669c046c4adbc56ee49c9672fdd30c54937ea062` | `True` | 1.29 |

## Checks

| Check | Status | Severity | Detail |
|---|---|---|---|
| `external_registry_loaded` | `pass` | `error` | {"path": "protocols/paper_upgrade_v1/external_strong_baselines_v1.json", "selected_entries": 6} |
| `requested_entries_exist` | `pass` | `error` | {"missing": []} |
| `repository_entries_have_expected_heads` | `pass` | `error` | {"camel_google_research": "f083b6b396399d3b3c7f2ddaf613a5945eaf32d8", "fides_microsoft": "669c046c4adbc56ee49c9672fdd30c54937ea062", "ipiguard_github_emnlp2025": "4e686ed2f62c135cb12564a4466daa95f3ace878", "progent_ar... |
| `executed_checkouts_have_matching_heads` | `pass` | `error` | {"failed_or_not_ready": []} |
| `source_checkout_manifest_not_result_eligible` | `pass` | `warning` | false |

## Boundary

Source checkout preparation only. It may clone or fetch Git source repositories when execute=true, but it does not install packages, download model weights, start model services, call APIs, run baselines or create formal effect evidence.
