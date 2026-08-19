# Independent blind authoring kit v1

## What this kit is

This folder is a content-free assignment and custody package for an independent 600-case confirmatory blind set. It is not a dataset and cannot raise the Q2 evidence score by itself. Project developers must not fill the prompts or expected effects.

## Who should author the candidate

Use at least one person or independently operated generator that has not read M3-v2 case content, experiment outputs, failure logs, Guard rules, detector thresholds or per-case expected actions. Two authors may split the rows using `author_group`; independence is about separation from model/defense development, not about manually typing every row.

An independent program is acceptable and is more realistic than 600 manually written rows, provided its source, seed, dependencies and generation prompts are frozen outside this repository before the M3 developers receive the candidate. Human authors should inspect a stratified sample before sealing.

## Authoring procedure

1. Copy this kit to a separate working directory controlled by the independent author/custodian. Do not give that environment access to `m3_attacks/cases/paper_v1`, `outputs`, Harness progress/failure files or Guard source.
2. Use `authoring_slots.csv` or `authoring_slots.jsonl` as the required distribution. Every slot becomes exactly one unique semantic template and one case.
3. Create 360 attack rows (40 for each of 9 families), 120 benign no-tool rows and 120 benign legal-tool rows. Keep the assigned language, authorization profile and scenario type unless a documented impossibility is found before sealing.
4. Fill fields using `case_template.json`. The runtime fields are the trusted request/context plus untrusted content/memory. Evaluation labels stay only inside `offline_evaluation`.
5. Do not add `authorized_actions`, top-level `requires_tool`, `expected_safe_behavior`, `unsafe_target_actions`, `target_actions`, `expected_answer`, `detector_answer` or any exact detector/Guard answer to the runtime object.
6. Keep every `case_id` and `template_id` unique. Do not copy or paraphrase known M3-v2 cases. Use mock-only recipients, endpoints and sandbox paths; never reference real credentials, real email addresses or destructive tools.
7. Validate the 600 JSONL rows in the independent environment. Record all validation commands and any excluded/replaced slot before seal.
8. Write the final candidate exactly once, compute SHA-256, then complete `custody_manifest_template.json` as `m3_v2_independent_blind_custody.json`. Set the same `sealed_at` timestamp in every row's custody block.
9. Run the package-local self-check before release:

   ```powershell
   python validate_candidate_before_release.py --candidate m3_v2_independent_blind_candidate.jsonl --custody-manifest m3_v2_independent_blind_custody.json --output pre_release_self_check.json
   ```

   A PASS here only checks content-free structure and custody consistency. It does not compare against M3 development data.
10. The custodian withholds the candidate from M3 developers until code, thresholds, hypotheses and exclusions are frozen. Release the candidate, custody manifest and pre-release self-check together.
11. In the M3 repository, place the released candidate at `m3_attacks/cases/paper_v1/m3_v2_independent_blind_candidate.jsonl`, run `audit_m3_v2_independent_blind.py`, and preserve any failed audit without editing results. A passing admission audit only freezes input; it is not a model result.

## Review burden

Do not ask two people to inspect all future model-run rows. Before sealing, independently inspect a stratified sample of the 600 authored cases (recommended 120–180 total, oversampling complex cross-tool/memory/obfuscation rows). After experiments, use the already established two-reviewer stratified sampling workflow for outcome/error taxonomy. Conflicts are adjudicated; targeted diagnostic rows are not pooled into population estimates.

## Release boundary

The independent candidate remains invalid for confirmatory claims if developers saw it before code/threshold freeze, if it was generated from existing M3 cases/results, if custody is incomplete, or if admission checks are weakened after inspecting model performance.
