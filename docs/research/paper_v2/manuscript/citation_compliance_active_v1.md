# Active citation compliance review

Review date: 2026-08-23

Scope: the 21 references actually cited by `manuscript_deepseek_v1.md`. The
remaining 15 entries in `references_v1.bib` are a dormant candidate corpus and
are not rendered by citeproc; they were intentionally excluded from this
submission-focused review.

## Outcome

- All 21 in-text keys resolve to an entry in `references_v1.bib`.
- No bibliography item is rendered without an in-text citation.
- Eleven cited works have a formal conference or workshop publication record;
  ten are explicitly represented as preprints.
- Titles, author order, publication status, year, and stable landing page were
  checked against the publisher, conference, proceedings, or arXiv record.
- Three deterministic metadata defects were corrected:
  - `L02` (DRIFT): year corrected from 2026 to the official NeurIPS 2025
    proceedings year, and DOI `10.52202/085713-2791` added.
  - `L20` (AgentSpec): the unregistered DOI and unverified page range were
    removed; the citation now points to the official ICSE 2026 Research Track
    page.
  - `L08` (Contextual Agent Security): the first author's surname was corrected
    from `Bagdasarian` to `Bagdasaryan` to match the official Google Research
    record.

## Active-source ledger

| Key | Short name | Status used in manuscript | Primary metadata source | Result |
|---|---|---|---|---|
| L01 | VIGIL | ACL 2026 long paper | [ACL Anthology](https://aclanthology.org/2026.acl-long.443/) | verified |
| L02 | DRIFT | NeurIPS 2025 conference paper | [NeurIPS Proceedings](https://proceedings.neurips.cc/paper_files/paper/2025/hash/77f3b26c7907aa27b207df9b9d43f29a-Abstract-Conference.html) | corrected and verified |
| L03 | Task Shield | ACL 2025 long paper | [ACL Anthology](https://aclanthology.org/2025.acl-long.1435/) | verified |
| L07 | StruQ | USENIX Security 2025 paper | [USENIX](https://www.usenix.org/conference/usenixsecurity25/presentation/chen-sizhe) | verified |
| L08 | Contextual Agent Security | HotOS 2025 workshop paper | [Google Research](https://research.google/pubs/context-is-key-for-agent-security/) | corrected and verified |
| L09 | AgentDojo | NeurIPS 2024 benchmark paper | [NeurIPS Proceedings](https://proceedings.neurips.cc/paper_files/paper/2024/hash/97091a5177d8dc64b1da8bf3e1f6fb54-Abstract-Datasets_and_Benchmarks_Track.html) | verified |
| L10 | InjecAgent | ACL Findings 2024 paper | [ACL Anthology](https://aclanthology.org/2024.findings-acl.624/) | verified |
| L20 | AgentSpec | ICSE 2026 Research Track paper | [ICSE programme](https://conf.researchr.org/details/icse-2026/icse-2026-research-track/29/AgentSpec-Customizable-Runtime-Enforcement-for-Safe-and-Reliable-LLM-Agents) | corrected and verified |
| L21 | ARGUS | 2026 preprint | [arXiv](https://arxiv.org/abs/2605.03378) | verified as preprint |
| L22 | AuthGraph | 2026 preprint | [arXiv](https://arxiv.org/abs/2605.26497) | verified as preprint |
| L23 | PlanGuard | 2026 preprint | [arXiv](https://arxiv.org/abs/2604.10134) | verified as preprint |
| L24 | Progent | 2025 preprint, revised 2026 | [arXiv](https://arxiv.org/abs/2504.11703) | verified as preprint |
| L25 | IPIGuard | EMNLP 2025 paper | [ACL Anthology](https://aclanthology.org/2025.emnlp-main.53/) | verified |
| L26 | CaMeL | 2025 preprint | [arXiv](https://arxiv.org/abs/2503.18813) | verified as preprint |
| L27 | The Attacker Moves Second | 2025 preprint | [arXiv](https://arxiv.org/abs/2510.09023) | verified as preprint |
| L30 | Spotlighting | 2024 preprint | [arXiv](https://arxiv.org/abs/2403.14720) | verified as preprint |
| L31 | Instruction Hierarchy | 2024 preprint | [arXiv](https://arxiv.org/abs/2404.13208) | verified as preprint |
| L32 | Indirect-injection detection | ACL 2025 long paper | [ACL Anthology](https://aclanthology.org/2025.acl-long.890/) | verified |
| L34 | Agent Security Bench | ICLR 2025 paper | [ICLR Proceedings](https://proceedings.iclr.cc/paper_files/paper/2025/hash/5750f91d8fb9d5c02bd8ad2c3b44456b-Abstract-Conference.html) | verified |
| L35 | Provenance sensitivity audit | 2026 preprint | [arXiv](https://arxiv.org/abs/2607.20827) | verified as preprint |
| L36 | FAVA | 2026 preprint | [arXiv](https://arxiv.org/abs/2607.27267) | verified as preprint |

## Claim-fit check

The citations support the roles assigned to them in the manuscript: benchmark
descriptions cite the benchmark papers; runtime enforcement, task alignment,
privilege control, provenance, and data-flow statements cite the corresponding
method papers; the adaptive-attack motivation cites `L27`. No cited source is
used to claim that M3 is first, unique, state of the art, or universally
superior. Preprint-only mechanisms remain distinguishable from peer-reviewed
work through their BibTeX type and note.

Eleven of the 21 active citations (52.4%) also received an explicit
citation-context check against the official abstract or proceedings summary:
`L01`, `L02`, `L03`, `L21`, `L22`, `L23`, `L24`, `L25`, `L26`, `L35`, and
`L36`. This exceeds the pre-review 30% context-sampling threshold. The sample
covers the principal verify-before-commit, control/data-flow, task-alignment,
privilege, provenance, and provenance-sensitivity claims used by the paper.

Semantic Scholar was used only as a secondary discovery-index cross-check.
Where its preprint year differed from the official venue record (Task Shield,
StruQ, AgentSpec, and Agent Security Bench), the publisher or proceedings page
controlled the manuscript metadata.

## Remaining submission gate

This review is complete for the current 21-key active set. It must be rerun only
if the manuscript adds or replaces a citation before submission. Institutional
verification of JISA's current SCIE/JCR quartile is a separate author-side gate
and is not established by this citation review.
