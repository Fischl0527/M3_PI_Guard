# Stage 3 Review 3 — LLM-Agent Security Domain

## Dimension Scores

| Dimension | Score | Basis |
|---|---|---|
| D1 methodology rigor | `warn` | The study has meaningful paired and adaptive evidence, but the configuration contrast is confounded and the authorization constructs are insufficiently operationalized in the paper. |
| D2 domain accuracy | `warn` | Threat/effect boundaries are accurate; however, calling the Public comparator merely “structural” hides that it is a source-pinned VIGIL adaptation, and module language exceeds the actual contrast. |
| D3 argumentative coherence | `warn` | The negative-result framing is appropriate, but the title and RQ2 still invite a provenance-specific interpretation not isolated by the design. |
| D4 cross-disciplinary relevance | `pass` | The field needs evaluations that expose authorization inputs and jointly report effect and utility. |
| D5 writing and structure | `warn` | The online/offline boundary is clear, but readers cannot reproduce the five authorization regimes from their current prose definitions. |

## Failure Condition Checks

- F1: not triggered; no mandatory dimension is `block` in this review.
- F2: this reviewer assigns warn-or-worse to all three mandatory dimensions;
  panel-level majority is deferred to synthesis.
- F3: not triggered; D4 is `pass`.
- F0: not satisfied.

## Review Body

### Contribution and novelty boundary

The manuscript correctly recognizes that VIGIL, DRIFT, Task Shield, Progent,
IPIGuard, CaMeL, ARGUS, AuthGraph, FAVA, and provenance-sensitivity auditing
already occupy verify-before-commit, information-flow, privilege, dependency,
and provenance-aware authorization space. Its defensible novelty is an
evaluation contract plus negative empirical evidence. That is a credible
contribution if the implementation-specific factors are fully exposed.

### Major issues

#### DOM-M1 — Fully specify the compared configurations

The paper currently invites readers to treat full versus policy-only as a
provenance/data-flow/confirmation ablation. It must state that M3-full also uses
`safe_prompt` while policy-only uses `normal`. Rename the conditions in prose
as complete configuration bundles or add a condition-components table with
columns for prompt profile, policy, provenance, temporal/data flow,
permission monotonicity, and confirmation. Do not conclude that provenance
itself caused either the security disadvantage or utility loss.

#### DOM-M2 — Operationalize every authorization regime

Current definitions are conceptual labels. The actual transformations are more
specific:

- `auto_compiled` compiles trusted request, trusted app context, and tool
  schemas;
- `broad` replaces exact argument constraints with type constraints and may
  require confirmation for changed side-effect rules;
- `underspecified` drops the last compiled rule;
- `conflicting` replaces exact values with controlled conflicting values; and
- `exact_gold` converts evaluator-derived expected tool calls into exact
  required argument rules with confirmation disabled.

These details affect construct validity and plausibly explain DENY/failure
behavior. Include them in Methods and provide one sanitized example. Avoid
implying that these transformations represent the distribution of real human
policy errors.

#### DOM-M3 — Identify and qualify the VIGIL comparator

The completed Public and medium studies use a source-pinned VIGIL
verify-before-commit adapter, not an unnamed generic structural baseline. State
the source revision, which upstream components are unchanged, how the official
constraint generator receives the evaluated provider client, and any
environment/tool-schema adaptation. “Strongest peer-reviewed structural
baseline” is a ranking label, not a reproducible method description.

#### DOM-M4 — Answer benchmark dependence directly

The single unsafe event and most failures in the new authorization experiment
are concentrated in AgentDojo, while the pooled benign-tool authorization
effect reverses direction across AgentDojo and M3-v2. This should be part of
RQ3's answer. The present Table 5 pools configurations and does not show the
paired regime effect within each benchmark.

### Minor issues

1. Clarify that “parameter provenance” refers to runtime evidence propagated
   by this implementation, not a complete semantic lineage guarantee.
2. Explain what an `ASK` does when independent confirmation remains pending and
   whether the isolated backend treats it as non-execution.
3. Distinguish provider/model generation failures from Guard denials; both can
   prevent effects but only one is an authorization decision.
4. The title should emphasize authorization regimes and configuration
   evaluation rather than imply that context/provenance uncertainty itself was
   separately randomized.
5. The Related Work section is current and appropriately status-aware, but the
   final paper should explicitly state that no direct DRIFT effect comparison
   was run.

## Editorial Decision

**Major revision.** The empirical direction is interesting, especially because
it is unfavorable to the proposed full system. Publication requires exact
configuration and regime descriptions plus a narrower, bundle-level claim.

