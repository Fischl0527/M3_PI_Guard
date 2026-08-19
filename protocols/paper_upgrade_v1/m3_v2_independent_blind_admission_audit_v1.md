# M3-v2 independent blind admission audit v1

Generated: 2026-07-21T10:08:10.750506+00:00

## Result

- Status: `blocked_missing_candidate`
- Candidate exists: `False`
- Result eligible for confirmatory Q2 tables: `False`
- Passed checks: 0/1

## Checks

| Check | Status | Severity | Detail |
|---|---|---|---|
| `candidate_jsonl_present` | `fail` | `error` | "E:\\M3_PI_Guard_test\\m3_attacks\\cases\\paper_v1\\m3_v2_independent_blind_candidate.jsonl" |

## Boundary

Admission audit only. The current deterministic sealed holdout remains excluded from independent confirmatory claims until a separately authored candidate JSONL passes this gate.
