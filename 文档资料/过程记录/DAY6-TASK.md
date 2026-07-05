下面给出 **DAY6 详细任务**。你们 DAY5 已经完成最终实验、Dashboard、图表、报告草稿和提交包雏形。**DAY6 的核心任务是“提交前清洗 + 官方模板报告成稿 + 发布包质检”**。

今天不要再扩展攻击样本、不要再大改系统功能。DAY6 只做三件事：

```text
1. 清理项目中所有 AIagent / Codex / 自动生成指令痕迹
2. 按官方 Word 模板写出正式作品报告
3. 生成干净、匿名、可提交、可复现的 release 包
```

官方模板要求作品报告采用 A4 纸，除标题外使用宋体、小四号字、1.5 倍行距；模板中的说明文字在报告撰写完毕后要删除，但“填写说明”页不删除；同时报告中应避免出现学校、院系、指导教师等泄露身份的信息。模板的主体结构包括摘要、第一章作品概述、第二章作品设计与实现、第三章作品测试与分析、第四章创新性说明、第五章总结和参考文献。

---

# DAY6 总目标

DAY6 结束时，你们应该得到：

```text
1. 一个无 AIagent / Codex / 自动生成指令痕迹的干净项目目录
2. 一份按官方模板完成的 Word 报告：
   docs/report/作品报告_终稿.docx
3. 一份可选 PDF：
   docs/report/作品报告_终稿.pdf
4. 一个干净 release 包：
   release/Redteam_LLM_Security_v1.0/
5. 一份清理记录：
   outputs/quality/day6_cleanup_log.md
6. 一份提交前检查清单：
   outputs/quality/day6_release_checklist.md
```

---

# DAY6 工作原则

今天最重要的是**不要误删功能代码**。

你们要删除的是：

```text
AIagent 指令
Codex 指令
“你是队员 A/B/C 的本地 AIagent”这类提示
“请只修改……”
“完成后请输出……”
DAY2/DAY3/DAY4/DAY5 给 AIagent 的任务指令
“由 AI 生成”
“ChatGPT 生成”
“Codex 生成”
“AI 写的”
开发过程中的提示词、任务单、对话痕迹
```

但不要删除：

```text
LLM Agent 作为系统概念
Agent 靶场
AI 安全
大模型
OpenAI SDK 包名
openai Python 库引用
模型名称 Qwen / Llama / DeepSeek
攻击样本中的 prompt injection 内容
实验日志中的 model 字段
报告中关于大模型安全的必要描述
```

换句话说：

> **删除“开发过程中的 AI 协作痕迹”，保留“作品研究对象中的 AI/LLM/Agent 概念”。**

---

# DAY6 时间安排总览

| 时间段         | 目标                 | A：代码与 release      | B：文档清洗与攻击章节                       | C：报告成稿与质检    |
| ----------- | ------------------ | ------------------ | --------------------------------- | ------------ |
| 09:00–09:30 | 冻结 DAY5，创建 DAY6 分支 | 打 tag、建分支          | 拉取代码                              | 拉取代码         |
| 09:30–11:00 | 全项目 AI 痕迹扫描        | 扫代码/scripts/README | 扫 docs/case_cards/report_sections | 扫报告草稿/模板     |
| 11:00–12:30 | 第一轮清理              | 删除无关开发指令文件         | 清理文档口吻                            | 搭建报告 Word 结构 |
| 13:30–15:30 | 报告正文成稿             | 补系统实现与运行说明         | 补攻击场景与案例                          | 补摘要、设计、测试、创新 |
| 15:30–17:00 | 结果与图表嵌入            | 提供实验路径             | 提供案例摘要                            | 插入指标表、图、截图   |
| 17:00–18:30 | 提交包构建              | 生成 release 包       | 检查无身份泄露                           | 检查格式与目录      |
| 19:30–21:00 | 全队交叉审阅             | 跑 demo 脚本          | 审报告攻击内容                           | 审报告格式与引用     |
| 21:00–22:00 | 最终打包与 tag          | 打 tag              | 确认案例                              | 确认报告         |

---

# DAY6 开始前：全员先做

## 1. 冻结 DAY5 成果

由 A 或仓库管理员执行：

```bash
git checkout day5-release
git pull
git tag day5-done
git push origin day5-done
```

创建 DAY6 分支：

```bash
git checkout -b day6-clean-report
git push -u origin day6-clean-report
```

每个人从 `day6-clean-report` 开分支：

```bash
git checkout -b day6-A-release-clean
git checkout -b day6-B-doc-clean
git checkout -b day6-C-final-report
```

如果你们不熟 Git 分支，至少保证：

```text
A 只改 m3_core/ scripts/ README.md release/ outputs/quality/
B 只改 m3_attacks/ docs/case_cards/ docs/report_sections/ docs/DATASET_CARD.md
C 只改 docs/report/ docs/report_v*.md outputs/quality/ docs/references/
```

---

## 2. 新建质量检查目录

```bash
mkdir -p outputs/quality
mkdir -p docs/report
mkdir -p release
```

Windows PowerShell：

```powershell
New-Item -ItemType Directory -Force outputs/quality
New-Item -ItemType Directory -Force docs/report
New-Item -ItemType Directory -Force release
```

