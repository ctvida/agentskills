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

It also collects skills made anywhere else, which is what skillshare is for:
a skill written inside agy, Claude or JoffrieClaw lands as a plain folder in
that tool's skills directory, and skillshare only spreads it after a manual
`skillshare collect`. Nobody ran that, so 13 skills sat as local copies in
~/.claude/skills and never reached Gemini. Now, for every plain skill folder
in a target (or in JoffrieClaw's skills dir, collect-only):

- not in skillshare's store: audited (`skillshare audit`, high and above
  blocks), then copied into the store; the target's folder becomes a link.
- in the store and identical: the copy becomes a link.
- in the store and different: reported as CONFLICT and left alone. Which
  version wins is the operator's call, not a script's.

Then `skillshare sync` links every store skill into every target. The
launchd agent `com.agentskills.link` runs this hourly.

    python3 scripts/link-skills.py           # link and collect, report what changed
    python3 scripts/link-skills.py --check   # exit 1 on any drift, change nothing
"""
import filecmp
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CONFIG = Path.home() / ".config" / "skillshare" / "config.yaml"
BACKUP = Path.home() / ".cache" / "agentskills-replaced"
# Collect-only: JoffrieClaw keeps its own skills and is not a skillshare target,
# so nothing is linked back into it.
JC = Path.home() / "Documents" / "repos" / "joffrieclaw" / "data"
COLLECT_ONLY = [JC / "default" / "skills", JC / "shared" / "skills"]
# Not JoffrieClaw's own: third-party skills it bundles (Anthropic's
# skill-creator, a generic MCP client). Claude has both natively, and the MCP
# client would compete with the real MCP servers. A skill JoffrieClaw installed
# from a URL carries .joffrie-manifest.json and is skipped the same way.
COLLECT_SKIP = {"mcpclient", "skillcreator"}
NOISE = [".DS_Store", "__pycache__", ".remember"]


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


def _same(a: Path, b: Path) -> bool:
    c = filecmp.dircmp(a, b, ignore=NOISE)
    if c.left_only or c.right_only or c.diff_files or c.funny_files:
        return False
    return all(_same(a / d, b / d) for d in c.common_dirs)


def _audit_ok(path: Path) -> bool:
    r = subprocess.run(["skillshare", "audit", str(path), "--threshold", "high"],
                       capture_output=True, text=True)
    return r.returncode == 0


def _backup(at: Path) -> None:
    BACKUP.mkdir(parents=True, exist_ok=True)
    at.rename(BACKUP / f"{at.name}-{at.parent.parent.name}-{time.strftime('%Y%m%d%H%M%S')}")


def collect(store: Path, targets: list, collect_only: list, own: set,
            audit=_audit_ok, check: bool = False) -> list:
    """Bring plain skill folders from targets into the store (see module doc)."""
    out = []
    for src in list(targets) + list(collect_only):
        if not src.is_dir() or src.resolve() == store.resolve():
            continue
        linkable = src in targets
        for at in sorted(src.iterdir()):
            if at.is_symlink() or not (at / "SKILL.md").is_file() or at.name in own:
                continue
            if not linkable and (at.name in COLLECT_SKIP or (at / ".joffrie-manifest.json").exists()):
                continue
            home = store / at.name
            if home.exists():
                if not _same(at, home):
                    out.append(f"CONFLICT {at} differs from {home}; left alone")
                    continue
                if not linkable:
                    continue
                out.append(f"relinked {at} -> {home}")
            else:
                if not check and not audit(at):
                    out.append(f"BLOCKED {at}: skillshare audit found high-severity issues")
                    continue
                out.append(f"collected {at} -> {home}")
                if not check:
                    shutil.copytree(at, home, symlinks=True,
                                    ignore=shutil.ignore_patterns(*NOISE))
            if check or not linkable:
                continue
            _backup(at)
            at.symlink_to(home)
    return out


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

        # collect: new -> store + link; identical -> link; different -> left alone
        store, tgt, jc = d / "store", d / "tgt", d / "jc"
        for folder, body in ((tgt / "fresh", "new"), (tgt / "same", "s"), (tgt / "clash", "mine"),
                             (tgt / "bad", "evil"), (store / "same", "s"),
                             (store / "clash", "theirs"), (jc / "jskill", "j")):
            folder.mkdir(parents=True)
            (folder / "SKILL.md").write_text(body)
        (jc / "webskill").mkdir()
        (jc / "webskill" / "SKILL.md").write_text("w")
        (jc / "webskill" / ".joffrie-manifest.json").write_text("{}")
        (tgt / "one").symlink_to(repo / "one")      # agentskills-owned: never collected
        audit = lambda p: p.name != "bad"
        assert collect(store, [tgt], [jc], {"one"}, audit, check=True) and \
            not (store / "fresh").exists(), "check changed files"
        lines = collect(store, [tgt], [jc], {"one"}, audit)
        assert (store / "fresh" / "SKILL.md").read_text() == "new"
        assert (tgt / "fresh").resolve() == (store / "fresh").resolve()
        assert (tgt / "same").resolve() == (store / "same").resolve()
        assert (tgt / "clash").is_dir() and not (tgt / "clash").is_symlink()
        assert (store / "clash" / "SKILL.md").read_text() == "theirs"
        assert not (store / "bad").exists() and any(l.startswith("BLOCKED") for l in lines)
        assert (store / "jskill").is_dir() and not (jc / "jskill").is_symlink(), "collect-only"
        assert not (store / "webskill").exists(), "a JoffrieClaw web install was collected"
        assert [l for l in collect(store, [tgt], [jc], {"one"}, audit)
                if not l.startswith(("CONFLICT", "BLOCKED"))] == [], "second run is a no-op"
    print("[OK] link-skills self-check passed")


if __name__ == "__main__":
    if "--selfcheck" in sys.argv:
        demo()
        sys.exit(0)
    check = "--check" in sys.argv
    dests = destinations()
    lines = [("DRIFT " if check else "linked ") + l for l in link_all(dests=dests, check=check)]
    lines += collect(dests[0], dests[1:], COLLECT_ONLY, {p.name for p in skills()}, check=check)
    if not check and shutil.which("skillshare"):
        subprocess.run(["skillshare", "sync"], capture_output=True)
    for line in lines:
        print(line)
    sys.exit(1 if check and lines else 0)
