# DAY6-TARGET-A：提交前清洗与最终 Release 方案

## Summary

- 从 `team-a/m3-core-day5` 创建 `team-a/m3-core-day6`，完成提交前清洗、最小验证和最终发布包质检。
- DAY6 不新增核心实验能力，重点是把仓库从开发态整理为正式提交态。
- 保留必要技术内容：LLM Agent、OpenAI-compatible 本地接口、Prompt Injection 样本、模型字段、实验日志字段。
- 最终交付 `release/Redteam_LLM_Security_v1.0/`、DAY6 质量记录、stub demo 验证结果和发布包扫描结果。

## Key Changes

- 扫描仓库中的开发过程指令痕迹，记录到 `outputs/quality/day6_ai_trace_scan_before.txt`。
- 清理或排除根目录历史讨论文档、DAY 任务文件、个人过程报告和旧发布包。
- 更新 `scripts/make_release_package.ps1`，默认生成 `release/Redteam_LLM_Security_v1.0/`。
- 新建 `docs/report/` 作为正式作品报告入口；若终稿尚未合入，则在清理日志和 checklist 中标注待合并。
- 运行 DAY6 stub demo matrix，并用 `m3_eval.evaluate --log-dir` 生成汇总 CSV。

## Test Plan

- 代码检查：
  `python -m py_compile m3_core/run_matrix.py m3_core/run_batch.py m3_core/agent_runner.py m3_core/check_logs.py m3_eval/evaluate.py`
- 最小闭环：
  `python -m m3_core.run_matrix --cases fixtures/demo_cases.jsonl --backend stub --defense-modes baseline,full_guard --out-dir outputs/runs/day6_demo_stub_matrix --run-prefix day6_demo_stub --run-group day6 --max-steps 5`
- 指标汇总：
  `python -m m3_eval.evaluate --log-dir outputs/runs/day6_demo_stub_matrix --cases fixtures/demo_cases.jsonl --out outputs/metrics/day6_demo_stub_summary.csv`
- 发布包检查：
  `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/make_release_package.ps1`

## Assumptions

- 未跟踪的 `DAY*-TASK.md` 和个人过程报告只作为本地任务输入，不进入提交和发布包。
- 若正式 Word 报告尚未由全队合入，A 侧不伪造终稿，只保留入口和缺失项记录。
- DAY6 最低验收以 stub demo 闭环和 release 质检为准；本地 Qwen demo 可选。
