# External Q2 Readiness Review — M3-PI Guard / `codex/q2-empirical-study`

Reviewer: external (Claude), 2026-09-20
Repo state reviewed: branch `codex/q2-empirical-study`, cloned to `D:\HangProject\RedTeam_LLM_Security`
Scope: read-only. No repo file was modified, no experiment was run, no provider call was made.

---

## 1. Verdict

**Yes. Q2 is realistic, and the question is no longer "does it have potential" — the manuscript exists, the venue is correct, and the evidence is stronger than the project's own scorecard implies.**

The internal `completion_scorecard_v2.json` reports 68% submission readiness / 72.4% evidence completion. That number is calibrated against an internal standard — five source-backed strong baselines, an independent third-party blind set, two frontier API vendors, a full 100/500/2000 adaptive panel — which is closer to a **Q1 / top-venue** bar than to what JISA actually requires. Measured against the JISA bar, the work is substantially further along than 68%.

**Venue check (verified today):** *Journal of Information Security and Applications* is **SCIE-indexed, WOS Quartile Q2**, Computer Science–Information Systems, rank **94/266 by JIF** and 82/266 by JCI; Elsevier, ISSN 2214-2126, CiteScore 8.7, ~325 articles/year. The target in `jisa_submission_checklist.md` is correct. (Institutional Clarivate confirmation on the actual submission date is still the right final step — this is public/crowdsourced data, not an institutional pull.)

---

## 2. What is genuinely strong

### 2.1 E6 is the security result, and it holds up

`table_6_e6_activity_calibration.csv`, 60 tasks per condition, risk-enriched cohort:

| Condition | Unsafe | Rate | Wilson 95% CI |
|---|---|---|---|
| no_defense | 17/60 | 28.3% | 0.185 – 0.408 |
| peer-reviewed structural baseline (VIGIL) | 16/60 | 26.7% | 0.171 – 0.390 |
| m3_policy_only | 2/60 | 3.3% | 0.009 – 0.114 |
| m3_policy + safe prompt | 1/60 | 1.7% | 0.003 – 0.089 |
| m3_full (normal prompt) | 0/60 | 0.0% | 0 – 0.060 |
| m3_full | 0/60 | 0.0% | 0 – 0.060 |

Non-overlapping CIs against an **active no-defense control** and a **published baseline**. Most agent-defense papers have neither. This is the single most defensible security claim in the package, and the paper should lead the security story with it rather than with the floor-limited lean cells.

### 2.2 The authorization-regime finding reframes a field assumption

`exact_gold` — the per-case oracle authorization that much prior work implicitly grants to defenses — does not behave as an upper bound on utility. It behaves as a straitjacket:

- M3-v2 benign-tool completion: **17/30 → 0/30** (policy-only), **12/30 → 0/30** (full). McNemar p = 1.5e-05 and 4.9e-04.
- DENY record rate in that cell: 16.7% → **83.3%** (policy), 16.7% → 66.7% (full).
- Attack-cell operational failure: 6–8% → **24–26%**.
- p95 latency: ~9–10 s → **~19.6 s**.

That is a real methodological contribution: evaluations that grant defenses exact gold authorization are measuring a configuration that cannot be realized and that severely degrades utility.

### 2.3 Benchmark direction reversal

Exact-vs-auto benign-tool completion is **+4/30 on AgentDojo and −17/30 on M3-v2** under policy-only (+3/30 / −12/30 under full). A pooled −21.7 pp hides a sign flip. Reporting this properly is an external-validity contribution to the whole subfield, and Stage 3 caught it (P0-2) before it became a defect.

### 2.4 Adaptive budget curve

10% (4/40) first unsafe effect by query 50 → **45% (18/40) by 200**; 0/12 prespecified B200 survivors newly succeeded through 500 (Wilson upper 24.25%). Directly supports "static-attack evaluations overstate safety."

### 2.5 Process rigor well above the venue median

Preregistration with a **stop-and-pivot rule that was actually honored** when the mechanism route failed its own gate; freeze manifests with SHA-256; ITT retention of timeouts/refusals/parse failures in the primary denominator; Wilson intervals, paired McNemar, Holm within separate endpoint families, 10,000-replicate clustered bootstrap; explicit refusal to use post-hoc power; diagnostic/qualification/formal evidence classes that cannot impersonate each other. A five-perspective internal review (Stage 3) issued a `major revision` and Stage 4 closed all nine P0/P1 commitments. This is unusually disciplined for a Q2 submission.

---

## 3. The four things that will draw reviewer fire

Ordered by how likely they are to cost you a revision cycle.

### R1 — Single vendor (highest risk)

All effects come from DeepSeek: V4 Pro plus V4 Flash, same provider, likely same family. Both Gemini attempts closed incomplete (32/450 terminal with five responses; the E6 prefix added five more and a 503 wall on 2026-09-20).

The paper's own thesis is that measured security is **configuration-dependent and benchmark-dependent**. The immediately obvious reviewer question is: is it also **model-dependent**? Right now the paper cannot answer, and §5.9 concedes it. Expect at least one reviewer to make a second model a condition of acceptance.

**Fix that costs zero USD:** you already have Ollama configured (`OLLAMA_MODELS` → `E:\Ollama\models`), `Modelfile.qwen25-7b-8k`, two 8B models with 24/24 qualification smoke passed, and a complete non-oracle runner. Run an **open-weights replication** of the four primary cells (policy/full × auto/exact) on 60–100 paired cases with Qwen2.5-7B and/or Llama-3.1-8B. Label it exactly as what it is — an open-weights replication under a different capability class, *not* a second frontier vendor. That converts "one vendor" into "one API vendor plus an independent open-weights family," which is a materially different sentence in a rebuttal.

