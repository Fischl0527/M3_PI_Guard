# A06-agentdojo-detector entrypoints

- Artifact: AgentDojo
- Component: transformer prompt-injection detector defense
- Commit: `089ed468cf3ed0322acc66b0211f26d9d90dbf60`

## Online boundaries

- `external/benchmarks/agentdojo/src/agentdojo/agent_pipeline/pi_detector.py:56` — `PromptInjectionDetector.query`; parameters: `self, query, runtime, env, messages, extra_args`
- `external/benchmarks/agentdojo/src/agentdojo/agent_pipeline/pi_detector.py:156` — `TransformersBasedPIDetector.detect`; parameters: `self, tool_output`

## Offline/evaluator boundaries

- None identified for this audit unit.

## Scope note

The detector sees tool-output text and a fixed detector threshold/model; model class labels are detector outputs, not benchmark gold labels.
