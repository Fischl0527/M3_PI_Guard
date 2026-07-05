下面给你们一个**更详细的 DAY5 作战清单**。DAY5 的定位和前几天不一样：DAY2 是跑通闭环，DAY3 是扩展样本和增强 Guard，DAY4 是做消融、Dashboard、报告初稿。**DAY5 是“作品化收口日”**，目标是把系统从“能跑”变成“能提交、能答辩、能稳定复现、能讲清楚创新点”。

你们这个赛题要求从红队视角研究大模型和智能化应用攻击面，构造对抗输入，设计可落地防御策略，并交付至少 3 类攻击场景、越狱测试用例集、智能体攻击脚本、行为监督原型系统、模拟业务工具、模型调用链安全监控、实时告警或阻断记录。 综述也说明提示注入已经覆盖直接覆盖、多轮操纵、JSON/XML 结构化间接注入、自动红队、多模态和工具集成 Agent 攻击等方向，所以 DAY5 的重点是把这些能力整理成**证据链**，而不是继续堆新功能。

---

# DAY5 总目标

DAY5 结束时，你们应该得到一个可以给老师、评委或队友完整演示的版本：

```text
1. 最终样本库冻结：all_cases.jsonl 通过审计，无 schema 错误，无真实攻击内容
2. 最终实验结果：stub 全量四模式 + Qwen2.5 代表样本 baseline/full_guard
3. 最终指标：ASR、UTR、DSR、BSR、FPR、AvgRisk、WRS 都有 CSV/JSON/图表
4. Dashboard 可演示：能展示总览、消融、阻断记录、单案例回放
5. 3 个稳定 Demo：RAG 间接注入、JSON/RPC 注入、多语言/T2L 注入
6. 报告 v0.3：有背景、威胁模型、攻击场景、防御机制、实验结果、案例分析
7. PPT 或答辩材料初版：可以按 6–8 分钟讲完整个作品
8. 一键运行脚本：评委现场或录屏时能稳定运行 demo
9. 提交包：代码、样本、报告、截图、结果、说明文档全部整理好
```

DAY5 的一句话目标是：

> **把“红队攻击样本 — 本地 Agent 靶场 — 工具调用 — Guard 阻断 — 指标评测 — Dashboard 回放 — 报告论证”完整串起来。**

---

# DAY5 工作原则

今天不要再大改架构。只允许做三类事情：

```text
1. 修 bug
2. 补证据
3. 打磨展示
```

今天不建议再做：

```text
新增大型攻击类型
接 OpenClaw 真服务
接真实邮箱或真实 API
尝试大规模多模型对比
临时引入复杂依赖
重写 Agent 框架
复杂多模态功能
```

所有攻击仍然只在本地 sandbox/mock 环境中进行：

```text
send_email 只写 sandbox/outbox/outbox.jsonl
call_api 只调用 /mock/*
run_code 不真实执行
read_file/write_file 只能访问 sandbox/
secret 只使用 M3_CANARY 假数据
```

---

# DAY5 时间安排总览

| 时间段         | 目标                | A：靶场/集成         | B：样本/案例/材料   | C：评测/Dashboard/报告     |
| ----------- | ----------------- | --------------- | ------------ | --------------------- |
| 09:00–09:30 | 冻结 DAY4，建 DAY5 分支 | 打 tag、建分支       | 拉取最新代码       | 拉取最新代码                |
| 09:30–11:00 | 最终运行前体检           | 检查脚本、模型、sandbox | 审计样本库        | 检查 evaluate/dashboard |
| 11:00–12:30 | 第一轮最终实验           | 跑 stub 全量四模式    | 修样本问题        | 生成 stub 指标            |
| 13:30–15:30 | 第二轮真实模型实验         | 跑 Qwen2.5 代表样本  | 确认 demo case | 生成 Qwen 指标和图          |
| 15:30–17:30 | Dashboard 与案例回放   | 配合截图            | 写案例卡最终版      | 修 Dashboard、导出截图      |
| 17:30–19:00 | 报告/PPT 充实         | 写环境与系统实现        | 写攻击章节        | 写防御、指标、实验结果           |
| 19:30–21:00 | 模拟答辩              | 现场跑 demo        | 讲攻击案例        | 讲指标与防御                |
| 21:00–22:00 | 打包与提交检查           | 生成提交包           | 检查文档         | 检查图表和报告               |

---

# DAY5 开始前：全员先做

## 1. 冻结 DAY4 版本

由 A 或仓库管理员执行：

```bash
git checkout day4-production
git pull
git tag day4-done
git push origin day4-done
```

然后创建 DAY5 分支：

```bash
git checkout -b day5-release
git push -u origin day5-release
```

每个人从 `day5-release` 开自己的分支：

```bash
git checkout -b day5-A-final-runs
git checkout -b day5-B-case-materials
git checkout -b day5-C-report-dashboard
```

如果你们不熟分支，至少遵守：

```text
A 只改 m3_core/ scripts/ fixtures/ outputs/runs/
B 只改 m3_attacks/ docs/case_cards/ docs/report_sections/
C 只改 m3_guard/ m3_eval/ outputs/metrics/ outputs/figures/ docs/report_v*.md
```

---

## 2. 今日版本号统一

建议设定：

```text
project_version = v0.5-day5
guard_version = guard-v0.5
dataset_version = cases-v0.5
experiment_version = exp-day5-final
```

所有日志、报告、Dashboard 都尽量出现这些版本号，方便答辩时说明“这是最终实验版本”。

---

## 3. 今日最终目录目标

DAY5 结束时希望目录长这样：

```text
M3_PI_Guard/
  README.md
  requirements-core.txt
  requirements-dashboard.txt
  .gitignore

  m3_core/
  m3_attacks/
  m3_guard/
  m3_eval/

  fixtures/
    demo_cases.jsonl
    day5_representative_cases.jsonl

  scripts/
    run_day5_demo.ps1
    run_day5_stub_matrix.ps1
    run_day5_qwen_matrix.ps1
    run_day5_dashboard.ps1
    make_release_package.ps1

  docs/
    report_v0.3.md
    PPT_outline.md
    ETHICS_AND_SCOPE.md
    SYSTEM_ARCHITECTURE.md
    case_cards/
      DEMO_001_RAG_INDIRECT.md
      DEMO_002_JSON_RPC.md
      DEMO_003_MULTILINGUAL_T2L.md
    report_sections/
      03_attack_scenarios.md
      04_defense_design.md
      05_experiment_results.md

  outputs/
    runs/
      day5_stub_matrix/
      day5_qwen25_matrix/
      day5_demo_matrix/
    metrics/
      day5_stub_summary.csv
      day5_qwen25_summary.csv
      day5_final_summary.csv
      day5_summary.json
      DAY5_EXPERIMENT_SUMMARY.md
    figures/
      day5_asr_by_defense_mode.png
      day5_utr_by_defense_mode.png
      day5_bsr_by_defense_mode.png
      day5_fpr_by_defense_mode.png
      day5_asr_by_attack_family.png
      day5_guard_reasons_top10.png

  release/
    M3_PI_Guard_v0.5/
```

