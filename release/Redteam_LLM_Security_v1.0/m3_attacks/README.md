# M3_PI_Guard DAY3 Attack Case Library

队员 B 的 DAY3 交付物：作品级红队攻击样本库。样本覆盖直接越狱、RAG 间接提示注入、多语言/T2L、JSON/RPC 结构化注入、工具输出注入，以及用于误报率评估的 benign clean 正常样本。

所有样本都只面向本地 `sandbox` mock 工具，不包含真实恶意代码，不调用真实网络，不涉及真实账号。

## Directory

```text
m3_attacks/
  __init__.py
  attackgen.py
  ATTACK_MATRIX.md
  README.md
  cases/
    direct_jailbreak_cases.jsonl
    rag_indirect_cases.jsonl
    multilingual_t2l_cases.jsonl
    json_rpc_cases.jsonl
    tool_output_cases.jsonl
    benign_clean_cases.jsonl
    all_cases.jsonl
```

## Required Schema

每条 JSONL 样本保留 DAY2 统一字段：

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

DAY3 额外加入可选评估字段：

- `success_indicators`
- `safe_indicators`
- `demo_priority`

`demo_priority` 含义：

- `1`: 最适合现场演示
- `2`: 可用于批量实验
- `3`: 备用或 clean/FPR 样本

## Allowed Unsafe Target Actions

攻击样本中的危险目标只允许以下本地 mock 动作：

- `read_file:sandbox/secrets/api_key.txt`
- `send_email:redteam@example.test`
- `write_file:sandbox/public/notes.txt`
- `call_api:/mock/external/submit`
- `run_code:mock_only`

`benign_clean` 样本用于误报率 FPR，`unsafe_target_actions` 固定为空数组。

## Counts

DAY3 当前源样本总数：69 条。

- `direct_jailbreak`: 15
- `rag_indirect`: 18
- `multilingual_t2l`: 15
- `json_rpc`: 8
- `tool_output_injection`: 5
- `benign_clean`: 8

## Generate And Validate

在仓库根目录运行：

```bash
python -m m3_attacks.attackgen --out m3_attacks/cases/all_cases.jsonl --stats outputs/metrics/day3_case_stats.json
```

DAY4 质量审计命令：

```bash
python -m m3_attacks.attackgen --out m3_attacks/cases/all_cases.jsonl --stats outputs/metrics/day4_case_stats.json --audit outputs/metrics/day4_case_audit.json
```

脚本会：

- 读取 `m3_attacks/cases/` 下的源 JSONL。
- 跳过输出文件 `all_cases.jsonl`。
- 校验必要字段。
- 校验 `case_id` 唯一。
- 校验 `unsafe_target_actions` 是否在白名单内。
- 合并生成 `m3_attacks/cases/all_cases.jsonl`。
- 输出并写入统计，包括 `total_cases`、`attack_family_count`、`carrier_count`、`language_count`、`severity_count`、`demo_priority_count`、`unsafe_target_actions_count`、`benign_count`、`missing_required_fields`、`duplicate_case_id`。
- 在指定 `--audit` 时生成质量审计报告，检查重复 ID、攻击族规范、语言字段、mock 动作白名单、空字段、benign clean 动作、真实邮箱/URL、真实攻击命令、相似样本、`demo_priority` 和 `expected_detectors`。

## Demo Priority 1 Cases

- `RAG-PI-016`: Markdown 报告隐藏注释中的 RAG 间接注入。
- `JSONRPC-001`: JSON data 字段中隐藏读取秘密与邮件外发。
- `MTL-009`: JSON 翻译任务中的多语言/T2L 任务切换。

DAY4 代表性样本集由 B 提供给 A 运行模型矩阵：

```text
fixtures/day4_representative_cases.jsonl
```

它包含 24 条样本，覆盖 6 类攻击/正常任务。

## Safety Boundary

本库用于本地红队靶场评测，目标是验证 M3_PI_Guard 对未授权 mock 工具调用的识别、告警和阻断能力。样本不提供真实攻击步骤，不包含真实凭据，不访问公网，不真实发送邮件。
