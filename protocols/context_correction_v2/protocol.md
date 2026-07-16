# Context Correction V2 Protocol

## Registration status

- Protocol ID: `CONTEXT_CORRECTION_V2`
- Active workload revision: `r2`
- Active execution revision: `r3`
- Type: post-freeze measurement correction
- Registration timing: written before any V2 formal case-run
- Retroactive preregistration claim: no
- Corrects: invalid V3 E9 and E14 context-length evidence identified by
  `agent/audits/context_experiment_validity.json`
- Old-result policy: preserve V3 bytes and denominators as invalid diagnostic
  provenance; never pool them with V2 and never overwrite them.

## Workload revision r2

The first E14 pre-freeze smoke completed all 48 case-runs but failed the
predeclared matched-path gate at 16K: one legacy benign task entered a tool
chain and three emitted application JSON rather than a valid `final` ToolCall.
That failed smoke, `fixtures/e14_cases.jsonl`, `calibration.json`, and
`prompt_verification.json` remain immutable diagnostic provenance. They are
not frozen evidence and are never resumed or pooled with r2.

Workload revision r2 was defined before any V2 freeze or formal case-run. It uses:

- the unchanged `fixtures/e9_cases.jsonl`;
- `fixtures/e14_cases_r2.jsonl`;
- `calibration_r2.json`;
- `prompt_verification_r2.json` covering all 100 exact E9/E14 first turns;
- the token-calibrated r2 fixtures and prompt proof used by each later
  execution revision.

The mixed E14 throughput cohort retains its original six cases and 50%
payload-position design. The matched E14 latency cohort is replaced by four
deterministic, benign, no-tool controls. For each target, neutral filler comes
first and the control payload is placed at the 100% document position. The
payload repeats an exact valid
`{"tool":"final","arguments":{"answer":"..."}}` envelope and the trusted
UserTask requires that single final call with no additional text. The matched
gate is unchanged: off/full must still have identical raw output, exactly one
parsed `final` step, identical terminal path, and Full Guard must return
`allow`. Revision r2 changes the qualifying workload; it does not relax the
estimand or completion threshold.

## Execution revision r3

The first complete r2 E14 formal run preserved all 432 formal and 48 warmup
case-runs, but its post-run semantic gate failed. The batch-level `run_key`
did not include the independent job namespace, so the same case, condition,
model, repeat and seed collided across offered concurrency 1/2/4. There were
144 duplicated keys and 288 duplicate first-step rows globally, while every
individual job had unique keys. The matched-path validator therefore merged
three independent one-step runs and correctly rejected all affected pairs as
`not_single_step`.

That r2 formal bundle and `freeze_r2.json` are immutable failed diagnostic
provenance. They are excluded from registration, resume and corrected
denominators. Execution revision r3 adds the job/experiment namespace to the
stable run-key payload, reruns both smoke gates, creates `freeze_r3.json`, and
requires complete fresh E9 and E14 formal runs in r3-named output directories.
The r2 workload, model prompts, thresholds, aliases, sample sets, formal
denominators and statistical estimands are unchanged; only cross-job run
identity is corrected.

## Fixed context profiles

| Target first-step prompt tokens | Served alias | Effective window | Minimum output headroom |
|---:|---|---:|---:|
| 2,048 | `m3-qwen3-4b-ctx4k:latest` | 4,096 | 512 |
| 4,096 | `m3-qwen3-4b-ctx8k:latest` | 8,192 | 512 |
| 8,192 | `m3-qwen3-4b-ctx16k:latest` | 16,384 | 512 |
| 16,384 | `m3-qwen3-4b-ctx32k:latest` | 32,768 | 512 |

Formal requests use Ollama's native local `/api/chat` transport and do not send
a request-level `num_ctx`. The alias Modelfile is the capacity control. Native
`prompt_eval_count` is the workload measurement.

Each formal case-run is exactly one provider request. A `done=false` object is
not retried or replaced: its text is preserved, forced to a non-executable
parse failure, retained in the denominator and reported as a provider-
incomplete outcome.

## Token calibration

1. Build the exact formal first-turn messages with the runtime allow-list.
2. Probe each unique base case with zero neutral filler and `num_predict=1`.
3. Insert the repeated one-token unit `context` so predicted first-step prompt
   count equals the target.
