# Final Experiment Chart Map

## Reporting contract

- Audience: technical competition reviewers and project maintainers.
- Primary deliverables: reproducible static figures, chart-ready tables and the interactive Dashboard. PPT and DOCX report are outside the current user-approved scope.
- Static export: reproducible PNG and SVG plus chart-ready CSV under the frozen results tree.
- Interactive surface: Dashboard filters by model, defense, attack family, language and experiment batch.
- Palette: restrained blue/orange roots plus neutral greys; line style, marker shape, labels or facets provide non-colour distinction.
- Every figure must show a neutral title, metric/unit, experiment ID, sample or denominator context and uncertainty/caveat. An adjacent paragraph states takeaway, how to read the figure and implication.

## Planned visuals

| Section | Analytical question | Family / type | Required fields | Supported claim | Output |
|---|---|---|---|---|---|
| Main defense effect | How much does full Guard change ASR, DSR, TCR and malicious-call Recall under the same prompt? | Comparison / grouped bar with Wilson intervals | model, condition, metric, numerator, denominator, estimate, CI | Same-prompt incremental effect and utility trade-off | `main_defense_effect.{png,svg,csv}` |
| Prompt vs Guard | Is safety-prompt hardening additive to Guard? | Comparison / paired dot-and-interval or grouped bar | model, prompt_profile, guard_mode, paired difference, bootstrap CI | Separates prompting from runtime protection | `prompt_guard_increment.{png,svg,csv}` |
| Component contribution | Which Guard modules materially contribute? | Comparison / ranked horizontal bar with paired-difference CI | ablation, ASR delta, Recall delta, TCR delta, CI | Identifies high-value and redundant components | `guard_ablation.{png,svg,csv}` |
| Cross-model robustness | Does the result generalize across the four core models and Vicuna compatibility baseline? | Matrix / heatmap plus exact-value table | model, condition, metric, estimate, n | Exposes model-specific weakness rather than hiding it in an aggregate | `cross_model_heatmap.{png,svg,csv}` |
| Attack-family coverage | Which of the nine attack families remain vulnerable? | Matrix / heatmap; family detail horizontal bars | attack_family, model, condition, ASR, Recall, DSR, n, CI | Shows residual blind spots and family heterogeneity | `family_robustness.{png,svg,csv}` |
| Language and evasion | How robust is Guard across language and encoding variants? | Comparison / grouped bars and matrix | language, evasion_type, condition, ASR, Recall, n | Separates multilingual from encoding failures | `language_evasion.{png,svg,csv}` |
| Context position/length | How do attack outcomes and latency change across ordered context lengths and injection positions? | Trend / faceted line with markers and CI | context_tokens, injection_position, ASR, latency, n, CI | Reveals degradation shape across E9 conditions | `context_position_trends.{png,svg,csv}` |
| Multi-turn/adaptive rounds | Does delayed activation or adaptive rewriting erode protection over ordered turns/rounds? | Trend / line with markers and CI | turns_or_round, strategy, ASR, Recall, n, CI | Shows cumulative or adaptive degradation in E10/E16 | `multiturn_adaptive_trends.{png,svg,csv}` |
| Threshold calibration | What trade-off supports the frozen operating threshold? | Relationship / ROC and PR lines with selected-point annotation | threshold, TPR, FPR, precision, recall | Documents validation-only threshold choice | `threshold_calibration.{png,svg,csv}` |
| Random stability | How variable are outputs across seeds and temperatures? | Distribution / box plot plus flip-rate bars | model, temperature, seed, metric/outcome | Quantifies stochastic robustness and outliers | `random_stability.{png,svg,csv}` |
| Performance | What latency/throughput/overhead distributions arise by concurrency and context? | Distribution / box plot and ordered line | concurrency, context_tokens, model_latency, guard_latency, total_latency, throughput, VRAM | Evaluates p50/p95 and engineering targets without mean-only summaries | `performance_profile.{png,svg,csv}` |
| Cross-tool chain patterns | How do the four frozen E11 chain patterns compare with the separately frozen post-hoc scope supplement? | Comparison / two-panel grouped bars with exact counts | evidence_scope, chain_pattern, condition, metric, numerator, denominator, estimate, CI | Shows chain-pattern behavior while preserving the original E11 denominator boundary | `cross_tool_chain_patterns.{png,svg,csv}` |
| Failure taxonomy | What share and count of failures are leak, over-block, ASK, parse or timeout classes? | Composition / donut for rough share plus sorted count bar | failure_class, count, share, experiment_id | Makes E17 review coverage visible; count bar remains authoritative | `failure_taxonomy.{png,svg,csv}` |

## QA gates

- Bars comparing absolute magnitude start at zero; narrowed axes are allowed only for explicit delta views with exact labels and a focused-scale note.
- Line plots require meaningful ordered grids, not two-point decoration; sparse results fall back to bars or exact tables.
- Confidence intervals or paired-difference intervals appear wherever supported; small-n panels state the limitation.
- No chart silently drops timeout, refusal, parse failure or max-step outcomes from its source denominator.
- The E11 post-hoc supplement is displayed as a separate evidence panel and is never pooled into the original frozen E11 denominator.
- All final PNG/SVG exports are opened and inspected for clipping, collisions, honest scales, readable legends and grayscale distinction.
- The final analysis provides an adjacent explanatory paragraph for every visual; the Dashboard exposes the underlying rows or exact-value table.

## 2026-07-15 interim report visuals

These checkpoint visuals do not replace or pre-empt the 13 frozen final figures:

| Section | Analytical question | Family / type | Fields | Supported claim | Surface |
|---|---|---|---|---|---|
| Corrected E9 result | How does ASR differ between No Guard and full Guard at each calibrated prompt target and injection position? | Comparison / grouped bar with Wilson intervals | context, position, condition, ASR, numerator, denominator, parse counts | execution-r3 is complete; full Guard is 0/15 in each context while baseline remains nonzero | `E9_context_correction_v2_r3/primary_chart.png` plus exact table in the interim report |
| Corrected E14 latency | How does end-to-end latency vary across ordered contexts and concurrency? | Trend / faceted line with markers and uncertainty | context, concurrency, condition, median/p95 latency, paired n, CI | Latency rises with context; overall paired Guard overhead is small, while per-cell high-concurrency estimates remain uncertain | `E14_context_correction_v2_r3/latency_by_context.png` |
| Corrected E14 throughput | How does successful system throughput compare across the three tested concurrency levels? | Comparison / zero-based grouped bars in context facets | context, concurrency, condition, successful throughput | Shows observed system-path throughput without implying a continuous three-point trend or pure Guard cost | `figures/e14-throughput-grouped-bar.png` |
| Corrected E14 GPU capacity | How does device-wide peak GPU memory vary by context and concurrency? | Matrix / heatmap | context, concurrency, device peak MiB | 16K/high-concurrency cells approach the 8GB capacity boundary; values are not Guard-exclusive | `E14_context_correction_v2_r3/gpu_memory_by_context.png` |
| Automated E17 diagnostic | How consistently do two isolated automated agents apply the public failure taxonomy? | Exact agreement table; no composition chart at this stage | agreement counts/rates, kappa, disagreements, code-pair counts | Reveals taxonomy ambiguity while remaining ineligible for human E17 evidence | `E17_auto_review_corrected_r3/comparison.{json,md}` |

All interim chart datasets were reviewed against execution-r3 manifests and have adjacent interpretation/caveat text. Bars use zero baselines; the latency line uses a meaningful ordered context axis; the three-level concurrency view uses grouped bars instead of a decorative line. GPU values are labeled as device-wide, and automated E17 outputs are kept diagnostic-only.
