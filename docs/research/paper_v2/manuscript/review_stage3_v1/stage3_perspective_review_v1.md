# Stage 3 Review 4 — Cross-Disciplinary Usable-Security Perspective

## Dimension Scores

| Dimension | Score | Basis |
|---|---|---|
| D1 methodology rigor | `warn` | ASK/DENY, failure, latency, and completion are measured, but the main burden table pools attack and benign workflows and no human confirmation process is observed. |
| D2 domain accuracy | `pass` | The paper explicitly states that pending ASK decisions cannot be interpreted as successful human approval and makes no human-participant claim. |
| D3 argumentative coherence | `pass` | The paper consistently treats low unsafe-effect rate and usable task completion as joint considerations. |
| D4 cross-disciplinary relevance | `warn` | The usable-security bridge is promising but needs benign-workflow stratification and support from human-in-the-loop security literature. |
| D5 writing and structure | `warn` | Figure 4 is effective, while Figure 2 compresses the floor-limited security evidence and the repeated diagnostic caveats interrupt the main trade-off story. |

## Failure Condition Checks

- F1: not triggered; no mandatory dimension receives `block`.
- F2: not triggered by this reviewer because only one mandatory dimension is
  warn-or-worse.
- F3: not triggered; D4 is `warn`, not `block`.
- F0: not satisfied because D1 is `warn`.

## Review Body

### Strengths

The paper does more than report attack success. It retains task completion,
ASK, DENY, operational failure, latency, token, and cost data, and it rejects a
deny-all interpretation as useful security. It also correctly refuses to infer
human confirmation success from a synthetic pending state. This is stronger
usable-security hygiene than most agent-defense evaluations.

### Major issues

#### PERS-M1 — Report burden on benign tool workflows separately

Table 4 reports ASK, DENY, failure, and latency across all 180 records per main
condition, mixing attack, benign-tool, and benign-no-tool tasks. A deployer
needs to know how often legitimate effectful work is interrupted. Add an
offline panel for the 60 benign-tool tasks by condition and authorization
regime, ideally also separated by benchmark. Retain attack burden separately.
Do not call an all-task ASK rate “confirmation burden” without this breakdown.

#### PERS-M2 — Separate system burden from human burden

Use “confirmation-request incidence” or “system ASK incidence” for the measured
quantity. Reserve “user burden,” “approval burden,” or claims about habituation
for a future human study. The manuscript mostly respects this boundary, but
the abstract, discussion, figure title, and practical implications should use
the stricter terminology consistently.

#### PERS-M3 — Ground practical implications in usable-security literature

The recommendation that confirmation may be acceptable in high-consequence
workflows but unacceptable in routine automation is plausible, not measured.
Add a small set of primary human-factors/permission-prompt studies or rewrite
the statement as a design hypothesis. No new participant study is needed for
this manuscript if the claim remains explicitly prospective.

### Minor issues

1. Figure 4 is the manuscript's most useful operational visualization. Add raw
   denominators or direct readers to Table 4 in the caption.
2. Figure 2 should plot unsafe-effect rate rather than `1 − unsafe-effect rate`
   on a 0–100 axis; all points currently sit at the top border.
3. Explain whether a pending ASK always leads to no simulated effect and no
   task completion, or whether later trajectory steps can proceed.
4. Separate latency cost attributable to extra model turns from latency caused
   by failure/recovery.
5. A short deployment scenario would help readers understand why exact argument
   rules can increase DENY despite appearing more informative.

## Editorial Decision

**Major revision.** No human study is required, but the measured system burden
must be stratified and the language must not imply validated human usability.

