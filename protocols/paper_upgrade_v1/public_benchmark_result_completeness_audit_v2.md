# Public benchmark result-completeness audit v1

Generated: 2026-07-22T07:51:51.390888+00:00

## Result

- Status: `completed`
- Result completeness gate: `not_satisfied`
- Expected cells: 84
- Complete cells: 0
- Missing/incomplete cells: 84
- Initialized cells: 84
- Uninitialized cells: 0
- Expected case-runs: 74760
- Complete case-runs: 0
- Result eligible for formal tables: `False`

## Manifest status counts

| Manifest status | Cells |
|---|---:|
| `pending` | 84 |

## Missing or incomplete cells by benchmark

| Benchmark | Missing/incomplete cells |
|---|---:|
| `agentdojo` | 42 |
| `injecagent` | 42 |

## Checks

| Check | Status | Severity | Detail |
|---|---|---|---|
| `freeze_manifest_loaded` | `pass` | `error` | {"path": "protocols/paper_upgrade_v1/public_benchmark_formal_freeze_v2.json", "status": "completed"} |
| `expected_cells_declared` | `pass` | `error` | {"expected_cell_count": 84} |
| `expected_cell_ids_unique` | `pass` | `error` | [] |
| `result_gate_satisfied_only_when_all_cells_complete` | `pass` | `error` | {"complete_cells": 0, "expected_cells": 84, "result_gate": "not_satisfied"} |
| `incomplete_cells_not_result_eligible` | `pass` | `warning` | {"missing_or_incomplete_cell_count": 84, "result_gate": "not_satisfied"} |

## Boundary

Result-completeness audit only. It does not run public benchmarks or judge effect sizes. Formal claims may use public-benchmark results only when this gate is satisfied and the upstream freeze, strong-baseline readiness and statistical-analysis gates also pass.
