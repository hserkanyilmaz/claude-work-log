#!/usr/bin/env python3
"""Claude Code hook: logs prompts and responses to SQLite for work history tracking.

Handles both UserPromptSubmit and Stop events.
Reads active GitHub issue from .claude/github-issue.local.md in the cwd
(compatible with the github-issue-tracker plugin).
Detects repo from git remote origin.
"""

import json
import os
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path.home() / ".claude" / "work-log" / "work-log.db"


def init_db():
    """Create the database and tables if they don't exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            event_type TEXT NOT NULL,
            repo TEXT,
            issue_number TEXT,
            issue_title TEXT,
            cwd TEXT,
            content TEXT,
            content_length INTEGER DEFAULT 0
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_session ON entries(session_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_repo ON entries(repo)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_issue ON entries(repo, issue_number)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON entries(timestamp)")
    conn.commit()
    return conn


def get_repo_from_cwd(cwd):
    """Detect the GitHub repo (owner/name) from git remote origin in the given cwd."""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=5, cwd=cwd
        )
        if result.returncode == 0:
            url = result.stdout.strip()
            m = re.search(r"github\.com[:/]([^/]+/[^/]+?)(?:\.git)?$", url)
            if m:
                return m.group(1)
    except Exception:
        pass
    return None


def get_active_issue(cwd):
    """Read active GitHub issue from .claude/github-issue.local.md in the cwd."""
    state_file = Path(cwd) / ".claude" / "github-issue.local.md"
    if not state_file.exists():
        return None, None, None
    try:
        content = state_file.read_text()
        number = None
        title = None
        repo = None
        for line in content.splitlines():
            if line.startswith("number: "):
                number = line[len("number: "):].strip()
            elif line.startswith("title: "):
                title = line[len("title: "):].strip()
            elif line.startswith("repo: "):
                repo = line[len("repo: "):].strip()
        return number, title, repo
    except Exception:
        return None, None, None


def truncate_content(text, max_chars=5000):
    """Truncate content to a reasonable size for storage."""
    if not text:
        return text
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n... [truncated, {len(text)} chars total]"


def handle_user_prompt_submit(data):
    """Log a user prompt."""
    session_id = data.get("session_id", "unknown")
    cwd = data.get("cwd", os.getcwd())
    prompt = data.get("user_prompt", "")

    if not prompt or not prompt.strip():
        return

    # Skip slash commands that are just navigation/control
    stripped = prompt.strip()
    if stripped in ("/clear", "/help", "/exit", "/quit"):
        return

    repo = get_repo_from_cwd(cwd)
    issue_number, issue_title, issue_repo = get_active_issue(cwd)

    # Prefer repo from active issue if available
    if issue_repo:
        repo = issue_repo

    conn = init_db()
    try:
        conn.execute(
            """INSERT INTO entries
               (session_id, timestamp, event_type, repo, issue_number, issue_title, cwd, content, content_length)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                session_id,
                datetime.now(timezone.utc).isoformat(),
                "prompt",
                repo,
                issue_number,
                issue_title,
                cwd,
                truncate_content(prompt),
                len(prompt),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def handle_stop(data):
    """Log that a response was completed. Capture response summary from stdin data."""
    session_id = data.get("session_id", "unknown")
    cwd = data.get("cwd", os.getcwd())

    # The Stop event may contain stop_response or assistant_response
    response = data.get("stop_response", data.get("assistant_response", ""))

    # If no direct response content, try to get a summary from transcript
    if not response:
        transcript_path = data.get("transcript_path", "")
        if transcript_path and os.path.exists(transcript_path):
            try:
                with open(transcript_path, "r") as f:
                    lines = f.readlines()
                # Find the last assistant message
                for line in reversed(lines):
                    try:
                        msg = json.loads(line.strip())
                        if msg.get("role") == "assistant":
                            content_parts = msg.get("content", [])
                            texts = []
                            for part in content_parts:
                                if isinstance(part, dict) and part.get("type") == "text":
                                    texts.append(part["text"])
                                elif isinstance(part, str):
                                    texts.append(part)
                            if texts:
                                response = "\n".join(texts)
                            break
                    except (json.JSONDecodeError, KeyError):
                        continue
            except Exception:
                pass

    repo = get_repo_from_cwd(cwd)
    issue_number, issue_title, issue_repo = get_active_issue(cwd)
    if issue_repo:
        repo = issue_repo

    conn = init_db()
    try:
        conn.execute(
            """INSERT INTO entries
               (session_id, timestamp, event_type, repo, issue_number, issue_title, cwd, content, content_length)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                session_id,
                datetime.now(timezone.utc).isoformat(),
                "response",
                repo,
                issue_number,
                issue_title,
                cwd,
                truncate_content(response) if response else "[response completed]",
                len(response) if response else 0,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def main():
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, IOError):
        data = {}

    event = data.get("hook_event_name", os.environ.get("CLAUDE_HOOK_EVENT", ""))

    if event == "UserPromptSubmit":
        handle_user_prompt_submit(data)
    elif event == "Stop":
        handle_stop(data)

    # Always allow the action to continue
    print(json.dumps({"continue": True}))


if __name__ == "__main__":
    main()