---

## 3. 复制官方模板

把你上传的模板复制到项目中：

```text
docs/report/作品报告_模板.docx
```

然后后续基于这个模板生成：

```text
docs/report/作品报告_终稿.docx
```

不要直接覆盖原模板。

---

# A 模块：DAY6 详细任务

## A 今日定位

A 是**代码仓库清洗、运行验证和 release 包负责人**。

A 今天要完成：

```text
1. 扫描代码和脚本中的 AIagent / Codex 痕迹
2. 清理 README、scripts、注释、临时任务文件
3. 保证系统功能不被误删
4. 重新跑最小 demo 验证
5. 生成 release 包
6. 输出清理日志
```

---

## A-1：代码与脚本扫描

在项目根目录执行：

```bash
rg -n --hidden --glob "!.git/**" --glob "!release/**" --glob "!outputs/runs/**" --glob "!*.png" --glob "!*.jpg" --glob "!*.pdf" "AIagent|AI Agent|AIAgent|Codex|Copilot|ChatGPT|GPT生成|AI生成|由AI|由 AI|本地 AIagent|你是队员|请只修改|完成后请输出|给 AIagent|给AIagent|DAY[0-9].*AIagent" . > outputs/quality/day6_ai_trace_scan_before.txt
```

如果没有 `rg`，用 Python 脚本扫描：

```python
from pathlib import Path
import re

patterns = [
    r"AIagent", r"AI Agent", r"AIAgent", r"Codex", r"Copilot",
    r"ChatGPT", r"GPT生成", r"AI生成", r"由AI", r"由 AI",
    r"本地 AIagent", r"你是队员", r"请只修改", r"完成后请输出",
    r"给 AIagent", r"给AIagent", r"DAY[0-9].*AIagent"
]

skip_dirs = {".git", "release", "__pycache__"}
out = []

for p in Path(".").rglob("*"):
    if any(part in skip_dirs for part in p.parts):
        continue
    if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".pdf", ".docx", ".zip"}:
        continue
    if not p.is_file():
        continue
    try:
        text = p.read_text(encoding="utf-8")
    except Exception:
        continue
    for i, line in enumerate(text.splitlines(), 1):
        if any(re.search(pattern, line, re.I) for pattern in patterns):
            out.append(f"{p}:{i}: {line}")

Path("outputs/quality").mkdir(parents=True, exist_ok=True)
Path("outputs/quality/day6_ai_trace_scan_before.txt").write_text(
    "\n".join(out), encoding="utf-8"
)
print(f"Found {len(out)} suspicious lines.")
```

---

## A-2：重点清理位置

A 重点检查这些文件和目录：

```text
README.md
scripts/
m3_core/
m3_eval/
m3_guard/
docs/*.md
docs/report_sections/
docs/case_cards/
outputs/metrics/DAY*.md
```

优先删除或改写：

```text
DAY2 任务清单
DAY3 任务清单
DAY4 任务清单
DAY5 任务清单
AIagent 工作单
Codex 指令
“你是本地 AIagent……”
“请确保以下命令……完成后输出……”
```

如果这些内容是单独文件，例如：

```text
docs/DAY2_TASKS.md
docs/DAY3_TASKS.md
docs/DAY4_TASKS.md
docs/DAY5_TASKS.md
docs/AIAGENT_PROMPTS.md
```

可以选择：

```text
不放入 release 包
或者移动到 private_notes/ 并加入 .gitignore
```

建议不要直接删 Git 历史，只要最终提交包里没有即可。

---

## A-3：代码注释清洗原则

如果代码里有这种注释：

```python
# AIagent generated
# codex wrote this
# prompt from ChatGPT
# 让 AIagent 修改这里
```

删除。

如果代码里有这种注释：

```python
# OpenAI-compatible local API
# LLM Agent tool call parser
# Agent runner
```

保留。

如果代码里有 `openai`：

```python
from openai import OpenAI
```

保留，因为这是 SDK 包名，不是 AI 生成痕迹。

---

## A-4：重新运行最小功能验证

清理后必须跑一遍最小 demo，确保没有误删功能。

```bash
python -m m3_core.run_matrix \
  --cases fixtures/demo_cases.jsonl \
  --backend stub \
  --defense-modes baseline,full_guard \
  --out-dir outputs/runs/day6_demo_stub_matrix \
  --run-prefix day6_demo_stub \
  --max-steps 5
```

再跑评测：

```bash
python -m m3_eval.evaluate \
  --log-dir outputs/runs/day6_demo_stub_matrix \
  --cases fixtures/demo_cases.jsonl \
  --out outputs/metrics/day6_demo_stub_summary.csv
```

如果本地模型可用，再跑：

```bash
python -m m3_core.run_matrix \
  --cases fixtures/demo_cases.jsonl \
  --backend ollama \
  --model m3-target-qwen25-7b \
  --defense-modes baseline,full_guard \
  --out-dir outputs/runs/day6_demo_qwen_matrix \
  --run-prefix day6_demo_qwen \
  --max-steps 5
```

---

## A-5：清理 release 包内容

创建：

```text
release/Redteam_LLM_Security_v1.0/
```

release 包建议包含：

