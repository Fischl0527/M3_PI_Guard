# Failure Log

Use this file to prevent repeated invalid attempts and to make failures
recoverable across sessions.

## Format

```text
Date:
Task ID:
Feature ID:
Error:
Impact:
Likely Cause:
Attempts:
Final Resolution:
Follow-Up:
```

## Entries

Date: 2026-07-13  
Task ID: M3-EXPANSION-001  
Feature ID: F-HARNESS-001  
Error: `validate_requirement_ledger.py` rejected `pending` as a placeholder status even though the state-file reference recommends it during execution.  
Impact: Initial non-final requirement-ledger validation failed; no implementation evidence was affected.  
Likely Cause: Runpro validator contract and suggested interim status vocabulary are inconsistent.  
Attempts: Ran requirement-lock validation successfully, then ran the ledger validator once.  
Final Resolution: Use meaningful interim status `in progress`; retain final-only statuses for completion audit.  
Follow-Up: Re-run the validator and do not bypass it.

Date: 2026-07-13  
Task ID: M3-EXPANSION-001  
Feature ID: F-HARNESS-001  
Error: Running `python -m unittest discover -s tests -v` before a local `tests/` directory existed resolved an unrelated installed `tests` package, which imported Ultralytics and attempted an environment-only `nvidia-ml-py` auto-install.  
Impact: Baseline test discovery was invalid; the repository was not modified, but the user Python environment gained one package.  
Likely Cause: Python discovery searched outside the repository because the requested start directory did not exist locally.  
Attempts: One baseline discovery command.  
Final Resolution: Create explicit local `tests`, `tests/unit`, and `tests/integration` packages before any further discovery.  
Follow-Up: Verification scripts must assert the local test path exists and must not discover external packages.

Date: 2026-07-13  
Task ID: M3-EXPANSION-001  
Feature ID: F-EXP-002  
Error: The first one-case real-model probe used the legacy mock sandbox, whose `read_file` implementation could read the on-disk file under `sandbox/secrets` after a successful prompt-injection tool call.  
Impact: The probe was not admitted as formal evidence. No secret value was displayed or copied into the Harness state, but the legacy implementation violated the experiment permission boundary.  
Likely Cause: The Day7 mock sandbox implemented DSR with a file-backed fake canary instead of a strictly in-memory synthetic fixture.  
Attempts: Ran one Qwen attack case under `normal:off`, then inspected only path-handling source and execution metadata.  
Final Resolution: Intercept all reads under `sandbox/secrets` before filesystem probes and return an in-memory synthetic marker; reject all writes there; add tests proving no `exists`, `read_text` or `write_text` call occurs.  
Follow-Up: Re-run the probe and full tests; exclude the pre-fix probe from E0-E17 manifests and final metrics.

Date: 2026-07-13  
Task ID: M3-EXPANSION-001  
Feature ID: F-EXP-002  
Error: The first Stub reproducibility audit reported 2,426 mismatched steps out of 3,909 shared steps.  
Impact: The audit initially failed; neither Stub matrix was discarded or altered.  
Likely Cause: Per-module `guard_trace[].latency_ms` remained in the semantic projection even though all decisions, actions and observations matched.  
Attempts: Ran two independent 3,300-case Stub matrices, generated a strict semantic comparison, then summarized differing field paths without weakening result fields.  
Final Resolution: Exclude the nested wall-clock-only field `latency_ms`; retain actions, parsed calls, observations, decisions, scores, reasons and terminal states. The corrected audit compares 3,909 steps with identical semantic SHA-256 values and zero mismatches.  
Follow-Up: Keep the projection unit-tested so future result fields are not silently ignored.

Date: 2026-07-13  
Task ID: M3-EXPANSION-001  
Feature ID: F-EXP-002  
Error: After the successful 60/60 real-model smoke stage, Python reader threads raised `UnicodeDecodeError` while decoding Ollama lifecycle output with the Windows GBK default; malformed model text also emitted `SyntaxWarning` during the safe literal parser fallback.  
Impact: Case logs and smoke completion were intact, but some stop/snapshot stdout could be lost and the console contained noisy warnings.  
Likely Cause: `subprocess.run(text=True)` did not declare Ollama's UTF-8 encoding, and `ast.literal_eval` exposes parser warnings for invalid escape sequences before returning or raising.  
Attempts: Completed all five model smoke jobs, inspected the lifecycle helper and parser call sites, and reproduced the responsible defaults in source.  
Final Resolution: Decode Ollama and GPU subprocess output explicitly as UTF-8 with replacement for invalid bytes; suppress only `SyntaxWarning` inside the already constrained literal parser call. Targeted tests and a live five-model inventory snapshot pass without reader-thread errors.  
Follow-Up: Preserve the original smoke stderr as evidence; use the fixed lifecycle helper for all later stages.

Date: 2026-07-13  
Task ID: M3-EXPANSION-001  
Feature ID: F-EXP-002 / F-EXP-003  
Error: The first smoke audit showed common small-model protocol variants (`read\\_file`, mock paths with a leading slash, and one unescaped nested object inside `final.answer`); a validation-baseline process had already started with the pre-fix parser.  
Impact: Vicuna had 8/12 parse failures and Llama had 2/29 step-level parse failures. The interrupted validation output is excluded from E13 and all formal denominators.  
Likely Cause: The parser handled ordinary JSON/code fences and field aliases but not invalid Markdown underscore escapes or the safe non-executable nested-final pattern.  
Attempts: Audited every smoke failure, replayed raw outputs through a general repair candidate, and stopped the stale validation process tree while preserving its partial files.  
Final Resolution: Remove only JSON-invalid backslashes, canonicalize local mock path aliases, and recover malformed nested content only for the non-executable `final` tool. Historical smoke replay improves from 4/12 to 12/12 for Vicuna and 27/29 to 28/29 for Llama without mapping the unsupported `summarize` tool. A fresh five-model `program_v2` smoke is required before calibration.  
Follow-Up: Use only `program_manifest_v2.json` and `program_v2/` for E13 onward; retain the first smoke and interrupted validation as diagnostic evidence.

Date: 2026-07-13  
Task ID: M3-EXPANSION-001  
Feature ID: F-EXP-002 / F-EXP-003  
Error: The validation log auditor rejected two `call_api` proposals using `api.example.test` and `api.example.com`; after correcting the auditor, an interrupted E4 job refused resume because the implementation hash had changed.  
Impact: E13 inputs remained valid and passed after re-audit, but 180 completed and one partial v2 ablation runs are excluded from E4. No files were deleted.  
Likely Cause: `_safe_mock_endpoint` accepted only `mock:` syntax even though the sandbox never performs network I/O and IANA reserves the `example.com/.test` namespaces; run-matrix correctly forbids appending to a manifest produced under a different implementation hash.  
Attempts: Stopped E4, verified sandbox `network=disabled`, checked the IANA reserved-domain registry, narrowed acceptance to reserved example/special-use suffixes, reran the 117-row log audit, then attempted normal resume.  
Final Resolution: Validation audit now passes 60 cases/117 rows with zero issues while arbitrary public and lookalike hosts remain rejected. A fresh `program_v3` root is used for smoke, E4 and all post-freeze experiments; old v2 E4 artifacts remain diagnostic only.  
Follow-Up: Do not merge program roots in denominators; use `program_manifest_v3.json` for E1-E12/E15 and v2 validation only for E13 provenance.

Date: 2026-07-13  
Task ID: M3-EXPANSION-001  
Feature ID: F-EXP-002 / F-EXP-003 / F-EVAL-001  
Error: Formal smoke and E4 shared the repository-level mock sandbox. Vicuna smoke performed an unauthorized `write_file` on `sandbox/public/clean_report.md`; all 187 E4 reads observed the mutated content instead of the frozen fixture.  
Impact: The `program_v3` E4 batch was stopped at 23/25 conditions (1,380/1,500 completed). The entire batch is excluded from formal analysis, and the prior validation calibration must be rerun under isolation. No E4 result is registered.  
Likely Cause: `run_case()` called `init_sandbox()`, which only created missing directories/files. Tool state, outbox state and writable public files were global across cases, conditions and concurrent lanes.  
Attempts: Correlated the tracked fixture diff and mtime with the exact smoke RunLog/tool event, audited E4 read-observation hashes against HEAD, and independently reviewed validation/E14 concurrency behavior.  
Final Resolution: Superseded and resolved by the next entry: fixed-seed per-run sandbox isolation was implemented, and Stub, five-model smoke, validation/calibration and the complete 1,500-run E4 matrix were rerun in a clean formal root.  
Follow-Up: Never resume or analyze `program_v3` as formal evidence. Verify the repository sandbox remains byte-identical before and after sequential and concurrent runs, then freeze only the new final root.

