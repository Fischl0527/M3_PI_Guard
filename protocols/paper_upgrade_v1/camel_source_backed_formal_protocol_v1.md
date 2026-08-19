# CaMeL source-backed formal protocol v1

## Scope

This protocol qualifies and then executes the pinned Google CaMeL interpreter over the same frozen AgentDojo universe used by the other official-baseline cells: 97 utility tasks and 629 security cases.

The condition is a source-backed disclosed adapter. The external CaMeL checkout remains unmodified at commit `f083b6b396399d3b3c7f2ddaf613a5945eaf32d8`.

## Compatibility disclosure

The pinned CaMeL source imports AgentDojo suite modules in an order that collides with the current pinned AgentDojo checkout. The adapter therefore:

1. installs a process-local AgentDojo suite import compatibility preload before importing CaMeL pipeline modules;
2. keeps upstream CaMeL policy engines, capability wrappers, `PrivilegedLLM` and `AgentDojoFunction` wrappers;
3. uses loopback OpenAI-compatible transports for both privileged generation and quarantined parsing;
4. passes the quarantined model through PydanticAI's OpenAI provider using the frozen local Qwen3 8B paper alias;
5. does not modify the external CaMeL checkout or substitute M3 policy logic;
6. logs the transport binding and policy engine for every completed case.

The direct AgentDojo attack is frozen for comparability with the other baseline cells. The freeze and preflights execute zero benchmark cases and are not result evidence.

## Frozen artifacts

- Freeze: `protocols/paper_upgrade_v1/camel_source_backed_formal_freeze_v1.json`
- Freeze report: `protocols/paper_upgrade_v1/camel_source_backed_formal_freeze_v1.md`
- Import preflight: `protocols/paper_upgrade_v1/camel_source_backed_import_preflight_v1.json`
- Compatibility preflight: `protocols/paper_upgrade_v1/camel_source_backed_compat_preflight_v1.json`
- Runner-wiring preflight: `protocols/paper_upgrade_v1/camel_source_backed_runner_preflight_v1.json`
- Transport/mapping preflight: `protocols/paper_upgrade_v1/camel_transport_mapping_preflight_v1.json`
- Runner: `experiments/paper_v1/benchmarks/run_camel_source_backed_formal.py`
- Analyzer: `experiments/paper_v1/benchmarks/analyze_camel_source_backed_formal.py`
- Qualification output: `outputs/paper_upgrade_v1/baselines/camel_source_backed_qualification_v1/`
- Formal output: `outputs/paper_upgrade_v1/baselines/camel_source_backed_formal_v1/`

## Execution order

Do not run CaMeL while another AgentDojo/Ollama formal job owns the local model. After the active official baseline job releases the service, execute the two-case qualification:

```powershell
E:\M3_PI_Guard_runtime\camel\.venv\Scripts\python.exe -B -m experiments.paper_v1.benchmarks.run_camel_source_backed_formal --case-id agentdojo:v1:workspace:user_task_0 --case-id agentdojo:v1:workspace:user_task_0:injection_task_0 --output-dir E:\M3_PI_Guard_test\outputs\paper_upgrade_v1\baselines\camel_source_backed_qualification_v1
```

Qualification must complete 2/2 selected cases, preserve two official traces, record a `camel_transport_binding` for every completed row and produce zero runner failures. Qualification remains diagnostic regardless of outcome.

Analyze the qualification run only as a diagnostic:

```powershell
E:\M3_PI_Guard_runtime\camel\.venv\Scripts\python.exe -B -m experiments.paper_v1.benchmarks.analyze_camel_source_backed_formal --run-dir E:\M3_PI_Guard_test\outputs\paper_upgrade_v1\baselines\camel_source_backed_qualification_v1 --output-dir E:\M3_PI_Guard_test\outputs\paper_upgrade_v1\baselines\camel_source_backed_qualification_v1\analysis --allow-diagnostic
```

Only after that gate passes, execute the full frozen cell:

```powershell
E:\M3_PI_Guard_runtime\camel\.venv\Scripts\python.exe -B -m experiments.paper_v1.benchmarks.run_camel_source_backed_formal --admit-formal --output-dir E:\M3_PI_Guard_test\outputs\paper_upgrade_v1\baselines\camel_source_backed_formal_v1
```

Do not silently retry failed cases. A repair or explicit `--retry-failed` decision must be documented before a retry. Existing failed manifests remain evidence.

After `run_manifest.json` reports `completed_formal`, run:

```powershell
E:\M3_PI_Guard_runtime\camel\.venv\Scripts\python.exe -B -m experiments.paper_v1.benchmarks.analyze_camel_source_backed_formal
```

## Formal admission

The result may enter a CaMeL source-backed AgentDojo table only when all conditions hold:

- exact 726/726 unique frozen case coverage;
- 97 utility and 629 security cases in the original denominator;
- zero unexplained runner failures;
- one case manifest and one official trace per case;
- `camel_transport_binding` evidence for every completed case;
- exact frozen source hashes and transport/mapping preflight hash still match;
- explicit `--admit-formal` request;
- completed metrics, statistics, figures and analysis manifest;
- registry, dependency, strong-baseline readiness and Q2 audits refreshed after the run.

This result alone does not establish InjecAgent, M3-v2, multilingual, long-context, adaptive-query or frontier-model performance.