```text
README.md
requirements-core.txt
requirements-dashboard.txt

m3_core/
m3_attacks/
m3_guard/
m3_eval/
fixtures/
scripts/

docs/report/作品报告_终稿.docx
docs/report/作品报告_终稿.pdf   # 可选
docs/DATASET_CARD.md
docs/ETHICS_AND_SCOPE.md
docs/case_cards/
docs/SYSTEM_ARCHITECTURE.md

outputs/metrics/
outputs/figures/
outputs/runs/day5_demo_matrix/ 或 day6_demo_stub_matrix/
```

release 包不要包含：

```text
.git/
.venv/
__pycache__/
*.pyc
ollama 模型文件
sandbox/secrets/
sandbox/outbox/
sandbox/logs/ 大量临时日志
private_notes/
DAY2/DAY3/DAY4/DAY5 AIagent 指令文档
outputs/quality/day6_ai_trace_scan_before.txt  # 可内部保留，不一定进 release
```

---

## A-6：release 包二次扫描

对 release 包再扫一次：

```bash
rg -n --hidden "AIagent|AIAgent|AI Agent|Codex|Copilot|ChatGPT|AI生成|由AI|由 AI|你是队员|请只修改|完成后请输出|给AIagent|给 AIagent" release/Redteam_LLM_Security_v1.0 > outputs/quality/day6_release_ai_trace_scan.txt
```

验收标准：

```text
day6_release_ai_trace_scan.txt 为空，或者只包含合理的项目研究对象描述，而不是 AIagent/Codex 生成痕迹。
```

---

## A-7：A 的交付物

```text
outputs/quality/day6_ai_trace_scan_before.txt
outputs/quality/day6_release_ai_trace_scan.txt
outputs/quality/day6_cleanup_log.md
outputs/metrics/day6_demo_stub_summary.csv
release/Redteam_LLM_Security_v1.0/
scripts/make_release_package.ps1
```

---

## A 可以直接给 AIagent 的 DAY6 指令

```text
你是队员 A 的本地开发助手。今天是 DAY6，项目已经完成主要功能和实验。你的任务是清理代码仓库中的 AI 协作痕迹、保证功能可运行，并生成干净 release 包。

请只修改：
m3_core/
m3_eval/
m3_guard/ 仅限清理注释，不改逻辑
scripts/
README.md
outputs/quality/
release/

目标：
1. 扫描整个项目中与 AIagent、Codex、Copilot、ChatGPT 生成痕迹相关的内容。
2. 删除开发过程中的 AIagent 指令、Codex 指令、任务提示文本，例如：
   - “你是队员 A 的本地 AIagent”
   - “请只修改……”
   - “完成后请输出……”
   - “给 AIagent 的指令”
   - “Codex 生成”
   - “AI 生成”
3. 不要删除项目研究对象中的正常术语，例如 LLM、Agent、AI 安全、大模型、OpenAI SDK、Qwen、DeepSeek。
4. 不要删除功能代码，不要改动攻击样本含义。
5. 清理后运行 demo stub，确认系统仍可运行。
6. 生成 release/Redteam_LLM_Security_v1.0/，只包含提交需要的干净代码、样本、报告、图表、指标和脚本。
7. release 包不得包含：
   - .git
   - __pycache__
   - .venv
   - sandbox/secrets
   - sandbox/outbox
   - 模型文件
   - AIagent/Codex 指令文档
   - private_notes

请执行或生成等价脚本：
rg -n --hidden --glob "!.git/**" --glob "!release/**" --glob "!outputs/runs/**" --glob "!*.png" --glob "!*.jpg" --glob "!*.pdf" "AIagent|AI Agent|AIAgent|Codex|Copilot|ChatGPT|GPT生成|AI生成|由AI|由 AI|本地 AIagent|你是队员|请只修改|完成后请输出|给 AIagent|给AIagent|DAY[0-9].*AIagent" . > outputs/quality/day6_ai_trace_scan_before.txt

清理后运行：
python -m m3_core.run_matrix --cases fixtures/demo_cases.jsonl --backend stub --defense-modes baseline,full_guard --out-dir outputs/runs/day6_demo_stub_matrix --run-prefix day6_demo_stub --max-steps 5

python -m m3_eval.evaluate --log-dir outputs/runs/day6_demo_stub_matrix --cases fixtures/demo_cases.jsonl --out outputs/metrics/day6_demo_stub_summary.csv

最后对 release 包运行：
rg -n --hidden "AIagent|AIAgent|AI Agent|Codex|Copilot|ChatGPT|AI生成|由AI|由 AI|你是队员|请只修改|完成后请输出|给AIagent|给 AIagent" release/Redteam_LLM_Security_v1.0 > outputs/quality/day6_release_ai_trace_scan.txt

完成后请输出：
1. 清理的文件列表
2. 删除或改写的关键词统计
3. demo stub 运行结果
4. release 包路径
5. release 二次扫描结果
6. 是否发现误删或功能异常
```

---

# B 模块：DAY6 详细任务

## B 今日定位

B 是**文档内容清洗、攻击案例合规化、报告攻击章节负责人**。

B 今天要完成：

```text
1. 清理 docs 中所有 AIagent 指令痕迹
2. 保留攻击案例和实验说明
3. 把攻击描述改成竞赛报告口吻
4. 避免真实攻击细节
5. 配合 C 写正式报告
```