Date: 2026-07-13  
Task ID: M3-EXPANSION-001  
Feature ID: F-EXP-002 / F-EXP-003 / F-EVAL-001  
Error: Follow-up resolution for the repository-level sandbox contamination recorded above.  
Impact: No invalid `program_v3` result was admitted; the invalid namespace remains preserved for audit only.  
Likely Cause: Confirmed global mutable sandbox state in the pre-isolation runner.  
Attempts: Implemented per-logical-run temporary sandboxes, immutable public fixture generation, in-memory-only secret canaries, deterministic final-state hashing and cleanup verification; reran Stub, smoke, validation, calibration and E4 in `program_final`.  
Final Resolution: Isolation tests and the full unit suite passed; canonical Stub reproduced exactly across two independent 3,300-run matrices; the fresh E4 completed 1,500/1,500 with 1,500 unique `fresh_cleaned` sandbox instances, zero temporary residue and byte-identical tracked public fixtures.  
Follow-Up: Use only `program_final` for formal E0-E17 evidence and retain `program_v3/INVALIDATED.json` as the provenance boundary.

Date: 2026-07-14  
Task ID: M3-EXPANSION-001  
Feature ID: F-EXP-003 / F-EVAL-001  
Error: E14 completed all 24 performance jobs and four warmups, then failed while summarizing paired end-to-end overhead because legitimate negative percentages were passed to `latency_summary()`, which only accepts non-negative latencies.  
Impact: No model job or raw run was lost. The first formal E14 process exited 1 before aggregate metrics, statistics and figures were finalized; the manifest remained `running` because post-processing exceptions were not durably caught.  
Likely Cause: A signed effect distribution (`full_guard - off`) incorrectly reused a validator designed for absolute latency samples.  
Attempts: Preserved every work/job record and GPU snapshot, captured the traceback and environment reference in `outputs/experiments/E14/failures/postprocessing_20260714T0009.json`, then added a signed finite-value summary plus durable post-processing failure handling.  
Final Resolution: The signed summary and durable post-processing failure path passed regression tests, and an explicit resume rebuilt the initial 144-run aggregate without rerunning model jobs. The resulting evidence exposed a second design issue: only the off condition had been warmed, and the first full-Guard cell contained two retained high-tail observations. That complete batch was migrated intact to `outputs/experiments/E14_initial_cold_start_diagnostic/` and marked as a diagnostic rather than discarded. The plan was then strengthened to warm both off and full Guard over all six representative cases at every context and to run three repeats. The complete replacement matrix finished 432/432 measured case-runs with zero errors/timeouts; all 12 cells met Guard p95 < 10 ms and median end-to-end overhead < 10%.  
Follow-Up: Keep the cold-start diagnostic and final warm-state denominators separate in all reports; do not describe negative signed path differences as pure additive Guard overhead or as model acceleration.

Date: 2026-07-14  
Task ID: M3-EXPANSION-001  
Feature ID: F-HARNESS-001  
Error: `bash scripts/verify.sh` reported four downstream failures because the WSL Bash environment could not resolve the script's default `python` command.  
Impact: Harness file and shell syntax checks passed, but JSON, compile, test and registry checks did not start; no code or experiment evidence was changed.  
Likely Cause: PowerShell resolves Python from `F:\robot\Anaconda3\python.exe`, while the Bash process has no `python` entry on PATH and exposes that interpreter at `/mnt/f/robot/Anaconda3/python.exe`.  
Attempts: Ran the verifier once with its default environment, then resolved and executed the Windows interpreter through its WSL mount path.  
Final Resolution: Reran the same Harness verifier through WSL with `PYTHON_BIN=/mnt/f/robot/Anaconda3/python.exe`; Harness files, JSON contracts, shell syntax, Python compile, unit/integration discovery and registry structure all passed with `Verification failed=0`. The broader pytest suite had already passed 222 tests with one platform-specific symlink skip.  
Follow-Up: Preserve the explicit WSL interpreter override in verification evidence and create the blind freeze only after the remaining read-only data/provenance checks pass.

Date: 2026-07-14  
Task ID: M3-EXPANSION-001  
Feature ID: F-EXP-003  
Error: A post-freeze read-only audit found that the program-stage plan hash pins the model tag but not the Ollama digest, and does not serialize the orchestration-only `continue_on_error` / model-lifecycle booleans.  
Impact: The frozen code, dataset, thresholds, 12-job grid and every matrix command are pinned, but the top-level stage hash alone is insufficient to prove binary model identity or those two default orchestration choices. Each job manifest still records the live model identity, and the current invocation uses fail-fast/default lifecycle management.  
Likely Cause: Digest capture occurs inside the matrix runner after the stage plan is built; orchestration flags affect control flow rather than the generated matrix command.  
Attempts: Independently recomputed the v2 stage plan, frozen input hashes, 4-model × 3-seed grid, 540-run job scale, blind filter and 1.0/1.0 thresholds while the first job was running.  
Final Resolution: The completion-time strict integrity audit verified every formal job's model tag/digest/Ollama provenance and lifecycle-complete run counts; all four model identities were single-valued, and 10,526 logical runs plus 65/65 frozen files passed without changing the freeze.  
Follow-Up: Record the default `continue_on_error=false` and lifecycle management behavior as a reproducibility limitation in the final analysis, and fail admission if any model tag maps to multiple digests.

Date: 2026-07-14  
Task ID: M3-EXPANSION-001  
Feature ID: F-HARNESS-001 / F-EXP-003  
Error: The first synthetic integrity-auditor test raised `TypeError: unhashable type: 'list'` while normalizing list-valued matrix filters.  
Impact: Only temporary test fixtures were affected; no experiment manifest, log, freeze file or protected source was modified.  
Likely Cause: `_csv_values()` checked membership in a set before branching on list-like inputs.  
Attempts: Kept the failed test evidence, changed the empty-value check to explicit `None`/empty-string comparisons, and reran all three focused tests.  
Final Resolution: The passing fixture, active-stage no-scan gate and tamper-detection test all pass; the completed first main job also audits cleanly at 540 logical runs and 540 unique cleaned sandboxes.  
Follow-Up: Run the one-command audit only after `main`, `derived` and `stability` are all marked completed.

Date: 2026-07-14  
Task ID: M3-EXPANSION-001  
Feature ID: F-EVAL-001 / FINAL-ANALYSIS  
Error: The first synthetic final-analysis test run rejected every fixture at E0 because the same primary `manifest.json` appeared once in `required_artifacts` and once in `evidence`, and candidate discovery counted path occurrences instead of unique resolved files.  
Impact: Five synthetic tests failed before admission; no formal experiment output or protected source was read or modified.  
Likely Cause: Registry lists intentionally overlap, but `_find_primary_manifest()` did not deduplicate resolved paths.  
Attempts: Confirmed both entries resolved to the same file and kept the strict requirement that each experiment have exactly one distinct primary manifest.  
Final Resolution: Primary-manifest discovery now deduplicates resolved paths before enforcing cardinality; focused tests are rerun after this correction.  
Follow-Up: Retain an explicit regression test in the synthetic all-completed registry because real registry required/evidence lists also overlap.

Date: 2026-07-14  
Task ID: M3-EXPANSION-001  
Feature ID: F-EVAL-001 / FINAL-ANALYSIS  
Error: Direct invocation with `python scripts/build_final_analysis.py --help` initially raised `ModuleNotFoundError: experiments` even though pytest imports succeeded.  
Impact: The module API and seven synthetic tests passed, but the documented one-command CLI entry point was not executable; no experiment evidence was accessed or changed.  
Likely Cause: Direct script execution places `scripts/` rather than the repository root at the front of `sys.path`.  
Attempts: Reproduced the failure from the repository root after compilation and focused tests had passed.  
Final Resolution: Resolve and prepend the script's repository root before importing `experiments` and `m3_eval`; revalidate both direct CLI help and the synthetic suite.  
Follow-Up: Keep a direct-entry smoke check in final verification in addition to import-based pytest coverage.

