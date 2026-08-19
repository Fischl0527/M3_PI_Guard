# IPIGuard official source smoke v1

Generated: 2026-07-22T07:58:37.373686+00:00

## Result

- Status: `completed_source_smoke_only`
- Formal result eligible: `False`
- Checks passed: 8/8

## Source checkout

- Path: `external/baselines/ipiguard`
- Git HEAD: `4e686ed2f62c135cb12564a4466daa95f3ace878`
- Expected commit: `4e686ed2f62c135cb12564a4466daa95f3ace878`
- Matches expected: `True`

## Required source files

| Key | Exists | Lines | SHA-256 |
|---|---:|---:|---|
| `readme` | `True` | 132 | `182c7cdf050903a5bf667ff1431a2f4d814d365cbccb5f745c79c8c02329a614` |
| `eval_shell` | `True` | 20 | `02ba807b2e91d60353b98bdc3067f26459ba2fa07f446c2dd8dcaddb0d4afadc` |
| `run_eval` | `True` | 258 | `a01dfb86d33bccb45b4ef68d38e77614235cb82727a415f8550c1bc8c87b9dfc` |
| `run_data_module` | `True` | 27 | `886f625bf79ca99b2065fc13f565d750c552811151bd96d9addde1238ab62992` |
| `agent_pipeline` | `True` | 256 | `de794ed8bcf5e7ef18897ac3564257153c0a70a0858e1e3fbe779b8ad8dfdbd5` |
| `tool_execution` | `True` | 398 | `03be3212a6492b0a5015feb0000102824bfbb5ffdf1f960f4d5290273a6b42eb` |
| `ipiguard_llm` | `True` | 554 | `5bed3e68ae31dff804674edbc96a1b61fd74fdc0533083561cff78bcdbb88a5a` |
| `tool_whitelist` | `True` | 52 | `c21f39a9bce9719cdc2c3714507c9aa21f7f9999ada802f55e2fa5133d540297` |

## Marker groups

| Group | Source file | Passed | Missing markers |
|---|---|---:|---|
| `evaluation_entrypoint` | `run_eval` | `True` | - |
| `ipiguard_pipeline_wiring` | `agent_pipeline` | `True` | - |
| `dag_construction` | `ipiguard_llm` | `True` | - |
| `dag_traversal_and_repair` | `ipiguard_llm` | `True` | - |
| `dag_execution_loop` | `tool_execution` | `True` | - |
| `whitelist_command_split` | `tool_execution` | `True` | - |

## Dataset universe parsed from official script

- Parsed: `True`
- User task counts: `{'banking': 16, 'workspace': 40, 'slack': 21, 'travel': 20}`
- Injection task counts: `{'banking': 9, 'workspace': 6, 'slack': 5, 'travel': 7}`
- Total benign user tasks: `97`
- Total attack pairs: `629`

## Checks

| Check | Status | Severity |
|---|---|---|
| `preflight_manifest_present` | `pass` | `error` |
| `preflight_source_ready` | `pass` | `error` |
| `source_checkout_matches_expected_commit` | `pass` | `error` |
| `required_source_files_present` | `pass` | `error` |
| `required_source_files_syntax_compile` | `pass` | `error` |
| `official_source_marker_groups_present` | `pass` | `error` |
| `dataset_universe_counts_match_expected_public_script` | `pass` | `error` |
| `formal_result_eligibility_remains_false` | `pass` | `error` |

## Boundary

Source smoke only. It verifies pinned IPIGuard code structure and official TDG wiring markers without importing dependencies, calling APIs, executing models or scoring any benchmark case. Formal result eligibility remains false until an accepted source-backed adapter runs complete cells with raw logs and materializer admission.
