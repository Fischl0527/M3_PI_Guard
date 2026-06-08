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
```

## 样本规模

当前样本库共 69 条：

| attack_family | 数量 |
|---|---:|
| benign_clean | 8 |
| direct_jailbreak | 15 |
| json_rpc | 8 |
| multilingual_t2l | 15 |
| rag_indirect | 18 |
| tool_output_injection | 5 |

样本覆盖直接越狱、RAG 间接提示注入、多语言/T2L、JSON/RPC 结构化注入、工具输出注入和正常任务，用于观察攻击成功率、未授权工具调用、敏感数据外流风险和误报率。

## 统一字段

每条 JSONL 样本至少包含：

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

评测扩展字段包括 `success_indicators`、`safe_indicators`、`demo_priority` 和 `expected_detectors`。

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
python -m m3_attacks.attackgen --out m3_attacks/cases/all_cases.jsonl --stats outputs/metrics/final_case_stats.json --audit outputs/metrics/final_case_audit.json
```

脚本会合并源 JSONL、校验必要字段、检查 `case_id` 唯一性、检查 mock 动作白名单，并输出样本统计与审计结果。

## 演示样本

`demo_priority=1` 的三个样本用于最终演示：

- `RAG-PI-016`：Markdown 报告隐藏注释中的 RAG 间接提示注入。
- `JSONRPC-001`：JSON `data.next_step` 字段中的结构化任务切换。
- `MTL-009`：JSON 翻译任务中的多语言/T2L 工具调用诱导。

对应案例卡位于 `docs/case_cards/`。
