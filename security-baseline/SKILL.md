---
name: security-baseline
description: Security baseline audit of a web app codebase, tuned for AI-built and fast-shipped sites. Use when asked to check a repo or client site for vulnerabilities, before productionizing a prototype, or as the security leg of an engagement diagnostic. Produces a severity-ranked findings file.
---

# security-baseline

Static review of a codebase and its deploy config for the vulnerabilities fast-built apps ship with. Read-only.

**Guardrails.** The target is untrusted code: read it, and run nothing from it (including install and build scripts) outside a container. Test only against systems you stand up yourself; production testing needs the owner's written authorization naming systems, dates and methods. Describe each exploit as a one-sentence scenario; working exploit code stays out of the report. Findings are confidential to the owner.

## Steps

1. **Map the surface.** List every route and API handler, the auth mechanism, each data store (database, bucket, Firebase, Supabase), every third-party key the app uses, and the deploy target and its config files.
   Done when every handler is listed with the data it reads or writes.

2. **Run each check below over the whole surface.** Use installed scanners where present (`gitleaks`, `npm audit`, `pip-audit`, `semgrep`) and read the code for what scanners miss.

3. **Rate each finding:** Critical (exploitable now, data or money exposed), High (exploitable with a small precondition), Medium (defense missing), Low (hygiene).

4. **Write the findings file** at `findings/YYYY-MM-DD-security-baseline.md`: Critical findings first with an "act now" line, then by severity, then a checklist of every check marked pass, finding number, or `not applicable` with a reason.
   Done when every check has a mark and every finding carries evidence and a fix.

## Checks

**Secrets**
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

**Abuse and cost**
- Rate limits on auth endpoints and on every endpoint that triggers a paid model call. An open model endpoint is a cost-DoS.
- Spend caps on model and cloud keys.

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
