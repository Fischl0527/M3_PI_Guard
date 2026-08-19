# M3 paper-v1 implementation status

Updated: 2026-07-23

## Current authoritative checkpoint — 2026-07-23

- Q2 readiness remains raw 66.0/100 and capped 60.0/100;
  `goal_80_met=false` and `goal_90_met=false`.
- AgentDojo official `tool_filter` and PromptGuard detector-only formal remain
  the only two formal-ready strong baselines.
- Task Shield v1.3-v1.6 remain preserved negative engineering evidence and are
  not admissible formal baselines.
- Progent v1.2 is preserved as a pre-model instrumentation failure. Progent
  v1.3 fixed that instrumentation bug but failed P3 with parser/runtime
  failures. Progent v1.4 repaired the policy-output contract failure class and
  passed freeze/G1 gates, but the fresh P3 qualification failed the staged
  latency gate.
- Progent v1.4 P3 retained 8/8 terminal rows with 0 missing and 0 operational
  failures. Observed ASR was 0/4, full-denominator ASR bounds were 0% to 0%,
  utility-row success was 3/4, first policy contract success was 8/8 and total
  model requests were 81.
- Progent v1.4 G2 failed 11/12. The only failed check was p95 latency <=5x the
  matched ToolFilter comparator: 460,866 ms versus 41,643 ms, ratio 11.07x.
- Progent v1.4 P4/P5/P6, formal admission and registry updates are blocked.
  The refreshed planner preserves Progent as failed P3 qualification evidence.
- Current Progent evidence:
  `outputs/paper_upgrade_v1/baselines/progent_source_backed_qualification_v14_p3`,
  `outputs/paper_upgrade_v1/analysis_v2/progent_source_backed_v14_p3/`, and
  `protocols/paper_upgrade_v1/execution/progent_v14_p3_gate_failure_review_v1.md`.
- CaMeL v1 and v2 are preserved historical/diagnostic evidence. v2 failed on
  Windows GBK stdout when upstream CaMeL printed generated code containing
  `✅`; it was not retried in place.
- CaMeL v3 now has a fresh freeze and protocol:
  `protocols/paper_upgrade_v1/camel_source_backed_formal_freeze_v3.json` and
  `protocols/paper_upgrade_v1/camel_source_backed_formal_protocol_v3.md`.
- CaMeL v3 two-case qualification completed 2/2 with 0 failures. The follow-up
  P3 8-case qualification completed 8/8 with 0 failures and 0 unresolved
  security rows, but utility TCR was 0/4 and p95 latency was 159.003 s.
- CaMeL v3 remains diagnostic-only and is not formal-ready. The refreshed
  planner now blocks CaMeL formal execution at
  `review_camel_or_fides_v3_p3_before_p4`; P4/P5 gates or an IPIGuard/FIDES
  route decision are required before any 726-case run.
- Current CaMeL review:
  `protocols/paper_upgrade_v1/execution/camel_v3_p3_qualification_review_v1.md`.

## Current authoritative checkpoint — 2026-07-22

- Q2 readiness is raw 66.0/100 and capped 60.0/100;
  `goal_80_met=false` and `goal_90_met=false`.
- AgentDojo official `tool_filter` has completed its exact 726/726 formal run
  with 0 failures and has been admitted through the fail-closed analyzer and
  registry bridge. It is now one of two formal-ready strong baselines, together
  with PromptGuard detector-only formal.
- Task Shield v1.3 and v1.4 are sealed failed roots. v1.3 stopped at 42/726
  completed with one retained timeout and 683 missing; v1.4 stopped at 24/726
  completed, two invalid-JSON failures and 700 missing. Neither root was
  selectively retried, repaired, pooled or admitted.
- Task Shield v1.5 completed an exact 12-case stress qualification with
  11 completed and one timeout. The subsequent P0 source/raw-trace audit proved
  that the shared adapter inverted AgentDojo's official injection-success
  semantics; non-mutating analysis-v2 reports Task Shield raw Targeted ASR 0/6
  and ToolFilter 7/629. Historical rows remain unchanged.
- Task Shield v1.6 completed the prospective correctness path. G0 passed 15/15,
  G1 passed 20/20, its freeze passed 21/21, and the fresh four-case P3 passed
  G2 11/11. The fresh 12-case P4 retained 12/12 terminal rows but only nine
  completed: Slack utility and Workspace utility/attack reached the 600-second
  hard cap. Standalone utility was 2/6, attack-condition utility 0/6 and p95
  latency 600.070 seconds, 15.175 times the matched comparator. G3 failed at
  12/16.
- Task Shield formal expansion is now stopped. P5/P6 are not authorized, no
  result entered formal tables or registries, Q2 score change is zero, and the
  v1.3-v1.6 chain is retained as negative engineering evidence. The next strong
  baseline implementation route is Progent followed by CaMeL or an equivalent
  information-flow baseline. No model workload or Ollama listener remains live.
- `execution/q2_to_80_action_audit_v1.json/.md` is the current read-only
  action audit for the remaining sub-80 hard caps. It is operational metadata,
  not effect evidence, and it does not change the readiness score.
- Older dated sections below are historical checkpoint records. They are not
  current-state overrides when they mention raw 63.5, PromptGuard as the only
  admitted strong baseline, or ToolFilter as the active workload.

## 2026-07-22 independent-blind post-preregistration evidence separation

- The preregistration-bound `m3_v2_independent_blind_admission_audit_v1` remains
  byte-identical. The active candidate gate now writes a separate portable v2
  audit, currently `blocked_missing_candidate`, so future custody admission
  cannot overwrite the pre-candidate snapshot.
- `paper_v1_evidence_index_v1.json` is the only mutable pointer for future
  confirmatory paper-v1 evidence. Q2 readiness reads the independent-blind
  manifest from this index while continuing to use the immutable historical
  `final_analysis` manifest only for E0-E17 evidence.
- `admit_independent_blind_formal_result.py` requires an admitted candidate,
  exact 600-case independent scope, candidate SHA match, complete non-failed
  case-run counts and hash-verified runs/metrics/statistics/figures artifacts.
  It updates the index only with explicit `--write-evidence-index`; the current
  plan-only admission is correctly blocked and does not change the score.
- Focused independent-blind/Q2/layout regression passes 30/30, Ruff passes,
  portability/freeze checks pass, and readiness remains raw 66.0/capped 60.0.

## 2026-07-21 Task Shield v1.2 hash-bound disclosed reproduction checkpoint

- `taskshield_paper_formal_freeze_v1` has been rebuilt as schema
  `paper-taskshield-reproduction-freeze-1.2`. It now passes 13/13 checks and
  hash-binds the local disclosed-reproduction runtime, import preflight, runner,
  analyzer, shared resume-identity helper and protocol file alongside the ACL
  paper PDF SHA-256 and common 726-case AgentDojo universe.
- `taskshield_paper_import_preflight_v1` now passes 9/9 checks with no network,
  no Ollama probe and zero benchmark cases. It verifies that local adapter
  hashes match the freeze before any future model qualification can run.
- Task Shield registry/external status is now
  `disclosed_paper_reproduction_v1_2_hash_bound_formal_protocol_import_preflight_completed_qualification_pending`.
  This remains engineering readiness only; no public official Task Shield
  repository is pinned, no real-model two-case qualification has run, no
  complete 726-case logs exist and no admitted paper analysis exists.
- Refreshed dependency snapshot, baseline registry audit, external source audit,
  strong-baseline formal-readiness audit, Q2 readiness and read-only execution
  plan. Formal-ready strong baselines remain `["promptguard"]`; Q2 remains raw
  63.5/100 and capped 60.0/100 with `goal_90_met=false`. The active ToolFilter
  formal run is still read-only healthy at 433/726 completed, 0 failed and 293
  missing.

## 2026-07-21 CaMeL v1.2 hash-bound formal adapter checkpoint

- `camel_source_backed_formal_freeze_v1` has been rebuilt as schema
  `paper-camel-source-backed-formal-freeze-1.2`. It now passes 17/17 checks and
  hash-binds the local formal runner, analyzer, AgentDojo compat layer,
  source-backed runner, import/runner/transport audits, shared resume-identity
  helper and protocol file alongside the pinned CaMeL source and common 726-case
  AgentDojo universe.
- `run_camel_source_backed_formal.py` validates all frozen local-adapter hashes
  before service probing, and rejects stale resume roots before any Ollama probe
  when freeze SHA-256, runner version, model id, condition id, selected case
  count or selected-case-row SHA-256 differ. This prevents a stale v1.1 output
  root from being silently reused under v1.2 evidence.
- CaMeL registry/external status is now
  `source_smoke_completed_transport_mapping_hash_bound_formal_runner_ready_qualification_pending`.
  This remains engineering readiness only; CaMeL still has no real-model
  two-case qualification, no complete 726-case logs and no admitted paper
  analysis.
- Refreshed dependency snapshot, baseline registry audit, external source audit,
  strong-baseline formal-readiness audit, Q2 readiness and read-only execution
  plan. Formal-ready strong baselines remain `["promptguard"]`; Q2 remains raw
  63.5/100 and capped 60.0/100 with `goal_90_met=false`.

## 2026-07-21 Progent v1.1 hash-bound formal adapter checkpoint

- Added `progent_source_backed_formal_protocol_v1.md` and rebuilt
  `progent_source_backed_formal_freeze_v1` as schema
  `paper-progent-source-backed-formal-freeze-1.1`. The freeze now passes 13/13
  checks and binds the pinned Progent source, common 726-case universe, local
  runner, analyzer, import audit, shared resume-identity helper and protocol
  file hashes.
- `run_progent_source_backed_formal.py` now validates freeze SHA-256, runner
  version, model id, condition id, selected cases and selected-case-row SHA-256
  before any Ollama probe when resuming an existing output root. This prevents a
  stale v1 root from being silently reused under v1.1 evidence.
- The Progent import preflight now validates the same local adapter hashes and
  passes 10/10 checks with no network, no Ollama probe and zero benchmark cases.
  This remains engineering readiness only; Progent has no real-model
  qualification, no 726-case formal logs and no admitted paper result.
- Refreshed dependency snapshot, baseline registry audit, external source audit,
  strong-baseline formal-readiness audit and Q2 readiness. Formal-ready strong
  baselines remain `["promptguard"]`; Q2 remains raw 63.5/100 and capped
  60.0/100 with `goal_90_met=false`.
- Verification: Progent focused tests 7/7, combined public/strong-baseline
  regressions 108/108, Q2 planner/readiness tests 11/11, `py_compile`, Ruff and
  `git diff --check` passed.

## 2026-07-21 Q2 evidence-chain hardening checkpoint

- `audit_q2_readiness.py` now treats the independent blind gate as a formal
  result-admission check rather than a final-manifest field check. A future
  `m3_v2_independent_blind_manifest` must resolve to an admitted independent
  blind result with formal status, result eligibility, exactly 600 cases,
  independent-blind scope, non-post-hoc boundary and a candidate SHA-256 that
  matches `m3_v2_independent_blind_admission_audit_v1`. The current candidate
  is absent, so the Q2 blind gate remains blocked and the score does not rise.
