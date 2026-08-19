# Paper-v1 confirmatory preregistration freeze v1

- Status: `completed_frozen_preregistration`
- Frozen at: `2026-07-21T10:28:53.067205+00:00`
- Preregistration SHA-256: `b4b747196274e877c4b2bd0e5bbdebdcc582d585c714263815a8e4956f6b742a`
- Result eligible: `False`

## Hypotheses

| ID | Family | Pre-registered claim |
|---|---|---|
| `H1_primary_adaptive_safety` | `primary` | Under non-gold authorization, M3 full reduces worst-budget adaptive attack success rate by at least 50% relative to the strongest formally admitted comparator. |
| `H2_primary_utility_noninferiority` | `primary` | M3 full is non-inferior to the strongest formally admitted comparator on legitimate task completion. |
| `H3_authorization_uncertainty` | `secondary` | Authorization degradation from auto-compiled to ambiguous, partial, and incorrect policies changes ASR, ASK burden, and TCR in a measurable safety-utility trade-off. |
| `H4_provenance_temporal_contribution` | `secondary` | Removing provenance or temporal authorization produces a non-zero increase in unsafe effects relative to M3 full. |
| `H5_cross_environment_consistency` | `secondary` | The direction of M3 full's safety effect is consistent across M3-v2, AgentDojo, InjecAgent, local-model tiers, and two frontier API vendors. |

## Analysis contract

- `alpha_familywise`: 0.05
- `confidence_level`: 0.95
- `bootstrap_iterations`: 10000
- `bootstrap_seed`: 20260718
- `cluster_unit`: "semantic_template_or_public_benchmark_user_task"
- `paired_binary_test`: "exact_McNemar"
- `multiple_testing`: "Holm within each declared hypothesis family"
- `mixed_effects`: {"binary_outcomes": "binomial mixed model", "fixed_effects": ["defense", "authorization_regime", "attack_family", "language", "dataset"], "random_intercepts": ["template_or_task", "model"]}
- `latency`: {"effect_size": "rank-biserial correlation", "paired_test": "Wilcoxon signed-rank", "summaries": ["median", "p95", "ECDF"]}
- `proportion_reporting`: ["raw numerator", "raw denominator", "percentage", "Wilson 95% CI"]
- `primary_endpoint_order`: ["unsafe_effect_rate", "unauthorized_side_effect_rate", "data_exfiltration_rate", "task_completion_rate"]
- `adaptive_endpoint`: "worst observed ASR at 2000-query budget"
- `decision_rule`: "Report effect sizes and confidence intervals regardless of p-value; primary claims require the pre-specified margin and multiplicity-adjusted inference."

## Failure and exclusion policy

- `case_exclusions_after_freeze`: "forbidden"
- `allowed_pre_run_exclusions`: ["public task is provably incompatible with the declared tool/runtime interface", "license or provider policy forbids execution"]
- `required_exclusion_record`: ["case_id", "reason", "decision_time", "decider", "affected_conditions"]
- `timeouts_parse_failures_max_steps`: "remain in the original denominator and are separately reported"
- `formal_cell_failure`: "any unresolved case failure blocks formal admission; repair requires rerunning all affected conditions, not selecting favorable cases"
- `duplicate_rows`: "hard error unless byte-identical resume evidence selects one canonical case manifest"
- `missing_rows`: "hard error and formal admission blocked"
- `threshold_tuning`: "validation only; no threshold changes after independent blind admission"
- `stopping_rule`: "complete the frozen universe; no optional early stopping based on effect direction"

## Frozen figure plan

| ID | Type | Content |
|---|---|---|
| `F1` | `architecture` | threat model and trusted/untrusted data flow |
| `F2` | `pareto_scatter` | security-utility Pareto frontier |
| `F3` | `line` | adaptive ASR versus query budget |
| `F4` | `heatmap` | model by defense condition |
| `F5` | `heatmap` | attack family by language by defense |
| `F6` | `line` | ASR, TCR, and ASK versus authorization quality |
| `F7` | `forest` | component ablation effects with 95% intervals |
| `F8` | `ecdf_box` | end-to-end and guard latency |
| `F9` | `stacked_bar` | failure taxonomy |
| `F10` | `pie` | dataset composition only |

## Freeze checks

| Check | Passed |
|---|---|
| `public_benchmark_protocol_frozen` | `True` |
| `adaptive_protocol_frozen` | `True` |
| `adaptive_panel_has_80_tasks` | `True` |
| `independent_blind_kit_has_600_slots` | `True` |
| `independent_blind_not_yet_admitted` | `True` |
| `adaptive_formal_result_absent` | `True` |
| `independent_blind_formal_result_absent` | `True` |
| `five_hypotheses_declared` | `True` |
| `ten_figures_declared` | `True` |

## Boundary

Protocol evidence only. This freeze was created before independent-blind admission and formal adaptive results. It does not convert historical, diagnostic, running, or future incomplete runs into confirmatory evidence.
