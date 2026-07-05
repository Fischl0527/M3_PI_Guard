有，**DAY7 很有必要**。
如果 DAY6 已经完成“清理 AIagent/Codex 痕迹 + 官方模板报告 + release 包初版”，那么 **DAY7 就是最终封版、答辩演练、提交包验收日**。

DAY7 的原则是：

```text
不新增功能。
不新增攻击样本。
不大改代码。
不临时换模型。
不临时换报告结构。
只做最终检查、演示演练、提交包封装和兜底方案。
```

官方模板里明确要求报告按模板结构撰写，说明文字需删除，填写说明页保留，并避免出现学校、院系、指导教师等身份信息。赛题方向本身要求你们交付安全风险分析、至少 3 类攻击场景、越狱测试用例集、智能体攻击脚本、行为监督原型系统、模拟业务工具、模型调用链监控与告警/阻断记录。所以 DAY7 的重点就是检查：**这些东西是否都能在提交包里找到，并且能被评委看懂。**

---

# DAY7 总目标

DAY7 结束时，你们应该得到一个真正可提交的最终版本：

```text
1. 最终 release 包：
   release/Redteam_LLM_Security_v1.0.zip

2. 最终作品报告：
   docs/report/作品报告_终稿.docx
   docs/report/作品报告_终稿.pdf   # 如果可导出

3. 最终演示材料：
   docs/presentation/答辩PPT.pptx
   docs/presentation/演示讲稿.md
   docs/presentation/答辩问题准备.md

4. 最终可复现说明：
   README.md
   docs/RUNBOOK.md
   docs/RELEASE_CHECKLIST.md

5. 最终证据索引：
   docs/SUBMISSION_EVIDENCE_INDEX.md

6. 最终质量检查记录：
   outputs/quality/day7_final_checklist.md
   outputs/quality/day7_identity_leak_scan.txt
   outputs/quality/day7_ai_trace_scan_release.txt
   outputs/quality/day7_smoke_test_result.md

7. 最终 tag：
   v1.0-final
```

DAY7 的一句话目标：

> **让评委可以从报告、PPT、Dashboard、日志、代码和演示中完整理解你们的红队攻击链与行为监督系统。**

---

# DAY7 时间安排总览

| 时间段         | 目标               | A：代码/打包/演示环境             | B：文档/案例/安全边界 | C：报告/PPT/答辩 |
| ----------- | ---------------- | ------------------------ | ------------ | ----------- |
| 09:00–09:30 | 冻结 DAY6，创建最终分支   | 打 tag、建分支                | 拉取最终版        | 拉取最终版       |
| 09:30–11:00 | release 包独立可运行测试 | clean clone / smoke test | 检查样本和案例索引    | 检查报告格式      |
| 11:00–12:30 | 提交包结构整理          | 生成 zip、校验脚本              | 生成证据索引       | 导出 docx/pdf |
| 13:30–15:00 | PPT 与演示脚本联调      | 跑 demo / Dashboard       | 补案例讲解        | 整合 PPT      |
| 15:00–17:00 | 模拟答辩第一轮          | 控制演示流程                   | 讲攻击样本        | 讲实验结果       |
| 17:00–18:30 | 修复问题与第二轮演练       | 修脚本/路径                   | 修案例材料        | 修 PPT/报告    |
| 19:30–21:00 | 最终扫描与封包          | release 扫描               | 匿名化扫描        | 格式检查        |
| 21:00–22:00 | 最终确认、打 tag、备份    | 生成最终 zip                 | 检查提交材料       | 确认提交版本      |

---

# DAY7 开始前：全员先做

## 1. 冻结 DAY6

由 A 或仓库管理员执行：

```bash
git checkout day6-clean-report
git pull
git tag day6-clean
git push origin day6-clean
```

创建最终分支：

```bash
git checkout -b day7-final-release
git push -u origin day7-final-release
```

---

## 2. 今日不允许修改核心逻辑

DAY7 只允许修改：

```text
README.md
docs/
scripts/
release/
outputs/quality/
少量 bug fix
```

不要再修改：

```text
攻击样本结构
Guard 评分逻辑
Agent 主流程
Dashboard 大结构
实验指标公式
```

除非发现严重 bug，否则不要动。

---

## 3. 建立最终目录

```bash
mkdir -p docs/presentation
mkdir -p docs/report
mkdir -p outputs/quality
mkdir -p release
```

