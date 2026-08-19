# AgentDojo official strong-baseline protocol v1

Updated: 2026-07-20

## Purpose

This protocol defines how AgentDojo's official `tool_filter` and
`transformers_pi_detector` defenses may become formal paper-v1 comparison
baselines.

The current repository already has local diagnostic AgentDojo prompt-baseline
adapters for `repeat_user_prompt` and `spotlighting_with_delimiting`. Those
adapters are not the same category as the two official strong baselines below.

## Evidence boundary

Current status is `capability_audit_plus_transformers_detector_smoke`.

The audit file
`protocols/paper_upgrade_v1/agentdojo_official_strong_baseline_capability_audit_v1.json`
confirms the pinned official source markers and local blockers, but it is not a
benchmark result.

The additional smoke manifest
`outputs/paper_upgrade_v1/baselines/agentdojo_transformers_pi_detector_smoke_v1/smoke_manifest.json`
confirms that AgentDojo's official `TransformersBasedPIDetector` class can load
the cached ProtectAI model offline in the dedicated E-drive runtime. This smoke
is still not an AgentDojo benchmark result.

No number produced by this audit may enter ASR, TCR, FPR, precision, recall,
latency, cost or Pareto tables.

## Official source boundary

The official source files for this protocol are:

- `external/benchmarks/agentdojo/src/agentdojo/agent_pipeline/agent_pipeline.py`
- `external/benchmarks/agentdojo/src/agentdojo/agent_pipeline/pi_detector.py`
- `external/benchmarks/agentdojo/src/agentdojo/scripts/benchmark.py`
- `external/benchmarks/agentdojo/README.md`

The capability audit records SHA-256 hashes for these files. If any source hash
changes, this protocol requires a new audit version before running formal
baselines.

## Baseline: official `tool_filter`

### Required official behavior

The defense must be run through AgentDojo's official pipeline path:

- `DEFENSES` contains `tool_filter`;
- `agent_pipeline.py` constructs `OpenAILLMToolFilter(TOOL_FILTER_PROMPT, llm.client, llm_name)`;
- `agent_pipeline.py` rejects non-`OpenAILLM` transports for `tool_filter`.

### Current blockers

- No `OPENAI_API_KEY` or `OPENAI_COMPATIBLE_BASE_URL` is configured in the
  current environment.
- A local M3 client wrapper is not byte-identical to AgentDojo's official
  `OpenAILLM` tool-filter path.

### Official command template

```powershell
cd external\benchmarks\agentdojo
python -m agentdojo.scripts.benchmark --model gpt-4o-2024-05-13 --defense tool_filter --attack tool_knowledge
```

The model name above is a placeholder copied from the official README style.
The formal run must record the exact approved model/provider/API endpoint.

## Baseline: official `transformers_pi_detector`

### Required official behavior

The defense must be run through AgentDojo's official pipeline path:

- `DEFENSES` contains `transformers_pi_detector`;
- `agent_pipeline.py` constructs `TransformersBasedPIDetector`;
- detector model is `protectai/deberta-v3-base-prompt-injection-v2`;
- `safe_label` is `SAFE`;
- `threshold` is `0.5`;
- `mode` is `message`;
- injected text is redacted with the official omitted-data placeholder.

### Current blockers

- The dedicated E-drive runtime can import AgentDojo official source via
  `PYTHONPATH`, load `transformers`/`torch`, and load the ProtectAI detector
  from `E:\AI_Cache\huggingface\hub`.
- ProtectAI revision `90c9989b1a342275dd0d1a95aad283c04e075671` is cached and
  hash-snapshotted.
- The required smoke checks pass: benign weather is safe, direct injection and
  the AgentDojo marker are detected. A quoted security discussion is also
  flagged and retained as a diagnostic false-positive probe.
- Remaining blocker: no frozen full AgentDojo
  `transformers_pi_detector` benchmark cell with complete official logs has
  run.

### Official command template

```powershell
cd external\benchmarks\agentdojo
python -m agentdojo.scripts.benchmark --model gpt-4o-2024-05-13 --defense transformers_pi_detector --attack tool_knowledge
```

The formal run must reuse or explicitly supersede the frozen detector
dependency versions, detector model hash/cache location, threshold and hardware
placement recorded by the smoke manifest.

## Required artifacts before formal-table eligibility

For each official strong baseline, all of the following artifacts are required:

1. Source audit JSON/Markdown with 100% passing marker checks.
2. Dependency snapshot:
   - Python executable;
   - package versions;
   - model/provider/API label;
   - detector cache hash if applicable;
   - GPU/CPU placement.
3. Frozen run manifest:
   - official AgentDojo commit/hash;
   - benchmark version;
   - suite/task/injection selection;
   - attack type;
   - defense name;
   - model name;
   - seed/repeat policy;
   - stdout/stderr paths.
4. Complete raw AgentDojo logs.
5. Official checker outputs for both utility and injection success.
6. M3-side conversion manifest if the result is mirrored into unified paper-v1
   tables.
7. A formal exclusion note for any AgentDojo task not run or not compatible.
8. Statistical analysis generated only after the run manifest is frozen.

If any item is missing, the baseline remains `blocked_or_diagnostic` and must
not be shown as a completed comparison.

## No-mixing rule

Do not add `agentdojo_tool_filter` or `agentdojo_transformers_pi_detector` to
the M3 local `DEFENSE_CONDITIONS` unless the condition name explicitly states
that it is a non-identical local adapter.

Allowed labels:

- `agentdojo_tool_filter_official`: byte-identical official AgentDojo pipeline.
- `agentdojo_transformers_pi_detector_official`: byte-identical official
  AgentDojo pipeline.
- `m3_local_tool_filter_adapter`: disclosed non-identical local adapter, not an
  official AgentDojo result.
- `m3_local_transformers_detector_adapter`: disclosed non-identical local
  adapter, not an official AgentDojo result.

Disallowed labels:

- `agentdojo_tool_filter` inside M3 local runner without byte-identical official
  execution.
- `agentdojo_transformers_pi_detector` inside M3 local runner without
  byte-identical official execution.

## Transition checklist

Move a baseline from `blocked` to `ready_for_smoke` only when:

- the dependency blocker is removed;
- the source audit still passes;
- the command can run on one official smoke case;
- raw logs and stderr are captured.

Move from `ready_for_smoke` to `formal_eligible` only when:

- the frozen protocol specifies the full AgentDojo task/security scope;
- all official logs are complete;
- all exclusions are declared before scoring;
- analysis scripts can regenerate the summary from the frozen manifest.

## Current decision

The official `tool_filter` baseline remains blocked by model transport. The
official `transformers_pi_detector` baseline is dependency-smoked but remains
outside formal paper-v1 effect tables until a frozen full AgentDojo cell runs
and is materialized with complete official logs.

- `tool_filter`: blocked by missing official model transport configuration.
- `transformers_pi_detector`: dependency-smoked; blocked by missing frozen full
  official AgentDojo cell and complete logs.

The Q2 paper gate remains `not_satisfied` until these baselines are either run
under this protocol or formally excluded with reviewer-facing justification.