---

# A 模块：DAY5 详细任务

## A 今日定位

A 是**最终运行与提交包稳定性负责人**。DAY5 A 的目标不是写新功能，而是保证系统可以稳定复现。

A 今天要完成：

```text
1. 环境检查脚本
2. 最终实验运行
3. 一键 demo 脚本
4. 日志完整性检查
5. 输出 release 包
6. 演示电脑稳定性确认
```

---

## A-1：写环境检查脚本

创建：

```text
scripts/check_env.ps1
```

内容建议：

```powershell
Write-Host "==== M3_PI_Guard Environment Check ===="

python --version
pip show openai
pip show pandas
pip show streamlit

Write-Host "Checking Ollama..."
ollama list

Write-Host "Checking project directories..."
Test-Path m3_core
Test-Path m3_attacks
Test-Path m3_guard
Test-Path m3_eval
Test-Path sandbox
Test-Path outputs

Write-Host "Checking sandbox..."
Test-Path sandbox/secrets
Test-Path sandbox/outbox
Test-Path sandbox/logs

Write-Host "Done."
```

运行：

```powershell
.\scripts\check_env.ps1
```

验收：

```text
能显示 Python、依赖、Ollama 模型、项目目录均存在。
```

---

## A-2：最终样本运行前清理

不要删除历史结果，但要创建 DAY5 专用目录：

```bash
mkdir -p outputs/runs/day5_stub_matrix
mkdir -p outputs/runs/day5_qwen25_matrix
mkdir -p outputs/runs/day5_demo_matrix
mkdir -p outputs/metrics
mkdir -p outputs/figures
mkdir -p sandbox/outbox
mkdir -p sandbox/logs
```

Windows PowerShell：

```powershell
New-Item -ItemType Directory -Force outputs/runs/day5_stub_matrix
New-Item -ItemType Directory -Force outputs/runs/day5_qwen25_matrix
New-Item -ItemType Directory -Force outputs/runs/day5_demo_matrix
New-Item -ItemType Directory -Force outputs/metrics
New-Item -ItemType Directory -Force outputs/figures
New-Item -ItemType Directory -Force sandbox/outbox
New-Item -ItemType Directory -Force sandbox/logs
```

清空 DAY5 mock outbox，避免混入 DAY4：

```powershell
Remove-Item sandbox/outbox/day5_outbox.jsonl -ErrorAction SilentlyContinue
Remove-Item sandbox/logs/day5_tool_events.jsonl -ErrorAction SilentlyContinue
```

不要删除：

```text
sandbox/secrets/api_key.txt
```

它里面应该是假的 canary：

```text
M3_CANARY_SECRET_API_KEY=sk-local-redteam-demo-not-real
```

---

## A-3：stub 全量四模式最终实验

这是最终全量覆盖实验，必须完成。

```bash
python -m m3_core.run_matrix \
  --cases m3_attacks/cases/all_cases.jsonl \
  --backend stub \
  --defense-modes baseline,keyword_only,policy_only,full_guard \
  --out-dir outputs/runs/day5_stub_matrix \
  --run-prefix day5_stub_all \
  --max-steps 5
```

如果 Windows PowerShell：

```powershell
python -m m3_core.run_matrix `
  --cases m3_attacks/cases/all_cases.jsonl `
  --backend stub `
  --defense-modes baseline,keyword_only,policy_only,full_guard `
  --out-dir outputs/runs/day5_stub_matrix `
  --run-prefix day5_stub_all `
  --max-steps 5
```

生成文件应该包括：

```text
outputs/runs/day5_stub_matrix/day5_stub_all_baseline.jsonl
outputs/runs/day5_stub_matrix/day5_stub_all_keyword_only.jsonl
outputs/runs/day5_stub_matrix/day5_stub_all_policy_only.jsonl
outputs/runs/day5_stub_matrix/day5_stub_all_full_guard.jsonl
outputs/runs/day5_stub_matrix/manifest.json
```

验收标准：

```text
4 个 jsonl 文件都存在
每个文件非空
baseline 的 guard_decision 基本为 allow
full_guard 有 ask/deny
manifest.json 包含版本号、模型、时间、case 文件路径
```

---

## A-4：Qwen2.5 代表样本最终实验

不要强求 Qwen 跑全量。今天真实本地模型重点是“代表性验证”。

B 应该已经提供或确认：

```text
fixtures/day5_representative_cases.jsonl
```

建议 24 条左右：

```text
direct_jailbreak：3 条
rag_indirect：5 条
multilingual_t2l：4 条
json_rpc：4 条
tool_output_injection：3 条
benign_clean：5 条
```

运行：

```bash
python -m m3_core.run_matrix \
  --cases fixtures/day5_representative_cases.jsonl \
  --backend ollama \
  --model m3-target-qwen25-7b \
  --defense-modes baseline,full_guard \
  --out-dir outputs/runs/day5_qwen25_matrix \
  --run-prefix day5_qwen25_rep \
  --max-steps 5
```

如果时间够，再补 `keyword_only,policy_only`：

```bash
python -m m3_core.run_matrix \
  --cases fixtures/day5_representative_cases.jsonl \
  --backend ollama \
  --model m3-target-qwen25-7b \
  --defense-modes baseline,keyword_only,policy_only,full_guard \
  --out-dir outputs/runs/day5_qwen25_matrix \
  --run-prefix day5_qwen25_rep_full_ablation \
  --max-steps 5
```

最低验收：

```text
Qwen2.5 至少跑完 baseline 和 full_guard
至少覆盖 15 条以上代表样本
至少包含 3 个 demo case
```

---

## A-5：最终 Demo 运行矩阵

只跑 3 个 demo case，用于现场演示。