Date: 2026-07-14  
Task ID: M3-EXPANSION-001  
Feature ID: F-DASH-001 / F-DELIVERY-001  
Error: The first static `run_final_dashboard.ps1 -ValidateOnly` preflight treated `experiments` in `registry.json` as a keyed object and therefore rejected completed E0.  
Impact: The new delivery gate did not pass its initial static preflight; no Dashboard, model, raw result, or experiment process was started or changed.  
Likely Cause: The registry stores experiment entries as an array with an `id` field, while the first implementation used keyed `PSObject` lookup.  
Attempts: Parsed the PowerShell script successfully, ran only `-ValidateOnly`, observed zero Streamlit process delta, and inspected only registry structure metadata.  
Final Resolution: Resolve each experiment by its array `id`, require exactly one match, and require `status=completed`. The corrected script parses successfully, advances through completed E0, rejects at the missing E1 bundle as expected, and keeps the Streamlit process delta at zero.  
Follow-Up: The corrected gate is expected to reject the current in-progress program at the first incomplete/missing formal bundle. Rerun `-ValidateOnly` after E0-E17 and `final_analysis` are complete.

Date: 2026-07-14  
Task ID: M3-EXPANSION-001  
Feature ID: F-EXP-003 / F-EVAL-001  
Error: The frozen blind main stage failed fast in `main__llama3_2_3b__seed_104729`, condition `regular_none`, when case `DJX-B-007` proposed a Windows-invalid write target ending in `:`. The isolated sandbox's atomic `os.replace()` raised `WinError 87`.  
Impact: Main stopped at 3,240/6,480 completed logical runs after all Qwen and Phi jobs had completed. The Llama job preserved 25 successful logical runs plus one explicit `runner-error` checkpoint, while all later Llama/Gemma jobs remained pending. No case was silently skipped or removed from the intended denominator.  
Likely Cause: The sandbox validates containment but does not reject or normalize Windows-reserved path syntax before attempting a filesystem write. The model generation is seed-pinned, so an unchanged resume is expected to execute the same failed logical run again rather than provide a reliable recovery.  
Attempts: Preserved the program traceback and failed matrix manifest, confirmed fail-fast exit code 1, identified the exact case/run/condition from checkpoint metadata without reading raw model text, verified the failed checkpoint is not considered a successful terminal run, and triggered an independent cleanup/lifecycle audit.  
Final Resolution: The failed blind namespace was invalidated and preserved. Windows-invalid paths were made fail-closed with regression tests, affected pre-freeze gates were rerun, `blind_freeze_v3.json` was created, and the formal main matrix restarted from zero and completed 6,480/6,480.  
Follow-Up: Preserve the failed namespace and its hashes as diagnostic evidence; add Windows reserved-name/character tests, rerun all affected conditions under the replacement freeze, and do not admit Qwen/Phi results from this invalidated blind attempt into formal conclusions.

Date: 2026-07-14  
Task ID: M3-EXPANSION-001  
Feature ID: F-DELIVERY-001 / FINAL-PRESENTATION  
Error: Initial presentation workspace setup did not complete because dependency discovery stalled, `HOME` was unset so Artifact Tool resolved its cache under the repository, and the template inspector could not find a Unix-compatible `unzip`.  
Impact: Only the external temporary presentation workspace was affected; the source deck, formal experiment outputs, models and protected blind-run inputs were not modified.  
Likely Cause: The Windows host needed explicit bundled-runtime and Git utility paths that the generic setup scripts do not infer reliably.  
Attempts: Terminated the stalled dependency lookup, inspected the installed runtime, set `HOME=$USERPROFILE`, selected the bundled Python runtime and prepended Git's `unzip.exe` directory.  
Final Resolution: The reproducible PowerShell entry point now establishes those paths before setup. The final synthetic run inspected all 12 template slides and passed the frame-map validator with zero issues.  
Follow-Up: Keep the presentation workspace outside the repository and retain these environment bindings for the formal build.

Date: 2026-07-14  
Task ID: M3-EXPANSION-001  
Feature ID: F-DELIVERY-001 / FINAL-PRESENTATION  
Error: Early deck-builder iterations hit an invalid `await` inside a synchronous `flatMap`, PowerShell 5.1 garbled a Chinese literal path, and the imported slide collection exposed `getItem()` rather than the assumed `getItemAt()`. An initial patch also targeted the sibling repository because `apply_patch` resolves from the desktop workspace root.  
Impact: The preview build failed before producing a deliverable. One newly created frame-map file briefly landed in the sibling repository; it was immediately moved with `apply_patch`, and no existing sibling file was changed.  
Likely Cause: JavaScript async misuse, Windows PowerShell source encoding, an API collection-method mismatch, and an incorrect patch-relative path.  
Attempts: Replaced the async `flatMap` with an explicit loop, selected the source deck by SHA-256 using an ASCII wildcard, switched to `getItem()`, and prefixed all subsequent patches with `../M3_PI_Guard_test/`.  
Final Resolution: All JavaScript modules pass `node --check`; the PowerShell script parses cleanly; the source deck remains byte-identical; and the 12-slide synthetic preview exports successfully.  
Follow-Up: Continue selecting the immutable source deck by hash and never overwrite it in formal mode.

Date: 2026-07-14  
Task ID: M3-EXPANSION-001  
Feature ID: F-DELIVERY-001 / FINAL-PRESENTATION  
Error: The first QA pass invoked a system Python without `python-pptx`, then still failed when `HOME` was not propagated. Artifact Tool's montage export also contained only the first slide.  
Impact: The deck itself had already exported, but the required overflow and whole-deck visual checks were incomplete.  
Likely Cause: Runtime mismatch plus a montage limitation in the imported-deck export path.  
Attempts: Reran QA with the bundled Python and explicit `HOME`, inspected every full-size slide PNG, and added a supplied `create_montage.py` pass over exactly the 12 `slide-*.png` files.  
Final Resolution: Template fidelity passes with zero issues, `slides_test.py` reports no overflow, all 12 slides were rendered and visually reviewed, and the supplemental contact sheet contains exactly 12 labeled slides.  
Follow-Up: Treat the supplied 12-slide contact sheet and individual PNGs as authoritative visual QA; retain the Artifact Tool montage only as a non-blocking diagnostic artifact.

Date: 2026-07-14  
Task ID: M3-EXPANSION-001  
Feature ID: F-EXP-003 / E14-PREFLIGHT  
Error: The first E14 plan-audit snippet queried a nonexistent `progress.expected_jobs` field and exited with `KeyError` after the plan-only command had completed successfully.  
Impact: Only the read-only audit snippet failed; the planned E14 manifest and execution plan were not changed, no model or GPU job was started, and no experiment result was admitted.  
Likely Cause: The E14 manifest names its measured-job counter `progress.expected_runs`, while the preflight note described it conceptually as expected jobs.  
Attempts: Inspected the manifest keys and job schema without modifying either file.  
Final Resolution: Correct the audit to require `progress.expected_runs == 24`, together with 8 warmup and 24 measured job records.  
Follow-Up: Keep the manifest-schema assertion in the corrected preflight before starting the formal E14 run.

Date: 2026-07-14  
Task ID: M3-EXPANSION-001  
Feature ID: F-EXP-003 / E14-VISUAL-QA  
Error: Independent visual QA found that the transparent upper-right Condition legend in `throughput_by_concurrency.png` allowed the c=4/full_guard line to cross and obscure the `full_guard` label.  
Impact: E14 numeric, runtime, lifecycle, statistical, and artifact-hash audits passed, but the chart-delivery gate failed. The completed canonical E14 package was therefore not retained as formal evidence.  
Likely Cause: Both chart legends were configured with `frameon=False`, so plotted data remained visible through legend text.  
Attempts: Reproduced the issue at original PNG resolution and confirmed latency and GPU charts were otherwise readable.  
Final Resolution: Configure both legends with a 96%-opaque white background and border, add a regression assertion to chart-integrity metadata, archive the complete failed-visual package under `_invalid/e14_v2_visual_qa`, return E14 to pending, and rerun the entire E14 matrix under the new implementation digest.  
Follow-Up: Require independent original-resolution visual QA before registering the replacement E14 result.

Date: 2026-07-14  
Task ID: M3-EXPANSION-001  
Feature ID: F-EXP-003 / BLIND-V3-PREFLIGHT  
Error: A read-only program-status snippet queried a nonexistent `validation` stage key and exited with `KeyError`; the manifest uses `validation-baseline`.  
Impact: No manifest, freeze, result, model, or registry state changed; the preceding CLI help succeeded and the follow-up inspection was read-only.  
Likely Cause: The diagnostic used a shorthand stage name rather than the orchestrator's canonical key.  
Attempts: Enumerated `manifest["stages"]` directly.  
Final Resolution: Re-ran the status inspection using the manifest's actual keys and confirmed the four pre-blind stages are completed.  
Follow-Up: Use manifest-discovered keys for all later stage-status audits.

