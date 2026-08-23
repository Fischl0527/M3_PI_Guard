# JISA submission package index

Status: `scientific_content_closed_author_completion_required`

This is the single handoff index for the Word-based submission route to the
*Journal of Information Security and Applications* (JISA). It does not create
a second copy of the manuscript, figures, or evidence. Paths below point to the
current controlled files in the repository.

## Files for Editorial Manager

| Upload role | Controlled file | State at this checkpoint | Final action |
|---|---|---|---|
| Main manuscript | `M3_PI_Guard_JISA_working_draft.docx` | Scientific text, 7 tables and 5 inline review figures are closed | Add the approved author/title-page information and complete the Word/WPS page review |
| Supplementary tables | `M3_PI_Guard_JISA_supplementary_tables.docx` | Editable supplementary tables are prepared | Confirm the final supplementary-material label in Editorial Manager |
| Highlights | `M3_PI_Guard_JISA_highlights.docx` | Five editable highlights; every item is at most 85 characters | Upload as the separate Highlights file |
| Cover letter | `M3_PI_Guard_JISA_cover_letter.docx` | Scientific wording is closed and contains no cross-provider or SOTA claim | Fill the submission date and corresponding-author signature block |
| Glossary | `M3_PI_Guard_JISA_glossary.docx` | Fifteen field-specific terms are prepared in editable form | Upload only if requested by the live submission workflow |
| Figure 1 | `../lean_empirical/figures_deepseek_v1/figure_1_online_field_isolation.pdf` | Separate vector PDF prepared | Upload as Figure 1 |
| Figure 2 | `../lean_empirical/figures_deepseek_v1/figure_2_safety_utility_pareto.pdf` | Separate vector PDF prepared | Upload as Figure 2 |
| Figure 3 | `../lean_empirical/figures_deepseek_v1/figure_3_authorization_forest.pdf` | Separate vector PDF prepared | Upload as Figure 3 |
| Figure 4 | `../lean_empirical/figures_deepseek_v1/figure_4_runtime_burden.pdf` | Separate vector PDF prepared | Upload as Figure 4 |
| Figure 5 | `../lean_empirical/figures_deepseek_v1/figure_5_adaptive_first_success.pdf` | Separate vector PDF prepared | Upload as Figure 5 |

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
5. Open the final manuscript and attachments in Word or WPS and inspect every
   page for pagination, figure placement, table wrapping and font substitution.
6. On the actual submission date, use the institution's subscribed database to
   confirm that JISA is still SCIE indexed and JCR Q2, then complete the
   similarity/self-plagiarism check and upload.

## Current verification boundary

- The Stage 4.5 scientific integrity gate passed with only non-blocking author
  and institutional warnings.
- The four new Word attachments pass focused structure, page-geometry and
  accessibility checks (0 high, 0 medium and 0 low findings for each file).
- LibreOffice/`soffice` and Poppler are unavailable on this machine. Therefore
  the package does not claim automated page-render QA; Step 5 above remains a
  required author action.
- No provider API, new experiment, Full Harness, historical replay, blind test,
  or additional evidence/hash package is required for this handoff.

The Word route is intentionally retained. No LaTeX or submission PDF duplicate
is generated because it would create an avoidable second formatting source of
truth for a journal that accepts editable Word files.
