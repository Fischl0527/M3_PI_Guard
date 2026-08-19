# Q2 readiness audit v1

Generated: 2026-07-23T02:05:37.267024+00:00

## Result

- Raw score: 66.0/100
- Capped score: 60.0/100
- Readiness band: `paper_upgrade_in_progress`
- Goal met (>=90): `False`

## Criteria

| Criterion | Earned | Status | Main blockers |
|---|---:|---|---|
| Historical E0-E17 engineering evidence | 12.0/12.0 | `complete` | none |
| Non-oracle runtime mechanism and formalization | 10.0/10.0 | `complete` | none |
| Independent confirmatory blind evidence | 2.0/15.0 | `blocked` | new independent M3-v2 blind split is not admitted, frozen and run; independent blind admission audit has not admitted a candidate dataset; post-hoc/historical blind evidence cannot serve as confirmatory Q2 evidence; blind_manifest_reference_present; blind_manifest_resolved; blind_manifest_candidate_audit_admitted; blind_manifest_manifest_status_formal; blind_manifest_manifest_result_eligible; blind_manifest_manifest_case_count_600; blind_manifest_manifest_candidate_sha_matches_admission; blind_manifest_manifest_scope_independent_blind |
| AgentDojo/InjecAgent public benchmark formal results | 3.0/15.0 | `blocked` | public benchmark formal matrix is not complete; AgentDojo official transformers_pi_detector full cell is not admitted |
| Source-backed strong baselines | 6.0/15.0 | `blocked` | fewer than five source-backed strong baselines are formal-ready |
| Model coverage | 6.0/10.0 | `partial` | two frontier API vendor model slots are still missing; frontier API local configuration is not ready for explicit network smoke |
| Adaptive query-budget attacks | 4.0/10.0 | `blocked` | 80-task adaptive query-budget attack is not complete; MCTS/black-box budget curves are still missing as formal evidence |
| Statistics, human review, and figures | 8.0/8.0 | `complete` | none |
| Reproducibility, freezes, and exclusion gates | 8.0/8.0 | `complete` | none |
| Manuscript package and paper narrative | 7.0/7.0 | `complete` | none |

## Active Caps

- public_benchmark_gate: cap 75.0; formal public-benchmark matrix is incomplete (score currently below this cap)
- strong_baseline_gate: cap 70.0; fewer than five strong baselines are formal-ready (score currently below this cap)
- independent_blind_gate: cap 65.0; new independent confirmatory blind evidence is missing (score limited)
- frontier_api_model_gate: cap 60.0; two frontier API vendor slots are missing (score limited)
- adaptive_budget_gate: cap 60.0; formal adaptive query-budget evidence is missing (score limited)

## Boundary

Readiness audit only.  It is not a manuscript acceptance predictor and cannot turn partial, diagnostic, smoke, or running results into formal paper evidence.  Scores should move upward only when the underlying frozen artifacts and formal manifests are actually present.
