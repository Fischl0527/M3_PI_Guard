# Public benchmark result-completeness audit v1

Generated: 2026-07-22T07:51:33.063928+00:00

## Result

- Status: `completed`
- Result completeness gate: `not_satisfied`
- Expected cells: 60
- Complete cells: 0
- Missing/incomplete cells: 60
- Initialized cells: 60
- Uninitialized cells: 0
- Expected case-runs: 53400
- Complete case-runs: 0
- Result eligible for formal tables: `False`

## Manifest status counts

| Manifest status | Cells |
|---|---:|
| `pending` | 60 |

## Missing or incomplete cells by benchmark

| Benchmark | Missing/incomplete cells |
|---|---:|
| `agentdojo` | 30 |
| `injecagent` | 30 |

## Checks

| Check | Status | Severity | Detail |
|---|---|---|---|
| `freeze_manifest_loaded` | `pass` | `error` | {"path": "protocols/paper_upgrade_v1/public_benchmark_formal_freeze_v1.json", "status": "completed"} |
| `expected_cells_declared` | `pass` | `error` | {"expected_cell_count": 60} |
| `expected_cell_ids_unique` | `pass` | `error` | [] |
| `result_gate_satisfied_only_when_all_cells_complete` | `pass` | `error` | {"complete_cells": 0, "expected_cells": 60, "result_gate": "not_satisfied"} |
| `incomplete_cells_not_result_eligible` | `pass` | `warning` | {"missing_or_incomplete_cell_count": 60, "result_gate": "not_satisfied"} |

## Boundary

Result-completeness audit only. It does not run public benchmarks or judge effect sizes. Formal claims may use public-benchmark results only when this gate is satisfied and the upstream freeze, strong-baseline readiness and statistical-analysis gates also pass.