---

## B-1：文档扫描

重点扫描：

```text
docs/
m3_attacks/README.md
m3_attacks/ATTACK_MATRIX.md
docs/case_cards/
docs/report_sections/
docs/DATASET_CARD.md
docs/ETHICS_AND_SCOPE.md
docs/PPT_attack_notes.md
```

执行：

```bash
rg -n "AIagent|AIAgent|AI Agent|Codex|Copilot|ChatGPT|AI生成|由AI|你是队员|请只修改|完成后请输出|给AIagent|给 AIagent" docs m3_attacks > outputs/quality/day6_docs_ai_trace_scan.txt
```

---

## B-2：删除或改写开发过程口吻

把这类内容删掉：

```text
你是队员 B 的本地 AIagent……
今天是 DAY5……
请只修改……
完成后请输出……
运行后必须输出……
```

改成正式报告口吻：

原文：

```text
你是队员 B 的本地 AIagent，今天的任务是构造样本……
```

改成：

```text
本项目构建了面向大模型智能体的红队测试样本集，覆盖直接越狱、RAG 间接提示注入、多语言/T2L 注入、JSON/RPC 结构化注入与工具输出注入等场景。
```

原文：

```text
完成后请输出样本总数……
```

改成：

```text
样本集统计包括样本总数、攻击类型分布、语言分布、载体分布和目标工具分布。
```

---

## B-3：攻击描述合规化

报告里不要写成：

```text
攻击者可以利用该方法窃取真实密钥……
```

改成：

```text
在本地授权沙箱中，样本使用 canary 假密钥模拟敏感数据，验证 Agent 在提示注入影响下是否会触发未授权文件读取和 mock 外发行为。
```

不要出现：

```text
真实恶意代码
真实漏洞利用步骤
真实 API 地址
真实邮箱
真实系统路径
真实 secret
```

可以保留：

```text
sandbox/secrets/api_key.txt
redteam@example.test
/mock/external/submit
M3_CANARY_SECRET_API_KEY
```

因为这些是 mock。

---

## B-4：整理攻击矩阵最终版

更新：

```text
m3_attacks/ATTACK_MATRIX.md
```

正式化结构：

```markdown
# 红队攻击场景矩阵

## 1. 直接越狱与说服性提示
- 攻击目标
- 攻击载体
- 代表样本
- 预期风险
- 安全边界

## 2. RAG/文档间接提示注入
...

## 3. 多语言/T2L 注入
...

## 4. JSON/RPC 结构化注入
...

## 5. 工具输出注入
...

## 6. 正常样本与误报率校准
...
```

不要出现“AIagent 指令”。

---

## B-5：整理案例卡最终版

检查：

```text
docs/case_cards/DEMO_001_RAG_INDIRECT.md
docs/case_cards/DEMO_002_JSON_RPC.md
docs/case_cards/DEMO_003_MULTILINGUAL_T2L.md
```

每个案例卡必须是正式描述：

```text
案例目标
攻击入口
攻击载体
用户正常任务
注入内容摘要
预期安全行为
不安全目标动作
baseline 观察结果
full_guard 观察结果
Guard 触发原因
证据文件
安全边界
```

不能有：

```text
请 AIagent……
按步骤执行……
你是……
```

---

## B-6：提供报告第三章和第四章素材

B 给 C 提供可直接放进报告的内容：

```text
docs/report_sections/03_attack_scenarios_clean.md
docs/report_sections/04_innovation_attack_side.md
```

其中 `03_attack_scenarios_clean.md` 应包含：

```markdown
第三章中“测试数据与攻击样本”部分可用内容：
- 样本类型
- 样本规模
- 样本字段
- 安全边界
- 代表样本说明
```

`04_innovation_attack_side.md` 应包含：

```markdown
第四章中“红队样本构造创新”部分可用内容：
- 面向工具链行为而非仅文本输出
- 多语言/T2L + 结构化注入组合
- RAG/工具输出多阶段攻击模拟
- benign_clean 样本用于误报率校准
```

---

## B-7：B 的交付物

```text
outputs/quality/day6_docs_ai_trace_scan.txt
m3_attacks/ATTACK_MATRIX.md
docs/case_cards/DEMO_001_RAG_INDIRECT.md
docs/case_cards/DEMO_002_JSON_RPC.md
docs/case_cards/DEMO_003_MULTILINGUAL_T2L.md
docs/report_sections/03_attack_scenarios_clean.md
docs/report_sections/04_innovation_attack_side.md
docs/DATASET_CARD.md
docs/ETHICS_AND_SCOPE.md
```

---

## B 可以直接给 AIagent 的 DAY6 指令