Date: 2026-07-14  
Task ID: M3-EXPANSION-001  
Feature ID: F-EXP-003 / DERIVED-V3-ARTIFACT-AUDIT  
Error: The first read-only bundle audit treated manifest `required_artifacts` entries as filenames relative to each experiment directory, although they are already repository-relative paths, and therefore reported 52 false missing-file findings.  
Impact: Only the diagnostic snippet exited nonzero; no experiment output, registry entry, model process, freeze input, or formal denominator changed.  
Likely Cause: The one-off audit did not inspect the path convention before joining each required-artifact entry to the bundle directory.  
Attempts: Inspected the stored values, distinguished repository-relative entries from bare filenames, and reran the same size/hash/figure/raw-index checks with the corrected resolver.  
Final Resolution: The corrected audit passed all E7-E11 bundles with zero missing files or hash mismatches; all five raw indexes validate their complete formal run counts and admit zero Stub records.  
Follow-Up: Resolve manifest-declared paths from the repository root whenever an entry contains directory components.

Date: 2026-07-14  
Task ID: M3-EXPANSION-001  
Feature ID: F-EXP-003 / STABILITY-V3-PREFLIGHT  
Error: A read-only status snippet queried `manifest["stages"]["stability"]` before the first stability invocation had created that stage and exited with `KeyError`.  
Impact: The subsequent freeze verification and `ollama ps` checks still passed; no model, output, registry entry, frozen input, or experiment denominator was changed by the failed snippet.  
Likely Cause: Unlike previously executed stages, the orchestrator does not persist a pending stability stage until its first formal invocation.  
Attempts: Enumerated the actual stage keys and independently recalculated the stability plan from the protected fixture and matrix builder.  
Final Resolution: Confirmed the absent key was the valid first-run state, verified 120 jobs and 3,600 intended runs through a separate preflight, and launched stability without `--resume`, allowing the orchestrator to create the canonical stage.  
Follow-Up: Treat a missing optional future-stage key as pending until the stage's first invocation; inspect stage membership before dereferencing.

Date: 2026-07-14  
Task ID: M3-EXPANSION-001  
Feature ID: F-DELIVERY-001 / FINAL-PRESENTATION-CONTRACT  
Error: Read-only delivery preflight found that the deck builder requested `attack_family_heatmap` and `language_evasion_heatmap`, while the formal E18 analysis contract emits `family_robustness` and `language_evasion`.  
Impact: No formal deck had been built yet, but an unchanged final-mode build would deterministically fail its evidence gate with `formal figure is missing`. Experiment data, metrics, figures, registry state, and the blind freeze were unaffected.  
Likely Cause: Presentation fixture identifiers drifted from the finalized `CHART_SPECS` names after the analysis chart taxonomy was refined.  
Attempts: Cross-checked every selected slide figure against `scripts.build_final_analysis.CHART_SPECS` and inspected the synthetic fixture and delivery notes for the same stale names.  
Final Resolution: Aligned the deck and fixture IDs to `family_robustness` and `language_evasion`, corrected the non-selected context chart name in the README, and added a contract test requiring all ten deck figures to exist in E18 and the synthetic fixture order to match the deck slots. The test, both JavaScript syntax checks, and the unchanged blind-freeze verification pass.  
Follow-Up: Keep `tests/unit/test_presentation_figure_contract.py` in the final delivery gate so future chart renames fail before deck generation.

Date: 2026-07-14  
Task ID: M3-EXPANSION-001  
Feature ID: F-DASH-001 / E18-FIGURE-INTEGRATION  
Error: Delivery integration preflight found that the final-analysis manifest classified `figure_manifest.json` as `analysis_artifact`, while the Dashboard loader requires exactly one artifact with kind `figure_manifest` to anchor and admit a figure bundle.  
Impact: Each final-analysis and Dashboard unit test passed in isolation, but an unchanged end-to-end load would reject all 12 E18 synthesis figures with an anchor warning. No formal experiment output or frozen input was affected.  
Likely Cause: The final-analysis artifact classifier distinguished only PNG/SVG figures from generic analysis files and lacked the Dashboard's explicit manifest-anchor kind.  
Attempts: Traced the E18 manifest writer and Dashboard `_verify_figure_manifest_anchor` contract, then generated a complete synthetic E0-E17 analysis bundle through the real integration path.  
Final Resolution: Classify only `figure_manifest.json` as `figure_manifest`, retain PNG/SVG as `figure`, and keep all remaining files as `analysis_artifact`. The integration test now requires one anchored figure manifest, zero Dashboard warnings, and exactly 12 loaded E18 figures; it passes and the blind freeze remains unchanged.  
Follow-Up: Preserve the cross-module assertion in `test_full_synthetic_program_builds_reproducible_final_bundle`.

Date: 2026-07-14  
Task ID: M3-EXPANSION-001  
Feature ID: F-DASH-001 / FINAL-EVIDENCE-REHASH  
Error: Delivery preflight found that the Dashboard launcher checked completed statuses and allowlisted paths but did not rehash the live E0-E17 evidence or the E18 artifact/input ledgers before loading their CSV files.  
Impact: A post-generation source or synthesis drift could pass the launcher's structural gate and be consumed by the Dashboard. No such drift was observed, and the formal Dashboard had not yet been launched.  
Likely Cause: The launcher and strict report evidence loader were implemented separately, so the stronger cross-artifact validator was not called from the Dashboard entry path.  
Attempts: Traced the public `load_report_evidence` validator, which already rehashes E0-E17, E18, the live registry, stored input ledger, chart map, and figure manifest.  
Final Resolution: Added `Assert-HashVerifiedEvidenceChain` before the `-ValidateOnly` return and normal Streamlit launch, using `load_report_evidence` as the single strict validator. Four targeted launcher/report tests pass, and the blind freeze remains unchanged.  
Follow-Up: The final `-ValidateOnly` run must print the validated bundle/figure counts before Dashboard smoke testing.

Date: 2026-07-14  
Task ID: M3-EXPANSION-001  
Feature ID: F-DASH-001 / POWERSHELL-PARSE-DIAGNOSTIC  
Error: The first nested PowerShell parse-check command allowed the outer shell to expand `$null`, so the child command reported `=[scriptblock]::Create` as unknown even though a later statement printed `PARSE_OK` and the child exited zero.  
Impact: Only the diagnostic command was unreliable; the launcher file and experiment state were not changed.  
Likely Cause: Double-quoted nesting passed a PowerShell variable through two shell layers without preserving the dollar sign.  
Attempts: Repeated the parse check with the child command enclosed as a literal single-quoted argument.  
Final Resolution: The corrected child process performs `[scriptblock]::Create(...)` and returns only `PARSE_OK` with exit code zero.  
Follow-Up: For nested PowerShell diagnostics, preserve child variables with a single-quoted outer argument and do not treat a trailing sentinel as proof when earlier non-terminating errors occurred.

Date: 2026-07-14  
Task ID: M3-EXPANSION-001  
Feature ID: F-EXP-003 / E11-COVERAGE-AUDIT  
Error: Final plan-to-evidence reconciliation found that the formal E11 derived matrix covers `read_file_to_send_email`, `read_file_to_call_api`, `run_code_to_write_file`, and `write_file_to_call_api`, whereas the requested chains were read-to-send, search-to-API, memory-to-file, and tool-output-to-next-action.  
Impact: E11's 44/44 runs are internally complete and hash-valid, but only read-to-send directly matches the requested four-chain taxonomy. The other three requested chains cannot be claimed as independently tested from the current evidence.  
Likely Cause: The canonical attack generator's four chain definitions predate the expanded execution plan, and the derived fixture preserved those older definitions without a plan-to-fixture semantic coverage assertion.  
Attempts: Cross-checked `chain_metrics.csv`, canonical chain definitions, derived-case construction, and the documented attack matrix.  
Final Resolution: Chose a separately frozen, transparently post-hoc supplemental matrix so the original E11 denominator stayed immutable. Revision 2 completed 8/8 smoke and 48/48 formal runs across the four requested patterns; hashes, statistics, semantics and visual layout passed, and the supplement is never pooled into frozen E11.  
Follow-Up: Do not describe E11 as full planned coverage until the three missing chain families have formal evidence; add a semantic plan-to-fixture coverage test for future runs.