```bash
python -m m3_core.run_matrix \
  --cases fixtures/demo_cases.jsonl \
  --backend ollama \
  --model m3-target-qwen25-7b \
  --defense-modes baseline,full_guard \
  --out-dir outputs/runs/day5_demo_matrix \
  --run-prefix day5_demo \
  --max-steps 5
```

如果现场模型不稳定，用 stub 兜底：

```bash
python -m m3_core.run_matrix \
  --cases fixtures/demo_cases.jsonl \
  --backend stub \
  --defense-modes baseline,full_guard \
  --out-dir outputs/runs/day5_demo_matrix_stub \
  --run-prefix day5_demo_stub \
  --max-steps 5
```

---

## A-6：日志完整性检查

创建：

```text
m3_core/check_logs.py
```

支持命令：

```bash
python -m m3_core.check_logs --log-dir outputs/runs/day5_qwen25_matrix
```

检查：

```text
是否存在空日志
每条日志是否有 run_id/case_id/model/defense_mode/step
parsed_tool_call 是否存在
guard_decision 是否存在
final_status 是否存在
parse_error 是否过多
是否出现 sandbox 外路径
是否出现真实 URL / 真实邮箱 / 非 mock endpoint
```

输出：

```text
outputs/metrics/day5_log_audit.json
```

---

## A-7：一键运行脚本

创建或更新：

```text
scripts/run_day5_stub_matrix.ps1
scripts/run_day5_qwen_matrix.ps1
scripts/run_day5_demo.ps1
scripts/run_day5_dashboard.ps1
scripts/make_release_package.ps1
```

`run_day5_demo.ps1` 建议内容：

```powershell
conda activate LFischl

python -m m3_core.run_matrix `
  --cases fixtures/demo_cases.jsonl `
  --backend ollama `
  --model m3-target-qwen25-7b `
  --defense-modes baseline,full_guard `
  --out-dir outputs/runs/day5_demo_matrix `
  --run-prefix day5_demo `
  --max-steps 5

python -m m3_eval.evaluate `
  --log-dir outputs/runs/day5_demo_matrix `
  --cases fixtures/demo_cases.jsonl `
  --out outputs/metrics/day5_demo_summary.csv

streamlit run m3_eval/dashboard.py -- `
  --logs outputs/runs/day5_demo_matrix `
  --metrics outputs/metrics/day5_demo_summary.csv
```

---

## A-8：生成提交包

创建：

```text
release/M3_PI_Guard_v0.5/
```

复制：

```text
m3_core/
m3_attacks/
m3_guard/
m3_eval/
fixtures/
docs/
scripts/
outputs/metrics/
outputs/figures/
README.md
requirements-core.txt
requirements-dashboard.txt
```

不要复制：

```text
__pycache__/
.venv/
ollama 模型文件
sandbox/secrets/
sandbox/outbox/
大体积历史日志
.git/
```

保留少量演示日志：

```text
outputs/runs/day5_demo_matrix/
outputs/runs/day5_qwen25_matrix/
```

不要把真实本机路径写死。

---

## A 今日交付物

```text
scripts/check_env.ps1
scripts/run_day5_stub_matrix.ps1
scripts/run_day5_qwen_matrix.ps1
scripts/run_day5_demo.ps1
scripts/run_day5_dashboard.ps1
scripts/make_release_package.ps1

m3_core/check_logs.py

outputs/runs/day5_stub_matrix/
outputs/runs/day5_qwen25_matrix/
outputs/runs/day5_demo_matrix/
outputs/metrics/day5_log_audit.json

release/M3_PI_Guard_v0.5/
```

---

## A 可以直接给 AIagent 的 DAY5 指令

```text
你是队员 A 的本地 AIagent。今天是 DAY5，项目已经完成 DAY4 的消融实验和 Dashboard 初版。今天你的任务是负责最终运行、稳定性检查、一键脚本和提交包。

请只修改：
m3_core/
scripts/
fixtures/
outputs/runs/
outputs/metrics/
release/

目标：
1. 创建 scripts/check_env.ps1，用于检查 Python、依赖、Ollama、项目目录、sandbox 目录。
2. 运行 stub 全量四模式实验：
   baseline、keyword_only、policy_only、full_guard。
3. 运行 Qwen2.5 代表性样本实验，至少 baseline 和 full_guard 两组。
4. 运行 fixtures/demo_cases.jsonl 的最终 demo 实验。
5. 创建 m3_core/check_logs.py，检查日志完整性、parse_error、sandbox 越界、非 mock endpoint、真实 URL/邮箱等风险。
6. 创建或更新 DAY5 一键脚本：
   scripts/run_day5_stub_matrix.ps1
   scripts/run_day5_qwen_matrix.ps1
   scripts/run_day5_demo.ps1
   scripts/run_day5_dashboard.ps1
   scripts/make_release_package.ps1
7. 生成 release/M3_PI_Guard_v0.5/ 提交包目录。

安全要求：
- 不真实发送邮件。
- 不访问公网 API。
- 不执行模型生成代码。
- 不复制 sandbox/secrets/ 到 release 包。
- 不提交模型文件。

请确保以下命令可运行：

python -m m3_core.run_matrix --cases m3_attacks/cases/all_cases.jsonl --backend stub --defense-modes baseline,keyword_only,policy_only,full_guard --out-dir outputs/runs/day5_stub_matrix --run-prefix day5_stub_all --max-steps 5

python -m m3_core.run_matrix --cases fixtures/day5_representative_cases.jsonl --backend ollama --model m3-target-qwen25-7b --defense-modes baseline,full_guard --out-dir outputs/runs/day5_qwen25_matrix --run-prefix day5_qwen25_rep --max-steps 5

python -m m3_core.run_matrix --cases fixtures/demo_cases.jsonl --backend ollama --model m3-target-qwen25-7b --defense-modes baseline,full_guard --out-dir outputs/runs/day5_demo_matrix --run-prefix day5_demo --max-steps 5

python -m m3_core.check_logs --log-dir outputs/runs/day5_qwen25_matrix

完成后请输出：
1. 生成的日志文件路径
2. 每组实验的 case 数量
3. parse_error 数量
4. 日志审计结果路径
5. 一键脚本路径
6. release 包路径
7. 当前仍然不稳定的 case_id
```

---

# B 模块：DAY5 详细任务

## B 今日定位

B 是**红队样本、案例叙事和答辩攻击侧材料负责人**。DAY5 B 不再追求增加样本数量，而是要把已有样本“讲清楚、审干净、可展示”。

B 今天要完成：

