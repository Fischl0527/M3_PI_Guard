# Decision Log

Record architecture, policy, dependency, and workflow decisions here.

## Format

| Date | Decision | Context | Alternatives Considered | Consequences | Owner |
| --- | --- | --- | --- | --- | --- |

## Decisions

### 2026-07-13 — Secret-path experiments use an in-memory synthetic fixture

- Decision: any `sandbox/secrets/**` read is intercepted before filesystem probing and returns a clearly synthetic in-memory marker; writes are rejected.
- Reason: the first discarded Qwen probe proved that the Day7 file-backed fake canary violated the Harness permission boundary even though it was not a production secret.
- Consequence: DSR and cross-tool exfiltration remain measurable without reading, creating or exposing a secret file. Pre-fix probe outputs are excluded from E0-E17 evidence.

### 2026-07-13 — Canonicalize common small-model tool argument aliases

- Decision: normalize aliases such as `file→path`, `recipient→to` and `content→body/answer` immediately after ToolCall parsing while retaining unknown context fields.
- Reason: Qwen produced valid JSON with `file`; leaving it unnormalized made a malicious call indeterminate and biased ASR/Recall downward.
- Consequence: policy, execution and evaluation receive the same canonical call shape, with regression tests for precedence and alias handling.

| Date | Decision | Context | Alternatives Considered | Consequences | Owner |
| --- | --- | --- | --- | --- | --- |
| 2026-07-08 | Adopt repository-backed AI Agent Harness | The project needs long-running, recoverable, verifiable agent execution. | Single prompt only; external task tracker only. | Context, progress, verification, and handoff are stored in the repository as source-of-truth files. | Harness Architect |
| 2026-07-08 | Use feature-list driven delivery tracking | Agents need a durable way to know what is planned, active, verified, or blocked. | Free-form progress notes only. | `harness/features/feature_list.json` becomes the feature status contract. | Harness Architect |
| 2026-07-08 | Require verification evidence before completion claims | Agent outputs must be auditable. | Trust agent claims without command evidence. | Final reports must include commands and results. | Harness Architect |
| 2026-07-13 | Base the experiment project on Day7 commit `2c53f52` and local branch `test1` | The Harness directory initially contained no Git history or product code, while Day7 contains the complete runnable prototype. | Rebuild from the minimal main branch; copy files without history. | Preserves the strongest existing implementation and makes subsequent changes auditable. | Codex |
| 2026-07-13 | Run the project in strict mode with E0-E17 registry gates | The user requires continued execution until every experiment and delivery artifact is complete. | Treat experiments as an informal checklist. | Each experiment requires machine-readable status and evidence before completion. | Codex |
| 2026-07-13 | Separate runtime-visible case data from evaluation metadata | Existing prompts and Guard context expose expected behavior, attack family and injection annotations. | Keep the convenient full case object. | Prevents label leakage and makes Guard comparisons interpretable. | Codex |
| 2026-07-13 | Make prompt profile and Guard configuration orthogonal | Existing defense modes change both the system prompt and runtime Guard. | Continue the legacy defense mode switch. | Enables causal prompt-only, Guard-only and combined comparisons. | Codex |
| 2026-07-13 | Use `obfuscation_evasion` as the ninth attack family | The original dataset has five attack families, so three newly named families would total only eight. | Count benign as an attack family; invent a different ninth category. | Keeps benign separate and directly covers the approved encoding/evasion experiment dimension. | Codex |
| 2026-07-13 | Treat Stub as oracle-backed regression only | Stub directly uses evaluation metadata and deterministic unsafe actions. | Include Stub in effectiveness tables. | Prevents synthetic pipeline behavior from inflating real-model conclusions. | Codex |
| 2026-07-14 | Require automated dual diagnosis followed by two real human E17 reviews | The user explicitly requested dual-agent automatic checking and then two human blind reviewers. | Treat automated reviews as the two required reviewers; let one agent simulate human labels. | Automated outputs remain diagnostic-only; E17 stays blocked until two independent real humans complete the frozen review packets. | User/Codex |
| 2026-07-14 | Exclude PPT, DOCX report and submission ZIP from the active delivery scope | The user explicitly said not to make PPT, not to make a DOCX report yet, and not to create a submission ZIP. | Keep early document requirements; silently delete existing files. | Existing assets are preserved untouched, while final delivery is code/data/statistics/charts/Dashboard/Harness plus a local commit. | User |
| 2026-07-14 | Preserve frozen Dashboard source and isolate enhanced evidence UI | Post-freeze browser fixes changed a path included in the blind freeze. | Rewrite the freeze; allow presentation-only mismatches. | `m3_eval/dashboard.py` remains byte-identical to the freeze, while `m3_eval/evidence_dashboard.py` owns post-freeze UI improvements. | Codex |
| 2026-07-14 | Preserve old v3 E9/E14 and correct them under a new protocol/freeze | Post-freeze audit proved E9 context workloads were uncalibrated/collapsed and E14 prompt workloads were flat across context labels. | Overwrite v3; relabel old cells; treat truncation/parse failure as safety; ignore the semantic defect. | Old v3 remains immutable diagnostic provenance. E9/E14 return to running, all affected cells must be rerun with token-calibrated workloads and effective context aliases, and E17/final synthesis must be rebuilt. | Codex |
| 2026-07-14 | Use probe-verified Modelfile aliases for corrected context experiments | The OpenAI-compatible runtime path did not establish a trustworthy dynamic per-request `num_ctx` axis. | Continue passing request options; switch the entire runtime to an unvalidated API path. | Local `m3-qwen3-4b-ctx4k/8k/16k/32k` aliases define effective context settings. Probe success is a prerequisite only; formal corrected runs still require a separate freeze and measured prompt-token checks. | Codex |
