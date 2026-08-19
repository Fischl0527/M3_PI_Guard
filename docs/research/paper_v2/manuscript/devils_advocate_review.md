# Devil’s Advocate review — pre-result

## Highest-risk rejection arguments

1. **The novelty may be incremental.** ARGUS and AuthGraph overlap directly
   with provenance-aware authorization, while VIGIL, DRIFT, Progent, CaMeL, and
   IPIGuard cover adjacent verification, privilege, and data-flow mechanisms.
   The paper cannot rely on “parameter provenance is new.” Its defensible
   contribution must be the joint evaluation boundary, permission monotonicity,
   confirmation semantics, and paired module evidence.

2. **The original answer-key narrative is not supported.** Twenty source-audit
   units found nine covered paths without observed online gold, nine components
   that are not runtime guards, one path-dependent case, and one inconclusive
   case. With no independent second review, a domain-wide leakage claim would
   overstate the evidence. The neutral context/provenance-uncertainty title is
   currently the only defensible title.

3. **Zero-call baseline qualification is not reproduction.** The VIGIL
   symbolic auditor and DRIFT pipeline construction pass source-backed smoke
   tests, but their model-dependent policy generation and validation have not
   run on the paired study. A paper that compares M3 against stubs or manually
   supplied VIGIL constraints would be rejected.

4. **The public-benchmark scale has a preregistration conflict.** AgentDojo v1
   exposes 97 unique utility tasks, below the planned 150/100 benign counts.
   Duplicating tasks would create a false denominator. The deviation must be
   reported and power interpreted at the unique-task level.

5. **Independent blind evaluation is currently absent.** A content-free kit is
   not a blind dataset. Unless an external custodian supplies a sealed
   candidate, the paper must use “internally sealed” and narrow its external
   validity claim.

6. **Adaptive evaluation may be financially infeasible.** The frozen maximum
   is 75,000 attacker queries before counting multi-step agent calls and guard
   model calls. A provider/cost estimate and hard spend cap are required before
   execution.

7. **Confirmation can hide deny-all behavior.** A low unsafe-effect rate is not
   useful if benign actions are routinely denied or pushed to users. The paper
   must foreground tool TCR, initial ASK-or-DENY rate, confirmation outcomes,
   and actual confirmation burden.

8. **Operational failures can masquerade as safety.** Provider failures,
   parser failures, and max-step exits must stay in the ITT security denominator
   and remain visible by condition. Any imbalance requires root-cause analysis,
   not result exclusion.

9. **SIREN cannot currently support an implementation claim.** The fixed VIGIL
   repository contains no identifiable SIREN loader/evaluator, so SIREN is an
   external-validity target only after official code or a fixed data artifact is
   available.

10. **Venue fit and quartile are not frozen facts.** JISA appears
    scope-compatible, but SCIE/JCR Q2 must be confirmed through an institutional
    source at submission. The paper should not optimize its claims around a
    third-party quartile page.

11. **The medium matrix is a falsification gate, not the final sample.** It has
    36 attack and 36 benign cases. Even a large point difference cannot by
    itself support the planned formal-scale or cross-model claim. The achieved
    discordance must drive power analysis, and the paper must not present
    canary or partial rows as confirmatory evidence.

12. **A provider-managed model alias limits exact reproducibility.** The
    request chain proves that the official endpoint returned
    `deepseek-v4-pro`; it does not freeze hidden weights or a provider revision.
    Temporal replication and a second auditable model remain necessary.

13. **JSON Output is part of the experimental transport.** v4 fixes
    `response_format=json_object` for all six conditions after v3 exposed a
    parse failure under text output. This is a prospective, condition-invariant
    reliability control, but the manuscript must disclose the failed versions
    and must not compare their records to v4 effects.

14. **UTR and DSR are not separately identifiable in the medium record.** The
    frozen common contract contains unsafe effect and task completion, not a
    per-action authorization label or a distinct spill label. Reporting
    unsafe-effect rate under either legacy name would be a metric-semantics
    error. Dataset-specific later results need explicit denominators.

15. **Repeated pre-result gate revisions need a transparent audit trail.**
    Several never-activated candidates were superseded after schema and
    analysis-coverage review. This is defensible only because outcomes remained
    sealed, each old manifest identity is retained, and the final candidate was
    frozen before result admission.

## Pre-submission rejection checklist

- Reject the mechanism route if any of the security, utility, or module gates
  fails.
- Reject any table with a missing numerator/denominator or a silently removed
  operational failure.
- Reject performance claims for a baseline whose official model path did not
  run.
- Reject “independent blind” unless custody evidence is complete.
- Reject first/only/SOTA wording unless the claim ledger is explicitly amended
  after a new search.
- Reject the manuscript if result tables cannot be regenerated from frozen
  records and manifests.
- Reject any UTR/DSR table that lacks a frozen, directly labeled denominator.
- Reject use of v1–v3 failed matrix records in a v4 comparison.
- Reject a claim that the official model alias fixes an immutable weight
  revision.
