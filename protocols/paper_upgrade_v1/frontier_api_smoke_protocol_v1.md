# Frontier API two-vendor smoke protocol v1

## Scope

This protocol qualifies OpenAI and Anthropic model transports for later paper matrices. It is not a formal effectiveness experiment and never registers a model slot by itself.

## Safety boundary

- Credentials remain only in ignored `config/project.local.env` and request headers.
- Logs record `set_redacted`, model IDs, endpoint origin, payload hash, latency and usage; they never record tokens or authorization headers.
- The smoke uploads only two fixed synthetic sentences from `smoke_frontier_api_models.py`. It does not upload M3 cases, public-benchmark cases, experiment outputs, failures, unpublished drafts or private data.
- The client makes exactly one request per provider and performs no automatic retry. Failed provider responses remain failed qualification evidence.
- A real request is impossible unless both `--execute` and `M3_FRONTIER_API_CONSENT=yes_for_network_smoke` are present.

## Configuration

Each team member edits only the ignored local file:

```text
OPENAI_API_KEY=<personal key>
FRONTIER_OPENAI_MODEL_ID=<exact current model id>
FRONTIER_OPENAI_BASE_URL=<optional official-compatible HTTPS base>
ANTHROPIC_API_KEY=<personal key>
FRONTIER_ANTHROPIC_MODEL_ID=<exact current model id>
FRONTIER_ANTHROPIC_BASE_URL=<optional official-compatible HTTPS base>
M3_FRONTIER_API_CONSENT=yes_for_network_smoke
```

Do not put real values in `project.env.example`, Git, Markdown, screenshots or chat.

## Plan-only command

This is the default and makes zero network calls:

```powershell
E:\M3_PI_Guard_runtime\promptguard\Scripts\python.exe -B -m experiments.paper_v1.benchmarks.smoke_frontier_api_models
```

Current result: `plan_only_no_network`, configured providers 0/2, network calls 0. This state is not a blocker in code; it is an external credential/model-selection/consent blocker.

## Explicit network smoke

Run only after the project owner approves the two selected model IDs and expected cost:

```powershell
E:\M3_PI_Guard_runtime\promptguard\Scripts\python.exe -B -m experiments.paper_v1.benchmarks.smoke_frontier_api_models --execute
```

After two successful smokes, freeze provider-reported model identifiers, request schema, pricing date, usage counters and smoke manifest. Then create a non-overwriting model-registry revision and public-benchmark freeze revision. Do not edit v1/v2 freezes or call a smoke a formal result.

## Formal follow-up

Formal API experiments require a separately approved cost/query budget, the same frozen cases and conditions as local models, complete provider logs, zero silent retries, explicit failure denominators and a non-overwriting experiment manifest. Exact current model names and pricing must be verified at execution time because provider catalogs change.
