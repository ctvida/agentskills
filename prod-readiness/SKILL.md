---
name: prod-readiness
description: Production-readiness review of a prototype or AI-built app. Use when asked whether a site or service is ready for real customers, what it needs to run reliably, or as the operations leg of an engagement diagnostic. Produces a gap list ranked by blast radius, sized for a SOW.
---

# prod-readiness

Rate how a codebase is built, deployed, tested, observed and recovered, and turn each gap into a sized work item. Read-only. The target may be untrusted: read it, and run nothing from it outside a container.

**Secrets first.** Before reading the code, run a local secret scanner (`gitleaks` or `trufflehog`) over the clone and its git history. Every file the agent reads goes to the model provider, so when the scan finds live keys, stop and report them; the owner rotates them before model-assisted reading continues.

## Steps

1. **Inventory the operation.** Build and deploy path, environments, CI, tests, scheduled jobs (including bots on a person's machine or in automation services), data stores, backups, monitoring, and who gets alerted.
   Done when each item is named or recorded as absent.

2. **Rate every check below** as `present`, `partial` or `missing`, each with evidence (`file:line`, config, or the absence searched for).

3. **Rank the gaps by blast radius**: data loss, then money, then customer-visible outage, then silent wrong output, then developer friction.

4. **Size each gap** S (under a day), M (1 to 3 days), L (a week or more), so the list prices directly into a SOW.

5. **Write the findings file** at `findings/YYYY-MM-DD-prod-readiness.md`: the ranked gaps first, then the full scorecard.
   Done when every check has a rating with evidence.

## Checks

**Build and deploy**
- Reproducible build: a committed lockfile and pinned runtime version.
- Separate dev and production environments with separate keys and data.
- Deploys from CI on merge, with a known rollback path.

**Tests**
- Tests exist on the paths that move money or data and on each scheduled job's core logic.
- CI runs them on every pull request.
- Tests write to fixtures or temp stores only. A test that writes to live data or a live queue is a finding.

**Scheduled and batch jobs**
- Each job is idempotent: a rerun produces the same result without duplicating work or cost.
- Long jobs checkpoint per item and resume after a crash. The checkpoint tells failed from done, and a re-fetch keeps state already verified.
- One bad item (a 404, a malformed record) is logged and skipped. A queue cursor that advances only after a clean batch lets one poison item stop every later run.
- Completion markers are written after the work they mark. A marker written early hides a failure; one never written triggers repeat runs.
- The job is tested under the scheduler's own environment (PATH, HOME, working directory, credentials, shell quoting), which differs from the developer's shell.
- Runs that never fired (host asleep, cold start, disabled trigger) are detected, not only runs that failed.
- Each run is observable after the fact: start, finish, item counts, cost, exit status.
- A missed or failed run alerts a person. Silence counts as a failure: a probe that checks the job actually ran.

**Failure handling**
- Errors fail loudly: no swallowed exceptions, no empty `catch`, no `|| true` on a step that matters, and expired auth surfaces as an error rather than empty data.
- A job that fails exits nonzero, so the scheduler's status is true. A log line saying "failed" under a zero exit reads as healthy.
- Decisions that must be right (gates, approvals, eligibility) are made by code and exit codes. A model call may advise; it never decides them.
- Retries back off and cap, on retryable errors only.
- External calls have timeouts.

**Data**
- Backups exist, run on a schedule, and a restore has been tested.
- Schema changes go through versioned migrations.

**Secrets and config**
- Secrets come from the platform's secret store or environment, never the repo.
- Config that selects a model, endpoint or plan is read where it is used (trace one value from config to the request).

**Efficiency (non-model spend)**
- API and database responses return the fields the page uses: no overfetching whole records, no N+1 query loops.
- Images and video served at display size in modern formats; page weight measured on the key pages.
- Compute matches the load: a monthly job does not run on always-on servers, and idle environments scale to zero.
- Egress and logging volume checked against the bill; verbose debug logging off in production.

**Ownership**
- A runbook for the top three failure modes.
- Monitoring on uptime and error rate, with alerts routed to a person.
