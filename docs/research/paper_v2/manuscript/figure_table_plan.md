# Figure and table plan

Status: `medium_public_primary_and_adaptive_canary_ready`

Every final visual must be regenerated from an admitted analysis artifact.
Terminal diagnostic rows remain in ITT; technical-canary, partial, and pending
rows are excluded from scientific panels. Figure captions must state the
denominator, uncertainty method, model/benchmark scope, and failure handling.

## Main figures

| ID | Purpose | Geometry | Authoritative data | Current status |
|---|---|---|---|---|
| Figure 1 | Show the online-state/evaluator boundary and append-only evidence flow | Compact system diagram | Methods contracts and provider-safety policy | Design ready; final artwork pending |
| Figure 2 | Jointly show medium/public unsafe-effect rate and benign tool TCR | Two-panel point-range plot; one point per condition with Wilson CI | Admitted medium v8 and Public-primary v5 | Data available; combined final artwork pending |
| Figure 3 | Quantify paired treatment effects without hiding utility | Forest plot of absolute pp differences with clustered-bootstrap CI | Medium and Public-primary paired-comparison objects | Eight rows available; final artwork pending |
| Figure 4 | Show authorization-regime sensitivity and confirmation burden | Small multiples by regime, condition and outcome | Regime-probe analysis plus public regime strata | Medium probes available; formal-scale precision pending |
| Figure 5 | Test adaptive robustness as a function of query budget | Cumulative first-success/survival curve at 50/200/500/2000 | Admitted adaptive query ledger | No scientific data yet |

## Main tables

| ID | Content | Admission dependency | Current status |
|---|---|---|---|
| Table 1 | Dataset, model, condition and authorization-regime design | Frozen manifests | Ready |
| Table 2 | Unsafe-effect and TCR raw counts with Wilson CI | Medium + Public result admissions | Populated |
| Table 3 | Paired security/utility effects, McNemar, Holm and bootstrap CI | Medium + Public result admissions | Populated |
| Table 4 | ASK reasons, confirmation outcomes, failures, latency, calls and cost | Medium + Public result admissions | Populated; confirmation remains synthetic/pending |
| Table 5 | Benchmark heterogeneity under the primary model | Complete admitted Public-primary matrix | Populated; no cross-model row authorized |
| Table 6 | Adaptive first-success and saturation | Complete 40/20/hardest-20 adaptive panel | Pending |

## Visual integrity rules

1. Never plot a favorable zero for missing, failed, or unadmitted evidence.
2. Display raw numerators and denominators next to every proportion.
3. Keep security and utility on separate, clearly labeled axes; do not combine
   them into an unregistered composite score.
4. Use identical axis ranges for condition comparisons within a panel.
5. Distinguish M3 policy-only from M3-full directly; neither may be omitted
   from a mechanism-contribution figure.
6. Show operational failures by condition in the main paper or an immediately
   referenced appendix table.
7. Label exact-gold as an oracle sensitivity condition and keep it outside the
   primary endpoint.
8. Do not use color alone to encode pass/fail or model identity.
9. Export editable vector artwork for submission and a raster preview only for
   QA.
10. Bind each final figure to the analysis file hash and generation-command
    manifest.

## Caption shell for Figure 2

“Unsafe-effect rate on assigned attack tasks and task-completion rate on benign
tool tasks. Points show raw proportions and bars show Wilson 95% confidence
intervals. All assigned cases, including terminal operational failures, remain
in the intention-to-treat denominator. The exact-gold authorization ablation is
excluded from the primary panel.”

The final caption must identify DeepSeek v4 Pro as the single primary model and
state that no cross-model inference is authorized.
