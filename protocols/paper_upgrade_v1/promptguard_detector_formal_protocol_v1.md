# PromptGuard detector-only formal protocol v1

Protocol status: `pre_run_fixed`

## Estimand and evidence scope

This protocol evaluates the frozen `meta-llama/Llama-Prompt-Guard-2-86M`
classifier as an **external-content prompt-injection detector**.  It estimates
malicious-content recall, benign-content false-positive rate, precision, F1,
score discrimination and detector latency.  It does not estimate end-to-end
agent ASR, TCR or tool-call utility and must not be presented as if it did.

The formal universe contains exactly 3,280 case-level detector decisions:

- M3-v2: 1,500 cases (900 malicious, 600 benign);
- AgentDojo v1: 629 security pairs and 97 utility tasks;
- InjecAgent official release: 1,054 security cases.

The frozen threshold is not tuned on these results.  The M3-v2 automated
holdout is reported by split and is not described as an independently authored
blind set.

## Detector-visible input

Only untrusted runtime text is encoded by PromptGuard:

- M3-v2: `untrusted_content` followed by every `untrusted_memory` item;
- AgentDojo utility: every benign tool-output message produced by the official
  ground-truth user-task trajectory in the default environment;
- AgentDojo security: every tool-output message from the same official
  ground-truth trajectory after applying AgentDojo's registered `injecagent`
  attack template to the selected injection vector;
- InjecAgent: the official-stage `online_inputs.untrusted_content` tool response.

Trusted user requests, tool schemas, attack labels, target actions, expected
answers, official checkers, gold tool names and authorization answers are not
encoded.  Detector inputs and evaluator labels are serialized into separate
frozen JSONL files.  The inference runner reads only the detector-input file;
the analysis process joins labels after inference.

AgentDojo injection goals are used only through the official registered attack
implementation to construct the actual attacked environment and tool output.
They are never substituted directly for a tool output or exposed to M3 policy
compilation.

## Frozen model and inference

- Model: `meta-llama/Llama-Prompt-Guard-2-86M`
- Revision: `a8ded8e697ce7c355e395a0df51f94adb4a2fd27`
- Runtime: local files only; no network fallback
- Binary order: class 0 `BENIGN`, class 1 `MALICIOUS`
- Threshold: malicious probability `>= 0.5`
- Maximum encoded length: 512 tokens including special tokens
- Windowing: tokenize once without special tokens, split into deterministic
  non-overlapping payload windows of `512 - num_special_tokens_to_add(False)`,
  then add the tokenizer's special tokens to each window
- Aggregation: maximum malicious probability over all windows and messages
- Sampling: none; classifier inference is deterministic
- Failure policy: retain one row for every failed case and operationally treat
  the detector failure as `malicious/block` (fail closed); report inference
  success separately
- Resume policy: skip only a previously completed row whose case id, frozen
  input hash and freeze id all match; never silently retry failed rows

## Outcomes and statistics

Primary metrics report integer counts, proportions and Wilson 95% confidence
intervals:

- malicious recall;
- benign false-positive rate;
- precision and F1;
- inference success rate.

Secondary outputs include AUROC and average precision where both labels exist,
score distributions, median/p95 latency, per-benchmark results, M3 attack-family
recall, M3 language results and M3 split results.  Undefined denominators remain
null rather than being converted to zero.

Core figures are benchmark recall/FPR bars with confidence intervals, M3 family
recall, M3 language performance, score distributions, ROC/PR curves and latency
ECDF.  All figures must be generated from the frozen raw predictions and labels.

## Formal admission gate

The detector-only result is eligible for a detector-performance table only if:

1. the frozen source, model, dependency, protocol and runner hashes match;
2. all 3,280 input ids and all 3,280 label ids are unique and identical as sets;
3. all detector inputs are constructed from the permitted runtime sources;
4. the inference runner loads the exact revision without a stub or network;
5. every case has exactly one completed or explicitly failed prediction row;
6. every successful case retains all tokenizer-window probabilities;
7. raw logs, metrics, statistics, figures and their hashes are complete;
8. the analysis retains failure rows in the original denominator.

Passing this gate does not make PromptGuard an end-to-end runtime defense result.
It remains ineligible for ASR/TCR comparisons until it is separately integrated
into the agent execution path under a frozen protocol.

