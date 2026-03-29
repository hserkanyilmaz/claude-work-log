#!/usr/bin/env python3
"""Search and display Claude Code work log entries.

Usage:
    search.py recent [N]              -- Show N most recent entries (default 20)
    search.py issue OWNER/REPO#NUM    -- Show entries for a specific issue
    search.py repo OWNER/REPO         -- Show entries for a repository
    search.py session SESSION_ID      -- Show entries for a session
    search.py search QUERY            -- Full-text search in prompts/responses
    search.py stats                   -- Show summary statistics
    search.py sessions [OWNER/REPO]   -- List sessions, optionally filtered by repo
    search.py export                  -- Export all entries as JSON
"""

import json
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path.home() / ".claude" / "work-log" / "work-log.db"


def get_conn():
    if not DB_PATH.exists():
        print("No work log database found. Start a session to begin logging.")
        sys.exit(1)
    return sqlite3.connect(str(DB_PATH))


def format_entry(row):
    """Format a single entry for display."""
    id_, session_id, timestamp, event_type, repo, issue_num, issue_title, cwd, content, content_len = row
    ts = timestamp[:19].replace("T", " ")
    icon = ">" if event_type == "prompt" else "<"
    issue = f" #{issue_num}" if issue_num else ""
    repo_str = repo or "no-repo"
    display_content = content or ""
    if len(display_content) > 200:
        display_content = display_content[:200] + "..."
    return f"[{ts}] {icon} {repo_str}{issue} | {event_type} ({content_len} chars)\n  {display_content}\n"


def cmd_recent(n=20):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM entries ORDER BY timestamp DESC LIMIT ?", (n,)
    ).fetchall()
    conn.close()
    if not rows:
        print("No entries found.")
        return
    print(f"=== {len(rows)} most recent entries ===\n")
    for row in reversed(rows):
        print(format_entry(row))


def cmd_issue(issue_ref):
    """Search by issue. Accepts: owner/repo#123, #123, or just 123."""
    repo = None
    number = None
    if "#" in issue_ref:
        parts = issue_ref.split("#")
        if parts[0]:
            repo = parts[0]
        number = parts[1]
    else:
        number = issue_ref

    conn = get_conn()
    if repo:
        rows = conn.execute(
            "SELECT * FROM entries WHERE issue_number = ? AND repo = ? ORDER BY timestamp",
            (number, repo),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM entries WHERE issue_number = ? ORDER BY timestamp",
            (number,),
        ).fetchall()
    conn.close()

    if not rows:
        print(f"No entries found for issue {issue_ref}")
        return
    print(f"=== {len(rows)} entries for issue {issue_ref} ===\n")
    for row in rows:
        print(format_entry(row))


def cmd_repo(repo):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM entries WHERE repo = ? ORDER BY timestamp", (repo,)
    ).fetchall()
    conn.close()
    if not rows:
        print(f"No entries found for repo {repo}")
        return
    print(f"=== {len(rows)} entries for {repo} ===\n")
    for row in rows:
        print(format_entry(row))


def cmd_session(session_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM entries WHERE session_id LIKE ? ORDER BY timestamp",
        (f"%{session_id}%",),
    ).fetchall()
    conn.close()
    if not rows:
        print(f"No entries found for session {session_id}")
        return
    print(f"=== {len(rows)} entries in session ===\n")
    for row in rows:
        print(format_entry(row))


def cmd_search(query):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM entries WHERE content LIKE ? ORDER BY timestamp DESC LIMIT 50",
        (f"%{query}%",),
    ).fetchall()
    conn.close()
    if not rows:
        print(f"No entries matching '{query}'")
        return
    print(f"=== {len(rows)} entries matching '{query}' ===\n")
    for row in rows:
        print(format_entry(row))


