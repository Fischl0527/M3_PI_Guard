# paper-v2 lean empirical manuscript workspace

Status: `deepseek_authorization_results_complete_gemini_pending`

This directory is a complete working-paper workspace, but not yet a
submission-ready package. It contains the active manuscript, existing
Pro/Flash/medium/adaptive results, a frozen 900-row DeepSeek authorization
experiment, a planned 450-row Gemini free-tier cross-provider validation, a
figure/table plan, and bounded review material.

Current working title:

> Evaluating Runtime Authorization Under Context and Provenance Uncertainty for
> Tool-Using LLM Agents

The former “Beyond Answer-Key Authorization” title is suspended because the
22-unit source audit did not establish a domain-wide oracle-authorization
problem. It can be restored only after independent source review supplies
stronger evidence.

The medium falsification checkpoint is complete. Its result rejected
the defense-mechanism route because M3-full did not improve on policy-only and
missed the preregistered benign-tool non-inferiority criterion. The active route
is an empirical authorization-uncertainty and security–utility trade-off paper.
The 5,082-record Public primary result is complete and independently
reproduced, the 1,791-record DeepSeek Flash replication is complete, and the
900-record DeepSeek authorization-regime experiment now has terminal analysis,
five paper figures, and six tables. Gemini supports a cross-provider claim only
if all 450 planned work items reach terminal status under the three-quota-day
rule.

Files:

- `manuscript_deepseek_v1.md`: reader-facing unified English working draft
  assembled from the reviewed sections. Rebuild it with
  `F:\robot\Anaconda3\python.exe -B scripts/build_lean_paper_manuscript.py`;
  the builder enforces section order, the JISA abstract limit, bibliography
  coverage, figure/table availability, main-versus-supplementary numbering, and
  removal of workflow-only metadata.
- `M3_PI_Guard_JISA_working_draft.docx`: editable, single-column Word review
  copy with citeproc-rendered author-year citations, 21 cited references,
  six numbered main tables, one inline decision table, and five figures.
  Rebuild it with
  `python scripts/build_lean_paper_docx.py` using a Python environment with
  `python-docx` and Pandoc. Structural and accessibility checks pass; visual
  page rendering remains pending on a host with LibreOffice, Word or WPS.
- `supplementary_tables_v1.md` and
  `M3_PI_Guard_JISA_supplementary_tables.docx`: the six detailed tables S1-S6
  referenced from Results. Rebuild both with
  `python -m scripts.build_lean_paper_supplement`; the main manuscript retains
  every interpretation and denominator while the editable supplement carries
  the full tables.
- `introduction_draft.md`: source-status-aware motivation, RQs, bounded
  contributions, admitted medium route decision and exploratory adaptive
  boundary.
- `methods_draft.md`: active lean Methods, failed-row recovery rule and
  focused-only verification contract.
- `results_shell.md`: active Results draft covering medium, Public Pro/Flash,
  the DeepSeek authorization experiment, and adaptive budgets 50/200.
- `discussion_draft.md`: active interpretation of the DeepSeek authorization
  findings, with the cross-provider section still pending Gemini.
- `conclusion_draft.md`: provisional conclusions bounded to completed DeepSeek
  and budget-50/200 evidence.
- `figure_table_captions_v1.md`: publication-facing captions with denominators,
  endpoint semantics and claim boundaries.
- `declarations_draft.md`: provisional competing-interest, funding,
  availability, AI-use, safety and CRediT language requiring author approval.
- `submission_statements_draft.md`: reader-facing statement block included in
  the working manuscript. It records the known data/code, AI-use and safety
  facts while leaving competing interests, funding, institutional review and
  CRediT as explicit author-confirmation gates.
- `cover_letter_draft.md`: a concise, results-bounded JISA cover letter draft.
  It follows Elsevier's current general cover-letter guidance, excludes
  funding/declarations/reviewer suggestions, and remains contingent only on
  final author details and Gemini's prespecified stopping rule.
- `citation_compliance_active_v1.md`: submission-focused metadata and claim-fit
  review for the 21 references actually cited in the manuscript.
- `author_metadata_and_submission_inputs.md`: author-owned title-page,
  declaration, CRediT, biography and release fields that must be completed by
  the author team rather than inferred from the repository.
- `glossary_v1.md`: separate definitions for the field-specific terms used in
  the manuscript, prepared for the JISA submission package.
- `abstract_shell.md`: provisional DeepSeek-results abstract; the final
  cross-provider sentence remains contingent on Gemini's stopping rule.
- `highlights_v1.md`: five JISA-length highlights summarizing the current
  method and DeepSeek results.
- `figure_table_plan.md`: lean data-source map for five main figures and six
  tables; no hash bundle or recursive evidence replay is required.
- `pre_result_integrity_audit_v1.md`: scoped data/method/failure-mode audit of
  the admitted medium manuscript assets; explicitly not a formal Stage 2.5
  pass.
- `critical_citation_refresh_v1.md`: authoritative metadata and abstract-level
  audit of the ten papers that define the closest innovation boundary.
- `full_citation_refresh_v1.md`: historical 34-source audit; the active
  bibliography now adds the 2026 provenance-sensitivity measurement paper.
- `references_v1.bib`: 36-entry bibliography that explicitly distinguishes
  peer-reviewed work from preprints.
- The admitted Public-primary result path includes a second computation
  implementation that independently reproduces condition counts, Wilson
  intervals, four critical paired differences, exact McNemar tests, and ITT
  diagnostic retention.
- `related_work_draft.md`: source-status-aware positioning, audited contexts
  for the closest innovation-boundary papers, and the completed bibliography
  binding; submission-date refresh remains pending.
- `claim_evidence_ledger_lean_v1.json`: active 13-claim ledger for the lean
  empirical manuscript, including completed DeepSeek claims, Gemini and JCR
  gates, and explicit forbidden claims.
- `claim_evidence_ledger_v1.json`: retained historical paper-v2 ledger; it is
  not the active source for the lean manuscript because it includes superseded
  blind, large-adaptive and full-Harness gates.
- `devils_advocate_review.md`: novelty, validity, reproducibility, and venue
  risks that must be answered before submission.
- `completion_scorecard_v1.json`: historical pre-Public readiness baseline.
- `completion_scorecard_v2.json`: historical post-Public scorecard; its blind,
  budget-500/2,000 and full second-model requirements were superseded by the
  owner-approved lean plan and are not active acceptance gates.
- `jisa_submission_checklist.md`: official-scope, journal-package and
  result-dependent submission gates.

Current DeepSeek analysis products are under
`docs/research/paper_v2/lean_empirical/`: the compact analysis JSON is
`authorization_results_deepseek_v1.json`, the five PNG/SVG/PDF figure triplets are in
`figures_deepseek_v1/`, and the six CSV tables are in
`tables_deepseek_v1/`. These are single-model products; their metadata
explicitly disables a cross-provider claim while Gemini remains pending.

The active execution freeze is
`protocols/paper_upgrade_v2/lean_empirical_execution_plan_v1.jsonl`; the active
compact design manifest is
`protocols/paper_upgrade_v2/lean_empirical_execution_manifest_v1.json`.