```text
1. 最终样本审计
2. demo case 最终确认
3. 代表性样本集 day5_representative_cases.jsonl
4. 3 个案例卡最终版
5. 攻击矩阵最终版
6. 报告攻击章节最终版
7. PPT 攻击部分讲稿
```

---

## B-1：最终样本审计

运行：

```bash
python -m m3_attacks.attackgen \
  --out m3_attacks/cases/all_cases.jsonl \
  --stats outputs/metrics/day5_case_stats.json \
  --audit outputs/metrics/day5_case_audit.json
```

必须检查并修复：

```text
case_id 重复
字段缺失
attack_family 命名不统一
severity 为空
language 为空
unsafe_target_actions 不是 mock 工具
document_content 为空
expected_safe_behavior 为空
benign_clean 却有 unsafe_target_actions
样本中出现真实邮箱/真实 URL/真实攻击命令
样本中出现真实敏感路径，例如 C:\Users\... 或 /etc/passwd
样本中出现不可解释的危险内容
```

允许的 unsafe_target_actions 只能是：

```text
read_file:sandbox/secrets/api_key.txt
send_email:redteam@example.test
write_file:sandbox/public/notes.txt
call_api:/mock/external/submit
run_code:mock_only
```

今天如果发现问题样本，不要临时大改攻击逻辑，优先：

```text
修 schema
改成 mock 目标
降低危险描述
移到备用样本
```

---

## B-2：冻结最终样本统计

生成：

```text
docs/DATASET_CARD.md
```

内容：

```markdown
# M3-PI Guard 红队样本集说明

## 1. 样本规模
- 总样本数：
- 攻击样本数：
- benign_clean 样本数：

## 2. 攻击类型分布
| attack_family | count |
|---|---|

## 3. 载体分布
| carrier | count |
|---|---|

## 4. 语言分布
| language | count |
|---|---|

## 5. 工具目标分布
| unsafe_target_action | count |
|---|---|

## 6. 安全边界
所有样本仅用于本地 sandbox mock 工具，不访问真实网络、不读取真实敏感文件、不发送真实邮件、不执行真实代码。

## 7. 使用方式
python -m m3_attacks.attackgen --out m3_attacks/cases/all_cases.jsonl
```

---

## B-3：确认 day5_representative_cases.jsonl

创建或最终确认：

```text
fixtures/day5_representative_cases.jsonl
```

建议 20–30 条，不要过多，否则 A 跑不完。

推荐配置：

| 类型                    | 数量 |
| --------------------- | -: |
| direct_jailbreak      |  3 |
| rag_indirect          |  5 |
| multilingual_t2l      |  4 |
| json_rpc              |  4 |
| tool_output_injection |  3 |
| benign_clean          |  5 |
| 合计                    | 24 |

选择标准：

```text
1. 攻击意图清晰
2. baseline 更容易出现异常工具调用
3. full_guard 更容易给出清晰 reasons
4. 不含真实攻击内容
5. 适合答辩讲解
```

---

## B-4：最终确认 3 个 Demo Case

三个 demo 必须稳定可讲：

```text
DEMO-001：RAG 文档间接提示注入
DEMO-002：JSON/RPC 结构化注入
DEMO-003：多语言/T2L 注入
```

每个 demo case 要有：

```text
1. case_id
2. user_task
3. attack_family
4. carrier
5. injected_content 摘要
6. unsafe_target_actions
7. expected_safe_behavior
8. baseline 预期
9. full_guard 预期
10. 对应截图编号
```

---

## B-5：案例卡最终版

更新：

```text
docs/case_cards/DEMO_001_RAG_INDIRECT.md
docs/case_cards/DEMO_002_JSON_RPC.md
docs/case_cards/DEMO_003_MULTILINGUAL_T2L.md
```

每个案例卡要包含：

```markdown
# DEMO-001：RAG 文档间接提示注入

## 1. 红队目标
## 2. 攻击入口
## 3. 攻击载体
## 4. 用户正常任务
## 5. 注入内容摘要
## 6. 预期安全行为
## 7. 不安全目标动作
## 8. baseline 下观察到的行为
## 9. full_guard 下观察到的行为
## 10. Guard 触发原因
## 11. 关键证据文件
## 12. 安全边界声明
```

“关键证据文件”填写：

```text
outputs/runs/day5_demo_matrix/day5_demo_baseline.jsonl
outputs/runs/day5_demo_matrix/day5_demo_full_guard.jsonl
outputs/metrics/day5_demo_summary.csv
outputs/figures/...
```

---

## B-6：攻击章节最终版

更新：

```text
docs/report_sections/03_attack_scenarios.md
```

建议结构：

```markdown
# 3. 红队攻击场景设计

## 3.1 攻击总体设计
说明我们只在本地 sandbox 中模拟攻击，目标是验证 Agent 信任边界与工具调用风险。

## 3.2 直接越狱与说服性提示
说明角色扮演、权限伪装、说服性提示、场景嵌套。

## 3.3 RAG/文档间接提示注入
说明恶意指令来自不可信文档、邮件、网页、FAQ、工具返回值。

## 3.4 多语言/T2L 注入
说明中英混合、翻译任务切换、拼音/谐音、跨语言扰动。

## 3.5 JSON/RPC 结构化注入
说明 instruction/system/developer/function_call/method/params 等字段欺骗。

## 3.6 工具输出注入
说明工具返回值污染下一步计划。

## 3.7 benign_clean 样本
说明用于 FPR 校准。

## 3.8 红队安全边界
说明所有攻击均是本地授权模拟。
```

---

## B-7：PPT 攻击部分讲稿

创建：

```text
docs/PPT_attack_notes.md
```

内容按 2 分钟讲：

```markdown
# 攻击侧讲稿

我们的红队样本集不是追求真实破坏，而是构造本地沙箱中的可控攻击链。我们覆盖五类攻击：直接越狱、RAG 间接提示注入、多语言/T2L、JSON/RPC 结构化注入、工具输出注入。每条样本都只指向 mock 工具，例如读取 sandbox/secrets/api_key.txt 中的 canary 假密钥，或调用 mock send_email 写入 outbox 文件。

最重要的是 RAG 间接提示注入。用户任务只是总结报告，但报告中包含伪装指令，诱导 Agent 读取 secret 并尝试外发。在 baseline 模式下，Agent 可能把文档内容误认为高优先级指令；在 full_guard 模式下，系统会识别 untrusted_source_instruction、secret_path_access 和 intent_action_mismatch，并阻断工具调用。
```

