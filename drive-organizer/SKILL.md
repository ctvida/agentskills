---
name: drive-organizer
description: Organizes local directories or Google Drive (via local mount or API) into a broad folder taxonomy using a divide-and-conquer strategy with human-in-the-loop review before any files are moved.
scope: global
sandbox: host
preflight:
  ask: |
    Which drive or directory would you like me to organize? Please provide the exact local path.
    Examples:
    • /Volumes/MyExternalDrive  (external drive)
    • ~/Documents/Projects  (local folder)
    • /path/to/Google Drive/My Drive  (Google Drive mounted locally)

    Note: use the local filesystem path. Only use gdrive://root if you want to
    organize via the Google Drive REST API (requires credentials setup — see Modes below).
  satisfied_when: has_path
---

# Skill: Drive Organizer

## Modes

| Mode | Invocation | Credentials required |
|------|-----------|----------------------|
| **Local path** | `python3 scanner.py /path/to/folder` | None |
| **Google Drive API** | `python3 scanner.py gdrive://root` | `credentials.json` in skill dir (see below) |

**Google Drive API setup (one-time):**
1. Go to [Google Cloud Console](https://console.cloud.google.com/) → APIs & Services → Credentials.
2. Create an OAuth 2.0 client ID (Desktop app type). Download it as `credentials.json`.
3. Place `credentials.json` in the skill directory.
4. On first run, a browser window opens for OAuth authorization. A `token.json` is saved for reuse.

## Protocol

**Rules the executing agent MUST follow:**
1. **Never skip steps.** Always run `scanner.py` first to produce `audit.json`.
2. **Use the absolute path to this skill's directory.** Your agent runtime should provide the exact path. Do NOT guess or use a relative path.
3. **Output files land in the skill directory.** `audit.json` and `governed_actions.csv` are written relative to the script's own location — the agent does not need to handle redirection.

**Workflow:**
1. **Audit:** `python3 <SKILL_DIR>/scanner.py <confirmed_path>`
2. **Propose:** `python3 <SKILL_DIR>/proposer.py`
   *(reads `audit.json` from the skill directory, writes `governed_actions.csv`)*
3. **Wait:** Tell the user: *"Please review governed_actions.csv. Set approved=TRUE for any moves you want to proceed with."*
4. **Commit (local):** `python3 <SKILL_DIR>/committer.py governed_actions.csv --local <confirmed_path>`
5. **Commit (GDrive API):** `python3 <SKILL_DIR>/committer.py governed_actions.csv`

> [!NOTE]
> The `preflight:` YAML block is a machine-readable prerequisite declaration. Agent runtimes that support this convention will enforce it automatically before invoking the skill. If your runtime does not support it, implement the prerequisite check manually: ask the user for the target path before running any scripts.