Windows PowerShell：

```powershell
New-Item -ItemType Directory -Force docs/presentation
New-Item -ItemType Directory -Force docs/report
New-Item -ItemType Directory -Force outputs/quality
New-Item -ItemType Directory -Force release
```

---

# A 模块：DAY7 详细任务

## A 今日定位

A 是**最终提交包、可复现运行和演示环境负责人**。

A 今天要完成：

```text
1. release 包独立测试
2. smoke test
3. 一键运行脚本最终确认
4. 提交包 zip
5. release 包扫描
6. 备份与 tag
```

---

## A-1：独立 release 包测试

最重要的一步：不要只在开发目录里跑，要测试 release 包是否独立可用。

建议在项目外新建测试目录：

```bash
mkdir ../release_test
cd ../release_test
```

复制 release 包：

```bash
cp -r ../Redteam_LLM_Security/release/Redteam_LLM_Security_v1.0 .
cd Redteam_LLM_Security_v1.0
```

Windows 可手动复制或：

```powershell
New-Item -ItemType Directory -Force ..\release_test
Copy-Item -Recurse .\release\Redteam_LLM_Security_v1.0 ..\release_test\
cd ..\release_test\Redteam_LLM_Security_v1.0
```

检查目录：

```text
m3_core/
m3_attacks/
m3_guard/
m3_eval/
fixtures/
scripts/
docs/
outputs/metrics/
outputs/figures/
README.md
```

不应该出现：

```text
.git/
.venv/
__pycache__/
sandbox/secrets/
sandbox/outbox/
模型文件
private_notes/
AIagent 指令文档
```

---

## A-2：release 包 smoke test

在 release 测试目录运行：

```bash
python -m m3_core.run_matrix \
  --cases fixtures/demo_cases.jsonl \
  --backend stub \
  --defense-modes baseline,full_guard \
  --out-dir outputs/runs/day7_smoke_stub \
  --run-prefix day7_smoke \
  --max-steps 5
```

再评测：

```bash
python -m m3_eval.evaluate \
  --log-dir outputs/runs/day7_smoke_stub \
  --cases fixtures/demo_cases.jsonl \
  --out outputs/metrics/day7_smoke_summary.csv
```

如果本地模型环境可用，再测试：

```bash
python -m m3_core.run_matrix \
  --cases fixtures/demo_cases.jsonl \
  --backend ollama \
  --model m3-target-qwen25-7b \
  --defense-modes baseline,full_guard \
  --out-dir outputs/runs/day7_smoke_qwen \
  --run-prefix day7_smoke_qwen \
  --max-steps 5
```

smoke test 结果记录到：

```text
outputs/quality/day7_smoke_test_result.md
```

内容模板：

```markdown
# DAY7 Smoke Test Result

## 测试时间
YYYY-MM-DD HH:MM

## 测试目录
release/Redteam_LLM_Security_v1.0

## 测试命令
- stub demo run
- evaluate

## 结果
- demo cases 数量：
- baseline 日志：
- full_guard 日志：
- summary.csv：
- 是否成功：

## 发现问题
无 / 列出问题

## 结论
release 包可独立运行。
```

---

## A-3：检查一键脚本

确认这些脚本存在并能跑：

```text
scripts/check_env.ps1
scripts/run_day5_demo.ps1
scripts/run_day5_dashboard.ps1
scripts/run_day7_smoke_test.ps1
scripts/make_release_package.ps1
```

如果没有 `run_day7_smoke_test.ps1`，新建：

```powershell
Write-Host "==== DAY7 Smoke Test ===="

python -m m3_core.run_matrix `
  --cases fixtures/demo_cases.jsonl `
  --backend stub `
  --defense-modes baseline,full_guard `
  --out-dir outputs/runs/day7_smoke_stub `
  --run-prefix day7_smoke `
  --max-steps 5

python -m m3_eval.evaluate `
  --log-dir outputs/runs/day7_smoke_stub `
  --cases fixtures/demo_cases.jsonl `
  --out outputs/metrics/day7_smoke_summary.csv

