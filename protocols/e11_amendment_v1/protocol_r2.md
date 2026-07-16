# E11 Post-hoc Amendment v1 — Execution Revision r2

## Status and claim boundary

- Protocol ID remains `E11_POSTHOC_AMENDMENT_V1`.
- Research question, 24 cases, four patterns, two conditions, model, thresholds,
  estimand, and independent denominator are unchanged from `protocol.md`.
- `execution_revision=r2` exists only because the runtime changed after the
  revision-2 visualization execution was frozen.
- The original `freeze.json` and its result directories are preserved as
  historical diagnostic provenance. They are not overwritten or represented
  as current-runtime evidence.
- The v3 blind freeze is retained as a hash-bound historical reference. Its
  internal historical runtime hashes are not compared with current source.

## Fixed rerun contract

`freeze_r2.json` must be created before any r2 model execution and must bind
this amendment, the original protocol, cases, fixtures, the historical freeze,
the historical v3 freeze file, E13 thresholds, all current runtime/scoring
files, runner, analyzer, registrar, final-analysis validator, and freeze
builder. Any later drift invalidates the r2 execution.

After freezing, run a fresh eight-logical-run Ollama smoke gate followed by a
fresh 48-logical-run formal matrix using `qwen3:4b-instruct`. Do not seed or
resume r2 from the historical result directories. The analyzer must require
`execution_revision=r2`; the resulting supplement remains post-hoc,
`pre_registered=false`, and excluded from the original E11 denominator.

## Commands

```powershell
python scripts/freeze_e11_amendment_r2.py
python scripts/e11_amendment_runner.py plan
python scripts/e11_amendment_runner.py run --phase smoke --backend ollama --model qwen3:4b-instruct --output-root outputs/experiments/E11_posthoc_amendment_v1_runs
python scripts/e11_amendment_runner.py run --phase formal --backend ollama --model qwen3:4b-instruct --output-root outputs/experiments/E11_posthoc_amendment_v1_runs
python scripts/e11_amendment_analyzer.py --run-root outputs/experiments/E11_posthoc_amendment_v1_runs --output-dir outputs/experiments/E11_posthoc_amendment_v1
```