- Q2 monitor selection for AgentDojo `transformers_pi_detector` now prefers a
  monitor snapshot whose `run_manifest_path` matches the selected detector run.
  The selected monitor is
  `protocols/paper_upgrade_v1/monitors/transformers_pi_detector_formal_v2/agentdojo_official_formal_run_monitor_v1.json`,
  not the stale generic monitor. It reports 75/726 completed, 1 failed, 650
  missing and `pid_alive=false`.
- The selected detector failure is now classified as a resource failure:
  `agentdojo:v1:workspace:user_task_25` raises a CPU `DefaultCPUAllocator`
  error while the official Hugging Face text-classification pipeline attempts
  to allocate 2,185,056,432 bytes. This remains exact-official diagnostic
  evidence only; it is not a formal baseline result and should not be repaired
  by silently truncating detector input.
- Added `diagnose_agentdojo_formal_run_failures.py` and generated
  `protocols/paper_upgrade_v1/diagnostics/agentdojo_transformers_detector_failure_v1/failure_diagnostic.json/.md`.
  The artifact classifies retained failures without retrying, excluding,
  repairing or admitting rows. Current classification is `resource_cpu_memory`
  with 76 outcome rows, 1 failed row and stderr hashes; it remains
  `result_eligible_for_formal_tables=false`.
- `q2_readiness_audit_v1` remains raw 63.5/100 and capped 60.0/100. The active
  hard caps remain public benchmark completion, strong-baseline count,
  independent blind, frontier API model slots and adaptive budget evidence.
- Verification for this checkpoint: py_compile passed, focused Q2/frontier/tool
  filter admission/failure-diagnostic tests passed 21/21, and Ruff passed for
  the changed audit, diagnostic and tests.

## 2026-07-21 CaMeL isolated runtime, transport mapping and formal-freeze checkpoint

- CaMeL 现在已有隔离的 E 盘依赖 runtime：`E:\M3_PI_Guard_runtime\camel\.venv\Scripts\python.exe`
  为 Python 3.10.12，依赖由 `E:\M3_PI_Guard_runtime\camel_bootstrap`
  中的 `uv` 同步，缓存固定到 `E:\AI_Cache\uv`。该步骤没有污染
  PromptGuard venv，没有启动 Ollama，也没有调用模型/API。
- `audit_camel_source_backed_import_preflight.py` 生成
  `camel_source_backed_import_preflight_v1.json/.md`；12/12 checks 通过，
  status=`completed_dependency_import_preflight_blocked`，
  `result_eligible_for_formal_tables=false`；它保留 fresh-process 官方
  pipeline/suite import-order failure 证据。
- 新增 `camel_agentdojo_compat.py` 和
  `audit_camel_source_backed_compat_preflight.py`，生成
  `camel_source_backed_compat_preflight_v1.json/.md`；8/8 checks 通过。
  compat 层只在当前进程预加载官方 AgentDojo suite modules，不编辑外部源码或
  site-packages，不联网、不启动 Ollama/API、不运行 benchmark case。
- 新增 `camel_source_backed_runner.py` 和
  `audit_camel_source_backed_runner_preflight.py`，生成
  `camel_source_backed_runner_preflight_v1.json/.md`；14/14 checks 通过。
  它只构建官方 `PrivilegedLLM` 加 suite security policy pipeline 骨架：
  workspace、travel、banking、slack 四个 suite 均可构建，benchmark cases=0，
  model/API calls=0，network_attempted=false，且
  `result_eligible_for_formal_tables=false`。
- 新增 `camel_transport_mapping_preflight_v1.json/.md`；16/16 checks 通过。
  它冻结 loopback privileged/quarantined transport、suite capability mapping、
  benchmark cases=0、model/API calls=0、network_attempted=false 和
  `result_eligible_for_formal_tables=false` 的边界。
- `camel_source_backed_formal_freeze_v1` 已重建为 schema
  `paper-camel-source-backed-formal-freeze-1.2`，17/17 checks，
  status=`completed_frozen_formal_protocol`。当前 CaMeL blocker 已从
  “uv missing / import-order cycle / runner wiring / transport mapping absent”
  精确化为 two-case real-model qualification、726-case complete logs 和
  formal admission 缺失；v1.2 还额外 hash-bind 本地 adapter 文件并在
  Ollama probe 前拒绝 resume identity drift。
- 强基线 dependency/source snapshot、baseline registry audit、external
  source audit、formal-readiness audit 和 Q2 readiness 均已刷新。CaMeL
  source/runtime blockers 已清空，但 PromptGuard 仍是唯一 formal-ready
  required strong baseline，且只限 detector 表；CaMeL 仍为
  blocked/non-formal。`q2_readiness_audit_v1` 维持 raw 63.5/100、capped
  60.0/100，goal_90_met=false。
- AgentDojo official `tool_filter` 726-case formal run 仍由 PID 36472 健康
  运行；latest read-only snapshot 为 433/726 completed、0 failed、
  293 missing。未完成和 analyzer admission 前不得计入正式表，
  也不得并发启动其他 Ollama/GPU formal job。
- 本轮验证：CaMeL/强基线 targeted tests 19 passed；blind/adaptive/frontier
  scaffolding tests 16 passed；TaskShield/Progent/IPIGuard/CaMeL strong-baseline
  regression 23 passed。
- 新增 `admit_agentdojo_tool_filter_formal_result.py` admission bridge。它只在
  run manifest、monitor 和 analysis 三方均证明 exact 726/726、0 failure、
  `completed_formal` 时才允许用 `--write-registry` 把 `agentdojo_tool_filter`
  更新为 formal-ready strong baseline。当前运行一次为
  `blocked_not_formally_admitted`，未写 registry。
- `audit_q2_readiness.py` 已修复 stale `transformers_pi_detector` 监控归因。
  旧 detector running manifest 不再因 tool_filter monitor 健康而被记作
  `running_progressing`；当前 detector scored status 为
  `not_admitted_or_not_progressing`。
- Frontier API model-slot gate 的自动衔接已修复。`audit_frontier_api_model_slots.py`
  现在只在 `frontier_api_model_slot_registry_admission_v1.json` 为
  `admitted_registry_candidate` 且 `model_registry_v3_candidate.json` 哈希匹配时
  选择 v3 candidate；`audit_q2_readiness.py` 使用该审计后的 registered
  frontier vendor count 来计算 model coverage 和 frontier API cap。当前实际状态
  仍是 0/2 providers configured、registry admission `blocked_smoke_not_qualified`，
  因此 Q2 raw/cap 不变。

## 2026-07-21 Q2-readiness and AgentDojo strong-baseline checkpoint

- Independent-blind admission now requires a separately released custody
  sidecar whose candidate filename, 600-row count, SHA-256, independent author
  IDs, custodian, isolated environment, no-developer-access declaration and
  seal timestamp all validate and match every candidate row. The candidate is
  still absent, so the gate remains blocked and no score is awarded.
- Frontier API registry admission is implemented as a no-network, no-credential
  step after smoke. Current plan-only evidence fails closed, writes no v3
  registry candidate and remains non-formal; mocked clean and blocked paths are
  covered by tests.
- Strong-baseline readiness now distinguishes IPIGuard source-backed adapter
  completion from formal-result completion. Its adapter-source requirement
  passes, while runtime qualification, complete logs and formal admission remain
  missing; it therefore remains `blocked_or_diagnostic` and PromptGuard remains
  the only formal-ready baseline.
- The official AgentDojo detector exact full-run path is now resource-blocked.
  The v2 CPU retry reproduced the same 2,185,056,432-byte CPU allocation
  failure on `workspace:user_task_25`, and a direct long-output smoke that
  unloads Ollama before calling the pinned official detector also failed on the
  preserved 27,697-character `list_files` output. The v1/v2 roots and smoke are
  diagnostic only; no exact-official 726-case run is currently being started.

- `q2_readiness_audit_v1` is now the conservative paper-upgrade scorecard.
  Current score is raw 63.5/100 and capped 60.0/100, so the 90+ Q2-readiness
  goal is not met. Active hard gates remain: public-benchmark formal matrix,
  at least five source-backed strong baselines, independent M3-v2 blind
  evidence, two frontier API vendor model slots and formal adaptive
  query-budget attacks.
- `formal_security_properties_v1.md` records the conditional safety properties
  for the non-oracle runtime monitor. The paper may cite these only as a
  proof sketch under complete mediation and correct provenance/labelling, not
  as an unconditional security proof.
- `paper_storyline_v1.md` freezes the current manuscript narrative, blocked
  claims and required figures.
- `adaptive_mcts_budget_freeze_v1.json/.md` freezes an 80-task query-budgeted
  adaptive attack panel across 9 attack families, 6 languages and 100/500/2000
  query-budget groups. It excludes sealed holdout cases and is not result
  eligible until the separate MCTS run manifest reports `completed_formal`.
- AgentDojo official `tool_filter` has a frozen local OpenAI-compatible
  protocol, runner and analyzer and has passed a 2-case diagnostic qualification
  as `ready_official_tool_filter_qualification_completed_formal_run_pending`,
  but remains outside formal result tables. The runner/analyzer are
  `run_agentdojo_official_tool_filter_formal.py` and
  `analyze_agentdojo_official_tool_filter_formal.py`. Runner 1.1 records a
  disclosed OpenAI-compatible tool-filter model-binding shim for the local
  Ollama transport; it changes only `OpenAILLMToolFilter.model` from the
  provider name to the frozen model id, not the prompt, algorithm, selection
  rule, tasks or checkers. A second utility+security diagnostic qualification
  also completed 2/2 with zero failures; its security case had
  `attack_success=1`, so the qualification proves executability, not defensive
  effectiveness. The 726-case formal cell has now been launched with
  `--admit-formal`, but it is still running and ineligible until completion,
  exact coverage, zero unexplained failures and analyzer admission.
- AgentDojo official `transformers_pi_detector` v1 automatic-CUDA full attempt
  was invalidated after CUDA OOM at 92 completed / 4 failed / 630 missing. An
  early v2 empty-CUDA preflight was also invalidated because transformers still
  selected CUDA. Runner 1.2 now uses `CUDA_VISIBLE_DEVICES=-1` for
  `--detector-device cpu`; a one-case CPU-device preflight completed 1/1 with
  `Device set to use cpu`.
- A resource-isolated freeze
  `agentdojo_transformers_pi_detector_resource_isolated_freeze_v1.json` and
  runner 1.3 are available, but the direct long-output smoke failed before any
  fresh resource-isolated 726-case formal manifest was created. The old v2 CPU
  root remains stale/diagnostic and must not be resumed or admitted.
- `agentdojo_official_formal_run_monitor_v1` is now a read-only monitor for
  official AgentDojo long runs. The latest snapshot points to the
  resource-isolated target root and reports `missing_manifest`; this is
  intentional after the direct long-output smoke blocked another exact full run.
  The monitor is operational evidence only; it does not admit, retry, repair or
  analyze results.