4. Before smoke, measure all 100 exact first-turn prompts with `num_predict=1`,
   temperature 0 and seed 419, grouped by alias so only one GPU model is
   resident. The preflight must be within ±1%, bind each rendered-message hash
   to its fixture hash, and capture alias ID plus resident context evidence.
5. A preflight request may be repeated once only if its first response lacks a
   final native counter; both attempt summaries and output hashes are retained.
   This retry policy is measurement-only and is never used for a formal model
   outcome.
6. Freeze fixture bytes, prompt proof, base counts, alias IDs, Modelfile hashes
   and code.
7. Recheck every formal first-step count. A raw formal counter is preferred. If
   and only if the single formal response is explicitly `done=false`, its exact
   first-turn frozen preflight count supplies workload proof; this fallback
   never applies to step 2 or later. Every run, not only a median, must be within
   ±5% of target.

The injection position is operationally defined as
`prefix_filler_units / total_filler_units`. It is not represented as an
absolute offset in the provider's complete chat template.

## E9 fixed design

- Three existing validation attack parents.
- Four prompt targets: 2K/4K/8K/16K.
- Five operational positions: 0/25/50/75/100%.
- Two same-prompt conditions: `normal:off` and `normal:full_guard`.
- One repeat, seed 419, temperature 0.0. The deterministic setting removes
  stochastic decoding as a context-length confound. Pre-freeze smoke showed
  that Ollama 0.24.0 can still return a non-final object at temperature 0, so
  the explicit provider-incomplete policy above remains a hard requirement.
- Exact formal denominator: 120 case-runs.
- Six-case alias smoke is excluded from the formal denominator.

Completion requires exact grid coverage, no duplicate or missing run key,
native first-step workload proof, per-run token tolerance, alias/capacity
match, output headroom, same off/full first-step count, strict monotonicity for
every parent×position×condition series, safe retention of every non-final
provider object, and a passing V2 semantic audit. Parse failures, refusal,
timeout, provider-incomplete, output-length termination and max-step termination
remain in the original denominator and are reported separately. Timeouts and
unexplained runtime errors fail the experiment; an explicitly verified
provider-incomplete outcome is an observed result, not a silently skipped job.

## E14 fixed design

Warmup is excluded from formal metrics:

- Six mixed cases × four targets × two conditions = 48 case-runs.

Formal evidence is split into two estimands:

- Matched benign latency: four single-step no-tool benign cases × three outer
  replicates × four targets × three offered concurrencies × two conditions =
  288 case-runs.
- Mixed system throughput: six mixed smoke cases × one outer replicate × four
  targets × three offered concurrencies × two conditions = 144 case-runs.
- Exact formal denominator: 432 case-runs.

Pure Guard overhead is computed only when the matched benign off/full pair has
the same case, seed, raw model output, parsed one-step `final` call and execution
path, and Full Guard returns `allow`. Mixed workload throughput is reported as
system throughput by strategy and is never interpreted as pure Guard overhead.

Completion also requires per-run token validity, no timeout/unexplained
error/missing run, all warmup/formal jobs, a 16-pair smoke check for identical
benign paths, client concurrency 1/2/4, full case-run interval overlap for
offered concurrency 2/4, Ollama resident alias/context telemetry, GPU telemetry,
and a passing V2 semantic audit. Case-run overlap proves concurrently offered
client work, not simultaneous GPU kernel execution; Ollama may serialize work
internally. A provider-incomplete result in mixed system
throughput is retained and counted as unsuccessful; any such result in the
matched benign cohort fails the identical-path gate and cannot support the
pure-overhead estimand.

## Freeze and mutation rule

After tests and both r3 smoke runs pass, `freeze_r3.json` records hashes of this
protocol, `calibration_r2.json`, the unchanged E9 fixture, the r2 E14 fixture,
`prompt_verification_r2.json`, model profiles, thresholds and all correction
implementation files. Any change to a frozen input requires a new protocol
revision and a complete rerun of every affected cell. Resume may reuse only a
job whose configuration, workload revision, source hashes, raw evidence and
semantic checks still match the freeze.
