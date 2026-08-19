# Lean Empirical Study Plan

Status: active owner-approved paper-v2 plan (2026-08-19)

## Research questions

1. How do online authorization regimes change unsafe effect, task completion,
   and ASK/DENY burden?
2. Does M3-full add benefit beyond policy-only, and at what operational cost?
3. Are the effects stable across AgentDojo, M3-v2, models/providers, and the
   already completed adaptive budgets 50/200?

## Fixed studies

### DeepSeek Pro authorization study

- 180 cases: 100 attack, 60 benign-tool, 20 benign-no-tool.
- Main cells: policy-only/full crossed with auto_compiled/exact_gold (720 rows).
- Nested 60-case uncertainty subset: M3-full under broad, underspecified and
  conflicting (180 rows).
- Total: 900 rows.

### Gemini compact validation

- Nested 90 cases: 50 attack, 30 benign-tool, 10 benign-no-tool.
- Cells: structural-auto, policy-auto, full-auto, policy-exact, full-exact.
- Total: 450 rows; first six are the non-repeated formal prefix.
- Official free tier only; USD paid ceiling 0; at most three quota days.

## Existing evidence reused once

- DeepSeek Pro Public: 5082 rows.
- DeepSeek Flash Public: 1791 rows.
- Medium study: 480 rows.
- Adaptive Pro: budgets 50/200 only.

## Minimal verification

- Focused tests for changed provider/projection/evaluator/statistics code.
- Six-row formal prefix per new provider path.
- One terminal pass checking expected counts, work-key uniqueness, online-field
  isolation, exact provider/model identity and ITT failure retention.
- No Full Harness, recursive evidence replay, blind evaluation, budget 500/2000,
  full Gemini Public or redundant hash/review artifacts.

## Failure semantics

- No official response: repair and rerun only the failed row.
- Official response obtained: retain timeout/refusal/parse failure in primary ITT;
  any sensitivity retry is appended and never replaces the first terminal row.
- Successful unaffected rows are never rerun.
