# Related Work — source-status-aware draft

Status: `active_citations_verified`  
Context audit date: 2026-08-20  
Scope: the ten closest innovation-boundary papers plus the benchmark and
adaptive-evaluation works needed to position the study.

This draft uses stable source links and literature-matrix identifiers, with
publication status recorded separately from the methodological relationship.

## Runtime verification and task alignment

VIGIL implements a verify-before-commit protocol for tool-stream injection and
introduces the 959-case SIREN benchmark [@L01]. It is the closest
peer-reviewed structural comparator to M3 because both systems interpose before
an effect is committed. DRIFT instead combines dynamic rules with control- and
data-level constraints and memory-stream isolation [@L02].
The Task Shield verifies whether instructions and tool calls contribute to the
user's declared objective [@L03]. Together, these systems establish verification,
information-flow constraints, and task alignment as complementary runtime strategies.

PlanGuard is a related preprint that isolates planning from untrusted context
and applies hierarchical tool and parameter consistency checks [@L23]. These
approaches provide comparison classes for studying how enforcement structure
interacts with the authorization information available to a runtime Guard.

## Privilege, provenance, and information flow

Progent represents least privilege as symbolic tool-and-argument rules. Its
latest arXiv v3 description explicitly distinguishes automatic narrowing from
expansion that requires approval [@L24]. This overlaps directly with M3's
permission-monotonicity and confirmation design. IPIGuard, published at EMNLP
2025, constrains execution through a planned tool-dependency graph [@L25].
CaMeL separates trusted control and data flow and uses capabilities to prevent
unauthorized flows [@L26]. These systems provide the privilege, dependency, and
information-flow foundations for provenance-aware runtime authorization.

FAVA is a July 2026 preprint that translates natural-language tasks into a
permission intermediate representation, lowers it to an evidence-backed
permission graph, and uses an SMT authorizer before effectful execution [@L36].
This formulation makes the relationship between task meaning and executable
permission explicit. Our study treats the authorization regime as a paired
experimental factor and reports benchmark-specific security, benign utility,
confirmation/blocking burden, and operational failure together.

Two 2026 preprints overlap even more closely with provenance-aware
authorization. ARGUS constructs an influence-provenance graph for
context-dependent decisions [@L21], while AuthGraph compares an
authorization graph derived in an isolated context against a parameter-source
execution graph [@L22]. Both connect action authorization to the sources that
influence its parameters. We use these preprints to position the measurement
question alongside current provenance-aware designs.

*Auditing Provenance Sensitivity in LLM Agent Action Selection* supplies an
especially close 2026 measurement counterpart: it holds task content and
policy fixed while changing source authority, then measures whether action
selection changes [@L35]. Its
controlled next-action design differs from M3's multi-step evaluation, but
it reinforces the need to separate evidence relevance from authorization. Our
experiment extends that question to full tool trajectories, paired runtime
Guard conditions, benign utility, `ASK/DENY` burden, and operational failure.

The contribution is methodological and empirical. We vary authorization
information, separate online inputs from evaluator fields, compare policy and
full-module conditions, and quantify `ASK` burden and operational failures.
The current paired comparison holds ordinary prompts fixed; historical
package comparisons retain their original prompt/runtime assignments.

## Prompt-level defenses and execution-level outcomes

Structured queries, spotlighting, instruction hierarchy, and injection
detectors act at the prompt, representation, or model-output layer
[@L07; @L30; @L31; @L32]. These approaches complement execution-level monitoring.
The corrected evaluation links proposals, Guard decisions, sandbox receipts,
and outcome scoring while reporting completion and failures separately.
AgentDojo retains its native security checker, whereas M3-v2 uses observed
simulated effects.

## Benchmarks and adaptive evaluation

AgentDojo supplies dynamic security and utility tasks and is the main public
benchmark in this study [@L09].
InjecAgent provides a complementary collection of indirect prompt injections
for tool-integrated agents [@L10]. ASB broadens the scenario and defense
taxonomy [@L34].
The public expansion retains the benchmarks' unique task identities instead of
duplicating benign cases to manufacture a denominator.

*The Attacker Moves Second* motivates defense-aware optimization rather than
evaluation against a fixed attack set [@L27]. Our historical adaptive panel
exposes public `ALLOW/ASK/DENY` and legacy evaluator-labelled risk feedback,
then measures first success on frozen tasks at prespecified query budgets.

PIArena, published at ACL 2026, integrates attacks, defenses, and benchmarks
and evaluates feedback-adaptive injection, including cases where the injected
task aligns with the intended task [@L37]. The AgentDyn preprint instead
emphasizes dynamic planning, open-ended tasks, and helpful third-party
instructions [@L38]. These works motivate testing useful behavior under
authorization constraints, not merely counting blocked actions. The ASPI
preprint evaluates matched execution and clarification-seeking states and
finds increased vulnerability in its clarification setting [@L39]. That
interaction differs from our controller-only permission diagnostic, which
measures permit eligibility without a model clarification turn.

## Positioning summary

The active paper studies how authorization scope and runtime configuration shape
the measured security–utility frontier. Its paired design connects this question
to prior work on verification, least privilege, provenance, and task alignment.
Historical studies supply context for prompt/runtime factors and attack-budget
sensitivity; the current evaluation supplies corrected authorization and
contemporaneous utility measurements.

## Critical citation-context audit

| Context claim | Supporting IDs | Status boundary | Allowed use |
|---|---|---|---|
| Verify-before-commit and SIREN | L01 | Peer reviewed, ACL 2026 | Structural baseline and benchmark context |
| Dynamic rule, control/data constraints, memory isolation | L02 | Peer reviewed, NeurIPS 2025 | Adjacent mechanism boundary |
| Task/action alignment checking | L03 | Peer reviewed, ACL 2025 | Goal-alignment comparator |
| Context-dependent provenance auditing | L21 | Preprint | Novelty boundary; reported effects not treated as settled |
| Authorization/execution dual graph and parameter source | L22 | Preprint | Parameter-source authorization context |
| Controlled provenance-sensitivity audit | L35 | Preprint | Closest measurement boundary; motivates paired source-authority analysis |
| Evidence-backed permission graph and SMT authorization | L36 | Preprint | Structured-authorization context |
| Isolated planning and hierarchical consistency | L23 | Preprint | Adjacent mechanism, not formal baseline without code admission |
| Symbolic least privilege and approval-gated expansion | L24 | Preprint, arXiv v3 | Direct monotonic-permission overlap |
| Tool-dependency-graph enforcement | L25 | Peer reviewed, EMNLP 2025 | Privilege/data-flow comparator |
| Trusted control/data flow and capabilities | L26 | Preprint | Information-flow boundary |
| Defense-aware adaptive attacks | L27 | Preprint | Protocol motivation, not peer-reviewed fact |

## Bibliography export and submission-date gate

The 39-entry bibliography in `references_v1.bib` is assembled from ACL
Anthology, official proceedings pages, arXiv records and DOI/Crossref metadata.
It distinguishes peer-reviewed work from preprints and requires author, title,
year, URL, and venue or explicit preprint metadata.

The 24 references currently used by the unified manuscript have been checked
against their publisher, proceedings, conference, or arXiv landing pages, and
their claim contexts have been reviewed (21 earlier contexts plus three newly
checked contexts on 2026-09-05). The 15 unused entries remain a
candidate corpus and are not rendered in the working paper. If the final draft
adds a source, only the newly active citation and its claim context need review.
Publication status and the institutional JCR check must still be refreshed on
the submission date; the active lean study does not create a bibliography hash
bundle.
