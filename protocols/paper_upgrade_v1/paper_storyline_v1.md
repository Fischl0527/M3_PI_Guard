# Paper storyline v1

## Working title

M3-PI Guard: Non-oracle runtime authorization for multilingual, multi-tool LLM
agents under prompt-injection pressure

## One-sentence thesis

LLM-agent prompt-injection defenses are overestimated when the defense sees
gold per-case authorization; M3 reframes the problem as runtime authorization
under uncertain, provenance-tracked task policy and evaluates the resulting
security-utility trade-off across synthetic, public-benchmark and adaptive
settings.

## Main research questions

1. How much protection remains when the guard no longer consumes evaluator
   fields such as `authorized_actions`, `requires_tool`, attack family, target
   action or expected answer?
2. How do exact, broad, partial and ambiguous task-policy manifests affect ASR,
   TCR, FPR, ASK rate and unauthorized side effects?
3. Do static attack results survive public AgentDojo/InjecAgent tasks and
   adaptive query-budget attacks?
4. Which module contributes independently once policy-only behavior is separated
   from provenance, temporal, data-flow and confirmation logic?
5. Are the patterns stable across small local models, 7B-14B open models and
   frontier API models?

## Contribution claims allowed before final evidence

- A non-oracle runtime-monitor interface: `TaskPolicyManifest`,
  `ActionProposal`, `ProvenanceEvent` and `GuardDecision`.
- A three-state decision contract: `ALLOW`, `ASK`, `DENY`.
- A reproducible evidence harness that separates smoke, diagnostic, historical,
  post-hoc remediation and formal result artifacts.
- A negative empirical finding from the historical E0-E17/V2 program: exact
  policy information can dominate the measured effect, so policy leakage and
  post-hoc blind reuse must be disclosed rather than hidden.
- Detector-only PromptGuard evidence is available, but it must be reported only
  as detector performance, not as end-to-end agent safety.

## Claims still blocked

- Strong public-benchmark superiority over source-backed baselines.
- Any "SOTA" or "first" claim.
- Confirmatory M3-v2 blind-set performance.
- Robustness under formal adaptive query-budget attacks.
- Generalization to frontier API models.
- Completed AgentDojo `transformers_pi_detector` or `tool_filter` results.

## Proposed paper structure

1. Introduction
   - why prompt injection in tool agents is a runtime authorization problem;
   - why gold authorization and static attacks can overstate safety.
2. Threat model
   - trusted user/app/tool-schema inputs;
   - untrusted documents, tool outputs and memory;
   - attacker visibility and query-budget settings.
3. Method
   - policy manifest;
   - provenance graph;
   - ALLOW/ASK/DENY monitor;
   - confirmation and permission expansion;
   - formal properties and limitations.
4. Experimental design
   - historical E0-E17 as engineering baseline only;
   - M3-v2 independent blind protocol;
   - AgentDojo and InjecAgent public benchmarks;
   - strong baselines and exclusion rules;
   - adaptive query-budget attack protocol;
   - model coverage and statistics.
5. Results
   - safety-utility Pareto curves;
   - public-benchmark matrix;
   - model-by-defense heatmaps;
   - attack family and language heatmaps;
   - authorization-regime sensitivity;
   - component ablation with confidence intervals;
   - adaptive ASR versus query budget;
   - latency and cost.
6. Discussion
   - what policy-only dominance means;
   - where provenance and confirmation help;
   - when narrow manifests cause ASK/FPR utility costs;
   - limitations and deployment assumptions.
7. Reproducibility
   - manifests, hashes, frozen thresholds, logs and one-command regeneration.

## Required core figures

1. Threat model and trust-boundary diagram.
2. Safety-utility Pareto plot.
3. Adaptive ASR versus query budget line plot.
4. Model by defense heatmap.
5. Attack family by language heatmap.
6. Authorization-regime sensitivity line plot.
7. Component ablation forest plot.
8. Latency ECDF or box plot.
9. Failure-type stacked bar chart.
10. Dataset composition chart for descriptive context only.

## Evidence routing

- Historical E0-E17 and Acceptance Remediation V2: engineering maturity and
  audit-disclosure evidence.
- PromptGuard formal detector-only run: detector baseline table only.
- AgentDojo `transformers_pi_detector` v2 CPU-detector run: pending formal
  public-benchmark strong-baseline evidence until its manifest reports
  `completed_formal`.
- AgentDojo `tool_filter`: frozen protocol, pending qualification and formal
  execution.
- Task Shield, IPIGuard, Progent and CaMeL/Fides: source/adaptation evidence
  pending formal execution.
- M3-v2 independent blind, adaptive query-budget attacks and frontier API
  models: required for Q2-readiness, not yet complete.

