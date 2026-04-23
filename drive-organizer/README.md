# Autonomous Drive Organizer Skill

This is a specialized capability skill designed for Claw bots (and compatible autonomous agents) to intelligently organize local hard drives or Google Drive files. It utilizes a "Divide & Conquer" batching architecture alongside an opt-in governance model with human-in-the-loop review.

## Features
- **Audit:** Scans a defined local directory or Google Drive path, ignoring hidden system files, and collecting metadata.
- **Analyze & Propose:** Flattens the file manifest and submits it to an LLM in rate-limited chunks with exponential backoff.
- **Deep Analysis (Secondary Phase):** Performs optional file-content analysis using Gemini Flash-Lite for ambiguous files.
- **Output:** Generates a `governed_actions.csv` containing broad folder taxonomy proposals.
- **Human-in-the-Loop Review:** Halts execution for the user to review proposed actions.
- **Commit:** Safely executes the approved actions, physically moving files or directly interacting with Google Drive APIs.

## Modes

| Mode | Command | Credentials required |
|------|---------|----------------------|
| **Local path** | `python3 scanner.py /path/to/folder` | None |
| **Google Drive API** | `python3 scanner.py gdrive://root` | `credentials.json` in skill dir (see below) |

> **Note:** For most users, the local-path mode is recommended. The Google Drive API mode requires OAuth credentials setup (see below) and is only needed when you want to organize Drive files that are not already mounted locally.

## Installation & Registration

### One-Line CLI Install (Recommended)
You can directly download and install this skill onto any system via curl. This will pull the specific `drive-organizer` folder from the repository and install its dependencies.

```bash
curl -sL https://raw.githubusercontent.com/ctvida/agentskills/main/drive-organizer/install.sh | bash
```

*(By default, this installs into a `./drive-organizer` directory in your current path. You can provide an argument to name the folder differently if you download the script first).*

### Bot Command Registration
If your active bot supports the `<TRUST_REPO>` autonomous registration protocol, you can simply message your bot to install it:
```text
/register_skill https://github.com/ctvida/agentskills/tree/main/drive-organizer
```

### Manual Setup (For Local Testing)
1. Clone the repository or download the skill folder.
2. Install the necessary Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set your `GEMINI_API_KEY` environment variable (required by `proposer.py`):
   ```bash
   export GEMINI_API_KEY=your_key_here
   # or create a .env file in the skill directory:
   echo "GEMINI_API_KEY=your_key_here" > .env
   ```
4. **Google Drive API only:** Place your `credentials.json` (OAuth 2.0 Desktop client) in the skill directory. On first run a browser window opens for authorization; a `token.json` is saved for reuse.

## Agent Protocol

When the bot engages this skill it strictly follows this pipeline. All output files (`audit.json`, `governed_actions.csv`) are written **to the skill's own directory** regardless of the agent's working directory.

1. **Audit:** `python3 <SKILL_DIR>/scanner.py <confirmed_path>`
   *(Safely ignores hidden files like `.DS_Store` and `desktop.ini`. Writes `audit.json` to the skill directory.)*
2. **Propose:** `python3 <SKILL_DIR>/proposer.py`
   *(Reads `audit.json` from the skill directory, batches files with exponential backoff for rate limits, writes `governed_actions.csv` to the skill directory.)*
3. **Analyze (Optional):** `python3 <SKILL_DIR>/analyzer.py governed_actions.csv [--local]`
   *(Downloads and analyzes contents of ambiguous files mapped to `/Needs_Content_Analysis/` using Gemini Flash-Lite, updating `governed_actions.csv` in-place.)*
4. **Wait:** Pauses and tells the user: *"Please review governed_actions.csv. Proposals default to TRUE. Set `approved=FALSE` for any moves you want to cancel."*
5. **Commit (local):** `python3 <SKILL_DIR>/committer.py governed_actions.csv --local <confirmed_path>`
6. **Commit (GDrive API):** `python3 <SKILL_DIR>/committer.py governed_actions.csv`

## Governance Model
The skill employs an enforced governance model to prevent unintended destructive actions. To optimize for mobile and headless execution, proposals **default to `TRUE`** (Opt-Out Governance). The Committer script will execute all proposed actions unless they are explicitly marked as `FALSE` under the `approved` column in the CSV.