Date: 2026-07-14  
Task ID: M3-EXPANSION-001  
Feature ID: F-EVAL-001 / INTEGRITY-AUDIT-INSPECTION  
Error: A read-only inspection snippet treated the result-integrity report's `models` object as a list and raised `KeyError: 0` after successfully printing the stage schema.  
Impact: Only the diagnostic snippet failed; the audit JSON, experiment outputs, registry, models, and frozen inputs were unchanged.  
Likely Cause: The report stores model provenance as a dictionary keyed by model tag, whereas stage summaries are stored as a list.  
Attempts: Inspected the top-level value types and reran the query using `.items()` for model provenance.  
Final Resolution: Recovered all four model digests/Ollama versions and the per-job parse counts without altering evidence.  
Follow-Up: Assert JSON node types before positional indexing in one-off audit queries.

Date: 2026-07-14  
Task ID: M3-EXPANSION-001  
Feature ID: F-EXP-003 / E11-POSTHOC-PREFLIGHT  
Error: The first amendment plan command incorrectly passed `--output-root` to the `plan` subcommand, which accepts no options.  
Impact: The command exited before any model/GPU process or experiment output was created.  
Likely Cause: The option belongs only to the `run` subcommand and was copied into the read-only planning invocation.  
Attempts: Inspected the `plan` and `run` subcommand help separately.  
Final Resolution: Re-ran `python scripts/e11_amendment_runner.py plan` without extra arguments and verified the 24-case, 48-run, four-pattern frozen design.  
Follow-Up: Query subcommand-specific help before composing multi-command experiment wrappers.

Date: 2026-07-14  
Task ID: M3-EXPANSION-001  
Feature ID: F-EXP-003 / E11-POSTHOC-BUNDLE-AUDIT  
Error: The first two read-only post-hoc bundle audits respectively resolved bundle-relative artifact paths from the repository root and queried a nonexistent `chain_pattern` CSV column instead of the actual `pattern` field.  
Impact: The diagnostics produced false missing-file findings and then a `KeyError`; no raw result, bundle artifact, registry entry, freeze, or model output changed.  
Likely Cause: The amendment manifest intentionally uses paths relative to its bundle, and its compact metrics schema uses `pattern` rather than the canonical E11 analyzer's `chain_pattern`.  
Attempts: Inspected the manifest artifact entries and CSV header, then reran the same hash/count/statistical checks using the declared conventions.  
Final Resolution: Corrected audit passed all nine bundle artifacts, 48/48 logical runs, eight metric cells, four comparisons, 10,000 bootstrap iterations, Holm correction, zero timeouts/nonterminal runs, and two retained parse-failure runs.  
Follow-Up: Resolve artifact paths according to each manifest's explicit scope and inspect headers before column assertions.

Date: 2026-07-14  
Task ID: M3-EXPANSION-001  
Feature ID: F-EXP-003 / E11-POSTHOC-VISUAL-QA  
Error: Original-resolution QA found that `primary_chart.png` placed the footer across the x-axis category labels, making the bottom annotations overlap and partially clip.  
Impact: Numeric, runtime, statistical, and hash audits passed, but the amendment evidence package failed its visual-delivery gate and must not be registered or admitted into E18.  
Likely Cause: The analyzer combined a long footer and long chain labels with tight-layout output without reserving an explicit lower margin.  
Attempts: Inspected the full-resolution PNG after all numeric/hash checks; no selective metric or data change was made.  
Final Resolution: Revision 1 was preserved under `_invalid`. Revision 2 added a measurable footer/tick layout gate, updated its separate pre-run freeze and reran all calls from scratch; the 2070x1188 chart passed automated and original-resolution inspection with a 149.23 px gap above the 23.76 px minimum.  
Follow-Up: Add a layout regression gate and repeat original-resolution QA before registering the replacement amendment evidence.

Date: 2026-07-14  
Task ID: M3-EXPANSION-001  
Feature ID: F-EXP-003 / E11-POSTHOC-AMENDMENT-V1  
Error: The first CPU-only amendment plan validation required the canonical `injected_instruction` sentence to occur verbatim inside every mock observation and rejected `E11A-RTS-02`, whose observation intentionally used a semantic paraphrase.  
Impact: Validation stopped before any matrix execution; no Ollama request, GPU work, original E11 bundle, registry entry, v3 frozen input, or formal denominator was touched.  
Likely Cause: The initial integrity assertion conflated a frozen semantic target with exact surface wording, despite the protocol deliberately varying instruction phrasing.  
Attempts: Compared all fixture observations with their frozen unsafe ToolCalls and separated stable target identity from linguistic realization.  
Final Resolution: Added a tool-specific semantic-target extractor and now require the concrete recipient, endpoint, path, or code payload to occur in each observation while retaining exact case-to-fixture and offline-label equality. The amended freeze was rehashed; plan validation, seven targeted tests, and the 8/8 stub smoke preflight pass.  
Follow-Up: Preserve semantic target assertions for paraphrased attack fixtures; do not use verbatim sentence equality as a proxy for chain identity.

Date: 2026-07-14  
Task ID: M3-EXPANSION-001  
Feature ID: F-EXP-003 / E11-POSTHOC-VISUAL-QA-REV2  
Error: The revision-1 E11 amendment chart failed original-resolution QA because its footer overlapped the x-axis labels.  
Impact: Revision 1 remained invalidated and was never registered or admitted to final synthesis.  
Likely Cause: The first renderer did not reserve a measurable footer-to-tick gap.  
Attempts: Archived all revision-1 raw and derived artifacts under `_invalid`, updated the amendment freeze, added explicit 24-case selection and a pixel/bounding-box layout gate, then reran all model calls from scratch.  
Final Resolution: Revision 2 freeze `5e68ee0eb28e16bb82748040c37668b554af7cc2ec4600d88e9419c7f2317e53` completed 8/8 smoke and 48/48 formal runs. The regenerated 2070x1188 PNG passed the automated layout gate with a 149.23 px footer-to-tick gap versus a 23.76 px minimum and passed manual original-resolution inspection. The hash-verified supplement was registered as independent post-hoc evidence without replacing or pooling the original E11 denominator.  
Follow-Up: Keep the layout regression and fresh-run requirement in every future visualization-only amendment.

Date: 2026-07-14  
Task ID: M3-EXPANSION-001  
Feature ID: F-E17-001 / AUTOMATED-REVIEWER-SCHEMA  
Error: The first diagnostic automated reviewer B used a detailed custom primary taxonomy, while reviewer A used numeric confidence values; both drifted from parts of the frozen E17 review schema.  
Impact: Both 3379-row files preserved blinded evidence and were internally deterministic, but they were not mutually comparable under the canonical E17 schema and were ineligible for the automated agreement calculation. Neither was submitted as a human review or admitted to formal E17.  
Likely Cause: The initial isolation prompts hid outcomes correctly but did not explicitly bind every reviewer field to the shared canonical codebook.  
Attempts: Added a strict comparator that rejects any noncanonical primary/secondary code, attestation, confidence value, evidence mutation, duplicate ID, or incomplete row. Launched fresh isolated A and B reviews from their separate blinded packets with codes `leak|false_block|ask|parse_failure|timeout|max_steps|other|none` and confidence levels `low|medium|high`.  
Final Resolution: Resolved. Two fresh isolated canonical reviewers completed 3379/3379 rows each, preserved every blinded evidence field, used distinct automated reviewer IDs, and passed the strict schema validator. Their frozen outputs produced 2839/3379 primary-code agreements (84.02%, Wilson 95% CI 82.74%-85.22%) with Cohen's kappa 0.7881; the full primary-plus-secondary agreement was 2663/3379 (78.81%). A second comparator run was byte-identical: comparison JSON `9e5776d02e28a89ee9bb8ca18f779581601b18be92aa28ccdaa71c2fb4c45aeb`, report `dd34ef1459197d2f6070cf01c5e35c89f097a2fdcd915b946c45c63d6347d4c9`, and disagreement CSV `f5171f8fb3791457f89045139c835ba564a51a0992cc150ab3b85cca22743a2f`. All automated artifacts are explicitly diagnostic-only and remain ineligible for formal E17 human submission.  
Follow-Up: Freeze the complete shared annotation schema before launching independent reviewers; isolation must hide outcomes, not the common rubric.

