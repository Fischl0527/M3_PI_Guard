# A14-piarena-runtime entrypoints

- Artifact: PIArena
- Component: common attack/defense runtime
- Commit: `c39fd88e733493242a8ea6bdbc824ad30245bcf7`

## Online boundaries

- `external/paper_v2_audits/piarena/piarena/defenses/base.py:41` — `BaseDefense.get_response`; parameters: `self, target_inst, context, llm, system_prompt`
- `external/paper_v2_audits/piarena/piarena/defenses/base.py:35` — `BaseDefense._build_messages`; parameters: `self, target_inst, context, system_prompt`

## Offline/evaluator boundaries

- `external/paper_v2_audits/piarena/piarena/evaluations/__init__.py:24` — `substring_match`

## Scope note

The common runtime applies a prompt/context defense before a target LLM query; it does not authorize tool execution.
