# paper-v2 lean empirical manuscript workspace

Status: `current_corrected_evidence_integrated_submission_in_progress`

2026-10-08 current entry: [English main article](manuscript_current_v2.md)
and [Chinese content comparison](manuscript_current_zh_v2.md). The English
body is 8,148 words; the separate complete working draft remains 15,838 body
words. Current evidence covers the corrected 900 authorization assignments,
480 contemporary calibration assignments, 16 component controls and the
post-outcome review of 60 benign tasks. Four current main figures and four main
tables are included; twenty historical supplementary tables and five historical
figures remain available separately. This does not establish defense superiority,
cross-provider generalization or submission readiness.

See [the executed closeout report](current_manuscript_closeout_2026-10-08.md)
for exact checks, limitations and the outputs directory map. Current PDFs have
35 pages (local template) and 26 pages (Elsevier article); authors remain blank.
The unchanged 24-page supplement retains its preceding verification result.
The dated September descriptions below are historical context, not current
page counts or current scientific acceptance.

2026-09-05 update: Methods/Results now include the P0/P2 diagnostics and E7a
execution-permit study, with its permission-only, no-backend-effect boundary.
Native E8 remains unevaluated. See `usability_manuscript_update_v1.md` for the
revision, exact verification commands and the `outputs/` QA directory map.

This directory is a complete working-paper workspace, but not yet a
submission-ready package. It contains the active manuscript, existing
Pro/Flash/medium/adaptive results, a frozen 900-row DeepSeek authorization
experiment, two closed incomplete Gemini free-tier diagnostic studies, a
figure/table plan, and bounded review material.

Current working title:

> Evaluating Authorization Regimes and Runtime Guardrail Configurations for
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
900-record DeepSeek authorization-regime experiment has terminal analysis. The
incremental E1--E6 studies are complete. E5 closed at 0/12 new first successes
among selected B200 survivors through query 500 (Wilson upper limit 24.25%). E6
closed as a 360-row DeepSeek, risk-enriched single-block calibration; its nested
Gemini prefix failed the technical gate. That historical package used five main figures,
seven main tables and twelve supplementary tables; the current four/twenty
layout is described above. Neither incomplete Gemini
dataset supports estimation of a cross-provider effect.

Files:

- `../../../../LaTeX通用模板/M3_PI_Guard_JISA/` is the submission-facing,
  flat Elsevier LaTeX package. Its `M3_PI_Guard_JISA.tex` entry uses
  `elsarticle`; the independent `M3_PI_Guard_JISA_supplement.tex` entry carries
  Tables S1--S20 and Figures S1--S5. The current PDFs have 26 and 24 pages, respectively, and
  deliberately contain no author metadata. Rebuild instructions are in
  `LaTeX通用模板/README.md` at the repository root. This LaTeX package, rather
  than the Word rendering, is now the formatting source of truth. The user's
  `数模通用模板.tex` review entry has 35 A4 pages with Times New Roman and
  40 PDF outline entries; the submission-facing entry retains elsarticle style.
- `manuscript_current_v2.md` / `manuscript_current_zh_v2.md`: current compact
  English article and Chinese content comparison. From the repository root run
  `python -X utf8 -B -m scripts.build_lean_paper_manuscript --profile current`,
  then `python -X utf8 -B -m scripts.build_jisa_latex --main-markdown manuscript_current_v2.md`.
  These explicit options select the compact article. The default build remains
  the full working draft for compatibility; it must not be mistaken for the
  compact publication-facing entry.
- `manuscript_deepseek_v1.md`: reader-facing unified English working draft
  assembled from the reviewed sections. Rebuild it with
  `F:\robot\Anaconda3\python.exe -B scripts/build_lean_paper_manuscript.py`;
  the builder enforces section order, the JISA abstract limit, bibliography
  coverage, figure/table availability, main-versus-supplementary numbering, and
  removal of workflow-only metadata.
- `M3_PI_Guard_JISA_working_draft.docx`: historical editable, single-column Word review
  copy with citeproc-rendered author-year citations, 21 cited references,
  six numbered main tables, one inline decision table, and five figures.
  Rebuild it with
  `python scripts/build_lean_paper_docx.py` using a Python environment with
  `python-docx` and Pandoc. Structural and accessibility checks pass; the
  current 35-page WPS render passed page-by-page visual review on 2026-09-04.
