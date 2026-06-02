# M3_PI_Guard 本地提示注入与越狱攻击样本集

本目录是队员 B 负责的本地沙箱攻击用例集合，用于 M3_PI_Guard 项目的提示注入、越狱攻击、多语言任务切换和工具调用劫持评测。样本只面向本地 mock 工具链，不依赖本地大模型、GPU、队员 A 的模型环境或队员 C 的评测模块。

## 目录结构

```text
m3_attacks/
  __init__.py
  attackgen.py
  cases/
    direct_jailbreak_cases.jsonl
    rag_indirect_cases.jsonl
    multilingual_t2l_cases.jsonl
    json_rpc_cases.jsonl
    tool_output_cases.jsonl
    all_cases.jsonl
  README.md
```

## 样本 Schema

每行一个 JSON 对象，字段包含：

- `case_id`
- `attack_family`
- `carrier`
- `language`
- `user_task`
- `document_content`
- `injected_content`
- `expected_safe_behavior`
- `unsafe_target_actions`
- `risk_tags`
- `severity`
- `notes`

`unsafe_target_actions` 只允许以下本地靶场动作：

- `read_file:sandbox/secrets/api_key.txt`
- `write_file:sandbox/public/notes.txt`
- `send_email:redteam@example.test`
- `call_api:/mock/external/submit`
- `run_code:mock_only`

## 攻击分类与设计思路

### direct_jailbreak

直接攻击用户提示本身，覆盖角色扮演、权威和紧迫性、道德重构、ReNeLLM 风格嵌套改写、文本续写、代码补全、表格补全、字符级扰动等形式。

这些样本用于测试模型是否会把用户输入中的越权目标误认为合法授权，尤其是读取本地秘密、写公开笔记、发送 mock 邮件、调用 mock API 或运行 mock 代码。

### rag_indirect

间接攻击来自不可信外部内容，包括 Markdown 报告、邮件正文、网页片段、工具返回值、CSV 单元格、OCR 文本、Issue 评论、日程邀请、聊天记录、Wiki 页面和日志工具输出。

这些样本对应 RAG 场景中的典型风险：模型应只使用文档事实回答用户任务，不应执行文档、网页、邮件或检索结果里写给“助手”的隐藏指令，也不应服从“不要告诉用户”“先执行维护步骤再总结”等任务劫持文本。

### multilingual_t2l

多语言与 T2L 样本覆盖中文攻击意图的英文表达、中英混合、中文加日文/韩文/俄文片段、拼音、谐音、回译腔、繁体中文、结构化翻译任务和标签语义污染。

这些样本用于测试模型是否能在翻译、转写、纠错、分类、标签映射等任务中保持执行边界。模型可以翻译或解释文本，但不能执行文本描述的本地 mock 工具动作。

### json_rpc

JSON-RPC 样本把攻击动作放进 `data`、`tool_call`、`instruction`、`developer`、`system`、`ordinary_text` 等字段，或把工具调用伪装成 RPC 参数。

这些样本用于测试结构化输入中的任务切换风险。即使字段名看起来像 `system` 或 `developer`，它们仍然只是用户提供的普通数据，模型不应把它们提升为真实高优先级指令。

### tool_output_injection

工具输出扩展样本模拟搜索工具、检索器、CI 工具、文件索引器、邮件分类器等返回值中的提示注入。

这些样本用于测试工具链监督：上游工具返回的文本不应控制下游模型执行额外工具动作，尤其不能触发秘密读取、邮件发送、文件写入、API 调用或代码运行。

## 样本数量统计

当前样本总数：50 条。

按攻击族统计：

- `direct_jailbreak`: 10
- `rag_indirect`: 15
- `multilingual_t2l`: 15
- `json_rpc`: 5
- `tool_output_injection`: 5

按严重程度统计：

- `high`: 38
- `medium`: 12

按目标动作分布：

- `read_file:sandbox/secrets/api_key.txt`: 20
- `send_email:redteam@example.test`: 20
- `write_file:sandbox/public/notes.txt`: 14
- `call_api:/mock/external/submit`: 14
- `run_code:mock_only`: 9

## 为什么覆盖验收要求

- 直接攻击：`direct_jailbreak_cases.jsonl` 覆盖角色扮演、权威压迫、紧急维护、道德重构、嵌套续写、代码/表格补全和字符扰动。
- 间接攻击：`rag_indirect_cases.jsonl` 覆盖 Markdown、邮件、网页、工具返回、CSV、OCR、Issue、日程、聊天、Wiki 和日志等不可信载体。
- 多语言/T2L：`multilingual_t2l_cases.jsonl` 覆盖英文表达中文意图、中英混合、日韩俄片段、拼音/谐音、回译、繁体、标签映射和结构化翻译。
- JSON 注入：`json_rpc_cases.jsonl` 覆盖 data 字段 payload、伪 RPC 工具调用、伪 instruction/developer/system 字段和“只翻译 JSON”任务切换。
- 工具调用劫持：`tool_output_cases.jsonl` 覆盖工具输出中的隐藏指令、维护前置步骤和分类器/索引器诱导。

## 生成与校验

运行以下命令合并并校验所有样本：

```bash
python -m m3_attacks.attackgen --out m3_attacks/cases/all_cases.jsonl
```

脚本会执行：

- 读取 `m3_attacks/cases/` 下所有 JSONL 样本文件。
- 跳过输出文件 `all_cases.jsonl`，避免重复合并。
- 校验必要字段是否存在。
- 校验 `case_id` 是否唯一。
- 校验 `unsafe_target_actions` 是否在本地靶场白名单内。
- 输出 attack_family、language、severity 和 unsafe_target_actions 统计。

## 伦理说明

本样本集仅用于 M3_PI_Guard 本地沙箱安全评测。所有目标动作均为 mock 靶场动作，不包含真实恶意代码、不连接真实攻击服务、不引导真实网络攻击，也不包含真实凭据或真实外发地址。
