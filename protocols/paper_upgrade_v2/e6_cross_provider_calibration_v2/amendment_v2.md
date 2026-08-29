# E6-v2 prospective engineering amendment

E6-v1 W1/W2 records, provider traces, call ledgers, gate/seal artifacts and
provider-stop markers remain immutable. E6-v2 reuses only the frozen v1 case
membership, condition order and logical work keys. It derives a new study ID,
new per-provider/window run and execution identities, and writes exclusively to
`outputs/experiments/e6_cross_provider_calibration_v2/`.

Live execution is code-gated to the previously untouched W3 rows. W1 and W2
cannot reach credential loading, dispatcher construction or an output write.
Before any W3 credential loading, dispatcher construction or output write, the
runner also requires a sealed immutable E6-v1 W2 artifact for that provider and
checks that the prospective W3 start is 18--30 hours after the recorded W2
start. DeepSeek currently has such a W2 seal; Gemini does not, so Gemini fails
closed unless a separately reviewed prospective protocol supplies a valid
predecessor rather than fabricating or backfilling historical evidence.
The first admitted W3 call freezes its start in the v2 window state. Later
canary expansion or explicit failed-key recovery reuses that frozen start for
the predecessor check and must still occur within the same 12-hour window.
The prospective W3 projection contains 360 DeepSeek rows and 180 Gemini rows.
Consequently, v1 W1/W2 plus v2 W3 are engineering/sensitivity calibration only;
they are not presented as three interchangeable replicates from one frozen
study implementation. Gemini has only one prospective v2 window and therefore
remains diagnostic even if all 180 W3 rows complete.

The repair admits one explicit generic recovery only when exactly one work key
is unresolved, its complete E6-v2 history contains exactly outer attempt 1,
that history contains no provider response evidence, the latest row is marked
retry-eligible, and attempt 1 has a valid pretransport payload commitment. The
recovery is outer attempt 2, uses independent trace, budget and call-ledger
paths, and compares each canonical payload digest with attempt 1 before
transport. It is terminal whether or not it obtains a response. Attempt 3,
response-bearing recovery and successful-row replay remain forbidden. An
attempt-1 failure that occurs before any valid payload commitment is written is
closed as an ITT diagnostic terminal rather than advertised as recoverable.

HTTP 429 is not generic recovery. The underlying manually authorized
same-provider ledger semantics remain unchanged, but this prospective W3-only
protocol does not exercise them: a 429 closes as an ITT diagnostic terminal and
does not create a fatal provider stop. Ordinary `ProviderTransportError` also
does not create a provider-wide stop. Every other escaped exception fails
closed; response-bearing runtime provider failures are classified from their
sanitized failure class before any provider-wide continuation.

The technical prefix gate now counts response-bearing runtime
`provider_failure` rows when checking repeated systemic errors. Public records
retain only a sanitized stage, exception class, provider-call index and HTTP
status class; prompts, responses, headers and credentials remain excluded.

Source-pinned AgentDojo fixtures may carry credential-like *labels* in simulated
tool observations. E6-v2 admits those labels only for the public benchmark
content class. This is a case-scoped exemption covering the entire public
benchmark conversation, because later model calls may legitimately replay the
pinned fixture observation. High-confidence secret patterns and an exact match
to the active API key remain forbidden. Synthetic M3 cases do not receive this
allowance.

This amendment is offline-qualified only. It does not authorize API execution,
does not create a replacement 1,620-row plan artifact, and does not alter the
scientific outcomes or interpretation of E6-v1.