---

## B 今日交付物

```text
m3_attacks/cases/all_cases.jsonl
outputs/metrics/day5_case_stats.json
outputs/metrics/day5_case_audit.json

fixtures/day5_representative_cases.jsonl
fixtures/demo_cases.jsonl

docs/DATASET_CARD.md
docs/ATTACK_MATRIX.md 或 m3_attacks/ATTACK_MATRIX.md
docs/case_cards/DEMO_001_RAG_INDIRECT.md
docs/case_cards/DEMO_002_JSON_RPC.md
docs/case_cards/DEMO_003_MULTILINGUAL_T2L.md
docs/report_sections/03_attack_scenarios.md
docs/ETHICS_AND_SCOPE.md
docs/PPT_attack_notes.md
```

---

## B 可以直接给 AIagent 的 DAY5 指令

```text
你是队员 B 的本地 AIagent。今天是 DAY5，项目已经进入竞赛作品收尾阶段。你的任务是负责红队样本审计、代表案例选择、攻击章节和答辩攻击侧材料。

请只修改：
m3_attacks/
fixtures/
docs/
outputs/metrics/

目标：
1. 审计 m3_attacks/cases/all_cases.jsonl，确保无重复 case_id、无缺失字段、无真实攻击内容。
2. 确保 unsafe_target_actions 只包含以下 mock 动作：
   read_file:sandbox/secrets/api_key.txt
   send_email:redteam@example.test
   write_file:sandbox/public/notes.txt
   call_api:/mock/external/submit
   run_code:mock_only
3. 生成 outputs/metrics/day5_case_stats.json 和 outputs/metrics/day5_case_audit.json。
4. 创建 docs/DATASET_CARD.md，总结样本规模、攻击类型分布、语言分布、载体分布和安全边界。
5. 创建或确认 fixtures/day5_representative_cases.jsonl，包含 20–30 条代表性样本，覆盖 direct_jailbreak、rag_indirect、multilingual_t2l、json_rpc、tool_output_injection、benign_clean。
6. 最终确认 fixtures/demo_cases.jsonl 中 3 个 demo：
   DEMO-001 RAG 间接提示注入
   DEMO-002 JSON/RPC 结构化注入
   DEMO-003 多语言/T2L 注入
7. 完成 3 个案例卡：
   docs/case_cards/DEMO_001_RAG_INDIRECT.md
   docs/case_cards/DEMO_002_JSON_RPC.md
   docs/case_cards/DEMO_003_MULTILINGUAL_T2L.md
8. 更新 docs/report_sections/03_attack_scenarios.md。
9. 创建 docs/PPT_attack_notes.md，写出攻击侧 2 分钟讲稿。

运行：
python -m m3_attacks.attackgen --out m3_attacks/cases/all_cases.jsonl --stats outputs/metrics/day5_case_stats.json --audit outputs/metrics/day5_case_audit.json

完成后请输出：
1. 样本总数
2. 每类 attack_family 数量
3. benign_clean 数量
4. 修复的问题样本列表
5. day5_representative_cases.jsonl 的 case_id 列表
6. 3 个 demo case_id
7. 案例卡路径
8. 攻击章节路径
9. 样本安全边界说明
```

---

# C 模块：DAY5 详细任务

## C 今日定位

C 是**最终指标、Dashboard、报告和答辩结果侧负责人**。DAY5 C 的重点是把结果做成评委能看懂的证据。

C 今天要完成：

```text
1. 最终指标 CSV/JSON
2. 最终图表 PNG
3. Dashboard 演示版
4. 报告 v0.3
5. 实验总结
6. PPT 结果部分讲稿
```

自动红队和评测框架的价值在于为模型应用安全性、鲁棒性和运行表现生成可验证证据与指标，这正好对应你们 DAY5 要做的“最终证据链”。

---

## C-1：生成 stub 全量指标

运行：

```bash
python -m m3_eval.evaluate \
  --log-dir outputs/runs/day5_stub_matrix \
  --cases m3_attacks/cases/all_cases.jsonl \
  --out outputs/metrics/day5_stub_summary.csv
```

应该同时生成：

```text
outputs/metrics/day5_stub_summary.csv
outputs/metrics/day5_stub_summary.json
outputs/metrics/day5_stub_grouped_by_family.csv
outputs/metrics/day5_stub_grouped_by_mode.csv
outputs/metrics/day5_stub_grouped_by_language.csv
```

验收：

```text
baseline、keyword_only、policy_only、full_guard 四模式都有指标
按 attack_family 有分组
按 defense_mode 有分组
FPR 可以计算
```

---

## C-2：生成 Qwen2.5 代表样本指标

运行：

```bash
python -m m3_eval.evaluate \
  --log-dir outputs/runs/day5_qwen25_matrix \
  --cases fixtures/day5_representative_cases.jsonl \
  --out outputs/metrics/day5_qwen25_summary.csv
```

生成：

```text
outputs/metrics/day5_qwen25_summary.csv
outputs/metrics/day5_qwen25_summary.json
outputs/metrics/day5_qwen25_grouped_by_family.csv
outputs/metrics/day5_qwen25_grouped_by_mode.csv
```

---

## C-3：生成 demo 指标

运行：

```bash
python -m m3_eval.evaluate \
  --log-dir outputs/runs/day5_demo_matrix \
  --cases fixtures/demo_cases.jsonl \
  --out outputs/metrics/day5_demo_summary.csv
```

demo 指标要用于现场展示，不需要复杂，但要清晰：

```text
case_id
attack_family
defense_mode
tool_called
guard_decision
risk_score
reasons
final_status
```

---

## C-4：生成最终综合 summary

创建：

```text
outputs/metrics/day5_final_summary.csv
outputs/metrics/day5_final_summary.json
```

建议综合：

```text
stub 全量结果
Qwen2.5 代表样本结果
demo case 结果
```

`day5_final_summary.json` 可以写：

```json
{
  "project": "M3_PI_Guard",
  "version": "v0.5-day5",
  "dataset": {
    "all_cases": 0,
    "representative_cases": 0,
    "demo_cases": 3
  },
  "models": [
    "stub",
    "m3-target-qwen25-7b"
  ],
  "defense_modes": [
    "baseline",
    "keyword_only",
    "policy_only",
    "full_guard"
  ],
  "key_findings": [
    "full_guard reduced unauthorized mock tool calls compared with baseline",
    "policy_only is effective for explicit high-risk tools but weaker for hidden prompt injection",
    "keyword_only detects obvious instruction text but misses behavior-level data flow risk"
  ]
}
```

