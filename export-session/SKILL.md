---
name: export-session
description: Export Claude conversations to searchable markdown with auto-generated summaries and tags. Use this whenever you want to save a valuable conversation for later reference—either the current session or a past session by ID. Works globally across projects. No manual tagging required; Claude generates semantic tags and a concise summary automatically. Optionally add a personal note or reminder. Output goes to <project-root>/outputs/ai-sessions/ organized by semantic tags.
compatibility: Requires claude CLI (Claude Code) or local inference (Ollama/MLX) or OpenRouter API key. Haiku or equivalent small model recommended.
---

# export-session

## Installation

1. **Copy the skill to your global skills directory:**
   ```bash
   cp -r <path-to-export-session> ~/.claude/skills/export-session
   ```
   Where `<path-to-export-session>` is the directory containing this SKILL.md and the `scripts/` folder.

2. **Make scripts executable:**
   ```bash
   chmod +x ~/.claude/skills/export-session/scripts/*.sh
   chmod +x ~/.claude/skills/export-session/scripts/*.py
   ```

3. **Verify installation:**
   - Restart Claude Code or reload skills: `/reload-plugins` or `/plugin`
   - Type `/export-session --help` to test
   - Should display usage without errors

4. **Optional: Configure model** (if not using claude -p)
   ```bash
   # For omlx/MLX (Mac):
   export CLAUDE_EXPORT_MODEL="omlx://hermes-2-pro-mistral"

   # For Ollama:
   export CLAUDE_EXPORT_MODEL="ollama://mistral"

   # For OpenRouter:
   export OPENROUTER_API_KEY="your-key"
   export CLAUDE_EXPORT_MODEL="openrouter://meta-llama/llama-2-7b-chat:free"
   ```

## Quick Start

Once installed, use it in any Claude Code session:

Export conversations from Claude Code (or other Claude harnesses) to markdown with auto-generated summaries and semantic tags.

## When to use

- Save valuable conversations before they're lost
- Build a searchable archive of insights, strategies, code patterns, or learnings
- Minimize digital clutter by only exporting sessions worth keeping
- Access past conversations without resuming the full session

## Usage

```bash
# Export current session (interactive project selection)
/export-session

# Export specific past session by ID
/export-session fb62a3e8-e2e9-4637-bbd8-cec06dd2a49e

# Add a personal note/reminder (optional)
/export-session --note "this strategy needs testing against Q3 data"

# Specify target project folder explicitly
/export-session --project projects/arctusai-launch
```

## What gets exported

- **Full conversation**: All prompts and responses from the session (excluding AI meta-commands — see below)
- **Auto-generated summary**: One sentence, max 60 characters (e.g., "Fundamental analysis backtesting strategy")
- **Semantic tags**: 3-5 tags inferred from content (e.g., `[trading, backtesting, strategy, learning]`)
- **Metadata frontmatter**: Date, session ID, project path, optional user note, model used
- **Filename**: `YYYY-MM-DD-HHmm-slug.md` derived from summary
- **Location**: `<project-root>/outputs/ai-sessions/`

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

## Frontmatter example

```yaml
---
date: 2026-07-12
session_id: fb62a3e8-e2e9-4637-bbd8-cec06dd2a49e
summary: Fundamental analysis backtesting strategy
tags: [trading, backtesting, strategy, learning]
project: /Users/toraphan/Documents/repos/agentic-os
user_note: Test this against Q3 earnings data
model_used: haiku
---
```

## How it works

1. **Session extraction**: Retrieves the specified session (current or by ID) via Claude introspection
2. **Summary + tags**: Claude reads the conversation and generates semantic tags and a one-line summary
3. **Project inference**: Automatically detects project root and target folder, or prompts interactively if ambiguous
4. **Directory creation**: Creates `outputs/ai-sessions/` if needed
5. **Markdown formatting**: Exports conversation with clean formatting and metadata
6. **Output confirmation**: Shows filename, location, tags, and summary

## Model selection

The skill automatically detects your harness and uses the most cost-efficient model:

**When running in Claude Code:**
- Automatically uses `claude -p` with Haiku (lowest-cost reasoning model)
- No extra charges to your subscription
- No configuration needed

**When running in other harnesses** (Hermes, local agents, etc.):
1. **`CLAUDE_EXPORT_MODEL` env var** (explicit override): Set to use a specific model
   ```bash
   export CLAUDE_EXPORT_MODEL="mlx://hermes-2-pro-mistral"
   export CLAUDE_EXPORT_MODEL="ollama://mistral"
   export CLAUDE_EXPORT_MODEL="openrouter://meta-llama/llama-2-7b-chat:free"
   ```
2. **MLX/omlx** (if available on Mac): Uses local Apple Silicon acceleration
3. **Ollama** (if running): Uses local inference (no external API)
4. **OpenRouter** (if `OPENROUTER_API_KEY` set): Free/cheap small models
5. **Fallback**: Claude Code subscription (`claude -p`)

No manual configuration needed—the skill detects your setup and uses what's available, prompting for alternatives if desired.

## Project path resolution

If you're in a git repository, exports default to `<repo-root>/outputs/ai-sessions/` automatically. No prompt unless you want a specific project subfolder.

If you want to export to a specific project instead:

```
Export to repo root or a specific project?
  • (leave blank for /Users/toraphan/Documents/repos)
  • projects/arctusai-launch
  • projects/fundamental-analysis-agent
  
Enter project path (or leave blank for repo root): projects/fundamental-analysis-agent
```

Or skip the prompt with `--project <path>`:

```bash
export-session --project projects/fundamental-analysis-agent
export-session --project .  # Explicitly use repo root
```

If not in a git repo, defaults to `~/outputs/ai-sessions/`.

## MLX/omlx Setup (Mac users)

If you have MLX and Hermes models on your Mac, the skill will auto-detect and use them:

```bash
# Model auto-detection order:
# 1. Check for mlx_lm.generate (Python MLX)
# 2. Check for omlx CLI (omlx wrapper)
# 3. Fall back to Ollama, OpenRouter, or claude -p

# To explicitly use a specific model:
export CLAUDE_EXPORT_MODEL="omlx://hermes-2-pro-mistral"
export CLAUDE_EXPORT_MODEL="mlx://mistral-7b"
```

No additional configuration needed—just have `omlx` or MLX installed and the skill will use it.

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
- **Outside git repo**: Defaults to `~/outputs/ai-sessions/`
- **Permission issues**: Notifies user, suggests checking directory permissions
- **Past session not in history**: Confirms session ID is valid (check `~/.claude/history.jsonl`)
- **MLX/omlx not found**: Falls back to next available model in priority order

## Example output

```
✓ Exported to: /Users/toraphan/Documents/repos/agentic-os/outputs/ai-sessions/2026-07-12-1447-fundamental-analysis-backtest.md

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
