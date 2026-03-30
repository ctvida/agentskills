# JoffrieClaw Skill Development Rules

This repository (`agentskills`) is dedicated to building and organizing autonomous agent skills for **JoffrieClaw**. When developing, updating, or reviewing any skill in this repository, you MUST adhere to the following strict guidelines:

## 1. Skill Documentation (CRITICAL)
Every single skill you create MUST have a primary documentation file named exactly **`SKILL.md`** (or `skill.md`). This file acts as the entry point and manifest for JoffrieClaw's scraper.

## 2. Mandatory YAML Frontmatter
The `SKILL.md` file MUST begin with a YAML frontmatter block enclosed by `---`. JoffrieClaw parses this metadata to dynamically load the skill. Without this, the skill is invisible to the agent framework.

The minimum required format is:
```yaml
---
name: [skill-name]
description: [Short, clear description of what the skill does and when to use it]
scope: [local | global] 
---

# Skill: [Skill Name]
...
```
- **name**: Must be ≤ 64 characters, lowercase, alphanumeric with hyphens (no special characters or XML tags).
- **description**: Must clearly tell the agent *when* and *why* to use this skill. Keep it ≤ 1024 characters. No XML tags.
- **scope**: Use `local` if it's meant for a specific project directory, or `global` if it's meant to be shared across all workspaces (e.g., Gmail or Drive tools).

## 3. Skill Architecture & Design
- **Single Responsibility**: Skills should do one thing exceptionally well (e.g., "drive-organizer", "lead-finder").
- **Statelessness**: Assume scripts are executed in ephemeral environments. If state needs to be maintained, rely on JoffrieClaw's memory system or write out simple local state files (like JSON or SQLite).
- **Silent & Machine-Readable Output**: Skills are meant to be consumed by an LLM, not a human. Output structured data like JSON or clear CSVs containing the results of actions. Avoid unnecessary console logging or interactive CLI prompts (`input()`).
- **Dependencies**: For Python, use `requirements.txt`. For Node, use `package.json`. Make sure the setup steps are explicitly defined in the `SKILL.md` file.

## 4. Security & Exfiltration
- Ensure NO hardcoded API keys exist in the repository. Skills must read keys from the environment variables injected by JoffrieClaw.
- Respect JoffrieClaw's egress limitations. The framework enforces strict domain whitelisting.

## 5. Development Workflow
1. Create a new directory for your skill (e.g., `feature-name/`).
2. Write the executable scripts (`.py`, `.sh`, `.ts`).
3. Create the `SKILL.md` file inside that directory and add the YAML frontmatter.
4. Detail the **Protocol**, **Persona**, and exact command execution steps in the markdown.