Write-Host "Smoke test finished."
```

---

## A-4：最终 release 扫描

在项目根目录运行：

```bash
rg -n --hidden "AIagent|AIAgent|AI Agent|Codex|Copilot|ChatGPT|AI生成|由AI|由 AI|你是队员|请只修改|完成后请输出|给AIagent|给 AIagent" release/Redteam_LLM_Security_v1.0 > outputs/quality/day7_ai_trace_scan_release.txt
```

身份信息扫描：

```bash
rg -n "学校|学院|指导教师|指导老师|老师|学号|姓名|队员|院系|班级" release/Redteam_LLM_Security_v1.0 > outputs/quality/day7_identity_leak_scan.txt
```

注意：
`全国大学生信息安全竞赛` 里面的“大学生”可以保留。
参考文献作者姓名可以保留。
但不能出现你们真实学校、学院、老师、姓名、学号。

---

## A-5：生成最终 zip

进入 `release/`：

```bash
cd release
zip -r Redteam_LLM_Security_v1.0.zip Redteam_LLM_Security_v1.0
```

Windows PowerShell：

```powershell
Compress-Archive -Path .\release\Redteam_LLM_Security_v1.0 -DestinationPath .\release\Redteam_LLM_Security_v1.0.zip -Force
```

建议生成哈希：

```bash
sha256sum release/Redteam_LLM_Security_v1.0.zip > outputs/quality/day7_release_sha256.txt
```

Windows PowerShell：

```powershell
Get-FileHash .\release\Redteam_LLM_Security_v1.0.zip -Algorithm SHA256 | Out-File outputs/quality/day7_release_sha256.txt
```

---

## A 今日交付物

```text
release/Redteam_LLM_Security_v1.0/
release/Redteam_LLM_Security_v1.0.zip
outputs/quality/day7_smoke_test_result.md
outputs/quality/day7_ai_trace_scan_release.txt
outputs/quality/day7_identity_leak_scan.txt
outputs/quality/day7_release_sha256.txt
scripts/run_day7_smoke_test.ps1
```

---

## A 可以直接给本地开发助手的 DAY7 指令

```text
你是队员 A 的本地开发助手。今天是 DAY7，项目进入最终封版与提交包验收阶段。你的任务是验证 release 包可独立运行、检查敏感痕迹、生成最终 zip。

请只修改：
scripts/
release/
outputs/quality/
README.md 仅限修复运行说明

目标：
1. 在 release/Redteam_LLM_Security_v1.0/ 中检查最终提交包结构。
2. 确保 release 包不包含 .git、.venv、__pycache__、sandbox/secrets、sandbox/outbox、模型文件、private_notes、AIagent 指令文档。
3. 新建 scripts/run_day7_smoke_test.ps1。
4. 在 release 包内运行 stub demo smoke test。
5. 运行 evaluate 生成 day7_smoke_summary.csv。
6. 生成 outputs/quality/day7_smoke_test_result.md。
7. 扫描 release 包是否存在 AIagent、Codex、ChatGPT 生成痕迹。
8. 扫描 release 包是否存在学校、学院、指导教师、队员姓名、学号等身份泄露信息。
9. 生成 release/Redteam_LLM_Security_v1.0.zip。
10. 生成 SHA256 哈希。

运行命令：
python -m m3_core.run_matrix --cases fixtures/demo_cases.jsonl --backend stub --defense-modes baseline,full_guard --out-dir outputs/runs/day7_smoke_stub --run-prefix day7_smoke --max-steps 5

python -m m3_eval.evaluate --log-dir outputs/runs/day7_smoke_stub --cases fixtures/demo_cases.jsonl --out outputs/metrics/day7_smoke_summary.csv

rg -n --hidden "AIagent|AIAgent|AI Agent|Codex|Copilot|ChatGPT|AI生成|由AI|由 AI|你是队员|请只修改|完成后请输出|给AIagent|给 AIagent" release/Redteam_LLM_Security_v1.0 > outputs/quality/day7_ai_trace_scan_release.txt

rg -n "学校|学院|指导教师|指导老师|老师|学号|姓名|队员|院系|班级" release/Redteam_LLM_Security_v1.0 > outputs/quality/day7_identity_leak_scan.txt

