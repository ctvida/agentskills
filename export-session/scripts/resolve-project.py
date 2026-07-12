#!/usr/bin/env python3
"""
Resolve project path from current working directory.
Infers target folder based on git repo structure and current location.
Returns "PROMPT" if ambiguous (multiple projects, or repo root).
"""

import subprocess
import sys
from pathlib import Path


def find_git_root(start_path: str) -> Path:
    """Find the root of the git repository."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
            cwd=start_path
        )
        return Path(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def infer_project_path(current_dir: str) -> str:
    """
    Infer project path from current directory.
    Returns:
      - Explicit project folder if clearly inside projects/<name>
      - "PROMPT" if at repo root or ambiguous
    """
    current = Path(current_dir).resolve()
    git_root = find_git_root(current_dir)

    if not git_root:
        # Not in a git repo
        return "PROMPT"

    # Check if we're inside a projects/ folder
    try:
        rel_path = current.relative_to(git_root)
    except ValueError:
        return "PROMPT"

    parts = rel_path.parts

    # Look for projects/<project-name> pattern
    if "projects" in parts:
        idx = parts.index("projects")
        if idx + 1 < len(parts):
            # We're inside projects/something
            project_name = parts[idx + 1]
            return str(git_root / "projects" / project_name)

    # Look for domains/<domain-name> pattern (agentic-os structure)
    if "domains" in parts:
        idx = parts.index("domains")
        if idx + 1 < len(parts):
            # We're inside domains/something - export to repo root
            return str(git_root)

    # We're at repo root or in some other location
    return "PROMPT"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("PROMPT")
        sys.exit(0)

    current_dir = sys.argv[1]
    result = infer_project_path(current_dir)
    print(result)
