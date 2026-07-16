# Remediation Log

## Issue: requirement-ledger interim status rejected

## Impact

Strict Gate 3 ledger validation failed before implementation.

## Likely Cause

The validator treats `pending` as a placeholder while the state-file guide lists it as a recommended execution status.

## Options Considered

Bypass validation; change the validator; use a meaningful non-placeholder interim status.

## Chosen Fix

Use `in progress` for active requirements and keep the upstream validator unchanged.

## Validation Result

Interim validation passed at execution start; the ledger was later migrated to final statuses during the 2026-07-14 strict completion audit.

## Remaining Risk

None after a successful rerun.

## Issue: Harness state drifted behind completed experiment work

## Impact

Requirement-ledger final validation rejected 20 stale `in progress` items, the final audit was an empty template, and current-scope documents still treated PPT/DOCX as mandatory despite explicit user cancellation.

## Likely Cause

Long experiment execution updated runtime evidence and `agent/progress.md` but not every Runpro/Harness control file; later user scope changes were recorded only in the active task state.

## Options Considered

Ignore the generic validators; mark everything ready; or reconcile every active control file with frozen evidence and preserve the human E17 blocker.

## Chosen Fix

Update the requirement lock, project route, specs, feature/task state, ledger, checklist, handoff, interim final audit and summary. Mark E0-E16 and independent infrastructure satisfied, while keeping R26/R32/R33 blocked on real human E17 and final synthesis.

## Validation Result

Requirement lock, final-status ledger and blocked final-audit validators passed at that checkpoint; a later semantic-validity audit superseded the registry statement and reopened E9/E14.

## Remaining Risk

Superseded by the context-validity issue below: E9/E14 are now internal recoverable blockers, while two independent human reviews remain externally required.

## Issue: E9/E14 context axis failed post-freeze semantic validity

## Impact

Old v3 is artifact-complete but cannot support E9 long-context robustness or E14 performance-by-context claims. The registry was corrected to 15 completed / 3 running / 0 failed, and E17/final synthesis must be rebuilt after corrected evidence.

## Likely Cause

E9 calibrated by whitespace items rather than model tokens and relied on an ineffective per-request context setting; E14 changed context labels without changing the six-case prompt workload.

## Options Considered

Relabel or overwrite v3; report parse collapse as safety; ignore the axis defect; or preserve v3 and run a separately frozen corrected protocol.

## Chosen Fix

Preserve v3 as diagnostic provenance. Create token-calibrated E9/E14 v2 under a new protocol/freeze using probe-verified 4K/8K/16K/32K Modelfile aliases, rerun every affected cell, and rebuild E17 inputs before human review.

## Validation Result

The audit reproducibly fails the old evidence. The corrected execution-r3 later completed both 48-run smoke gates, a 44-file freeze, E9 120/120, E14 432 formal plus 48 warmup runs, and the independent paired audit. E9/E14 were atomically registered; the old bundles remain unchanged.

## Remaining Risk

Do not cite old E9/E14 context conclusions. Corrected claims must use execution-r3 identity. E17 still requires two independent human reviews.

## Issue: E14 r2 reused run keys across concurrency jobs

## Impact

All 104 jobs and all 480 E14 r2 case-runs persisted successfully, but the final semantic gate rejected the bundle. It is excluded from registration and corrected denominators.

## Likely Cause

The stable run-key payload omitted the independent experiment/job namespace. Because E14 repeats the same case, condition, model, seed and outer replicate at concurrency 1/2/4, 144 keys collided three times; the matched-path validator then merged independent one-step paths.

## Options Considered

We considered weakening the validator to use a composite key, post-processing the existing logs, or fixing the producer and rerunning. Weakening or rewriting evidence after observing the failure would undermine the preregistered uniqueness gate.

## Chosen Fix

Preserve r2 unchanged. Add the experiment namespace to the producer-level run key, expand the frozen unit gate to cover cross-experiment uniqueness, define execution revision r3 with new output and freeze paths, and fully rerun both corrected experiments before paired admission.

## Validation Result

The diagnosis is complete: 480 first-step rows contain 192 unique raw keys, with 144 keys repeated three times and no within-job duplicates. execution-r3 added the experiment namespace at the producer, passed 49 focused pre-smoke tests, two 48-run smoke gates and a 44-file freeze, then fully reran E9 120/120 and E14 432 formal plus 48 warmups. The independent audit passed 144/144 matched paths and 480/480 unique first-step keys; the atomic registrar completed with registry state 17/1/0.

## Remaining Risk

The failed r2 E14 evidence remains diagnostic-only and must never be relabeled. Any future mutation of the 44 frozen r3 files requires a new revision and affected-cell rerun.

## Issue: E17 corrected-source reader required a synthetic evidence tier

