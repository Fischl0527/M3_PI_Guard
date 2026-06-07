# DAY7 Final Submission Check

## Report
- DOCX: `docs/report/作品报告_终稿.docx`
- Format check: PASS
  - A4 page size: 21.0 cm x 29.7 cm.
  - Normal style font size: 12 pt, equivalent to 小四.
  - Normal style line spacing: 1.5.
  - Required sections present: 封面、填写说明、目录、摘要、第一章、第二章、第三章、第四章、第五章、参考文献.
  - Filling-instructions page retained.
  - Body template guidance replaced with final report content.
- PDF export: NOT GENERATED
  - Local LibreOffice/soffice command is unavailable.
  - Word COM export was attempted with fixed-format export and SaveAs2 PDF; both timed out in this environment.
  - Manual export from Word/WPS is required after updating the table of contents.

## Presentation
- PPTX: `docs/presentation/Redteam_LLM_Security_答辩PPT.pptx`
- Slide count: PASS, 12 slides.
- Suggested structure: PASS
  - Cover, background, threat model, architecture, attack samples, Agent range, Guard, metrics, results, case demo, innovation, summary.
- Visual QA: PASS
  - PowerPoint COM exported PNG previews to `outputs/quality/day7_ppt_preview/`.
  - Contact sheet generated at `outputs/quality/day7_ppt_contact_sheet.png`.
  - Dense slides 9, 10 and 12 were inspected individually.

## Supporting Materials
- Script: `docs/presentation/演示讲稿.md`
- Defense Q&A: `docs/presentation/答辩问题准备_综合.md`
- Screenshot checklist: `docs/presentation/截图清单.md`

## Trace Scan
- Scope: `docs/report/` and `docs/presentation/`.
- Result: PASS. No configured forbidden generation-trace terms were found in Markdown sources or unpacked DOCX/PPTX XML.

## Identity Leak Scan
- Scope: `docs/report/` and `docs/presentation/`.
- Result: PASS. No school, department, advisor, team-member name, or student-id fields were found.

## Manual Checklist
- Open the Word report in Word/WPS and update table-of-contents page numbers.
- Review final pagination after updating the table of contents.
- Export `docs/report/作品报告_终稿.pdf` manually from Word/WPS.
- Play through the PPT once on the submission machine and verify fonts render normally.
