# Full literature-matrix citation refresh v1

Audit date: 2026-07-28 +08:00  
Scope: all 34 rows in `docs/research/paper_v2/literature_matrix.md`  
Status: `ALL_34_AUTHORITATIVE_RECORDS_EXPORTED_INLINE_CONTEXT_AUDIT_PENDING`

## Result

All 34 current rows were checked against an authoritative publisher,
conference-proceedings, DOI/Crossref-backed, or arXiv record. The refreshed
matrix now contains 24 peer-reviewed records and 10 preprint-only records.
No preprint in the current matrix is represented as peer reviewed.

The audit corrected:

- 18 shortened, invented, or otherwise non-canonical paper titles;
- one unsupported “Oral” venue descriptor;
- one completely misbound record (`L20`), whose URL resolved to an unrelated
  biomedical retrieval paper;
- two stale preprint classifications (`L32`, `L33`) whose ACL/EMNLP
  publications are now linked directly.

`L20` was not silently relabeled. The unsupported “Virtual Context” row was
removed and replaced with the independently verified ICSE 2026 paper
*AgentSpec: Customizable Runtime Enforcement for Safe and Reliable LLM
Agents*, which is directly relevant to runtime policy enforcement.

## Audit trail by source group

| IDs | Authoritative surfaces opened | Outcome |
|---|---|---|
| L01, L03–L06, L10, L14, L20, L25, L32, L33 | ACL Anthology or official ICSE program/DOI | Titles, venue/year, and abstract-level method descriptions checked; L20 replacement and L32/L33 status corrections recorded |
| L02, L09, L11, L12, L15–L17 | NeurIPS Proceedings | Titles, track/year, and abstract-level scope checked |
| L07, L13 | USENIX Security proceedings | Titles, year, pages, and abstract-level scope checked |
| L08 | Google Research publication record | HOTOS 2025 venue and contextual-policy scope checked |
| L18 | IEEE DOI plus Crossref-backed bibliographic records and archived author copy | Canonical title, 2026 IEEE Access status, and DOI checked |
| L19 | MDPI version-of-record page | Canonical title, 2026 journal metadata, and DOI checked |
| L21–L24, L26–L31 | arXiv records | Current displayed title, version date, subject, and preprint status checked |
| L34 | ICLR Proceedings | Title, 2025 conference status, and benchmark scope checked |

## Publication-status controls

Peer-reviewed (`PR`, including `PR+BM`):

`L01`–`L20`, `L25`, `L32`, `L33`, and `L34`.

Preprint-only (`PP`, including `PP+BM`):

`L21`, `L22`, `L23`, `L24`, `L26`, `L27`, `L28`, `L29`, `L30`, and `L31`.

The following high-overlap works therefore remain explicitly non-peer-reviewed:
ARGUS, AuthGraph, PlanGuard, Progent, CaMeL, and *The Attacker Moves Second*.
Their claims may define the novelty boundary and motivate experiments, but
their reported effects must not be written as settled peer-reviewed evidence.

## Reproducible bindings

- literature matrix SHA-256:
  `ecf952832afe5d474b70aa2141b8f9c05b0bd43d8da47287bcc836c9c3633570`;
- regenerated citation manifest SHA-256:
  `0c6713700b9a77ba5ec9869b2259171ebc986421a135012c4c917fbf1f0c881e`;
- citation count: 34;
- peer-reviewed count: 24;
- preprint-only count: 10.

The manifest was regenerated from the matrix and passed
`python -m experiments.paper_v2.citation_integrity --verify-only`.

## Bibliography export completed

- BibTeX: `docs/research/paper_v2/manuscript/references_v1.bib`;
- bibliography SHA-256:
  `40680e3eca610e9f9569a62a2ed08f5d27a8fbc78058c98a008d0d5897074828`;
- build report:
  `docs/research/paper_v2/manuscript/bibliography_build_v1.json`;
- build manifest SHA-256:
  `d8ed622075d245faca520525b5b9177f1b43a2917d40a1a9b1e80a5dd1431ec0`;
- verification: 34/34 keys, 24 peer-reviewed, 10 preprint-only, no LLM
  provider calls or credentials; focused bibliography tests 2/2.

## Remaining citation gate

This closes the literature-matrix metadata and abstract-level scope audit. It
does not yet close formal Stage 2.5 because the final manuscript does not have
a complete reference list or finalized in-text citation contexts. Before
submission:

1. bind every substantive literature claim to one or more bibliography keys;
2. verify that each citation supports the surrounding sentence rather than
   merely sharing a topic;
3. recheck current arXiv versions and publication status on the submission
   date;
4. obtain institutional JCR/SCIE confirmation for the selected journal.
