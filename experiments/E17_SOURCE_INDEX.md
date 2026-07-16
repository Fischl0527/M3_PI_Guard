# E17 frozen source index

E17 is a read-only, human-in-the-loop review over completed evidence. It does not start a model and it does not create reviewer or adjudicator decisions. The formal command accepts one frozen, hash-pinned source index and writes directly to `outputs/experiments/E17`:

```powershell
python -m experiments.e17_review --source-index path\to\e17_source_index.json
```

The formal index has this shape:

```json
{
  "schema_version": "1.0",
  "experiment_id": "E17",
  "status": "frozen",
  "coverage_complete": true,
  "secondary_disagreement_policy": "adjudicate_primary_or_secondary_code_set_difference",
  "source_mode": "formal_program",
  "program_root": "outputs/experiments/program_v3",
  "program_manifest": {
    "path": "outputs/experiments/program_v3/program_manifest.json",
    "sha256": "..."
  },
  "program_matrix_manifests": [
    {"path": "outputs/experiments/program_v3/smoke/job/manifest.json", "sha256": "..."}
  ],
  "required_program_stages": [
    "smoke",
    "validation-baseline",
    "ablation",
    "main",
    "derived",
    "stability"
  ],
  "e14_manifest": {"path": "outputs/experiments/E14/manifest.json", "sha256": "..."},
  "e16_manifest": {"path": "outputs/experiments/E16/manifest.json", "sha256": "..."}
}
```

`program_matrix_manifests` must contain every matrix manifest referenced by every job in the six required real-model stages, exactly once. Stub matrices, legacy `program`, `program_v2`, and `program_repro` roots, incomplete jobs, hash drift, missing conditions, duplicated logical runs, and E14 warmup rows are rejected.

The first run emits two blank blinded packets under `outputs/experiments/E17/packets` and remains pending. Complete them independently, with real reviewer identities and the required attestation, then pass both files with repeated `--reviewer` options. Any primary-code or secondary-code-set difference creates an adjudication packet and keeps E17 pending until a distinct human adjudicator submits `--adjudication`.

Validated human submissions are copied into `outputs/experiments/E17/submissions` and hash-pinned in the manifest. A completed fast-path invocation rechecks every source and output artifact hash before accepting the existing result.

## Sampled two-human audit protocol

The canonical workflow above remains a full-population protocol. A 360-item
two-human audit is generated as a separate, non-registering protocol revision:

```powershell
python -m experiments.e17_human_sample
```

Its frozen package is written to
`outputs/experiments/E17_human_stratified_360_v1`. It contains 300
representative evidence clusters, 40 additional automated-review disagreement
clusters, and 20 rare/complex clusters. Exact-evidence duplicates are collapsed
before selection, both human reviewers receive the same blinded items, and the
private sampling strata are not exposed in either packet.

The sampled package never overwrites the canonical 3,299-row E17 packet and
does not mark E17 complete. Population estimates may use only the representative
stratum with its recorded design weights. The two targeted strata are diagnostic
stress audits and must be reported separately.

The package root `README.md` is the administrator-facing index,
`REVIEW_INSTRUCTIONS.md` is the complete reviewer-facing codebook and operating
manual, `packets/README.md` separates the two assigned templates, and
`submissions/README.md` fixes the names and format of returned files. Private
sample membership remains under `private/` and must not be shown to either
reviewer before both completed CSVs are frozen. These generated Markdown files
are sourced from `experiments/review_templates/`; edit those source templates
and rebuild the package instead of editing generated copies only.
