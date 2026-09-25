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

    # Check for Antigravity IDE
    if os.getenv("ANTIGRAVITY_AGENT") or os.getenv("ANTIGRAVITY_CONVERSATION_ID"):
        return "antigravity"

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


def get_model(cli_model: Optional[str] = None) -> str:
    """Determine which model to use for summarization."""
    # 1. Explicit CLI argument
    if cli_model:
        return cli_model

    # 2. Explicit environment variable override
    if env_model := os.getenv("CLAUDE_EXPORT_MODEL"):
        return env_model

    # 3. Prefer Gemini 3.7 Flash via agy CLI if available (fast, 1M context, saves Claude quota)
    try:
        subprocess.run(["agy", "--version"], capture_output=True, check=True, timeout=2)
        return "gemini-3.7-flash-medium"
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        pass

    harness = detect_harness()

    # 4. If in Claude Code or claude is available, use subscription (Haiku)
    if harness == "claude-code":
        return "claude-p-haiku"

    try:
        subprocess.run(["claude", "--version"], capture_output=True, check=True, timeout=2)
        return "claude-p-haiku"
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        pass

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


def parse_agy_transcript(path: Path, session_id: str) -> list[str]:
    """Reconstruct conversation from Antigravity IDE JSONL transcript."""
    turns = []
    skip_next_assistant = False
    with open(path, "r", errors="ignore") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            etype = entry.get("type")
            if etype == "USER_INPUT":
                content = entry.get("content")
                if not isinstance(content, str) or not content.strip():
                    continue
                m = re.search(r"<USER_REQUEST>(.*?)</USER_REQUEST>", content, re.DOTALL)
                text = m.group(1).strip() if m else content.strip()
                if is_ai_meta_command(text):
                    skip_next_assistant = True
                    continue
                skip_next_assistant = False
                turns.append(f"**User:**\n\n{text}\n")
            elif etype == "PLANNER_RESPONSE":
                if skip_next_assistant:
                    continue
                content = entry.get("content")
                if isinstance(content, str) and content.strip():
                    turns.append(f"**Assistant:**\n\n{content.strip()}\n")

    if not turns:
        raise ValueError(f"No conversation content found for session {session_id}")
    return turns


def parse_claude_transcript(path: Path, session_id: str) -> list[str]:
    """Reconstruct conversation from Claude Code JSONL transcript."""
    turns = []
    skip_next_assistant = False
    skip_next_output = False
    with open(path, "r", errors="ignore") as f:
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