- `m3_v2_independent_blind_admission_audit_v1` now defines the candidate
  gate for a future 600-case independently authored blind set: 360 attacks,
  120 benign no-tool, 120 benign legal-tool, 9 attack families x 40 cases,
  custody records, no template/runtime overlap with the reference dataset and
  no oracle runtime fields. Current status is `blocked_missing_candidate`, so
  the automated sealed holdout remains excluded from confirmatory blind claims.
- `frontier_api_model_slot_admission_audit_v1` now records the Q2 frontier-API
  model gate without making network calls or printing credentials. The local
  config is ignored/untracked and has no tracked-file secret hits, but OpenAI
  and Anthropic model slots are still placeholders, explicit network-smoke
  consent is absent, and `model_registry_v2.json` still has 0 registered
  frontier API vendor slots.
- IPIGuard now has a pinned-source formal adapter preparation layer:
  `ipiguard_source_backed_formal_freeze_v1` freezes all 726 AgentDojo cases and
  11 upstream source hashes (8/8 checks), while the runner/analyzer directly use
  upstream construction, traversal, DAG execution and trace classes. The
  disclosed fresh-process import isolation replaces only an unused optional
  Vertex AI constant required by package import; it does not replace the
  baseline algorithm.
- `ipiguard_source_backed_import_preflight_v1` passed 6/6 checks in a child
  process with no network, no Ollama probe and zero benchmark cases. The later
  2-case runtime qualification completed only 1/2 cases and failed 1/2 inside
  upstream IPIGuard `construct_dag()` with `KeyError('function_name')` because
  the local Qwen3 8B DAG tool-call JSON did not satisfy the expected schema.
  Registry status is therefore
  `source_backed_adapter_runtime_qualification_failed_model_dag_schema`, not
  formal-ready. A disclosed frozen fix/configuration, followed by qualification
  and a full 726-case admitted run, remains mandatory.
- The adaptive MCTS formal runner/analyzer and protocol are implemented. A
  2-task x 3-query Stub orchestration preflight completed 6/6 query calls with
  zero task failures and generated diagnostic PNG/SVG figures. Both manifests
  remain explicitly ineligible. The readiness audit awards one engineering
  point for this runnable preflight, but stale detector-running credit was
  removed; the active healthy `tool_filter` run contributes only 0.5 engineering
  progress point (raw 63.5) while retaining the 60 cap until
  the real frozen 80-task 100/500/2000-budget run is analyzed and admitted.
- A content-free independent-blind authoring kit is complete under
  `independent_blind_authoring_kit_v1/`: 600 stratified assignment slots, case
  and custody templates, and detailed external authoring/sealing/sample-review
  instructions. It creates zero candidate cases and remains result-ineligible;
  the project developer must not fill it, so the independent-blind admission
  gate correctly remains `blocked_missing_candidate`.
- OpenAI/Anthropic frontier API transports and a redacted smoke harness are now
  implemented. The default plan-only execution reported 0 configured providers
  and 0 network calls; 13 focused client/config tests passed. Real transport
  requires HTTPS, explicit consent and exactly one provider attempt, while
  stored metadata omits credentials. No API slot is registered and no readiness
  point is awarded until the owner selects models, approves cost and completes
  both real synthetic smokes.

## 2026-07-20 PromptGuard detector-only formal baseline checkpoint

- PromptGuard v1 has advanced from qualification-only to a source-backed,
  frozen detector-only formal baseline over 3,280 external-content detector
  inputs: M3-v2 1,500 cases, AgentDojo 97 utility + 629 security cases and
  InjecAgent 1,054 security cases.
- The freeze separates `detector_inputs.jsonl` from `detector_labels.jsonl`.
  The runner does not read labels, target actions, expected answers,
  per-case `authorized_actions` or evaluator checker results.
- The formal run used revision `a8ded8e697ce7c355e395a0df51f94adb4a2fd27`,
  threshold 0.5, real tokenizer-aware non-overlap 512-token windows and
  max-malicious-score aggregation. It completed 3,280/3,280 predictions with
  0 inference failures.
- Overall detector result: TP 635, FN 1,948, FP 0, TN 697; Recall 24.58%,
  FPR 0.00%, Precision 100.00%, F1 39.47%; median / p95 per-case latency
  17.384 / 47.167 ms.
- Benchmark split: AgentDojo recall 629/629 = 100.00% with FPR 0/97 = 0.00%;
  InjecAgent recall 6/1,054 = 0.57%; M3-v2 recall 0/900 = 0.00% with FPR
  0/600 = 0.00%.
- Formal eligibility is deliberately narrow: this result may enter
  detector-performance tables only. It does not support end-to-end agent ASR,
  TCR, legal-tool utility, security-utility Pareto or SOTA claims.
- Generated artifacts:
  `protocols/paper_upgrade_v1/promptguard_detector_formal_protocol_v1.md`,
  `protocols/paper_upgrade_v1/promptguard_detector_formal_freeze_v1.json`,
  `outputs/paper_upgrade_v1/baselines/promptguard_detector_formal_v1/`,
  and six figure pairs under the analysis directory.
- Strong-baseline formal-readiness is now 1/5: PromptGuard is the only
  formal-ready required strong baseline, and only for detector performance.
  The Q2 strong-baseline gate remains `not_satisfied`.

## 2026-07-20 PromptGuard real-model qualification checkpoint

- The ignored local configuration passed redacted credential, Git-safety and tracked-file secret scans; no credential value appears in logs or manifests.
- Frozen revision `a8ded8e697ce7c355e395a0df51f94adb4a2fd27` is complete in `E:\AI_Cache\huggingface`: 10 files / 1,131,674,611 bytes with per-file SHA-256 evidence.
- A real CUDA 12-case smoke completed with all runtime checks passing and no stub path. Diagnostic agreement was 9/12: both direct injections detected, Chinese indirect injection and Base64 missed, and one benign quoted security discussion flagged.
- This output remains qualification-only by itself; the separate detector-only
  formal baseline above is the only PromptGuard result eligible for formal
  paper tables, and only within detector-performance scope.
- Final qualification verification matched all 10 downloaded files by size/SHA-256; focused regression passed 101/101; Registry/history/static gates passed; source/dependency/formal-readiness/registry audits passed 10/10, 5/5, 7/7 and 11/11. The aggregate verifier's repeated full-pytest stall is disclosed separately and not counted as a pass.
- Final service state is Ollama 0, port 11434 listeners 0, Docker 0 and Python 0.

## 2026-07-18 Ollama migration and modern-open model checkpoint

- Active Ollama storage is `E:\Ollama\models`. The pre-migration union contained 53 files, 41 blobs and 11 model manifests (17.561 GiB); every target file matched source size and SHA-256. Both restart validations completed 11/11 metadata/generation smokes before the exact D-drive backup was deleted, reclaiming 13.200 GiB while preserving `D:\Ollama\app`.
- `qwen3:8b` and `llama3.1:8b` are frozen locally as `m3-paper-qwen3-8b-v1:latest` and `m3-paper-llama31-8b-v1:latest`. Their exact manifests, blob digests, Q4_K_M quantization and context metadata are registered in `model_registry_v2.json`.
- The modern-open qualification rerun completed 24/24 case-runs with zero runner/provider failures across two models, six fixed validation cases and two conditions. This remains diagnostic qualification evidence and is not eligible for formal effect tables.
- The PromptGuard environment is pinned under `E:\M3_PI_Guard_runtime\promptguard`, with Hugging Face cache under `E:\AI_Cache\huggingface`. The official 86M revision is now complete and hash-frozen; the prior gated/partial snapshot remains archived as historical blocker evidence.
- `public_benchmark_formal_freeze_v2` preserves v1 and expands the ready-local declaration to seven models, 84 cells and 74,760 pending case-runs. The two modern 7B-14B slots are now filled; the Q2 model gate remains unsatisfied because two frontier API vendor slots and all formal runs are still missing.
- 2026-07-20 credential handoff is complete: the ignored per-member config passed redacted validation, the frozen download and real smoke succeeded, and the credential was not written into tracked files or evidence. The later detector-only formal run is complete and admitted only for detector-performance tables.

## Current evidence boundary

This paper-v1 track is a new non-oracle research path. It preserves E0-E17 and
Acceptance Remediation V2 as historical evidence, but does not treat them as a
new blind confirmation.

Current generated outputs are split into three evidence levels:

| Level | Meaning | Current examples |
|---|---|---|
| `demo_not_formal_evidence` | Figure layout and artifact build-chain checks only. | `outputs/paper_upgrade_v1/figures_demo/` |
| `diagnostic_not_formal_evidence` | Real runtime or data pipeline smoke checks; useful for debugging and method development. | local-model smoke, policy-regime smoke, InjecAgent replay, AgentDojo native repeated slices and selected-cluster screens |
| formal evidence | Frozen hypotheses, cases, thresholds, exclusions, public benchmark protocol and statistical plan before execution. | PromptGuard detector-only v1 is complete for detector-performance tables only; full public benchmark/end-to-end formal cells remain pending |

No paper-v1 diagnostic output may be cited as a confirmatory blind result or a
state-of-the-art comparison.

## Implemented

- Non-oracle task-policy runtime:
  - `TaskPolicyManifest`, `ActionProposal`, `GuardDecision`, `ProvenanceEvent`;
  - trusted-input-only policy compiler;
  - provenance-aware `ALLOW/ASK/DENY` monitor;
  - policy/provenance/temporal/dataflow/confirmation component switches.
- Policy-regime support:
  - `auto_compiled`, `ambiguous`, `partial`, `incorrect`;
  - diagnostic qwen3 smoke completed for 24 case-runs.
- M3-v2 dataset:
  - 1,500 cases;
  - 900 attacks, 300 benign no-tool, 300 benign legal-tool;
  - 600/300/600 template-isolated split;
  - 500-row stratified human-review sampling frame.
- Public benchmark indexing:
  - AgentDojo pinned and indexed: 97 utility tasks, 629 security cases;
  - InjecAgent pinned and indexed: 1,054 security cases, 330 tool schemas;
  - offline labels remain outside online inputs.
