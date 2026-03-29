---
allowed-tools: Bash, Read
description: Search and display work log entries (prompts/responses tracked by repo and issue)
---

Search the Claude Code work log database. The work log captures all prompts and responses, tagged with the active GitHub issue and repository.

The user's query is: $ARGUMENTS

Run the search script based on the user's request:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/search.py <command> [args]
```

Available commands:
- `recent [N]` — Show N most recent entries (default 20)
- `issue OWNER/REPO#NUM` or `issue #NUM` — Show entries for a specific GitHub issue
- `repo OWNER/REPO` — Show entries for a repository
- `session SESSION_ID` — Show entries for a specific session
- `search QUERY` — Full-text search across all prompts and responses
- `stats` — Show summary statistics (total entries, top repos, top issues)
- `sessions [OWNER/REPO]` — List sessions, optionally filtered by repo
- `export` — Export all entries as JSON

If the user didn't specify a command, show `stats` first, then ask what they'd like to search for.

Display the results clearly. For large result sets, summarize the key findings.
