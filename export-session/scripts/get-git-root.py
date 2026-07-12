#!/usr/bin/env python3
"""
Get the git repository root directory.
Falls back to checking for common project directories (repos, projects, etc).
"""

import subprocess
import sys
from pathlib import Path


def find_git_root(start_path: str) -> str:
    """Find and return the git repository root directory."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
            cwd=start_path
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def find_project_root(start_path: str) -> str:
    """
    Fallback: find a common project directory name by walking up the tree.
    Looks for: repos, projects, agentic-os, code, dev, work, etc.
    """
    common_names = {"repos", "projects", "agentic-os", "code", "dev", "work", "src"}
    current = Path(start_path).resolve()

    # Check current directory and parents
    for parent in [current] + list(current.parents):
        if parent.name in common_names:
            return str(parent)

    return ""


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(1)

    current_dir = sys.argv[1]

    # Try git root first
    git_root = find_git_root(current_dir)
    if git_root:
        print(git_root)
        sys.exit(0)

    # Fall back to common project directory names
    project_root = find_project_root(current_dir)
    if project_root:
        print(project_root)
        sys.exit(0)

    # No root found
    sys.exit(1)