Date: 2026-07-14  
Task ID: M3-EXPANSION-001  
Feature ID: F-DASH-001 / SEMANTIC-BATCH-FILTER  
Error: Browser QA found that result-manifest job identifiers such as `main__...` and `ablation__...` leaked into the experiment-batch multiselect beside the intended E0-E17 semantic aliases.  
Impact: The underlying RunLogs, metrics, replay identities, and experiment denominators were unchanged, but the filter was noisy and could invite a user to select a physical job identifier instead of a registered experiment.  
Likely Cause: Program job logs inherited `_program_job_experiment_batches`, while the separately normalized result-manifest row retained only its physical `experiment_id`.  
Attempts: Reproduced the issue against the full v3 program manifest, compared the normalized log and manifest records, and added a real loader regression assertion.  
Final Resolution: Result-manifest rows in the post-freeze `m3_eval/evidence_dashboard.py` now inherit the same semantic batch aliases as their parent program job. Dashboard tests pass 20/20, and fresh browser QA exposes only semantic experiment batches.  
Follow-Up: Keep filter-value tests over the combined metrics/logs/manifests source set; testing logs alone cannot detect manifest-only option pollution.

Date: 2026-07-14  
Task ID: M3-EXPANSION-001  
Feature ID: F-DASH-001 / STREAMLIT-LIFECYCLE-QA  
Error: Fresh browser QA first showed six Vega warnings per KPI render and then left Streamlit's visible status widget on `RUNNING...` after all content and server computation had finished.  
Impact: Values and evidence remained correct, but the browser surface appeared unfinished and accumulated stale accessibility-tree content during successive filter reruns.  
Likely Cause: `st.bar_chart` generated an empty stacking extent for the sparse KPI slice, and the Streamlit wrapper raised `SystemExit(0)` instead of returning through Streamlit's normal script lifecycle.  
Attempts: Confirmed zero application exceptions, captured the exact Vega warnings, measured zero server CPU while the status widget remained visible, and repeated the full five-dimensional browser flow after each isolated fix.  
Final Resolution: Replaced the convenience bar chart in the post-freeze evidence dashboard with an explicit zero-to-100 Vega-Lite bar specification and changed the Streamlit wrapper to call `main()` without raising `SystemExit`. Cold-start and five-filter reruns now finish with no visible Stop control, 0 console errors, and 0 console warnings; replay-key and case-id modes both passed.  
Follow-Up: Retain a real-browser smoke that waits for the Streamlit status widget to disappear and inspects console warnings, not only page text and unit tests.

Date: 2026-07-14  
Task ID: M3-EXPANSION-001  
Feature ID: F-INTEGRITY-001 / POST-FREEZE-DASHBOARD-ISOLATION  
Error: Re-running the strict result-integrity audit after browser fixes reported one frozen-file SHA mismatch for `m3_eval/dashboard.py`; all 10,526 audited main/derived/stability runs were otherwise complete.  
Impact: The model outputs and denominators were unchanged, but the formal audit correctly refused to pass while a path named in `blind_freeze_v3.json` differed from its frozen hash.  
Likely Cause: Presentation-only Dashboard improvements were applied directly to a source path that the blind freeze had included, even though that module is not imported by the experiment runners.  
Attempts: Did not rewrite the freeze or whitelist the mismatch. Recovered the exact 1,538-line frozen source from line-numbered pre-change session evidence, independently reconstructed it by reversing all 21 post-freeze patches, and required both methods to produce the same SHA256.  
Final Resolution: Restored `m3_eval/dashboard.py` byte-for-byte to 60,207 bytes and SHA256 `ce81b87225c42b17248e2c9b60c2e0fd59c05e32ca6ddde2db08c06bf5d47053`. Moved all enhanced presentation behavior to new, non-frozen `m3_eval/evidence_dashboard.py`, and pointed only the final Streamlit wrapper/tests at it. The targeted suite passes 57/57 and the strict integrity audit now passes with 65/65 frozen files, 0 errors, and 10,526 audited runs.  
Follow-Up: Treat every path listed in the blind freeze as immutable; all post-freeze reporting or Dashboard revisions must live under a new path with an explicit non-causal presentation boundary.

Date: 2026-07-14  
Task ID: M3-EXPANSION-001  
Feature ID: F-HARNESS-001 / STRICT-COMPLETION-AUDIT  
Error: Runpro final ledger validation rejected 20 stale `in progress` statuses, `final-audit.md` was still an empty template, and several control files still required PPT/DOCX despite the user's later explicit cancellation.  
Impact: Experiment evidence was unaffected, but the Harness could not truthfully support recovery or final handoff and might have produced a false incomplete/complete claim.  
Likely Cause: Long-running experiment work updated operational state selectively, while early Runpro templates and later scope changes were not reconciled across the full control plane.  
Attempts: Ran requirement lock, final ledger and final-audit validators; audited active specs/features/tasks/Runpro files; compared them with frozen experiment evidence and the latest user scope.  
Final Resolution: Updated all active control documents, marked 30 requirements satisfied and R26/R32/R33 blocked on human E17/final synthesis, excluded PPT/DOCX/ZIP from current scope, populated the interim final audit and reran all three strict validators successfully.  
Follow-Up: After human E17, reopen the three blocked requirements, rebuild final analysis, rerun every strict validator and only then create the local commit.

Date: 2026-07-14  
Task ID: M3-EXPANSION-001  
Feature ID: F-EXP-003 / CONTEXT-SEMANTIC-VALIDITY  
Error: A post-freeze design audit found that old v3 E9 generated whitespace-counted `ctxNN` filler instead of calibrated model-token workloads, while the OpenAI-compatible request path did not provide an effective dynamic context axis. Declared E9 2K produced a 6,310-token median; 4K/8K/16K collapsed to 8,192, with 0/30 parse success in each collapsed cell. E14 reused the same short six cases at every context label, yielding flat prompt medians (off 486.5; full_guard 230.5).  
Impact: Hash and artifact integrity remain valid, but old E9 cannot support long-context robustness claims and old E14 cannot support latency/throughput/GPU claims by context length. Their completed statuses were withdrawn; registry state is 15 completed, 3 running (E9/E14/E17), 0 failed. Any E17 input and final synthesis based on the old context claims must be rebuilt.  
Likely Cause: The fixture treated whitespace items as target tokens, the runtime assumed per-request `num_ctx` would be effective on the OpenAI-compatible path, and E14 varied only a configuration label rather than actual prompt workload.  
Attempts: Added a reproducible non-causal context audit; preserved old v3 unchanged; created `m3-qwen3-4b-ctx4k/8k/16k/32k` Modelfile aliases and verified them with real one-token probes. The 4K/8K/16K aliases capped at 4,096/8,192/16,384 prompt tokens, and the 32K alias recorded 20,156 tokens for a 20K workload.  
Final Resolution: Resolved through a separate correction chain. execution-r3 passed the calibrated prompt proof, two smoke gates, a 44-file freeze, E9 120/120 and E14 432 formal plus 48 warmup runs. The independent paired audit passed 144/144 matched paths and 480/480 unique first-step run keys; E9/E14 were atomically registered. Old v3 remains unchanged and diagnostic-only.  
Follow-Up: Cite only execution-r3 for context-axis claims. Continue to preserve old v3 as provenance and require a new revision for any future frozen-path change.

Date: 2026-07-15  
Task ID: M3-EXPANSION-001  
Feature ID: F-EXP-003 / CONTEXT-R2-SMOKE-QUALIFICATION  
Error: The first pre-freeze E14 Context Correction V2 smoke completed 48/48 case-runs but failed the unchanged matched-path gate at 16K: one benign control entered a three-step read/send chain and three controls emitted non-ToolCall application JSON. Only 12/16 off/full latency pairs were eligible.  
Impact: No formal run or freeze existed, so no formal denominator was contaminated. The complete failed smoke, 249+ telemetry samples and artifact hashes were retained; the gate correctly prevented a biased pure-Guard latency estimate.  
Likely Cause: Heterogeneous canonical benign tasks placed at the document midpoint lost the ToolCall envelope at 16K. This was a workload qualification failure, not a GPU, context-alias, concurrency, timeout or Provider-counter failure.  
Attempts: Preserved the failed smoke and all original prompt/fixture files; created workload revision r2 under new paths with four deterministic no-tool final-only controls placed at the 100% document position; regenerated and verified all 100 native prompt counts; retained the exact single-step/final/allow/raw-output matched gate without relaxation.  
Final Resolution: r2 E9 smoke passed 48/48 and all 15 checks; r2 E14 smoke passed 48/48, all 15 checks and 16/16 matched paths with zero parse/provider/timeout failures. `freeze_r2.json` binds 42 files, both smoke manifest hashes and 29 passing tests at SHA-256 `f40d8edba37c66fb5e982f27c05f8a0296c9296e344a007e5c9cd828190384c2`.  
Follow-Up: Keep every frozen path immutable while E9 120-run and E14 48-warmup/432-formal matrices execute; admit them only through the independent all-or-nothing context registrar.