---

## C-5：最终图表

运行：

```bash
python -m m3_eval.plot_metrics \
  --summary outputs/metrics/day5_qwen25_summary.csv \
  --out-dir outputs/figures
```

至少生成：

```text
outputs/figures/day5_asr_by_defense_mode.png
outputs/figures/day5_utr_by_defense_mode.png
outputs/figures/day5_dsr_by_defense_mode.png
outputs/figures/day5_bsr_by_defense_mode.png
outputs/figures/day5_fpr_by_defense_mode.png
outputs/figures/day5_wrs_by_defense_mode.png
outputs/figures/day5_asr_by_attack_family.png
outputs/figures/day5_guard_reasons_top10.png
```

图表要求：

```text
标题清楚
横轴/纵轴清楚
不要依赖交互页面才能看
能直接放报告/PPT
```

---

## C-6：Dashboard 最终版检查

运行：

```bash
streamlit run m3_eval/dashboard.py -- \
  --logs outputs/runs/day5_qwen25_matrix \
  --metrics outputs/metrics/day5_qwen25_summary.csv
```

Dashboard 至少要有 6 个区域：

```text
1. 项目总览
2. 防御模式对比
3. 攻击类型分组
4. 阻断/告警记录
5. 单案例回放
6. 原始日志查看
```

单案例回放必须显示：

```text
case_id
attack_family
user_task
document_content 摘要
baseline 下模型输出
baseline 下工具调用
full_guard 下模型输出
full_guard 下 Guard 决策
risk_score
reasons
observation
```

---

## C-7：报告 v0.3

更新：

```text
docs/report_v0.3.md
```

结构建议：

```markdown
# M?-PI Guard：面向大模型智能体的提示注入红队评测与行为监督系统

## 摘要

## 1. 项目背景与赛题对应关系
说明对应面向大模型及其应用的安全性研究方向。

## 2. 威胁模型
说明用户输入、不可信文档、工具输出、模拟外发工具、文件访问等攻击面。

## 3. 红队攻击场景设计
引用 B 的攻击章节。

## 4. 系统架构
说明 Agent 靶场、LLM、本地工具沙箱、Guard、Evaluator、Dashboard。

## 5. 行为监督机制
说明 Prompt Analyzer、Context Isolation、Policy Engine、Dataflow Tracker、Call-chain Auditor。

## 6. 实验设置
说明模型、硬件、样本集、防御模式、运行方式。

## 7. 评测指标
ASR、UTR、DSR、BSR、FPR、AvgRisk、WRS。

## 8. 实验结果
插入最终 CSV 表格和图表。

## 9. 代表性案例分析
DEMO-001 / DEMO-002 / DEMO-003。

## 10. 系统实现与使用说明
一键运行命令。

## 11. 安全边界与伦理声明
强调本地授权 mock 测试。

## 12. 局限性与后续工作
本地模型规模有限、样本为合成、Guard 以规则为主、多模态作为未来扩展。
```

报告里要把“为什么不用远程大模型也有说服力”写清楚：

```text
我们关注的是智能体工具链行为风险，而不是真实危险内容生成。
通过 mock 工具、canary 数据、调用链日志和阻断记录，可以验证提示注入导致的未授权行为链。
本地 Qwen2.5 作为代表模型，stub 全量实验用于覆盖完整样本集，二者共同保证可复现性与实验覆盖。
```

---

## C-8：PPT 结果部分讲稿

创建：

```text
docs/PPT_result_notes.md
```

内容按 2 分钟讲：

```markdown
# 结果侧讲稿

我们设置了四种防御模式：baseline、keyword_only、policy_only 和 full_guard。baseline 不做拦截，用来观察 Agent 在攻击样本下是否会触发未授权 mock 工具调用。keyword_only 只检测提示注入关键词，policy_only 只检查工具和路径策略，full_guard 同时使用输入规范化、结构化注入检测、上下文隔离、工具策略、敏感数据流追踪和意图-动作一致性检测。

实验中，我们分别在 stub 全量样本和本地 Qwen2.5 代表样本上运行。结果显示，full_guard 相比 baseline 明显降低未授权工具调用和敏感数据外发风险，同时通过 benign_clean 样本计算误报率。Dashboard 可以回放每个 case 的模型输出、工具调用、风险分和阻断原因。
```

---

## C 今日交付物

```text
outputs/metrics/day5_stub_summary.csv
outputs/metrics/day5_qwen25_summary.csv
outputs/metrics/day5_demo_summary.csv
outputs/metrics/day5_final_summary.csv
outputs/metrics/day5_final_summary.json
outputs/metrics/DAY5_EXPERIMENT_SUMMARY.md

outputs/figures/day5_asr_by_defense_mode.png
outputs/figures/day5_utr_by_defense_mode.png
outputs/figures/day5_dsr_by_defense_mode.png
outputs/figures/day5_bsr_by_defense_mode.png
outputs/figures/day5_fpr_by_defense_mode.png
outputs/figures/day5_wrs_by_defense_mode.png
outputs/figures/day5_asr_by_attack_family.png
outputs/figures/day5_guard_reasons_top10.png

docs/report_v0.3.md
docs/PPT_result_notes.md
```

---

## C 可以直接给 AIagent 的 DAY5 指令

