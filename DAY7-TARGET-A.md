# DAY7-TARGET-A：最终封版、独立验收与提交包计划

## Summary

- DAY7 只做最终同步、release 独立测试、扫描、zip、哈希、RUNBOOK、证据索引和 A 侧复核报告。
- 已从最新 `origin/team-a/m3-core-day6` 创建 `team-a/m3-core-day7`，并合并 `upstream/main` 的最终报告、PPT 和提交材料。
- 不修改 Agent 主流程、Guard 评分、攻击样本结构、Dashboard 大结构或指标公式。
- 最终目标是让 `release/Redteam_LLM_Security_v1.0.zip` 可解压、可运行、可复核。

## Key Changes

- 新增 `scripts/run_day7_smoke_test.ps1`，用于在 release 包根目录内运行 stub demo 与评估。
- 新增 `docs/RUNBOOK.md`、`docs/RELEASE_CHECKLIST.md`、`docs/SUBMISSION_EVIDENCE_INDEX.md`，补齐可复现说明、发布检查和赛题证据索引。
- 保留 `docs/DATASET_CARD.md` 与 `docs/SYSTEM_ARCHITECTURE.md`，并确保最终 release 包包含这两份正式项目文档。
- 生成 DAY7 质量记录：smoke test、AI trace scan、identity leak scan、final checklist、zip hash。

## Test Plan

- 代码检查：
  `python -m py_compile m3_core/run_matrix.py m3_core/run_batch.py m3_core/agent_runner.py m3_core/check_logs.py m3_eval/evaluate.py`
- 生成 release：
  `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/make_release_package.ps1`
- 独立测试：
  复制 `release/Redteam_LLM_Security_v1.0/` 到仓库外测试目录，运行 `scripts/run_day7_smoke_test.ps1`。
- 扫描与封包：
  运行 release trace scan、private identifier scan、zip 生成和 SHA256 生成。

## Assumptions

- 正式报告和 PPT 来自上游 DAY7 材料；A 只做合并、验证和封包。
- `DAY7-REPORT-A.md` 是过程复核报告，不进入 release 包。
- 只有所有最终材料、扫描和 smoke test 都通过后，才适合打 `v1.0-final` tag。
