# Pre-result manuscript integrity audit v1

Audit time: 2026-07-28 +08:00  
Scope: admitted medium Methods/Results/Discussion/abstract shell only  
Mode: pre-Stage-2.5 readiness audit; not a Stage 2.5 PASS  
Verdict: `NOT_READY_PENDING_PUBLIC_ADAPTIVE_AND_FULL_REFERENCE_INTEGRITY`

## Evidence boundary

This audit checks whether the current manuscript workspace faithfully describes
evidence already admitted by the project. It does not authorize public or
adaptive result access, does not verify a final bibliography, and does not
release the manuscript to peer review.

Authoritative inputs:

- `admitted_medium_analysis_v8.json`, SHA-256
  `ea3d6197b0f97b5057b1d0f9fff054f3ae43743eb9cb85eb4122b6c152d7e041`;
- combined result admission SHA-256
  `0ed21b6d934d8aefab95667adbf07203140d5cf3d115b891eef882eb9fb028d7`;
- technical review SHA-256
  `8b1d3f1db6a8b02f815087fc36e129ed99f398285e9b47124958a22a7021aeda`;
- `medium_gate_spec_v2.json`, prospectively frozen before v5 continuation;
- frozen medium, public, and adaptive manifests.

## Verification summary

| Category | Scope | Result | Evidence |
|---|---|---|---|
| Medium result counts and rates | 100% of six displayed conditions | PASS | Focused test rebuilds numerators, denominators and Wilson intervals from admitted JSON |
| Paired comparisons | Four displayed comparisons | PASS | Values match admitted McNemar, Holm and 10,000-cluster-bootstrap objects |
| Operational burden | Six conditions | PASS | ASK, benign ASK, failure, provider-call and cost prefixes rebuilt from admitted JSON |
| Result disposition | Mechanism gate and empirical fallback | PASS | `mechanism_paper_candidate=false`, module and utility gates retained as failed |
| Pending result isolation | Public and adaptive sections | PASS | All scientific cells remain literal `pending`; no favorable zero is inserted |
| Methods-to-run fidelity | Medium quality and result-admission rules | CORRECTED, THEN PASS | Stale zero-failure wording replaced with the frozen v2 quality and diagnostic envelopes |
| External references and citation contexts | Final paper | PARTIAL | All 34 matrix records were refreshed against authoritative sources; final bibliography and inline citation integration are incomplete |
| Originality and self-plagiarism | Final paper | NOT RUN | Final prose and author publication list are not available |

## Correction made during this audit

The pre-result Methods draft said that the mechanism gate and result admission
required zero operational failures. That statement no longer matched the
prospectively frozen v2 protocol used by the admitted v8+v9 analysis.

The corrected Methods now distinguishes:

1. the mechanism-claim quality envelope: all terminal primary records retained
   in ITT, overall operational failures at most 10%, provider/timeout failures
   at most 5%, and runner failures equal to zero; and
2. the technical result gate: complete 480-record coverage, no open/missing/
   duplicate/unknown work, prespecified terminal statuses, no runner failure,
   formal-candidate identity/trace requirements, and at most 1% closed
   diagnostic provider/timeout records.

The admitted evidence passed these gates with 479 formal-candidate records,
one closed diagnostic, zero open attempts, and 459 completed plus 21 retained
non-completed terminal records across the full 480-record matrix. The primary
432-record analysis contained 411 completed and the same 21 non-completed
terminal records.

## Numerical claim audit

The following high-impact claims were traced directly to the admitted analysis:

| Claim | Manuscript value | Source value | Verdict |
|---|---:|---:|---|
| Structural unsafe effects | 8/36 | 8/36 | VERIFIED |
| M3-full unsafe effects | 0/36 | 0/36 | VERIFIED |
| Security paired difference | −22.22 pp | −0.222222… | VERIFIED |
| Security bootstrap CI | −36.11 to −8.33 pp | −0.361111… to −0.083333… | VERIFIED |
| Structural benign-tool completion | 12/24 | 12/24 | VERIFIED |
| M3-full benign-tool completion | 6/24 | 6/24 | VERIFIED |
| Utility paired difference | −25.00 pp | −0.25 | VERIFIED |
| M3 policy-only unsafe effects | 0/36 | 0/36 | VERIFIED |
| M3-full initial ASK | 22/72 | 22/72 | VERIFIED |
| M3-full benign ASK | 8/36 (22.22%) | 8/36 | VERIFIED |
| Primary retained terminal failures | 21/432 (4.86%) | 21/432 | VERIFIED |
| Primary provider failures | 9/432 (2.08%) | 9/432 | VERIFIED |

No public-scale, cross-model, adaptive-success, independent-blind, or SOTA
number is asserted.

## Seven-mode AI research failure checklist

| Mode | Status | Evidence and remaining action |
|---|---|---|
| 1. Implementation bug passing self-review | CLEAR for admitted medium; recheck final | Analysis was admitted, independently rebuilt, hash-bound, and table values are independently read back by focused tests. Current full Harness remains a separate engineering gate. |
| 2. Hallucinated citation | PARTIAL—MATRIX CLEAR | All 34 matrix records were opened at authoritative sources. The audit corrected 18 title drifts, one unsupported venue suffix, one unrelated L20 source binding, and two stale publication-status/link records. Final inline citations and the complete submission bibliography still require 100% verification at formal Stage 2.5. |
| 3. Hallucinated experimental result | CLEAR for admitted medium | Every displayed medium number is traceable to the admitted JSON and admission digest. Pending experiments remain visibly pending. |
| 4. Shortcut reliance | INSUFFICIENT EVIDENCE | Policy-only/full pairing prevents one mechanism shortcut claim, but benchmark/model/adaptive generalization remains untested until public and adaptive execution. |
| 5. Bug reframed as insight | CLEAR after correction | The stale Methods statement was corrected instead of being narrated as a result. The negative module and utility gates remain explicit. |
| 6. Methodology fabrication | CLEAR for current medium description | Medium design, gate thresholds, coverage and failure handling now match frozen manifests and the admitted run. Recheck after public/adaptive Methods are added. |
| 7. Early frame-lock | CLEAR | The prospective fail-redirect was followed: the mechanism route was abandoned after its gate failed, rather than preserving the original preferred narrative. |

Mode 2 is partially cleared for the complete 34-entry matrix, while mode 4
remains `INSUFFICIENT EVIDENCE` until public and adaptive execution. Both must
be resolved or explicitly bounded before final integrity. Modes 1, 3, 5, and 6
are not left insufficient for the admitted medium claims.

## Mandatory work before formal Stage 2.5

1. Complete and admit all 6,873 public case-condition records.
2. Complete and admit the primary 40-task, second-model 20-task, and
   hardest-20 adaptive panels.
3. Regenerate final Results, Discussion, abstract, figures, and tables from
   admitted analysis files.
4. Integrate the final reference list and inline citations.
5. Verify every reference through publisher/DOI or other authoritative
   metadata with an audit trail; perform citation-context and originality
   sampling at the required rates.
6. Re-run all seven failure modes on the complete manuscript.
7. Obtain institutional JCR/SCIE verification at submission time.

Until these steps are complete, the document remains a results-ready partial
manuscript. The 34/34 citation refresh and synchronized manuscript assets raise
the evidence score to 753/1200 (62.75%, reported as 63%); they do not substitute
for the missing public, adaptive, second-model, or independent-blind evidence.
