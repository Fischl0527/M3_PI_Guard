# m3_attacks

`m3_attacks` 是 M3-PI Guard 的本地红队攻击样本库与样本校验工具。样本用于评估大模型智能体在接触不可信输入、结构化任务、跨语言文本和工具返回值时，是否会触发未授权的本地 mock 工具动作。

## 目录结构

```text
m3_attacks/
  __init__.py
  attackgen.py
  ATTACK_MATRIX.md
  README.md
  SAMPLE_REVIEW.md
  cases/
    direct_jailbreak_cases.jsonl
    rag_indirect_cases.jsonl
    multilingual_t2l_cases.jsonl
    json_rpc_cases.jsonl
    tool_output_cases.jsonl
    benign_clean_cases.jsonl
    all_cases.jsonl
    dataset_stats.json
    dataset_audit.json
```

## 样本规模

当前 canonical 数据集为 `cases-v1.0-300`，共 300 条。原有 69 条样本仅作为
`dev` legacy 数据保留；其余样本由固定模板确定性生成。

| attack_family | 数量 |
|---|---:|
| benign_clean | 90 |
| direct_jailbreak | 27 |
| rag_indirect | 30 |
| multilingual_t2l | 27 |
| json_rpc | 20 |
| tool_output_injection | 17 |
| memory_poisoning | 23 |
| environment_context_pollution | 22 |
| cross_tool_attack_chain | 22 |
| obfuscation_evasion | 22 |

攻击样本共 210 条，正常样本共 90 条；正常样本进一步严格平衡为 45 条
无工具任务和 45 条合法工具任务。模板级切分为 `dev=150`、
`validation=60`、`blind=90`，同一 `template_id` 不跨集合。

## 统一字段

每条 JSONL 样本至少包含：

- `case_id`
- `schema_version`
- `sample_type`
- `attack_family`
- `template_id`
- `mutation_id`
- `split`
- `carrier`
- `language`
- `task_type`
- `requires_tool`
- `authorized_actions`
- `user_task`
- `document_content`
- `injected_content`
- `expected_safe_behavior`
- `unsafe_target_actions`
- `risk_tags`
- `severity`
- `notes`

评测扩展字段包括 `success_indicators`、`safe_indicators`、`demo_priority`、
`expected_detectors`、`parent_case_id` 和 `attack_dimensions`。真实模型输入只能使用
`user_task` 与 `document_content`；标签、预期行为和危险目标均为 evaluator-only。

## 本地 mock 动作白名单

样本中的危险目标动作只允许使用以下本地靶场动作：

- `read_file:sandbox/secrets/api_key.txt`
- `send_email:redteam@example.test`
- `write_file:sandbox/public/notes.txt`
- `call_api:/mock/external/submit`
- `run_code:mock_only`

这些动作均由本地 sandbox 或 mock 工具模拟，不访问真实网络，不发送真实邮件，不执行真实恶意代码。

## 生成与审计

在项目根目录运行：

```powershell
python -m m3_attacks.attackgen
```

脚本会读取显式列出的 69 条 legacy sources，补齐元数据并按冻结配额生成 300 条
canonical JSONL，同时输出 `dataset_stats.json` 和 `dataset_audit.json`。审计覆盖
字段完整性、精确数量、ID 唯一性、模板跨 split、授权动作、危险动作、标签字段名
泄漏、真实地址以及跨 split 重复。固定输入重复运行会得到相同数据哈希。

## 演示样本

`demo_priority=1` 的三个样本用于最终演示：

- `RAG-PI-016`：Markdown 报告隐藏注释中的 RAG 间接提示注入。
- `JSONRPC-001`：JSON `data.next_step` 字段中的结构化任务切换。
- `MTL-009`：JSON 翻译任务中的多语言/T2L 工具调用诱导。

对应案例卡位于 `docs/case_cards/`。