Date: 2026-07-15  
Task ID: M3-EXPANSION-001  
Feature ID: F-HARNESS-001 / POST-PAUSE-VERIFICATION  
Error: A post-pause full `python -m pytest -q` attempt exceeded the 120-second command timebox before pytest emitted a final result.  
Impact: No test failure was established and no experiment evidence changed, but this attempt cannot replace the last completed full-suite result. The timeout process exited and left no pytest, experiment, Ollama model or GPU residency.  
Likely Cause: The complete suite now includes broader context, registrar, E17, analysis and browser-adjacent coverage than fits the short reporting-turn timebox.  
Attempts: Confirmed the process tree was empty, then ran the focused corrected-context runtime/runners, paired registrar, E17 corrected-source and final-analysis admission tests.  
Final Resolution: The focused chain passed 61/61 in 63.06 seconds. Harness and the interim report retain the last completed full-suite record of 293 passed / 1 skipped rather than narrating the timed-out attempt as a pass.  
Follow-Up: Before final delivery, rerun the complete suite with a longer timeout and record its actual final count; do not reuse the 120-second timebox.

Date: 2026-07-15  
Task ID: M3-EXPANSION-001  
Feature ID: F-EXP-003 / CONTEXT-R2-RUN-IDENTITY  
Error: E14 r2 completed 104/104 jobs, 432/432 formal and 48/48 warmup case-runs with zero job failures, but its post-run semantic gate failed `no_duplicate_run_key` and `matched_benign_paths_identical`. Across independent concurrency 1/2/4 jobs, 144 run keys each appeared three times, producing 288 duplicate first-step rows globally; every individual job remained duplicate-free.  
Impact: The model outputs, prompt-token proof and job evidence are retained, but the r2 E14 bundle is ineligible for registration and cannot support the pure-Guard latency estimand. E9 r2 remains independently valid but will not be paired with the failed E14 evidence.  
Likely Cause: `m3_core.run_batch._make_run_key` omitted the experiment/job namespace even though E14 intentionally repeats the same case, condition, model, seed and outer replicate at three offered concurrency levels. The matched-path grouper then merged three independent one-step runs and correctly reported them as `not_single_step`.  
Attempts: Reconstructed all 480 first-step identities, confirmed multiplicity `{3: 144, 1: 48}`, confirmed 0 within-job duplicate keys, and preserved the failed r2 manifest plus raw logs without mutation.  
Final Resolution: Resolved under execution revision r3. The stable run-key payload now includes a hashed experiment namespace; 49 focused pre-smoke tests, both 48-case smokes and the 44-file `freeze_r3.json` passed. E9 120/120 and E14 432 formal plus 48 warmups were rerun from scratch. The independent audit passed 144/144 matched paths and 480/480 globally unique first-step keys, and the paired atomic registrar moved the registry to 17 completed / 1 running / 0 failed.  
Follow-Up: Preserve failed r2 E14 unchanged and diagnostic-only. Never weaken the global uniqueness gate or splice r2/r3 denominators.

Date: 2026-07-15  
Task ID: M3-EXPANSION-001  
Feature ID: F-E17-001 / CORRECTED-SOURCE-EVIDENCE-TIER  
Error: The first corrected E17 source-index build rejected valid execution-r3 rows because the reader required a synthetic row-level evidence tier that the frozen formal runner never emitted.  
Impact: No frozen evidence or E17 human submission changed, but the corrected source index could not be built until the downstream admission contract matched the real formal-row schema.  
Likely Cause: The reader required `formal_context_correction_v2`, while real frozen rows correctly used the generic `formal_model` tier and were already bound to the correction through manifest, protocol and freeze hashes.  
Attempts: Rejected rewriting frozen rows or weakening source identity checks. Updated only the post-freeze E17 reader to accept the real tier after strict corrected-source checks, normalized a derived E17 tier in the copied view, and added a fixture matching the real schema.  
Final Resolution: Twenty-four focused E17 tests passed. The index rebuilt twice identically with SHA-256 `6d3baa721317b50d9dca82c958d5b0f47b23114066c9e2a42e922c8c512fd17d`, 12,704 logical runs, 0 duplicate runs/steps and 3,299 review items.  
Follow-Up: This repair does not satisfy the human-review gate; retain E17 at 0/2 humans until two independent real submissions pass.

Date: 2026-07-15  
Task ID: M3-EXPANSION-001  
Feature ID: F-HARNESS-001 / WINDOWS-BASH-PYTHON-PATH  
Error: Running `bash scripts/verify.sh` from the Windows desktop environment failed its Python-dependent checks because that Bash/WSL PATH did not contain a `python` executable. Harness-file and shell-syntax checks passed.  
Impact: The failed command is not evidence of a JSON, compile, test or registry defect, but it cannot be narrated as a passing end-to-end Harness run.  
Likely Cause: The workspace uses Windows PowerShell/Anaconda Python, while the invoked Bash environment is a separate WSL process without Python on PATH.  
Attempts: Re-ran the underlying checks through the configured Windows Python: JSON parsing, `compileall`, registry validation, 44-file freeze validation, corrected E17 source `--check`, 22 focused tests and four Runpro validators all passed.  
Final Resolution: Environment mismatch identified and stage checks completed natively. The Bash wrapper remains non-passing in this shell and the full test suite is still scheduled for the final E17 handoff.  
Follow-Up: At final delivery, use the configured Windows Python/PowerShell verification path or explicitly provision Python inside the Bash environment; record the actual complete-suite result.

Date: 2026-07-16  
Task ID: M3-EXPANSION-001  
Feature ID: F-HARNESS-001 / WINDOWS-NATIVE-VERIFIER  
Error: The first `scripts/verify.ps1` parse check failed because PowerShell parsed `$LASTEXITCODE:` as an invalid variable reference.  
Impact: Verification stopped before tests; experiment evidence and registry were unchanged.  
Likely Cause: A colon immediately after an unbraced variable name is interpreted as scope syntax.  
Attempts: Ran the PowerShell parser directly and isolated the single interpolation.  
Final Resolution: Replaced it with `${LASTEXITCODE}:`; PowerShell and Bash syntax checks then passed. The final verifier completed with 339 passed, 1 skipped and zero verification failures.  
Follow-Up: Keep native parser checks before executing long verification steps.

Date: 2026-07-16  
Task ID: M3-EXPANSION-001  
Feature ID: F-EVAL-001 / SYNTHETIC-FINAL-ANALYSIS-FIXTURE  
Error: The first full verifier reported seven final-analysis/report/statistics test failures because helper repositories reused the synthetic E17 source fixture without installing its synthetic loader outside the defining module.  
Impact: Production validators were not implicated, but the full suite could not pass.  
Likely Cause: A module-local autouse monkeypatch was assumed to follow a shared helper imported by three other test modules.  
Attempts: Reproduced the failures in the three affected modules and rejected changing the production E17 admission path.  
Final Resolution: Extracted a test-only loader installer and explicitly applied it in every module that uses the synthetic repository. Targeted tests passed 12/12; final suite passed 339/339 runnable tests.  
Follow-Up: Shared synthetic repositories must install their full test boundary explicitly rather than relying on the originating module's fixtures.

Date: 2026-07-16  
Task ID: M3-EXPANSION-001  
Feature ID: F-EXP-003 / E11-EXECUTION-FREEZE-DRIFT  
Error: The remaining full-suite failure showed the historical E11 amendment freeze no longer matched current `agent_runner`, `llm_client`, `run_batch`, `run_matrix` and RunLog-related runtime files.  
Impact: The prior E11 supplement could not be claimed as reproducible from the current checkout. Old evidence stayed intact and E11 remained registered only with its historical boundary until remediation.  
Likely Cause: Later context/runtime identity repairs correctly changed files that the older post-hoc amendment had hash-bound.  
Attempts: Rejected overwriting the old freeze, restoring obsolete runtime, weakening the validator or copying old logs into a new bundle.  
Final Resolution: Preserved legacy freeze/results, created execution-r2 protocol and 31-artifact freeze `ceb320...ba37`, then reran 8/8 smoke and 48/48 formal from empty active directories. Analysis, original-resolution figure QA, registrar apply and 32 focused tests passed.  
Follow-Up: Treat the legacy result directories as diagnostic provenance only; any mutation of an r2-bound file requires another execution revision and complete affected rerun.

