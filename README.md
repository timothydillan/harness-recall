# harness-recall

Universal CLI for exporting and searching AI coding sessions from Codex and Claude Code.

![PyPI](https://img.shields.io/pypi/v/harness-recall) ![Python](https://img.shields.io/pypi/pyversions/harness-recall) ![License](https://img.shields.io/badge/license-MIT-blue)

---

## What it does

harness-recall (`hrc`) parses local JSONL session files from AI coding tools, normalizes them into a common format, and indexes them with SQLite + FTS5 full-text search. You can list recent sessions, search across all of them, view sessions in the terminal, and export to Markdown, HTML, or JSON.

Codex and Claude Code are supported in v1. The parser interface is designed to be extended — adding Cursor, Copilot, or Aider support means writing one new file.

## Installation

```bash
pip install harness-recall
```

```bash
pipx install harness-recall
```

## Quick Start

```bash
# List recent sessions (auto-indexes on first run)
$ hrc list
  ID        Source       Date        Project                Title
  019cbc4c  codex        2026-04-06  ~/GitHub/myapp         fix auth middleware redirect loop
  018fa31d  claude-code  2026-04-05  ~/GitHub/myapp         add docker-compose health checks
  018e119a  codex        2026-04-04  ~/GitHub/api-service   refactor token validation logic

# Search across all sessions
$ hrc search "auth middleware"
  019cbc4c  codex  2026-04-06  fix auth middleware redirect loop
  018c774e  codex  2026-03-28  debug auth middleware CORS issue

# View a session in the terminal
$ hrc show 019cbc4c

# Export to HTML
$ hrc export 019cbc4c --format html -o ./exports/
Exported: ./exports/019cbc4c-fix-auth-middleware.html
```

## Supported Sources

| Source      | Session Location                                    | Status   |
|-------------|-----------------------------------------------------|----------|
| Codex       | `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl`     | Supported |
| Claude Code | `~/.claude/projects/{project-slug}/{session}.jsonl` | Supported |
| Cursor      | `~/Library/Application Support/Cursor/User/globalStorage/state.vscdb` | Supported |
| Copilot     | —                                                   | Planned  |

## Commands

### `hrc list`

List sessions, most recent first.

```bash
hrc list                          # default 25 sessions
hrc list --source codex           # filter by source
hrc list --after 2026-03-01       # filter by date
hrc list --project ~/GitHub/myapp # filter by project directory
hrc list --limit 50               # show more results
```

### `hrc search`

Full-text search across all session content using SQLite FTS5.

```bash
hrc search "docker compose"
hrc search "auth middleware" --source codex
hrc search "fix" --tool exec_command   # sessions using a specific tool
```

### `hrc show`

Pretty-print a session in the terminal using `rich`.

```bash
hrc show 019cbc4c          # show session (tool call details collapsed)
hrc show 019cbc4c --full   # include full tool call arguments and outputs
hrc show 019cbc4c --turns 1-5  # show specific turns only
```

Session IDs can be abbreviated — `hrc show 019cbc` resolves by prefix match.

### `hrc export`

Export one or more sessions to a file.

```bash
hrc export 019cbc4c                    # Markdown (default)
hrc export 019cbc4c --format html      # styled HTML
hrc export 019cbc4c --format json      # normalized IR as JSON
hrc export 019cbc4c -o ./exports/      # specify output directory
hrc export --all --format md           # bulk export all sessions
hrc export --source codex -o ./        # export all Codex sessions
```

### `hrc index`

Manage the SQLite index. Index updates run automatically on other commands, but you can trigger them manually.

```bash
hrc index             # index new and changed sessions only
hrc index --rebuild   # full re-index from scratch
hrc index --stats     # show index statistics
```

### `hrc config`

Show or edit configuration.

```bash
hrc config
```

## Export Formats

**Markdown** — default format. Clean transcript with session metadata header, role labels, and fenced code blocks. Renders on GitHub and is pasteable into any document.

**HTML** — self-contained single file. Warm, minimal design with collapsible tool calls (`<details>/<summary>`), syntax-highlighted code, and automatic dark mode via `prefers-color-scheme`. Optionally loads `Space Grotesk` and `JetBrains Mono` from CDN; system font fallbacks work offline. No JavaScript frameworks.

**JSON** — the normalized intermediate representation (IR). Useful for scripting or piping into other tools.

## How it Works

```
Parsers (Codex, Claude Code, ...)
    |
    v
Intermediate Representation (IR)
    |
    v
SQLite + FTS5 Index (~/.harness-recall/index.db)
    |
    v
Renderers (Markdown, HTML, JSON)
```

Each parser reads raw JSONL from its source and emits IR objects (`Session`, `Turn`, `ToolCall`). Renderers and the search index only ever see IR — never raw source data. The index is built automatically on first use and updated incrementally using file modification times.

## Adding a Parser

Implement `BaseParser` in a new file under `src/harness_recall/parsers/` and register it in `__init__.py`.

```python
from harness_recall.parsers.base import BaseParser
from harness_recall.ir import Session
from pathlib import Path

class MyCLIParser(BaseParser):
    name = "mycli"
    default_paths = ["~/.mycli/sessions/"]
    file_pattern = "**/*.jsonl"

    def parse(self, file_path: Path) -> Session:
        # Read file_path, return a Session IR object
        ...
```

The `discover()` method is provided by `BaseParser` — it globs `default_paths` with `file_pattern`. Override it if the source uses a non-standard layout.

Parser contributions are welcome. See `docs/adding-a-parser.md` for a full walkthrough.

## Configuration

harness-recall auto-detects `~/.codex/sessions/` and `~/.claude/projects/` on first run. Override paths or add custom sources in `~/.harness-recall/config.toml`:

```toml
[sources]
codex = ["/custom/codex/path"]
claude-code = ["/custom/claude/path"]

[index]
db_path = "/custom/index.db"
```

## Contributing

Pull requests are welcome. Parser contributions are the easiest entry point — if you use an AI coding tool that isn't supported, adding a parser is a well-defined, isolated task.

Please open an issue before starting significant work to confirm the approach.

## License

MIT
