# Derived v3 evidence-bundle audit

Status: **PASS**  
Date: 2026-07-14  
Program root: `outputs/experiments/program_final_v3`

## Bundle integrity

| Experiment | Formal runs | Manifest artifacts | Statistical comparisons | Unresolved retained | Result |
|---|---:|---:|---:|---:|---|
| E7 | 120 / 120 | 15 | 9 | 5 | PASS |
| E8 | 90 / 90 | 16 | 9 | 4 | PASS |
| E9 | 120 / 120 | 24 | 20 | 94 | PASS |
| E10 | 72 / 72 | 15 | 12 | 0 | PASS |
| E11 | 44 / 44 | 16 | 4 | 2 | PASS |

- All required files exist and are non-empty.
- All artifact byte counts and SHA-256 values match their bundle manifests.
- All five `figure_manifest.json` files validate against their experiment IDs.
- All five raw-run indexes are complete, admit zero Stub records, and validate exactly the expected formal run count.
- Input-quality issue count, nonterminal logical runs, duplicate run-step rows, and failed jobs are all zero.
- The 105 unresolved/parse-failure runs remain in the original denominators. E9 accounts for 94 and must be disclosed as a long-context reliability limitation.

## Original-resolution visual QA

| Experiment | Figure | Result | Notes |
|---|---|---|---|
| E7 | Language ASR heatmap | PASS | Labels, color scale, values, and axes are readable; no clipping. |
| E8 | Obfuscation ASR heatmap | PASS | Nine mutation families are readable; no clipping or NA-as-zero rendering. |
| E9 | Context-position ASR trend | PASS | Wilson intervals and eight series are visible; legend is dense but complete and not clipped. |
| E10 | Multi-turn ASR trend | PASS | Turn axis, six series, Wilson intervals, and legend are complete. |
| E11 | Cross-tool-chain ASR heatmap | PASS | Four chain patterns, conditions, values, and color scale are readable. |

No chart was regenerated or selectively altered after inspection.
