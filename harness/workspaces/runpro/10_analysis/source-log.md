# Source Log

This code/data project uses the competition brief, official model registry pages and frozen local experiment evidence. External model pages support availability/environment descriptions only; formal effect claims come from local frozen RunLogs and statistics.

## Source

Official competition brief, competition organizer.

## Year

2026 workspace copy; publication year not stated in extracted text.

## URL Or File Path

`文档资料/比赛与规范/比赛要求/附件1：命题挑战赛赛题.pdf`

## What It Supports

Required attack scenarios, behavior-supervision prototype, mock tools, model-chain monitoring and alert/block display.

## Notes

Primary local requirements source. The current task does not modify the report/PPT materials stored beside it.

## Source

Qwen3 official Ollama model registry.

## Year

Accessed 2026-07-13.

## URL Or File Path

https://ollama.com/library/qwen3/tags

## What It Supports

Availability and local tag/size description for Qwen3 4B variants.

## Notes

Environment description only; formal model identity is recorded in manifests.

## Source

Phi-4 Mini official Ollama model registry.

## Year

Accessed 2026-07-13.

## URL Or File Path

https://ollama.com/library/phi4-mini

## What It Supports

Availability and local model description for Phi-4 Mini.

## Notes

Environment description only, not experiment outcomes.

## Source

Llama 3.2 official Ollama model registry.

## Year

Accessed 2026-07-13.

## URL Or File Path

https://ollama.com/library/llama3.2

## What It Supports

Availability and local model description for Llama 3.2 3B.

## Notes

Environment description only, not experiment outcomes.

## Source

Gemma 3 official Ollama model registry.

## Year

Accessed 2026-07-13.

## URL Or File Path

https://ollama.com/library/gemma3

## What It Supports

Availability and local model description for Gemma 3 4B.

## Notes

Environment description only, not experiment outcomes.

## Source

Frozen M3-PI Guard formal experiment program.

## Year

2026-07-14.

## URL Or File Path

`outputs/experiments/program_manifest_final_v3.json` and `outputs/experiments/blind_freeze_v3.json`

## What It Supports

Formal program scale, dataset/model/config identity, case counts, artifact paths and blind-freeze provenance.

## Notes

Primary source for result claims; registered bundle statistics and raw RunLogs provide supporting detail.

## Source

Ollama OpenAI compatibility documentation.

## Year

Accessed 2026-07-14.

## URL Or File Path

https://docs.ollama.com/api/openai-compatibility

## What It Supports

The supported OpenAI-compatible API surface and the documented Modelfile approach for configuring model context size.

## Notes

Used to design the corrected context experiment; it does not support any outcome claim.

## Source

Ollama running-models API documentation.

## Year

Accessed 2026-07-14.

## URL Or File Path

https://docs.ollama.com/api/ps

## What It Supports

Reading the effective `context_length` for loaded local models.

## Notes

The correction protocol will record this observation for every context alias.

## Source

Ollama usage accounting documentation.

## Year

Accessed 2026-07-14.

## URL Or File Path

https://docs.ollama.com/api/usage

## What It Supports

The `prompt_eval_count` field used to calibrate actual prompt workload rather than approximating tokens with whitespace splitting.

## Notes

Used for protocol validity checks, not model-effect claims.

## Source

Post-freeze E9/E14 context-design validity audit.

## Year

2026-07-14.

## URL Or File Path

`agent/audits/context_experiment_validity.json` and `agent/audits/context_experiment_validity.md`

## What It Supports

The decision to reopen E9 and E14: E9 target prompt lengths were not calibrated and E14 prompt workload was flat across declared context cells.

## Notes

This audit is non-causal, preserves the original bundles and intentionally returns `status=fail` until corrected runs exist.

## Source

Superseded Context Correction V2 r2 freeze and prompt proof.

## Year

2026-07-15.

## URL Or File Path

`protocols/context_correction_v2/freeze_r2.json` and `protocols/context_correction_v2/prompt_verification_r2.json`

## What It Supports

The r2 protocol identity, 42 frozen files, 29-test gate and calibrated 2K/4K/8K/16K prompt targets with native Ollama usage evidence. It documents the precursor workload, not the admitted execution revision.

## Notes

Freeze SHA-256 is `f40d8edba37c66fb5e982f27c05f8a0296c9296e344a007e5c9cd828190384c2`. r2 E14 later failed global run-key uniqueness and remains diagnostic-only; execution-r3 supersedes it.

## Source

Superseded E9 r2 formal evidence.

## Year

2026-07-15.

## URL Or File Path

`outputs/experiments/E9_context_correction_v2_r2/manifest.json`, `validity_checks.json`, `context_position.csv` and `statistics.json`

## What It Supports

120/120 formal first-step runs, 8/8 jobs, 15/15 validity checks, No Guard ASR 36/60 and full Guard ASR 0/60 under calibrated contexts.

## Notes

The E9 bundle is internally valid but was not paired with failed E14 r2. execution-r3 reran E9 from scratch; old v3 and r2 are not the active registered source.

## Source

Failed E14 r2 execution evidence.

## Year

2026-07-15.

## URL Or File Path

