# Discussion draft — admitted medium and Public primary evidence

Status: `medium_and_public_primary_interpreted_formal_adaptive_and_second_model_pending`

This section interprets the admitted 480-record DeepSeek medium study and the
independently reproduced 5,082-record Public primary-model matrix. Formal
adaptive and second-model evidence remain pending. Related-work claims remain
bound to the verified literature matrix.

## Security improvement did not establish a mechanism contribution

M3-full reduced the medium-study unsafe-effect rate from 8/36 under the
structural condition to 0/36. The Public primary matrix reproduced the
structural comparison at larger scale: 38/600 under M3-full versus 133/600
under the structural condition, a paired difference of −15.83 percentage
points (95% bootstrap CI −19.50 to −12.17).

Neither study isolates a positive contribution from provenance,
temporal/data-flow, and confirmation modules. M3 policy-only also produced
0/36 unsafe effects in the medium study. In the Public matrix, policy-only was
strictly safer than full: 13/600 versus 38/600, a full-minus-policy difference
of +4.17 points (95% CI 2.50–6.00). The added modules were therefore associated
with more, not fewer, unsafe effects under the frozen implementation and task
mix.

The evidence supports a narrower interpretation: restrictive runtime policy
enforcement can prevent many unsafe effects relative to the admitted
structural adapter, while the additional modules did not demonstrate
incremental security value. It does not support a claim that M3-full is a
superior defense architecture or that provenance tracking caused the observed
security reduction.

## The primary trade-off was utility, not deny-all behavior

The full monitor was not a literal deny-all system. In the medium study its
benign initial ASK-or-DENY rate was 22.22%, and all benign no-tool tasks
completed. Nevertheless, benign tool completion fell from 12/24 under the
structural condition to 6/24 under M3-full. Public evidence strengthened this
negative conclusion: completion was 49/168 under M3-full versus 103/168 under
the structural condition, a −32.14-point difference (95% CI −39.88 to
−25.00). M3-full and policy-only both completed 49/168.

All six Public conditions completed 79/79 benign no-tool tasks. The contrast
between perfect no-tool completion and low tool-task completion localizes the
main cost to authorization around action execution rather than general answer
generation. Benchmark strata sharpen this diagnosis: M3-full completed 36/71
M3-v2 tool tasks but only 13/97 AgentDojo tool tasks. Policy
underspecification, parameter-scope mismatch, unresolved confirmation, and
multi-step recovery should therefore be analyzed separately.

## Confirmation was measurable but unresolved

M3-full issued 22 `ASK` decisions across 72 primary records: 17 for permission
expansion, four for independent confirmation, and one for an out-of-scope
parameter. Eight of the 36 benign records entered `ASK`, yielding a 22.22%
benign ASK rate. All confirmation outcomes remained pending in the synthetic
medium environment.

These records quantify how often the system transfers a decision to a user,
but they do not measure whether a real user would approve correctly, how long
approval would take, or whether confirmation improves final task completion.
The manuscript must describe this quantity as confirmation burden, not as
successful human oversight.

## Authorization information changed behavior in small paired probes

The explicitly labeled exact-gold probe increased task completion from 1/6
under matched auto-compiled authorization to 3/6 and reduced initial ASK from
3/6 to 0/6. With only six pairs, neither comparison was statistically precise.
The broader set of regime probes also contained no unsafe effects, preventing a
security-effect comparison.

The probe therefore illustrates why authorization regime should be reported
as an experimental factor, but it does not establish that answer-key
authorization is a field-wide source of inflated security. The source audit
likewise supports only path-scoped statements. The neutral
authorization-uncertainty framing remains more defensible than the suspended
“Beyond Answer-Key Authorization” framing.

## Public diagnostic imbalance limits causal interpretation

The medium analysis retained 21 non-completed terminal records and stayed
inside its prospectively frozen quality envelope. The Public matrix retained
466 non-completed terminal records: 112 `max_steps`, 120 parse failures, and
234 provider failures. Seventy-six records were diagnostic (1.4955%), so the
frozen 1% mechanism-quality ceiling failed and was not waived.

Diagnostics were materially imbalanced: 27 structural, 24 safe-prompt, 22
M3-full, two no-defense, one PromptGuard, and zero policy-only. Because failure
can suppress an executed effect, this imbalance weakens a clean causal
interpretation of the full-versus-structural contrast. All assigned attacks
nevertheless remain in the conservative intention-to-treat denominator, and
the paper reports the result as an empirical fallback rather than mechanism
quality.

## Implications for evaluation design

Four design implications follow from the admitted evidence.

1. Runtime defenses should be evaluated on executed unsafe effects and benign
   task completion together. Detector accuracy or guard decisions alone cannot
   reveal the observed security–utility trade-off.
2. Policy-only and full systems require a direct paired comparison. Comparing
   only the full system with a weaker baseline would have hidden the absence of
   module gain.
3. Authorization regime and confirmation handling are part of the treatment.
   They must be frozen, disclosed, and separated from evaluator-only labels.
4. Terminal diagnostics require two distinct judgments: evidence integrity and
   mechanism-quality eligibility. Retaining a closed failure in ITT is not the
   same as claiming a clean completed provider trace.

These are empirical and methodological conclusions. They are not first,
unique, or state-of-the-art claims.

## Limits of the current evidence

Both completed studies use one provider-managed model alias. The structural
comparison reflects the admitted project adapter and does not establish
superiority over every provenance, planning, privilege, or information-flow
defense. UTR and DSR cannot be recovered from a record contract that lacks
their distinct denominators. The Public result is large but not independently
blind: no third-party author/custodian or custody chain exists.

DeepSeek Flash replication and the formal defense-aware adaptive panel remain
pending. Accordingly, the current evidence cannot support cross-model,
adaptive-robustness, independent-blind, or SOTA claims. If adaptive search
recovers unsafe effects, the paper must report query budgets and first-success
distributions and must not describe the static result as robust. No later
branch permits deletion of the medium or Public negative module-gain and
utility results.
