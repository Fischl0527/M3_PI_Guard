# Stage 4 Statistical Interpretation and Fallacy Check

## Material Passport

- Origin Skill: academic-research-suite / experiment-agent
- Origin Mode: validate
- Origin Date: 2026-08-23
- Verification Status: ANALYZED
- Version Label: stage4_statistical_validation_v1

## Validation Report

- **Source:** completed DeepSeek Public, medium, lean authorization, and
  adaptive records; no new provider calls
- **Overall confidence:** CAUTION
- **Reason:** the paired estimates are reproducible and retain failures in ITT,
  but the main lean sample is modest, unsafe effects are floor-limited, the two
  benchmarks reverse direction for benign utility, and the policy/full
  contrast is a bundled configuration comparison.

### Statistical findings

| Finding | Test or interval | Estimate | Interpretation | Confidence |
|---|---|---:|---|---|
| Policy package, auto to exact, benign-tool TCR | paired cluster bootstrap; exact McNemar; Holm within utility family | -21.67 pp overall | Pooling hides +13.33 pp on AgentDojo and -56.67 pp on M3-v2 | RED_FLAG if pooled alone; CAUTION when stratified |
| Full package, auto to exact, benign-tool TCR | paired cluster bootstrap; exact McNemar; Holm within utility family | -15.00 pp overall | Pooling hides +10.00 pp on AgentDojo and -40.00 pp on M3-v2 | RED_FLAG if pooled alone; CAUTION when stratified |
| Policy package, auto to exact, unsafe-or-failure bound | paired cluster bootstrap; exact McNemar; Holm within security-sensitivity family | +18.00 pp | Failure-sensitive bound worsens although observed unsafe effects remain at floor | CAUTION |
| Full package, auto to exact, unsafe-or-failure bound | paired cluster bootstrap; exact McNemar; Holm within security-sensitivity family | +18.00 pp | Same failure-sensitive direction; not observed attack success | CAUTION |
| Policy versus full package | paired estimates | approximately +1 pp full-minus-policy on the composite bound | Interval crosses zero and the contrast is package-confounded | CAUTION |
| Zero unsafe effects in 100 attack cases | Wilson 95% CI | upper bound 3.70% | Zero observations do not prove zero risk | CAUTION |
| Zero unsafe effects in 30-case stress cells | Wilson 95% CI | upper bound 11.35% | Stress-regime security comparisons are imprecise | CAUTION |

Exact McNemar p-values are reported rather than converted into binary
“significant/non-significant” prose. The two primary endpoint families use
separate Holm correction. Cluster-bootstrap intervals are unadjusted and are
reported as estimation intervals, not multiplicity-corrected tests. No post hoc
achieved-power claim is made.

### Warnings

| Type | Detail | Affected claims |
|---|---|---|
| Benchmark interaction | AgentDojo and M3-v2 benign-tool effects have opposite directions | Any pooled authorization-utility claim |
| Floor limitation | Observed unsafe-effect counts are 0 or 1 in the four primary lean attack cells | Claims of stable or zero security risk |
| Operational availability | Exact cells have 25--26% attack operational failure | Security claims based only on executed effects |
| Bundled treatment | Prompt profile changes together with runtime modules | Any component-specific provenance/data-flow/confirmation attribution |
| Selection chronology | Lean study was designed after Public results, although the selector did not read outcome files | Confirmatory-language strength |
| External validity | Gemini stopped as diagnostic; only DeepSeek evidence is complete | Cross-provider generalization |

### Fallacy scan

- **Coverage:** 11/11 statistical fallacy types checked.

| Fallacy | Severity | Finding | Stage 4 handling |
|---|---|---|---|
| Simpson's paradox | CAUTION | The pooled utility decline masks opposite benchmark directions; this is a qualitative interaction rather than a strict all-strata reversal. | Abstract, Results, Discussion, Conclusion, Table 5, and Figure 4 report benchmark strata. |
| Ecological fallacy | NOTE | Inference remains at the task/benchmark level; no individual-user claim is made. | Preserve task-level language. |
| Berkson's paradox | NOTE | Benchmark cases are selected populations, but the paper does not estimate a general correlation from admission-conditioned samples. | Limit claims to tested tasks and policies. |
| Collider bias | NOTE | No post-treatment covariate adjustment is used in the paired comparisons. | No action required. |
| Base-rate neglect | NOTE | Attack and benign denominators and raw counts are reported separately; no deployment prevalence or predictive-value claim is made. | Preserve separate endpoint denominators. |
| Regression to the mean | NOTE | No pre/post cohort selected for extreme scores is analyzed. | No action required. |
| Survivorship bias | NOTE | All terminal failures remain in ITT; superseded no-response transport attempts are disclosed separately. | Keep the failure-sensitive bound and raw failure counts. |
| Look-elsewhere effect | CAUTION | Multiple condition and benchmark contrasts exist. | Keep two prespecified endpoint families, Holm-adjusted p-values, and label other strata descriptive. |
| Garden of forking paths | CAUTION | The lean study followed the Public results, creating researcher-degree-of-freedom risk despite outcome-blind selection. | Disclose chronology, frozen selector inputs, fixed comparisons, and no outcome-driven exclusions. |
| Correlation is not causation | CAUTION | Authorization regimes are manipulated, but policy/full also changes prompt profile; component causation is not identified. | Treat RQ2 as a configuration-package comparison only. |
| Reverse causality | NOTE | Experimental condition assignment precedes outcomes; no cross-sectional directional inference is used. | No action required. |

### Reproducibility

- **Method:** deterministic offline regeneration of analysis JSON, CSV tables,
  manuscript, and figures from already completed records
- **Verdict:** REPRODUCIBLE for the Stage 4 derived outputs
- **Focused verification:** 25 manuscript/analysis/table/figure tests passed;
  Ruff and Python syntax checks passed
- **Excluded by design:** provider replay, Full Harness, historical evidence
  replay, and recursive hash verification

