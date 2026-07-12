#!/usr/bin/env python3
"""
Display interactive project selection prompt.
Lists detected projects and the root path provided.
"""

from pathlib import Path


def list_projects(root: Path) -> list[str]:
    """List all projects in projects/ folder."""
    projects_dir = root / "projects"
    projects = []

    if projects_dir.exists():
        for item in sorted(projects_dir.iterdir()):
            if item.is_dir():
                projects.append(item.name)

    return projects


if __name__ == "__main__":
    import sys
    root_path = sys.argv[1] if len(sys.argv) > 1 else "."
    root = Path(root_path).resolve()

    print()
    print(f"  • (leave blank for {root.name})")

    projects = list_projects(root)
    for project in projects:
        print(f"  • projects/{project}")

    print()
