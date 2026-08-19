# A11-struq-runtime entrypoints

- Artifact: StruQ
- Component: structured-query frontend and model interface
- Commit: `e4372b9e3d45ecdfc7c0ad70662094efe6e3850b`

## Online boundaries

- `external/paper_v2_audits/struq/test.py:91` — `form_llm_input`; parameters: `data, injection_method, prompt_format, apply_defensive_filter, defense, sample_ids`
- `external/paper_v2_audits/struq/test.py:49` — `test_model_output`; parameters: `llm_input, model, tokenizer`

## Offline/evaluator boundaries

- `external/paper_v2_audits/struq/struq.py:112` — `preprocess`

## Scope note

StruQ structures natural-language instruction/data for a model and does not enforce tool authorization.
