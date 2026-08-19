# paper-v2 results-ready manuscript workspace

Status: `medium_public_primary_and_adaptive_canary_admitted`

This directory is deliberately not a completed paper. It contains the methods
contract, admitted medium and Public primary results, an exploratory adaptive
canary, still-pending formal adaptive/second-model cells, a claim–evidence
ledger, and an adversarial review.

Current working title:

> Evaluating Runtime Authorization Under Context and Provenance Uncertainty for
> Tool-Using LLM Agents

The former “Beyond Answer-Key Authorization” title is suspended because the
22-unit source audit did not establish a domain-wide oracle-authorization
problem. It can be restored only after independent source review supplies
stronger evidence.

The medium falsification checkpoint is complete. Its admitted result rejected
the defense-mechanism route because M3-full did not improve on policy-only and
missed the preregistered benign-tool non-inferiority criterion. The active route
is an empirical authorization-uncertainty and security–utility trade-off paper.
The 5,082-record Public primary result is complete and independently
reproduced. Formal adaptive and second-model evidence remain mandatory before
cross-model or robustness conclusions can be finalized.

Files:

- `introduction_draft.md`: source-status-aware motivation, RQs, bounded
  contributions, admitted medium route decision and exploratory adaptive
  boundary.
- `methods_draft.md`: pre-result Methods text and reproducibility contract.
- `results_shell.md`: admitted medium and Public primary results plus explicitly
  pending second-model and formal adaptive tables.
- `discussion_draft.md`: interpretation of admitted medium/Public evidence and
  boundaries for the still-pending adaptive and second-model studies.
- `abstract_shell.md`: branch-locked abstract structure containing admitted
  medium evidence and explicitly gated public/adaptive slots.
- `figure_table_plan.md`: data-source and admission map for five main figures
  and six main tables.
- `pre_result_integrity_audit_v1.md`: scoped data/method/failure-mode audit of
  the admitted medium manuscript assets; explicitly not a formal Stage 2.5
  pass.
- `critical_citation_refresh_v1.md`: authoritative metadata and abstract-level
  audit of the ten papers that define the closest innovation boundary.
- `full_citation_refresh_v1.md`: controlling 34/34 metadata,
  publication-status, abstract-level scope audit and completed authoritative
  bibliography export; final full-manuscript context audit remains pending.
- `references_v1.bib`: 34-entry bibliography (24 peer-reviewed, 10
  preprint-only), with offline integrity tests.
- The admitted Public-primary result path includes a second computation
  implementation that independently reproduces condition counts, Wilson
  intervals, four critical paired differences, exact McNemar tests, and ITT
  diagnostic retention. The v5 analysis also retains a hash-locked audit trail
  of four pre-summary validator/projection failures and their prospective
  corrections.
- `related_work_draft.md`: source-status-aware positioning, audited contexts
  for the closest innovation-boundary papers, and the completed bibliography
  binding; submission-date refresh remains pending.
- `claim_evidence_ledger_v1.json`: every intended claim, present evidence, and
  unlock condition.
- `devils_advocate_review.md`: novelty, validity, reproducibility, and venue
  risks that must be answered before submission.
- `completion_scorecard_v1.json`: historical pre-Public readiness baseline.
- `completion_scorecard_v2.json`: post-Public scientific-evidence completion
  estimate with the second model, blind custody, and formal adaptive work still
  counted as incomplete.
- `jisa_submission_checklist.md`: official-scope, journal-package and
  result-dependent submission gates.

The authoritative medium execution freeze is
`protocols/paper_upgrade_v2/medium_execution_plan_v2.jsonl`. The v1 execution
plan created no results and is retained only as a superseded pre-run artifact;
it did not distinguish case-level visibility from condition-specific runtime
visibility.
