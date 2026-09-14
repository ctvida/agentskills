#!/usr/bin/env python3
"""
Extract the project path for a given session ID from Claude history or Antigravity transcript
"""

import json
import re
import sys
from pathlib import Path


def get_claude_session_project(session_id: str) -> str:
    """Get the project path from a Claude session's history entry."""
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


def get_agy_session_project(session_id: str) -> str:
    """Get the project path from an Antigravity IDE transcript."""
    transcript = (
        Path.home()
        / ".gemini"
        / "antigravity-ide"
        / "brain"
        / session_id
        / ".system_generated"
        / "logs"
        / "transcript.jsonl"
    )
    if not transcript.exists():
        return ""

    try:
        with open(transcript, "r", errors="ignore") as f:
            for _ in range(30):
                line = f.readline()
                if not line:
                    break
                m = re.search(r"Active Document:\s*([^\s(]+)", line)
                if m:
                    doc_path = Path(m.group(1))
                    for parent in [doc_path] + list(doc_path.parents):
                        if (parent / ".git").exists():
                            return str(parent)
                m = re.search(
                    r'["\']?(?:Cwd|DirectoryPath)["\']?\s*:\s*["\']([^"\']+)["\']', line
                )
                if m:
                    p = Path(m.group(1))
                    for parent in [p] + list(p.parents):
                        if (parent / ".git").exists():
                            return str(parent)
    except Exception:
        pass

    return ""


def get_session_project(session_id: str) -> str:
    # Try Claude first, then Antigravity IDE
    if proj := get_claude_session_project(session_id):
        return proj
    return get_agy_session_project(session_id)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(1)

    session_id = sys.argv[1]
    project = get_session_project(session_id)
    if project:
        print(project)
    else:
        sys.exit(1)