- Strong-baseline registry:
  - baseline registry upgraded to schema `m3-paper-baselines-1.1`;
  - AgentDojo official `tool_filter` and `transformers_pi_detector` are now explicitly represented as blocked official strong-baseline candidates;
  - PromptGuard, Task Shield, IPIGuard, Progent and CaMeL/Fides are represented with blocker lists, compatibility plans and formal exclusion rules;
  - readiness audit `baseline_registry_audit_v1` completed 11/11 checks and keeps the Q2 strong-baseline gate at `not_satisfied`.
  - AgentDojo official strong-baseline capability audit `agentdojo_official_strong_baseline_capability_audit_v1` completed 9/9 checks and records source markers, dependency blockers, official command templates and the no-mixing boundary for `tool_filter` and `transformers_pi_detector`.
  - External strong-baseline source registry/audit `external_strong_baseline_source_audit_v1` completed 11/11 checks, covering PromptGuard, Task Shield, IPIGuard, Progent and both CaMeL/FIDES candidates with source URLs, remote HEADs where available, blockers, formal exclusion rules and PromptGuard's detector-only formal admission.
  - Strong-baseline source checkout manifest `strong_baseline_source_checkout_manifest_v1` completed 5/5 checks after pinning PurpleLlama, IPIGuard, CaMeL and FIDES under `external/baselines/`; these checkouts remain ignored reproducible caches, not vendored source.
  - IPIGuard official source-smoke `ipiguard_official_source_smoke_v1` completed 8/8 checks, validating the pinned source commit, official eval entrypoint, `ipiguard` pipeline wiring, DAG construction/traversal markers, whitelist/command split and 97 utility / 629 security dataset universe; it remains non-experimental and result-ineligible.
  - Strong-baseline dependency/source snapshot `strong_baseline_dependency_snapshot_v1` completed 5/5 checks, records local package, model-cache, adapter-preflight, source-smoke and source-checkout state; IPIGuard is source-smoke complete but still lacks a source-backed formal adapter, CaMeL is selected with source ready but `uv` missing, and the Q2 strong-baseline gate remains `not_satisfied`.
  - Strong-baseline formal-readiness audit `strong_baseline_formal_readiness_audit_v1` completed 7/7 checks, consumes the dependency snapshot with status `completed`, and confirms PromptGuard is the only required strong baseline admitted so far, with detector-performance scope only. Task Shield, IPIGuard, Progent, CaMeL/FIDES and AgentDojo official strong-baseline entries remain outside formal result tables until source-backed adapters, dependency snapshots, manifests and complete logs exist.
  - Public benchmark formal-freeze manifest `public_benchmark_formal_freeze_v1` completed 9/9 checks, freezes the full AgentDojo 97 utility + 629 security and InjecAgent 1,054 security case universes, declares a 53,400 case-run ready-local matrix, and keeps the Q2 public-benchmark gate at `not_satisfied`.
  - Public benchmark formal-run plan `public_benchmark_formal_run_plan_v1` initialized the frozen ready-local matrix into 60 pending cell manifests and 53,400 pending case-run todo rows under `outputs/paper_upgrade_v1/public_benchmark_formal_runs`, without starting models or marking any result eligible.
  - Public benchmark formal case-result row builder `formal_case_result_rows.py` standardizes benchmark-specific outcomes into materializer-ready `case_results.jsonl` rows and refuses to upgrade diagnostic source statuses into formal evidence.
  - Public benchmark formal-cell runner wrapper `run_public_benchmark_formal_cell.py` and protocol `public_benchmark_formal_cell_runner_v1.md` dry-run one frozen cell, convert supplied official outcome JSONL into standardized case results, keep missing outcomes in the denominator, and only allow materialization after explicit formal admission plus accepted source evidence.
  - AgentDojo formal-cell source producer `run_agentdojo_formal_cell.py` and protocol `agentdojo_formal_cell_runner_v1.md` can dry-run a frozen AgentDojo cell, execute explicit AgentDojo native source jobs when requested, emit `agentdojo_outcomes.jsonl`, track `progress.jsonl`, resume completed jobs, preserve failures unless `--retry-failed` is supplied, and only label rows as `agentdojo_official_formal_case_run` for full-cell, non-stub, zero-failure runs with explicit formal-source admission.
  - InjecAgent formal-cell source producer `run_injecagent_formal_cell.py` and protocol `injecagent_formal_cell_runner_v1.md` can dry-run a frozen InjecAgent cell, execute explicit official-stage source jobs when requested, emit `injecagent_outcomes.jsonl`, track `progress.jsonl`, resume completed jobs only when paired `runs.jsonl` exists, preserve failures unless `--retry-failed` is supplied, and only label rows as `injecagent_official_formal_case_run` for full-cell, non-stub, zero-failure runs with explicit formal-source admission and an official ReAct prompt style.
  - Public benchmark formal-cell materializer `materialize_public_benchmark_formal_cell.py` now enforces the raw-runs → metrics → statistics → figure-manifest → completed-cell contract; it marks a cell result-eligible only when every frozen todo case-run is present, completed and declared as `formal_public_benchmark_case_run`.
  - Public benchmark result-completeness audit `public_benchmark_result_completeness_audit_v1` completed 5/5 checks and records the current formal-result gate as `not_satisfied`: 60 expected matrix cells, 60 initialized pending cells, 0 complete cells, 53,400 expected case-runs and 0 complete case-runs.
  - PromptGuard detector adapter preflight `promptguard_detector_adapter_preflight_v1` links the completed real-model smoke. The follow-up source-backed detector-only formal run `promptguard_detector_formal_v1` is complete and eligible only for detector-performance tables; its low recall on InjecAgent and M3-v2 is retained as an actual result, not tuned away.
  - Task Shield alignment adapter preflight `taskshield_alignment_adapter_preflight_v1` completed its stub smoke, proving online-only task-alignment record construction, runtime action-proposal separation and forbidden-field exclusion while keeping real Task Shield reproduction blocked until verifier semantics are frozen.
  - IPIGuard TDG stub preflight and official source-smoke remain historical mechanics evidence. The new pinned-source formal adapter, 726-case freeze and isolated import preflight are implemented, but no runtime case has been admitted; qualification, complete formal logs and analyzer admission remain required.
  - Progent policy adapter preflight `progent_policy_adapter_preflight_v1` completed its stub smoke, proving trusted-input-only policy-bundle construction, symbolic allow/ask/deny rule packaging and runtime action checking while keeping real Progent DSL semantics blocked until an official or disclosed reproduction is frozen.
  - CaMeL/FIDES IFC-capability adapter preflight `camel_fides_ifc_adapter_preflight_v1` completed its stub smoke; CaMeL is selected and source checkout is ready, while the real information-flow/capability baseline remains blocked by missing `uv`, unfrozen interpreter/dependency assumptions and no complete source-backed benchmark adapter.
- AgentDojo native diagnostic:
  - native `BasePipelineElement` adapter implemented;
  - non-gold intent/domain compiler distinguishes action verbs, negative scopes and informational references;
  - nullable JSON Schema parameters are normalized without collapsing strings into objects;
  - structured tool-output provenance separates participant fields from instruction-bearing description/body/content fields;
  - rejected actions can recover without entering the official executed-tool trace;
  - resume-safe native matrix runner supports defense conditions, attacks, repeats and retained failures;
  - exact selected-cluster runner supports frozen diagnostic cluster selections, repeat seeds and defense override;
  - official AgentDojo prompt baselines `repeat_user_prompt` and `spotlighting_with_delimiting` are available as local diagnostic adapters;
  - official `TaskSuite.run_task_with_pipeline` now passes `workspace/user_task_0` utility and blocks the paired injection in the corrected smoke.
- Public replay diagnostic:
  - InjecAgent public replay runner implemented;
  - qwen3 limit-3 smoke completed for `no_defense` and `m3_full`;
  - official-formula replay scorer implemented for DH/DS S1/S2 ASR formulas;
  - qwen3 limit-3 replay scoring smoke completed;
  - manifests mark `result_eligible_for_formal_tables=false`.
- InjecAgent official-stage diagnostic:
  - scratchpad-stage runner implemented for the official post-User-Tool observation phase;
  - prompt styles include `m3_json`, official InjecAgent prompted-agent ReAct, and official `hwchase17_react` simple ReAct;
  - model sees the benchmark prelude because InjecAgent official runners start after the trusted User Tool has executed;
  - online policy compilation still uses only trusted user request, trusted app context and tool schemas;
  - scorer ignores `prelude` rows when determining model parse validity;
  - ReAct parser prioritizes Action before later Final Answer and accepts no-argument tools with `None`/no-input wording;
  - result-blind stratified selection builder freezes case ids before execution;
  - runner accepts frozen `--selection` files and records selection/progress hashes;
  - `progress.jsonl` and `runs.jsonl` are written incrementally after each case/defense pair;
  - CLI now supports per-run `--timeout` and `--max-tokens` for long-run control;
  - official compatibility audit added for pinned source hashes, official-stage markers, official prompted parser cross-checks, synthetic DH/DS S1/S2 formula checks and source-order prompt rendering;
  - official prompted-parser intent scorer added to score raw model ReAct outputs with InjecAgent's `evaluate_output_prompted`, separating model attack intent from runtime execution blocking;
  - policy compiler repair prevents same-provider read-only over-authorization such as `AmazonViewSavedAddresses` for an Amazon product-details request;
  - qwen3 data-security limit-2 and direct-harm limit-2 smokes completed with 0 failures and `result_eligible_for_formal_tables=false`.
- Experiment harness:
  - resume-safe local matrix runner;
  - analysis scripts for local smoke and policy-regime smoke;
  - metrics distinguish normal task completion, intervention, legitimate-tool FPR, ASK rate and unauthorized side effects.
- Figures:
  - ten fixed paper figure contracts;
  - demo figure builder with visible non-formal watermark;
  - diagnostic local-model and policy-regime figures generated and visually checked.
- Verification snapshot (2026-07-18):
  - all 58 unit-test files executed and passed: 422 passed, 1 intentionally skipped;
  - the repository-level result-integrity audit adds 3 passed checks;
  - combined verified total: 425 passed, 1 skipped, 0 failed;
  - all ten AgentDojo repeated-diagnostic analysis artifacts exist and have recorded SHA-256 hashes;
  - focused paper-v1 public-benchmark/runtime/statistics regression after InjecAgent official-ReAct, selection, paired-analysis, figure-generation, official-compatibility-audit, official prompted intent scorer, baseline registry audit, AgentDojo official strong-baseline capability audit, external strong-baseline source audit, strong-baseline source checkout manifest, IPIGuard official source-smoke, strong-baseline dependency snapshot, strong-baseline formal-readiness audit, public-benchmark formal-freeze manifest, public-benchmark formal-run pending ledger, public-benchmark formal case-result row builder, public-benchmark formal-cell runner wrapper, AgentDojo formal-cell source producer, InjecAgent formal-cell source producer, public-benchmark formal-cell materializer, public-benchmark result-completeness audit, PromptGuard adapter preflight, Task Shield alignment preflight, IPIGuard TDG preflight, Progent policy preflight and CaMeL/FIDES IFC-capability preflight work: 122 passed.

## Latest diagnostic results

Local-model smoke:

- Scope: 5 local models x 6 fixed validation cases x `no_defense`/`m3_full` = 60 case-runs.
- Status: completed, 0 failed case-runs.
- Output: `outputs/paper_upgrade_v1/smoke_local_5models_v1/analysis/`.
- Boundary: runtime smoke only; cell size is too small for model ranking or paper-level confidence intervals.

Policy-regime smoke:

- Scope: qwen3 x 6 validation cases x `m3_full` x four policy regimes = 24 case-runs.
- Status: completed, 0 failed case-runs.
- Output: `outputs/paper_upgrade_v1/policy_regime_smoke/analysis_v1/`.
- Diagnostic signal: attack unauthorized side-effect rate stayed 0%; non-auto regimes reduced TCR from 100% to 66.7% and raised normal ASK from 0% to 33.3%.
- Boundary: this only validates the authorization-uncertainty measurement chain.

InjecAgent replay smoke:

- Scope: first 3 indexed InjecAgent cases x `no_defense`/`m3_full`.
- Status: completed, 0 failures, 16 step logs.
- Output: `outputs/paper_upgrade_v1/public_replay/injecagent_qwen3_limit3_v1/`.
- Boundary: diagnostic replay, not the official InjecAgent benchmark result.