完成后请输出：
1. release 包路径
2. zip 路径
3. smoke test 是否成功
4. AI 痕迹扫描结果
5. 身份信息扫描结果
6. SHA256 文件路径
7. 仍需人工确认的问题
```

---

# B 模块：DAY7 详细任务

## B 今日定位

B 是**提交材料合规性、证据索引和攻击案例最终审核负责人**。

B 今天要完成：

```text
1. 检查攻击样本是否合规
2. 检查案例卡是否能支撑答辩
3. 生成提交证据索引
4. 检查报告和 PPT 中攻击描述是否安全
5. 准备答辩中攻击侧问答
```

---

## B-1：最终样本审计确认

检查这些文件：

```text
m3_attacks/cases/all_cases.jsonl
fixtures/demo_cases.jsonl
fixtures/day5_representative_cases.jsonl
docs/DATASET_CARD.md
m3_attacks/ATTACK_MATRIX.md
docs/case_cards/
```

确认：

```text
1. 样本均为本地授权 mock 测试
2. 没有真实攻击目标
3. 没有真实邮箱
4. 没有真实 API 地址
5. 没有真实系统路径
6. 没有真实恶意代码
7. demo case 能讲清楚
```

---

## B-2：生成提交证据索引

创建：

```text
docs/SUBMISSION_EVIDENCE_INDEX.md
```

这个文件非常重要。它让评委可以快速定位你们满足赛题要求的材料。

模板：

```markdown
# 提交材料证据索引

## 1. 安全风险分析报告
对应文件：
- docs/report/作品报告_终稿.docx
- docs/report/作品报告_终稿.pdf

说明：
报告中第一章至第三章描述了大模型智能体提示注入攻击面、威胁模型、测试方案和结果分析。

## 2. 至少三类攻击场景
对应文件：
- m3_attacks/cases/direct_jailbreak_cases.jsonl
- m3_attacks/cases/rag_indirect_cases.jsonl
- m3_attacks/cases/multilingual_t2l_cases.jsonl
- m3_attacks/cases/json_rpc_cases.jsonl
- m3_attacks/cases/tool_output_cases.jsonl

说明：
样本集覆盖直接越狱、RAG 间接提示注入、多语言/T2L、JSON/RPC 结构化注入和工具输出注入。

## 3. 越狱测试用例集
对应文件：
- m3_attacks/cases/all_cases.jsonl
- docs/DATASET_CARD.md

## 4. 智能体攻击脚本
对应文件：
- m3_core/run_batch.py
- m3_core/run_matrix.py
- scripts/run_day5_demo.ps1
- scripts/run_day7_smoke_test.ps1

## 5. 行为监督原型系统
对应文件：
- m3_guard/guard_engine.py
- m3_guard/detector.py
- m3_guard/policy_engine.py
- m3_guard/dataflow.py
- m3_guard/normalizer.py

## 6. 模拟业务工具
对应文件：
- m3_core/tool_sandbox.py

包含工具：
- read_file
- write_file
- send_email
- call_api
- run_code

## 7. 模型调用链安全监控
对应文件：
- outputs/runs/day5_demo_matrix/
- outputs/runs/day5_qwen25_matrix/
- m3_eval/dashboard.py

## 8. 告警或阻断记录
对应文件：
- outputs/metrics/day5_demo_summary.csv
- outputs/metrics/day5_qwen25_summary.csv
- outputs/figures/
- Dashboard 单案例回放页面

## 9. 安全边界声明
对应文件：
- docs/ETHICS_AND_SCOPE.md