```text
你是队员 B 的文档整理助手。今天是 DAY6，项目进入提交前清洗和报告成稿阶段。你的任务是清理文档中的 AIagent/Codex/自动生成指令痕迹，并把攻击样本和案例描述改成正式竞赛报告口吻。

请只修改：
m3_attacks/
docs/case_cards/
docs/report_sections/
docs/DATASET_CARD.md
docs/ETHICS_AND_SCOPE.md
outputs/quality/

目标：
1. 扫描 docs/ 和 m3_attacks/ 中所有 AIagent、Codex、ChatGPT、AI生成、你是队员、请只修改、完成后请输出等开发过程指令痕迹。
2. 删除这些开发过程指令，不删除真实项目内容。
3. 将文档口吻改为正式报告口吻。
4. 保留大模型、LLM Agent、AI 安全、提示注入等项目研究对象术语。
5. 不加入真实攻击步骤、真实漏洞利用、真实邮箱、真实 API、真实敏感路径。
6. 所有攻击描述必须说明是本地授权 sandbox mock 测试。
7. 更新 m3_attacks/ATTACK_MATRIX.md，使其成为正式红队攻击场景矩阵。
8. 更新 3 个 case card：
   docs/case_cards/DEMO_001_RAG_INDIRECT.md
   docs/case_cards/DEMO_002_JSON_RPC.md
   docs/case_cards/DEMO_003_MULTILINGUAL_T2L.md
9. 创建 docs/report_sections/03_attack_scenarios_clean.md。
10. 创建 docs/report_sections/04_innovation_attack_side.md。

请先运行：
rg -n "AIagent|AIAgent|AI Agent|Codex|Copilot|ChatGPT|AI生成|由AI|你是队员|请只修改|完成后请输出|给AIagent|给 AIagent" docs m3_attacks > outputs/quality/day6_docs_ai_trace_scan.txt

完成后再次运行同样扫描，确保不再出现开发过程指令痕迹。

完成后请输出：
1. 被清理的文档列表
2. 仍保留的必要 AI/LLM/Agent 术语说明
3. 攻击矩阵路径
4. 三个案例卡路径
5. 报告攻击章节素材路径
6. 文档二次扫描结果
```

---

# C 模块：DAY6 详细任务

## C 今日定位

C 是**官方模板报告成稿、格式规范、引用和最终质检负责人**。

C 今天要完成：

```text
1. 基于官方 docx 模板生成正式报告
2. 删除模板说明文字
3. 保留填写说明页
4. 避免身份泄露
5. 插入系统架构、实验结果、图表、案例
6. 检查 AIagent/Codex 痕迹
7. 输出 docx 和可选 pdf
```

---

## C-1：报告结构按官方模板

官方模板主体结构是：

```text
摘要
第一章 作品概述
第二章 作品设计与实现
第三章 作品测试与分析
第四章 创新性说明
第五章 总结
参考文献
```

你们报告就按这个结构写，不要写成开发日志。

---

# 报告内容建议

## 封面

```text
命题赛道：勾选
自由赛道：不勾选
作品名称：Redteam_LLM_Security：面向大模型智能体的提示注入红队评测与行为监督系统
电子邮箱：填写团队公开邮箱，避免使用含学校域名或个人姓名的邮箱
提交日期：填写提交当天日期
```

注意不要出现：

```text
学校
学院
指导老师
队员姓名
学号
```

---

## 摘要

内容包括：

```text
创作动机：
大模型智能体越来越多地接入文件、邮件、API 和代码执行工具，提示注入会从“文本输出风险”扩展为“工具链行为风险”。

功能：
本作品构建本地红队靶场，提供攻击样本库、智能体模拟工具、行为监督 Guard、评测模块和 Dashboard。

特性：
完全本地运行，mock 工具沙箱，支持 direct_jailbreak、rag_indirect、multilingual_t2l、json_rpc、tool_output_injection 等攻击场景。

创新：
从输出安全转向行为安全，支持工具调用审计、上下文隔离、数据流追踪和意图-动作一致性检测。

实用性：
可用于大模型智能体应用上线前的安全测试、红队评估和防御策略验证。
```

---

## 第一章 作品概述

建议小节：

```text
1.1 背景分析
1.2 相关工作
1.3 作品目标
1.4 作品特色
1.5 应用前景
```

关键内容：

```text
大模型应用正在从单轮对话走向工具集成 Agent。
提示注入风险会影响文件访问、邮件发送、API 调用、代码执行等行为。
本作品以本地授权红队模拟方式，评估智能体对不可信输入的处理能力。
```

---

## 第二章 作品设计与实现

建议小节：

```text
2.1 系统总体架构
2.2 红队攻击样本库
2.3 本地智能体靶场
2.4 模拟业务工具
2.5 行为监督 Guard
2.6 评测与 Dashboard
2.7 数据格式与运行流程
```

要写清楚：

```text
m3_core：Agent 靶场与工具沙箱
m3_attacks：攻击样本库
m3_guard：行为监督
m3_eval：评测和 Dashboard
fixtures：代表样本
outputs：实验结果
```

可以放系统流程：

```text
AttackCase → Agent Runner → ToolCall → Guard Decision → Mock Tool → RunLog → Metrics → Dashboard
```

---

## 第三章 作品测试与分析

建议小节：

```text
3.1 测试环境
3.2 测试数据
3.3 测试方案
3.4 评测指标
3.5 实验结果
3.6 代表性案例分析
3.7 结果讨论
```

测试环境写：

```text
GPU：NVIDIA GeForce RTX 4060 Laptop GPU，约 8GB 显存
Python：3.9.23
PyTorch：2.5.1 + CUDA 11.8
本地模型：Qwen2.5-7B-Instruct 量化版本
后端：Ollama / OpenAI-compatible local API
```