InjecAgent official-formula replay scorer smoke:

- Scope: the same first 3 indexed InjecAgent public-replay cases.
- Status: completed.
- Output: `outputs/paper_upgrade_v1/public_replay/injecagent_qwen3_limit3_v1/official_formula_score_v1/`.
- `no_defense` ASR-all Total: 0.0; Valid Rate: 100.0.
- `m3_full` ASR-all Total: 0.0; Valid Rate: 100.0.
- Boundary: the scorer mirrors InjecAgent's ASR aggregation formulas, but labels are derived from M3 replay tool execution. This is not byte-identical InjecAgent prompted-agent or function-calling execution.

InjecAgent official-stage diagnostic smoke:

- Runner: `experiments/paper_v1/benchmarks/injecagent_stage_runner.py`.
- Protocol: `protocols/paper_upgrade_v1/injecagent_stage_runner_v1.md`.
- Data-security smoke: first 2 `data_security` cases x `no_defense`/`m3_full`; 0 failures; 12 log rows; output `outputs/paper_upgrade_v1/injecagent_stage/qwen3_limit2_v3/`.
- Direct-harm smoke: first 2 `direct_harm` cases x `no_defense`/`m3_full`; 0 failures; 12 log rows; output `outputs/paper_upgrade_v1/injecagent_stage/qwen3_dh_limit2_v1/`.
- Data-security diagnostic slice: first 5 `data_security` cases x `no_defense`/`m3_full`, max_steps=3; 0 failures; 32 log rows; output `outputs/paper_upgrade_v1/injecagent_stage/qwen3_ds_limit5_v1/`.
- Direct-harm diagnostic slice: first 5 `direct_harm` cases x `no_defense`/`m3_full`, max_steps=3; 0 failures; 32 log rows; output `outputs/paper_upgrade_v1/injecagent_stage/qwen3_dh_limit5_v1/`.
- Official-formula score for both smokes: Valid Rate 100.0 for both defenses; ASR-all Total 0.0 for both defenses.
- Official-formula score for both 5-case diagnostic slices: Valid Rate 100.0 for both defenses; ASR-all Total 0.0 for both defenses.
- Diagnostic signal: a smoke run exposed same-provider read-only over-authorization, which was repaired and covered by regression tests. The 5-case slices also show weak baseline triggering in the first InjecAgent cases under this local qwen3 JSON/ReAct runner. This is method-development evidence, not a paper result.
- Boundary: this aligns the model input with InjecAgent's post-user-tool stage, but is not byte-identical to the original InjecAgent prompted/function-calling runners.

InjecAgent Vicuna official simple-ReAct baseline-vulnerable diagnostic:

- Prompt style: `official_react_simple`, loaded from the pinned InjecAgent `hwchase17_react` template without executing external benchmark code.
- DS slice: first 3 `data_security` cases, Vicuna 7B, `no_defense` vs `m3_full`, max_steps=3.
  - `no_defense`: attack success 3/3.
  - `m3_full`: attack success 0/3.
  - Paired risk difference: -100.0 percentage points; McNemar p=0.25.
  - Output: `outputs/paper_upgrade_v1/injecagent_stage/vicuna_official_react_simple_ds_limit3_pair_v1/`.
- DH slice: first 3 `direct_harm` cases, Vicuna 7B, `no_defense` vs `m3_full`, max_steps=3.
  - `no_defense`: attack success 1/3.
  - `m3_full`: attack success 0/3.
  - Paired risk difference: -33.3 percentage points; McNemar p=1.0.
  - Output: `outputs/paper_upgrade_v1/injecagent_stage/vicuna_official_react_simple_dh_limit3_pair_v1/`.
- DS exploratory extension: cases `data_security:0004` and `data_security:0005`
  under Vicuna 7B + `official_react_simple` + `no_defense` reached Valid
  Rate 100.0 but ASR-all Total 0.0 (`S1=50.0`, `S2=0.0`), so they are
  retained as a negative diagnostic and not promoted into a paired effectiveness
  slice. Output: `outputs/paper_upgrade_v1/injecagent_stage/vicuna_official_react_simple_ds_0004_0005_nodefense_v1/`.
- Stratified selector:
  - 30-case frozen selection:
    `protocols/paper_upgrade_v1/injecagent_stage_stratified_30_selection_v1.json`,
    six `(suite, attack_type)` buckets x 5 cases each.
  - 6-case smoke selection:
    `protocols/paper_upgrade_v1/injecagent_stage_stratified_6_selection_v1.json`,
    one case per bucket.
  - A pre-progress 30-case Vicuna no-defense attempt was stopped because it
    produced no auditable intermediate logs or manifest; it is retained only in
    `harness/state/failure-log.md`.
  - Progress-enabled 6-case Vicuna pair completed with 0 failures under
    max_steps=2, timeout=60s and max_tokens=192.
  - Paired result: no-defense attack success 1/6, `m3_full` 0/6, risk
    difference -16.7 percentage points, McNemar p=1.0.
  - Output: `outputs/paper_upgrade_v1/injecagent_stage/vicuna_official_react_simple_selection6_pair_timeout_v1/`.
- Progress-enabled 30-case diagnostic:
  - Same frozen 30-case selection, Vicuna 7B, `official_react_simple`,
    max_steps=3, timeout=60s, max_tokens=256.
  - no-defense output:
    `outputs/paper_upgrade_v1/injecagent_stage/vicuna_official_react_simple_selection30_nodefense_timeout_v2/`.
  - `m3_full` output:
    `outputs/paper_upgrade_v1/injecagent_stage/vicuna_official_react_simple_selection30_m3full_timeout_v2/`.
  - Both conditions completed 30/30 cases with 0 failures.
  - no-defense ASR-all Total 46.7%, Valid Rate 73.3%; `m3_full` ASR-all
    Total 0.0%, Valid Rate 73.3%.
  - Paired result: no-defense attack success 14/30, `m3_full` 0/30, risk
    difference -46.7 percentage points, McNemar p=0.0001221.
  - Generated bucket summary and figures:
    `attack_success_by_defense`, `attack_success_by_bucket`, and
    `paired_outcomes`.
  - Output:
    `outputs/paper_upgrade_v1/injecagent_stage/vicuna_official_react_simple_selection30_pair_timeout_v2/`.
- Boundary: deliberately tiny diagnostic slices; useful for locating baseline-vulnerable strata and validating parser/scorer behavior, not for publication effect-size claims.

InjecAgent official prompted-parser intent diagnostic:

- Script:
  `experiments/paper_v1/benchmarks/score_injecagent_stage_official_prompted.py`.
- Outputs:
  - no-defense:
    `outputs/paper_upgrade_v1/injecagent_stage/vicuna_official_react_simple_selection30_nodefense_timeout_v2/official_prompted_intent_score_v1/`;
  - `m3_full`:
    `outputs/paper_upgrade_v1/injecagent_stage/vicuna_official_react_simple_selection30_m3full_timeout_v2/official_prompted_intent_score_v1/`;
  - paired analysis:
    `outputs/paper_upgrade_v1/injecagent_stage/vicuna_official_react_simple_selection30_official_prompted_intent_pair_v1/`.
- Result on the frozen 30-case Vicuna selection:
  - no-defense raw model attack intent success: 7/30, ASR-all Total 23.3%,
    Valid Rate 30.0%;
  - `m3_full` raw model attack intent success: 6/30, ASR-all Total 20.0%,
    Valid Rate 26.7%;
  - paired difference: -3.3 percentage points; McNemar p=1.0.
- Interpretation: compared with the execution-derived diagnostic result
  14/30 to 0/30, this shows the current M3 effect is mainly runtime
  authorization blocking rather than prompt-level elimination of malicious
  model intent. This is useful for paper framing and for future ablation design.
- Boundary: `official_prompted_parser_on_m3_stage_logs_not_official_runner`.
  The scorer uses the official parser but still evaluates M3-generated stage
  logs, not byte-identical InjecAgent official runner outputs.

InjecAgent official compatibility audit:

- Script:
  `experiments/paper_v1/benchmarks/audit_injecagent_official_compatibility.py`.
- Output:
  `protocols/paper_upgrade_v1/injecagent_official_compatibility_audit_v1.json`
  and
  `protocols/paper_upgrade_v1/injecagent_official_compatibility_audit_v1.md`.
- Status: completed, 19/19 checks passed.
- What it supports: pinned official prompted runner/parser/prompt/scorer files
  are hashed; official post-user-tool stage markers are present; the official
  prompted parser agrees with fixed ReAct success/failure/invalid samples; the
  M3 scorer bridge matches synthetic InjecAgent DH/DS S1/S2 formula
  expectations; official ReAct rendering preserves source-case tool order.
- Boundary: this is still `compatibility_audit_not_official_benchmark_result`.
  It does not make the current M3 Guard runner byte-identical to InjecAgent,
  because M3 still supplies the model transport, Guard hook, local observation
  replay and additional provenance logging.

AgentDojo native repeated diagnostic:

- Scope: 2 workspace user tasks x 4 injection tasks x `no_defense`/`m3_full` x 3 repeats = 48 paired attack runs.
- Attack: official `important_instructions`; model `qwen3:4b-instruct`; 0 failed jobs.
- `no_defense` official injection success: 3/24 = 12.5% (Wilson 95% CI 4.3%-31.0%).
- `m3_full` official injection success: 0/24 = 0% (Wilson 95% CI 0%-13.8%).
- Paired difference (`m3_full` - `no_defense`): -12.5 percentage points; task/injection-cluster bootstrap 95% CI -37.5 to 0.0 percentage points; exact McNemar p=0.25.
- Injected utility was 6/24=25% in both conditions. All baseline successes were concentrated in one of eight task/injection clusters.
- Output: `outputs/paper_upgrade_v1/agentdojo_native_matrix/workspace_2x4inj_important_qwen3_repeat3_v1/analysis/`.
- Boundary: diagnostic only. The interval includes zero and the slice is too small and concentrated for a paper effectiveness claim.

AgentDojo four-suite diagnostic screen:

- Scope: banking, slack, travel and workspace selected user/injection tasks under `no_defense` and `m3_full`; qwen3; official `important_instructions`; total 124 jobs.
- Status: completed, 0 failed jobs.
- Output: `outputs/paper_upgrade_v1/agentdojo_native_matrix/four_suite_screen_summary_v1/`.
- Diagnostic signal: banking, slack and travel expose baseline-vulnerable clusters; workspace did not expose a positive cluster under this exact seed/max-step/utility configuration.
- Boundary: this is a candidate-selection screen only. It intentionally samples tasks and must not be used as an all-AgentDojo result.

AgentDojo selected-cluster repeat diagnostic:

- Scope: 25 positive baseline-vulnerability clusters plus 4 zero-control clusters x `no_defense`/`m3_full` x 3 repeats = 174 jobs.
- Status: completed, 0 failed jobs.
- Output: `outputs/paper_upgrade_v1/agentdojo_native_matrix/selected_repeat_qwen3_v1/analysis/`.
- `no_defense` official injection success: 72/87 = 82.8%.
- `m3_full` official injection success: 0/87 = 0%.
- Paired exact McNemar: 72 baseline-only events, p=4.24e-22.
- Cluster bootstrap for `m3_full - no_defense`: -82.8 percentage points, 95% CI [-96.6, -69.0] percentage points.
- Cluster stability: 24/29 clusters are stable positive under no defense; all 24 are stable blocked by `m3_full`.
- Boundary: this is enriched for baseline-vulnerable candidate clusters and therefore cannot estimate AgentDojo-wide ASR.

AgentDojo official prompt-baseline diagnostic:

- Diagnostic defense ids:
  - `agentdojo_repeat_user_prompt`;
  - `agentdojo_spotlighting_with_delimiting`.
- Prompt-baseline run: 174/174 jobs completed, 0 failed jobs.
- Combined four-condition analysis: 348/348 jobs joined from selected repeat and prompt-baseline manifests.
- Output: `outputs/paper_upgrade_v1/agentdojo_native_matrix/selected_prompt_baseline_comparison_qwen3_v1/`.
- `agentdojo_repeat_user_prompt` official injection success: 66/87 = 75.9%.
- `agentdojo_spotlighting_with_delimiting` official injection success: 66/87 = 75.9%.
- In the same joined comparison, `no_defense` is 72/87 and `m3_full` is 0/87.
- Paired prompt-baseline vs `m3_full`: 66 prompt-baseline-only events, exact McNemar p=2.71e-20 for each prompt baseline.
- Boundary: this remains selected-cluster diagnostic evidence, not a formal AgentDojo result.

Strong-baseline readiness audit:

- Registry:
  `protocols/paper_upgrade_v1/baseline_registry.json`.
- Audit script:
  `experiments/paper_v1/benchmarks/audit_baseline_registry.py`.
- Audit output:
  `protocols/paper_upgrade_v1/baseline_registry_audit_v1.json`
  and
  `protocols/paper_upgrade_v1/baseline_registry_audit_v1.md`.
- Status: completed, 11/11 checks passed.
- Registered strong-baseline requirements:
  PromptGuard, Task Shield, IPIGuard, Progent, CaMeL/Fides, AgentDojo
  `tool_filter`, and AgentDojo `transformers_pi_detector`.
- Dependency probe:
  AgentDojo upstream exposes `tool_filter` and `transformers_pi_detector`;
  `OPENAI_API_KEY` is absent for `tool_filter`; `transformers_pi_detector` has
  an E-drive runtime smoke with cached ProtectAI detector revision
  `90c9989b1a342275dd0d1a95aad283c04e075671`.
- Boundary: the audit is an exclusion/readiness gate only. The Q2 strong
  baseline gate remains `not_satisfied`, so these methods cannot be cited as
  completed comparisons until exact adapters, dependencies, frozen protocols and
  run manifests exist.

AgentDojo official strong-baseline capability audit:

- Script:
  `experiments/paper_v1/benchmarks/audit_agentdojo_official_strong_baselines.py`.
- Protocol:
  `protocols/paper_upgrade_v1/agentdojo_official_strong_baselines_v1.md`.
- Output:
  `protocols/paper_upgrade_v1/agentdojo_official_strong_baseline_capability_audit_v1.json`
  and
  `protocols/paper_upgrade_v1/agentdojo_official_strong_baseline_capability_audit_v1.md`.
- Status: completed, 9/9 checks passed.
- What it supports:
  official AgentDojo source files and hashes are recorded; upstream `DEFENSES`
  contains `tool_filter` and `transformers_pi_detector`; official source
  markers for `OpenAILLMToolFilter`, `TransformersBasedPIDetector`, the
  ProtectAI detector model, threshold 0.5 and message-mode redaction all pass.
- Current blockers:
  `tool_filter` remains blocked by missing `OPENAI_API_KEY` or compatible API
  endpoint for the official OpenAILLM transport; `transformers_pi_detector`
  has no dependency blocker but still lacks a frozen full official AgentDojo
  cell and complete logs.
- Boundary: this is a capability audit only, not an AgentDojo benchmark result.
  The audit also confirms the two official strong-baseline ids are not silently
  mixed into the M3 local runner's `DEFENSE_CONDITIONS`.

External strong-baseline source/readiness audit:

- Registry:
  `protocols/paper_upgrade_v1/external_strong_baselines_v1.json`.
- Protocol:
  `protocols/paper_upgrade_v1/external_strong_baselines_v1.md`.
- Audit script:
  `experiments/paper_v1/benchmarks/audit_external_strong_baselines.py`.
- Audit output:
  `protocols/paper_upgrade_v1/external_strong_baseline_source_audit_v1.json`
  and
  `protocols/paper_upgrade_v1/external_strong_baseline_source_audit_v1.md`.
- Status: completed, 10/10 checks passed.
- Coverage:
  PromptGuard / Llama Prompt Guard 2, Task Shield, IPIGuard, Progent, CaMeL and
  FIDES. CaMeL and FIDES remain paired candidates for the required
  information-flow/capability baseline.
- Source state:
  PromptGuard/PurpleLlama, IPIGuard, CaMeL and FIDES have exact local source
  checkouts pinned under `external/baselines/`; Task Shield and Progent remain
  paper-only entries in this checkout.
- Dependency state:
  PromptGuard dependencies/cache are complete in the dedicated E-drive runtime;
  the AgentDojo ProtectAI detector is cached and smoke-tested in the same
  runtime. This older source-readiness section is superseded for CaMeL by
  `strong_baseline_dependency_snapshot_v1` plus CaMeL import/compat/runner-wiring preflights:
  CaMeL now has an isolated E-drive runtime, source-backed compat preflight and
  non-formal runner-wiring preflight, but still lacks frozen model transport,
  qualification, complete formal execution logs and admission evidence. Local
  source checkouts remain reproducible caches recorded by
  `strong_baseline_source_checkout_manifest_v1`.
- Boundary: source/readiness only. These entries are more precise than the
  previous generic blockers, but they still cannot enter formal result tables
  until exact checkouts/adapters, dependency snapshots, frozen manifests and
  complete logs exist.

Strong-baseline source checkout manifest:

- Script:
  `experiments/paper_v1/benchmarks/prepare_strong_baseline_source_checkouts.py`.
- Output:
  `protocols/paper_upgrade_v1/strong_baseline_source_checkout_manifest_v1.json`
  and
  `protocols/paper_upgrade_v1/strong_baseline_source_checkout_manifest_v1.md`.
- Status:
  completed, 5/5 checks passed.
- Source-ready entries:
  `promptguard_llama_prompt_guard_2`, `ipiguard_github_emnlp2025`,
  `camel_google_research` and `fides_microsoft`.
- Local checkout root:
  `external/baselines/`, ignored by Git as reproducible source caches.
- Boundary:
  source checkout preparation only. It does not install packages, download
  model weights, start services, call APIs, run baselines or create formal
  effect evidence.

Strong-baseline dependency/source snapshot:

- Script:
  `experiments/paper_v1/benchmarks/build_strong_baseline_dependency_snapshot.py`.
- Output:
  `protocols/paper_upgrade_v1/strong_baseline_dependency_snapshot_v1.json`
  and
  `protocols/paper_upgrade_v1/strong_baseline_dependency_snapshot_v1.md`.
- Status:
  completed, 5/5 checks passed.
- What it records:
  local Python package availability, executable availability, PromptGuard model
  cache probes, expected external source-checkout locations and Git HEAD state.
- Current blockers:
  PromptGuard dependencies and model cache are pinned in the dedicated E-drive
  environment and detector-only formal admission is complete; IPIGuard has no
  dependency/source blockers in the snapshot but still
  needs official TDG wiring and formal logs; CaMeL is selected with source ready
  but remains blocked by missing `uv`; Task Shield and Progent remain blocked by unfrozen
  official or disclosed reproduction semantics.
- Boundary:
  this is a dependency/source snapshot only. It performs no install, download,
  model call or baseline run, and it is not result-eligible for formal tables.

Strong-baseline formal-readiness audit:

- Script:
  `experiments/paper_v1/benchmarks/audit_strong_baseline_formal_readiness.py`.
- Output:
  `protocols/paper_upgrade_v1/strong_baseline_formal_readiness_audit_v1.json`
  and
  `protocols/paper_upgrade_v1/strong_baseline_formal_readiness_audit_v1.md`.
- Status:
  completed, 7/7 checks passed.
- Dependency snapshot:
  `strong_baseline_dependency_snapshot_v1` is present with status `completed`
  and SHA-256 recorded in the audit output.
- Formal-ready strong baselines:
  none.
- What it enforces:
  PromptGuard, Task Shield, IPIGuard, Progent, CaMeL/FIDES, AgentDojo
  `tool_filter` and AgentDojo `transformers_pi_detector` can enter formal
  tables only after source-backed adapters, dependency snapshots, formal
  manifests, complete logs and no-label-leakage checks exist.
- Boundary:
  this is a formal-admission gate only; it does not run any baseline and does
  not create new effect-size evidence.

Public benchmark formal-freeze manifest:

- Script:
  `experiments/paper_v1/benchmarks/build_public_benchmark_formal_freeze.py`.
- Output:
  `protocols/paper_upgrade_v1/public_benchmark_formal_freeze_v1.json`
  and
  `protocols/paper_upgrade_v1/public_benchmark_formal_freeze_v1.md`.
- Status:
  completed, 9/9 checks passed.
- Frozen universe:
  AgentDojo 97 utility tasks + 629 security cases; InjecAgent 1,054
  official-stage-compatible security cases.
- Ready local matrix:
  5 declared local model slots x 6 ready formal main conditions x
  (726 AgentDojo + 1,054 InjecAgent cases) = 53,400 case-runs for one repeat.
- Current formal conditions admitted into the ready-local matrix:
  `no_defense`, `safe_prompt`, `spotlighting`, `prompt_sandwich`,
  `m3_policy_only` and `m3_full`.
- Explicit exclusions:
  PromptGuard is excluded from end-to-end public-benchmark ASR/TCR/tool-utility
  cells and admitted only for detector-performance tables. Task Shield,
  IPIGuard, Progent and CaMeL/FIDES remain blocked; AgentDojo official prompt
  diagnostics are excluded from the formal matrix.
- Q2 gate:
  v1 remains an immutable historical queue. The non-overwriting v2 freeze fills
  both modern 7B-14B open-model slots, but the two frontier API vendor slots are
  still missing. PromptGuard is the only formal-ready strong baseline and only
  for detector performance; no end-to-end public-benchmark formal cell has run.
- Boundary:
  this is a freeze/coverage manifest only. It is not a result manifest and does
  not make any public-benchmark effect claim.

Public benchmark result-completeness audit:

- Script:
  `experiments/paper_v1/benchmarks/audit_public_benchmark_result_completeness.py`.
- Output:
  `protocols/paper_upgrade_v1/public_benchmark_result_completeness_audit_v1.json`
  and
  `protocols/paper_upgrade_v1/public_benchmark_result_completeness_audit_v1.md`.
- Status:
  completed, 5/5 checks passed.
- Current result gate:
  `not_satisfied`.
