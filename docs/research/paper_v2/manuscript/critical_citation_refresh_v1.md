# Critical frontier citation refresh v1

Audit date: 2026-07-28 +08:00  
Scope: ten papers frozen as `critical_frontier_ids` (`L01`–`L03`,
`L21`–`L27`)  
Status: `CRITICAL_SET_METADATA_REFRESHED_SUPERSEDED_BY_FULL_REFRESH`

## Evidence boundary

This is a submission-preparation metadata and abstract-level claim audit. Each
record below was opened at its authoritative ACL Anthology, NeurIPS
Proceedings, or arXiv page. It verifies the displayed title, publication
surface/status, year, and whether the matrix's short method description is
supported by the official abstract.

It does not:

- convert an arXiv preprint into peer-reviewed evidence;
- establish implementation fidelity or reproduce reported effects;
- replace a final DOI/BibTeX and citation-context audit.

The refreshed literature matrix has SHA-256
`ecf952832afe5d474b70aa2141b8f9c05b0bd43d8da47287bcc836c9c3633570`.
Its regenerated structural manifest has SHA-256
`0c6713700b9a77ba5ec9869b2259171ebc986421a135012c4c917fbf1f0c881e`.

The later `full_citation_refresh_v1.md` extends this check to all 34 entries and
is the controlling pre-submission metadata audit.

## Critical-record audit

| ID | Authoritative record | Status retained | Metadata result | Abstract-level method check |
|---|---|---|---|---|
| L01 | [ACL 2026](https://aclanthology.org/2026.acl-long.443/) | PR | Corrected to the official title *VIGIL: Defending LLM Agents Against Tool-Stream Injection via Verify-Before-Commit*; DOI `10.18653/v1/2026.acl-long.443` | Supports verify-before-commit and a 959-case SIREN benchmark |
| L02 | [NeurIPS 2025](https://proceedings.neurips.cc/paper_files/paper/2025/hash/77f3b26c7907aa27b207df9b9d43f29a-Abstract-Conference.html) | PR | Corrected to the official title *DRIFT: Dynamic Rule-Based Defense with Injection Isolation for Securing LLM Agents* | Supports dynamic validation, control/data constraints, and memory-stream injection isolation |
| L03 | [ACL 2025](https://aclanthology.org/2025.acl-long.1435/) | PR | Corrected the leading “The” and the “in LLM Agents” suffix; DOI `10.18653/v1/2025.acl-long.1435` | Supports test-time verification of whether instructions and tool calls serve user-specified goals |
| L21 | [arXiv:2605.03378v2](https://arxiv.org/abs/2605.03378) | PP | Corrected to *ARGUS: Defending LLM Agents Against Context-Aware Prompt Injection*; latest observed version v2, 2026-07-08 | Supports an influence-provenance graph, evidence grounding, action release checks, and the reported 3.8% ASR / 87.5% clean utility |
| L22 | [arXiv:2605.26497v1](https://arxiv.org/abs/2605.26497) | PP | Corrected to *Aligning Provenance with Authorization: A Dual-Graph Defense for LLM Agents* | Supports comparison of an authorization graph and execution provenance, including parameter-source-level deviations |
| L23 | [arXiv:2604.10134v1](https://arxiv.org/abs/2604.10134) | PP | Corrected to *PlanGuard: Defending Agents against Indirect Prompt Injection via Planning-based Consistency Verification* | Supports isolated planning plus hierarchical tool/parameter consistency verification |
| L24 | [arXiv:2504.11703v3](https://arxiv.org/abs/2504.11703) | PP | Corrected to *Progent: Securing AI Agents with Privilege Control*; latest observed version v3, 2026-05-14 | Supports symbolic tool/argument privilege rules, automatic narrowing, and approval for privilege expansion |
| L25 | [EMNLP 2025](https://aclanthology.org/2025.emnlp-main.53/) | PR | Official title already matched; removed the unsupported local “Oral” designation; DOI `10.18653/v1/2025.emnlp-main.53` | Supports a planned Tool Dependency Graph that constrains tool traversal |
| L26 | [arXiv:2503.18813v2](https://arxiv.org/abs/2503.18813) | PP | Corrected to the official title *Defeating Prompt Injections by Design*; CaMeL is the method name, not part of the title | Supports trusted-query control/data-flow extraction and capability-based unauthorized-flow prevention |
| L27 | [arXiv:2510.09023v1](https://arxiv.org/abs/2510.09023) | PP | Corrected to include both LLM jailbreaks and prompt injections | Supports defense-aware adaptive evaluation rather than reliance on static attacks |

## Disposition

All ten critical links resolve to the intended paper. Four are retained as
peer-reviewed records (`L01`, `L02`, `L03`, `L25`); six remain preprints and
must be described as such (`L21`, `L22`, `L23`, `L24`, `L26`, `L27`).

The critical-set audit found nine title drifts plus one unsupported
venue-detail suffix.
Those metadata defects are now corrected in `literature_matrix.md`, and
`citation_integrity_manifest_v1.json` was deterministically regenerated and
verified. The underlying innovation-boundary assessment remains conservative:
ARGUS/AuthGraph overlap with provenance-aware authorization, Progent overlaps
with monotonic privilege control, and VIGIL/DRIFT/IPIGuard/CaMeL occupy the
closest structural-defense neighborhood.

All 24 remaining records were subsequently checked in
`full_citation_refresh_v1.md`. The formal Stage 2.5 citation gate nevertheless
remains closed until the final bibliography fields and every in-text citation
context are independently checked.
