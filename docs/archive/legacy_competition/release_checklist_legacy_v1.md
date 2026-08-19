# Release Checklist

## 1. Package Structure

- [x] `README.md`
- [x] `requirements-core.txt`
- [x] `requirements-dashboard.txt`
- [x] `m3_core/`
- [x] `m3_attacks/`
- [x] `m3_guard/`
- [x] `m3_eval/`
- [x] `fixtures/`
- [x] `scripts/`
- [x] `docs/`
- [x] `outputs/metrics/`
- [x] `outputs/runs/day5_demo_matrix/`
- [x] `outputs/runs/day6_demo_stub_matrix/`

## 2. Documentation

- [x] `docs/DATASET_CARD.md`
- [x] `docs/SYSTEM_ARCHITECTURE.md`
- [x] `docs/ETHICS_AND_SCOPE.md`
- [x] `docs/SUBMISSION_EVIDENCE_INDEX.md`
- [x] `docs/RUNBOOK.md`
- [x] `docs/case_cards/` contains the three demo case cards.
- [x] Final report and presentation files are included when available under `docs/report/` and `docs/presentation/`.

## 3. Dataset

- [x] `m3_attacks/cases/all_cases.jsonl` exists.
- [x] Dataset size is 69 cases.
- [x] The dataset covers more than three attack families.
- [x] `duplicate_case_id` is 0.
- [x] `missing_required_fields` is 0.
- [x] Dangerous target actions are limited to the local mock allowlist.

## 4. Safety Boundary

- [x] No real malicious code is included.
- [x] No real mailbox target is used by the sandbox tools.
- [x] No real public API endpoint is called by the sandbox tools.
- [x] No real credential is included in the release package.
- [x] `sandbox/secrets/` is excluded from the release package.
- [x] `sandbox/outbox/` is excluded from the release package.

## 5. Runtime Validation

- [x] Dataset merge and audit command is documented.
- [x] Stub demo smoke test is runnable.
- [x] Evaluation can generate CSV metrics.
- [x] Dashboard can read generated metrics and logs.
- [x] Release package smoke test result is recorded in `outputs/quality/day7_smoke_test_result.md`.

## 6. Packaging

- [x] `release/Redteam_LLM_Security_v1.0/` exists.
- [x] Release package does not include `.git/`.
- [x] Release package does not include virtual environments.
- [x] Release package does not include `__pycache__/` or `.pyc`.
- [x] Release package does not include model artifacts.
- [x] Release package does not include nested old release packages.
- [x] Release ZIP can be extracted.
- [x] SHA256 digest is recorded in `outputs/quality/day7_release_sha256.txt`.