## 10. 一键运行说明
对应文件：
- README.md
- docs/RUNBOOK.md
- scripts/run_day7_smoke_test.ps1
```

---

## B-3：最终案例卡检查

确认 3 个案例卡能讲：

```text
DEMO-001 RAG 间接提示注入
DEMO-002 JSON/RPC 结构化注入
DEMO-003 多语言/T2L 注入
```

每个案例卡中要有：

```text
攻击入口
攻击载体
用户正常任务
注入内容摘要
不安全目标动作
baseline 观察结果
full_guard 阻断原因
证据文件路径
安全边界
```

不要出现：

```text
AIagent
Codex
ChatGPT 生成
真实攻击步骤
真实攻击目标
```

---

## B-4：准备答辩攻击侧 Q&A

创建：

```text
docs/presentation/答辩问题准备_攻击侧.md
```

建议问题与回答：

### Q1：你们是不是在做真实攻击？

答：

```text
不是。所有攻击均为本地授权红队模拟，攻击目标是 sandbox 中的 mock 工具。send_email 不会真实发邮件，call_api 不会访问公网，run_code 不执行模型生成代码，secret 文件只包含 canary 假数据。
```

### Q2：为什么本地小模型也有研究价值？

答：

```text
本作品关注的是智能体工具链信任边界，而不是生成真实危险内容。提示注入风险的关键在于模型是否会把不可信文档或工具输出误当成指令并触发工具行为。我们通过 mock 工具和调用链日志验证这种行为风险，具有可复现性。
```

### Q3：你们覆盖了哪些红队攻击类型？

答：

```text
覆盖直接越狱、RAG/文档间接提示注入、多语言/T2L 注入、JSON/RPC 结构化注入、工具输出注入，并加入 benign_clean 样本用于误报率评估。
```

### Q4：你们如何避免误伤正常任务？

答：

```text
系统设置 benign_clean 样本，并计算 FPR。Guard 采用 allow/ask/deny 三态策略，对高风险但不确定的外发工具调用采用 ask，而不是全部拒绝。
```

### Q5：攻击样本是否公开安全？

答：

```text
样本只包含本地 mock 行为目标，不包含真实恶意代码、真实 API、真实邮箱或真实漏洞利用步骤，适合用于受控安全评测。
```

---

## B-5：B 今日交付物

```text
docs/SUBMISSION_EVIDENCE_INDEX.md
docs/presentation/答辩问题准备_攻击侧.md
docs/case_cards/DEMO_001_RAG_INDIRECT.md
docs/case_cards/DEMO_002_JSON_RPC.md
docs/case_cards/DEMO_003_MULTILINGUAL_T2L.md
docs/DATASET_CARD.md
docs/ETHICS_AND_SCOPE.md
m3_attacks/ATTACK_MATRIX.md
```

---

## B 可以直接给本地开发助手的 DAY7 指令

```text
你是队员 B 的文档审核助手。今天是 DAY7，项目进入最终封版。你的任务是检查攻击样本与案例材料的合规性，生成提交证据索引，并准备攻击侧答辩问答。

请只修改：
docs/
m3_attacks/ATTACK_MATRIX.md
outputs/quality/ 仅可新增检查记录

目标：
1. 检查 m3_attacks/cases/all_cases.jsonl、fixtures/demo_cases.jsonl、fixtures/day5_representative_cases.jsonl，确认所有攻击均为本地 sandbox mock 测试。
2. 检查 docs/case_cards/ 中 3 个 demo 案例卡，确保内容正式、合规、可答辩。
3. 创建 docs/SUBMISSION_EVIDENCE_INDEX.md，将赛题要求与项目文件逐项对应。
4. 创建 docs/presentation/答辩问题准备_攻击侧.md。
5. 检查文档中不得出现：
   - AIagent
   - Codex
   - ChatGPT 生成
   - 真实攻击步骤
   - 真实 API
   - 真实邮箱
   - 真实敏感路径
   - 学校/学院/指导老师/队员姓名/学号
6. 保留正常项目术语：大模型、LLM、Agent、智能体、提示注入、越狱、AI 安全。

完成后请输出：
1. 证据索引路径
2. 攻击侧答辩问题路径
3. 三个 demo case_id
4. 是否发现不合规样本
5. 是否发现身份泄露信息
6. 是否仍需人工确认
```

---

# C 模块：DAY7 详细任务

## C 今日定位

C 是**最终报告、PPT、答辩演示和格式质检负责人**。

C 今天要完成：

```text
1. Word 报告最终检查
2. PDF 导出
3. PPT 最终版
4. 演示讲稿
5. 答辩问题准备
6. 报告与 PPT 匿名化扫描
```

---

## C-1：官方报告最终检查

检查：

```text
docs/report/作品报告_终稿.docx
docs/report/作品报告_终稿.pdf
```

官方模板要求：

```text
A4
正文宋体
小四号字
1.5 倍行距
说明文字删除
填写说明页保留
避免学校、院系、指导教师等身份信息
```

这些要求来自模板填写说明。

---

## C-2：报告内容检查

逐章检查：

```text
摘要：是否说明动机、功能、特性、创新、实用性
第一章：是否讲清背景、相关工作、特色、应用前景
第二章：是否讲清系统设计与实现
第三章：是否有测试环境、测试数据、指标、结果分析
第四章：是否有创新性说明
第五章：是否有总结与后续工作
参考文献：是否格式统一
```

不要留模板占位句：

```text
（请简要说明……）
（建议包括……）
（本部分内容主要说明……）
```

---

## C-3：PPT 最终版

创建或整理：

```text
docs/presentation/Redteam_LLM_Security_答辩PPT.pptx
```

如果还没做 PPT，建议 12 页：

```text
1. 封面
2. 项目背景与问题
3. 威胁模型
4. 系统总体架构
5. 红队攻击样本库
6. Agent 靶场与模拟工具
7. 行为监督 Guard 设计
8. 实验设置与指标
9. 实验结果：baseline vs full_guard
10. 代表性案例演示
11. 创新点
12. 总结与后续工作
```

封面不要写学校、学院、指导老师、队员姓名。

---

## C-4：演示讲稿

创建：

```text
docs/presentation/演示讲稿.md
```

建议 8 分钟结构：

```markdown
# 演示讲稿

