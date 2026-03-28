# Autonomous Drive Organizer Skill

This is a specialized capability skill designed for Claw bots (and compatible autonomous agents) to intelligently organize local hard drives or Google Drive files. It utilizes a "Divide & Conquer" batching architecture alongside an opt-in governance model with human-in-the-loop review.

## Features
- **Audit:** Scans a defined local directory or Google Drive path and collects contextual metadata.
- **Analyze:** Groups files logically by modification time (`mtime`) and path context.
- **Propose:** Generates a `governed_actions.csv` containing proposed operations.
- **Human-in-the-Loop Review:** Halts execution for the user to review proposed actions.
- **Commit:** Safely executes the approved actions, physically moving files or directly interacting with Google Drive APIs.

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
3. Place your Google API `credentials.json` in the root of the skill folder (if targeting Google Drive). Upon first run, it will generate a `token.json` for subsequent auth.

## Agent Protocol

When the bot engages this skill, it strictly follows this pipeline:
1. **Audit:** Executes `python3 scanner.py [gdrive://root | /local/path]`. For example, `python3 scanner.py gdrive://root` or `python3 scanner.py /Users/toraphan/Documents/`.
2. **Analyze:** Reads the output JSON, grouping files logically.
3. **Propose:** Proposes actions directly to `governed_actions.csv`.
4. **Wait:** Pauses execution and notifies the user: *"Please review governed_actions.csv and set 'approved=TRUE' for the moves you want."*
5. **Commit:** Following review, executes `python3 committer.py governed_actions.csv [--local /base/path]`. If organizing local drives, the `--local` flag alongside the base directory is required to physically move the files.

## Governance Model
The skill employs an enforced governance model to prevent unintended destructive actions. The Committer script will **only** execute actions explicitly marked as `TRUE` under the `approved` column in the CSV. Any unapproved or invalid changes are safely ignored.
