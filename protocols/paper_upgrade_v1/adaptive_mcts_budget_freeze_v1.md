# Adaptive MCTS budget freeze v1

- Status: `completed_frozen_protocol`
- Selected attack tasks: 80
- Query budgets: 100, 500, 2000
- Result eligible: `False`

## Distribution

| Field | Counts |
|---|---|
| `split` | development: 50, validation: 30 |
| `attack_family` | cross_tool_attack_chain: 9, direct_jailbreak: 9, environment_context_pollution: 9, json_rpc: 9, memory_poisoning: 9, multilingual_t2l: 9, obfuscation_evasion: 9, rag_indirect: 9, tool_output_injection: 8 |
| `language` | cross_lingual: 14, en: 13, pinyin: 14, zh: 13, zh_en: 13, zh_hant: 13 |
| `authorization_profile` | ambiguous_recipient: 13, auto_compiled_exact: 13, dynamic_parameter: 13, legal_cross_tool_chain: 14, partial_resource_scope: 14, trusted_context_exact: 13 |
| `attack_budget_group` | 100: 27, 2000: 26, 500: 27 |

## Boundary

This artifact freezes an 80-task adaptive attack panel only. It does not run the MCTS search, does not start models or services, and is not formal adaptive robustness evidence until a separate run manifest reports completed_formal with complete query logs and figures.
