# InjecAgent official compatibility audit v1

Generated: 2026-07-22T08:23:48.988430+00:00

## Result

- Status: `completed`
- Passed checks: 19/19
- Evidence boundary: `compatibility_audit_not_official_benchmark_result`
- Formal result eligible: `False`

## What is aligned

- official InjecAgent prompt templates are loaded from the pinned checkout
- official post-user-tool scratchpad stage is rendered before model scoring
- available tool names preserve official source-case order
- official prompted parser is directly imported for fixed ReAct cross-checks
- InjecAgent DH/DS S1/S2 ASR aggregation formulas are cross-checked on synthetic rows

## What is not byte-identical

- model transport uses M3 local/API client wrappers instead of InjecAgent's model classes
- m3_full inserts a runtime monitor between model output and simulated tool execution
- tool observations after model-chosen attacker actions use cached or deterministic local replay
- M3 logs additional guard/provenance fields not present in official InjecAgent result files
- function-calling InjecAgent runner compatibility is not implemented in this audit

## Official source hashes

| Component | Relative path | SHA-256 |
|---|---|---|
| prompted_runner | `src/evaluate_prompted_agent.py` | `cd088c4672bcf7e82912c12c48bd5e5fc086f4decb4c086ff9c390f86990114b` |
| prompt_parser | `src/output_parsing.py` | `ffbc9e8286d8bc19c53a3e4ee8ee37ae01707ae3b4f5de74f104bcbd9eb63ddd` |
| scorer_utils | `src/utils.py` | `3d043df620312d0d5e4ee8e8532fc1c6e776a2b444a7a4b33ffafc7153980292` |
| params | `src/params.py` | `309d486539cc1c84ef084e042baba386c488d1ce3d92ebfb656bd1bacae5c103` |
| prompt_templates | `src/prompts/agent_prompts.py` | `4eccf23c59170fd3349b07fe2f1f40b7b9326557e000eee51fc0c0b60bddba6b` |
| readme | `README.md` | `48fefba69837d571825823938b599d59d2656379b4ef386152cf5ceda5e4ac18` |

## Checks

| Check | Status | Detail |
|---|---|---|
| `all_official_files_exist` | `pass` | {'prompted_runner': True, 'prompt_parser': True, 'scorer_utils': True, 'params': True, 'prompt_templates': True, 'readme': True} |
| `official_marker_post_user_tool_available_tools` | `pass` | available_tool_names = [item['User Tool']] + item['Attacker Tools'] |
| `official_marker_prelude_user_tool_action` | `pass` | Action: {item['User Tool']} |
| `official_marker_prelude_user_tool_observation` | `pass` | Observation: {item['Tool Response']} |
| `official_marker_stage1_attacker_target` | `pass` | evaluate_output_prompted(item['output'], item['Attacker Tools'][0] |
| `official_marker_stage2_attacker_target` | `pass` | evaluate_output_prompted(output, item['Attacker Tools'][1] |
| `official_marker_official_prompt_type_injecagent` | `pass` | --prompt_type InjecAgent |
| `official_marker_official_prompt_type_react` | `pass` | hwchase17_react |
| `parser_crosscheck_succ_action_json` | `pass` | {'official_eval': 'succ', 'official_invalid_reason': '', 'm3_parse_ok': True, 'm3_tool': 'GmailSendEmail', 'm3_parse_error': ''} |
| `parser_crosscheck_succ_action_none_input` | `pass` | {'official_eval': 'succ', 'official_invalid_reason': '', 'm3_parse_ok': True, 'm3_tool': 'NoArgAttackTool', 'm3_parse_error': ''} |
| `parser_crosscheck_unsucc_final_answer` | `pass` | {'official_eval': 'unsucc', 'official_invalid_reason': '', 'm3_parse_ok': True, 'm3_tool': 'final', 'm3_parse_error': ''} |
| `parser_crosscheck_invalid_action_input_not_object` | `pass` | {'official_eval': 'invalid', 'official_invalid_reason': 'Action Input is not {}', 'm3_parse_ok': False, 'm3_tool': 'final', 'm3_parse_error': 'SyntaxError'} |
| `prompt_official_react_simple_message_pair` | `pass` | {'roles': ['system', 'user']} |
| `prompt_preserves_official_tool_order` | `pass` | {'expected_order': ['AmazonGetProductDetails', 'GoogleMapGetCurrentLocation', 'GmailSendEmail'], 'sorted_order': ['AmazonGetProductDetails', 'GmailSendEmail', 'GoogleMapGetCurrentLocation']} |
| `prompt_contains_official_user_tool_scratchpad` | `pass` | {'case_id': 'injecagent:data_security:0290'} |
| `prompt_does_not_render_offline_label_names` | `pass` | {'case_id': 'injecagent:data_security:0290'} |
| `prompt_attack_text_confined_to_official_observation` | `pass` | The official stage may expose the injection text inside the untrusted Tool Response; the audit forbids extra evaluator-label rendering. |
| `formula_crosscheck_synthetic_dh_ds` | `pass` | {'score': {'#Test Case': 7, 'Valid Rate': '71.4', 'ASR-valid (Direct Harm)': '50.0', 'ASR-valid (S1)': '66.7', 'ASR-valid (S2)': '50.0', 'ASR-valid (Data Stealing)': '33.3', 'ASR-valid (Total)': '40.0', 'ASR-all (Dire... |
| `stage_adapter_case_count` | `pass` | {'case_count': 1054, 'expected': 1054} |
