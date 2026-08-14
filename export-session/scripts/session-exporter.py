#!/usr/bin/env python3
"""
Export Claude sessions to markdown with auto-generated summaries and tags.
"""

import argparse
import difflib
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

# A slash command typed by the user is stored as plain "/command args" text, but a
# harness meta-command (e.g. /model) is instead expanded into an XML-ish block whose
# <command-name> tag holds the actual command. Check that tag's content, not the raw
# text, or these commands slip past the regex above undetected.
_COMMAND_NAME_TAG_RE = re.compile(r"<command-name>\s*(.*?)\s*</command-name>", re.IGNORECASE | re.DOTALL)

# The output of a local (harness-handled) command, e.g. /model's confirmation
# message. Arrives as its own separate "user" turn immediately after the
# <command-name> turn, not as an assistant reply, so it needs its own skip.
_LOCAL_COMMAND_OUTPUT_RE = re.compile(r"^\s*<local-command-(?:stdout|stderr)>", re.IGNORECASE)


def is_ai_meta_command(text: str) -> bool:
    """Return True if a user message is a slash-command about the AI/harness itself.

    These turns are not part of the work conversation and should be excluded from
    session exports (e.g. /usage, /context, /cost, /memory, /help, etc.). Handles
    both plain "/model" text and the <command-name>/model</command-name> block the
    harness expands typed commands into.
    """
    text = text.strip()
    if m := _COMMAND_NAME_TAG_RE.search(text):
        text = m.group(1)
    return bool(_AI_META_COMMAND_RE.match(text))


def is_local_command_output(text: str) -> bool:
    """Return True if a user turn is a <local-command-stdout/stderr> block."""
    return bool(_LOCAL_COMMAND_OUTPUT_RE.match(text.strip()))

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


def get_session_turns(session_id: str) -> list[str]:
    """
    Reconstruct the conversation from Claude Code's on-disk JSONL transcript
    (~/.claude/projects/<slugified-cwd>/<session_id>.jsonl), one rendered
    markdown block per turn. Works the same way for the current session and
    past sessions - the transcript is the only complete record of either.
    """
    matches = list((Path.home() / ".claude" / "projects").glob(f"*/{session_id}.jsonl"))
    if not matches:
        raise FileNotFoundError(f"No transcript found for session {session_id}")

    turns = []
    skip_next_assistant = False  # True when the previous user turn was a meta-command
    skip_next_output = False  # True when the previous user turn was a meta-command's <command-name> block
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
                if skip_next_output and is_local_command_output(content):
                    skip_next_output = False
                    continue
                skip_next_output = False
                if is_ai_meta_command(content):
                    # Skip this turn, its local-command-stdout, and the assistant reply that follows
                    skip_next_assistant = True
                    skip_next_output = True
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

    return turns


# --- Appending to a previous export of the same session -------------------

# Sentinel that opens each appended section. Exact-match so continuation
# headings can be stripped before diffing without touching turn content.
_CONT_SENTINEL = "<!-- export-continued -->"
_CONT_RE = re.compile(rf"\n*{re.escape(_CONT_SENTINEL)}\n### Continued [^\n]*\n", re.M)
_TURN_RE = re.compile(r"^\*\*(?:User|Assistant):\*\*$", re.M)


def find_existing_export(output_dir: Path, session_id: str) -> Optional[Path]:
    """Newest export in output_dir whose frontmatter records this session, if any."""
    pattern = re.compile(rf"^session_id: {re.escape(session_id)}\s*$", re.M)
    matches = [p for p in output_dir.glob("*.md") if pattern.search(p.read_text()[:2000])]
    return max(matches, key=lambda p: p.stat().st_mtime, default=None)


def split_turns(exported: str) -> list[str]:
    """Split a previously exported markdown file back into turn blocks."""
    body = _CONT_RE.sub("\n", exported)
    starts = [m.start() for m in _TURN_RE.finditer(body)]
    return [body[a:b].strip() for a, b in zip(starts, starts[1:] + [len(body)])]


def turns_after(old: list[str], new: list[str]) -> list[str]:
    """Turns in `new` that follow everything already present in `old`.

    Diffs the two turn lists and returns the tail of `new` past the last
    common block, so re-exports append only what the session has said since.
    """
    old = [t.strip() for t in old]
    stripped = [t.strip() for t in new]
    blocks = difflib.SequenceMatcher(None, old, stripped, autojunk=False).get_matching_blocks()
    last = max((b for b in blocks if b.size), key=lambda b: b.b + b.size, default=None)
    return new if last is None else new[last.b + last.size:]


