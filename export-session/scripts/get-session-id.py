#!/usr/bin/env python3
"""
Get the current session ID, scoped to the project dir of the cwd.

Resolution order (first hit wins):
  1. session-id env var set by the harness (CLAUDE_*, ANTIGRAVITY_*)
  1.5. newest transcript.jsonl in ~/.gemini/antigravity-ide/brain/ matching cwd/repo
       (if newer than Claude Code session or no Claude session exists)
  2. newest *.jsonl in ~/.claude/projects/<encoded-cwd>/
  3. ambiguous (several files touched in the last AMBIGUOUS_WINDOW seconds)
     -> list candidates on stderr and exit 2 instead of guessing

Never falls back to ~/.claude/history.jsonl: that is global and returns
whichever window wrote last.
"""

import datetime
import json
import os
import sys
from pathlib import Path
from typing import Optional, Tuple

ENV_VARS = (
    "CLAUDE_SESSION_ID",
    "CLAUDE_CODE_SESSION_ID",
    "SESSION_ID",
    "ANTIGRAVITY_CONVERSATION_ID",
)
AMBIGUOUS_WINDOW = 300  # seconds


def find_git_root(cwd: Path) -> Optional[Path]:
    """Find enclosing git repository root, if any."""
    for parent in [cwd] + list(cwd.parents):
        if (parent / ".git").exists():
            return parent
    return None


def project_dir(cwd: Path) -> Path:
    # Claude Code encodes the cwd by replacing '/' and '.' with '-'
    encoded = str(cwd).replace("/", "-").replace(".", "-")
    return Path.home() / ".claude" / "projects" / encoded


def get_agy_candidates(cwd: Path) -> list[Tuple[float, str, Path]]:
    """
    Find Antigravity IDE sessions belonging to current project/cwd,
    sorted by transcript.jsonl mtime descending.
    Returns list of (mtime, session_id, transcript_path).
    """
    brain_dir = Path.home() / ".gemini" / "antigravity-ide" / "brain"
    if not brain_dir.is_dir():
        return []

    git_root = find_git_root(cwd)
    project_paths = [str(cwd)]
    if git_root and git_root != cwd:
        project_paths.append(str(git_root))

    candidates = []
    for subdir in brain_dir.iterdir():
        if not subdir.is_dir():
            continue
        transcript = subdir / ".system_generated" / "logs" / "transcript.jsonl"
        if not transcript.is_file():
            continue

        try:
            mtime = transcript.stat().st_mtime
            # Quick check: read the first 10KB to verify this session belongs to this project
            with open(transcript, "r", errors="ignore") as f:
                header = f.read(10000)
                if any(p in header for p in project_paths):
                    candidates.append((mtime, subdir.name, transcript))
        except OSError:
            continue

    candidates.sort(key=lambda c: c[0], reverse=True)
    return candidates


def get_claude_candidates(cwd: Path) -> list[Tuple[float, str, Path]]:
    """
    Find Claude Code sessions belonging to current project/cwd,
    sorted by mtime descending.
    Returns list of (mtime, session_id, jsonl_path).
    """
    pdir = project_dir(cwd)
    if not pdir.is_dir():
        return []

    files = sorted(pdir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    candidates = []
    for f in files:
        try:
            candidates.append((f.stat().st_mtime, f.stem, f))
        except OSError:
            continue
    return candidates


def get_current_session(
    debug: bool = False, cwd: Optional[Path] = None
) -> Tuple[str, Optional[Path], str]:
    """
    Get current session info: (session_id, transcript_path, harness)
    """
    cwd = cwd or Path.cwd()

    # Rule 1: Harness session-id env var
    for var in ENV_VARS:
        if sid := os.getenv(var):
            if debug:
                print(f"[debug] rule 1: env {var}", file=sys.stderr)
            harness = "antigravity" if "ANTIGRAVITY" in var else "claude-code"
            # Look up transcript path if possible
            tpath = None
            if harness == "antigravity":
                candidate = (
                    Path.home()
                    / ".gemini"
                    / "antigravity-ide"
                    / "brain"
                    / sid
                    / ".system_generated"
                    / "logs"
                    / "transcript.jsonl"
                )
                if candidate.exists():
                    tpath = candidate
            else:
                matches = list((Path.home() / ".claude" / "projects").glob(f"*/{sid}.jsonl"))
                if matches:
                    tpath = matches[0]
            return sid, tpath, harness

    agy_candidates = get_agy_candidates(cwd)
    claude_candidates = get_claude_candidates(cwd)

    if debug:
        print(
            f"[debug] candidates: AGY={len(agy_candidates)}, Claude={len(claude_candidates)}",
            file=sys.stderr,
        )

    # Rule 1.5 & Rule 2: Compare recency
    # If AGY has sessions and is newer than Claude (or Claude has none):
    agy_newest_mtime = agy_candidates[0][0] if agy_candidates else -1.0
    claude_newest_mtime = claude_candidates[0][0] if claude_candidates else -1.0

    if agy_candidates and agy_newest_mtime >= claude_newest_mtime:
        # Check AGY ambiguity
        recent_agy = [c for c in agy_candidates if agy_newest_mtime - c[0] < AMBIGUOUS_WINDOW]
        if len(recent_agy) > 1:
            print(
                "Ambiguous: multiple Antigravity IDE sessions active in this project.",
                file=sys.stderr,
            )
            for mtime, sid, _ in recent_agy:
                ts = datetime.datetime.fromtimestamp(mtime).isoformat(timespec="seconds")
                print(f"  {sid}  {ts}", file=sys.stderr)
            print("Re-run with an explicit session ID.", file=sys.stderr)
            sys.exit(2)

        if debug:
            print(
                f"[debug] rule 1.5: newest AGY transcript in brain ({agy_candidates[0][1]})",
                file=sys.stderr,
            )
        return agy_candidates[0][1], agy_candidates[0][2], "antigravity"

    if claude_candidates:
        # Check Claude ambiguity
        recent_claude = [
            c for c in claude_candidates if claude_newest_mtime - c[0] < AMBIGUOUS_WINDOW
        ]
        if len(recent_claude) > 1:
            print("Ambiguous: multiple sessions active in this project.", file=sys.stderr)
            for mtime, sid, _ in recent_claude:
                ts = datetime.datetime.fromtimestamp(mtime).isoformat(timespec="seconds")
                print(f"  {sid}  {ts}", file=sys.stderr)
            print("Re-run with an explicit session ID.", file=sys.stderr)
            sys.exit(2)

        if debug:
            print("[debug] rule 2: newest jsonl in project dir", file=sys.stderr)
        return claude_candidates[0][1], claude_candidates[0][2], "claude-code"

    return "", None, ""


def get_current_session_id(debug: bool = False) -> str:
    sid, _, _ = get_current_session(debug=debug)
    return sid


if __name__ == "__main__":
    debug = "--debug" in sys.argv
    show_path = "--path" in sys.argv or "--transcript" in sys.argv
    as_json = "--json" in sys.argv

    sid, path, harness = get_current_session(debug=debug)
    if not sid:
        sys.exit(1)

    if as_json:
        print(
            json.dumps(
                {
                    "session_id": sid,
                    "transcript_path": str(path) if path else None,
                    "harness": harness,
                }
            )
        )
    elif show_path:
        if path:
            print(str(path))
        else:
            print(sid)
    else:
        print(sid)
