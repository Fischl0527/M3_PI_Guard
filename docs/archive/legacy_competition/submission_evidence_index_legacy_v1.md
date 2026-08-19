# Submission Evidence Index

本索引用于把赛题要求与项目文件一一对应，便于快速定位安全风险分析、攻击样本、行为监督、正式实验证据和演示材料。

## 0. 正式证据总入口

当前最终 HTML 技术报告、Markdown 分析和 Dashboard 的受控数据源为（PPT、DOCX、ZIP 不在本轮范围）：

- `experiments/registry.json` 映射的 E0-E17 primary bundles：逐实验 manifest、指标、统计检验、分析和图表；E17 映射到 `outputs/experiments/E17_human_stratified_360_v1/review/`；
- `outputs/experiments/program_manifest_final_v3.json`：Stub、smoke、validation、ablation、main、derived、stability 的统一运行状态与模型身份记录；
- `outputs/experiments/program_final_v3/`：只由 v3 manifest 索引的正式运行根；
- `outputs/experiments/blind_freeze_v3.json`：盲测前代码、数据和阈值冻结；
- `outputs/experiments/E11_posthoc_amendment_v1/`：发现原始 E11 scope 偏差后追加的独立 post-hoc 正式补充；当前只准入 `visualization_revision=2` 的全新运行与布局 QA，`pre_registered=false`，不得替换或合并原始 E11 分母；
- `outputs/experiments/final_analysis/`：E0-E17 完成后生成的验收矩阵、综合分析和最终图表；
- `experiments/registry.json`：E0-E17 完成状态和证据路径注册表。

证据层级必须区分：E0 是历史口径诊断；E1-E12、E15 是正式真实模型结果；E13 是验证集校准；E14、E16 是独立正式子矩阵；E17 是 360 行双真人分层抽样审计。E17 的 300 representative 行用于加权总体估计，60 targeted 行只作诊断，不能声称 3,299 行全量人工复核。E11 post-hoc amendment 是哈希绑定但未预注册的独立补充，只能分面披露；revision 1 不得进入证据链。Stub、smoke 和早期 FPR=0 结果均不得表述为正式效果结论。

## 1. 安全风险分析

对应文件：

- `docs/report/作品报告_终稿.docx`
- `docs/report_sections/03_attack_scenarios.md`
- `docs/report_sections/04_innovation_attack_side.md`
- `docs/ETHICS_AND_SCOPE.md`
- `docs/SYSTEM_ARCHITECTURE.md`

说明：报告正文和攻击场景章节描述大模型智能体提示注入攻击面、威胁模型、测试方案、结果分析和创新点。

## 2. 至少三类攻击场景

对应文件：

- `m3_attacks/ATTACK_MATRIX.md`
- `m3_attacks/cases/direct_jailbreak_cases.jsonl`
- `m3_attacks/cases/rag_indirect_cases.jsonl`
- `m3_attacks/cases/multilingual_t2l_cases.jsonl`
- `m3_attacks/cases/json_rpc_cases.jsonl`
- `m3_attacks/cases/tool_output_cases.jsonl`

说明：样本库覆盖直接越狱、RAG 间接提示注入、多语言/T2L、JSON/RPC 结构化注入和工具输出注入，超过三类攻击场景要求。

## 3. 测试用例集

对应文件：

- `m3_attacks/cases/all_cases.jsonl`
- `m3_attacks/README.md`
- `m3_attacks/SAMPLE_REVIEW.md`
- `docs/DATASET_CARD.md`
- `fixtures/demo_cases.jsonl`
- `fixtures/day5_representative_cases.jsonl`

说明：`all_cases.jsonl` 是自动合并后的完整样本库，`DATASET_CARD.md` 描述数据规模、字段、边界和限制。

## 4. Agent 攻击脚本与运行入口

对应文件：

- `m3_core/agent_runner.py`
- `m3_core/run_batch.py`
- `m3_core/run_matrix.py`
- `m3_core/llm_client.py`
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

## 7. 运行日志与监控

对应文件：

- `outputs/experiments/program_manifest_final_v3.json`
- `outputs/experiments/program_final_v3/`
- `outputs/experiments/E0/` 至 `outputs/experiments/E17/`
- `outputs/experiments/E11_posthoc_amendment_v1/`
- `outputs/experiments/final_analysis/`
- `m3_eval/dashboard.py`（盲测冻结时的逐字节来源快照，仅用于 provenance 复验）
- `m3_eval/evidence_dashboard.py`（后冻结、非因果的最终展示层）
- `scripts/dashboard_app.py`
- `scripts/run_final_dashboard.ps1`

