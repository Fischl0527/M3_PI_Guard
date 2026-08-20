# Devil’s Advocate review — lean empirical manuscript

Status: post-DeepSeek review; Gemini stopping rule pending

## Overall verdict

The manuscript is viable as a bounded empirical security study, not as a new
leading-defense paper. Its strongest contribution is the paired demonstration
that authorization construction changes benign utility, blocking, failure,
and latency even when the attack endpoint is near zero. The negative result
that M3-full does not reliably improve on policy-only is publishable if it
remains central rather than being softened in the final revision.

The current draft would merit major revision rather than immediate rejection.
Most rejection risks are already addressed, but four gates remain external to
the scientific text: the Gemini stopping rule, institutional confirmation of
JISA's submission-time SCIE/JCR quartile, author-owned declarations, and visual
inspection of the final Word/PDF rendering.

## Highest-risk rejection arguments and current disposition

1. **“The proposed mechanism is not novel.” — Addressed by repositioning.**
   VIGIL, DRIFT, Task Shield, IPIGuard, Progent, CaMeL, ARGUS, AuthGraph, FAVA,
   and provenance-sensitivity auditing already occupy adjacent mechanism and
   evaluation space. The paper no longer claims a first provenance tracker or
   a leading defense. Its novelty is the paired authorization-regime evaluation
   with executed effects, utility, burden, and ITT failures.

2. **“The new attack endpoint is uninformative because of a floor effect.” —
   Material limitation.** Only one unsafe effect appears across the 400 primary
   attack records in the 900-work-item authorization experiment. That experiment
   supports utility and burden conclusions much more strongly than security
   differences. The larger Public matrices must carry the security-direction
   evidence. A new limitation now states this explicitly.

3. **“The paper calls an implementation-specific exact policy an oracle
   effect.” — Controlled but still easy to overstate.** `exact_gold` is an
   intentionally artificial sensitivity condition. In this implementation it
   became more restrictive, not more useful. The text correctly reports this as
   authorization sensitivity in the tested compiler and never as proof that
   gold-derived policy generally inflates security or utility.

4. **“M3-full is worse than its ablation, so the defense contribution fails.”
   — Accepted negative result.** Public V4 Pro and Flash both show more unsafe
   effects under full than policy-only, and the new paired experiment shows no
   stable full-module advantage. The title, abstract, Discussion, Conclusion,
   and cover letter consistently present an evaluation contribution instead of
   a mechanism-superiority claim.

5. **“Failure imbalance can masquerade as safety.” — Disclosed, not eliminated.**
   Public diagnostics are uneven by condition, and exact authorization raises
   failure to roughly 24%. Failures remain in ITT and are reported next to
   unsafe effects and completion. The paper must retain raw failure counts in
   every final table and avoid interpreting a failed execution as positive
   evidence of a useful defense.

6. **“Bootstrap intervals exclude zero but corrected tests do not.” — Correctly
   bounded.** The exact-policy utility contrasts have clustered-bootstrap
   intervals excluding zero, while Holm-adjusted McNemar p-values exceed 0.05.
   The manuscript reports both and describes the result through direction and
   effect size rather than claiming conventional significance.

7. **“The structural baseline is not part of the new DeepSeek factorial.” —
   Transparent design choice.** The new primary experiment isolates policy-only
   versus full and auto versus exact. Structural comparisons come from the
   completed Public and medium matrices; Gemini adds a structural cell only if
   its entire 450-item cohort becomes inferentially eligible. The paper must not
   imply a six-condition DeepSeek authorization factorial.

8. **“Partial Gemini data are being used opportunistically.” — Prevented by
   analysis and prose.** Partial response-less rows are operational accounting
   only. Cross-provider comparisons, Tables 2–5, and external-validity prose
   require 450/450 terminal work items. After three provider quota days, an
   incomplete observed subset is diagnostic and unstarted items are explicitly
   unavailable.

9. **“The adaptive evidence is too shallow.” — Accepted scope limit.** Budgets
   50 and 200 show material budget sensitivity but cannot establish saturation,
   hardest-task robustness, or an asymptotic attack rate. The curve and text
   consistently stop at 200.

10. **“Official model aliases are not immutable model revisions.” — Disclosed
    reproducibility limitation.** The Methods now reports the July–August 2026
    execution window and states that official response identifiers and returned
    model names identify the served model at request time without freezing its
    hidden weights.

11. **“The isolated effect environment is not deployment evidence.” — Accepted
    safety trade-off.** Isolation prevents real email, payment, browser, code,
    or production effects. It also omits live-system state and recovery. The
    paper claims executed benchmark effects, not production incident rates.

12. **“No independent blind set weakens external validity.” — Disclosed.** The
    active paper does not claim independent blind evaluation. This absence is a
    limitation, not a hidden unfinished experiment and not a submission blocker
    for the bounded empirical claim.

13. **“The manuscript is too process-heavy.” — Substantially addressed.** Main
    prose excludes Harness versions, hashes, admissions, run directories, and
    historical recovery narratives. Reproducibility is described through the
    frozen design, append-only rows, bounded retry rule, and compact release
    assets.

14. **“The venue or quartile is asserted without authoritative evidence.” —
    Open submission gate.** JISA scope is compatible, but current SCIE/JCR Q2
    status must be confirmed through the institution at submission. No claim in
    the manuscript should depend on a third-party quartile site.

## Required final checks

- Keep the one-event attack floor explicit in Results and Limitations.
- Preserve every unfavorable M3-full versus policy-only comparison.
- Keep numerator/denominator, Wilson interval, paired effect, corrected test,
  and failure count together wherever a headline result appears.
- Include Gemini in inference only if all 450 frozen work items are terminal;
  otherwise report the stopping-rule outcome without a cross-provider claim.
- Do not add first, only, SOTA, saturation, causal-provenance, production, or
  independent-blind language.
- Obtain author confirmation for identities, affiliations, funding, competing
  interests, CRediT roles, ethics/institutional review, and final AI-use text.
- Confirm JISA's current indexing/quartile through the institutional source and
  visually inspect the final editable source/PDF before submission.