## 0:00–1:00 背景
大模型智能体接入工具后，提示注入可能导致工具调用劫持。

## 1:00–2:00 系统架构
介绍攻击样本库、Agent 靶场、模拟工具、Guard、评测和 Dashboard。

## 2:00–3:00 红队样本
介绍五类攻击样本与 benign_clean。

## 3:00–4:00 防御机制
介绍上下文隔离、工具策略、数据流追踪和意图-动作一致性检测。

## 4:00–6:00 Demo
展示 RAG 间接提示注入案例：
baseline 下触发 mock 工具调用；
full_guard 下阻断并记录 risk_score/reasons。

## 6:00–7:00 实验结果
展示 ASR、UTR、DSR、BSR、FPR、WRS 对比。

## 7:00–8:00 创新与总结
总结从输出安全转向行为安全、可复现本地红队靶场、多层行为监督。
```

---

## C-5：结果截图清单

创建：

```text
docs/presentation/截图清单.md
```

至少要有这些截图：

```text
1. 系统目录结构截图
2. 攻击样本 all_cases.jsonl 局部截图
3. baseline 日志截图
4. full_guard 阻断日志截图
5. Dashboard 总览截图
6. Dashboard 单案例回放截图
7. 指标图表截图
8. 作品报告封面截图
```

截图文件放：

```text
docs/presentation/screenshots/
```

---

## C-6：答辩问题准备

创建：

```text
docs/presentation/答辩问题准备_综合.md
```

建议问题：

### Q1：你们的核心创新是什么？

答：

```text
核心创新是从模型输出安全转向智能体行为安全。我们不仅判断模型回答是否违规，还审计模型是否触发文件访问、邮件发送、API 调用、代码执行等工具行为，并通过上下文隔离、工具策略和数据流追踪进行阻断。
```

### Q2：为什么需要 mock 工具？

答：

```text
mock 工具保证红队测试不会影响真实世界，同时保留工具调用链和行为证据。它可以安全模拟文件读取、邮件外发、API 调用和代码执行风险。
```

### Q3：为什么要有 keyword_only / policy_only / full_guard？

答：

```text
这是为了做消融实验。keyword_only 体现传统关键词过滤能力，policy_only 体现工具策略能力，full_guard 体现多层防御组合效果。
```

### Q4：系统如何降低误报？

答：

```text
通过 benign_clean 样本计算 FPR，并采用 allow/ask/deny 三态决策。对不确定但高风险的操作使用 ask，而不是直接 deny。
```

### Q5：后续可扩展什么？

答：

```text
可扩展多模型横向对比、多模态图片隐藏提示注入、学习型检测器、真实开源 Agent 框架接入以及更细粒度的数据流标签。
```

---

## C-7：PPT 和报告扫描

扫描报告和 PPT 目录：

```bash
rg -n "AIagent|AIAgent|AI Agent|Codex|Copilot|ChatGPT|AI生成|由AI|你是队员|请只修改|完成后请输出|给AIagent|给 AIagent" docs/report docs/presentation > outputs/quality/day7_report_ppt_ai_trace_scan.txt
```

身份扫描：

```bash
rg -n "学校|学院|指导教师|指导老师|老师|学号|姓名|队员|院系|班级" docs/report docs/presentation > outputs/quality/day7_report_ppt_identity_scan.txt
```

---

## C 今日交付物

```text
docs/report/作品报告_终稿.docx
docs/report/作品报告_终稿.pdf
docs/presentation/Redteam_LLM_Security_答辩PPT.pptx
docs/presentation/演示讲稿.md
docs/presentation/答辩问题准备_综合.md
docs/presentation/截图清单.md
docs/presentation/screenshots/
outputs/quality/day7_report_ppt_ai_trace_scan.txt
outputs/quality/day7_report_ppt_identity_scan.txt
```

---

## C 可以直接给本地开发助手的 DAY7 指令

```text
你是队员 C 的报告与答辩材料整理助手。今天是 DAY7，项目进入最终提交前检查。你的任务是完成报告、PPT、演示讲稿和答辩问题准备，并检查匿名化和 AI 痕迹。

