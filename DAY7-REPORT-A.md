# DAY7-REPORT-A：最终封版与提交包验收报告

## 1. 基本状态

- 当前分支：`team-a/m3-core-day7`
- 基底分支：`origin/team-a/m3-core-day6`
- 已合并上游：`upstream/main`
- 上游 DAY7 材料来源：
  - `4c5cfa7 Merge pull request #8 from Alysia163/codex/day7-final-submission-materials`
  - `52e76cf Fix report image embedding`
  - `4b9e2a6 Finalize submission materials`
- A 侧本次新增：RUNBOOK、release checklist、证据索引、DAY7 smoke 脚本、最终 zip/hash/扫描记录。

## 2. 远端同步结果

DAY7 开始时发现远端已有新内容：

- `origin/team-a/m3-core-day6` 已更新到 `4d570f3`
- `upstream/main` 已更新到 `4c5cfa7`
- `upstream/codex/day7-final-submission-materials` 已存在并已合入 `upstream/main`

处理方式：

- 从最新 `origin/team-a/m3-core-day6` 创建 `team-a/m3-core-day7`
- 合并 `upstream/main`
- 保留本地 DAY6 补充文档：`docs/DATASET_CARD.md`、`docs/SYSTEM_ARCHITECTURE.md`
- 不修改 Agent 主流程、Guard 评分、攻击样本结构和指标公式

## 3. DAY7 A 侧完成项

| 项目 | 状态 | 说明 |
|---|---:|---|
| DAY7 目标文档 | 完成 | `DAY7-TARGET-A.md` |
| 最终报告材料合入 | 完成 | `docs/report/作品报告_终稿.docx` 已存在 |
| PPT 材料合入 | 完成 | `docs/presentation/Redteam_LLM_Security_答辩PPT.pptx` 已存在 |
| 可复现说明 | 完成 | `docs/RUNBOOK.md` |
| 发布检查说明 | 完成 | `docs/RELEASE_CHECKLIST.md` |
| 提交证据索引 | 完成 | `docs/SUBMISSION_EVIDENCE_INDEX.md` |
| smoke 脚本 | 完成 | `scripts/run_day7_smoke_test.ps1` |
| release 包 | 完成 | `release/Redteam_LLM_Security_v1.0/` |
| release zip | 完成 | `release/Redteam_LLM_Security_v1.0.zip` |
| SHA256 | 完成 | `outputs/quality/day7_release_sha256.txt` |
| AI trace scan | 通过 | `outputs/quality/day7_ai_trace_scan_release.txt` 长度为 0 |
| identity scan | 通过 | `outputs/quality/day7_identity_leak_scan.txt` 长度为 0 |
| 独立 smoke test | 通过 | 在仓库外测试目录运行成功 |

## 4. 独立 Smoke Test

测试目录：

```text
E:\M3_PI_Guard_release_test_day7\Redteam_LLM_Security_v1.0
```

测试命令：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_day7_smoke_test.ps1
```

结果：

- demo cases：3
- baseline 日志行数：8
- full_guard 日志行数：3
- summary CSV：已生成
- success：True

记录文件：

```text
outputs/quality/day7_smoke_test_result.md
```

## 5. 扫描与封包

AI trace scan：

```text
outputs/quality/day7_ai_trace_scan_release.txt
```

结果：文件长度 0。

Identity scan：

```text
outputs/quality/day7_identity_leak_scan.txt
```

结果：文件长度 0。

最终 zip：

```text
release/Redteam_LLM_Security_v1.0.zip
```

zip 大小：

```text
479438 bytes
```

SHA256：

```text
CCD902446DBCA1E4AB83C59E14BF26E0F6DE6E1F0CD03D70729D49BD9E58B848
```

zip 已在独立目录完成解压检查。

## 6. 最终包内容

最终 release 包包含：

- `README.md`
- `requirements-core.txt`
- `requirements-dashboard.txt`
- `m3_core/`
- `m3_attacks/`
- `m3_guard/`
- `m3_eval/`
- `fixtures/`
- `scripts/`
- `docs/`
- `outputs/metrics/`
- `outputs/runs/day5_demo_matrix/`
- `outputs/runs/day5_qwen25_matrix/`
- `outputs/runs/day6_demo_stub_matrix/`
- `sandbox/public/`

最终 release 包不包含：

- `.git/`
- `.venv/`
- `__pycache__/`
- model artifacts
- sandbox secrets
- sandbox mailbox
- nested old release package
- day-by-day local process prompt files

## 7. DAY1-DAY7 总体复核

- DAY1：Schema、样本、指标读取器已进入历史提交并在后续版本保留。
- DAY2：本地 Agent 最小闭环、stub/ollama、baseline/guarded、RunLog 已完成。
- DAY3：批量运行、demo cases、CSV 与初步指标已完成。
- DAY4：四模式实验矩阵、代表样本、case cards 和展示入口已完成。
- DAY5：日志审计、最终实验、Dashboard/metrics 和 v0.5 release 已完成。
- DAY6：提交前清洗、v1.0 release 初版、发布包扫描已完成。
- DAY7：最终报告/PPT 合入、独立运行测试、扫描、zip 和 hash 已完成。

## 8. 结论

A 侧 DAY7 任务已完成。最终 release 包可以独立运行 stub demo，扫描无命中，zip 可解压，SHA256 已生成。当前状态已经满足 A 侧“最终提交包、可复现运行和演示环境负责人”的验收要求。
