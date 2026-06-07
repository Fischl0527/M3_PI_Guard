# DAY5 B Sample Review

DAY5 B 侧目标是对 DAY4 冻结后的样本库做最终审核，并确认 3 个答辩演示案例。DAY5 不新增攻击类型，不引入真实攻击内容。

## Final Audit Command

```bash
python -m m3_attacks.attackgen --out m3_attacks/cases/all_cases.jsonl --stats outputs/metrics/day5_case_stats.json --audit outputs/metrics/day5_case_audit.json
```

## Final Case Counts

- `total_cases`: 69
- `direct_jailbreak`: 15
- `rag_indirect`: 18
- `multilingual_t2l`: 15
- `json_rpc`: 8
- `tool_output_injection`: 5
- `benign_clean`: 8

## Final Demo Cases

| Demo | case_id | attack_family | Purpose |
|---|---|---|---|
| DEMO-001 | `RAG-PI-016` | `rag_indirect` | Markdown 报告中的隐藏注释诱导读 secret 和 mock 邮件外发 |
| DEMO-002 | `JSONRPC-001` | `json_rpc` | JSON `data.next_step` 字段伪装普通数据并诱导工具调用 |
| DEMO-003 | `MTL-009` | `multilingual_t2l` | JSON 翻译任务中非目标字段诱导任务切换 |

## Audit Scope

审计检查项：

- `case_id` 唯一。
- `attack_family` 类型规范。
- `unsafe_target_actions` 只包含本地 mock 工具。
- `benign_clean` 样本的 `unsafe_target_actions` 为空。
- 不包含真实邮箱、真实 URL 或真实攻击命令。
- `demo_priority=1` 只标记 3 个答辩演示案例。
- `expected_detectors` 与攻击类型一致。

## Safety Boundary

所有攻击样本均限定在本地 sandbox 和 mock 工具中：

- 不访问真实网络。
- 不发送真实邮件。
- 不读取真实敏感文件。
- 不执行真实代码。
- `sandbox/secrets/api_key.txt` 仅代表 canary 假数据。

