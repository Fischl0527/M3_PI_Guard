# AgentDojo official tool_filter formal protocol v1

## Research role

This experiment evaluates AgentDojo's official `tool_filter` defense as an
end-to-end public-benchmark strong baseline. It uses the pinned upstream
`OpenAILLMToolFilter` component and must not be conflated with an M3-local tool
selection heuristic.

## Frozen scope

- AgentDojo v1: 97 utility + 629 security cases.
- Official direct attack for all security cases.
- Official `AgentPipeline.from_config(..., defense="tool_filter")` path.
- Agent and filter model: `m3-paper-qwen3-8b-v1:latest` through AgentDojo's
  upstream OpenAI-compatible provider pointed at local Ollama.
- The exact upstream filter prompt, prompt SHA-256, source commit and source
  file hashes are recorded in `agentdojo_tool_filter_formal_freeze_v1.json`.
- Temperature 0, repeat 1, YAML tool-output format.

## Compatibility claim

The pinned AgentDojo commit explicitly supports the `OPENAI_COMPATIBLE` model
provider, returns an upstream `OpenAILLM` instance, and therefore satisfies the
official `tool_filter` type guard. The transport is local, but the filter
pipeline, prompt, exact-name selection rule, task suite, attacks and checkers
are the pinned upstream implementation.

## Admission rules

1. Run a utility/security qualification pair first; it remains diagnostic.
2. Execute all 726 frozen cases with a dedicated output directory and explicit
   formal-admission flag.
3. Preserve one upstream `TraceLogger` JSON file and SHA-256 per completed case.
4. Count utility failures as unsuccessful and security failures as attack
   success; do not silently retry.
5. Require exact coverage, unique IDs, zero unexplained failures, completed
   analysis and a registry audit before formal-table admission.
6. Any prompt, model digest, source, temperature, attack or universe change
   requires a new freeze.

## Commands

Diagnostic qualification after the current transformers-detector run releases
the Ollama/GPU slot:

```powershell
E:\M3_PI_Guard_runtime\promptguard\Scripts\python.exe -m experiments.paper_v1.benchmarks.run_agentdojo_official_tool_filter_formal --case-id agentdojo:v1:banking:user_task_0 --case-id agentdojo:v1:banking:user_task_0:injection_task_0 --output-dir outputs\paper_upgrade_v1\baselines\agentdojo_tool_filter_official_qualification_v1
```

Frozen full run:

```powershell
E:\M3_PI_Guard_runtime\promptguard\Scripts\python.exe -m experiments.paper_v1.benchmarks.run_agentdojo_official_tool_filter_formal --admit-formal --output-dir outputs\paper_upgrade_v1\baselines\agentdojo_tool_filter_official_formal_v1
```

The runner path is
`experiments/paper_v1/benchmarks/run_agentdojo_official_tool_filter_formal.py`.
It does not implement a local tool-selection heuristic; it constructs the
official AgentDojo pipeline with `defense="tool_filter"` and only adds frozen
case selection, file-only logging, failure retention, resume support and formal
admission checks.

After a formal run is admitted, generate descriptive metrics, figures and the
analysis manifest with:

```powershell
E:\M3_PI_Guard_runtime\promptguard\Scripts\python.exe -m experiments.paper_v1.benchmarks.analyze_agentdojo_official_tool_filter_formal
```

The analyzer path is
`experiments/paper_v1/benchmarks/analyze_agentdojo_official_tool_filter_formal.py`.

## Interpretation boundary

This baseline measures official AgentDojo utility and injection success. It
does not establish performance on M3-v2, InjecAgent, multilingual attacks,
adaptive attacks or frontier API models. A superiority statement requires a
separately frozen paired comparison on identical model/case pairs.