请只修改：
docs/report/
docs/presentation/
outputs/quality/

目标：
1. 检查 docs/report/作品报告_终稿.docx 是否符合官方模板：
   - A4
   - 正文宋体小四
   - 1.5 倍行距
   - 填写说明页保留
   - 模板说明文字删除
   - 无学校、学院、指导教师、队员姓名、学号
2. 如可行，导出 docs/report/作品报告_终稿.pdf。
3. 创建或完善 docs/presentation/Redteam_LLM_Security_答辩PPT.pptx。
4. PPT 建议 12 页：
   封面、背景、威胁模型、系统架构、攻击样本、Agent 靶场、Guard、实验指标、实验结果、案例演示、创新点、总结。
5. 创建 docs/presentation/演示讲稿.md。
6. 创建 docs/presentation/答辩问题准备_综合.md。
7. 创建 docs/presentation/截图清单.md。
8. 扫描 docs/report 和 docs/presentation，确认无 AIagent/Codex/ChatGPT 生成痕迹。
9. 扫描 docs/report 和 docs/presentation，确认无身份泄露信息。

完成后请输出：
1. 最终 Word 报告路径
2. 最终 PDF 路径
3. PPT 路径
4. 演示讲稿路径
5. 答辩问题准备路径
6. AI 痕迹扫描结果
7. 身份信息扫描结果
8. 仍需人工检查的项目
```

---

# DAY7 中午第一次集成

时间：**12:30 前**

目标：

```text
release 包可独立运行
报告/PPT 基本完整
证据索引完成
```

检查点：

```text
[ ] release smoke test 成功
[ ] day7_smoke_summary.csv 生成
[ ] docs/SUBMISSION_EVIDENCE_INDEX.md 完成
[ ] 作品报告_终稿.docx 可打开
[ ] PPT 初版可打开
```

---

# DAY7 下午第二次集成

时间：**17:30 前**

目标：

```text
完成第一轮模拟答辩并修复问题
```

模拟答辩流程：

```text
1. C 讲背景和系统架构
2. B 讲红队攻击样本和案例
3. A 现场跑 demo 或展示 Dashboard
4. C 讲实验结果和创新点
5. 全员回答问题
```

记录问题到：

```text
outputs/quality/day7_rehearsal_issues.md
```

模板：

```markdown
# DAY7 模拟答辩问题记录

## 第一轮问题
1. 问题：
   修复：
   负责人：

2. 问题：
   修复：
   负责人：

