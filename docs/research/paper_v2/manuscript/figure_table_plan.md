# Figure and table plan — incremental empirical study

> 历史图表计划：下文描述旧E1–E6文章的表图，不是当前精简文章的布局。
> 2026-10-09文档更新：当前四幅主图、四张主表的来源见
> [论文工作区说明](README.md)和
> [当前主图目录](../../../../outputs/experiments/research_followup_20261006_v1/manuscript_figures/)。
> 历史数量、生成状态和原始来源保留，不能当作修复版的新证据。

Status: `e1_e6_complete`

The paper uses the frozen 180-case factorial cohort, 60-task source-authority
counterfactual, 60-case outcome-enriched challenge set, 90-case Flash
replication, 12-task B200-survivor tail, and 60-task E6 activity calibration. Historical Public, authorization and
budget-50/200 evidence is reused only through its completed compact analysis.
No figure depends on the retired full Harness, blind test, budget 2,000, or a
recursive historical replay. Terminal response-bearing failures remain in ITT;
response-less engineering failures are recovered only under the failed-row rule.

## Main figures

| ID | Analytical question | Geometry | Authoritative data | Status |
|---|---|---|---|---|
| Figure 1 | Which fields and source-authority labels may enter the online Guard? | Online/offline authority-boundary schematic | Runtime projection and E2 counterfactual contract | Complete; reviewed in both Word manuscripts |
| Figure 2 | What are the prompt, module and interaction effects on unsafe effect, TCR and the failure-sensitive bound? | Three-panel 2×2 interaction plot | E1 factorial analysis | Complete; reviewed in both Word manuscripts |
| Figure 3 | Does swapping only source authority change deterministic Guard decisions or end-to-end actions? | Decision heatmap plus paired source-swap panel | E2 replay and end-to-end analysis | Complete; reviewed in both Word manuscripts |
| Figure 4 | Do factor effects change in the representative, risk-enriched and Flash cohorts? | Absolute-effect forest plot | E1, E3 and E4 analyses | Complete; reviewed in both Word manuscripts |
| Figure 5 | What additional first-success risk appears after budget 200 among selected survivors? | Original B50/B200 panel plus separate conditional survivor-tail panel | Existing adaptive analysis and E5 analysis | Complete; never merged into a complete B500 curve |

Each figure is exported once as editable SVG, submission-oriented vector PDF,
and QA PNG. The generator does not create a hash bundle or reopen provider
traces.

## Main tables

| ID | Content | Source | Status |
|---|---|---|---|
| Table 1 | Four contemporaneous factor cells and their prompt/module assignments | Frozen E1 plan | Generator qualified |
| Table 2 | E1 module, prompt and interaction estimates for the three endpoints | E1 analysis | E1 data complete |
| Table 3 | E2 end-to-end factor estimates, source-swap effects and offline false allow/block | E2 analysis | E2 data complete |
| Table 4 | E3 risk-enriched and E4 Flash factor estimates | E3/E4 analyses | E3/E4 data complete |
| Table 5 | Conditional E5 overall and attack-family first-success results | E5 analysis | Complete |
| Table 6 | E6 DeepSeek unsafe, failure, unsafe-or-failure and decision-event burden by condition | E6-v2 analysis | Complete; risk-enriched single block, 47/60 E3 anchors |

The six main CSV tables are exported from the frozen factor design, five
incremental `analysis_v1.json` files, and E6 `analysis_v2.json`. Twelve numbered
supplementary tables retain detailed historical endpoints, runtime burden and
E1--E6 operational context.
The exporter does not open raw provider traces and does not create an
integrity/hash bundle.

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
9. Keep both incomplete Gemini subsets diagnostic and outside cross-provider
   inference; administrative closure is not a safe or response-bearing result.
10. Display E5 only as a conditional B200-survivor tail; do not claim a complete
   original-panel B500 curve or attack saturation.
11. Display E6 only as a historically risk-enriched single-block calibration;
   disclose that 47/60 tasks also anchor E3, and do not claim deployment
   prevalence, benign utility, temporal repeatability or independent-sample
   replication.
