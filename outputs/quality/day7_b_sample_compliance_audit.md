# DAY7 B 样本合规审计摘要

## 审计对象

- `m3_attacks/cases/all_cases.jsonl`
- `fixtures/day4_representative_cases.jsonl`
- `docs/DATASET_CARD.md`
- `m3_attacks/ATTACK_MATRIX.md`
- `docs/case_cards/`

## 样本统计

| attack_family | 数量 |
|---|---:|
| benign_clean | 8 |
| direct_jailbreak | 15 |
| json_rpc | 8 |
| multilingual_t2l | 15 |
| rag_indirect | 18 |
| tool_output_injection | 5 |

总数：69 条。

## 审计结论

- 未发现重复 `case_id`。
- 未发现缺失必要字段。
- 未发现越出本地 mock 白名单的危险目标动作。
- 未发现真实攻击目标。
- 未发现真实邮箱。
- 未发现真实 API 地址。
- 未发现真实凭证。
- 未发现真实恶意代码或真实漏洞利用步骤。

## 代表案例

| case_id | attack_family | 安全边界 |
|---|---|---|
| `RAG-PI-016` | `rag_indirect` | 仅使用 canary secret 与 `.test` mock 邮箱。 |
| `JSONRPC-001` | `json_rpc` | JSON/RPC 内容为静态文本，不连接真实服务。 |
| `MTL-009` | `multilingual_t2l` | 仅诱导本地 notes 写入和 mock API 调用。 |

## 需要保留的说明

样本中出现的 `sandbox/secrets/api_key.txt`、`redteam@example.test`、`/mock/external/submit`、`run_code:mock_only` 均为本地靶场标识，不应作为真实攻击目标理解。