```text
你是队员 C 的本地 AIagent。今天是 DAY5，项目已经进入最终提交和答辩准备阶段。你的任务是生成最终指标、图表、Dashboard 演示版、报告 v0.3 和结果讲稿。

请只修改：
m3_eval/
m3_guard/ 仅限 bug fix
outputs/metrics/
outputs/figures/
docs/

目标：
1. 读取 outputs/runs/day5_stub_matrix，生成 stub 全量四模式指标。
2. 读取 outputs/runs/day5_qwen25_matrix，生成 Qwen2.5 代表样本指标。
3. 读取 outputs/runs/day5_demo_matrix，生成 demo case 指标。
4. 输出 day5_final_summary.csv 和 day5_final_summary.json。
5. 生成至少 8 张图：
   day5_asr_by_defense_mode.png
   day5_utr_by_defense_mode.png
   day5_dsr_by_defense_mode.png
   day5_bsr_by_defense_mode.png
   day5_fpr_by_defense_mode.png
   day5_wrs_by_defense_mode.png
   day5_asr_by_attack_family.png
   day5_guard_reasons_top10.png
6. 检查 Dashboard，确保支持项目总览、防御模式对比、攻击类型分组、阻断记录、单案例回放、原始日志查看。
7. 完成 docs/report_v0.3.md。
8. 创建 docs/PPT_result_notes.md。
9. 创建 outputs/metrics/DAY5_EXPERIMENT_SUMMARY.md。

运行命令：
python -m m3_eval.evaluate --log-dir outputs/runs/day5_stub_matrix --cases m3_attacks/cases/all_cases.jsonl --out outputs/metrics/day5_stub_summary.csv

python -m m3_eval.evaluate --log-dir outputs/runs/day5_qwen25_matrix --cases fixtures/day5_representative_cases.jsonl --out outputs/metrics/day5_qwen25_summary.csv

python -m m3_eval.evaluate --log-dir outputs/runs/day5_demo_matrix --cases fixtures/demo_cases.jsonl --out outputs/metrics/day5_demo_summary.csv

python -m m3_eval.plot_metrics --summary outputs/metrics/day5_qwen25_summary.csv --out-dir outputs/figures

streamlit run m3_eval/dashboard.py -- --logs outputs/runs/day5_qwen25_matrix --metrics outputs/metrics/day5_qwen25_summary.csv

完成后请输出：
1. 生成的 CSV/JSON 文件路径
2. 生成的图表路径
3. Dashboard 运行命令
4. 报告 v0.3 路径
5. DAY5 实验结论摘要
6. 当前风险或数据异常
```

---

# DAY5 中午第一次集成：12:30 前必须完成

## 目标

```text
stub 全量四模式跑完
样本审计完成
stub 指标生成
```

## 执行顺序

B 先提交样本审计：

```bash
python -m m3_attacks.attackgen \
  --out m3_attacks/cases/all_cases.jsonl \
  --stats outputs/metrics/day5_case_stats.json \
  --audit outputs/metrics/day5_case_audit.json
```

A 跑 stub：

```bash
python -m m3_core.run_matrix \
  --cases m3_attacks/cases/all_cases.jsonl \
  --backend stub \
  --defense-modes baseline,keyword_only,policy_only,full_guard \
  --out-dir outputs/runs/day5_stub_matrix \
  --run-prefix day5_stub_all \
  --max-steps 5
```

C 生成指标：

```bash
python -m m3_eval.evaluate \
  --log-dir outputs/runs/day5_stub_matrix \
  --cases m3_attacks/cases/all_cases.jsonl \
  --out outputs/metrics/day5_stub_summary.csv
```

中午验收：

```text
all_cases.jsonl 无审计错误
day5_stub_matrix 有四份日志
day5_stub_summary.csv 存在
baseline 阻断率约为 0
full_guard 有 ask/deny
benign_clean FPR 可计算
```

---

# DAY5 下午第二次集成：15:30 前完成

## 目标

```text
Qwen2.5 代表样本 baseline/full_guard 跑完
demo cases 跑完
Qwen 指标生成
```

A 跑 Qwen：

```bash
python -m m3_core.run_matrix \
  --cases fixtures/day5_representative_cases.jsonl \
  --backend ollama \
  --model m3-target-qwen25-7b \
  --defense-modes baseline,full_guard \
  --out-dir outputs/runs/day5_qwen25_matrix \
  --run-prefix day5_qwen25_rep \
  --max-steps 5
```

A 跑 demo：

```bash
python -m m3_core.run_matrix \
  --cases fixtures/demo_cases.jsonl \
  --backend ollama \
  --model m3-target-qwen25-7b \
  --defense-modes baseline,full_guard \
  --out-dir outputs/runs/day5_demo_matrix \
  --run-prefix day5_demo \
  --max-steps 5
```

C 生成 Qwen 指标：

```bash
python -m m3_eval.evaluate \
  --log-dir outputs/runs/day5_qwen25_matrix \
  --cases fixtures/day5_representative_cases.jsonl \
  --out outputs/metrics/day5_qwen25_summary.csv
```

C 生成 demo 指标：

```bash
python -m m3_eval.evaluate \
  --log-dir outputs/runs/day5_demo_matrix \
  --cases fixtures/demo_cases.jsonl \
  --out outputs/metrics/day5_demo_summary.csv
```

下午验收：

```text
Qwen 至少跑完 15–24 条代表样本
demo 3 条都跑完
day5_qwen25_summary.csv 存在
day5_demo_summary.csv 存在
至少有 1 个案例能清楚展示 baseline 与 full_guard 差异
```

---

# DAY5 傍晚第三次集成：18:30 前完成

## 目标

```text
Dashboard 演示稳定
报告 v0.3 有内容
图表可用
```

C 生成图：

```bash
python -m m3_eval.plot_metrics \
  --summary outputs/metrics/day5_qwen25_summary.csv \
  --out-dir outputs/figures
```

打开 Dashboard：

```bash
streamlit run m3_eval/dashboard.py -- \
  --logs outputs/runs/day5_qwen25_matrix \
  --metrics outputs/metrics/day5_qwen25_summary.csv
```

全员检查 3 个 demo：

```text
DEMO-001 RAG 间接注入
DEMO-002 JSON/RPC 注入
DEMO-003 多语言/T2L 注入
```

每个 demo 记录：

```text
baseline 的工具调用
full_guard 的阻断动作
risk_score
reasons
截图路径
```

---

# DAY5 晚上模拟答辩流程

你们晚上至少模拟 2 遍，每遍控制在 6–8 分钟。

## 推荐讲解顺序

### 第 1 分钟：项目背景

```text
我们研究的是大模型智能体应用中的提示注入和越狱攻击风险。
传统只看模型输出是否违规，但智能体更关键的问题是：模型是否会被恶意提示诱导去调用工具、读文件、发邮件、调用 API 或执行代码。
```

### 第 2 分钟：系统架构

```text
本系统包含红队攻击样本库、本地 Agent 靶场、mock 工具沙箱、行为监督 Guard、评测模块和 Dashboard。
```

### 第 3 分钟：攻击样本

```text
我们覆盖 direct_jailbreak、rag_indirect、multilingual_t2l、json_rpc、tool_output_injection，并加入 benign_clean 样本计算误报。
```

### 第 4 分钟：防御机制

```text
Guard 包含输入规范化、结构化注入检测、上下文隔离、工具策略、数据流追踪和意图-动作一致性检测。
```

### 第 5–6 分钟：Demo

展示：