## Impact

The first corrected E17 source-index build rejected valid r3 rows even though the source manifest, correction protocol and freeze hashes all passed.

## Likely Cause

The downstream E17 admission reader required row-level `evidence_tier=formal_context_correction_v2`, while real frozen model rows correctly used the generic formal tier `formal_model`. The specialized value had never been emitted by the frozen runner.

## Options Considered

Rewrite frozen rows, weaken all source checks, or accept the real formal tier only after strict manifest/protocol/freeze admission and normalize it in the derived E17 copy.

## Chosen Fix

Keep frozen evidence immutable. Update only the post-freeze E17 reader to accept `formal_model` (and the legacy specialized tier) after the corrected source identity checks, then add derived field `e17_evidence_tier=formal_context_correction_v2` to the normalized E17 view.

## Validation Result

Twenty-four focused E17 tests passed. The source index rebuilt twice byte-identically with SHA-256 `6d3baa721317b50d9dca82c958d5b0f47b23114066c9e2a42e922c8c512fd17d`, 12,704 logical runs, 0 duplicate runs/steps and 3,299 review items.

## Remaining Risk

No source-reader repair satisfies the human-review gate. Two independent human E17 submissions are still required.

## Issue: Windows verification was not a single reliable command

## Impact

The Bash wrapper could not discover Windows Python from WSL, while the initial PowerShell verifier had one parser error. The Harness therefore lacked a truthful native one-command check.

## Chosen Fix

Added `scripts/verify.ps1` and `scripts/test.ps1`, made the Bash wrappers resolve explicit Python, native Windows Python through `where.exe`/`wslpath`, or `python3`, and retained every failed exit code.

## Validation Result

PowerShell and Bash syntax passed. The final native verifier passed Harness/JSON/compile/registry/E17 checks and 339 tests with one explicit skip.

## Remaining Risk

The final delivery must rerun the same verifier after E17 and final-analysis generation; a pause-point pass is not a final-delivery pass.

## Issue: E11 historical freeze drifted from the repaired runtime

## Impact

The old post-hoc supplement was internally historical but could not be reproduced by current source. Rewriting the freeze or weakening hash checks would erase the provenance boundary.

## Options Considered

Restore obsolete runtime, overwrite the legacy freeze, admit old logs under a new hash, or create a new execution revision and fully rerun the affected calls.

## Chosen Fix

Preserve the legacy freeze and rename both old active result directories as execution-r1 diagnostic provenance. Add `protocol_r2.md`, a non-overwriting `freeze_r2.json`, execution-revision metadata and strict downstream admission. Rerun all 8 smoke and 48 formal logical runs from empty active directories.

## Validation Result

Freeze SHA is `ceb320a915d301d6658b5caa9b662cb2ed13e24c63ec5d79f8ff7caa9ad0ba37`. Smoke and formal matrices completed 8/8 and 48/48; analysis and 2070x1188 figure QA passed; registry apply preserved the original E11 primary manifest; full verifier passed 339 tests.

## Remaining Risk

E11 remains a post-hoc, independently denominated supplement. Its full-Guard memory-to-file Recall is 25% despite ASR 0/6, so absence of observed success must not be described as universal detection.

## Issue: Old v3 freeze no longer describes the current checkout

## Impact

A current-source compatibility audit found eight old freeze-bound source hash mismatches even though all 10,526 historical logical runs remained readable.

## Chosen Fix

Do not mutate old evidence or its freeze. Store the failing compatibility audit and route current-runtime claims through later revision freezes that bind the repaired code.

## Validation Result

The audit failure is deterministic and lists the exact eight paths. Context execution-r3 independently re-audits cleanly with fingerprint `296271...d5e`; E11 execution-r2 freeze check also passes.

## Remaining Risk

Historical v3 effect tables can be cited only with their historical provenance and disclosed compatibility limitation. Final synthesis must not claim the old blind freeze is clean against the current checkout.

## Issue: Expected E17 rejection looked like an internal crash

## Impact

The registrar protected the registry but printed a traceback when the manifest was still pending, weakening the Harness recovery experience.

## Chosen Fix

Translate `E17RegistrationError` at the CLI boundary into an argparse exit-2 rejection while leaving the programmatic exception and all admission checks unchanged. Add a regression that asserts the pending manifest is rejected without invoking execution, writing the registry, or printing a traceback.

## Validation Result

Focused E17 registrar/final-analysis tests passed 27/27. Live registrar rejection is exit 2 with a concise message. Final-analysis validate-only also exits 2, and `final_analysis/` is absent before and after. The complete Windows verifier passes 340 tests, one skip and zero failures.

## Remaining Risk

This improves recovery behavior but cannot satisfy E17. Two independent human reviews remain the sole external input gate.
