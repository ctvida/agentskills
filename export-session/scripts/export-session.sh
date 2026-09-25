#!/bin/bash
set -euo pipefail

# export-session: Export Claude conversations to markdown with auto-generated summaries and tags
#
# Usage:
#   export-session                                         # Current session, interactive project selection
#   export-session <session-id>                            # Export past session
#   export-session --note "your note here"                 # Add optional user note
#   export-session --project projects/my-project           # Explicit project folder
#   export-session --new                                   # Force a new file instead of appending
#
# Re-exporting a session that already has an export in the target folder appends
# only the turns since that export, in place. --new forces a separate file.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"

# Defaults
SESSION_ID=""
USER_NOTE=""
PROJECT_PATH=""
MODEL=""
FORCE_NEW=""
CURRENT_DIR="$(pwd)"

# Parse arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --session-id)
      SESSION_ID="$2"
      shift 2
      ;;
    --note)
      USER_NOTE="$2"
      shift 2
      ;;
    --project)
      PROJECT_PATH="$2"
      shift 2
      ;;
    --model)
      MODEL="$2"
      shift 2
      ;;
    --new)
      FORCE_NEW="--new"
      shift
      ;;
    --no-verify|--verified)
      shift
      ;;
    --help)
      echo "Usage: export-session [SESSION_ID] [--note 'note'] [--project path] [--new] [--no-verify]"
      echo ""
      echo "  SESSION_ID              Optional session ID to export (positional or --session-id flag)"
      echo "  --session-id ID         Session ID to export (alternative to positional)"
      echo "  --note TEXT             Optional personal note/reminder for this export"
      echo "  --project PATH          Target project folder (relative to repo root)"
      echo "  --model MODEL           Summarizer model (e.g. gemini-3.7, claude-p-haiku)"
      echo "  --new                   Write a new file instead of appending to an existing export"
      echo "  --no-verify             Bypass pre-flight verification gate"
      echo "  --verified              Mark pre-flight resume point as verified"
      echo ""
      echo "By default, re-exporting a session that already has an export in the target"
      echo "folder appends only the turns added since that export."
      exit 0
      ;;
    -*)
      echo "Unknown option: $1"
      exit 1
      ;;
    *)
      if [[ -z "$SESSION_ID" ]]; then
        SESSION_ID="$1"
      fi
      shift
      ;;
  esac
done

# If no session ID provided, use current session (from environment or ask)
if [[ -z "$SESSION_ID" ]]; then
  if [[ -n "${CLAUDE_SESSION_ID:-}" ]]; then
    SESSION_ID="$CLAUDE_SESSION_ID"
  elif [[ -n "${ANTIGRAVITY_CONVERSATION_ID:-}" ]]; then
    SESSION_ID="$ANTIGRAVITY_CONVERSATION_ID"
  else
    echo "No session ID provided. Getting current session..."
    # Try to extract from claude or antigravity context if available
    SESSION_ID=$(python3 "$SCRIPT_DIR/get-session-id.py" 2>/dev/null || echo "")

    if [[ -z "$SESSION_ID" ]]; then
      echo "Error: Could not determine session ID. Please specify one:"
      echo "  export-session <session-id>"
      echo ""
      echo "Find session IDs via:"
      echo "  claude --resume                                    # Interactive list (Claude Code)"
      echo "  grep sessionId ~/.claude/history.jsonl | head -20"
      echo "  ls -lt ~/.gemini/antigravity-ide/brain/ | head -20 # Antigravity IDE"
      exit 3  # no transcript for this harness: the skill skips this step
    fi
  fi
fi

# An explicitly passed --project always wins over the remembered destination.
PROJECT_EXPLICIT=""
if [[ -n "$PROJECT_PATH" ]]; then
  PROJECT_EXPLICIT="1"
fi

