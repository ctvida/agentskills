#!/usr/bin/env python3
"""
Extract the project path for a given session ID from history.jsonl
"""

import json
import sys
from pathlib import Path


def get_session_project(session_id: str) -> str:
    """Get the project path from a session's history entry."""
    history_file = Path.home() / ".claude" / "history.jsonl"

    if not history_file.exists():
        return ""

    try:
        with open(history_file, "r") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("sessionId") == session_id:
                        project = entry.get("project")
                        if project:
                            return project
                except json.JSONDecodeError:
                    continue
    except Exception:
        pass

    return ""


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(1)

    session_id = sys.argv[1]
    project = get_session_project(session_id)
    if project:
        print(project)
    else:
        sys.exit(1)
