#!/usr/bin/env python3
"""Remember where a session was exported, so a re-export lands in the same folder.

The bug this closes: `find_existing_export` only searches the folder being
written to, so exporting one session from two different working directories
produced two files instead of appending to the first. The destination is now
sticky per session id.

State is machine-local (a path on this machine means nothing on another), so it
lives under XDG state and never inside the skill, which is synced across
machines.

    sticky-dir.py get <session_id>          # prints the recorded dir, or nothing
    sticky-dir.py set <session_id> <dir>    # records it
"""

import json
import os
import sys
from pathlib import Path

STATE = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) \
    / "export-session" / "destinations.json"


def _load(path: Path = STATE) -> dict:
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        # A missing or corrupt state file must never block an export: the
        # caller falls back to the computed destination, which is the old
        # behaviour, not a failure.
        return {}


def get(session_id: str, path: Path = STATE) -> str:
    """The recorded directory for this session, if it still exists."""
    recorded = _load(path).get(session_id, "")
    return recorded if recorded and Path(recorded).is_dir() else ""


def set_(session_id: str, directory: str, path: Path = STATE) -> None:
    data = _load(path)
    data[session_id] = str(Path(directory).resolve())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def selfcheck() -> None:
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        state = Path(td) / "destinations.json"
        dest = Path(td) / "sessions"
        dest.mkdir()

        assert get("s1", state) == ""                    # nothing recorded yet
        set_("s1", str(dest), state)
        assert get("s1", state) == str(dest.resolve())    # sticks
        assert get("s2", state) == ""                     # per session, not global

        set_("s2", str(Path(td) / "gone"), state)
        assert get("s2", state) == ""                     # vanished dir is not returned

        state.write_text("{ not json")
        assert get("s1", state) == ""                     # corrupt state never raises
        set_("s1", str(dest), state)                      # and is recoverable
        assert get("s1", state) == str(dest.resolve())
    print("sticky-dir selfcheck ok")


if __name__ == "__main__":
    if "--selfcheck" in sys.argv:
        selfcheck()
    elif len(sys.argv) >= 3 and sys.argv[1] == "get":
        print(get(sys.argv[2]))
    elif len(sys.argv) >= 4 and sys.argv[1] == "set":
        set_(sys.argv[2], sys.argv[3])
    else:
        print(__doc__.strip().splitlines()[-2].strip(), file=sys.stderr)
        sys.exit(2)
