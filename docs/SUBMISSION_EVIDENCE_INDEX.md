# 提交材料证据索引

本索引用于把赛题要求与项目文件一一对应，便于评审快速定位安全风险分析、攻击样本、行为监督、运行日志和演示材料。

## 1. 安全风险分析报告

对应文件：

- `docs/report/作品报告_终稿.docx`
- `docs/report/作品报告_终稿.pdf`
- `docs/report_sections/03_attack_scenarios.md`
- `docs/report_sections/04_innovation_attack_side.md`

说明：报告正文和攻击场景章节描述了大模型智能体提示注入攻击面、威胁模型、测试方案、结果分析和创新点。

## 2. 至少三类攻击场景

对应文件：

- `m3_attacks/ATTACK_MATRIX.md`
- `m3_attacks/cases/direct_jailbreak_cases.jsonl`
- `m3_attacks/cases/rag_indirect_cases.jsonl`
- `m3_attacks/cases/multilingual_t2l_cases.jsonl`
- `m3_attacks/cases/json_rpc_cases.jsonl`
- `m3_attacks/cases/tool_output_cases.jsonl`

说明：样本库覆盖直接越狱、RAG 间接提示注入、多语言/T2L、JSON/RPC 结构化注入和工具输出注入，超过三类攻击场景要求。

## 3. 越狱测试用例集

对应文件：

- `m3_attacks/cases/all_cases.jsonl`
- `m3_attacks/README.md`
- `docs/DATASET_CARD.md`
- `m3_attacks/SAMPLE_REVIEW.md`

说明：`all_cases.jsonl` 是自动合并后的完整样本库，`DATASET_CARD.md` 描述数据规模、字段、边界和限制。

## 4. 智能体攻击脚本与运行入口

对应文件：

- `m3_core/run_batch.py`
- `m3_core/run_matrix.py`
- `scripts/run_day5_demo.ps1`
- `scripts/run_day7_smoke_test.ps1`

说明：运行入口用于批量执行 AttackCase，记录模型响应、工具调用和 Guard 决策。

## 5. 行为监督原型系统

对应文件：

- `m3_guard/guard_engine.py`
- `m3_guard/detector.py`
- `m3_guard/policy_engine.py`
- `m3_guard/dataflow.py`
- `m3_guard/normalizer.py`

说明：Guard 模块负责识别指令性文本、结构化注入、工具调用诱导、敏感路径访问、外发风险和意图-动作不一致。

## 6. 模拟业务工具

对应文件：

- `m3_core/tool_sandbox.py`
- `sandbox/public/`

模拟工具：

- `read_file`
- `write_file`
- `send_email`
- `call_api`
- `run_code`

说明：工具均为本地 mock 实现，不访问真实网络，不发送真实邮件，不执行真实恶意代码。

## 7. 模型调用链监控

对应文件：

- `outputs/runs/day5_demo_matrix/`
- `outputs/runs/day5_qwen25_matrix/`
- `outputs/runs/day5_stub_matrix/`
- `m3_eval/dashboard.py`

说明：运行日志记录用户任务、模型输出、工具调用、Guard 决策、风险原因和最终状态，可用于复核调用链。

## 8. 告警或阻断记录

对应文件：

- `outputs/metrics/day5_demo_summary.csv`
- `outputs/metrics/day5_qwen25_summary.csv`
- `outputs/metrics/day5_stub_summary.csv`
- `outputs/metrics/day5_log_audit.json`
- `outputs/metrics/final_case_audit.json`

说明：指标文件记录 ASR、UTR、DSR、BSR、FPR、AvgRisk 和 WRS 等结果，审计文件记录样本库质量和运行日志质量。

## 9. 代表案例卡

对应文件：

- `docs/case_cards/DEMO_001_RAG_INDIRECT.md`
- `docs/case_cards/DEMO_002_JSON_RPC.md`
- `docs/case_cards/DEMO_003_MULTILINGUAL_T2L.md`

说明：三张案例卡分别对应 RAG 间接提示注入、JSON/RPC 结构化注入和多语言/T2L 任务切换，适合答辩讲解。

## 10. 安全边界声明

对应文件：

- `docs/ETHICS_AND_SCOPE.md`
- `docs/DATASET_CARD.md`

说明：项目明确限定为本地授权 sandbox mock 评测，不包含真实攻击目标、真实凭证、真实 API、真实邮箱或真实恶意代码。

## 11. 可复现说明

对应文件：

- `README.md`
- `docs/RUNBOOK.md`
- `scripts/check_env.ps1`
- `scripts/run_day7_smoke_test.ps1`

说明：运行说明和 smoke test 脚本用于复现最小演示链路。

## 12. 最终提交包

对应文件：

- `release/Redteam_LLM_Security_v1.0/`
- `release/Redteam_LLM_Security_v1.0.zip`
- `outputs/quality/day7_final_checklist.md`

说明：最终 release 包应排除 `.git`、虚拟环境、缓存、真实 secret、临时 outbox 和过程性任务文本。