## 第二轮问题
...
```

---

# DAY7 晚上最终封版

## 1. 最终扫描

```bash
rg -n --hidden "AIagent|AIAgent|AI Agent|Codex|Copilot|ChatGPT|AI生成|由AI|由 AI|你是队员|请只修改|完成后请输出|给AIagent|给 AIagent" release/Redteam_LLM_Security_v1.0 > outputs/quality/day7_final_ai_trace_scan_release.txt
```

```bash
rg -n "学校|学院|指导教师|指导老师|老师|学号|姓名|队员|院系|班级" release/Redteam_LLM_Security_v1.0 > outputs/quality/day7_final_identity_scan_release.txt
```

---

## 2. 最终人工检查

```text
[ ] Word 报告能打开
[ ] PDF 能打开
[ ] PPT 能打开
[ ] release zip 能解压
[ ] README 有运行说明
[ ] RUNBOOK 有演示命令
[ ] demo smoke test 能跑
[ ] release 包没有 sandbox/secrets
[ ] release 包没有模型文件
[ ] release 包没有 .git
[ ] release 包没有 AIagent/Codex 指令
[ ] 报告无学校/老师/队员身份信息
[ ] 证据索引能对应赛题要求
```

---

## 3. 打最终 tag

```bash
git checkout day7-final-release
git pull
git tag v1.0-final
git push origin v1.0-final
```

---

# DAY7 最终验收表

| 模块 | 必须完成      | 验收标准                               |
| -- | --------- | ---------------------------------- |
| A  | release 包 | `Redteam_LLM_Security_v1.0.zip` 存在 |
| A  | 独立运行测试    | release 中 stub demo 能跑             |
| A  | 最终扫描      | 无 AIagent/Codex 痕迹，无身份泄露           |
| B  | 证据索引      | 赛题要求与文件一一对应                        |
| B  | 案例卡       | 3 个 demo 案例能支撑答辩                   |
| B  | 攻击侧问答     | 能解释安全边界和红队价值                       |
| C  | 官方报告      | docx/pdf 完成，格式符合模板                 |
| C  | PPT       | 12 页左右，结构完整                        |
| C  | 演示讲稿      | 8 分钟内可讲完                           |
| 全队 | 模拟答辩      | 至少完成 2 轮                           |
| 全队 | 最终封版      | 打 tag `v1.0-final`                 |

---

# DAY7 最终提交包建议结构

```text
Redteam_LLM_Security_v1.0/
  README.md
  requirements-core.txt
  requirements-dashboard.txt

  m3_core/
  m3_attacks/
  m3_guard/
  m3_eval/
  fixtures/
  scripts/

  docs/
    report/
      作品报告_终稿.docx
      作品报告_终稿.pdf
    presentation/
      Redteam_LLM_Security_答辩PPT.pptx
      演示讲稿.md
      答辩问题准备_综合.md
    DATASET_CARD.md
    ETHICS_AND_SCOPE.md
    SUBMISSION_EVIDENCE_INDEX.md
    RUNBOOK.md
    case_cards/

  outputs/
    metrics/
      day5_qwen25_summary.csv
      day5_stub_summary.csv
      day5_demo_summary.csv
    figures/
      day5_asr_by_defense_mode.png
      day5_utr_by_defense_mode.png
      day5_bsr_by_defense_mode.png
      day5_fpr_by_defense_mode.png
    runs/
      day5_demo_matrix/
```

不要包含：

```text
.git/
.venv/
__pycache__/
sandbox/secrets/
sandbox/outbox/
ollama 模型文件
private_notes/
开发过程 AIagent 指令文件
```

---

# DAY7 风险与兜底方案

## 风险 1：现场模型跑不起来

兜底：

```text
用 stub demo 演示完整攻击链
展示 Qwen2.5 预先生成的日志
展示 Dashboard 回放
```

答辩解释：

```text
stub 用于可复现全链路验证，Qwen2.5 代表样本用于验证真实本地模型效果。
```

---

## 风险 2：Dashboard 现场卡顿

兜底：

```text
提前准备截图
打开 CSV 和日志文件展示
用 case card 讲解攻击链
```

---

## 风险 3：评委质疑攻击危险性

回答：

```text
本作品是授权红队模拟。所有工具均为 mock，所有敏感数据均为 canary 假数据，不访问真实网络、不发送真实邮件、不执行真实代码。目标是评估智能体信任边界和行为监督能力。
```

---

## 风险 4：评委质疑本地模型能力

回答：

```text
作品关注的是工具链行为风险，不依赖真实危险内容生成能力。即使模型规模较小，只要它会把不可信内容误当成指令，就能复现提示注入导致的工具调用风险。我们通过调用链日志和 Guard 阻断记录提供可复现实验证据。
```

---

# DAY7 最后 30 分钟终极检查

全员一起逐项确认：

```text
[ ] release zip 已生成
[ ] release zip 已解压测试
[ ] smoke test 通过
[ ] Word 报告可打开
[ ] PDF 可打开
[ ] PPT 可打开
[ ] README 可读
[ ] RUNBOOK 可执行
[ ] ETHICS_AND_SCOPE 明确安全边界
[ ] SUBMISSION_EVIDENCE_INDEX 完成
[ ] 报告无模板说明文字
[ ] 报告无身份信息
[ ] release 无 AIagent/Codex 痕迹
[ ] release 无 sandbox/secrets
[ ] release 无模型文件
[ ] 演示脚本可运行
[ ] 两轮模拟答辩完成
[ ] 已打 tag v1.0-final
```

---

# DAY7 一句话执行口号

```text
A：保证提交包能独立运行。
B：保证材料能证明赛题要求。
C：保证报告和答辩能讲清楚。
```

DAY7 做完后，你们就不再是“项目开发中”，而是进入**正式提交状态**。这一天的价值不是新增功能，而是最大限度降低提交失败、答辩卡壳、报告不合规、身份泄露和材料缺失的风险。
