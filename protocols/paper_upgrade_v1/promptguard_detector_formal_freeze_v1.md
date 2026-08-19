# PromptGuard detector formal freeze v1

- Status: `frozen_pre_run`
- Created: `2026-07-20T15:59:56.820747+00:00`
- Freeze version: `m3-paper-v1-promptguard-detector-formal-freeze-1.0`
- Cases: `3280`
- Inputs SHA-256: `19adbfabd5c328238633af9c40ad1d41c04fd28e07094cdf7be99fc6f9868c1d`
- Labels SHA-256: `b2ad1531e94bc62d05ed0d9bc1824486186b0d1301d260640783e8f1c8ade52c`
- Model revision: `a8ded8e697ce7c355e395a0df51f94adb4a2fd27`
- Threshold: `0.5`
- Maximum length: `512`

## Universe

| Benchmark | Cases |
|---|---:|
| `agentdojo` | 726 |
| `injecagent` | 1054 |
| `m3_v2` | 1500 |

## Admission boundary

Pre-run freeze only. It fixes the detector-visible text, separated evaluator labels, model revision, tokenizer windowing, threshold, aggregation and failure policy before any 3,280-case inference. It is not itself an effect result.