def _set_field(frontmatter: str, key: str, value: str) -> str:
    """Replace `key:` in a frontmatter block, or append it if absent."""
    line = f"{key}: {value}"
    updated, count = re.subn(rf"(?m)^{re.escape(key)}: ?.*$", lambda _: line, frontmatter)
    return updated if count else frontmatter.rstrip("\n") + "\n" + line + "\n"


def update_frontmatter(exported: str, **fields: str) -> str:
    """Rewrite frontmatter fields in place, preserving field order."""
    if not exported.startswith("---\n"):
        raise ValueError("export has no frontmatter to update")
    end = exported.index("\n---\n", 3) + 1
    frontmatter = exported[4:end]
    for key, value in fields.items():
        frontmatter = _set_field(frontmatter, key, value)
    return "---\n" + frontmatter + exported[end:]


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


REDACT_FILE = Path(os.environ.get(
    "EXPORT_SESSION_REDACT_FILE", Path.home() / ".agents" / "redact-terms.txt"))


def load_redactions(path: Path = None) -> list[str]:
    """Terms to strip from an export, one per line, '#' comments allowed.

    The terms live OUTSIDE this script on purpose. An export lands in a tracked
    directory, so anything the operator will not have in a repo must not be in
    the exporter either — this skill is itself synced across machines and tools.
    Missing file means no redaction, which is the right default for anyone who
    has not opted in.
    """
    p = path or REDACT_FILE
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    return [ln.strip() for ln in lines if ln.strip() and not ln.lstrip().startswith("#")]


def redact(text: str, terms: list[str]) -> tuple[str, int]:
    """Case-insensitively replace each term with [REDACTED]. Returns (text, hits).

    Whole-word-ish: bounded by non-word characters so 'tuck' does not maul
    'Kentucky'. Longest terms first so 'Acme Global' wins over 'Acme'.
    """
    hits = 0
    for term in sorted(terms, key=len, reverse=True):
        pattern = re.compile(r"(?<!\w)" + re.escape(term) + r"(?!\w)", re.IGNORECASE)
        text, n = pattern.subn("[REDACTED]", text)
        hits += n
    return text, hits


