---
name: security-baseline
description: Security baseline audit of a web app codebase, tuned for AI-built and fast-shipped sites. Use when asked to check a repo or client site for vulnerabilities, before productionizing a prototype, or as the security leg of an engagement diagnostic. Produces a severity-ranked findings file with each serious finding sized in dollars of exposure.
---

# security-baseline

Static review of a codebase and its deploy config for the vulnerabilities fast-built apps ship with. Read-only.

**Guardrails.** The target is untrusted code: read it, and run nothing from it (including install and build scripts) outside a container. Test only against systems you stand up yourself; production testing needs the owner's written authorization naming systems, dates and methods. Describe each exploit as a one-sentence scenario; working exploit code stays out of the report. Findings are confidential to the owner.

**Secrets first.** Before reading the code, run a local secret scanner (`gitleaks` or `trufflehog`) over the clone and its git history. Every file the agent reads goes to the model provider, so when the scan finds live keys, stop and report them; the owner rotates them before model-assisted reading continues.

## Steps

1. **Map the surface.** List every route and API handler, the auth mechanism, each data store (database, bucket, Firebase, Supabase), every third-party key the app uses, and the deploy target and its config files. Include code that runs outside the repo: bots and scheduled scripts on the owner's machine, automation services, other repos. Those hold keys and run unreviewed.
   Done when every handler is listed with the data it reads or writes.

2. **Run each check below over the whole surface.** Use installed scanners where present (`gitleaks`, `npm audit`, `pip-audit`, `semgrep`) and read the code for what scanners miss.

3. **Rate each finding:** Critical (exploitable now, data or money exposed), High (exploitable with a small precondition), Medium (defense missing), Low (hygiene).

4. **Size the exposure** of every Critical and High finding. This is the pricing story: exposure set against the cost of the fix.
   - *Reachable:* which data classes, how many records, which of the owner's customers.
   - *By whom:* anyone on the internet, any logged-in user, or an insider.
   - *Dollar range,* built from the owner's own numbers: key abuse = provider rate limit × unit price × days until noticed (or the spend cap, if one exists); customer loss = annual revenue from the customers whose data is reachable, plus contract penalties in their confidentiality clauses; breach response = notification, forensics and counsel, using a sourced figure cited with its date.
   - Every figure is a range with its assumptions shown; a single precise number overclaims.
   Done when each Critical and High finding has all three, and the fix effort sits beside it.

5. **Write the findings file** at `findings/YYYY-MM-DD-security-baseline.md`: an exposure table first (finding, reachable, by whom, dollar range, fix effort), then Critical findings with an "act now" line, then by severity, then a checklist of every check marked pass, finding number, or `not applicable` with a reason.
   Done when every check has a mark and every finding carries evidence and a fix.

## Checks

**Secrets**
- Secret files readable only by their owner (mode 0600), and the secrets boundary covers every repo and service, not just the main one.
- Keys in the tree and in git history, including unprefixed keys in assignment position (`api_key = "..."`), not only vendor-prefixed ones.
- Server keys in the client bundle: any secret behind `NEXT_PUBLIC_`, `VITE_`, `REACT_APP_` or a Firebase/Gemini key called directly from browser code. A model key in the browser is both a leak and an open bill.
- `.env`, `.git` or backups reachable over HTTP from the deploy.

**Access control**
- Every handler that reads or writes data checks auth on the server. A client-side route guard alone is a finding.
- Ownership: an object id taken from the request is checked against the caller (one customer reading another's records).
- Database-level policy: Supabase RLS enabled on every table, Firebase/Firestore rules not open, buckets not public-writable.
- Demo, default or shared credentials; admin routes; password storage (a slow hash, never plain or fast-hashed).
- Session cookies `HttpOnly`, `Secure`, `SameSite`; token expiry.

**Injection**
- SQL or NoSQL built by string concatenation.
- XSS: `dangerouslySetInnerHTML`, `innerHTML`, unescaped templates, rendering model output as HTML.
- SSRF: server fetches a URL the user supplies.
- Path traversal on file reads and uploads; upload type and size limits.
- Prompt injection: untrusted content (scraped pages, user text, social posts) reaching a model that can call tools, write data, or produce output rendered to other users.
- Model authority: a field in model output that triggers an irreversible action (send, delete, pay, publish) passes a deterministic check or a human gate first.
- Least privilege for model calls: a text-generation call runs with no tools and outside the code tree.

**Abuse and cost**
- Rate limits on auth endpoints and on every endpoint that triggers a paid model call. An open model endpoint is a cost-DoS.
- Spend caps on model and cloud keys, covering total spend across keys rather than one key.
- Outbound sends (email, SMS, social posts) capped per day.

**Filters that never held**
- Every redaction list, blocklist and exclusion rule is tested against a real positive sample. A filter built and wired but never fed its terms is a no-op that reads as protection.
- The match covers every field where the term can appear (a company named only inside a title escapes a company-field check).

**Configuration**
- CORS not `*` on authenticated routes; security headers (CSP, HSTS, frame options).
- Debug mode, stack traces or verbose errors in production.
- Dependencies with known vulnerabilities; a committed lockfile.
- Personal data collected without a privacy policy; third-party platform API terms honored.

## Findings format

```
### N. [Severity] <title>
Evidence: file:line (or URL)
Scenario: <one sentence: who does what, and what they get>
Fix: <the change>
Effort: S | M | L
```
