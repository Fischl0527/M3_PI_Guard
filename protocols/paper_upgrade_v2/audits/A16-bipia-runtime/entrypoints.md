# A16-bipia-runtime entrypoints

- Artifact: BIPIA
- Component: benchmark prompt construction and defenses
- Commit: `a004b69ec0dd446e0afd461d98cb5e96e120a5d0`

## Online boundaries

- `external/paper_v2_audits/bipia/bipia/data/abstract.py:59` — `AbstractIPIADataset.construct_prompt`; parameters: `self, example, require_system_prompt, ign_guidance`
- `external/paper_v2_audits/bipia/bipia/model/gpt.py:167` — `GPTModelWSystem.process_fn`; parameters: `self, example, prompt_construct_fn`

## Offline/evaluator boundaries

- `external/paper_v2_audits/bipia/bipia/data/abstract.py:70` — `AbstractIPIADataset.construct_response`

## Scope note

BIPIA constructs indirect-prompt-injection prompts and model messages; it does not gate tool execution.
