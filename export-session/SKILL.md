---
name: export-session
description: >-
  Export agent conversations to searchable markdown with auto-generated summaries and tags.
  MANDATORY PRE-FLIGHT: Next action is always written (driven by Objective) and verified
  with the operator before running the export script, unless the operator explicitly stated
  in the prompt that no verification is needed. Output goes to <repo-root>/.workbench/sessions/
  organized by semantic tags.
compatibility: Requires claude CLI (Claude Code), agy CLI (Antigravity), or local inference (Ollama/MLX), or OpenRouter API key. Haiku or equivalent small model recommended.
---

# export-session

## MANDATORY PRE-FLIGHT GATE: Resume Point & Verification

**STOP. DO NOT call `scripts/export-session.sh` in the first turn.**

When the operator invokes `/export-session`:

1. **Next action is always written unless there is no legitimate next action.**
   - If the project's objective was completely met (every done-when item settled by a command or file), propose completion to the operator.
   - Otherwise, a resume point MUST be written.
2. **Next action is driven by Objective.**
   - Derive `next_action` directly from `objective.md` or the standing project goal, not just the micro-task touched last.
   - Follow the required four-part shape: Objective, Plan (a pointer), Standing instruction, Done-when.
3. **Verification with the operator:**
   - **Unless stated by the operator in the prompt that no verification is needed** (e.g., "no verification needed", "--no-verify", "just export"):
     - You MUST pause tool execution immediately.
     - Present the draft of `next_action` and `## Operator next steps` in your response.
     - Ask the operator to confirm or edit.
     - **DO NOT run `scripts/export-session.sh` until the operator confirms.**
   - **If the operator explicitly stated in the prompt that no verification is needed**:
     - Write the resume point to the repo file (`_index.md`) and proceed directly to running `scripts/export-session.sh`.

## Run it (Only After Gate Is Cleared)

Run `scripts/export-session.sh` ONLY AFTER:
- The operator confirms the resume point draft, OR
- The operator explicitly bypassed verification in their prompt.

```bash
scripts/export-session.sh                       # current session
scripts/export-session.sh <SESSION_ID>          # a past session
scripts/export-session.sh --note "..."          # attach a note
scripts/export-session.sh --project <path>      # skip the project prompt
scripts/export-session.sh --new                 # force a separate file
```

That script is the export interface. It resolves the session, generates the
summary and tags, redacts, and writes the file. Do not reimplement any of that
here; run it only after the pre-flight gate is cleared and report what it prints.

Setup, model configuration and troubleshooting are in `README.md`, not here.

## What it does

Export conversations from Claude Code, Antigravity, or other harnesses to markdown with auto-generated summaries and semantic tags.

## When to use

- Save valuable conversations before they're lost
- Build a searchable archive of insights, strategies, code patterns, or learnings
- Minimize digital clutter by only exporting sessions worth keeping
- Access past conversations without resuming the full session

## Resume point requirements

A session that ends with unfinished work leaves a resume point, so the next
session does not re-derive what this one already knew. Do this **before**
running the export.

**Next action is always written unless there is no legitimate next action.**
If the work is genuinely done (shipped, verified, nothing blocked, no open question),
write no resume point and propose completion. Ask: "what would a fresh session
be stuck on?", not "what could be done next" -- there is always something that
could be done next.

### Finished work gets closed, not left blank

Silence is not disposition. A project whose objective was met still renders as
open, and whatever else infers next actions will eventually write it a new one,
so the session that met the objective is the one that has to say so.

Check the objective this session was working to (the existing resume point) and
its done-when, item by item, against what actually happened. If every item is
settled by a command or a file:

1. Say which done-when items are met and what settles each -- a command's
   output, a path, a commit. Evidence, not assertion.
2. **Propose completion and wait.** The operator confirms or names what is
   still open. Never conclude a project silently.
3. On confirmation, record it through whatever mechanism this repo's
   governance names for completion, which also clears the resume point. If it
   names none, say the objective is met and leave the record alone.

Completion recorded this way is a proposal that stops the work generating
more work, not an archive. Archiving, un-tracking, or moving anything stays
the operator's, through their own review.

If any done-when item is unsettled, this section does not apply: write the
resume point as below, scoped to what is left.

### Next action is driven by Objective

A resume point naming one step makes the operator the runtime: the next session
does that step, stops, and comes back for instructions. Over a week that is
constant babysitting, which is the opposite of the target state. Write what a
manager hands a capable report: the goal, how you will know it is met, and the
authority to keep going, not a ticket. Derive it directly from `objective.md` or
the standing project goal.

The resume point has four parts, in this order:

1. **Objective**: the outcome, and why it matters. Driven by the project objective, not a micro-task. Not "run X", but what is true when X has been run and everything it implies is done.
2. **Plan**: the ordered steps that get there, in the project file. The resume point points at them; it does not inline them.
3. **Standing instruction**: explicit permission to continue: work the plan top to bottom in one pass, do not stop after step 1, commit per step, and if a step blocks, record the blocker in the project file and continue with the next independent step.
4. **Done-when**: a short checkable list. Each item is something a command or a file can settle, not a feeling. This is the stop condition; without it, "continue until done" has no end and the agent either quits early or runs forever.

