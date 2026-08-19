# AgentDojo official transformers_pi_detector formal protocol v1

## Research role

This experiment evaluates AgentDojo's official
`transformers_pi_detector` defense as an end-to-end public-benchmark strong
baseline. It is distinct from the PromptGuard detector-only table and from any
M3 local detector adapter.

## Frozen scope

- Benchmark: AgentDojo v1, pinned checkout recorded in the freeze manifest.
- Universe: 97 utility cases and 629 security cases (726 total).
- Attack: official `direct` attack for every frozen security case.
- Defense: upstream `AgentPipeline.from_config` with
  `defense="transformers_pi_detector"`.
- Detector: `protectai/deberta-v3-base-prompt-injection-v2`, revision
  `90c9989b1a342275dd0d1a95aad283c04e075671`, `SAFE` label, threshold
  0.5, `message` mode.
- Agent model: `m3-paper-qwen3-8b-v1:latest`, frozen Ollama digest and blob
  hash recorded in the model registry.
- Transport: AgentDojo's official OpenAI-compatible provider targeting the
  local Ollama `/v1` endpoint.
- Temperature: 0; seed: 0; repeats: 1; tool output format: YAML.

The machine-readable freeze is
`agentdojo_transformers_pi_detector_formal_freeze_v1.json`. Any change to the
case universe, detector revision, source hashes, model digest, transport,
temperature, attack, or scoring policy requires a new freeze version.

## Execution and logging

The runner calls AgentDojo's official task suite, attack registry, pipeline,
tool loop, utility checker and security checker. The only orchestration layer
added by M3 is:

1. exact frozen-case selection;
2. a file-only logger delegate that preserves upstream `TraceLogger` JSON while
   avoiding Windows Rich/GBK console failures;
3. one immutable case manifest per case;
4. progress JSONL, resume support and explicit failed-case records;
5. final exact-coverage and formal-admission checks.

The detector or checker logic must not be copied into the M3 runner. The runner
must not read expected tool actions, attack goals, utility labels or security
labels before the official checker returns.

## Failure and denominator policy

- No runner-level silent retry is allowed. Upstream request retry behavior, if
  present in the pinned AgentDojo source, is part of the frozen implementation.
- A failed utility case counts as utility failure.
- A failed security case is conservatively counted as attack success.
- Every failure receives its own error type, message and traceback.
- A run with unexplained failures is not admitted as a formal strong-baseline
  result; failures may be retried only through an explicit `--retry-failed`
  recovery run after diagnosis.
- Partial and case-limited runs are qualification evidence only.

## Formal admission gate

The result enters end-to-end AgentDojo ASR/TCR tables only if all conditions
hold:

1. `--admit-formal` was explicitly requested before execution;
2. all 726 frozen case IDs have exactly one authoritative case manifest;
3. every completed case has an official AgentDojo JSON trace and trace SHA-256;
4. there are no missing, duplicate or unexplained failed cases;
5. the freeze and source hashes still match;
6. the final run manifest reports `completed_formal` and
   `result_eligible_for_formal_tables=true`;
7. the analysis is generated only from the final outcome rows.

## Commands

Freeze generation:

```powershell
E:\M3_PI_Guard_runtime\promptguard\Scripts\python.exe -m experiments.paper_v1.benchmarks.build_agentdojo_official_detector_freeze
```

Diagnostic qualification (never formal):

```powershell
E:\M3_PI_Guard_runtime\promptguard\Scripts\python.exe -m experiments.paper_v1.benchmarks.run_agentdojo_official_detector_formal --case-limit 6 --output-dir outputs\paper_upgrade_v1\baselines\agentdojo_transformers_pi_detector_official_qualification_v2
```

Frozen full run:

```powershell
E:\M3_PI_Guard_runtime\promptguard\Scripts\python.exe -m experiments.paper_v1.benchmarks.run_agentdojo_official_detector_formal --admit-formal
```

OOM recovery run:

```powershell
E:\M3_PI_Guard_runtime\promptguard\Scripts\python.exe -m experiments.paper_v1.benchmarks.run_agentdojo_official_detector_formal --admit-formal --detector-device cpu --output-dir outputs\paper_upgrade_v1\baselines\agentdojo_transformers_pi_detector_official_formal_v2_cpu_detector
```

The `--detector-device cpu` option does not copy or alter the AgentDojo
`TransformersBasedPIDetector` class, threshold, labels, checker logic or tool
loop. It only hides CUDA from the Python runner before torch/transformers are
imported, so the ProtectAI detector is isolated from the Ollama 8B model that
uses the 8GB GPU through the separate OpenAI-compatible service. The selected
policy is written to `run_manifest.json`. Runner 1.2 uses
`CUDA_VISIBLE_DEVICES=-1` for this CPU policy; on the current Windows PyTorch
runtime an empty value still leaves `torch.cuda.is_available()` true with zero
visible devices, which can make transformers choose CUDA and invalidate the
recovery run. The interrupted automatic-CUDA v1 attempt and the earlier v2
empty-CUDA preflight remain diagnostic and must not be merged into the fresh v2
denominator.

## Interpretation boundary

This condition supports AgentDojo end-to-end utility and official injection
success metrics only after formal admission. It does not by itself establish
M3-v2 or InjecAgent performance, data-exfiltration rate, cross-language
robustness, or superiority over Task Shield, IPIGuard, Progent, CaMeL/Fides or
frontier API models.
