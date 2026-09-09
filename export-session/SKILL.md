---
name: export-session
description: Export Claude conversations to searchable markdown with auto-generated summaries and tags. Use this whenever you want to save a valuable conversation for later reference—either the current session or a past session by ID. Works globally across projects. No manual tagging required; Claude generates semantic tags and a concise summary automatically. Optionally add a personal note or reminder. Output goes to <repo-root>/.workbench/sessions/ organized by semantic tags.
compatibility: Requires claude CLI (Claude Code) or local inference (Ollama/MLX) or OpenRouter API key. Haiku or equivalent small model recommended.
---

# export-session

## Run it

```bash
scripts/export-session.sh                       # current session
scripts/export-session.sh <SESSION_ID>          # a past session
scripts/export-session.sh --note "..."          # attach a note
scripts/export-session.sh --project <path>      # skip the project prompt
scripts/export-session.sh --new                 # force a separate file
```

That script is the whole interface. It resolves the session, generates the
summary and tags, redacts, and writes the file. Do not reimplement any of that
here; run it and report what it prints.

**First, though: [write the resume point](#before-exporting-write-the-resume-point).**
It goes in a repo file and has to be confirmed by the operator, so it cannot be
done after the export.

Setup, model configuration and troubleshooting are in `README.md`, not here.

## What it does

Export conversations from Claude Code (or other Claude harnesses) to markdown with auto-generated summaries and semantic tags.

## When to use

- Save valuable conversations before they're lost
- Build a searchable archive of insights, strategies, code patterns, or learnings
- Minimize digital clutter by only exporting sessions worth keeping
- Access past conversations without resuming the full session

## Before exporting: write the resume point

A session that ends with unfinished work leaves a resume point, so the next
session does not re-derive what this one already knew. Do this **before**
running the export.

**Only when there is something to resume.** If the work is done — shipped,
verified, nothing blocked, no open question — write no resume point and say so
in one line. A next action invented for a finished session is worse than none:
it reads as real to the next session and to any view that surfaces it. Ask
"what would a fresh session be stuck on?", not "what could be done next" —
there is always something that could be done next.

### Finished work gets closed, not left blank

Silence is not disposition. A project whose objective was met still renders as
open, and whatever else infers next actions will eventually write it a new one
— so the session that met the objective is the one that has to say so.

Check the objective this session was working to (the existing resume point) and
its done-when, item by item, against what actually happened. If every item is
settled by a command or a file:

1. Say which done-when items are met and what settles each — a command's
   output, a path, a commit. Evidence, not assertion.
2. **Propose completion and wait.** The operator confirms or names what is
   still open. Never conclude a project silently.
3. On confirmation, record it through whatever mechanism this repo's
   `CLAUDE.md` names for completion, which also clears the resume point. If it
   names none, say the objective is met and leave the record alone.

Completion recorded this way is a **proposal that stops the work generating
more work**, not an archive. Archiving, un-tracking, or moving anything stays
the operator's, through their own review.

If any done-when item is unsettled, this section does not apply: write the
resume point as below, scoped to what is left.

### Write an objective, not a task

A resume point naming one step makes the operator the runtime: the next session
does that step, stops, and comes back for instructions. Over a week that is
constant babysitting, which is the opposite of the target state. Write what a
manager hands a capable report — the goal, how you'll know it's met, and the
authority to keep going — not a ticket.

The resume point has four parts, in this order:

1. **Objective** — the outcome, and why it matters. Not "run X", but what is
   true when X has been run and everything it implies is done.
2. **Plan** — the ordered steps that get there, in the project file. The
   resume point points at them; it does not inline them.
3. **Standing instruction** — explicit permission to continue: work the plan
   top to bottom in one pass, do not stop after step 1, commit per step, and
   if a step blocks, record the blocker in the project file and continue with
   the next independent step.
4. **Done-when** — a short checkable list. Each item is something a command or
   a file can settle, not a feeling. This is the stop condition; without it,
   "continue until done" has no end and the agent either quits early or runs
   forever.

The smallest-first-action rule governs *starting*, never *scope*: name an easy
entry point, then state the whole objective. A resume point scaled down to one
step is that rule misapplied.

Keep it to a paragraph the operator can read in a card. Findings, blockers, and
the plan itself belong in the project file's body, not in the field.

### Procedure

1. **Find the destination.** Use the file or frontmatter field named by this
   repo's `CLAUDE.md`. If it names none, use `ops/next-session-prompt.md`.
2. **Draft the objective** in the four-part shape above. Put the plan,
   the findings this session produced, and any open question a fresh session
   would otherwise re-derive into the project file's body — the resume point
   itself is a snapshot, so rewrite in place; never append.
3. **Show the draft and wait for confirmation** before writing. The operator
   edits or accepts. Never write it silently.

## Re-exporting a session you continued

**Re-exporting appends, in place, by default.** If the target folder already
holds an export whose frontmatter records this session id, the exporter diffs
the turns and writes only the ones added since, under a `### Continued <date>`
heading. It does not rewrite the earlier text and it does not make a second
file. Re-exporting a session that has said nothing new prints `already up to
date` and writes nothing.

This is the normal case: something surfaces during an export, you keep working,
and you export again. One file per session, growing.

`--new` forces a separate file instead. Use it when the session genuinely
turned into different work and one record would bury it.

**The destination is sticky per session.** Once a session has been exported
somewhere, every later export of that session goes back to the same folder,
even if you run it from a different repo or directory. Without that, the search
for an existing export only looks in the folder being written to, so exporting
one session from two places produced two files. Recorded in
`~/.local/state/export-session/destinations.json`, which is machine-local and
deliberately not inside this skill.

Passing `--project` explicitly overrides the sticky destination, which is the
way to move a session's record on purpose. A missing or corrupt state file
falls back to the computed destination rather than failing the export.

## What gets exported

- **Full conversation**: All prompts and responses from the session (excluding AI meta-commands — see below)
- **Auto-generated summary**: One sentence, max 60 characters (e.g., "Fundamental analysis backtesting strategy")
- **Semantic tags**: 3-5 tags inferred from content (e.g., `[trading, backtesting, strategy, learning]`)
- **Metadata frontmatter**: Date, session ID, project path, optional user note, model used
- **Filename**: `YYYY-MM-DD-HHmm-slug.md` derived from summary
- **Location**: `<repo-root>/.workbench/sessions/`

### What is excluded

Slash commands that are about the AI/harness rather than the work topic are automatically filtered out, along with their responses:

| Category | Examples |
|---|---|
| Token / cost queries | `/usage`, `/cost`, `/tokens`, `/billing`, `/quota` |
| Context / memory | `/context`, `/memory`, `/history` |
| Model / config | `/model`, `/settings`, `/config`, `/version` |
| Session management | `/session`, `/reset`, `/clear`, `/exit`, `/quit` |
| Account / auth | `/whoami`, `/login`, `/logout`, `/account`, `/profile` |
| Harness utilities | `/help`, `/status`, `/doctor`, `/debug`, `/trace`, `/reload-plugins`, `/plugin`, `/permissions`, `/upgrade`, `/feedback`, `/report`, `/bug` |

These turns add no value to the exported record and are stripped before writing the markdown file.

### Redaction (protected terms)

Exports are **verbatim**, and they land in a tracked directory. Anything that
surfaced in the conversation — including content imported into context from
personal files like `~/.agents/SOUL.md` — would otherwise be committed.

Before the file is written, every term in `~/.agents/redact-terms.txt` is
replaced with `[REDACTED]`. One term per line, `#` comments ignored; matching is
case-insensitive and word-bounded (so `tuck` will not maul `Kentucky`), longest
term first. Override the path with `EXPORT_SESSION_REDACT_FILE`.

**The terms deliberately do not live in this skill.** This skill is synced
across machines and tools by skillshare, so a name hardcoded here would leak
exactly where the rule is trying to prevent. If the file is absent, nothing is
redacted — the right default for anyone who has not opted in — and the run says
so on stderr.

Scrubbing happens *before* the write, never as a fix-up afterwards: a file that
has to be corrected post-write has already been committable for however long
that took.

## Frontmatter example

```yaml
---
date: 2026-07-12
session_id: fb62a3e8-e2e9-4637-bbd8-cec06dd2a49e
summary: Fundamental analysis backtesting strategy
tags: [trading, backtesting, strategy, learning]
project: ~/repos/agentic-os
user_note: Test this against Q3 earnings data
model_used: haiku
---
```

## How it works

1. **Session extraction**: Retrieves the specified session (current or by ID) via Claude introspection
2. **Summary + tags**: Claude reads the conversation and generates semantic tags and a one-line summary
3. **Project inference**: Automatically detects project root and target folder, or prompts interactively if ambiguous
4. **Directory creation**: Creates `.workbench/sessions/` if needed
5. **Markdown formatting**: Exports conversation with clean formatting and metadata
6. **Output confirmation**: Shows filename, location, tags, and summary

## Project path resolution

If you're in a git repository, exports default to `<repo-root>/.workbench/sessions/` automatically. No prompt unless you want a specific project subfolder.

If you want to export to a specific project instead:

```
Export to repo root or a specific project?
  • (leave blank for ~/repos)
  • projects/arctusai-launch
  • projects/fundamental-analysis-agent
  
Enter project path (or leave blank for repo root): projects/fundamental-analysis-agent
```

Or skip the prompt with `--project <path>`:

```bash
export-session --project projects/fundamental-analysis-agent
export-session --project .  # Explicitly use repo root
```

If not in a git repo, defaults to `~/.workbench/sessions/`.

## Edge cases

- **Current-session detection** (`scripts/get-session-id.py`, first hit wins):
  1. Harness session-id env var (`CLAUDE_SESSION_ID`, `CLAUDE_CODE_SESSION_ID`, `SESSION_ID`).
  2. Newest `*.jsonl` in `~/.claude/projects/<cwd with / and . replaced by ->/`.
     Scoped to the current repo — the global `~/.claude/history.jsonl` is never
     used, since it returns whichever open window wrote last.
  3. If several sessions in that dir were modified within 5 minutes, it prints
     the candidates with mtimes and exits 2 — pass an explicit session ID.
  Add `--debug` to print which rule matched.
- **No active session**: Prompts for session ID
- **Session not found**: Explains error and suggests checking `claude --resume`
- **Outside git repo**: Defaults to `~/.workbench/sessions/`
- **Permission issues**: Notifies user, suggests checking directory permissions
- **Past session not in history**: Confirms session ID is valid (check `~/.claude/history.jsonl`)
- **MLX/omlx not found**: Falls back to next available model in priority order

## Example output

```
✓ Exported to: ~/repos/agentic-os/.workbench/sessions/2026-07-12-1447-fundamental-analysis-backtest.md

Summary: Fundamental analysis backtesting strategy
Tags: [trading, backtesting, strategy, learning]
Session: fb62a3e8-e2e9-4637-bbd8-cec06dd2a49e
Note: Test this against Q3 earnings data
```

## Notes

- Exports preserve the full conversation verbatim (no editing or summarization of responses)
- Auto-generated tags are semantic, not action-oriented (e.g., `[architecture, debugging]` not `[todo, wip]`)
- Files are immutable once created; create a new export to store updated notes
- Session IDs can be found in `~/.claude/history.jsonl` or via `claude --resume` interactive list
