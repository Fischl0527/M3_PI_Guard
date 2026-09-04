# JISA submission package index

Status: `latex_primary_verified_author_completion_required`

This is the handoff index for the LaTeX-based submission route to the
*Journal of Information Security and Applications* (JISA). The flat package
under `../../../../LaTeX通用模板/M3_PI_Guard_JISA/` follows Elsevier's source-file
constraint that an Editorial Manager LaTeX submission must not depend on
subdirectories. The Markdown manuscript remains the scientific-content source;
the LaTeX package is the formatting and submission source of truth.

## Files for Editorial Manager

| Upload role | Controlled file | State at this checkpoint | Final action |
|---|---|---|---|
| Main LaTeX source | `../../../../LaTeX通用模板/M3_PI_Guard_JISA/M3_PI_Guard_JISA.tex` plus same-level inputs | Official `elsarticle` source; six main sections, six numbered main tables, one inline decision table, five vector figures and 21 cited references | Add approved author/title-page information, then upload all same-level source files |
| Main review PDF | `../../../../LaTeX通用模板/M3_PI_Guard_JISA/M3_PI_Guard_JISA.pdf` | 55 pages; XeLaTeX/BibTeX exit 0; no unresolved citation/reference, overfull box or author metadata; rendered pages visually checked | Recompile after author completion and upload if requested |
| Supplementary LaTeX source | `../../../../LaTeX通用模板/M3_PI_Guard_JISA/M3_PI_Guard_JISA_supplement.tex` plus same-level table inputs | Twelve supplementary tables; independent 12-page PDF compiled and visually checked | Confirm the final supplementary-material label in Editorial Manager |
| Highlights | `M3_PI_Guard_JISA_highlights.docx` | Five current editable highlights; every item is at most 85 characters and the 1/1-page render passed visual review | Upload as the separate Highlights file |
| Cover letter | `M3_PI_Guard_JISA_cover_letter.docx` | Current E1--E6 scientific wording is synchronized, contains no cross-provider or SOTA claim, and the 1/1-page render passed visual review | Fill the submission date and corresponding-author signature block |
| Glossary | `M3_PI_Guard_JISA_glossary.docx` | Fifteen field-specific terms are prepared in editable form | Upload only if requested by the live submission workflow |
| Figure 1 | `../incremental_empirical_v1/figures/figure_1_authority_boundary.pdf` | Separate vector PDF prepared | Upload as Figure 1 |
| Figure 2 | `../incremental_empirical_v1/figures/figure_2_factorial_interactions.pdf` | Separate vector PDF prepared | Upload as Figure 2 |
| Figure 3 | `../incremental_empirical_v1/figures/figure_3_provenance_counterfactual.pdf` | Separate vector PDF prepared | Upload as Figure 3 |
| Figure 4 | `../incremental_empirical_v1/figures/figure_4_factor_effect_forest.pdf` | Separate vector PDF prepared | Upload as Figure 4 |
| Figure 5 | `../incremental_empirical_v1/figures/figure_5_adaptive_tail.pdf` | Separate vector PDF prepared | Upload as Figure 5 |
| Local template review only | `../../../../LaTeX通用模板/M3_PI_Guard_template_review.tex` | Uses the supplied `cumcmthesis` assets and compiles to a 49-page local comparison PDF | Do not submit as a JISA source file |

The relative figure paths above are resolved from this manuscript directory.
SVG files in the same figure directory remain editable sources; PNG files are
review previews and should not replace the vector PDFs unless the live portal
rejects PDF artwork.

## Internal author-completion files

Do not upload these files with unresolved placeholders:

- `M3_PI_Guard_JISA_author_input_form.docx`: editable English completion form.
- `author_metadata_and_submission_inputs.md`: controlled English source form.
- `author_metadata_and_submission_inputs_zh.md`: Chinese direct-fill companion.
- `M3_PI_Guard_JISA_chinese_comparison.docx`: internal Chinese comparison copy,
  not the JISA manuscript.
- `jisa_submission_checklist.md`: live author and institutional checklist.

## Author-owned completion order

1. Fill author names/order, affiliations, corresponding-author details and
   ORCID values in the internal form.
2. Obtain every author's approval of the manuscript and CRediT allocation;
   confirm competing interests, funding, acknowledgements and ethics wording.
3. Replace provisional data/code release wording with the intended public tag
   and, when available, an archival DOI or other immutable identifier.
4. Add each author biography (100 words maximum) and passport-type photograph
   if the live JISA workflow still requests them.
5. Recompile the final LaTeX source with XeLaTeX/BibTeX and inspect every PDF
   page for pagination, figure placement, table wrapping and font substitution.
6. On the actual submission date, use the institution's subscribed database to
   confirm that JISA is still SCIE indexed and JCR Q2, then complete the
   similarity/self-plagiarism check and upload.

## Current verification boundary

- The historical Stage 4.5 integrity gate remains recorded. The current E1--E6
  claim ledger, tables and bilingual prose were rebuilt from the admitted compact
  analyses; E5 remains a conditional B200-survivor tail and E6 remains a
  risk-enriched single execution block.
- The submission-facing `elsarticle` main manuscript (55 pages), independent
  supplement (12 pages), and local template review copy (49 pages) compile with
  exit 0. Logs contain no LaTeX error, undefined citation/reference or overfull
  box; the PDFs contain no raw citation marker, `??` or replacement glyph.
  Page-level visual review found no clipping, overlap, repeated caption or
  missing figure. An initially isolated portrait page and an avoidable S12
  continuation page were corrected before this checkpoint.
- Author names, affiliations, corresponding-author details and CRediT roles
  remain intentionally unfilled for the owner to complete. The internal author
  form and Chinese comparison copy are not upload-ready submission files.
- Gemini's E6 prefix did not qualify for effect estimation; all Gemini paired,
  factorial and cross-provider effects remain `NE`. The manuscript makes no
  cross-provider, temporal-repeatability, deployment-prevalence or SOTA claim.
- No provider API, new experiment, Full Harness, historical replay, blind test,
  or additional evidence bundle was run for this manuscript integration.

The former Word files are retained only as historical/internal review copies.
They are not the current formatting source and should not be used to overwrite
the verified LaTeX manuscript.
