# Figure and table plan — lean authorization study

Status: `deepseek_figures_and_tables_complete_gemini_pending`

The paper uses the frozen 180/90/60 nested samples, the compact authorization
analysis, and the already completed Pro/Flash/medium/adaptive analyses. No
figure depends on the retired full Harness, blind test, budget 500/2,000, or a
recursive historical evidence replay. Terminal model-response failures remain
in ITT; response-less transport failures are recovered only under the frozen
failed-row rule.

## Main figures

| ID | Analytical question | Geometry | Authoritative data | Status |
|---|---|---|---|---|
| Figure 1 | Which fields are visible to the online Guard? | Online/offline flow schematic | Runtime projection contract | Generated and visually checked; raw evaluator/gold-answer fields stay offline, while `exact_gold` exposes only a derived authorization object |
| Figure 2 | How do authorization regimes trade attack safety for benign utility? | Labeled safety–utility scatter | `authorization_results_deepseek_v1.json` condition summaries | DeepSeek visually checked; coincident points use a slash-linked marker; Gemini pending |
| Figure 3 | How large are the paired authorization and mechanism effects? | Forest plot of absolute pp difference with task-cluster bootstrap CI | Paired comparison objects | DeepSeek visually checked; legend is outside the estimate panel; Gemini pending |
| Figure 4 | What ASK, DENY, failure and latency burden is incurred? | Four horizontal-bar small multiples | Compact per-condition burden summary | DeepSeek generated and visually checked; ASK/DENY record incidence clarified |
| Figure 5 | How does first unsafe effect accumulate by query budget? | Cumulative first-success step curve | Existing Pro budget-50/200 analysis | Generator and data ready; no saturation claim |

Each figure is exported once as editable SVG, submission-oriented vector PDF,
and QA PNG. The generator does not create a hash bundle or reopen provider
traces.

## Main tables

| ID | Content | Source | Status |
|---|---|---|---|
| Table 1 | Models, datasets, nested samples, conditions and authorization regimes | Frozen lean execution plan | Ready |
| Table 2 | Unsafe-effect and benign-tool TCR counts with Wilson 95% CI | Condition summaries | DeepSeek exported; Gemini pending |
| Table 3 | Paired absolute effects, McNemar, Holm and clustered-bootstrap CI | Paired comparisons | DeepSeek exported; Gemini pending |
| Table 4 | ASK, DENY, failures, p50/p95 latency, tokens and API cost | Burden summaries | DeepSeek exported; event totals and record incidence both retained |
| Table 5 | Benchmark and attack-family heterogeneity | Predefined strata | DeepSeek exported; Gemini pending |
| Table 6 | Adaptive budget-50/200 first-success results | Existing Pro analysis | Ready; explicitly not a saturation table |

The six CSV tables are exported from the frozen plan plus the two compact
analysis JSON files. The exporter does not open raw provider traces and does
not create an integrity/hash bundle.

## Visual integrity rules

1. Never plot a favorable zero for missing evidence.
2. State model, task population, endpoint and denominator in the subtitle or
   caption.
3. Keep security and utility as separate axes; do not invent a composite score.
4. Include policy-only and M3-full in all mechanism-contribution comparisons.
5. Label `exact_gold` as an oracle sensitivity condition, not the primary
   authorization regime; never describe the derived online authorization object
   as direct visibility of raw evaluator labels or gold answers.
6. Show failures and confirmation/blocking burden in the main paper.
7. Use color plus shape, ordering, labels or faceting; do not rely on color
   alone.
8. Keep percentage axes honest and use a visible zero line for paired effects.
9. Report Gemini only as a cross-vendor result if all 450 planned work items
   become terminal; otherwise label the observed subset diagnostic.
10. Do not claim adaptive saturation from budgets 50 and 200.