`outputs/experiments/E14_context_correction_v2_r2/manifest.json` and its completed `work/*/job_record.json` files

## What It Supports

The historical user-requested safe pause and the later completed r2 execution. Final semantic validation found cross-job run-key collisions despite 104/104 jobs.

## Notes

The completed r2 bundle is diagnostic-only and cannot support latency, throughput, overhead or GPU-memory claims. execution-r3 is the active source.

## Source

Context Correction V2 execution-r3 freeze and formal evidence.

## Year

2026-07-15.

## URL Or File Path

`protocols/context_correction_v2/freeze_r3.json`, `outputs/experiments/E9_context_correction_v2_r3/` and `outputs/experiments/E14_context_correction_v2_r3/`

## What It Supports

The admitted calibrated-context evidence: a 44-file freeze, E9 120/120 formal, E14 432/432 formal plus 48/48 excluded warmups, 144/144 matched benign paths, 480/480 unique first-step run keys, Guard p95 and paired end-to-end overhead.

## Notes

Freeze SHA-256 is `314aa9ed1aa9b578019827a754d45254e093d755e4fd09bee18332f93ecd3ae3`. The joint audit fingerprint is `296271e14c74a453e107f88b384aec5f9ea4c87530618ee335f407d4e85d0d5e`; E9/E14 were atomically registered.

## Source

Corrected E17 schema-2 source and automated diagnostic comparison.

## Year

2026-07-15.

## URL Or File Path

`outputs/experiments/e17_source_index_corrected_v2.json` and `outputs/experiments/E17_auto_review_corrected_r3/comparison.json`

## What It Supports

The corrected E17 candidate universe (12,704 logical runs, 3,299 review items) and the diagnostic-only agreement of two isolated automated reviewers.

## Notes

Source-index SHA-256 is `6d3baa721317b50d9dca82c958d5b0f47b23114066c9e2a42e922c8c512fd17d`. Automated agreement cannot satisfy the human review gate; human progress remains 0/2.

## Source

E11 post-hoc amendment execution-r2 freeze, rerun and analysis bundle.

## Year

2026-07-16.

## URL Or File Path

`protocols/e11_amendment_v1/freeze_r2.json`, `outputs/experiments/E11_posthoc_amendment_v1_runs/` and `outputs/experiments/E11_posthoc_amendment_v1/`

## What It Supports

Fresh current-runtime evidence for the four requested cross-tool patterns: 8/8 smoke, 48/48 formal, pattern-level ASR/Wilson intervals, paired McNemar/bootstrap results, replay index and inspected PNG/SVG.

## Notes

Freeze SHA-256 is `ceb320a915d301d6658b5caa9b662cb2ed13e24c63ec5d79f8ff7caa9ad0ba37`. The supplement remains post-hoc, independently denominated and excluded from original E11; legacy freeze/results are preserved as diagnostic provenance.

## Source

2026-07-16 verification and historical-v3 current-source compatibility audits.

## Year

2026-07-16.

## URL Or File Path

`scripts/verify.ps1`, `agent/audits/context_correction_v2_pause_2026-07-16.json` and `agent/audits/blind_v3_current_source_compatibility_2026-07-16.json`

## What It Supports

The pause-point 339-test pass, clean Context execution-r3 evidence fingerprint, and explicit limitation that eight old v3 freeze-bound sources no longer match the current checkout.

## Notes

The compatibility audit is intentionally FAIL and must not be converted into a pass by retroactive rehashing. Historical v3 outputs retain their historical provenance; current-runtime claims use later revision freezes.

## Source

E17 external-gate audit and clean CLI rejection evidence.

## Year

2026-07-16.

## URL Or File Path

`agent/audits/e17_external_gate_2026-07-16.json`, `scripts/register_e17_evidence.py` and `tests/unit/test_register_e17_evidence.py`

## What It Supports

The claim that E17 remains at 0/2 real humans, automated labels are ineligible, premature registration/final synthesis is rejected, and no `final_analysis/` directory is created.

## Notes

The clean registrar rejection is exit 2 without a traceback. The final-analysis validate-only gate also exits 2. Full verifier result after the repair is 340 passed, 1 skipped, failures=0.

## Source

Completed sampled E17 human-review evidence and final synthesis.

## Year

2026-07-16.

## URL Or File Path

`outputs/experiments/E17_human_stratified_360_v1/review/`, `experiments/registry.json`, `outputs/experiments/final_analysis/` and `scripts/build_final_analysis_sampled_e17.py`

## What It Supports

Two distinct humans completed 360 rows each; reviewer agreement is 360/360 with kappa 1.000 and no adjudication. Registry is 18/0/0. The final synthesis admits 1,364 input artifacts, renders 13 charts, retains independent E11 denominators, and produces an 8-pass/4-fail acceptance matrix.

## Notes

Only 300 representative E17 rows support Hajek design-weighted shares with a stratified 10,000-repetition bootstrap. The 40 disagreement-targeted and 20 rare/complex-targeted rows remain diagnostic. Independent statistical validation and Dashboard evidence gates pass; the final aggregate Harness verifier reports 347 passed and 1 skipped.