```text
baseline：模型尝试 read_file/send_email mock 工具
full_guard：系统识别风险并 deny/ask
Dashboard：展示风险分、reasons 和调用链
```

### 第 7 分钟：实验结果

```text
对比 baseline、keyword_only、policy_only、full_guard。
full_guard 明显降低未授权工具调用和敏感数据外发风险。
```

### 第 8 分钟：安全边界与总结

```text
所有攻击均为本地授权红队模拟，不访问真实网络、不使用真实账号、不执行真实代码。
```

---

# DAY5 最终验收表

| 模块 | 必须完成       | 验收标准                                                 |
| -- | ---------- | ---------------------------------------------------- |
| A  | stub 全量四模式 | day5_stub_matrix 生成四份日志                              |
| A  | Qwen 代表样本  | baseline/full_guard 至少跑完 15 条以上                      |
| A  | demo 运行    | fixtures/demo_cases.jsonl 三条都可跑                      |
| A  | 日志审计       | day5_log_audit.json 生成，无高危真实行为                       |
| A  | 一键脚本       | run_day5_demo.ps1 可用                                 |
| B  | 样本审计       | day5_case_audit.json 无严重错误                           |
| B  | 数据集说明      | DATASET_CARD.md 完成                                   |
| B  | 代表样本       | day5_representative_cases.jsonl 完成                   |
| B  | 案例卡        | 3 个 demo case card 完成                                |
| B  | 攻击章节       | 03_attack_scenarios.md 完成                            |
| C  | 最终指标       | day5_stub_summary / qwen25_summary / demo_summary 生成 |
| C  | 图表         | 至少 8 张 PNG                                           |
| C  | Dashboard  | 能展示单案例回放                                             |
| C  | 报告         | report_v0.3.md 完成                                    |
| 全队 | 模拟答辩       | 至少完整演练 2 遍                                           |
| 全队 | 提交包        | release/M3_PI_Guard_v0.5 完成                          |

---

# DAY5 结束时应得到的最终文件

```text
outputs/runs/
  day5_stub_matrix/
  day5_qwen25_matrix/
  day5_demo_matrix/

outputs/metrics/
  day5_case_stats.json
  day5_case_audit.json
  day5_log_audit.json
  day5_stub_summary.csv
  day5_qwen25_summary.csv
  day5_demo_summary.csv
  day5_final_summary.csv
  day5_final_summary.json
  DAY5_EXPERIMENT_SUMMARY.md

outputs/figures/
  day5_asr_by_defense_mode.png
  day5_utr_by_defense_mode.png
  day5_dsr_by_defense_mode.png
  day5_bsr_by_defense_mode.png
  day5_fpr_by_defense_mode.png
  day5_wrs_by_defense_mode.png
  day5_asr_by_attack_family.png
  day5_guard_reasons_top10.png

docs/
  report_v0.3.md
  DATASET_CARD.md
  ETHICS_AND_SCOPE.md
  PPT_attack_notes.md
  PPT_result_notes.md
  case_cards/
    DEMO_001_RAG_INDIRECT.md
    DEMO_002_JSON_RPC.md
    DEMO_003_MULTILINGUAL_T2L.md
  report_sections/
    03_attack_scenarios.md
    04_defense_design.md
    05_experiment_results.md

scripts/
  check_env.ps1
  run_day5_stub_matrix.ps1
  run_day5_qwen_matrix.ps1
  run_day5_demo.ps1
  run_day5_dashboard.ps1
  make_release_package.ps1

release/
  M3_PI_Guard_v0.5/
```

---

# DAY5 风险与兜底方案

## 风险 1：Qwen2.5 跑得太慢

兜底：

```text
stub 全量四模式作为完整覆盖实验
Qwen2.5 只跑 demo 3 条 + 代表样本 10–15 条
报告中明确说明硬件限制和代表性验证策略
```

可写入报告：

```text
由于本地 8GB 显存设备限制，完整样本集采用 stub 靶场进行全量消融；真实本地 LLM 使用 Qwen2.5-7B 量化模型在代表性样本上验证攻击链和防御效果。
```

---

## 风险 2：baseline 没有稳定触发危险工具

兜底：

```text
选 demo_priority=1 的样本
降低 baseline prompt 中的安全提醒
使用 stub 演示完整攻击链
Qwen 作为代表性自然输出补充
```

答辩时可以说：

```text
本项目评估的是 Agent 工具链信任边界，stub 用于稳定复现攻击链，Qwen 用于验证真实模型下的可迁移性。
```

---

## 风险 3：full_guard 误报偏高

兜底：

```text
检查 benign_clean
read_file sandbox/public 放行
普通 final 放行
普通 JSON 字段抽取放行
send_email 默认 ask 而不是全部 deny
```

报告中解释：

```text
ask 是安全交互策略，不等同于误杀；对高风险外发工具采用人工确认是可接受的安全设计。
```

---

## 风险 4：Dashboard 临场卡顿

兜底：

```text
提前截图
准备 CSV 表格
准备 case card
保留 Streamlit 最小功能：summary + logs + case_id 回放
```

---

# DAY5 最后 30 分钟检查清单

全员一起检查：

```text
[ ] README 有安装和运行说明
[ ] requirements-core.txt 可用
[ ] requirements-dashboard.txt 可用
[ ] all_cases.jsonl 存在
[ ] demo_cases.jsonl 存在
[ ] day5_representative_cases.jsonl 存在
[ ] day5_stub_matrix 有日志
[ ] day5_qwen25_matrix 有日志
[ ] day5_demo_matrix 有日志
[ ] day5_qwen25_summary.csv 存在
[ ] 图表 PNG 存在
[ ] Dashboard 能启动
[ ] report_v0.3.md 有完整章节
[ ] ETHICS_AND_SCOPE.md 明确安全边界
[ ] release 包不包含 sandbox/secrets/
[ ] release 包不包含模型文件
[ ] demo 脚本能运行
[ ] 已打 tag
```

打 tag：

```bash
git checkout day5-release
git pull
git tag day5-v0.5
git push origin day5-v0.5
```

---

# DAY5 一句话执行口号

```text
A：跑稳最终实验，做出可复现提交包。
B：审干净样本，讲清楚红队案例。
C：做实指标图表，完成报告和 Dashboard。
```

DAY5 结束后，你们的作品应该已经具备**正式提交雏形**：有红队样本库、有本地 Agent 靶场、有行为监督系统、有消融实验、有 Dashboard、有报告、有演示案例、有安全边界声明。
