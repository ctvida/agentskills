#!/usr/bin/env python3
"""
Get the current session ID from Claude Code environment or active session data.
"""

import json
import os
import subprocess
from pathlib import Path


def get_current_session_id() -> str:
    """
    Attempt to retrieve current session ID.
    Tries multiple methods in order of preference.
    """

    # Method 1: Environment variable (if running within Claude Code)
    if session_id := os.getenv("CLAUDE_SESSION_ID"):
        return session_id

    # Method 2: Try to get from claude process info
    try:
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True,
            check=True
        )
        # Look for claude process with session ID in args
        for line in result.stdout.split("\n"):
            if "claude" in line and "-session" in line:
                # Parse session ID from command line
                parts = line.split()
                for i, part in enumerate(parts):
                    if part == "-session" and i + 1 < len(parts):
                        return parts[i + 1]
    except Exception:
        pass

    # Method 3: Check most recent history entry
    history_file = Path.home() / ".claude" / "history.jsonl"
    if history_file.exists():
        try:
            last_session = None
            with open(history_file, "r") as f:
                for line in f:
                    if line.strip():
                        entry = json.loads(line)
                        last_session = entry.get("sessionId")
            if last_session:
                return last_session
        except Exception:
            pass

    # No current session found
    return ""


if __name__ == "__main__":
    session_id = get_current_session_id()
    if session_id:
        print(session_id)
    else:
        exit(1)
