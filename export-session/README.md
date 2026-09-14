# export-session (setup)

Runtime behaviour is in `SKILL.md`. This file is for a human installing the
skill, and is deliberately kept out of `SKILL.md` so it does not load into an
agent's context on every invocation.

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

## Model selection

The skill picks the fastest, cheapest available option. If `agy` CLI is available,
it defaults to Gemini 3.7 Flash (`gemini-3.7-flash-medium`), which provides a 1M token
context window and avoids burning Claude subscription limits. In Claude Code without `agy`,
it falls back to `claude -p` (Haiku).

Override per-command via `--model` or globally via `CLAUDE_EXPORT_MODEL`:

```bash
export-session --model gemini-3.7
export-session --model claude-p-haiku

export CLAUDE_EXPORT_MODEL="gemini-3.7-flash-medium"
export CLAUDE_EXPORT_MODEL="claude-p-haiku"
export CLAUDE_EXPORT_MODEL="omlx://hermes-2-pro-mistral"
export CLAUDE_EXPORT_MODEL="ollama://mistral"
export CLAUDE_EXPORT_MODEL="openrouter://meta-llama/llama-2-7b-chat:free"
```

## Redaction

Terms listed in `~/.agents/redact-terms.txt` are replaced with `[REDACTED]`
before the file is written. One term per line, `#` comments ignored. Override
the path with `EXPORT_SESSION_REDACT_FILE`. If the file is absent nothing is
redacted and the run says so on stderr. The terms are deliberately not stored
in this skill, which is synced across machines.
