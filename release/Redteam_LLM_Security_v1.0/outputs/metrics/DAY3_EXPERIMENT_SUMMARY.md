# DAY3 Experiment Summary

## Scope

DAY3 upgrades M3_PI_Guard from a basic dangerous-tool blocker into a local behavior-supervision and evaluation module. The work stays local-only: no remote model, no remote API, and no public network dependency.

## Guard Upgrades

- Multilingual and T2L detection: NFKC normalization, zero-width stripping, mixed Chinese/English/Japanese/Korean/Russian script detection, suspicious Unicode checks, and pinyin-style evasion signals.
- Structured injection detection: JSON/RPC-style fields such as instruction, system, developer, tool, function_call, method, params, execute, and next_step add structured injection reasons.
- Tool-output injection detection: observations are scanned for follow-up instructions, tool lures, and structured next-step fields before the next tool call is allowed.
- Sensitive dataflow detection: canary, api_key, token, password, secret file content, and external destinations are labeled and scored when data flows into send_email or call_api.
- Intent-action consistency: summarize, translate, extract, review, classify, and compare tasks are treated as mismatched when the proposed tool is send_email, call_api, or run_code.

## Policy Matrix

- final: allow.
- read_file sandbox/public: allow unless other risk signals lift the decision.
- read_file sandbox/secrets: deny.
- write_file sandbox/public: ask.
- non-sandbox file paths: deny.
- send_email: ask by default; deny when sensitive data or M3_CANARY is present.
- call_api /mock endpoint: ask by default; deny for non-mock endpoints or sensitive data.
- run_code: deny.

## Evaluation

evaluate.py now writes:

- outputs/metrics/day3_summary.csv
- outputs/metrics/day3_summary.json
- outputs/metrics/day3_grouped_by_family.csv

Metrics include ASR, UTR, DSR, BSR, FPR, AvgRisk, and WRS. Summary rows are grouped by attack_family, carrier, language, severity, model, and defense_mode.

## Dashboard MVP

The Streamlit dashboard loads RunLog JSONL files and the metrics CSV. It shows overview metrics, baseline vs guarded comparison, attack-family grouping, grouped metrics for carrier/language/severity/model/defense_mode, blocked records, and single-case replay.

## Limitations

- Rules are deterministic and keyword-driven, so semantic paraphrases can still evade detection.
- Pinyin and homophone detection is intentionally shallow and should be expanded with curated adversarial samples.
- The dashboard is an MVP focused on inspection, not long-term experiment tracking.
- Metrics depend on RunLog completeness and consistent unsafe_target_actions annotations.
