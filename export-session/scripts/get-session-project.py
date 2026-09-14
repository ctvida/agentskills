#!/usr/bin/env python3
"""
Extract the project path for a given session ID from Claude history or Antigravity transcript
"""

import json
import re
import sys
from pathlib import Path


def get_claude_session_project(session_id: str) -> str:
    """Get the project path from a Claude session'''s history entry."""
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
    """Get the project path from an Antigravity transcript."""
    transcript = None
    for bdir in [
        Path.home() / ".gemini" / "antigravity" / "brain",
        Path.home() / ".gemini" / "antigravity-ide" / "brain",
        Path.home() / ".gemini" / "antigravity-cli" / "brain",
    ]:
        cand = bdir / session_id / ".system_generated" / "logs" / "transcript.jsonl"
        if cand.is_file():
            transcript = cand
            break

    if not transcript:
        return ""

    try:
        with open(transcript, "r", errors="ignore") as f:
            for _ in range(50):
                line = f.readline()
                if not line:
                    break

                # 1. Check Active Document in prompt metadata
                m = re.search(r"Active Document:\s*([^\s(]+)", line)
                if m:
                    doc_path = Path(m.group(1).strip('"\' '))
                    for parent in [doc_path] + list(doc_path.parents):
                        if (parent / ".git").exists():
                            return str(parent)

                # 2. Check active workspaces metadata
                m = re.search(r"(/Users/[^\s/]+/Documents/repos/[^\s/]+)", line)
                if m:
                    p = Path(m.group(1))
                    for parent in [p] + list(p.parents):
                        if (parent / ".git").exists():
                            return str(parent)

                # 3. Check JSON tool calls
                try:
                    data = json.loads(line)
                    for tc in data.get("tool_calls") or []:
                        args = tc.get("args") or {}
                        if isinstance(args, str):
                            try:
                                args = json.loads(args)
                            except Exception:
                                pass
                        if isinstance(args, dict):
                            for k in ("Cwd", "DirectoryPath", "SearchDirectory", "TargetFile", "AbsolutePath"):
                                val = args.get(k)
                                if val and isinstance(val, str):
                                    p = Path(val.strip('"\' '))
                                    for parent in [p] + list(p.parents):
                                        if (parent / ".git").exists():
                                            return str(parent)
                except Exception:
                    pass
    except Exception:
        pass

    return ""


def get_session_project(session_id: str) -> str:
    # Try Claude first, then Antigravity
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