def cmd_stats():
    conn = get_conn()
    total = conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
    prompts = conn.execute("SELECT COUNT(*) FROM entries WHERE event_type='prompt'").fetchone()[0]
    responses = conn.execute("SELECT COUNT(*) FROM entries WHERE event_type='response'").fetchone()[0]
    sessions = conn.execute("SELECT COUNT(DISTINCT session_id) FROM entries").fetchone()[0]
    repos = conn.execute(
        "SELECT repo, COUNT(*) as cnt FROM entries WHERE repo IS NOT NULL GROUP BY repo ORDER BY cnt DESC LIMIT 10"
    ).fetchall()
    issues = conn.execute(
        "SELECT repo, issue_number, issue_title, COUNT(*) as cnt FROM entries WHERE issue_number IS NOT NULL GROUP BY repo, issue_number ORDER BY cnt DESC LIMIT 10"
    ).fetchall()
    first = conn.execute("SELECT MIN(timestamp) FROM entries").fetchone()[0]
    last = conn.execute("SELECT MAX(timestamp) FROM entries").fetchone()[0]
    conn.close()

    print("=== Work Log Statistics ===\n")
    print(f"Total entries:    {total}")
    print(f"  Prompts:        {prompts}")
    print(f"  Responses:      {responses}")
    print(f"Sessions:         {sessions}")
    if first:
        print(f"First entry:      {first[:19]}")
        print(f"Last entry:       {last[:19]}")

    if repos:
        print(f"\nTop repositories:")
        for repo, cnt in repos:
            print(f"  {repo}: {cnt} entries")

    if issues:
        print(f"\nTop issues:")
        for repo, num, title, cnt in issues:
            title_short = (title[:50] + "...") if title and len(title) > 50 else (title or "")
            print(f"  {repo}#{num} ({title_short}): {cnt} entries")


def cmd_sessions(repo=None):
    conn = get_conn()
    if repo:
        rows = conn.execute("""
            SELECT session_id, MIN(timestamp) as first, MAX(timestamp) as last,
                   COUNT(*) as cnt, repo, issue_number, issue_title
            FROM entries WHERE repo = ?
            GROUP BY session_id ORDER BY first DESC LIMIT 30
        """, (repo,)).fetchall()
    else:
        rows = conn.execute("""
            SELECT session_id, MIN(timestamp) as first, MAX(timestamp) as last,
                   COUNT(*) as cnt, repo, issue_number, issue_title
            FROM entries
            GROUP BY session_id ORDER BY first DESC LIMIT 30
        """).fetchall()
    conn.close()

    if not rows:
        print("No sessions found.")
        return
    print(f"=== {len(rows)} sessions ===\n")
    for sid, first, last, cnt, repo, issue_num, issue_title in rows:
        ts = first[:19].replace("T", " ")
        issue = f" #{issue_num}" if issue_num else ""
        repo_str = repo or "no-repo"
        short_sid = sid[:12] if sid else "?"
        print(f"  {ts} | {short_sid}... | {repo_str}{issue} | {cnt} entries")


def cmd_export():
    """Export all entries as JSON."""
    conn = get_conn()
    rows = conn.execute("SELECT * FROM entries ORDER BY timestamp").fetchall()
    conn.close()
    columns = ["id", "session_id", "timestamp", "event_type", "repo",
               "issue_number", "issue_title", "cwd", "content", "content_length"]
    entries = [dict(zip(columns, row)) for row in rows]
    print(json.dumps(entries, indent=2))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    cmd = sys.argv[1].lower()

    if cmd == "recent":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 20
        cmd_recent(n)
    elif cmd == "issue":
        if len(sys.argv) < 3:
            print("Usage: search.py issue OWNER/REPO#NUM")
            sys.exit(1)
        cmd_issue(sys.argv[2])
    elif cmd == "repo":
        if len(sys.argv) < 3:
            print("Usage: search.py repo OWNER/REPO")
            sys.exit(1)
        cmd_repo(sys.argv[2])
    elif cmd == "session":
        if len(sys.argv) < 3:
            print("Usage: search.py session SESSION_ID")
            sys.exit(1)
        cmd_session(sys.argv[2])
    elif cmd == "search":
        if len(sys.argv) < 3:
            print("Usage: search.py search QUERY")
            sys.exit(1)
        cmd_search(" ".join(sys.argv[2:]))
    elif cmd == "stats":
        cmd_stats()
    elif cmd == "sessions":
        repo = sys.argv[2] if len(sys.argv) > 2 else None
        cmd_sessions(repo)
    elif cmd == "export":
        cmd_export()
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
