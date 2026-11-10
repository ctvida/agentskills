---
name: llm-cost-audit
description: LLM API spend and efficiency audit of a codebase, covering working code that overspends as well as defects. Use when a client or repo has a model bill to cut (Gemini, OpenAI, Anthropic, OpenRouter), when asked where model spend goes or how to reduce it, or as the cost leg of an engagement diagnostic. Produces a dollar-ranked findings file.
---

# llm-cost-audit

Find every paid model call in a codebase, tie the bill to call sites, and rank savings levers in dollars. Most savings sit in code that works: payloads larger than the task needs, items sent one call at a time, work handed to a model that code could do. Read-only: the audit changes no code.

The target code may be a client's and untrusted. Read it; run nothing from it outside a container.

**Secrets first.** Before reading the code, run a local secret scanner (`gitleaks` or `trufflehog`) over the clone and its git history. Every file the agent reads goes to the model provider, so when the scan finds live keys, stop and report them; the owner rotates them before model-assisted reading continues.

## Steps

1. **Inventory call sites.** Search for model SDK imports and endpoints: `google-genai`, `@google/generative-ai`, `vertexai`, the `generativelanguage` REST host, `openai`, `anthropic`, `openrouter.ai`, plus any raw HTTP client calling them. For each site, record `file:line`, the model id **as it reaches the request** (trace config to the call, since configured and sent model ids drift), the trigger (user request, cron, batch, queue), the input source, and whether output is stored.
   Done when every call site has a row, including ones inside loops, retries and fallbacks.

2. **Tie the bill to the sites.** Read the billing export (by model and SKU, monthly). Attribute spend to call sites by model, SKU (input, output, cached, thinking tokens), and trigger timing. When there is no bill, estimate tokens × current list price from logs or sample inputs, and label every number an *estimate*. Fetch the current price sheet at run time and record its date; prices move.
   Spend that maps to no call site in the repo usually runs from code outside it: scripts or bots on someone's machine, automation services, notebooks, another repo. Inventory those with the owner.
   Done when 90% or more of spend maps to named sites, or the unmapped share is stated.

3. **Measure the payloads.** For each site in the top 80% of spend (the tail rarely repays the capture work), capture real requests and break each prompt into its parts: instructions, examples, data, serialization overhead (keys, whitespace, markup), and media. Record tokens per part and what share of the data the output actually uses. Twenty requests per site shows what a prompt is made of; this measures composition, not an average, so more adds little.
   Done when each of those sites has a token breakdown and a used-versus-sent ratio.

4. **Apply every lever to every site.** Use the lever list below. Each site × lever cell is a finding, `n/a` with a reason, or `needs data` with what data.

5. **Quantify.** For each finding: monthly spend at that site × expected reduction = monthly saving, with the reduction's basis shown (vendor's published discount, measured sample, or assumption). A model-tier change counts only after a side-by-side quality check on a sample the owner approves; until then it is listed as `pending eval`.

6. **Write the findings file** at `findings/YYYY-MM-DD-llm-cost-audit.md` in the working repo: baseline table first (spend by model and site), then findings ranked by monthly dollars, then the `n/a` and `needs data` cells.
   Done when every row in step 1 appears in the file and every finding carries evidence, saving, risk and how to verify after the change.

## Levers

Grouped by what they cut. Every site gets every lever.

**Send less per call**
- **Payload.** Send only the fields the task reads. Strip markup, pretty-print whitespace and repeated long keys; prefer compact formats (CSV or terse keys over verbose JSON for tabular data); pass media by file reference rather than inline base64, at the resolution the task needs. The used-versus-sent ratio from step 3 sizes this lever.
- **Fixed overhead.** Measure what every call carries before the task: system prompt, tool schemas, framework or CLI-wrapper context, config files loaded per call. One wrapper carried 25.8k tokens per call that a bare call cut to 0.6k. A plain text-generation call carries no agent tools; an agent call reads files and runs commands, paying for work nobody asked for.
- **Prompt sediment.** System prompts gain a rule after every past bug. Prune rules the model follows by default and rules for features that no longer exist.
- **Bounded input.** Excerpts over whole documents, downscaled images and video frames, a bounded time window. The same content appears once per prompt, not twice.
- **Bounded output.** `max_output_tokens` set, structured output in place of prose, no echoing the input back. Where the price sheet charges more for output than input, output cuts pay first.

**Call less**
- **Filter first.** Items that need no model skip the call: already processed, unchanged, already read, empty, or decidable by a rule.
- **Code first.** Work code can do runs before the call: counting, sums, filtering, sorting, joins, formatting, rule-based classification, date math. The model gets pre-digested input and does only the judgment. Cache the model's judgment, and recompute the figures in code on every run so a cache never serves stale numbers.
- **Flatten.** Many calls over items that share instructions become one call over a list, sized to the model's context and output limits, with each result saved as it lands. Deduplicate identical inputs first, and group items by shared context so it is sent once.
- **Delta.** Each run processes only inputs that changed since the last run, keyed by content hash. The classic monthly waste is reprocessing the whole corpus.
- **Response cache.** An identical request (same input, same prompt version) returns the stored answer, keyed by content hash plus prompt version. A cache miss that silently triggers a full recompute is a finding.
- **Loops.** A model call inside an automatic loop (auto-refine, retry-until-score, agent loops) runs on demand or under a hard cap. A loop chasing a score that moves by noise on identical input multiplies spend for nothing.
- **Cadence.** A scheduled job runs as often as its inputs change, not more. A completion marker written only on success makes catch-up logic rerun the whole job on every trigger after a failure.
- **Dead calls.** Results that nothing reads, duplicate calls for the same input in one run, calls from test or dev environments on the production key.

**Pay less per call**
- **Route.** Each task type goes to the cheapest model that passes its own check. One model for every task is the common default and the common overspend.
- **Tier and effort.** Within a task, the smallest model and the lowest reasoning effort or thinking budget that pass. One review task scored 6 of 6, twice, at low effort and ran about 10x faster than at high.
- **Prompt cache.** Order prompts static-first (instructions, examples, shared documents, then the variable part), so the prefix is identical across calls and the provider's implicit or explicit caching can hit. Explicit caches bill storage by time; check that the call rate repays it.
- **Batch.** Work that is not interactive goes through the provider's batch API at its discounted rate.
- **Billing route.** The same work on a cheaper route: committed-use or provisioned capacity, or a flat-rate plan the owner already pays for.

**Stop waste**
- **Raw store.** Every paid response is written to disk before parsing, so a parse bug or rerun never pays twice.
- **Checkpoint.** A long loop persists each finished item, so a crash at 90% resumes instead of restarting from zero. A failed item is recorded as failed, never as done, or the rerun skips it and the work is lost.
- **Retry discipline.** Backoff with a cap, retries only on retryable errors (429, 5xx), and no retry inside a retry. Count retries per run, since they are invisible on the bill.
- **Fallback.** A failure on the cheap model can fall through to a pricier model or provider. Count fallbacks per run, since the bill shows only the expensive model.
- **Guardrail.** A spend cap on the project (Gemini offers project spend caps in AI Studio, marked experimental as of 2026-11), a budget alert, and a per-run cost log. A new or widened job is priced on one sample run before it is scheduled. Note an absent guardrail as a finding even though it saves nothing directly; it catches the next regression.

## Findings format

One block per finding:

```
### N. <lever>: <site>, $<monthly saving> (<basis>)
Evidence: file:line, billing SKU
Change: <one sentence>
Risk: <what could break; how the quality check covers it>
Verify: <the bill line or log that proves the saving after the change>
```
