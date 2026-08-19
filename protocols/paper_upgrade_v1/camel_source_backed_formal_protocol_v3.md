# CaMeL source-backed formal protocol v3

## Scope

This protocol refreshes the CaMeL source-backed strong-baseline route after two
preserved predecessor failures:

1. v1 failed the current identity gate before model probing.
2. v2 produced a diagnostic partial run, then failed when upstream CaMeL printed
   model-generated code containing `✅` to a Windows GBK stdout stream.

It keeps the pinned Google CaMeL checkout and the same frozen AgentDojo
universe: 97 utility tasks and 629 security cases.

The condition remains a source-backed disclosed adapter. The external CaMeL
checkout stays unmodified at commit `f083b6b396399d3b3c7f2ddaf613a5945eaf32d8`.

## Difference from v1/v2

CaMeL v1 is preserved as a historical freeze. It is not edited.

CaMeL v2 is preserved as a failed diagnostic qualification root. It is not
edited or retried in place.

CaMeL v3 only refreshes:

1. the hash-bound local adapter identity after shared runner-identity helpers
   changed;
2. the default freeze pointer used by the runner and analyzer;
3. project-internal paths in the new freeze and new manifests, which are stored
   relative to the repository root where possible;
4. the runner's stdio setup so upstream CaMeL debug prints use UTF-8 instead of
   the Windows default GBK stream;
5. the metric semantics layer, so AgentDojo raw `security=true` means the
   injection goal was achieved, and operational failures remain unresolved
   rather than being counted as safe.

It does not change the external CaMeL source, policy engine, security policy,
capability propagation, prompt templates, selected model alias or benchmark
case universe.

## Compatibility disclosure

The pinned CaMeL source imports AgentDojo suite modules in an order that
collides with the current pinned AgentDojo checkout. The adapter therefore:

1. installs a process-local AgentDojo suite import compatibility preload before
   importing CaMeL pipeline modules;
2. keeps upstream CaMeL policy engines, capability wrappers, `PrivilegedLLM`
   and `AgentDojoFunction` wrappers;
3. uses loopback OpenAI-compatible transports for both privileged generation and
   quarantined parsing;
4. passes the quarantined model through PydanticAI's OpenAI provider using the
   frozen local Qwen3 8B paper alias;
5. does not modify the external CaMeL checkout or substitute M3 policy logic;
6. logs the transport binding and policy engine for every completed case.

The direct AgentDojo attack is frozen for comparability with the other baseline
cells. The freeze and preflights execute zero benchmark cases and are not result
evidence.

## Frozen artifacts

- Freeze: `protocols/paper_upgrade_v1/camel_source_backed_formal_freeze_v3.json`
- Freeze report: `protocols/paper_upgrade_v1/camel_source_backed_formal_freeze_v3.md`
- Import preflight: `protocols/paper_upgrade_v1/camel_source_backed_import_preflight_v1.json`
- Compatibility preflight: `protocols/paper_upgrade_v1/camel_source_backed_compat_preflight_v1.json`
- Runner-wiring preflight: `protocols/paper_upgrade_v1/camel_source_backed_runner_preflight_v1.json`
- Transport/mapping preflight: `protocols/paper_upgrade_v1/camel_transport_mapping_preflight_v1.json`
- Runner: `experiments/paper_v1/benchmarks/run_camel_source_backed_formal_v3.py`
- Analyzer: `experiments/paper_v1/benchmarks/analyze_camel_source_backed_formal_v3.py`
- Qualification output: `outputs/paper_upgrade_v1/baselines/camel_source_backed_qualification_v3/`
- Formal output: `outputs/paper_upgrade_v1/baselines/camel_source_backed_formal_v3/`

## Execution order

Do not run CaMeL while another AgentDojo/Ollama formal job owns the local model.
After the service is free, execute the two-case qualification:

```powershell
& E:\M3_PI_Guard_runtime\camel\.venv\Scripts\python.exe -m experiments.paper_v1.benchmarks.run_camel_source_backed_formal_v3 --freeze protocols\paper_upgrade_v1\camel_source_backed_formal_freeze_v3.json --output-dir outputs\paper_upgrade_v1\baselines\camel_source_backed_qualification_v3 --case-id agentdojo:v1:banking:user_task_0 --case-id agentdojo:v1:banking:user_task_0:injection_task_0 --no-resume
```

Qualification must complete 2/2 selected cases, preserve official traces,
record a `camel_transport_binding` for every completed row, record
`metric_semantics_version=agentdojo_official_v2` for every case row and produce
zero runner failures. Qualification remains diagnostic regardless of outcome.

Analyze the qualification run only as a diagnostic:

```powershell
python -m experiments.paper_v1.benchmarks.analyze_camel_source_backed_formal_v3 --run-dir outputs\paper_upgrade_v1\baselines\camel_source_backed_qualification_v3 --output-dir outputs\paper_upgrade_v1\baselines\camel_source_backed_qualification_v3\analysis --allow-diagnostic
```

Only after that gate passes, execute the full frozen cell with explicit formal
admission and a fresh formal root:

```powershell
& E:\M3_PI_Guard_runtime\camel\.venv\Scripts\python.exe -m experiments.paper_v1.benchmarks.run_camel_source_backed_formal_v3 --freeze protocols\paper_upgrade_v1\camel_source_backed_formal_freeze_v3.json --admit-formal --output-dir outputs\paper_upgrade_v1\baselines\camel_source_backed_formal_v3
```

Do not silently retry failed cases. A repair or explicit `--retry-failed`
decision must be documented before a retry. Existing failed manifests remain
evidence.

## Formal admission

The result may enter a CaMeL source-backed AgentDojo table only when all
conditions hold:

- exact 726/726 unique frozen case coverage;
- 97 utility and 629 security cases in the original denominator;
- zero unexplained runner failures;
- zero unresolved security outcomes in formal analysis;
- one case manifest and one official trace per case;
- `camel_transport_binding` evidence for every completed row;
- `metric_semantics_version=agentdojo_official_v2` for every case row;
- exact frozen source hashes and transport/mapping preflight hash still match;
- explicit `--admit-formal` request;
- completed metrics, statistics, figures and analysis manifest;
- registry, dependency, strong-baseline readiness and Q2 audits refreshed after
  the run.

This result alone does not establish InjecAgent, M3-v2, multilingual,
long-context, adaptive-query or frontier-model performance.
