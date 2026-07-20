#!/usr/bin/env python3
"""
Get the current session ID, scoped to the project dir of the cwd.

Resolution order (first hit wins):
  1. session-id env var set by the harness
  2. newest *.jsonl in ~/.claude/projects/<encoded-cwd>/
  3. ambiguous (several files touched in the last AMBIGUOUS_WINDOW seconds)
     -> list candidates on stderr and exit 2 instead of guessing

Never falls back to ~/.claude/history.jsonl: that is global and returns
whichever window wrote last.
"""

import datetime
import os
import sys
from pathlib import Path

ENV_VARS = ("CLAUDE_SESSION_ID", "CLAUDE_CODE_SESSION_ID", "SESSION_ID")
AMBIGUOUS_WINDOW = 300  # seconds


def project_dir(cwd: Path) -> Path:
    # Claude Code encodes the cwd by replacing '/' and '.' with '-'
    encoded = str(cwd).replace("/", "-").replace(".", "-")
    return Path.home() / ".claude" / "projects" / encoded


def get_current_session_id(debug: bool = False) -> str:
    for var in ENV_VARS:
        if sid := os.getenv(var):
            if debug:
                print(f"[debug] rule 1: env {var}", file=sys.stderr)
            return sid

    pdir = project_dir(Path.cwd())
    files = sorted(pdir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    if debug:
        print(f"[debug] project dir: {pdir} ({len(files)} sessions)", file=sys.stderr)
    if not files:
        return ""

    newest = files[0].stat().st_mtime
    recent = [f for f in files if newest - f.stat().st_mtime < AMBIGUOUS_WINDOW]
    if len(recent) > 1:
        print("Ambiguous: multiple sessions active in this project.", file=sys.stderr)
        for f in recent:
            ts = datetime.datetime.fromtimestamp(f.stat().st_mtime).isoformat(timespec="seconds")
            print(f"  {f.stem}  {ts}", file=sys.stderr)
        print("Re-run with an explicit session ID.", file=sys.stderr)
        sys.exit(2)

    if debug:
        print("[debug] rule 2: newest jsonl in project dir", file=sys.stderr)
    return files[0].stem


if __name__ == "__main__":
    session_id = get_current_session_id("--debug" in sys.argv)
    if session_id:
        print(session_id)
    else:
        exit(1)
