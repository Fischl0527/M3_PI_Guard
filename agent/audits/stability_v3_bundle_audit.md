# E15 stability evidence-bundle audit

Status: **PASS**  
Date: 2026-07-14  
Program root: `outputs/experiments/program_final_v3`

## Evidence integrity

- Formal runs: 3,600 / 3,600 across 120 jobs and 120 conditions.
- Matrix outputs: 240 / 240 JSONL/CSV hashes match; 120 / 120 matrix manifests validate.
- Bundle manifest artifacts: 261 entries; every declared byte count and SHA-256 matches.
- Raw-run index: complete, 3,600 / 3,600 formal runs, zero Stub records admitted.
- Statistics: eight predeclared temperature comparisons.
- Stability table: 120 seed-level rows plus 12 model-temperature summaries.
- Input-quality issues, missing cases, duplicate run-step rows, timeouts, and nonterminal runs: zero.
- Parse-failure runs: 134; max-step runs: 4; all 138 unresolved runs remain in the original denominators.
- All four model lifecycle stops and GPU snapshots validate; active Ollama models and temporary sandbox residue are zero.

## Original-resolution visual QA

`primary_chart.png` passes original-resolution inspection:

- all 12 model-temperature categories and all ten deterministic seed colors are present;
- x-axis labels, title, legend, and y-axis are readable and not clipped;
- boxes summarize seed distributions and are not presented as confidence intervals;
- the shared 0-1 ASR scale is retained, so the concentration near zero is not visually exaggerated.

E15 remains an independent validation-derived stability matrix and is not merged into the 90-case blind main-matrix denominator.
