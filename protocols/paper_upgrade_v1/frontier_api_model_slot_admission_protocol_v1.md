# Frontier API model-slot admission protocol v1

This protocol separates three states that must not be conflated:

1. Local configuration exists and is ignored by Git.
2. Each provider completes one fixed synthetic network smoke with explicit local consent.
3. A new model-registry candidate records the exact provider model IDs and smoke hash.

`admit_frontier_api_model_slots.py` performs only step 3. It never reads API keys and never makes network requests. It accepts exactly the `openai` and `anthropic` provider set, requires one successful attempt per provider and refuses plan-only, partial or failed smoke manifests. On failure it removes no evidence and writes no registry candidate.

`audit_frontier_api_model_slots.py` now reads `frontier_api_model_slot_registry_admission_v1.json` and selects `model_registry_v3_candidate.json` only when that admission audit is `admitted_registry_candidate`, the candidate file exists, and its SHA-256 matches the admission record. `audit_q2_readiness.py` then uses the audited registered frontier vendor count for the model-coverage gate. If the admission audit is absent, blocked, stale or hash-mismatched, the Q2 audit falls back to `model_registry_v2.json` and keeps the frontier count at zero.

Even after admission, both slots remain `network_smoke_qualified_pending_formal_matrix` and `result_eligible_for_formal_tables=false`. A separate preregistered benchmark freeze, complete raw logs, cost/token accounting and analysis are required before either model can support a paper claim.
