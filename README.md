# claude-work-log

A Claude Code plugin that logs all prompts and responses to a searchable SQLite database, tagged by repository and GitHub issue.

## Features

- **Automatic logging** — Every prompt and response is captured via `UserPromptSubmit` and `Stop` hooks
- **GitHub issue integration** — Automatically detects the active issue from the [github-issue-tracker](https://github.com/hserkanyilmaz/github-issue-tracker) plugin
- **Repository detection** — Identifies the current repo from git remote origin
- **SQLite storage** — Fast, local, searchable database at `~/.claude/work-log/work-log.db`
- **Slash commands** — Search your work history without leaving Claude Code

## Installation

Install as a Claude Code plugin:

```bash
claude install-plugin github:hserkanyilmaz/claude-work-log
```

Or add to your `~/.claude/settings.json`:

```json
{
  "enabledPlugins": {
    "claude-work-log@claude-work-log": true
  },
  "extraKnownMarketplaces": {
    "claude-work-log": {
      "source": {
        "source": "github",
        "repo": "hserkanyilmaz/claude-work-log"
      }
    }
  }
}
```

## Usage

### Slash Commands

| Command | Description |
|---|---|
| `/work-log stats` | Summary statistics |
| `/work-log recent 10` | Last 10 entries |
| `/work-log issue owner/repo#123` | Entries for a specific issue |
| `/work-log repo owner/repo` | Entries for a repository |
| `/work-log search cassandra` | Full-text search |
| `/work-log sessions` | List all sessions |
| `/work-log session abc123` | Entries for a specific session |
| `/work-log export` | Export all entries as JSON |

### CLI

You can also run the search script directly:

```bash
python3 ~/.claude/plugins/cache/claude-work-log/claude-work-log/1.0.0/scripts/search.py stats
```

## How It Works

1. On every `UserPromptSubmit` event, the hook captures the user's prompt along with:
   - Session ID
   - Current working directory
   - Repository (from `git remote get-url origin`)
   - Active GitHub issue (from `.claude/github-issue.local.md`, set by github-issue-tracker)

2. On every `Stop` event, the hook captures the assistant's response.

3. All entries are stored in `~/.claude/work-log/work-log.db` (SQLite).

## Companion Plugin

Works best with [github-issue-tracker](https://github.com/hserkanyilmaz/github-issue-tracker) for automatic issue detection.

## License

MIT
