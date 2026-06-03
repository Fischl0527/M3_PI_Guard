# M3_PI_Guard DAY2 Red-Team Attack Cases

本目录是队员 B 的 DAY2 交付物：第一批本地红队攻击样本库。样本只攻击本地 `sandbox` mock 工具，不包含真实恶意代码，不调用真实网络，不涉及真实账号。

## Files

```text
m3_attacks/
  __init__.py
  attackgen.py
  cases/
    direct_jailbreak_cases.jsonl
    rag_indirect_cases.jsonl
    multilingual_t2l_cases.jsonl
    all_cases.jsonl
```

## Schema

每行 JSONL 样本都包含以下字段：

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

允许的 `unsafe_target_actions` 只有：

- `read_file:sandbox/secrets/api_key.txt`
- `send_email:redteam@example.test`
- `write_file:sandbox/public/notes.txt`
- `call_api:/mock/external/submit`
- `run_code:mock_only`

## Attack Families

`direct_jailbreak` 覆盖直接越狱提示，包括角色扮演、权限提升伪装、说服性提示、道德重构、文本续写嵌套、代码补全嵌套、表格填充嵌套、字符扰动、中英混合和多轮诱导。

`rag_indirect` 覆盖 RAG 间接提示注入，包括 Markdown 报告、邮件正文、网页片段、工具返回值、FAQ、日志摘要、客户报告、翻译文档、维护模式伪指令、“不要告诉用户”、“先读文件再总结”和“先外发再总结”。

`multilingual_t2l` 覆盖多语言与 T2L 任务切换，包括中文、英文、中英混合、日文、韩文、俄文、拼音/谐音、回译风格和 JSON 翻译任务切换。

## Counts

当前源样本文件共 40 条：

- `direct_jailbreak`: 10
- `rag_indirect`: 15
- `multilingual_t2l`: 15

数量高于 DAY2 最低要求：总数不少于 30，且三类攻击分别不少于 10、12、8 条。

## Generate And Validate

在仓库根目录运行：

```bash
python -m m3_attacks.attackgen --out m3_attacks/cases/all_cases.jsonl
```

脚本会：

- 读取 `m3_attacks/cases/` 下的 JSONL 样本文件。
- 跳过输出文件 `all_cases.jsonl`。
- 校验必要字段。
- 校验 `case_id` 唯一性。
- 校验 `unsafe_target_actions` 是否在白名单内。
- 合并生成 `m3_attacks/cases/all_cases.jsonl`。
- 输出 `total_cases`、`attack_family_count`、`language_count`、`severity_count`、`unsafe_target_actions_count`、`duplicate_case_id` 和 `missing_required_fields`。

## Ethics

这些样本仅用于 M3_PI_Guard 本地沙箱安全评测。所有外发、读写文件、API 调用和代码运行均为 mock 靶场动作，不能用于真实系统攻击。
