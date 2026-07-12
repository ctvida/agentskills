#!/bin/bash
set -euo pipefail

# export-session: Export Claude conversations to markdown with auto-generated summaries and tags
#
# Usage:
#   export-session                                         # Current session, interactive project selection
#   export-session <session-id>                            # Export past session
#   export-session --note "your note here"                 # Add optional user note
#   export-session --project projects/my-project           # Explicit project folder

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"

# Defaults
SESSION_ID=""
USER_NOTE=""
PROJECT_PATH=""
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
    --help)
      echo "Usage: export-session [SESSION_ID] [--note 'note'] [--project path]"
      echo ""
      echo "  SESSION_ID              Optional session ID to export (positional or --session-id flag)"
      echo "  --session-id ID         Session ID to export (alternative to positional)"
      echo "  --note TEXT             Optional personal note/reminder for this export"
      echo "  --project PATH          Target project folder (relative to repo root)"
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
  else
    echo "No session ID provided. Getting current session..."
    # Try to extract from claude context if available
    SESSION_ID=$(python3 "$SCRIPT_DIR/get-session-id.py" 2>/dev/null || echo "")

    if [[ -z "$SESSION_ID" ]]; then
      echo "Error: Could not determine session ID. Please specify one:"
      echo "  export-session <session-id>"
      echo ""
      echo "Find session IDs via:"
      echo "  claude --resume    # Interactive list"
      echo "  grep sessionId ~/.claude/history.jsonl | head -20"
      exit 1
    fi
  fi
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

# Ensure output directory exists
OUTPUT_DIR="$PROJECT_PATH/outputs/ai-sessions"
mkdir -p "$OUTPUT_DIR"

# Export the session
echo "Exporting session $SESSION_ID..."
python3 "$SCRIPT_DIR/session-exporter.py" \
  --session-id "$SESSION_ID" \
  --output-dir "$OUTPUT_DIR" \
  --user-note "$USER_NOTE"

echo ""
echo "✓ Session exported successfully"