def get_session_turns(session_id: str, transcript_path: str = "") -> list[str]:
    """
    Reconstruct the conversation from on-disk JSONL transcript,
    one rendered markdown block per turn. Supports both Antigravity IDE
    and Claude Code transcripts.
    """
    path = None
    if transcript_path:
        p = Path(transcript_path)
        if p.is_file():
            path = p
        else:
            raise FileNotFoundError(f"Specified transcript file not found: {transcript_path}")
    else:
        # 1. Check Antigravity brain directories
        brain_dirs = [
            Path.home() / ".gemini" / "antigravity" / "brain",
            Path.home() / ".gemini" / "antigravity-ide" / "brain",
            Path.home() / ".gemini" / "antigravity-cli" / "brain",
        ]
        agy_candidate = None
        for bdir in brain_dirs:
            cand = bdir / session_id / ".system_generated" / "logs" / "transcript.jsonl"
            if cand.is_file():
                agy_candidate = cand
                break
        if agy_candidate:
            path = agy_candidate
        else:
            # 2. Check Claude Code projects
            matches = list((Path.home() / ".claude" / "projects").glob(f"*/{session_id}.jsonl"))
            if matches:
                path = matches[0]
            else:
                raise FileNotFoundError(f"No transcript found for session {session_id}")

    # Detect format
    is_agy = "antigravity" in str(path) or "brain" in str(path)
    if not is_agy:
        try:
            with open(path, "r", errors="ignore") as f:
                for line in f:
                    if line.strip():
                        entry = json.loads(line)
                        if entry.get("type") in ("USER_INPUT", "PLANNER_RESPONSE", "CONVERSATION_HISTORY") or "source" in entry:
                            is_agy = True
                        break
        except Exception:
            pass

    if is_agy:
        return parse_agy_transcript(path, session_id)
    else:
        return parse_claude_transcript(path, session_id)


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

    # ponytail: two attempts, no fallback. A silent "Exported conversation" placeholder
    # writes a mis-named file the operator has to fix by hand; failing here costs a re-run
    # of a command whose transcript is still on disk.
    for attempt in (1, 2):
        try:
            if model in ("claude-p", "claude-p-haiku"):
                # Use claude -p (subscription, no extra cost)
                result = subprocess.run(
                    ["claude", "-p", prompt],
                    input="",
                    capture_output=True,
                    text=True,
                    timeout=60
                )
            elif model.startswith("gemini") or model.startswith("agy://") or model.startswith("gemini://"):
                model_name = model
                if "://" in model:
                    model_name = model.split("://")[1]
                if model_name in ("gemini-3.7", "gemini"):
                    model_name = "gemini-3.7-flash-medium"
                elif model_name == "gemini-3.8":
                    model_name = "gemini-3.8-flash-medium"
                result = subprocess.run(
                    ["agy", "--model", model_name, "-p", prompt],
                    capture_output=True,
                    text=True,
                    timeout=60
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
                raise RuntimeError(f"exit {result.returncode}: {result.stderr.strip()[:300]}")

            output = result.stdout.strip()

            # Parse response
            summary = ""
            tags = []
            for line in output.split("\n"):
                line_clean = line.strip()
                line_clean = re.sub(r"^[\*\-\s]*", "", line_clean)
                if line_clean.upper().startswith("SUMMARY:"):
                    summary = re.sub(r"^SUMMARY:\s*", "", line_clean, flags=re.IGNORECASE).strip().strip('"*')
                elif line_clean.upper().startswith("TAGS:"):
                    tags_str = re.sub(r"^TAGS:\s*", "", line_clean, flags=re.IGNORECASE).strip().strip("[]")
                    tags = [t.strip().strip('"*\'') for t in tags_str.split(",") if t.strip()]

            if not summary or not tags:
                raise RuntimeError(f"no SUMMARY/TAGS lines in output: {output[:300]!r}")

            return summary, tags[:5]  # Enforce max 5 tags

        except Exception as e:
            print(f"Summary attempt {attempt}/2 failed via {model}: {e}", file=sys.stderr)

    print(
        f"Error: {model} produced no usable summary in 2 attempts. Nothing was written.\n"
        "Re-run the export, or pass --model to use a different summarizer.",
        file=sys.stderr,
    )
    sys.exit(1)


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
    the exporter either - this skill is itself synced across machines and tools.
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
        # `(?:\\?b)?` absorbs a regex-escape artifact on either side. A logged
        # `grep "\bTerm\b"` reaches a transcript as `\bTerm\b`, or as `bTerm`
        # once the backslashes are lost, and a bare `(?<!\w)` guard refuses the
        # second because `b` is a word character. Caught 2026-08-21 when the
        # export of a session that was fixing this leaked the term twice.
        # The outer boundaries still span the whole match, so `bTermless` is
        # left alone rather than mauled down to `Termless`.
        pattern = re.compile(
            r"(?<!\w)(?:\\?b)?" + re.escape(term) + r"(?:\\?b)?(?!\w)", re.IGNORECASE)
        text, n = pattern.subn("[REDACTED]", text)
        hits += n
    return text, hits


EXIT_NO_TRANSCRIPT = 3


def main():
    parser = argparse.ArgumentParser(description="Export Claude/Antigravity sessions to markdown")
    parser.add_argument("--session-id", required=True, help="Session ID to export")
    parser.add_argument("--transcript", default="", help="Optional explicit path to transcript file")
    parser.add_argument("--model", default="", help="Summarizer model (e.g. gemini-3.7, claude-p-haiku)")
    parser.add_argument("--output-dir", required=True, help="Output directory")
    parser.add_argument("--user-note", default="", help="Optional user note")
    parser.add_argument("--project-root", default="",
                        help="Project root recorded in frontmatter (defaults to output dir's parent)")
    parser.add_argument("--new", action="store_true",
                        help="Always write a new file, even if this session was exported before")

    args = parser.parse_args()

    try:
        # Get model
        model = get_model(cli_model=args.model)

        # Retrieve session context
        print(f"Retrieving session {args.session_id}...", file=sys.stderr)
        try:
            turns = get_session_turns(args.session_id, transcript_path=args.transcript)
        except FileNotFoundError as e:
            # Exit 3 = this harness left no transcript we can parse. The skill
            # skips the transcript step; the resume point already stands.
            print(f"Transcript skipped: {e}", file=sys.stderr)
            sys.exit(EXIT_NO_TRANSCRIPT)
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
                print(f"Redaction: no term list at {REDACT_FILE} - nothing scrubbed",
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
            print(f"Redaction: no term list at {REDACT_FILE} - nothing scrubbed",
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

    # A summarizer that cannot produce a summary must abort, never return a placeholder.
    try:
        generate_summary_and_tags("x" * 500, "no-such-model://boom")
        raise AssertionError("summarizer returned a fallback instead of exiting")
    except SystemExit as e:
        assert e.code == 1, e.code

    # Test Antigravity IDE transcript parsing
    import tempfile
    with tempfile.NamedTemporaryFile("w+", suffix=".jsonl") as tf:
        tf.write(
            json.dumps({"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "<USER_REQUEST>\nHow to test AGY?\n</USER_REQUEST>\n<ADDITIONAL_METADATA>\nsome metadata\n</ADDITIONAL_METADATA>"}) + "\n"
            + json.dumps({"type": "PLANNER_RESPONSE", "source": "MODEL", "content": "You test it like this."}) + "\n"
            + json.dumps({"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "/model haiku"}) + "\n"
            + json.dumps({"type": "PLANNER_RESPONSE", "source": "MODEL", "content": "Switched model."}) + "\n"
            + json.dumps({"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "Next real question"}) + "\n"
            + json.dumps({"type": "PLANNER_RESPONSE", "source": "MODEL", "content": "Next real answer"}) + "\n"
        )
        tf.flush()
        agy_turns = parse_agy_transcript(Path(tf.name), "test-session")
        assert len(agy_turns) == 4, f"Expected 4 turns, got {len(agy_turns)}"
        assert agy_turns[0] == "**User:**\n\nHow to test AGY?\n", agy_turns[0]
        assert agy_turns[1] == "**Assistant:**\n\nYou test it like this.\n", agy_turns[1]
        assert agy_turns[2] == "**User:**\n\nNext real question\n", agy_turns[2]
        assert agy_turns[3] == "**Assistant:**\n\nNext real answer\n", agy_turns[3]

    # A harness with no parseable transcript exits 3 so the skill skips, not fails.
    import tempfile
    r = subprocess.run([sys.executable, __file__, "--session-id", "no-such-session",
                        "--output-dir", tempfile.mkdtemp()], capture_output=True)
    assert r.returncode == EXIT_NO_TRANSCRIPT, r.stderr

    print("selftest ok")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        main()