def main():
    parser = argparse.ArgumentParser(description="Export Claude sessions to markdown")
    parser.add_argument("--session-id", required=True, help="Session ID to export")
    parser.add_argument("--output-dir", required=True, help="Output directory")
    parser.add_argument("--user-note", default="", help="Optional user note")
    parser.add_argument("--project-root", default="",
                        help="Project root recorded in frontmatter (defaults to output dir's parent)")
    parser.add_argument("--new", action="store_true",
                        help="Always write a new file, even if this session was exported before")

    args = parser.parse_args()

    try:
        # Get model
        model = get_model()

        # Retrieve session context
        print(f"Retrieving session {args.session_id}...", file=sys.stderr)
        turns = get_session_turns(args.session_id)
        conversation = "\n".join(turns)

        output_dir = Path(args.output_dir)
        existing = None if args.new else find_existing_export(output_dir, args.session_id)

        if existing:
            exported = existing.read_text()
            fresh = turns_after(split_turns(exported), turns)
            if not fresh:
                print(f"\n✓ {existing} is already up to date ({len(turns)} turns); nothing to append.")
                return

            print(f"Generating summary and tags (using {model})...", file=sys.stderr)
            summary, tags = generate_summary_and_tags(conversation, model)

            # Scrub before writing, never after: an export lands in a tracked
            # directory, and a file that has to be fixed up post-write has already
            # been committable for however long that took.
            fresh_text = "\n".join(fresh)
            terms = load_redactions()
            if terms:
                fresh_text, hits = redact(fresh_text, terms)
                print(f"Redaction: {len(terms)} term(s) from {REDACT_FILE}, "
                      f"{hits} occurrence(s) replaced", file=sys.stderr)
            else:
                print(f"Redaction: no term list at {REDACT_FILE} — nothing scrubbed",
                      file=sys.stderr)

            now = datetime.now()
            fields = {"summary": summary, "tags": json.dumps(tags), "updated": now.isoformat()}
            if args.user_note:
                fields["user_note"] = args.user_note
            exported = update_frontmatter(exported, **fields)
            exported = (
                exported.rstrip("\n")
                + f"\n\n{_CONT_SENTINEL}\n### Continued {now.strftime('%B %d, %Y at %H:%M')}\n\n"
                + fresh_text
                + "\n"
            )
            existing.write_text(exported)

            print(f"\n✓ Appended {len(fresh)} new turns to: {existing}")
            print(f"Summary: {summary}")
            print(f"Tags: {', '.join(tags)}")
            if args.user_note:
                print(f"Note: {args.user_note}")
            if terms:
                print(f"Redacted: {hits} occurrence(s) of {len(terms)} protected term(s)")
            return

        # Generate summary and tags
        print(f"Generating summary and tags (using {model})...", file=sys.stderr)
        summary, tags = generate_summary_and_tags(conversation, model)

        # Format as markdown
        project_root = args.project_root or str(output_dir.parent.parent)
        markdown, filename = format_markdown(
            conversation, summary, tags, args.session_id,
            args.user_note, project_root, model
        )

        # Scrub before writing, never after: an export lands in a tracked
        # directory, and a file that has to be fixed up post-write has already
        # been committable for however long that took.
        terms = load_redactions()
        if terms:
            markdown, hits = redact(markdown, terms)
            print(f"Redaction: {len(terms)} term(s) from {REDACT_FILE}, "
                  f"{hits} occurrence(s) replaced", file=sys.stderr)
        else:
            print(f"Redaction: no term list at {REDACT_FILE} — nothing scrubbed",
                  file=sys.stderr)

        # Write to file
        output_path = output_dir / filename
        output_path.write_text(markdown)

        # Print summary
        print(f"\n✓ Exported to: {output_path}")
        print(f"Summary: {summary}")
        print(f"Tags: {', '.join(tags)}")
        if args.user_note:
            print(f"Note: {args.user_note}")
        if terms:
            print(f"Redacted: {hits} occurrence(s) of {len(terms)} protected term(s)")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def selftest():
    """Check meta-command filtering, then the append path: splitting, diffing, frontmatter rewrite."""
    # /model expands to a <command-name> block, not plain "/model" text - must
    # still be detected, along with its separate <local-command-stdout> turn.
    assert is_ai_meta_command(
        "<command-name>/model</command-name>\n            "
        "<command-message>model</command-message>\n            <command-args></command-args>"
    )
    assert is_ai_meta_command(
        "<command-message>export-session</command-message>\n<command-name>/model</command-name>"
    )
    assert not is_ai_meta_command(
        "<command-message>export-session</command-message>\n<command-name>/export-session</command-name>"
    )
    assert is_local_command_output(
        "<local-command-stdout>Set model to \x1b[1mOpus 5\x1b[22m and saved as your default</local-command-stdout>"
    )
    assert not is_ai_meta_command("plain conversation text, no command here")

    redacted, hits = redact("Acme Global signed with Acme, not Kentucky Acme Corp.", ["Acme Global", "Acme"])
    assert redacted == "[REDACTED] signed with [REDACTED], not Kentucky [REDACTED] Corp.", redacted
    assert hits == 3

    turns = [
        "**User:**\n\nfirst question\n",
        "**Assistant:**\n\n### A heading inside a reply\n\nfirst answer\n",
        "**User:**\n\nok\n",
        "**Assistant:**\n\nsecond answer\n",
        "**User:**\n\nok\n",  # duplicate text, must not collapse
    ]
    exported = (
        "---\ndate: 2026-08-10T22:00:00\nsession_id: abc\nsummary: Old\n"
        'tags: ["a"]\nuser_note: \nmodel_used: claude-p-haiku\n---\n\n'
        "# Old\n\n## Conversation\n\n" + "\n".join(turns[:2]) + "\n"
    )

    assert split_turns(exported) == [t.strip() for t in turns[:2]], split_turns(exported)
    assert turns_after(split_turns(exported), turns) == turns[2:]

    updated = update_frontmatter(exported, summary="New", tags='["b"]', updated="2026-08-10T23:00:00")
    assert "summary: New" in updated and "summary: Old" not in updated
    assert 'tags: ["b"]' in updated
    assert "updated: 2026-08-10T23:00:00" in updated
    assert updated.index("summary:") < updated.index("tags:"), "field order not preserved"
    assert updated.split("---\n")[2].startswith("\n# Old"), "body mangled"

    # A second append: continuation sentinel is stripped, no turns re-appended.
    appended = (
        updated.rstrip("\n")
        + f"\n\n{_CONT_SENTINEL}\n### Continued August 10, 2026 at 23:00\n\n"
        + "\n".join(turns[2:])
        + "\n"
    )
    assert split_turns(appended) == [t.strip() for t in turns], split_turns(appended)
    assert turns_after(split_turns(appended), turns) == []
    assert turns_after(split_turns(appended), turns + ["**User:**\n\nmore\n"]) == ["**User:**\n\nmore\n"]

    print("selftest ok")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        main()
