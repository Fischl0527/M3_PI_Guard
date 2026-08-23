# Stage 3 Phase 1: Paper-Content-Blind Review Commitments

These commitments were frozen from the venue, title, article type, field, and
the sprint contract before the Stage 3 reviewers read the manuscript body. They
define what each reviewer will score and prevent result-dependent changes to
the review standard.

## Reviewer 1 — Editor-in-Chief

### Contract Paraphrase

I will decide whether an original empirical security article about authorization
regimes and runtime guardrails is in JISA's scope, scientifically legible, and
ready to enter external review. Mandatory failures control the decision even if
the topic is timely.

### Scoring Plan

#### D1 — methodology_rigor

- `dimension_id`: D1
- `what_to_look_for`: A design capable of supporting the paper's principal
  claims, transparent outcome definitions, uncertainty, and reproducibility.
- `what_triggers_block`: The principal conclusion depends on an invalid or
  undisclosed comparison, outcome leakage, or missing evidence.
- `what_triggers_warn`: The design is usable but important inferential limits or
  robustness checks are incompletely presented.

#### D2 — domain_accuracy

- `dimension_id`: D2
- `what_to_look_for`: Accurate security terminology, mechanism boundaries,
  threat model, and relation to current agent-security work.
- `what_triggers_block`: A central security claim is technically false or the
  online Guard has access to forbidden evaluator information.
- `what_triggers_warn`: The core account is correct but baseline or related-work
  positioning needs material clarification.

#### D3 — argumentative_coherence

- `dimension_id`: D3
- `what_to_look_for`: Alignment among research questions, methods, results,
  limitations, title, abstract, and conclusions.
- `what_triggers_block`: Conclusions materially exceed the presented evidence.
- `what_triggers_warn`: The claims are recoverable through substantial
  restructuring or narrowing.

#### D4 — cross_disciplinary_relevance

- `dimension_id`: D4
- `what_to_look_for`: Practical meaning for access control, security policy,
  usable security, and deployed agent systems.
- `what_triggers_block`: The work reduces to a model-specific benchmark result
  without a defensible information-security contribution.
- `what_triggers_warn`: Broader implications are plausible but not yet made
  concrete.

#### D5 — writing_and_structure

- `dimension_id`: D5
- `what_to_look_for`: Clear contribution statement, navigable structure,
  efficient tables/figures, and submission-ready prose.
- `what_triggers_block`: Presentation prevents scientific evaluation.
- `what_triggers_warn`: The manuscript is understandable but overlong,
  repetitive, or locally ambiguous.

[CONTRACT-ACKNOWLEDGED]

## Reviewer 2 — Methodology

### Contract Paraphrase

I will evaluate whether the estimands, paired design, sampling, statistical
tests, operational-failure rules, and uncertainty support the stated empirical
conclusions, independently of whether the results favor M3.

### Scoring Plan

#### D1 — methodology_rigor

- `dimension_id`: D1
- `what_to_look_for`: Frozen sampling, paired estimands, adequate denominators,
  ITT handling, multiplicity policy, effect sizes, uncertainty, and sensitivity
  to missing or failed executions.
- `what_triggers_block`: Outcome definitions or missingness/failure treatment can
  reverse a central conclusion and no bounded sensitivity analysis is given.
- `what_triggers_warn`: Valid analyses are present but power, estimand, or
  sensitivity interpretation is incomplete.

#### D2 — domain_accuracy

- `dimension_id`: D2
- `what_to_look_for`: Security outcomes distinguish attempted text, Guard
  decisions, and isolated unsafe effects.
- `what_triggers_block`: The study equates detection or refusal with prevented
  unsafe effects without evidence.
- `what_triggers_warn`: Some metric semantics require tighter explanation.

#### D3 — argumentative_coherence

- `dimension_id`: D3
- `what_to_look_for`: Statistical conclusions match observed effect sizes,
  confidence intervals, and the prespecified analysis family.
- `what_triggers_block`: Null findings are treated as equivalence or a floor
  effect is treated as proof of safety.
- `what_triggers_warn`: Causal or confirmatory language is stronger than the
  available statistical information.

#### D4 — cross_disciplinary_relevance

- `dimension_id`: D4
- `what_to_look_for`: Outcomes map to operational security and human burden,
  not only model metrics.
- `what_triggers_block`: The estimands have no interpretable deployment meaning.
- `what_triggers_warn`: Operational implications are underdeveloped.

#### D5 — writing_and_structure

- `dimension_id`: D5
- `what_to_look_for`: Reproducible statistical methods and concise reporting of
  numerator, denominator, effect, interval, failure, and test family.
- `what_triggers_block`: Key calculations cannot be reconstructed.
- `what_triggers_warn`: Dense or duplicated reporting obscures the analysis.

[CONTRACT-ACKNOWLEDGED]

## Reviewer 3 — LLM-Agent Security Domain

### Contract Paraphrase

I will test whether the threat model, authorization regimes, provenance-aware
runtime behavior, effect isolation, and baseline positioning are technically
correct and differentiated from adjacent LLM-agent defenses.

### Scoring Plan

#### D1 — methodology_rigor

- `dimension_id`: D1
- `what_to_look_for`: Representative attack/benign tasks, condition parity,
  mechanism ablation, external benchmark coverage, and adaptive evaluation.
- `what_triggers_block`: The claimed mechanism contribution is inseparable from
  condition or benchmark confounds.
- `what_triggers_warn`: Evaluation breadth is limited but honestly bounded.

#### D2 — domain_accuracy

- `dimension_id`: D2
- `what_to_look_for`: Precise definitions of authorization, provenance,
  policy-only/full, unsafe effects, confirmations, and online/offline state.
