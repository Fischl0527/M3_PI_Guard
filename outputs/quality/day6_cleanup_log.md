# DAY6 Cleanup Log

## Summary

- Branch: `team-a/m3-core-day6`
- Release package: `release/Redteam_LLM_Security_v1.0/`
- Pre-clean scan record: `outputs/quality/day6_ai_trace_scan_before.txt`
- Release scan record: `outputs/quality/day6_release_ai_trace_scan.txt`
- Release checklist: `outputs/quality/day6_release_checklist.md`

## Cleaned Items

- Removed root-level historical planning notes from the submission branch:
  - `1、方向.md`
  - `2、具体实现方案.md`
  - `3、ABC分配任务.md`
- Removed personal day-by-day process reports from the submission branch:
  - `DAY2-REPORT-A.md`
  - `DAY3-TARGET-A.md`
  - `DAY3-REPORT-A.md`
  - `DAY4-REPORT-A.md`
  - `DAY5-TARGET-A.md`
- Removed the old generated package:
  - `release/M3_PI_Guard_v0.5/`
- Added ignore rules for local task prompts and personal process notes so they are not accidentally committed.
- Updated `README.md` to use formal project wording.
- Updated `scripts/make_release_package.ps1` to generate the final v1.0 package and exclude local-only artifacts.

## Validation

- `python -m py_compile m3_core/run_matrix.py m3_core/run_batch.py m3_core/agent_runner.py m3_core/check_logs.py m3_eval/evaluate.py`
- `python -m m3_core.run_matrix --cases fixtures/demo_cases.jsonl --backend stub --defense-modes baseline,full_guard --out-dir outputs/runs/day6_demo_stub_matrix --run-prefix day6_demo_stub --run-group day6 --max-steps 5`
- `python -m m3_eval.evaluate --log-dir outputs/runs/day6_demo_stub_matrix --cases fixtures/demo_cases.jsonl --out outputs/metrics/day6_demo_stub_summary.csv`
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/make_release_package.ps1`

## Results

- Stub demo baseline/full_guard logs were generated under `outputs/runs/day6_demo_stub_matrix/`.
- DAY6 summary CSV/JSON files were generated under `outputs/metrics/`.
- The release package scan file is empty, which means no forbidden development-process trace was found in `release/Redteam_LLM_Security_v1.0/`.
- The package excludes model files, sandbox secrets, sandbox outbox, sandbox runtime logs, and the previous generated package.

## Open Items

- `docs/report/作品报告_终稿.docx` has not been merged yet. The release checklist records this as `includes_final_report_docx: False`.
- The final Word report should be added by the full team before the official submission package is frozen.