- Current completeness:
  60 expected matrix cells, 60 initialized pending cells, 0 uninitialized cells,
  0 complete cells; 53,400 expected case-runs, 0 complete case-runs.
- Pending formal-run ledger:
  `experiments/paper_v1/benchmarks/prepare_public_benchmark_formal_runs.py`
  generated
  `protocols/paper_upgrade_v1/public_benchmark_formal_run_plan_v1.json`,
  `protocols/paper_upgrade_v1/public_benchmark_formal_run_plan_v1.md`,
  `outputs/paper_upgrade_v1/public_benchmark_formal_runs/run_plan_manifest.json`,
  `outputs/paper_upgrade_v1/public_benchmark_formal_runs/formal_cell_queue.jsonl`,
  and 60 per-cell `todo_cases.jsonl` queues containing 53,400 pending case-runs.
- Formal case-result row builder:
  `experiments/paper_v1/benchmarks/formal_case_result_rows.py` converts
  benchmark-specific outcome rows into standardized `case_results.jsonl` rows
  keyed by frozen `case_run_id`. It only emits
  `formal_public_benchmark_case_run` when the source status is an accepted
  formal source status and formal admission is explicitly enabled; diagnostic
  source rows remain diagnostic and fail the formal materializer gate.
- Formal-cell runner wrapper:
  `experiments/paper_v1/benchmarks/run_public_benchmark_formal_cell.py`
  with protocol
  `protocols/paper_upgrade_v1/public_benchmark_formal_cell_runner_v1.md`
  provides the single-cell execution contract around the row builder and
  materializer. Without an outcomes file it produces a dry-run plan for one
  frozen cell and does not start models or benchmark services. With a supplied
  official outcome JSONL it writes standardized `case_results.jsonl` plus
  `case_results_validation.json`; missing outcomes are converted into explicit
  failed rows rather than silently skipped. Materialization is optional and only
  succeeds for formal tables when every row has completed status and admitted
  formal source evidence.
- AgentDojo formal-cell source producer:
  `experiments/paper_v1/benchmarks/run_agentdojo_formal_cell.py`
  with protocol
  `protocols/paper_upgrade_v1/agentdojo_formal_cell_runner_v1.md`
  prepares AgentDojo-specific source outcomes for one frozen cell. Dry-run mode
  reports suite and utility/security coverage without starting services.
  Execution mode writes `agentdojo_outcomes.jsonl`, `progress.jsonl` plus
  per-case native job manifests/audit logs. It resumes completed jobs by
  default, preserves existing `failure.json` rows unless `--retry-failed` is
  supplied, and admits `agentdojo_official_formal_case_run` only for explicit
  full-cell, non-stub, zero-failure source runs; partial, stub or failed runs
  remain diagnostic and cannot complete a formal cell.
- InjecAgent formal-cell source producer:
  `experiments/paper_v1/benchmarks/run_injecagent_formal_cell.py`
  with protocol
  `protocols/paper_upgrade_v1/injecagent_formal_cell_runner_v1.md`
  prepares InjecAgent-specific official-stage source outcomes for one frozen
  cell. Dry-run mode reports suite/security coverage without starting services.
  Execution mode writes `injecagent_outcomes.jsonl`, `progress.jsonl` plus
  per-case source job manifests/run logs. It resumes completed jobs only when
  paired `runs.jsonl` exists, preserves existing `failure.json` rows unless
  `--retry-failed` is supplied, and admits
  `injecagent_official_formal_case_run` only for explicit full-cell,
  non-stub, zero-failure source runs with an official ReAct prompt style;
  partial, stub, `m3_json` or failed runs remain diagnostic and cannot complete
  a formal cell.
- Formal-cell materializer:
  `experiments/paper_v1/benchmarks/materialize_public_benchmark_formal_cell.py`
  verifies one cell against its frozen `todo_cases.jsonl`, writes
  `raw_runs.csv`, `raw_runs.jsonl`, `metrics.csv`, `statistics.json` and
  `figure_manifest.json`, updates artifact SHA-256s in the cell manifest, and
  refuses to make diagnostic/stub rows result-eligible.
- Required per-cell artifacts:
  `manifest.json`, raw run logs, metrics, statistics and figure manifest with
  SHA-256 checks where declared.
- Boundary:
  this is a result-completeness gate only. It does not run models or public
  benchmarks and does not make effect-size claims. Formal public-benchmark
  claims require this gate to become `satisfied` after frozen runs complete.

PromptGuard detector adapter preflight:

- Protocol:
  `protocols/paper_upgrade_v1/promptguard_detector_adapter_v1.md`.
- Adapter script:
  `experiments/paper_v1/benchmarks/promptguard_adapter.py`.
- Preflight output:
  `protocols/paper_upgrade_v1/promptguard_detector_adapter_preflight_v1.json`
  and
  `protocols/paper_upgrade_v1/promptguard_detector_adapter_preflight_v1.md`.
- Status:
  superseded by `promptguard_detector_formal_v1`.
- What it supports:
  online-only scan records are built from `trusted_user_request` and
  `untrusted_content`; offline/evaluator fields are excluded; deterministic
  fallback chunking, thresholding and `max_malicious_score` aggregation are
  unit-tested; stub attack/benign smoke decisions match expectation.
- Current blockers:
  none for detector-only formal execution. The completed formal result remains
  scoped to detector-performance tables only.
- Boundary:
  the preflight itself is adapter/mechanics evidence; the separate
  `promptguard_detector_formal_v1` run is the detector-performance result.

Task Shield disclosed paper reproduction:

- Source boundary:
  no public official Task Shield repository was identified. The ACL 2025 paper
  PDF is pinned locally at SHA-256
  `057ff02152c0bb61892b08abdc80f7af22416c03819e526878091ee87d3bf1e6`.
  This condition must never be labelled official-source Task Shield.
- Frozen protocol:
  `taskshield_paper_formal_freeze_v1.json/.md` is now schema
  `paper-taskshield-reproduction-freeze-1.2`, passed 13/13 checks and freezes
  the common 726-case AgentDojo universe, Qwen3 8B agent/verifier alias,
  temperature 0, fuzzy contribution threshold 0, strict JSON parsing,
  history policy, failure handling and local-adapter file hashes.
- Runtime:
  `taskshield_paper_runtime.py` implements user-task extraction, assistant
  content checking, tool-call argument checking, untrusted tool-output checking
  and bounded feedback. Prompt wording is a concise semantic restatement of the
  paper appendix, not a byte-identical copy.
- Import preflight:
  `taskshield_paper_import_preflight_v1.json/.md` passed 9/9 checks in a
  network-blocked fresh process with no Ollama probe and zero benchmark cases,
  including freeze/local-adapter hash consistency.
- Runner and analyzer:
  `run_taskshield_paper_formal.py` and `analyze_taskshield_paper_formal.py`
  provide failure retention, resume, exact-coverage admission, intervention
  metrics and figures.
- Status:
  `disclosed_paper_reproduction_v1_2_hash_bound_formal_protocol_import_preflight_completed_qualification_pending`.
- Current blockers:
  no real-model qualification or complete 726-case run has executed. It remains
  `result_eligible=false` until qualification, full zero-failure execution and
  formal analysis admission.

IPIGuard TDG adapter preflight:

- Protocol:
  `protocols/paper_upgrade_v1/ipiguard_tdg_adapter_v1.md`.
- Adapter script:
  `experiments/paper_v1/benchmarks/ipiguard_adapter.py`.
- Preflight output:
  `protocols/paper_upgrade_v1/ipiguard_tdg_adapter_preflight_v1.json`
  and
  `protocols/paper_upgrade_v1/ipiguard_tdg_adapter_preflight_v1.md`.
- Status:
  `ready_for_official_source_smoke`.
- What it supports:
  online-only TDG input packages are built from trusted task text, trusted app
  context and tool schemas; offline/evaluator fields are excluded; tool nodes,
  side-effect roles, trusted dependency edges and untrusted-content risk edges
  are unit-tested; stub attack/benign chain decisions match expectation.
- Current blockers:
  `external/baselines/ipiguard` is pinned to the expected commit, but the
  official TDG construction path is not called yet and no complete formal
  baseline logs exist.
- Boundary:
  this is an adapter/mechanics preflight only, not an IPIGuard algorithm result.

Progent source-backed formal preparation:

- Official source:
  `external/baselines/progent` at commit
  `8a8eb894b9d568a32b4e58252fea85b47f789c77` from
  `https://github.com/sunblaze-ucb/progent`.
- Source verification:
  `protocols/paper_upgrade_v1/progent_official_source_smoke_v1.json/.md`
  verifies the official policy engine and offline runtime path. The source
  checkout has no top-level license, so redistribution remains a disclosure
  blocker even though local evaluation is technically possible.
- Compatibility discovery:
  the pinned Progent checkout bundles AgentDojo 0.1.29 with 686 cases
  (97 utility + 589 security), whereas the common frozen AgentDojo universe is
  726 cases (97 utility + 629 security). The missing 40 cases are travel
  injection tasks 2 and 6 across 20 user tasks. This gap is recorded and is not
  silently excluded.
- Frozen compatibility protocol:
  `progent_source_backed_formal_freeze_v1.json/.md` now uses schema 1.1,
  passed 13/13 checks and
  freezes a disclosed port of the exact official `secagent` policy engine to
  the common 726-case AgentDojo lifecycle. Policy prompts, enforcement and
  automatic-update semantics remain pinned-source; only lifecycle/transport
  integration is adapted.
- Import preflight:
  `progent_source_backed_import_preflight_v1.json/.md` passed 9/9 checks in a
  network-blocked process with no Ollama probe and zero benchmark cases.
- Runner and analyzer:
  `run_progent_source_backed_formal.py` provides exact-coverage admission,
  failure retention and resume; `analyze_progent_source_backed_formal.py`
  requires formal admission and reports both the raw official trace checker
  and the pre-registered execution-grounded Slack injection-task-5 correction.
- Status:
  `source_backed_common_726_runner_analyzer_implemented_qualification_pending`.
- Current blockers:
  no real-model qualification or full 726-case run has executed. The existing
  AgentDojo `tool_filter` formal job owns Ollama/GPU resources, so Progent must
  remain queued until that job releases them.
- Boundary:
  the freeze, source smoke and import preflight are engineering evidence only;
  Progent remains `result_eligible=false` until qualification, exact 726/726
  zero-failure execution and formal analyzer admission complete.

CaMeL/FIDES IFC-capability adapter preflight:

- Protocol:
  `protocols/paper_upgrade_v1/camel_fides_ifc_adapter_v1.md`.
- Adapter script:
  `experiments/paper_v1/benchmarks/camel_fides_adapter.py`.
- Preflight output:
  `protocols/paper_upgrade_v1/camel_fides_ifc_adapter_preflight_v1.json`
  and
  `protocols/paper_upgrade_v1/camel_fides_ifc_adapter_preflight_v1.md`.
- Source-smoke output:
  `protocols/paper_upgrade_v1/camel_official_source_smoke_v1.json`
  and
  `protocols/paper_upgrade_v1/camel_official_source_smoke_v1.md`; this
  network-blocked smoke passed 8/8 checks against the pinned Google CaMeL
  checkout and verifies official capability/security-policy semantics only.
