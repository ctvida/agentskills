#!/usr/bin/env python3
"""
Export Claude sessions to markdown with auto-generated summaries and tags.
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
import re

# Slash commands that are about the AI/harness itself rather than the thread topic.
# These are filtered out of exports so the conversation reads as a clean record
# of what was actually worked on.
_AI_META_COMMAND_RE = re.compile(
    r"^\s*/"
    r"(usage|context|cost|model|status|help|memory|permissions|reload[-_]?plugins"
    r"|plugin|settings|config|version|session|whoami|logout|login|doctor|bug"
    r"|tokens|billing|limits|quota|upgrade|account|profile|feedback|report"
    r"|history|debug|trace|reset|clear|exit|quit)"
    r"(\s|$)",
    re.IGNORECASE,
)


def is_ai_meta_command(text: str) -> bool:
    """Return True if a user message is a slash-command about the AI/harness itself.

    These turns are not part of the work conversation and should be excluded from
    session exports (e.g. /usage, /context, /cost, /memory, /help, etc.).
    """
    return bool(_AI_META_COMMAND_RE.match(text.strip()))

def detect_harness() -> str:
    """Detect which AI harness is currently running."""
    # Check for Claude Code
    if os.getenv("CLAUDE_SESSION_ID"):
        return "claude-code"

    try:
        subprocess.run(["claude", "--version"], capture_output=True, check=True, timeout=2)
        return "claude-code"
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Check for Hermes
    if os.getenv("HERMES_API_KEY") or os.getenv("HERMES_MODEL"):
        return "hermes"

    # Check for other local harnesses
    if os.getenv("LOCALAI_API_URL") or os.getenv("OLLAMA_HOST"):
        return "local-inference"

    return "unknown"


def get_model() -> str:
    """Determine which model to use for summarization."""
    # 1. Explicit environment variable override
    if env_model := os.getenv("CLAUDE_EXPORT_MODEL"):
        return env_model

    harness = detect_harness()

    # 2. If in Claude Code, use subscription (lowest reasoning model = Haiku)
    if harness == "claude-code":
        return "claude-p-haiku"

    # 3. If not in Claude Code, check what's available and prompt user
    print(f"\nDetected harness: {harness}", file=sys.stderr)
    print("To use a different model, set CLAUDE_EXPORT_MODEL environment variable:", file=sys.stderr)
    print("  export CLAUDE_EXPORT_MODEL='mlx://hermes-2-pro-mistral'", file=sys.stderr)
    print("  export CLAUDE_EXPORT_MODEL='ollama://mistral'", file=sys.stderr)
    print("  export CLAUDE_EXPORT_MODEL='openrouter://meta-llama/llama-2-7b-chat:free'", file=sys.stderr)
    print("", file=sys.stderr)

    # Check for MLX
    try:
        subprocess.run(["python3", "-c", "import mlx_lm"], capture_output=True, check=True, timeout=2)
        print("Using MLX (local, free)...", file=sys.stderr)
        return "mlx://hermes-2-pro-mistral"
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.CalledProcessError):
        pass

    # Check for Ollama
    try:
        subprocess.run(["ollama", "--version"], capture_output=True, check=True, timeout=2)
        print("Using Ollama (local, free)...", file=sys.stderr)
        return "ollama://mistral"
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Check for OpenRouter
    if os.getenv("OPENROUTER_API_KEY"):
        print("Using OpenRouter free tier (cheap)...", file=sys.stderr)
        return "openrouter://meta-llama/llama-2-7b-chat:free"

    # Fallback: Claude Code if available
    return "claude-p-haiku"


def get_session_context(session_id: str) -> str:
    """
    Reconstruct the conversation from Claude Code's on-disk JSONL transcript
    (~/.claude/projects/<slugified-cwd>/<session_id>.jsonl). Works the same
    way for the current session and past sessions - the transcript is the
    only complete record of either.
    """
    matches = list((Path.home() / ".claude" / "projects").glob(f"*/{session_id}.jsonl"))
    if not matches:
        raise FileNotFoundError(f"No transcript found for session {session_id}")

    turns = []
    skip_next_assistant = False  # True when the previous user turn was a meta-command
    with open(matches[0], "r") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            if entry.get("isSidechain"):
                continue

            content = entry.get("message", {}).get("content")

            if entry.get("type") == "user" and isinstance(content, str):
                if is_ai_meta_command(content):
                    # Skip this turn and suppress the assistant reply that follows
                    skip_next_assistant = True
                    continue
                skip_next_assistant = False
                turns.append(f"**User:**\n\n{content}\n")
            elif entry.get("type") == "assistant" and isinstance(content, list):
                if skip_next_assistant:
                    skip_next_assistant = False
                    continue
                text = "\n".join(b["text"] for b in content if b.get("type") == "text")
                if text.strip():
                    turns.append(f"**Assistant:**\n\n{text}\n")

    if not turns:
        raise ValueError(f"No conversation content found for session {session_id}")

    return "\n".join(turns)


def sample_transcript(text: str, budget: int = 6000) -> str:
    """Head+middle+tail sample so summaries reflect the whole arc, not just the opening."""
    if len(text) <= budget:
        return text
    chunk = budget // 3
    mid_start = len(text) // 2 - chunk // 2
    return (
        text[:chunk]
        + "\n[... elided ...]\n"
        + text[mid_start:mid_start + chunk]
        + "\n[... elided ...]\n"
        + text[-chunk:]
    )


def generate_summary_and_tags(conversation: str, model: str) -> tuple[str, list[str]]:
    """
    Use Claude to generate a concise summary and semantic tags.
    """
    if len(conversation.strip()) < 200:
        print(
            f"Error: transcript is only {len(conversation.strip())} chars after stripping - "
            "likely loaded the wrong session or an empty one. Refusing to summarize emptiness.",
            file=sys.stderr,
        )
        sys.exit(1)

    prompt = f"""Analyze this conversation and provide:
1. A one-line summary (max 60 characters)
2. Exactly 3-5 semantic tags (comma-separated, lowercase, no brackets)

Focus on what the conversation is ABOUT, not actions to take.
Use semantic tags like: [trading, architecture, debugging, learning, strategy, analysis, etc.]

Examples:
- Summary: "Fundamental analysis backtesting strategy"
  Tags: trading, backtesting, strategy, learning

- Summary: "Design patterns for agentic systems"
  Tags: architecture, agents, design-patterns, learning

CONVERSATION:
{sample_transcript(conversation)}

Respond with ONLY these two lines (no other text):
SUMMARY: [your 60-char summary]
TAGS: [tag1, tag2, tag3, ...]"""

    try:
        if model in ("claude-p", "claude-p-haiku"):
            # Use claude -p (subscription, no extra cost)
            result = subprocess.run(
                ["claude", "-p", prompt],
                capture_output=True,
                text=True,
                timeout=30
            )
        elif model.startswith("mlx://"):
            model_name = model.split("://")[1]
            result = subprocess.run(
                ["python3", "-m", "mlx_lm.generate", "--model", model_name, "--prompt", prompt, "--max-tokens", "200"],
                capture_output=True,
                text=True,
                timeout=45
            )
        elif model.startswith("ollama://"):
            model_name = model.split("://")[1]
            result = subprocess.run(
                ["ollama", "run", model_name, prompt],
                capture_output=True,
                text=True,
                timeout=30
            )
        elif model.startswith("openrouter://"):
            model_name = model.split("://")[1]
            # OpenRouter API call
            result = _call_openrouter(prompt, model_name)
        else:
            raise ValueError(f"Unknown model: {model}")

        if result.returncode != 0:
            raise RuntimeError(f"Model inference failed: {result.stderr}")

        output = result.stdout.strip()

        # Parse response
        summary = ""
        tags = []
        for line in output.split("\n"):
            if line.startswith("SUMMARY:"):
                summary = line.replace("SUMMARY:", "").strip()
            elif line.startswith("TAGS:"):
                tags_str = line.replace("TAGS:", "").strip()
                tags = [t.strip() for t in tags_str.split(",")]

        if not summary:
            summary = "Untitled conversation"
        if not tags:
            tags = ["conversation"]

        return summary, tags[:5]  # Enforce max 5 tags

    except Exception as e:
        print(f"Warning: Could not generate summary via {model}: {e}", file=sys.stderr)
        return "Exported conversation", ["conversation"]


def _call_openrouter(prompt: str, model: str) -> subprocess.CompletedProcess:
    """Call OpenRouter API for model inference."""
    import urllib.request
    import json as json_module

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not set")

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    data = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 200,
    }

    req = urllib.request.Request(
        url,
        data=json_module.dumps(data).encode(),
        headers=headers,
        method="POST"
    )

    try:
        with urllib.request.urlopen(req) as response:
            result = json_module.loads(response.read())
            text = result["choices"][0]["message"]["content"]
            return subprocess.CompletedProcess(
                args="openrouter",
                returncode=0,
                stdout=text,
                stderr=""
            )
    except Exception as e:
        return subprocess.CompletedProcess(
            args="openrouter",
            returncode=1,
            stdout="",
            stderr=str(e)
        )


def format_markdown(conversation: str, summary: str, tags: list[str],
                    session_id: str, user_note: str, project_path: str, model: str) -> str:
    """Format the conversation as markdown with frontmatter."""

    # Create filename from summary
    slug = re.sub(r"[^a-z0-9]+", "-", summary.lower()).strip("-")[:40]
    now = datetime.now()
    filename = f"{now.strftime('%Y-%m-%d-%H%M')}-{slug}.md"

    # Build frontmatter
    frontmatter = f"""---
date: {now.isoformat()}
session_id: {session_id}
summary: {summary}
tags: {json.dumps(tags)}
project: {project_path}
user_note: {user_note if user_note else ""}
model_used: {model}
---

# {summary}

**Exported:** {now.strftime('%B %d, %Y at %H:%M')}
**Session:** `{session_id}`
**Tags:** {', '.join(f'`{t}`' for t in tags)}

{f'**Note:** {user_note}' if user_note else ''}

## Conversation

{conversation}
"""

    return frontmatter, filename


def main():
    parser = argparse.ArgumentParser(description="Export Claude sessions to markdown")
    parser.add_argument("--session-id", required=True, help="Session ID to export")
    parser.add_argument("--output-dir", required=True, help="Output directory")
    parser.add_argument("--user-note", default="", help="Optional user note")
    parser.add_argument("--project-root", default="",
                        help="Project root recorded in frontmatter (defaults to output dir's parent)")

    args = parser.parse_args()

    try:
        # Get model
        model = get_model()

        # Retrieve session context
        print(f"Retrieving session {args.session_id}...", file=sys.stderr)
        conversation = get_session_context(args.session_id)

        # Generate summary and tags
        print(f"Generating summary and tags (using {model})...", file=sys.stderr)
        summary, tags = generate_summary_and_tags(conversation, model)

        # Format as markdown
        project_root = args.project_root or str(Path(args.output_dir).parent.parent)
        markdown, filename = format_markdown(
            conversation, summary, tags, args.session_id,
            args.user_note, project_root, model
        )

        # Write to file
        output_path = Path(args.output_dir) / filename
        output_path.write_text(markdown)

        # Print summary
        print(f"\n✓ Exported to: {output_path}")
        print(f"Summary: {summary}")
        print(f"Tags: {', '.join(tags)}")
        if args.user_note:
            print(f"Note: {args.user_note}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