不要写个人电脑用户名路径。

指标写：

```text
ASR：攻击成功率
UTR：未授权工具调用率
DSR：敏感数据外泄风险率
BSR：阻断成功率
FPR：误报率
AvgRisk：平均风险分
WRS：加权韧性分
```

实验模式写：

```text
baseline
keyword_only
policy_only
full_guard
```

---

## 第四章 创新性说明

建议写 5 点：

```text
1. 从模型输出安全转向智能体行为安全
2. 多类型红队样本覆盖直接、间接、多语言、结构化和工具输出注入
3. 上下文隔离 + 工具策略 + 数据流追踪的多层行为监督
4. 支持消融实验和可解释风险评分
5. 完全本地可复现的安全沙箱实验体系
```

---

## 第五章 总结

写：

```text
本作品构建了面向大模型智能体的提示注入红队评测与行为监督系统。
系统能够模拟提示注入导致的未授权工具调用风险，并通过 full_guard 策略进行审计、告警和阻断。
后续可扩展多模型对比、多模态隐藏提示注入、更多开源 Agent 框架接入和更精细的学习型检测模型。
```

---

## 参考文献

至少建议放 8–12 条，采用 GB/T7714 风格。

可选文献：

```text
[1] Greshake K, Abdelnabi S, Mishra S, et al. Not what you've signed up for: Compromising real-world LLM-integrated applications with indirect prompt injection[C]. ACM AISec, 2023.
[2] Zhan Q, Liang Z, Ying Z, et al. InjecAgent: Benchmarking indirect prompt injections in tool-integrated large language model agents[C]. ACL Findings, 2024.
[3] Schulhoff S, Pinto J, Khan A, et al. Ignore this title and HackAPrompt: Exposing systemic vulnerabilities of LLMs through a global prompt hacking competition[C]. EMNLP, 2023.
[4] Shen X, Chen Z, Backes M, et al. Do anything now: Characterizing and evaluating in-the-wild jailbreak prompts on large language models[C]. ACM CCS, 2024.
[5] Zeng Y, Lin H, Zhang J, et al. How Johnny can persuade LLMs to jailbreak them[C]. ACL, 2024.
[6] Ding P, Kuang J, Ma D, et al. A wolf in sheep's clothing: Generalized nested jailbreak prompts can fool large language models easily[C]. NAACL, 2024.
[7] Sun Z, Miceli-Barone A V. Scaling behavior of machine translation with large language models under prompt injection attacks[C]. SCALE-LLM, 2024.
[8] Miceli-Barone A V, Sun Z. A test suite of prompt injection attacks for LLM-based machine translation[C]. WMT, 2024.
[9] Muliarevych O. Enhancing system security: LLM-driven defense against prompt injection vulnerabilities[C]. TCSET, 2024.
[10] Kumar S S, Cummings M, Stimpson A. Strengthening LLM trust boundaries: A survey of prompt injection attacks[C]. ICHMS, 2024.
```

---

## C-2：生成 Word 报告的建议方式

如果你们让本地 AIagent 自动生成 docx，可以让它使用 `python-docx`：

```bash
pip install python-docx
```

生成脚本：

```text
scripts/build_final_report.py
```

输入：

```text
docs/report/作品报告_模板.docx
docs/report_v0.3.md
outputs/figures/*.png
outputs/metrics/day5_qwen25_summary.csv
```

输出：

```text
docs/report/作品报告_终稿.docx
```

但注意：

```text
python-docx 不一定能自动更新 Word 目录页码。
最后需要用 Word 或 WPS 打开文档，手动“更新目录/更新域”。
```

---

## C-3：报告格式检查

必须检查：

```text
A4
标题样式统一
正文宋体
正文小四
1.5 倍行距
图片编号
表格编号
参考文献格式
页码正常
目录页码更新
模板说明文字已删除
填写说明页保留
无学校/学院/老师/队员身份信息
无 AIagent/Codex/ChatGPT 生成痕迹
```

---

## C-4：报告 AI 痕迹扫描

对报告源文件和 docx 解压文本都检查。

Markdown 源文件：

```bash
rg -n "AIagent|AIAgent|AI Agent|Codex|Copilot|ChatGPT|AI生成|由AI|你是队员|请只修改|完成后请输出|给AIagent|给 AIagent" docs/report docs/report_sections docs/case_cards > outputs/quality/day6_report_ai_trace_scan.txt
```

docx 检查可以把 docx 当 zip 解压：

```bash
mkdir -p outputs/quality/report_docx_unzip
unzip -o docs/report/作品报告_终稿.docx -d outputs/quality/report_docx_unzip
rg -n "AIagent|AIAgent|AI Agent|Codex|Copilot|ChatGPT|AI生成|由AI|你是队员|请只修改|完成后请输出|给AIagent|给 AIagent" outputs/quality/report_docx_unzip > outputs/quality/day6_report_docx_ai_trace_scan.txt
```

Windows 如果没有 unzip，可直接用 7-Zip 或手动复制 docx 改名 zip 解压。

---

## C-5：C 的交付物