- `manuscript_zh_v1.md`: complete Simplified Chinese working comparison with
  six sections, current main evidence and retained historical detail. It is
  not the compact main article; use `manuscript_current_zh_v2.md` for that.
  `M3_PI_Guard_JISA_chinese_comparison.docx` remains a historical review copy
  (21 references and six main tables), not updated in this LaTeX-only revision.
  The Chinese files are for author review and team communication rather than
  JISA submission. Historical Word rebuild command:
  `python -m scripts.build_lean_paper_chinese_docx` in an environment with
  `python-docx` and Pandoc. The current 30-page WPS render passed page-by-page
  visual review on 2026-09-04.
- `supplementary_tables_v1.md`: all twenty detailed historical tables S1-S20
  and five historical figures S1-S5. The Word supplement remains historical;
  for Markdown-only rebuilding use
  `python -m scripts.build_lean_paper_supplement --markdown-only`.
- `introduction_draft.md`: source-status-aware motivation, RQs, bounded
  contributions, admitted medium route decision and exploratory adaptive
  boundary.
- `methods_draft.md`: active lean Methods, failed-row recovery rule and
  focused-only verification contract.
- `results_shell.md`: active Results draft covering medium, Public Pro/Flash,
  the DeepSeek authorization experiment, E1--E6, adaptive budgets 50/200, and
  the completed conditional B200-survivor tail through 500.
- `discussion_draft.md`: active interpretation of the authorization,
  prompt×module, source-authority, challenge and replication findings, with the
  closed incomplete Gemini diagnostic boundary.
- `conclusion_draft.md`: conclusions bounded to completed DeepSeek evidence,
  the conditional E5 estimand, and the E6 single-block calibration.
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
  author-owned submission details. Its synchronized editable Word attachment
  passed a single-page WPS visual review on 2026-09-04.
- `citation_compliance_active_v1.md`: submission-focused metadata and claim-fit
  review for the 24 references actually cited in the manuscript, with the
  incremental three-source review separated from the earlier 21-source review.
- `author_metadata_and_submission_inputs.md`: author-owned title-page,
  declaration, CRediT, biography and release fields that must be completed by
  the author team rather than inferred from the repository.
- `author_metadata_and_submission_inputs_zh.md`: Chinese direct-fill companion
  for the same author-owned submission facts; it is not manuscript content.
- `glossary_v1.md`: separate definitions for the field-specific terms used in
  the manuscript, prepared for the JISA submission package.
- `abstract_shell.md`: DeepSeek-results abstract with the closed Gemini
  diagnostic boundary and no cross-provider inference.
- `highlights_v1.md`: five JISA-length highlights summarizing the current
  E1--E6 evidence. The synchronized editable Word attachment passed a
  single-page WPS visual review on 2026-09-04.
- `figure_table_plan.md`: original E1--E6 data-source map for five main figures,
  six main tables and twelve supplementary tables. The new Table 7 source and
  endpoint contract are in `usability_manuscript_update_v1.md`; no hash bundle
  or recursive evidence replay is required.
- `pre_result_integrity_audit_v1.md`: scoped data/method/failure-mode audit of
  the admitted medium manuscript assets; explicitly not a formal Stage 2.5
  pass.
- `critical_citation_refresh_v1.md`: authoritative metadata and abstract-level
  audit of the ten papers that define the closest innovation boundary.
- `full_citation_refresh_v1.md`: historical 34-source audit; the active
  bibliography now adds the 2026 provenance-sensitivity measurement paper.
- `references_v1.bib`: 39-entry bibliography that explicitly distinguishes
  peer-reviewed work from preprints.
- The admitted Public-primary result path includes a second computation
  implementation that independently reproduces condition counts, Wilson
  intervals, four critical paired differences, exact McNemar tests, and ITT
  diagnostic retention.
- `related_work_draft.md`: source-status-aware positioning, audited contexts
  for the closest innovation-boundary papers, and the completed bibliography
  binding; submission-date refresh remains pending.
- `../../../../harness/state/paper_v2/claim_evidence_ledger_lean_v1.json`: current and historical claim ledger for the lean
  empirical manuscript, including completed DeepSeek claims, both closed Gemini diagnostics and JCR
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

Historical lean DeepSeek analysis products are under
`outputs/experiments/lean_empirical/`: the compact analysis JSON is
`analysis/authorization_results_deepseek_v1.json`, the five PNG/SVG/PDF figure triplets are in
`figures_deepseek_v1/`, and its six legacy CSV tables are in
`tables_deepseek_v1/`. These are single-model products; their metadata
explicitly disables a cross-provider claim because Gemini closed incomplete.

The active execution freeze is
`protocols/paper_upgrade_v2/lean_empirical_execution_plan_v1.jsonl`; the active
compact design manifest is
`protocols/paper_upgrade_v2/lean_empirical_execution_manifest_v1.json`.
