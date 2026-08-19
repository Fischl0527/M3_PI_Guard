# A09-camel-runtime entrypoints

- Artifact: CaMeL
- Component: interpreter, capabilities, and security policies
- Commit: `f083b6b396399d3b3c7f2ddaf613a5945eaf32d8`

## Online boundaries

- `external/baselines/camel-prompt-injection/src/camel/pipeline_elements/privileged_llm.py:402` — `PrivilegedLLM.query`; parameters: `self, query, runtime, env, messages, extra_args`
- `external/baselines/camel-prompt-injection/src/camel/pipeline_elements/privileged_llm.py:235` — `PrivilegedLLM.run_code`; parameters: `self, code, env, namespace, dependencies`
- `external/baselines/camel-prompt-injection/src/camel/pipeline_elements/replay_privileged_llm.py:242` — `UserInjectionTasksGetter.query`; parameters: `self, query, runtime, env, messages, extra_args`
- `external/baselines/camel-prompt-injection/src/camel/pipeline_elements/replay_privileged_llm.py:287` — `PrivilegedLLMReplayer.query`; parameters: `self, query, runtime, env, messages, extra_args`

## Offline/evaluator boundaries

- None identified for this audit unit.

## Scope note

The live PrivilegedLLM path uses query/runtime/environment, while the optional replay path introspects benchmark stack frames and routes by user/injection task IDs.