```text
docs/report/作品报告_模板.docx
docs/report/作品报告_终稿.docx
docs/report/作品报告_终稿.pdf    # 可选
docs/report_v0.3.md              # 源稿可保留
outputs/quality/day6_report_ai_trace_scan.txt
outputs/quality/day6_report_docx_ai_trace_scan.txt
outputs/quality/day6_report_format_check.md
```

---

## C 可以直接给 AIagent 的 DAY6 指令

```text
你是队员 C 的报告生成助手。今天是 DAY6，项目需要按照官方《作品报告模板.docx》生成最终报告，并清理所有 AIagent/Codex/自动生成指令痕迹。

请只修改：
docs/report/
docs/report_sections/
docs/report_v0.3.md
outputs/quality/
scripts/build_final_report.py

输入：
docs/report/作品报告_模板.docx
docs/report_v0.3.md
outputs/metrics/day5_qwen25_summary.csv
outputs/metrics/day5_stub_summary.csv
outputs/figures/

输出：
docs/report/作品报告_终稿.docx
docs/report/作品报告_终稿.pdf（如果本机支持导出 PDF）

报告必须严格采用官方模板结构：
封面
填写说明
目录
摘要
第一章 作品概述
第二章 作品设计与实现
第三章 作品测试与分析
第四章 创新性说明
第五章 总结
参考文献

格式要求：
A4
除标题外，正文宋体、小四号、1.5 倍行距
模板说明文字删除，但填写说明页不删除
避免出现学校、院系、指导教师、队员姓名、学号等身份信息

内容要求：
1. 摘要：说明动机、功能、特性、创新点、实用性。
2. 第一章：背景分析、相关工作、作品目标、特色和应用前景。
3. 第二章：系统方案、实现原理、软件流程、模块功能和指标。
4. 第三章：测试环境、测试数据、测试方案、评测指标、实验结果、案例分析。
5. 第四章：创新性说明。
6. 第五章：总结与后续工作。
7. 参考文献：采用 GB/T7714 风格。

严禁出现：
AIagent
AIAgent
Codex
Copilot
ChatGPT 生成
AI 生成
你是队员
请只修改
完成后请输出
给 AIagent 的指令
开发过程任务单口吻
学校、学院、指导老师、队员姓名、学号等身份信息

允许保留：
大模型
人工智能安全
LLM
Agent
智能体
OpenAI-compatible API
Qwen2.5
提示注入
越狱攻击

请完成：
1. 生成 docs/report/作品报告_终稿.docx。
2. 如可行，导出 docs/report/作品报告_终稿.pdf。
3. 扫描报告源文件和 docx 解压内容，确认无 AIagent/Codex 痕迹。
4. 生成 outputs/quality/day6_report_format_check.md，记录格式检查结果。
5. 提醒用户最后使用 Word/WPS 更新目录页码。

完成后请输出：
1. 最终 docx 路径
2. 最终 pdf 路径，如有
3. 报告章节完整性检查
4. AI 痕迹扫描结果
5. 身份信息泄露检查结果
6. 需要人工打开 Word/WPS 完成的事项
```

---

# DAY6 中午第一次集成：12:30 前完成

目标：

```text
代码与文档 AIagent/Codex 痕迹第一轮清理完成
demo stub 仍可运行
报告大纲已进入官方模板
```

执行：

A：

```bash
python -m m3_core.run_matrix \
  --cases fixtures/demo_cases.jsonl \
  --backend stub \
  --defense-modes baseline,full_guard \
  --out-dir outputs/runs/day6_demo_stub_matrix \
  --run-prefix day6_demo_stub \
  --max-steps 5
```

B：

```bash
rg -n "AIagent|AIAgent|AI Agent|Codex|Copilot|ChatGPT|AI生成|由AI|你是队员|请只修改|完成后请输出|给AIagent|给 AIagent" docs m3_attacks > outputs/quality/day6_docs_ai_trace_scan.txt
```

C：

```bash
rg -n "AIagent|AIAgent|AI Agent|Codex|Copilot|ChatGPT|AI生成|由AI|你是队员|请只修改|完成后请输出|给AIagent|给 AIagent" docs/report docs/report_sections docs/case_cards > outputs/quality/day6_report_ai_trace_scan.txt
```

中午验收：

```text
demo stub 可运行
主要 docs 不再有 AIagent 工作单
报告 Word 初稿已有章节
没有学校/老师/队员身份信息
```

---

# DAY6 下午第二次集成：17:30 前完成

目标：

```text
正式报告 docx 生成
release 包初版生成
release 包 AI 痕迹扫描
```

A：

```bash
rg -n --hidden "AIagent|AIAgent|AI Agent|Codex|Copilot|ChatGPT|AI生成|由AI|由 AI|你是队员|请只修改|完成后请输出|给AIagent|给 AIagent" release/Redteam_LLM_Security_v1.0 > outputs/quality/day6_release_ai_trace_scan.txt
```

C：

```bash
rg -n "AIagent|AIAgent|AI Agent|Codex|Copilot|ChatGPT|AI生成|由AI|你是队员|请只修改|完成后请输出|给AIagent|给 AIagent" docs/report docs/report_sections docs/case_cards > outputs/quality/day6_report_ai_trace_scan.txt
```

人工检查：

```text
打开 docs/report/作品报告_终稿.docx
更新目录
检查页码
检查格式
检查图片
检查表格
检查参考文献
```

