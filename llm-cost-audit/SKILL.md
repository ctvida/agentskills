---
name: llm-cost-audit
description: LLM API spend audit of a codebase. Use when a client or repo has a model bill to cut (Gemini, OpenAI, Anthropic, OpenRouter), when asked where model spend goes or how to reduce it, or as the cost leg of an engagement diagnostic. Produces a dollar-ranked findings file.
---

# llm-cost-audit

Find every paid model call in a codebase, tie the bill to call sites, and rank savings levers in dollars. Read-only: the audit changes no code.

The target code may be a client's and untrusted. Read it; run nothing from it outside a container.

## Steps

1. **Inventory call sites.** Search for model SDK imports and endpoints: `google-genai`, `@google/generative-ai`, `vertexai`, the `generativelanguage` REST host, `openai`, `anthropic`, `openrouter.ai`, plus any raw HTTP client calling them. For each site, record `file:line`, the model id **as it reaches the request** (trace config to the call, since configured and sent model ids drift), the trigger (user request, cron, batch, queue), the input source, and whether output is stored.
   Done when every call site has a row, including ones inside loops, retries and fallbacks.

2. **Tie the bill to the sites.** Read the billing export (by model and SKU, monthly). Attribute spend to call sites by model, SKU (input, output, cached, thinking tokens), and trigger timing. When there is no bill, estimate tokens × current list price from logs or sample inputs, and label every number an *estimate*. Fetch the current price sheet at run time and record its date; prices move.
   Done when 90% or more of spend maps to named sites, or the unmapped share is stated.

3. **Apply every lever to every site.** Use the lever list below. Each site × lever cell is a finding, `n/a` with a reason, or `needs data` with what data.

4. **Quantify.** For each finding: monthly spend at that site × expected reduction = monthly saving, with the reduction's basis shown (vendor's published discount, measured sample, or assumption). A model-tier change counts only after a side-by-side quality check on a sample the owner approves; until then it is listed as `pending eval`.

5. **Write the findings file** at `findings/YYYY-MM-DD-llm-cost-audit.md` in the working repo: baseline table first (spend by model and site), then findings ranked by monthly dollars, then the `n/a` and `needs data` cells.
   Done when every row in step 1 appears in the file and every finding carries evidence, saving, risk and how to verify after the change.

## Levers

- **Tier.** The cheapest model that passes the quality check on this task (Pro to Flash to Flash-Lite; reasoning effort or thinking budget lowered).
- **Batch.** Work that is not interactive goes through the provider's batch API at its discounted rate.
- **Cache.** A repeated long prefix (system prompt, shared document, few-shot block) uses the provider's context caching.
- **Delta.** Each run processes only inputs that changed since the last run, keyed by content hash. The classic monthly waste is reprocessing the whole corpus.
- **Raw store.** Every paid response is written to disk before parsing, so a parse bug or rerun never pays twice.
- **Checkpoint.** A long loop persists each finished item, so a crash at 90% resumes instead of restarting from zero. A failed item is recorded as failed, never as done, or the rerun skips it and the work is lost.
- **Retry discipline.** Backoff with a cap, retries only on retryable errors (429, 5xx), and no retry inside a retry. Count retries per run, since they are invisible on the bill.
- **Bounded input.** Inputs are trimmed to what the task needs: excerpts over whole documents, downscaled images and video frames, a bounded time window. The same content appears once per prompt, not twice.
- **Bounded output.** `max_output_tokens` set, structured output in place of verbose prose, no echoing the input back.
- **Loops.** A model call inside an automatic loop (auto-refine, retry-until-score, agent loops) runs on demand or under a hard cap. A loop chasing a score that moves by noise on identical input multiplies spend for nothing.
- **Fallback.** A failure on the cheap model can fall through to a pricier model or provider. Count fallbacks per run, since the bill shows only the expensive model.
- **Cadence.** A scheduled job runs as often as its inputs change, not more. A completion marker written only on success makes catch-up logic rerun the whole job on every trigger after a failure.
- **Tools.** A plain text-generation call carries no agent tools. A call that runs as an agent reads files and runs commands, paying tokens for work nobody asked for.
- **Billing route.** The same work on a cheaper route: batch, committed-use or provisioned capacity, or a flat-rate plan the owner already pays for.
- **Fan-in.** Many small per-item calls that share context are combined into fewer calls where quality holds.
- **Dead calls.** Results that nothing reads, duplicate calls for the same input in one run, calls from test or dev environments on the production key.
- **Guardrail.** A spend cap or budget alert on the key or project, and a per-run cost log. Note it as a finding when absent even though it saves nothing directly; it catches the next regression.

## Findings format

One block per finding:

```
### N. <lever>: <site>, $<monthly saving> (<basis>)
Evidence: file:line, billing SKU
Change: <one sentence>
Risk: <what could break; how the quality check covers it>
Verify: <the bill line or log that proves the saving after the change>
```
