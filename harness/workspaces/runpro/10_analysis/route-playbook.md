# Route Playbook

- Primary route: `code`
- Secondary route: `data`
- Confidence: `high`

## Route Objective
Complete the reproducible experiment platform and its frozen evidence chain; expose verified results through static charts and the Dashboard.

## Immediate Next Actions
- Keep E0-E16 frozen and independently auditable.
- Leave E17 and final synthesis gated until two independent human reviews exist.
- After E17 registration, rebuild final analysis, rerun all validators and commit locally.

## First Working Version Target
An end-to-end local run with resumable manifests, validated metrics and reproducible evidence reconstruction.

## Execution Priorities
- Measurement truthfulness and frozen provenance
- Failure-preserving execution and deterministic reconstruction
- Statistical and chart correctness
- Dashboard evidence replay

## Recommended Skills Or Tools
- $runpro
- Use the code-branch validation path plus project-specific experiment audit scripts.

## Route-Specific Validations
- Full Python test suite and compile/import checks pass.
- Registry, freeze and bundle-integrity audits pass.
- Final analysis validator passes only after E17 completion.
- Dashboard real-browser QA passes without console errors.

## Exit Criteria
- E0-E17 are completed with no unexplained failures.
- One command rebuilds final tables and 13 charts from frozen evidence.
- Harness strict validators pass and local `test1` commit exists.
- No PPT, DOCX report, ZIP, push or PR is produced.

## Supporting Reference
- `references/code-branch.md`

## Routing Evidence Snapshot
- .agent\policies.md [document file]
- .agent\workflow.md [document file]
- AGENTS.md [document file]
- README.md [document file]
- harness/README.md [document file]
- agent\current-task.md [document file]
- agent\failure-log.md [document file]
- agent\memory.md [document file]
- docs\DATASET_CARD.md [keyword match]
- m3_eval\dashboard.py [keyword match]
