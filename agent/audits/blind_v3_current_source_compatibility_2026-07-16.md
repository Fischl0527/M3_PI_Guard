# Experiment Result Integrity Audit

- Status: **FAIL**
- Generated: `2026-07-15T16:57:18.707807+00:00`
- Program manifest SHA256: `ec8b144646f6b97c09bc4d051e25a0b7f8a7a66a22326302e410480ba3c218bc`
- Blind freeze SHA256: `a36791aa0dfb530d2829b9e3eabec2f89c7df0d864b2b5a146e4569cfd79554e`
- Threshold SHA256: `c1ebcddb1199ae9a2a728702ce6ed97c8688c47fea060e4dae90c289ae430dbf`

## Stage summary

| Stage | Scanned | Jobs | Conditions | Logical runs | Log rows | Parse-fail rows | Timeouts | Max-step | Nonterminal |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| main | yes | 12 | 72 | 6480 | 12538 | 457 | 0 | 108 | 0 |
| derived | yes | 8 | 16 | 446 | 619 | 105 | 0 | 0 | 0 |
| stability | yes | 120 | 120 | 3600 | 5087 | 134 | 0 | 4 | 0 |

## Model provenance

| Model tag | Digest | Ollama version |
|---|---|---|
| `gemma3:4b` | `a2af6cc3eb7f` | `ollama version is 0.24.0` |
| `llama3.2:3b` | `a80c4f17acd5` | `ollama version is 0.24.0` |
| `phi4-mini:3.8b` | `78fad5d182a7` | `ollama version is 0.24.0` |
| `qwen3:4b-instruct` | `0edcdef34593` | `ollama version is 0.24.0` |

## Findings

Errors: **8**; warnings: **0**.

| Severity | Code | Message |
|---|---|---|
| error | `freeze_file_sha_mismatch` | frozen file SHA256 changed |
| error | `freeze_file_sha_mismatch` | frozen file SHA256 changed |
| error | `freeze_file_sha_mismatch` | frozen file SHA256 changed |
| error | `freeze_file_sha_mismatch` | frozen file SHA256 changed |
| error | `freeze_file_sha_mismatch` | frozen file SHA256 changed |
| error | `freeze_file_sha_mismatch` | frozen file SHA256 changed |
| error | `freeze_file_sha_mismatch` | frozen file SHA256 changed |
| error | `freeze_file_sha_mismatch` | frozen file SHA256 changed |