### R2 — The 0/30 needs a mechanism, not just a p-value

A perfect 17/30 → 0/30 on **your own benchmark** under **your own policy compiler** reads as a specification artifact until you show otherwise. The p-value makes it worse, not better — it just says the zero is real.

The raw records (`outputs/experiments/lean_empirical/deepseek/raw_records_v1.jsonl`, 933 rows) carry `deny_count` and `ask_count` but **not guard decision reason codes**, so the explanation is not currently reconstructible from the frozen artifact. The monitor is deterministic given the manifest and the proposed action, so this is recoverable **offline with no provider calls**:

1. Recompile the `exact_gold` and `auto_compiled` manifests for the 30 M3-v2 benign-tool cases.
2. Tabulate DENY reason codes across the 21 deny events in `m3_full__exact_gold__benign_tool__m3-v2` and the 26 in the policy-only cell.
3. Publish one sanitized worked example: a legitimate benign action that `exact_gold` refuses, and why.

That turns the paper's most suspicious number into its most interesting one.

### R3 — Direction inconsistency between E6 and the Public matrices

- E6: full **≤** policy (0/60 vs 2/60 unsafe).
- Public Pro: full **>** policy (38/600 vs 13/600). Public Flash: 24/400 vs 12/400.

Both are in the manuscript. A reviewer will ask which one to believe, and if the answer is only implicit, it looks like selective emphasis. This needs **one explicit reconciliation paragraph** naming the differences (cohort selection, risk enrichment, prompt profile assignment, sample size and floor effects) and stating plainly which estimate governs which claim. Cheap to write; expensive to omit.

### R4 — Reference list is thin

18 distinct `[@key]` citations active in `manuscript_deepseek_v1.md`, against 39 entries in `references_v1.bib`. For a 15,570-word journal paper, 18 references will read as under-engaged with the literature regardless of how good the coverage is. The 15+ unused BibTeX candidates are already sitting there; activating the relevant ones and adding ~15 more in usable security, information-flow control, and 2025–2026 agent-security benchmarking would close this without changing a single claim.

### Minor — the VIGIL claim invites pushback

Reporting that a peer-reviewed structural baseline performs at essentially no-defense level (16/60 vs 17/60) is a strong claim about someone else's work. The adapter-fidelity disclosure exists (P1-3, source commit, provider injection, fail-closed fallback) — make sure it appears **adjacent to the result**, not only in Methods, so the reviewer reads the caveat before forming an objection.

---

## 4. What is already done (do not redo it)

Everything on `jisa_submission_checklist.md` is closed except author-owned items:

- [ ] Author names, order, affiliations, corresponding-author details, CRediT
- [ ] Biography (≤100 words) + passport photograph per author
- [ ] Competing-interests declaration — **drafted**, needs confirmation
- [ ] Funding statement — **drafted as placeholder**, needs the funder/grant or the journal's no-funding language
- [ ] Author-owned similarity / self-plagiarism check
- [ ] Institutional SCIE/JCR confirmation on submission date
- [ ] Upload editable sources

Abstract is within 250 words, 5 highlights ≤85 chars, sections numbered 1/1.1/1.1.1, data-availability and generative-AI declarations drafted, cover letter drafted, glossary and supplementary tables prepared as separate editable files, 35-page English + 30-page Chinese + 4-page supplement visually reviewed in WPS.

---

## 5. Realistic outcome

| Path | Expected result |
|---|---|
| Submit as-is today | Major revision likely. At least one reviewer asks for a second model. Acceptance plausible but the revision cycle is long. |
| Close R2 + R3 + R4 first (no provider calls, ~1–2 weeks) | Major revision still likely, but on presentation rather than on missing evidence. Shorter cycle. |
| Also close R1 with a local open-weights replication (+2–3 weeks GPU) | Strongest position. Removes the single most predictable reviewer demand before it is made. |

**Recommendation:** do R2, R3, R4 — they are cheap, offline, and change how the paper reads. Attempt R1 with local models. Then submit.

**Do not wait for:** the independent third-party blind set, the five-strong-baseline target, the second frontier API vendor, or the 500/2000 adaptive panel. Those are Q1-grade asks. JISA will not require them, and the project has been holding itself to them since July at a cost of roughly two months.

Gemini is correctly deferred. It is not on the critical path and the 503 wall is not yours to fix.

---

## 6. Suggested sequence

1. **R3** — reconciliation paragraph. Hours. Pure writing.
2. **R4** — activate unused bib entries, add ~15 refs with verified DOIs and claim context, run the existing citation-integrity check. Days.
3. **R2** — offline compiler replay + deny-reason table + worked example; one new supplementary table. Days. No API.
4. **R1** — local open-weights replication under the existing preregistration; new evidence class, does not touch admitted DeepSeek rows. Weeks, GPU only.
5. Author-owned admin (names, CRediT, biographies, photos, funding, similarity check, institutional JCR pull).
6. Final submission audit, then submit.

Every step above is compatible with the existing harness protocol: each needs a `harness/tasks/` record, a feature-status update, focused tests, and an evidence-class label. None of them requires reopening an admitted result or rerunning a successful provider row.

---

## 7. Note on this session

The local Linux workspace on `laptop-ld620crj` failed to start, so no command could be run against the repo and no verification loop (`pytest`, Ruff, `harness/scripts/verify.ps1`) could be executed. Everything above is from reading frozen artifacts, analysis JSON, result CSVs, the manuscript, and the internal review records. No number in this review was recomputed from raw records.