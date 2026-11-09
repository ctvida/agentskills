#!/usr/bin/env python3
"""
Extract the project path for a given session ID from Claude history or Antigravity transcript
"""

from collections import Counter
import json
import os
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
    """Get the project path from an Antigravity transcript."""
    brain_dirs = [
        Path.home() / ".gemini" / "antigravity" / "brain",
        Path.home() / ".gemini" / "antigravity-ide" / "brain",
        Path.home() / ".gemini" / "antigravity-cli" / "brain",
    ]
    if os.getenv("ANTIGRAVITY_APP_DATA_DIR"):
        brain_dirs.insert(0, Path(os.environ["ANTIGRAVITY_APP_DATA_DIR"]) / "brain")

    transcript = None
    for bdir in brain_dirs:
        cand = bdir / session_id / ".system_generated" / "logs" / "transcript.jsonl"
        if cand.is_file():
            transcript = cand
            break

    if not transcript:
        return ""

    try:
        root_scores = Counter()
        cwd_git_root = None
        cwd = Path.cwd()
        for parent in [cwd] + list(cwd.parents):
            if (parent / ".git").exists():
                cwd_git_root = str(parent)
                break

        with open(transcript, "r", errors="ignore") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                except Exception:
                    continue

                for tc in data.get("tool_calls") or []:
                    name = tc.get("name", "")
                    args = tc.get("args") or {}
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except Exception:
                            pass
                    paths = []
                    if isinstance(args, dict):
                        for k in ("Path", "path", "TargetFile", "AbsolutePath", "DirectoryPath", "Cwd", "cwd"):
                            val = args.get(k)
                            if isinstance(val, str):
                                paths.append(val.strip('"\' '))
                    for p in paths:
                        try:
                            target = Path(p)
                            for parent in [target] + list(target.parents):
                                if (parent / ".git").exists():
                                    weight = 5 if name in ("edit_file", "write_file") else 1
                                    root_scores[str(parent)] += weight
                                    break
                        except Exception:
                            pass

        if root_scores:
            # If current working directory's git root was active in the session, prefer it
            if cwd_git_root and cwd_git_root in root_scores:
                return cwd_git_root
            # Otherwise pick the git root with highest score
            return root_scores.most_common(1)[0][0]

        # Fallback to inspecting lines for paths if no tool calls
        with open(transcript, "r", errors="ignore") as f:
            for _ in range(50):
                line = f.readline()
                if not line:
                    break
                m = re.search(r"Active Document:\s*([^\s(]+)", line)
                if m:
                    doc_path = Path(m.group(1).strip('"\' '))
                    for parent in [doc_path] + list(doc_path.parents):
                        if (parent / ".git").exists():
                            return str(parent)
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
