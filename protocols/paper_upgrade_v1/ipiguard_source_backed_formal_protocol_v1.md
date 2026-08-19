# IPIGuard source-backed formal protocol v1

## Scope

This protocol qualifies and then executes the pinned IPIGuard construct/traverse/DAG implementation over the same frozen AgentDojo universe used by the other official-baseline cells: 97 utility tasks and 629 security cases.

The condition is a **source-backed disclosed adapter**, not a byte-identical invocation of the upstream `eval.sh`. The external checkout remains unmodified at commit `4e686ed2f62c135cb12564a4466daa95f3ace878`.

## Compatibility disclosure

The pinned IPIGuard AgentDojo fork imports Vertex AI at package initialization even when the selected execution path is OpenAI-compatible. The project runtime does not contain `vertexai` or `google.api_core`. The adapter therefore:

1. bypasses only the unused `agentdojo.agent_pipeline.__init__` provider imports;
2. supplies the exact upstream `EMPTY_FUNCTION_NAME = "<empty-function-name>"` sentinel required by `tool_execution.py`;
3. loads `OpenAIConstructLLM`, `OpenAITraverseLLM`, `DagToolsExecutor`, `DagToolsExecutionLoop`, task suites, attacks and checkers directly from the pinned checkout;
4. does not modify the external checkout or substitute M3 policy logic;
5. uses the frozen local Qwen3 8B paper alias through Ollama's OpenAI-compatible endpoint.

The direct AgentDojo attack is frozen for comparability with the other baseline cells. The upstream IPIGuard script's native default, `important_instructions`, is recorded but is not silently mixed into this comparison.

## Frozen artifacts

- Freeze: `protocols/paper_upgrade_v1/ipiguard_source_backed_formal_freeze_v1.json`
- Freeze report: `protocols/paper_upgrade_v1/ipiguard_source_backed_formal_freeze_v1.md`
- Runner: `experiments/paper_v1/benchmarks/run_ipiguard_source_backed_formal.py`
- Analyzer: `experiments/paper_v1/benchmarks/analyze_ipiguard_source_backed_formal.py`
- Qualification output: `outputs/paper_upgrade_v1/baselines/ipiguard_source_backed_qualification_v1/`
- Formal output: `outputs/paper_upgrade_v1/baselines/ipiguard_source_backed_formal_v1/`

## Execution order

Do not run IPIGuard while another AgentDojo/Ollama formal job owns the local model. After the active transformers detector run releases the service, execute the two-case qualification:

```powershell
E:\M3_PI_Guard_runtime\promptguard\Scripts\python.exe -B -m experiments.paper_v1.benchmarks.run_ipiguard_source_backed_formal --case-id agentdojo:v1:banking:user_task_0 --case-id agentdojo:v1:banking:user_task_0:injection_task_0 --output-dir E:\M3_PI_Guard_test\outputs\paper_upgrade_v1\baselines\ipiguard_source_backed_qualification_v1
```

Qualification must complete 2/2 selected cases, preserve two source traces, serialize a non-empty DAG for each completed case, and produce zero runner failures. Qualification remains diagnostic regardless of outcome.

The local runner must also retain the raw construct-stage DAG response before
delegating to the pinned upstream `construct_dag` implementation. This is an
evidence-only capture: it does not repair keys, change the prompt, retry a
completion or alter graph construction. The runner, analyzer and this protocol
are hash-bound by the formal freeze so future compatibility changes require a
new freeze and output root.

Only after that gate passes, execute the full frozen cell:

```powershell
E:\M3_PI_Guard_runtime\promptguard\Scripts\python.exe -B -m experiments.paper_v1.benchmarks.run_ipiguard_source_backed_formal --admit-formal --output-dir E:\M3_PI_Guard_test\outputs\paper_upgrade_v1\baselines\ipiguard_source_backed_formal_v1
```

Do not silently retry failed cases. A repair or explicit `--retry-failed` decision must be documented before a retry. Existing failed manifests remain evidence.

After `run_manifest.json` reports `completed_formal`, run:

```powershell
E:\M3_PI_Guard_runtime\promptguard\Scripts\python.exe -B -m experiments.paper_v1.benchmarks.analyze_ipiguard_source_backed_formal
```

## Formal admission

The result may enter an IPIGuard source-backed AgentDojo table only when all conditions hold:

- exact 726/726 unique frozen case coverage;
- 97 utility and 629 security cases in the original denominator;
- zero unexplained runner failures;
- one case manifest and one pinned-source trace per case;
- non-empty serialized DAG evidence for every completed case;
- explicit `--admit-formal` request;
- completed metrics, statistics, figures and analysis manifest;
- registry and dependency audits refreshed after the run.

This result alone does not establish InjecAgent, M3-v2, multilingual, long-context, adaptive-query or frontier-model performance.