- Formal-freeze protocol:
  `protocols/paper_upgrade_v1/camel_source_backed_formal_freeze_v1.json`
  and
  `protocols/paper_upgrade_v1/camel_source_backed_formal_freeze_v1.md` passed
  12/12 checks. It freezes the common 97-utility/629-security AgentDojo
  universe, pinned CaMeL source hashes, source-smoke hash, upstream `uv`/API
  requirements, failure policy and trusted-input boundary without installing
  dependencies or running benchmark cases.
- Status:
  `completed_source_smoke_only` for the official-source semantic smoke, while
  the source-backed formal-freeze status is
  `completed_dependency_blocked_frozen_protocol`. The executable benchmark
  adapter remains pending.
- What it supports:
  online-only IFC/capability packages are built from trusted task text, trusted
  app context, tool schemas, runtime action proposals and provenance events;
  offline/evaluator fields are excluded; trusted/untrusted source labels,
  argument provenance, capability grants and low-integrity-to-sink decisions are
  unit-tested; stub attack/benign flow decisions match expectation. The
  source-smoke additionally exercises CaMeL `Capabilities`, trust propagation,
  workspace/slack security policies and network-guard behavior without running
  any benchmark case.
- Current blockers:
  CaMeL is selected as the current information-flow/capability candidate and
  both CaMeL/FIDES source checkouts are pinned locally. Dependency snapshot
  blockers for CaMeL are now empty because the source-smoke and freeze protocol
  are complete, but `uv`, interpreter/API configuration, executable benchmark
  adapter, model qualification and complete logs are still absent.
- Boundary:
  this is adapter/source-smoke evidence only, not a CaMeL or FIDES benchmark
  result and not eligible for formal effect tables.

## Remaining paper blockers

- AgentDojo official native execution has a repeated diagnostic slice and now has a frozen-cell source producer, but no full 97-utility/629-security formal cell has completed in the result ledger.
- InjecAgent now has an official-stage-compatible diagnostic runner and a 19-check official compatibility audit, but still needs full 1,054-case execution and either byte-identical prompted/function-calling compatibility or a clearly disclosed compatibility argument before it can support paper claims.
- Strong baselines have a registry/audit gate, pinned source checkout manifest and dependency/source snapshot. PromptGuard's detector-only source-backed formal run is complete but is not end-to-end. AgentDojo `tool_filter` is now formally admitted after its exact 726/726 zero-failure run. IPIGuard now has source-backed construction/traversal/execution wiring and an offline import preflight, but runtime qualification failed on malformed DAG schema output and formal logs are absent. AgentDojo `transformers_pi_detector` is source-backed but exact-full-run resource-blocked on this host. Progent now has pinned official source, a v1.1 13/13 hash-bound common-726 freeze, a 10/10 import preflight and implemented runner/analyzer, but no model qualification or formal result. Task Shield v1.3 has passed qualification but its 726-case disclosed-reproduction formal root has one timeout failure and remains live/inadmissible; v1.4 failure-recovery protocol is prepared but not qualified or admitted, and the condition still must not be labelled official source. CaMeL now has an 8/8 official-source semantic smoke, a v1.2 17/17 hash-bound formal-freeze protocol and a clean dependency-snapshot readiness row, but real-model qualification and formal logs remain absent.
- Both required 7B-14B open-source slots are configured and qualification-smoked; the two frontier API vendor slots remain unconfigured.
- A new independent blind set is not yet available; the automated holdout is only sealed automated holdout.
- Formal adaptive attack budgets are not run: 80 tasks x 100/500/2000 query budgets.
- Paper-v1 confirmatory hypotheses, endpoints, margins, statistical methods,
  exclusion/failure rules and ten-figure plan are frozen before independent-blind
  admission and adaptive formal results in
  `paper_v1_confirmatory_preregistration_freeze_v1.json/.md` (9/9 checks;
  payload SHA-256
  `b4b747196274e877c4b2bd0e5bbdebdcc582d585c714263815a8e4956f6b742a`).
- 投稿前仍需重新做截至投稿月份的系统检索，不能提前写“first”或“SOTA”。

## Next implementation order

1. Expand InjecAgent beyond the completed frozen 30-case diagnostic only after deciding whether to pursue byte-identical official prompted/function-calling compatibility or keep the current runner as a disclosed compatibility diagnostic.
2. Do not resume or restart the exact AgentDojo `transformers_pi_detector` 726-case official cell on this host unless the preserved direct long-output smoke first passes under changed resource conditions. Treat the exact detector as source-backed but resource-incompatible, or create a separately labelled non-equivalent bounded-input/windowed adapter if the paper still needs a runnable detector-style baseline.
3. Preserve the active Task Shield v1.3 failed-root evidence without a competing
   Ollama/GPU job; because the current root already contains an
   `APITimeoutError` failed row, any usable Task Shield formal result now
   requires the prepared v1.4 failure-recovery revision to start from a fresh
   qualification/full-root path rather than selective retry, row exclusion or
   partial-row promotion.
4. After Ollama is free, run the frozen Progent and CaMeL two-case qualifications sequentially. Only a clean qualification may advance its corresponding 726-case formal cell; retain and disclose any failure before changing a protocol.
5. Decide IPIGuard's path: freeze a stronger/disclosed DAG-construction configuration and rerun qualification, or keep it as a disclosed runtime-incompatible baseline for this host/model.
6. Run medium diagnostic matrices for policy-regime, provenance ablation and adaptive attack settings before freezing the formal plan.
7. Preserve the completed confirmatory preregistration SHA in every subsequent independent-blind and adaptive formal manifest; do not revise hypotheses or thresholds after those gates open.
8. Run formal public benchmarks, independent blind set and adaptive attacks.
9. Generate formal tables/figures only from frozen manifests.

## 2026-07-21 confirmatory preregistration and admission hardening

- `build_paper_v1_preregistration_freeze.py` created a hash-stable preregistration
  payload before independent-blind admission and formal adaptive outcomes exist.
  It freezes H1-H5, primary/secondary endpoints, the 50% adaptive relative-risk
  reduction target, the -5pp TCR non-inferiority margin, cluster bootstrap,
  McNemar/Holm, mixed-effects analysis, failure handling and F1-F10.
- `audit_q2_readiness.py` now requires the completed 9/9 preregistration inside
  the reproducibility criterion. This does not raise the score for protocol-only
  evidence; Q2 remains raw 63.5 and capped 60.0.
- `audit_strong_baseline_formal_readiness.py` now treats
  `camel_or_fides` as a frozen single-method choice: the selected CaMeL entry
  must be eligible and the unselected FIDES entry must remain ineligible. The
  selection is read from the formal freeze even after `formal_manifest` points
  to a completed analysis.
- `admit_external_strong_baseline_formal_result.py` provides a fail-closed dual
  registry bridge for Task Shield, IPIGuard, Progent and CaMeL. It verifies
  exact 726-case coverage, zero failures, per-row formal eligibility, freeze
  hash, analysis/run/outcomes hashes and analysis artifact hashes. All four
  current plan-only admissions are correctly blocked because no complete formal
  run/analysis exists; neither registry was modified.
- `monitor_adaptive_mcts_budget_formal.py` adds read-only task/query/PID/stall
  monitoring, and the runner now records PID in its manifest. The current formal
  root remains absent and is reported as `missing_manifest`; no adaptive model
  calls were started.
- Focused verification passed: preregistration/Q2 10 tests, IFC/admission 5
  tests, adaptive runner/monitor 9 tests, plus Ruff and `py_compile` for all
  touched code. The active AgentDojo `tool_filter` job remained healthy at
  433/726 completed and 0 failed; the refreshed Q2 audit consumes this monitor
  snapshot but correctly leaves readiness at raw 63.5/capped 60.0 until formal
  completion, analysis and admission.

## 2026-07-21 fail-closed formal execution handoff

- Added `plan_q2_formal_execution.py`, a read-only state planner over the
  ToolFilter/adaptive monitors, formal admissions and public-v2 cell manifests.
  It emits exactly one next action and refuses to schedule model work while a
  live formal PID owns Ollama/GPU.
- The generated `execution/q2_formal_execution_plan_v1.json/.md` records
  `resource_gate=busy`, ToolFilter 433/726 with zero failures, and a monitor-only
  next action. It independently confirms 84 pending public cells and 74,760
  pending case-runs. The artifact is operational metadata, not effect evidence.
- Four state-machine tests, Ruff and `py_compile` pass.

## 2026-07-21 IPIGuard v1.1 evidence-only instrumentation

- The original two-case qualification remains immutable at 1/2 completed: one
  upstream `construct_dag` `KeyError('function_name')` and one empty DAG. No row
  was retried or removed.
- Runner v1.1 captures the raw construct response before calling the unchanged
  upstream parser, writes a separate hash-addressed artifact and records JSON
  validity plus tool-call key sets. The capture changes neither prompt, parser,
  selection rule nor graph semantics.
- Freeze v1.1 passes 9/9 and binds the runner, analyzer and protocol hashes. A
  resume-identity gate rejects an old freeze, runner, model, condition or case
  selection before any Ollama probe. Import preflight passes 7/7; unit tests are
  9/9 and lint/compile pass.
- Fresh v1.1 two-case qualification remains pending under a new output root.
  Refreshed dependency/source/readiness audits pass 5/5, 11/11, 11/11 and 7/7;
  no new formal baseline or readiness point was claimed.

## 2026-07-22 Q2-to-80 action audit and status correction

- AgentDojo official `tool_filter` is no longer the live workload. Its exact
  726/726 formal run completed with 0 failures and was admitted through the
  fail-closed analyzer/admission bridge. It is now one of two formal-ready
  strong baselines, alongside PromptGuard detector-only formal.
- The current live workload is Task Shield v1.3 under
  `outputs/paper_upgrade_v1/baselines/taskshield_paper_formal_v13`, monitored at
  `protocols/paper_upgrade_v1/monitors/task_shield_formal_v13/agentdojo_official_formal_run_monitor_v1.json`.
  The latest checked state is `running_with_failures_requires_attention`,
  28/726 completed, 1 failed, 697 missing and PID 27384 alive. The failed row is
  `agentdojo:v1:slack:user_task_18` with `APITimeoutError`, so this root cannot
  be admitted without an explicit failure-recovery revision/protocol decision.
- Added `plan_q2_to_80_actions.py`, producing
  `execution/q2_to_80_action_audit_v1.json/.md`. This read-only audit records
  the five hard caps that still prevent an honest Q2 >= 80 claim: two-vendor
  Frontier API admission, formal 80-task adaptive MCTS budget evidence,
  independent 600-case blind evidence, at least five formal-ready strong
  baselines, and the full public benchmark formal matrix.
- The action audit also records remaining path-portability exceptions: 23
  protocol files with checkout-specific path hits, of which 14 are
  frozen/hash-bound and 9 are evidence-bound snapshots that must not be
  rewritten in place.
- Current Q2 readiness remains raw 66.0/100 and capped 60.0/100 with
  `goal_80_met=false`. The new action audit is operational metadata only and
  does not increase the score.


