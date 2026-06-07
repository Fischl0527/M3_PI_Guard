# M3_PI_Guard Dataset Card

## Dataset Overview

M3_PI_Guard uses a local-only red-team dataset for evaluating LLM Agent tool-call safety under prompt injection, indirect instruction injection, and benign workflow conditions. The dataset is designed for reproducible sandbox experiments rather than for attacking real services.

Current full dataset:

- File: `m3_attacks/cases/all_cases.jsonl`
- Total cases: 69
- Format: one AttackCase JSON object per line
- Runtime environment: local sandbox only

## Attack Families

| Family | Count | Purpose |
|---|---:|---|
| `rag_indirect` | 18 | Tests untrusted document instructions that try to override the user task or leak sandbox secrets. |
| `direct_jailbreak` | 15 | Tests direct instruction-following pressure and role override attempts. |
| `multilingual_t2l` | 15 | Tests multilingual and translation-layer instruction hiding. |
| `json_rpc` | 8 | Tests structured payloads that imitate tool calls or RPC messages. |
| `tool_output_injection` | 5 | Tests malicious instructions embedded in simulated tool output. |
| `benign_clean` | 8 | Tests normal workflows and false-positive behavior. |

## Representative Sets

- `fixtures/demo_cases.jsonl`: 3-case demo set covering RAG indirect injection, JSON/RPC injection, and multilingual/T2L injection.
- `fixtures/day5_representative_cases.jsonl`: 24-case representative set covering all major families.
- `fixtures/sample_cases.jsonl`: compact baseline sample set used by early DAY2 validation.

## Safety Boundaries

- No real email is sent.
- No public API is called.
- No model-generated code is executed.
- Sandbox secrets are local canaries only.
- All file operations are restricted to the project sandbox.

## Intended Use

The dataset supports:

- Comparing baseline Agent behavior with guarded execution.
- Measuring unauthorized tool-call rate, data-spill behavior, block rate, false-positive rate, and guard risk score.
- Demonstrating how behavior-level supervision can intercept unsafe tool calls before execution.

The dataset is not intended for attacking real systems, extracting real credentials, or testing against production services.