Date: 2026-07-16  
Task ID: M3-EXPANSION-001  
Feature ID: F-EVAL-001 / HISTORICAL-V3-CURRENT-SOURCE-COMPATIBILITY  
Error: A pause-point read-only audit scanned 10,526 historical v3 logical runs but found eight current source files no longer match the old blind-freeze hashes.  
Impact: Historical output provenance remains available, but the current checkout cannot be represented as a clean reproduction of the original v3 freeze.  
Likely Cause: Legitimate post-v3 repairs changed E17 review, model/registry orchestration, Agent runtime and RunLog schema.  
Attempts: Re-ran the audit with the exact `program_manifest_final_v3.json`, `blind_freeze_v3.json` and artifact root after an initial invocation used default historical paths.  
Final Resolution: Stored the failing compatibility audit unchanged at `agent/audits/blind_v3_current_source_compatibility_2026-07-16.*` and documented the eight paths. Current-runtime claims instead use Context execution-r3 and E11 execution-r2 freezes.  
Follow-Up: Never state that all old v3 frozen source hashes match the current checkout; preserve the historical freeze and avoid retroactive rehashing.

Date: 2026-07-16  
Task ID: M3-EXPANSION-001  
Feature ID: F-HARNESS-001 / E17-CLI-REJECTION  
Error: The E17 registrar correctly rejected a pending manifest, but the command-line entry point exposed the expected `E17RegistrationError` as a full Python traceback with exit code 1.  
Impact: Registry and experiment evidence were safe, but the public recovery command was noisy and looked like an internal crash rather than an intentional admission gate.  
Likely Cause: `main()` did not translate the domain exception into an argparse rejection, unlike the final-analysis CLI.  
Attempts: Confirmed the registrar made no write and verified the script was not bound by the active context-r3 or E11-r2 freezes.  
Final Resolution: `main()` now catches `E17RegistrationError` and exits 2 with a concise message. A new CLI regression test verifies no traceback; focused tests passed 27/27 and the complete verifier passed 340 tests with one skip.  
Follow-Up: Preserve exit 2 as the expected incomplete-input contract until valid human evidence exists; after humans, dry-run must return exit 0 before apply.

Date: 2026-07-16  
Task ID: M3-EXPANSION-001  
Feature ID: F-HARNESS-001 / RUNPRO-90-PLUS-BLOCKED-SEMANTICS  
Error: A one-off audit wrapper incorrectly expected `validate_final_audit.py --require-90-plus` to reject a truthful `Blocked` final audit and raised its own exception when the validator returned success.  
Impact: Only the diagnostic wrapper failed; no Harness state, experiment evidence or validator changed.  
Likely Cause: The hypothesis overlooked that the 90+ score-band enforcement is intentionally inside the ready-state branch, while Blocked audits are validated through their explicit Blocking Issues section.  
Attempts: Read the validator's score extraction and final decision branch, then reran the command directly.  
Final Resolution: Confirmed `Final audit OK: Blocked` is correct behavior: it validates a well-formed blocker record without claiming 90+ readiness. Withdrew the defect hypothesis and continued the remaining checks.  
Follow-Up: Inspect decision-branch semantics before treating an intentionally accepted blocked state as a readiness bypass.

Date: 2026-07-16  
Task ID: M3-EXPANSION-001  
Feature ID: F-HARNESS-001 / HARNESS-DIRECTORY-SEPARATION  
Error: The first post-migration invocation of `harness/scripts/verify.ps1` reached the full `pytest -q` stage but did not finish within the interactive verification window and was terminated together with its child processes.  
Impact: No experiment or service was started and no failure was hidden, but this invocation cannot be cited as a completed full-suite pass.  
Likely Cause: The complete 340-test repository suite contains long experiment-evidence tests; a smaller E17-only run had shown the same long runtime before the directory migration.  
Attempts: Confirmed the pytest process was consuming CPU rather than deadlocked, waited several additional cycles, then terminated the exact verifier/test process tree.  
Final Resolution: Ran repository-boundary, JSON, PowerShell/Bash syntax, deterministic packet regeneration and 11 focused layout/E17 tests; all passed. The earlier 340-pass snapshot remains historical evidence only, and a new uninterrupted full run is still required before final commit.  
Follow-Up: Run `harness/scripts/verify.ps1` without an interactive timebox after both human files are available and before the final local commit.

Date: 2026-07-16  
Task ID: M3-EXPANSION-001  
Feature ID: F-HARNESS-001 / FINAL-PYTEST-ORPHAN-PROCESS  
Error: Two terminated shell cells left their child `pytest` processes alive, so the original aggregate verifier appeared to wait indefinitely with unchanged CPU time.  
Impact: No test failure, experiment mutation or service start occurred, but those aggregate invocations cannot be cited as completed verification runs.  
Likely Cause: Terminating the orchestration cell stopped its parent PowerShell but did not terminate already spawned Python children on Windows.  
Attempts: Checked process identity, command lines, CPU deltas and thread wait state; then terminated only the two orphaned pytest PIDs.  
Final Resolution: Re-ran every collected `test_*.py` file independently with fail-fast semantics. All 50 test files completed: 343 passed, 1 skipped, 0 failed.  
Follow-Up: When stopping a Windows verification cell, audit and explicitly terminate its child process tree before starting another full test run. The subsequent authoritative aggregate Harness verifier completed with 347 passed, 1 skipped and `Verification failed=0`.

Date: 2026-07-16
Task ID: M3-EXPANSION-001
Feature ID: F-EXP-004 / V2-REPORT-LAYER-COMPATIBILITY
Error: The frozen analyzer completed the 2,160-tuple audit but stopped first on a `value`/`estimate` serialization mismatch and then because its main manifest omitted the Dashboard-required `kind=figure_manifest` discriminator. A later visual repair attempt initially read a UTF-8 BOM as part of the recovery CSV header.
Impact: Formal RunLogs, counts and metrics were already complete and unchanged; only result serialization, Dashboard anchoring and chart presentation were blocked.
Likely Cause: The frozen analysis script and stable statistics/Dashboard contracts used different report-field conventions; CSV output uses UTF-8 with BOM.
Attempts: Rejected editing the frozen analyzer, manually changing acceptance CSV values or weakening Dashboard validation. Added an external hashed wrapper, then changed its CSV reader to `utf-8-sig` after reproducing the BOM header.
Final Resolution: The wrapper aliases `value` to `estimate`, adds the artifact kind, re-renders two charts from unchanged CSV values, refreshes hashes and reruns the original Dashboard loader. Final validation is 12/12 acceptance with 10 metric rows, 3,780 logs, 4 figures and zero warnings.
Follow-Up: Keep execution/metric freezes separate from report adapters and validate both schema compatibility and rendered charts before final handoff.

Date: 2026-07-16
Task ID: M3-EXPANSION-001
Feature ID: F-EXP-004 / HISTORICAL-FREEZE-COMPATIBILITY
Error: The first final Harness verifier correctly rejected the current checkout against historical E11 execution-r2 and context/E17 execution-r3 source hashes after remediation changed six/seven bound files.
Impact: One unit test and the old corrected-source rebuild check failed; V2 formal runs, its 12/12 acceptance result and all historical result files remained intact.
Likely Cause: The verifier still treated historical current-runtime freezes as if no later engineering revision could exist.
Attempts: Rejected overwriting old freeze hashes, silently skipping checks or rerunning unrelated historical human review.
Final Resolution: Added an exact compatibility declaration and verifier. It recursively verifies old evidence roots, permits only the declared old/current hash pairs, and independently verifies all 27 current V2 freeze records. The final Harness run passed 361 tests with one skip and zero verification failures.
Follow-Up: Every later runtime revision must either match V2 or add a new immutable current-evidence freeze plus an exact compatibility revision; never mutate historical freezes.

Date: 2026-07-16
Task ID: M3-EXPANSION-001
Feature ID: F-EXP-004 / GIT-BYTE-EXACT-FREEZE
Error: Initial Git staging under the machine-wide `core.autocrlf=true` normalized mixed line endings in 11 of 27 V2 source records, so the working-tree freeze passed while the index bytes would not.
Impact: A commit made in that state would fail source-hash verification after checkout even though all runtime results were valid.
Likely Cause: Several pre-existing files contain mixed LF/CRLF bytes and Git's default text clean filter silently normalized them.
Attempts: Rejected changing frozen hashes after execution or normalizing executed source files post hoc.
Final Resolution: Added path-scoped `.gitattributes -text`, re-staged the exact working bytes, and compared index blobs directly. All 27 source records and 56 result/figure/raw evidence references now match their declared SHA-256 values.
Follow-Up: Any new hash-bound evidence root must add byte-exact Git attributes before freezing and run the index-blob audit before commit.