说明：最终 Dashboard 通过固定白名单加载正式 bundle，支持按模型、防御、攻击族、语言和批次筛选，并回放经安全投影后的攻击链。展示层增强被隔离到 `m3_eval/evidence_dashboard.py`，不会改写 `blind_freeze_v3.json` 记录的冻结源码；Day5/Day6 输出仅为历史原型，不进入正式视图。

## 8. 指标、告警与阻断证据

对应文件：

- `outputs/experiments/E1/metrics.csv`
- `outputs/experiments/E4/ablation_contributions.csv`
- `outputs/experiments/E6/by_family_ci.csv`
- `outputs/experiments/E12/utility_metrics.csv`
- `outputs/experiments/E13/frozen_thresholds.json`
- `outputs/experiments/E14/performance.csv`
- `outputs/experiments/E16/adaptive_rounds.csv`
- `outputs/experiments/E17_human_stratified_360_v1/review/failure_taxonomy.csv`
- `outputs/experiments/E17_human_stratified_360_v1/review/weighted_population_estimates.csv`
- `outputs/experiments/final_analysis/`

说明：各 bundle 同时保留原始计数、分母、比例、Wilson 95% 置信区间、配对检验或 bootstrap 结果；最终综合分析统一呈现安全性、可用性、稳定性和性能边界。

## 9. 代表案例卡

对应文件：

- `docs/case_cards/DEMO_001_RAG_INDIRECT.md`
- `docs/case_cards/DEMO_002_JSON_RPC.md`
- `docs/case_cards/DEMO_003_MULTILINGUAL_T2L.md`

说明：三张案例卡分别对应 RAG 间接提示注入、JSON/RPC 结构化注入和多语言/T2L 任务切换，适合演示讲解。

## 10. 可复现说明

对应文件：

- `README.md`
- `docs/RUNBOOK.md`
- `scripts/check_env.ps1`
- `scripts/run_day7_smoke_test.ps1`
- `scripts/build_final_analysis.py`（冻结的基础构建器）
- `scripts/build_final_analysis_sampled_e17.py`（当前 sampled E17 正式适配入口）
- `scripts/validate_final_statistics.py`
- `scripts/build_final_html_report_artifact.py`
- `scripts/register_e11_amendment_evidence.py`
- `scripts/run_final_dashboard.ps1`
- `agent/result_integrity_audit.py`
- `requirements-core.txt`
- `requirements-dashboard.txt`

说明：smoke test 用于复现最小代码链路；当前 sampled E17 适配入口在完成态 registry 上重建 13 张正式综合图，并把自身哈希加入输入账本。第 13 张图将原始 E11 与 post-hoc 请求模式补充严格分面，不做 pooling。独立统计复算和 Dashboard 固定白名单必须随后通过。结果完整性审计仍需显式传 v3 manifest/freeze。

## 11. 演示材料

对应文件：

- `docs/presentation/Redteam_LLM_Security_答辩PPT.pptx`
- `docs/presentation/演示讲稿.md`
- `docs/presentation/答辩问题准备_综合.md`
- `docs/presentation/答辩问题准备_攻击侧.md`
- `docs/presentation/截图清单.md`

## 12. 最终提交包

对应文件：

- `release/Redteam_LLM_Security_v1.0/`
- `release/Redteam_LLM_Security_v1.0.zip`
- `outputs/quality/day7_final_checklist.md`
- `outputs/quality/day7_release_sha256.txt`

说明：最终 release 包排除 `.git`、虚拟环境、缓存、模型文件、sandbox secret、runtime outbox 和过程性任务文本。

## 13. 历史和被替代证据边界

以下内容可以用于说明工程演进，但不能与正式结果合并：

- `outputs/experiments/program_final/` 与 `blind_freeze.json`：首次正式盲测已作废，分别由根目录和 sibling invalidation marker 标识；
- `outputs/experiments/program_final_v2/` 及其 repro 根：独立复核后作废，均有 `INVALIDATED.json`；
- `outputs/experiments/program_v3/`：更早的 sandbox 污染批次，目录内 `INVALIDATED.json` 为作废边界；
- `outputs/experiments/E14_initial_cold_start_diagnostic/`：只用于解释首次 full Guard 冷启动高尾延迟，`SUPERSEDED.json` 表明已被替代；
- 旧 `program_manifest_final*.json`（v3 除外）、`program_v2/`、`program/`、各 repro 根和 `smoke_probe*/`：开发和协议修复证据；
- `outputs/runs/day*/`、`outputs/metrics/day*/`：早期原型与演示结果。

最终 Dashboard 启动脚本不接受额外 bundle/log/metric 参数，并验证 manifest 内所有 job 都位于 `program_final_v3/`、所有正式阶段都绑定 `blind_freeze_v3.json`，因此上述路径无法通过正式入口混入。
