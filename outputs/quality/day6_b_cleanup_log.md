# DAY6 B 文档清理记录

## 清理范围

- `m3_attacks/README.md`
- `m3_attacks/ATTACK_MATRIX.md`
- `m3_attacks/SAMPLE_REVIEW.md`
- `docs/report_sections/03_attack_scenarios.md`
- `docs/report_sections/04_innovation_attack_side.md`
- `docs/ETHICS_AND_SCOPE.md`
- `docs/DATASET_CARD.md`
- `docs/case_cards/DEMO_001_RAG_INDIRECT.md`
- `docs/case_cards/DEMO_002_JSON_RPC.md`
- `docs/case_cards/DEMO_003_MULTILINGUAL_T2L.md`

## 主要处理

- 将乱码和阶段任务口吻改为正式作品报告口径。
- 将攻击描述统一限定为本地授权 sandbox mock 测试。
- 保留攻击样本含义、case_id、风险标签和 mock 目标动作。
- 补齐攻击矩阵、数据集说明、伦理边界和案例卡中的安全边界。
- 移除阶段命名的样本复核文件，改为通用 `SAMPLE_REVIEW.md`。

## 新增文件

- `docs/DATASET_CARD.md`
- `docs/report_sections/04_innovation_attack_side.md`
- `docs/SUBMISSION_EVIDENCE_INDEX.md`
- `docs/RUNBOOK.md`
- `docs/RELEASE_CHECKLIST.md`
- `docs/presentation/答辩问题准备_攻击侧.md`

## 样本审计结果

- total_cases: 69
- duplicate_case_id: 0
- missing_required_fields: 0
- audit_status: pass
- audit_hard_fail_count: 0

## 扫描结果

- `outputs/quality/day6_docs_ai_trace_scan.txt`: 空文件，未发现过程指令痕迹。
- `outputs/quality/day7_b_identity_leak_scan.txt`: 空文件，未发现身份泄露关键词。