# Resolve project path
if [[ -z "$PROJECT_PATH" ]]; then
  # If exporting a past session by ID, try to use its original project
  if [[ -n "$SESSION_ID" ]] && [[ "$SESSION_ID" != "current" ]]; then
    PROJECT_PATH=$(python3 "$SCRIPT_DIR/get-session-project.py" "$SESSION_ID" 2>/dev/null || echo "")
  fi

  # If no project from session history, infer from current git repo and directory structure
  if [[ -z "$PROJECT_PATH" ]]; then
    PROJECT_PATH=$(python3 "$SCRIPT_DIR/resolve-project.py" "$CURRENT_DIR" 2>/dev/null || echo "")
  fi

  # If inference indicates specific project subfolder, use it
  # If PROMPT or empty, check if we're in a git repo and default to repo root
  if [[ -z "$PROJECT_PATH" || "$PROJECT_PATH" == "PROMPT" ]]; then
    INFERRED_ROOT=$(python3 "$SCRIPT_DIR/get-git-root.py" "$CURRENT_DIR" 2>/dev/null || echo "")

    if [[ -n "$INFERRED_ROOT" ]]; then
      # We're in a git repo - check if interactive
      if [[ -t 0 ]]; then
        # Interactive terminal - prompt user
        echo ""
        echo "Export to repo root or a specific project?"
        python3 "$SCRIPT_DIR/prompt-project.py" "$INFERRED_ROOT"
        read -p "Enter project path (or leave blank for repo root): " PROJECT_PATH

        if [[ -z "$PROJECT_PATH" ]]; then
          PROJECT_PATH="$INFERRED_ROOT"
        fi
      else
        # Non-interactive - default to inferred root (repo root or project folder)
        PROJECT_PATH="$INFERRED_ROOT"
      fi
    else
      # Not in a git repo - use home directory default
      PROJECT_PATH="$HOME"
    fi
  fi
fi

# Normalize project path (resolve to absolute)
if [[ "$PROJECT_PATH" == "." ]]; then
  PROJECT_PATH="$CURRENT_DIR"
elif [[ ! "$PROJECT_PATH" = /* ]]; then
  # Relative path - resolve from current directory
  PROJECT_PATH="$(cd "$CURRENT_DIR" && cd "$PROJECT_PATH" && pwd)"
fi

# Session exports are local-only working notes, not vault canon: they land in
# .workbench/sessions/ at the repo root (gitignored, never committed) so a
# repo that later goes public was never carrying transcripts. PROJECT_PATH may
# be a subfolder; .workbench/ always lives at the repo root above it.
REPO_ROOT=$(python3 "$SCRIPT_DIR/get-git-root.py" "$PROJECT_PATH" 2>/dev/null || echo "")
WORKBENCH_ROOT="${REPO_ROOT:-$PROJECT_PATH}"
OUTPUT_DIR="$WORKBENCH_ROOT/.workbench/sessions"

# Sticky destination. find_existing_export only searches the folder being
# written to, so exporting one session from two different working directories
# used to produce two files instead of appending to the first. Once a session
# has been exported somewhere, it keeps going there unless --project says
# otherwise.
if [[ -z "$PROJECT_EXPLICIT" ]]; then
  STICKY=$(python3 "$SCRIPT_DIR/sticky-dir.py" get "$SESSION_ID" 2>/dev/null || echo "")
  if [[ -n "$STICKY" && "$STICKY" != "$OUTPUT_DIR" ]]; then
    echo "Session was last exported to $STICKY; appending there (--project overrides)."
    OUTPUT_DIR="$STICKY"
    WORKBENCH_ROOT=$(python3 "$SCRIPT_DIR/get-git-root.py" "$STICKY" 2>/dev/null || echo "$WORKBENCH_ROOT")
  fi
fi

mkdir -p "$OUTPUT_DIR"

GITIGNORE="$WORKBENCH_ROOT/.gitignore"
if [[ -f "$GITIGNORE" ]] && ! grep -qx "\.workbench/" "$GITIGNORE"; then
  printf '\n# Local agent workbench: roadmaps, plans, next actions, session logs.\n.workbench/\n' >> "$GITIGNORE"
elif [[ ! -f "$GITIGNORE" ]] && [[ -n "$REPO_ROOT" ]]; then
  printf '# Local agent workbench: roadmaps, plans, next actions, session logs.\n.workbench/\n' > "$GITIGNORE"
fi

# Export the session
echo "Exporting session $SESSION_ID..."
python3 "$SCRIPT_DIR/session-exporter.py" \
  --session-id "$SESSION_ID" \
  --output-dir "$OUTPUT_DIR" \
  --project-root "$PROJECT_PATH" \
  --user-note "$USER_NOTE" \
  ${MODEL:+--model "$MODEL"} \
  ${FORCE_NEW:+"$FORCE_NEW"}

python3 "$SCRIPT_DIR/sticky-dir.py" set "$SESSION_ID" "$OUTPUT_DIR" 2>/dev/null || true

echo ""
echo "✓ Session exported successfully"
