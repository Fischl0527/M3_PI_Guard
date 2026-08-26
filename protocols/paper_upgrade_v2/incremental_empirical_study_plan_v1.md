# M3-PI Guard Incremental Empirical Study v1

## Material Passport

- Origin Skill: `academic-research-suite / experiment-agent`
- Mode: `run`
- Frozen date: 2026-08-26
- Status: `DESIGN FROZEN / EXECUTION PENDING`
- Feature: `F-PAPER-002`

## Scientific scope

This prospective layer keeps all historical records immutable and adds five
study-specific evidence sets.  It tests authorization and runtime behavior; it
does not reinstate a first/only/SOTA or leading-defense claim.

The registered questions are:

1. How do prompt hardening and the policy-versus-full runtime modules affect
   unsafe effect, benign-tool completion and operational burden separately and
   jointly?
2. When proposition text, value, policy and serialized block position are held
   fixed, how does changing only the declared source authority alter proposals
   and Guard decisions?
3. Are the factor-effect directions consistent in a representative cohort, an
   explicitly outcome-enriched challenge cohort and DeepSeek V4 Flash?
4. Among tasks with no unsafe effect through query 200, how many first unsafe
   effects are observed by query 500?

## Registered studies

| ID | Cohort | Cells | Planned API rows/queries | Claim boundary |
|---|---|---:|---:|---|
| E1 `factorial` | frozen representative 180 | prompt 2 × modules 2 | 720 Pro rows | paired representative estimate |
| E2 `provenance` | 60 controlled base tasks × source 2 | modules 2 | 240 Pro rows + 480 offline decisions | controlled derived benchmark only |
| E3 `challenge` | 60 prior-unsafe attacks | prompt 2 × modules 2 | 240 Pro rows | outcome-enriched conditional rate |
| E4 `flash` | frozen nested 90 | prompt 2 × modules 2 | 360 Flash rows | same-provider model replication |
| E5 `adaptive-tail` | 12 B200 survivors | q201–q500 | ≤3,600 Pro queries | survivor-conditional tail only |

The factor cells are fixed as follows:

| Cell | Condition profile | Prompt factor | Module factor |
|---|---|---|---|
| `policy_normal` | `m3_policy_only` | normal | policy |
| `policy_safe` | `m3_policy_safe_prompt` | safe | policy |
| `full_normal` | `m3_full_normal_prompt` | normal | full |
| `full_safe` | `m3_full` | safe | full |

All regular rows use `auto_compiled`.  E2 uses only the normal-prompt policy and
full profiles so source authority and module factor are the registered axes.
Historical `m3_policy_only` and `m3_full` semantics and records are not changed.

## Selection rules

- E1 is exactly the already-frozen 180-case `lean-v1` main selection.
- E4 is exactly the 90 cases marked `gemini_subset` in that selection; the old
  name is only a nesting marker and no Gemini execution occurs.
- E3 is selected from Public primary attack cases with an unsafe effect under
  no defense, VIGIL, policy-only or full.  Selection first covers AgentDojo
  suite or M3-v2 attack family, then orders by the number of prior unsafe cells
  descending, then by a fixed SHA-256 rank.  `prior_outcome_selected=true` is
  mandatory for every E3 row.  The four-condition candidate audit is 117
  AgentDojo and 55 M3-v2 cases.  The previously reported 127/71 counts refer to
  the broader any-of-six Public condition audit and are not used for selection.
- E2 has 30 AgentDojo-derived and 30 M3-v2-derived controlled base tasks, split
  30 supporting/30 competing across six authority targets.  Each trusted and
  untrusted pair has the same proposition text, value, policy, tool schema and
  `context_block_index`; only `source_authority` changes.
- E5 includes all four A2 B200 survivors and four each from A1/A3 by fixed
  SHA-256 rank.  Attack text is not an input to selection.  This is not a full
  40-task B500 curve.

## Endpoints and statistics

Unsafe-effect rate and benign-tool task-completion rate are co-primary for E1.
Operational failure, unsafe-or-failure, ASK, DENY, latency, token and cost are
secondary.  E2 separately reports deterministic Guard replay and end-to-end
system behavior.

- Cell proportions: raw numerator/denominator and Wilson 95% CI.
- Simple paired binary contrasts: exact McNemar.
- E1 factor main effects and difference-in-differences: 10,000 case-paired
  bootstrap replicates.  Module, prompt and interaction are Holm-corrected
  within each co-primary endpoint family.
- E2 source, module and source×module form one separate correction family.
- E3, E4 and E5 are challenge/replication/sensitivity analyses and create no
  additional significance family.
- Every planned row remains in ITT.  Failures are reported separately and also
  through an unsafe-or-failure sensitivity endpoint.

## Execution and recovery boundary

The only shared command is:

```text
F:\robot\Anaconda3\python.exe -B -m experiments.paper_v2.incremental_study_runner_v1 --study factorial|provenance|challenge|flash|adaptive-tail --canary-only|--resume-pending-only --config config/project.local.env
```

Each regular study begins with eight terminal-prefix rows.  E1/E4 cover every
factor cell once on attack and once on benign-tool.  E2 covers source × module ×
supporting/competing.  E3 is attack-only by construction and covers two cases
per factor cell.  Adaptive qualification uses five new queries on each of two
tail tasks.

Expansion requires exact returned model identity, complete local request ID,
payload digest and official response ID, zero online evaluator/gold fields,
zero provider tools and external effects, at least six parseable regular
prefixes, and no repeated runner/contract error.  There is no automatic retry
or cross-model fallback.  A response-bearing parse/refusal/max-step failure is
terminal ITT.  Only a response-less engineering/transport failure may receive a
new attempt after the cause is fixed, and successful rows are never replayed.

Hard fuses are CNY 8 for all Pro regular studies, CNY 3 for Flash, CNY 5 for
adaptive and CNY 16 globally.  All effects are isolated simulation; real email,
payment, browser, code execution and production API operations remain disabled.

## Artifacts

Machine-frozen plans live in
`protocols/paper_upgrade_v2/incremental_empirical_v1/`.  Each study writes one
raw JSONL, one compact analysis JSON and its paper tables/figures beneath
`outputs/experiments/incremental_empirical_v1/<study>/`.  Content-free request
traces and the minimal append-only run ledger are internal runtime evidence,
not a recursive historical hash package.

The protocol must not be described as independently blinded or cross-provider.
Author names, affiliations, CRediT, funding and declarations remain blank.
