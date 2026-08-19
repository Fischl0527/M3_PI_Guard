# A19-wasp-benchmark entrypoints

- Artifact: WASP
- Component: web-agent benchmark task construction, online agent loop, and evaluator separation
- Commit: `ffee6f41fde76acd14bd792db442479c506260c2`

## Online boundaries

- `external/paper_v2_audits/wasp-http1/visualwebarena/agent/agent.py:298` — `PromptAgent.next_action`; parameters: `self, trajectory, intent, meta_data, images, output_response, conversation_renderer, prompt_injection`

## Offline/evaluator boundaries

- `external/paper_v2_audits/wasp-http1/webarena_prompt_injections/prompt_injector.py:389` — `WebArenaPromptInjector._create_task_dicts`
- `external/paper_v2_audits/wasp-http1/webarena_prompt_injections/run.py:13` — `run_single_end_to_end`

## Scope note

The archived Meta repository constructs separate user-goal and attacker-goal evaluator task dictionaries. The inspected PromptAgent boundary receives the user intent, trajectory/web observations, prompts and injected content, but not the separate eval dictionaries.