The smallest-first-action rule governs starting, never scope: name an easy
entry point, then state the whole objective. A resume point scaled down to one
step is that rule misapplied.

Keep it to a paragraph the operator can read in a card. Findings, blockers, and
the plan itself belong in the project file's body, not in the field.

### Operator next steps: a separate section, never inside the resume point

`next_action` is for the next agent. What only the operator can do lives in a
`## Operator next steps` section in the body of the same `_index.md`, and
nowhere else: not in `next_action`, not in gate files, not in a plan's
checkboxes. The cockpit's queue reads that section for every unit
(`stack.py: operator_steps()`). Its checkbox removes the step, ticks every
gate item the step names on a `Gate:` line, and logs a win.

- One list item per step: a **bold name**, then indented lines for where,
  done-when, and `Gate: <label>` when finishing the step clears a gate item. Only steps the operator can take now; a step waiting on agent work
  is added when that work lands. "None." when there are none.
- Rewrite it whenever you rewrite `next_action`, and drop anything the operator
  has deferred. A deferred step that only matters at one moment belongs to that
  moment: the code refuses there and says what to do, and it is not repeated as a standing to-do.
- A gate states what must be true. It carries no instructions for the operator.

### Procedure

1. **Find the destination.** Use the file or frontmatter field named by this repo's `CLAUDE.md` or `AGENTS.md`. In repos with `_index.md`, write to frontmatter `next_action`. If it names none, use `ops/next-session-prompt.md`.
2. **Draft the objective** in the four-part shape above, driven directly by `objective.md`. Put operator-only steps in `## Operator next steps` in the body.
3. **Verify with the operator unless waived.** Show the draft of `next_action` and `## Operator next steps` and wait for confirmation before writing, unless the operator explicitly stated in their prompt that no verification is needed. Never write it silently without that explicit waiver.
4. **Export.** After operator confirmation (or explicit waiver), write the resume point to the repo file, commit if working on a branch, and run `scripts/export-session.sh`.

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

- **Full conversation**: All prompts and responses from the session (excluding AI meta-commands: see below)
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
surfaced in the conversation (including content imported into context from
personal files like `~/.agents/SOUL.md`) would otherwise be committed.

Before the file is written, every term in `~/.agents/redact-terms.txt` is
replaced with `[REDACTED]`. One term per line, `#` comments ignored; matching is
case-insensitive and word-bounded (so `tuck` will not maul `Kentucky`), longest
term first. Override the path with `EXPORT_SESSION_REDACT_FILE`.

**The terms deliberately do not live in this skill.** This skill is synced
across machines and tools by skillshare, so a name hardcoded here would leak
exactly where the rule is trying to prevent. If the file is absent, nothing is
redacted (the right default for anyone who has not opted in) and the run says
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

1. **Session extraction**: Retrieves the specified session (current or by ID) via Claude or Antigravity IDE introspection
2. **Summary + tags**: Summarizer reads the conversation and generates semantic tags and a one-line summary (defaults to Gemini 3.7 Flash via `agy` if available, or Claude Haiku subscription)
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
  1. Harness session-id env var (`CLAUDE_SESSION_ID`, `CLAUDE_CODE_SESSION_ID`, `SESSION_ID`, `ANTIGRAVITY_CONVERSATION_ID`).
  1.5. Antigravity IDE sessions in `~/.gemini/antigravity-ide/brain/<session-id>/.system_generated/logs/transcript.jsonl`.
       Scoped to the current repo/project. If newer than any Claude Code session (or if no Claude session exists),
       this rule matches. Applies the same 300s ambiguity window; `--path` / `--transcript` exposes the full transcript file.
  2. Newest `*.jsonl` in `~/.claude/projects/<cwd with / and . replaced by ->/`.
     Scoped to the current repo: the global `~/.claude/history.jsonl` is never
     used, since it returns whichever open window wrote last.
  3. If several sessions in that dir were modified within 5 minutes (300s), it prints
     the candidates with mtimes and exits 2: pass an explicit session ID.
  Add `--debug` to print which rule matched, `--path` to get the transcript path, or `--json` for structured metadata.
- **No active session**: Prompts for session ID
- **Session not found**: Explains error and suggests checking `claude --resume` (Claude Code) or `~/.gemini/antigravity-ide/brain/` (Antigravity IDE)
- **Outside git repo**: Defaults to `~/.workbench/sessions/`
- **Permission issues**: Notifies user, suggests checking directory permissions
- **Past session not in history**: Confirms session ID is valid (check `~/.claude/history.jsonl` or `~/.gemini/antigravity-ide/brain/`)
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
- Session IDs can be found in `~/.claude/history.jsonl`, via `claude --resume` interactive list, or in `~/.gemini/antigravity-ide/brain/`