- `what_triggers_block`: The central mechanism or comparison is mislabeled, or
  evaluator/gold data contaminates online decisions.
- `what_triggers_warn`: Terminology or comparison to VIGIL, DRIFT, Task Shield,
  ARGUS, AuthGraph, or related systems is incomplete.

#### D3 — argumentative_coherence

- `dimension_id`: D3
- `what_to_look_for`: Contribution claims follow from direct ablations and do
  not imply SOTA, uniqueness, or generalized oracle leakage.
- `what_triggers_block`: Novelty or superiority is asserted without a direct,
  faithful comparison.
- `what_triggers_warn`: The empirical contribution is valid but the title or
  narrative overemphasizes a mechanism result.

#### D4 — cross_disciplinary_relevance

- `dimension_id`: D4
- `what_to_look_for`: Lessons transferable to access-control design, benchmark
  construction, and secure agent deployment.
- `what_triggers_block`: Findings are only idiosyncratic implementation details.
- `what_triggers_warn`: Transfer conditions are not clearly stated.

#### D5 — writing_and_structure

- `dimension_id`: D5
- `what_to_look_for`: A readable threat model, architecture, condition table,
  and clear separation of evaluation method from defense implementation.
- `what_triggers_block`: Readers cannot identify what was online, offline, or
  actually executed.
- `what_triggers_warn`: Details exist but are scattered.

[CONTRACT-ACKNOWLEDGED]

## Reviewer 4 — Cross-Disciplinary Usable Security

### Contract Paraphrase

I will evaluate whether confirmation, denial, latency, failure, and task
completion are treated as meaningful human-and-system costs and whether the
paper avoids converting an automated `ASK` state into an unsupported claim about
human usability.

### Scoring Plan

#### D1 — methodology_rigor

- `dimension_id`: D1
- `what_to_look_for`: Operational burden definitions, denominators, benign-task
  strata, and separation of measured system behavior from unmeasured human
  response.
- `what_triggers_block`: A central utility conclusion depends on an unobserved
  human-confirmation process.
- `what_triggers_warn`: Burden is measured but not sufficiently decomposed or
  interpreted.

#### D2 — domain_accuracy

- `dimension_id`: D2
- `what_to_look_for`: Correct use of usable-security and human-in-the-loop
  language; no claim that ASK is equivalent to safe user confirmation.
- `what_triggers_block`: Simulated or absent users are presented as validated
  human factors evidence.
- `what_triggers_warn`: Terminology implies stronger human evidence than exists.

#### D3 — argumentative_coherence

- `dimension_id`: D3
- `what_to_look_for`: Security and utility trade-offs remain visible together,
  including failures and overblocking.
- `what_triggers_block`: Safety is claimed by ignoring denial/failure burden.
- `what_triggers_warn`: The trade-off is reported but practical implications
  are incomplete.

#### D4 — cross_disciplinary_relevance

- `dimension_id`: D4
- `what_to_look_for`: Actionable consequences for confirmation design,
  administrators, developers, and end users.
- `what_triggers_block`: The manuscript invokes human-centered relevance while
  providing no defensible bridge from system metrics.
- `what_triggers_warn`: The bridge exists but needs qualification or concrete
  examples.

#### D5 — writing_and_structure

- `dimension_id`: D5
- `what_to_look_for`: Accessible definitions and visualizations of ASK/DENY,
  failure, latency, and completion.
- `what_triggers_block`: The burden story is not interpretable.
- `what_triggers_warn`: Tables or prose make the trade-off unnecessarily hard to
  follow.

[CONTRACT-ACKNOWLEDGED]

## Reviewer 5 — Devil's Advocate

### Contract Paraphrase

I will assume a skeptical reviewer is looking for the strongest defensible
reason to reject the article. I will test alternative explanations, floor
effects, failure-induced apparent safety, benchmark dependence, baseline
fairness, model specificity, and whether an empirical negative result still
constitutes a publishable contribution.

### Scoring Plan

#### D1 — methodology_rigor

- `dimension_id`: D1
- `what_to_look_for`: Any design choice that could make a guard appear safe by
  preventing execution, failing operationally, or selecting easy tasks.
- `what_triggers_block`: A reasonable alternative analysis overturns a principal
  result and the paper neither reports nor bounds it.
- `what_triggers_warn`: The result survives only under a narrow estimand that is
  disclosed but not stress-tested.

#### D2 — domain_accuracy

- `dimension_id`: D2
- `what_to_look_for`: Hidden oracle information, implementation-specific claims,
  weak baseline fidelity, and conflation of policy precision with answer keys.
- `what_triggers_block`: The central security interpretation depends on a domain
  mischaracterization.
- `what_triggers_warn`: The paper is accurate but leaves a plausible skeptical
  interpretation unanswered.

#### D3 — argumentative_coherence

- `dimension_id`: D3
- `what_to_look_for`: Whether the smallest defensible contribution matches the
  title, abstract, and conclusion.
- `what_triggers_block`: Removing overclaiming leaves no supported contribution.
- `what_triggers_warn`: A publishable contribution remains after substantial
  narrowing.

#### D4 — cross_disciplinary_relevance

- `dimension_id`: D4
- `what_to_look_for`: Evidence that the results matter beyond the specific
  implementation/model/benchmark combination.
- `what_triggers_block`: No actionable or conceptual lesson survives the scope
  limitations.
- `what_triggers_warn`: Relevance is plausible but requires a sharper boundary.

#### D5 — writing_and_structure

- `dimension_id`: D5
- `what_to_look_for`: Places where detail volume obscures the core evidence or
  limitations.
- `what_triggers_block`: The manuscript structure prevents falsification of its
  own claims.
- `what_triggers_warn`: The paper needs substantial compression or reordering.

[CONTRACT-ACKNOWLEDGED]
