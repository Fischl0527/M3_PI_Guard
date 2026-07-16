# Project Routing

- Primary route: `code`
- Secondary route: `data`
- Confidence: `high`

## Route Basis
- Current user scope explicitly excludes PPT, DOCX report and submission ZIP.
- The controlling deliverable is runnable experiment software plus frozen data, statistics, charts and Dashboard evidence.
- Human E17 is an external validation gate, not a document-production route.

## Selected Evidence
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

## Default First Working Version
Run the audited experiment pipeline end to end, then rebuild evidence and Dashboard views from the frozen manifests.

## Route-Specific Validations
- Python tests/imports and experiment registry validate.
- Frozen manifests, hashes, case counts and statistics rebuild without drift.
- Dashboard filters and evidence replay pass real-browser QA.
- No PPT, DOCX report or submission ZIP is created by this task.
