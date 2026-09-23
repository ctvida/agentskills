#!/usr/bin/env python3
"""Link every skill in this repo into every agent's skills directory.

This repo is the only source for its skills. Every destination gets a symlink
straight to the skill folder here: skillshare's store and each target path in
skillshare's config (Claude, Gemini, Antigravity, ~/.agents). Straight to the
folder, because skillshare does not propagate a store entry that is itself a
symlink, so linking the store alone left Gemini and Antigravity without the
skill. A real directory found at a destination is a stale copy: it is moved to
~/.cache/agentskills-replaced/ (never deleted) and replaced by the link.

On 2026-09-23 export-session existed as three drifted copies, and three of the
four skills here reached Claude only. The post-commit and post-merge hooks run
this, so a new or renamed skill is linked the moment it lands.

    python3 scripts/link-skills.py           # link, report what changed
    python3 scripts/link-skills.py --check   # exit 1 on any drift, change nothing
"""
import re
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CONFIG = Path.home() / ".config" / "skillshare" / "config.yaml"
BACKUP = Path.home() / ".cache" / "agentskills-replaced"


def destinations(config: Path = CONFIG) -> list:
    """skillshare's source plus every target path, deduped, in config order.
    ponytail: two regexes, not a YAML parser; the file is one level of `path:`."""
    text = config.read_text() if config.is_file() else ""
    found = re.findall(r"^source:\s*(\S+)", text, re.M) + re.findall(r"^\s+path:\s*(\S+)", text, re.M)
    out = []
    for raw in found:
        p = Path(raw).expanduser()
        if p not in out:
            out.append(p)
    return out or [Path.home() / ".claude" / "skills"]


def skills(repo: Path = REPO) -> list:
    return sorted(p for p in repo.iterdir() if (p / "SKILL.md").is_file())


def link_all(repo: Path = REPO, dests: list = None, check: bool = False) -> list:
    """Returns one line per destination that was (or, with check, would be) changed."""
    changed = []
    for dest in destinations() if dests is None else dests:
        for skill in skills(repo):
            at = dest / skill.name
            if at.is_symlink() and at.resolve() == skill.resolve():
                continue
            changed.append(f"{at} -> {skill}")
            if check:
                continue
            dest.mkdir(parents=True, exist_ok=True)
            if at.is_symlink():
                at.unlink()
            elif at.exists():
                BACKUP.mkdir(parents=True, exist_ok=True)
                at.rename(BACKUP / f"{skill.name}-{dest.parent.name}-{time.strftime('%Y%m%d%H%M%S')}")
            at.symlink_to(skill)
    return changed


def demo() -> None:
    import tempfile
    global BACKUP
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        repo, a, b = d / "repo", d / "a", d / "b"
        (repo / "one").mkdir(parents=True)
        (repo / "one" / "SKILL.md").write_text("x")
        (repo / "notes").mkdir()                      # no SKILL.md: not a skill
        (b / "one").mkdir(parents=True)               # a stale copy
        (b / "one" / "SKILL.md").write_text("old")
        BACKUP = d / "backup"
        assert len(link_all(repo, [a, b], check=True)) == 2
        assert (b / "one").is_dir() and not (b / "one").is_symlink(), "check changed files"
        assert len(link_all(repo, [a, b])) == 2
        for dest in (a, b):
            assert (dest / "one").resolve() == (repo / "one").resolve()
            assert not (dest / "notes").exists()
        assert (next(BACKUP.iterdir()) / "SKILL.md").read_text() == "old", "the copy was lost"
        assert link_all(repo, [a, b]) == [], "second run must be a no-op"
    print("[OK] link-skills self-check passed")


if __name__ == "__main__":
    if "--selfcheck" in sys.argv:
        demo()
        sys.exit(0)
    check = "--check" in sys.argv
    lines = link_all(check=check)
    for line in lines:
        print(("DRIFT " if check else "linked ") + line)
    sys.exit(1 if check and lines else 0)
