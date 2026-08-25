---
name: agents-md
description: Use when creating, reviewing, or trimming an AGENTS.md or CLAUDE.md file, when an agent config file has grown past a screen, when repeated agent mistakes suggest the instructions file is wrong, or when adopting a repo that has no agent config yet.
---

# agents-md

## Overview

An AGENTS.md loads on **every** request in the repo, so its cost is permanent
while its benefit is not.

**Core principle: the ideal AGENTS.md is small, focused, and points elsewhere.**
Just enough to start working, with breadcrumbs to the rest.

Conventions here follow https://www.aihero.dev/a-complete-guide-to-agents-md.

## The minimum, and it really is the minimum

Three things belong in the root file. Add a fourth only when you can name the
mistake it prevents.

1. **One sentence saying what the project is.** This works like a role prompt
   and anchors every decision after it. "A React component library for
   accessible data visualization."
2. **The package manager**, when it isn't the default one for the ecosystem.
   Say `pnpm workspaces` or agents will emit npm commands. Point at the
   evidence (a lockfile, a CI build command) so it stays checkable.
3. **Build / typecheck / test commands**, only when non-standard. Stock
   `dev` / `build` / `lint` need no documentation.

## What to leave out

| Leave out | Why |
|---|---|
| `init`-generated content | It floods the file with what's "useful for most scenarios". Write it yourself or not at all. |
| Directory trees and file paths | They go stale silently, then actively mislead. Describe capabilities and the shape of the project instead. |
| Advice the model already has | "Write clean code", "add error handling" cost tokens and change nothing. |
| Contradictory style rules | Several contributors each adding a preference makes a file nobody can follow. |
| Anything scoped to one domain | Own file, loaded when that domain is in play. |

Domain concepts beat file paths, because concepts stay true when the tree
moves. "An organization owns groups; a group owns members" survives a refactor
that `src/lib/orgs/` does not.

## Progressive disclosure

Everything domain-specific moves out and is referenced by one line: `For
TypeScript conventions, see docs/TYPESCRIPT.md.` Those files may reference
further files. The tree is discoverable and loads only along the branch the
task needs.

| Where it goes | When |
|---|---|
| Root `AGENTS.md` | Relevant to *every* task in the repo |
| A separate doc, referenced by one line | Relevant to one domain |
| Nested further down that doc | A sub-case of that domain |

## Monorepos

Multiple AGENTS.md files merge with the root. Root carries the monorepo's
purpose, navigation, and shared tooling; each package carries its own purpose,
stack, and conventions. **Don't overload any level** — a bloated package file
is the same failure one directory down.

## CLAUDE.md

Claude Code reads `CLAUDE.md`; most other tools read `AGENTS.md`. Write one
file and symlink, so the two can never drift.

**Check which one is already the symlink before touching either.** In a repo
adopted earlier, `AGENTS.md` is often the link and `CLAUDE.md` holds the text.
Linking blind then produces `AGENTS.md -> CLAUDE.md -> AGENTS.md`: every read
fails with `OSError: Too many levels of symbolic links`, the content is gone
from the worktree, and if it is committed it is gone from git too. This
happened on 2026-08-24 in sales-engine and trading-system, and it took down an
unrelated tool that walked the repo.

```bash
ls -l AGENTS.md CLAUDE.md   # first: which is a link, and where does it point?
ln -s AGENTS.md CLAUDE.md   # only when AGENTS.md is the real file
```

**Edit the real file, never the symlink path.** Writing through the link works
until someone re-points it; then the edit lands in the wrong file or in a loop.

## Reviewing an existing file

Models follow roughly 150-200 instructions consistently, and this file spends
from the same budget as the task. So check the size (`wc -w AGENTS.md`); past
~250 words something belongs in a referenced doc.

Then go line by line with one question: **would this change what the agent does
on a task that has nothing to do with it?** If not, it moves out or is deleted.
Delete on sight: generated file tours, path tables, restated framework docs,
project history, anything phrased as encouragement.

## Common mistakes

- **Writing it for a human.** Onboarding belongs in `README.md`. This file is a
  prompt, and its reader has already read the code.
- **Documenting the tree "so the agent can navigate".** It can navigate. It
  cannot tell that your description went stale three commits ago.
- **Adding a rule after every mistake.** Ask first whether it is enforceable in
  code: a lint rule, a hook, a CI check. Enforcement binds. A prompt only binds
  an agent that is reading it.
- **Letting AGENTS.md and CLAUDE.md diverge.** Symlink them.