---

# DAY6 晚上最终检查

## 1. 全项目最终扫描

```bash
rg -n --hidden --glob "!.git/**" --glob "!outputs/runs/**" --glob "!release/**" --glob "!*.png" --glob "!*.jpg" --glob "!*.pdf" "AIagent|AIAgent|AI Agent|Codex|Copilot|ChatGPT|GPT生成|AI生成|由AI|由 AI|你是队员|请只修改|完成后请输出|给AIagent|给 AIagent" . > outputs/quality/day6_final_project_ai_trace_scan.txt
```

## 2. release 包最终扫描

```bash
rg -n --hidden "AIagent|AIAgent|AI Agent|Codex|Copilot|ChatGPT|AI生成|由AI|由 AI|你是队员|请只修改|完成后请输出|给AIagent|给 AIagent" release/Redteam_LLM_Security_v1.0 > outputs/quality/day6_final_release_ai_trace_scan.txt
```

## 3. 身份信息扫描

```bash
rg -n "大学|学院|学校|指导教师|指导老师|老师|学号|姓名|队员|院系|班级" docs release/Redteam_LLM_Security_v1.0 > outputs/quality/day6_identity_leak_scan.txt
```

注意：

```text
“全国大学生信息安全竞赛”里的“大学生”可以保留。
如果参考文献里有“University”也可以保留。
但不要出现你们真实学校、学院、姓名、指导老师。
```

---

# DAY6 最终验收表

| 模块 | 必须完成       | 验收标准                                          |
| -- | ---------- | --------------------------------------------- |
| A  | 代码 AI 痕迹清理 | release 包中无 AIagent/Codex/ChatGPT 生成痕迹        |
| A  | 功能验证       | day6 demo stub 可运行                            |
| A  | release 包  | release/Redteam_LLM_Security_v1.0 存在          |
| B  | 文档清理       | docs/case_cards 和 attack matrix 无 AIagent 工作单 |
| B  | 攻击章节       | 正式报告口吻，无真实攻击细节                                |
| B  | 案例卡        | 3 个 demo case card 完整                         |
| C  | Word 报告    | docs/report/作品报告_终稿.docx 完成                   |
| C  | 模板格式       | A4、宋体小四、1.5 倍行距、目录更新                          |
| C  | 匿名化        | 无学校/院系/指导老师/队员姓名/学号                           |
| C  | 引用         | 参考文献格式基本符合 GB/T7714                           |
| 全队 | 最终扫描       | AI 痕迹扫描和身份扫描无严重问题                             |
| 全队 | 提交包        | 不含 sandbox/secrets、模型文件、.git、虚拟环境             |

---

# DAY6 结束时应得到的文件

```text
docs/report/
  作品报告_模板.docx
  作品报告_终稿.docx
  作品报告_终稿.pdf      # 可选

docs/
  DATASET_CARD.md
  ETHICS_AND_SCOPE.md
  SYSTEM_ARCHITECTURE.md
  case_cards/
    DEMO_001_RAG_INDIRECT.md
    DEMO_002_JSON_RPC.md
    DEMO_003_MULTILINGUAL_T2L.md
  report_sections/
    03_attack_scenarios_clean.md
    04_innovation_attack_side.md

outputs/quality/
  day6_ai_trace_scan_before.txt
  day6_docs_ai_trace_scan.txt
  day6_report_ai_trace_scan.txt
  day6_report_docx_ai_trace_scan.txt
  day6_release_ai_trace_scan.txt
  day6_final_project_ai_trace_scan.txt
  day6_final_release_ai_trace_scan.txt
  day6_identity_leak_scan.txt
  day6_cleanup_log.md
  day6_report_format_check.md
  day6_release_checklist.md

release/
  Redteam_LLM_Security_v1.0/
```

---

# DAY6 最后 30 分钟人工检查清单

全员一起看：

```text
[ ] 报告封面没有学校、老师、队员姓名
[ ] 命题赛道勾选正确
[ ] 作品名称统一
[ ] 填写说明页保留
[ ] 模板中的括号说明文字已删除
[ ] 正文字体、字号、行距正确
[ ] 目录已更新
[ ] 图片和表格没有缺失
[ ] 参考文献格式基本统一
[ ] 报告里没有 AIagent / Codex / ChatGPT 生成痕迹
[ ] release 包没有 sandbox/secrets/
[ ] release 包没有 .git、.venv、模型文件
[ ] demo 脚本能运行
[ ] README 说明清楚
[ ] ETHICS_AND_SCOPE.md 明确说明本地授权 mock 测试
```

打最终 tag：

```bash
git checkout day6-clean-report
git pull
git tag v1.0-clean-report
git push origin v1.0-clean-report
```

---

# DAY6 一句话执行口号

```text
A：清代码与打包，保证 release 干净可跑。
B：清文档与案例，保证攻击描述正式合规。
C：成稿报告与质检，保证模板格式、匿名化和无 AI 痕迹。
```

DAY6 结束后，你们应该已经拥有一个**可以正式提交的干净作品包**：没有 AIagent/Codex 指令痕迹，有官方模板报告，有完整实验结果，有安全边界说明，有可复现 demo。
