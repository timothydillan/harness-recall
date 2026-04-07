# harness-recall Design Spec

**Date:** 2026-04-07
**Status:** Approved
**CLI command:** `hrc`
**Package name:** `harness-recall`

## Problem

AI coding assistants (Codex, Claude Code, Cursor, Copilot) store conversation sessions locally in proprietary, undocumented formats. Developers lose valuable knowledge — the reasoning behind code changes, debugging approaches, architectural decisions — because there's no good way to search, export, or share these sessions.

The existing landscape is fragmented:
- **ZeroSumQuant/claude-conversation-extractor** (465 stars) covers Claude Code only, appears stale (~7 months no commits), has known security and performance issues
- **Codex CLI** has almost zero export tooling despite massive demand (issue #2880 on the 73k-star repo)
- **SpecStory** (1.2k stars) is multi-tool but has a commercial cloud layer and is VS Code extension-focused
- No clean, standalone, open-source CLI exists that reads from multiple local data stores

## Solution

A universal, open-source Python CLI tool that:
1. Parses session data from multiple AI coding harnesses (Codex + Claude Code for v1)
2. Normalizes into a common intermediate representation (IR)
3. Indexes into SQLite with FTS5 full-text search
4. Exports to Markdown, HTML, and JSON

## Target Users

- Developers using Codex and/or Claude Code who want to find past sessions
- Vibe coders / non-developers who want to share AI coding sessions
- Teams who want to document AI-assisted development decisions

## Priorities

1. **Archival & Search** — find that session where you solved X three weeks ago
2. **Sharing & Showcase** — export as clean, readable Markdown/HTML to share on GitHub, blogs, or with colleagues
3. **Analytics & Insights** — (v2) understand usage patterns, token burn, costs

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     harness-recall                       │
│                                                         │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐           │
│  │  Codex   │   │  Claude  │   │  Future  │  Parsers   │
│  │  Parser  │   │  Code    │   │  (Cursor │  (one per  │
│  │          │   │  Parser  │   │  etc.)   │  source)   │
│  └────┬─────┘   └────┬─────┘   └────┬─────┘           │
│       │              │              │                   │
│       ▼              ▼              ▼                   │
│  ┌─────────────────────────────────────────┐           │
│  │     Intermediate Representation (IR)     │           │
│  └─────────────────────┬───────────────────┘           │
│                        │                               │
│                        ▼                               │
│  ┌─────────────────────────────────────────┐           │
│  │          SQLite + FTS5 Index             │           │
│  └─────────────────────┬───────────────────┘           │
│                        │                               │
│                        ▼                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐            │
│  │ Markdown │  │   HTML   │  │   JSON   │  Renderers  │
│  │ Renderer │  │ Renderer │  │ Renderer │             │
│  └──────────┘  └──────────┘  └──────────┘             │
└─────────────────────────────────────────────────────────┘
```

### Key Principles

- **Parsers are isolated** — each source has its own parser that reads raw JSONL and emits IR objects. Adding a new source = adding one file.
- **IR is the contract** — renderers and the index only ever see IR, never raw source data.
- **SQLite is the query layer** — FTS5 for full-text search, standard SQL for filtering. Auto-built and auto-updated via file mtime checks.
- **Renderers are isolated** — each output format has its own renderer targeting the IR.

---

## Source Data Formats

### Codex

- **Location:** `~/.codex/sessions/YYYY/MM/DD/rollout-{timestamp}-{UUID}.jsonl`
- **Format:** JSONL, one JSON object per line
- **Top-level types:** `session_meta`, `response_item`, `event_msg`, `turn_context`, `compacted`
- **response_item subtypes:** `message` (roles: user/assistant/developer), `function_call`, `function_call_output`, `reasoning` (encrypted), `web_search_call`, `custom_tool_call`, `custom_tool_call_output`
- **event_msg subtypes:** `token_count`, `agent_message`, `task_started`, `user_message`, `task_complete`, `agent_reasoning`, `context_compacted`, `turn_aborted`, `thread_rolled_back`
- **Key metadata:** session ID, cwd, originator (Desktop/CLI), cli_version, model_provider, git state (branch, commit, repo URL), subagent relationships (forked_from_id, agent_nickname, agent_role)
- **Notable:** Reasoning content is encrypted (`encrypted_content` field) — stored as null in IR. Token usage tracked per turn (input, cached, output, reasoning tokens).

### Claude Code

- **Location:** `~/.claude/projects/{project-slug}/{session-id}.jsonl` with `subagents/` subdirectory
- **Format:** JSONL, one JSON object per line
- **Top-level types:** `assistant`, `user`, `system`, `progress`, `queue-operation`, `file-history-snapshot`, `last-prompt`
- **Message structure:** Flat types with nested content blocks. Tool calls embedded as `tool_use` content blocks in assistant messages. Thinking blocks readable (not encrypted).
- **Organization:** By project (not by date). 4,565+ files including subagents across projects.

---

## Intermediate Representation (IR)

```python
@dataclass
class Session:
    id: str                        # unique, derived from source
    source: str                    # "codex" | "claude-code"
    source_file: str               # path to original JSONL
    source_file_mtime: float       # for incremental re-indexing
    started_at: datetime           # session start timestamp
    ended_at: datetime | None      # session end (last event)
    project_dir: str | None        # cwd / project directory
    model: str | None              # "gpt-5.3-codex", "claude-opus-4-6", etc.
    model_provider: str | None     # "openai", "anthropic"
    cli_version: str | None
    git_branch: str | None
    git_commit: str | None
    git_repo_url: str | None
    title: str | None              # auto-generated from first user message (~80 chars)
    parent_session_id: str | None  # for subagent sessions
    agent_name: str | None         # "Euclid", "Leibniz", etc.
    agent_role: str | None         # "explorer", etc.
    turns: list[Turn]

@dataclass
class Turn:
    id: str                        # "{session_id}:{sequence_num}"
    role: str                      # "user" | "assistant" | "system"
    content: str                   # plain text / markdown
    timestamp: datetime
    reasoning: str | None          # thinking (Claude Code only; null for Codex)
    tool_calls: list[ToolCall]
    token_usage: TokenUsage | None

@dataclass
class ToolCall:
    id: str                        # call_id for correlation
    name: str                      # "exec_command", "Read", "Edit", etc.
    arguments: str                 # JSON string of args
    output: str | None             # tool result (first 10KB in DB; full via source file)

@dataclass
class TokenUsage:
    input_tokens: int
    output_tokens: int
    cached_tokens: int | None
    reasoning_tokens: int | None
```

### Design Decisions

- **`title` auto-generated** from first user message, truncated to ~80 chars. Fallback: `"{source} session {YYYY-MM-DD HH:MM}"` if no user message exists.
- **`reasoning` is nullable** — Codex encrypts it (null), Claude Code exposes it (stored)
- **`tool_calls` nested under turns** — matches how both sources structure them
- **`source_file_mtime`** enables incremental indexing
- **Large tool outputs** — first 10KB in DB, full content via re-reading source file on demand
- **Subagents are separate sessions** with `parent_session_id` — keeps the tree navigable

---

## SQLite Schema

```sql
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    source_file TEXT NOT NULL,
    source_file_mtime REAL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    project_dir TEXT,
    model TEXT,
    model_provider TEXT,
    cli_version TEXT,
    git_branch TEXT,
    git_commit TEXT,
    git_repo_url TEXT,
    title TEXT,
    parent_session_id TEXT,
    agent_name TEXT,
    agent_role TEXT,
    total_input_tokens INTEGER,
    total_output_tokens INTEGER
);

CREATE TABLE turns (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    sequence_num INTEGER NOT NULL,
    role TEXT NOT NULL,
    content TEXT,
    timestamp TEXT,
    reasoning TEXT,
    input_tokens INTEGER,
    output_tokens INTEGER,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE TABLE tool_calls (
    id TEXT PRIMARY KEY,
    turn_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    name TEXT NOT NULL,
    arguments TEXT,
    output TEXT,
    FOREIGN KEY (turn_id) REFERENCES turns(id),
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

-- Full-text search
CREATE VIRTUAL TABLE turns_fts USING fts5(
    content,
    content='turns',
    content_rowid='rowid',
    tokenize='porter unicode61'
);

-- Indexes
CREATE INDEX idx_sessions_started_at ON sessions(started_at);
CREATE INDEX idx_sessions_source ON sessions(source);
CREATE INDEX idx_sessions_project_dir ON sessions(project_dir);
CREATE INDEX idx_turns_session_id ON turns(session_id);
CREATE INDEX idx_tool_calls_session_id ON tool_calls(session_id);
CREATE INDEX idx_tool_calls_name ON tool_calls(name);
```

### Indexing Strategy

1. **First run** — auto-detects unindexed sessions, builds full index (~2-3s for 537MB). Shows progress bar.
2. **Subsequent runs** — scans source directories, compares file mtimes, re-indexes only new/changed files (~50ms).
3. **Manual rebuild** — `hrc index --rebuild` for full re-index.
4. **DB location** — `~/.harness-recall/index.db`

---

## CLI Commands

```bash
# Discovery
hrc list                           # List all sessions (recent first, default 25)
hrc list --source codex            # Filter by source
hrc list --after 2026-03-01        # Filter by date
hrc list --project ~/GitHub/MyCH   # Filter by project dir
hrc list --limit 20                # Limit results

# Search
hrc search "auth middleware"                    # Full-text search
hrc search "docker compose" --source codex      # Scoped to source
hrc search "fix" --tool exec_command            # Sessions using specific tool

# View
hrc show 019cbc4c                  # Pretty-print session in terminal
hrc show 019cbc4c --full           # Include tool calls and outputs
hrc show 019cbc4c --turns 1-5      # Show specific turns only

# Export
hrc export 019cbc4c                # Export to Markdown (default)
hrc export 019cbc4c --format html  # Export to styled HTML
hrc export 019cbc4c --format json  # Export normalized IR as JSON
hrc export 019cbc4c -o ./exports/  # Output directory
hrc export --all --format md       # Bulk export all sessions
hrc export --source codex -o ./    # Export all Codex sessions

# Index Management
hrc index                          # Index new/changed sessions
hrc index --rebuild                # Full re-index
hrc index --stats                  # Show index stats

# Configuration
hrc config                         # Show/edit config
hrc --version
hrc --help
```

### UX Decisions

- **Auto-index on first command** — `hrc list` triggers indexing if needed. No separate setup step.
- **Short IDs** — display first 8 chars of UUID. Prefix matching for disambiguation.
- **`show` vs `export`** — `show` is terminal viewing (colorized, truncated). `export` writes complete files.
- **Default format is Markdown** — renders on GitHub, pasteable.
- **`--full` flag** — `hrc show` hides tool call details by default. `--full` shows everything. Exports always include full content.
- **Config auto-detects paths** — checks `~/.codex/sessions/` and `~/.claude/projects/` on first run. Override via `~/.harness-recall/config.toml`.

### Terminal Display (rich)

Polished output using `rich` library:
- Colored role labels with clear visual hierarchy
- Boxed session metadata headers
- Tool calls in bordered panels, collapsed-style with summary line
- Syntax-highlighted code blocks
- Progress bars for indexing
- Tables for `hrc list` output

---

## HTML Export Design

### Visual Thesis

"This should feel like reading a beautifully typeset technical transcript — warm, precise, with the quiet confidence of a Stripe docs page or a Linear changelog."

**Memorable element:** The conversation reads like an edited dialogue between peers, not a raw terminal dump. Tool calls feel like margin annotations you can peek into.

### Technical Approach

- Self-contained single HTML file (CSS embedded, fully functional offline; optional Google Fonts CDN for `Space Grotesk` and `JetBrains Mono` with system font fallbacks)
- Jinja2 template with vanilla CSS + ~15 lines of vanilla JS (theme toggle only)
- `<details><summary>` for collapsible tool calls — zero JS needed for core interaction
- CSS-only syntax highlighting via class-based tokens generated at export time

### Typography

- Session title: `Space Grotesk` or `Plus Jakarta Sans` (one CDN load, distinctive)
- Body: System font stack (`-apple-system, BlinkMacSystemFont, 'Segoe UI'...`) — zero FOUT
- Code: `JetBrains Mono` via CDN with system mono fallback
- Line length: `max-width: 65ch` for body text

### Color System

**Light mode:**
- Background: `#fafaf9` (warm stone)
- Surface: `#ffffff` with `1px solid #e7e5e4`
- Text primary: `#1c1917` (stone-900, no pure black)
- Text secondary: `#78716c` (stone-500)
- Accent: `#0d9488` (teal-600) — single accent for links and role indicators
- User turns: left-aligned, no background
- Assistant turns: subtle `#f5f5f4` background band (stone-100), full-width
- Tool calls: `#fafaf9` with left `2px solid #d6d3d1` border

**Dark mode:**
- Layered surfaces: `#0c0a09` → `#1c1917` → `#292524` → `#44403c` (stone scale)
- Text: `#e7e5e4` primary, `#a8a29e` secondary
- Accent: `#2dd4bf` (teal-400, same hue, lighter)
- `prefers-color-scheme: dark` as base, manual toggle via `localStorage`

### Layout

- Max width `720px` centered — reading column
- Session metadata: left-aligned, quiet metadata line (not boxed)
- Turns: vertical flow with `32px` gaps
- Role labels: small caps, muted, above content — not colored badges
- No avatars, no chat bubbles — this is a transcript

### Tool Calls

- Collapsed by default: `> exec_command: git fetch origin pull/49/head`
- Expand to show arguments and output in contained block
- `<details><summary>` — native HTML, no JS
- Code output: scrollable `<pre>` with `max-height: 300px`

### Micro-Details

- `::selection` styled to teal accent at 20% opacity
- Custom scrollbars on code blocks and tool output (thin, rounded, stone-300)
- `::focus-visible` on theme toggle
- No `#000000` — all darks are warm stone scale
- `<hr>` as hairline stone-200 with 24px vertical margin
- Print: hide theme toggle, force light mode, full-width reflow

### What It Explicitly Won't Have

- No chat bubbles with rounded corners and colored backgrounds
- No avatars or profile images
- No purple/blue AI gradients
- No "Powered by AI" badges
- No external image loading
- Font CDNs are optional — system fallbacks ensure full functionality offline
- No JavaScript frameworks

---

## Project Structure

```
harness-recall/
├── pyproject.toml
├── README.md
├── LICENSE                     # MIT
├── src/
│   └── harness_recall/
│       ├── __init__.py
│       ├── cli.py              # Click CLI entry point
│       ├── config.py           # Config loading (~/.harness-recall/config.toml)
│       ├── index.py            # SQLite index management, FTS5
│       ├── ir.py               # IR dataclasses
│       ├── parsers/
│       │   ├── __init__.py     # Parser registry (auto-discovers parsers)
│       │   ├── base.py         # Abstract base parser interface
│       │   ├── codex.py        # Codex JSONL parser
│       │   └── claude_code.py  # Claude Code JSONL parser
│       ├── renderers/
│       │   ├── __init__.py     # Renderer registry
│       │   ├── base.py         # Abstract base renderer interface
│       │   ├── markdown.py     # Markdown renderer
│       │   ├── html.py         # HTML renderer
│       │   └── json.py         # Normalized JSON renderer
│       └── display.py          # Rich terminal display
├── templates/
│   └── export.html             # Jinja2 template for HTML export
├── tests/
│   ├── fixtures/               # Sample JSONL snippets
│   ├── test_parsers.py
│   ├── test_index.py
│   ├── test_renderers.py
│   └── test_cli.py
└── docs/
    └── adding-a-parser.md      # Contributor guide
```

### Dependencies

| Package | Purpose |
|---------|---------|
| `click` | CLI framework |
| `rich` | Terminal styling |
| `orjson` | Fast JSONL parsing |
| `jinja2` | HTML templates |

4 dependencies total. SQLite/FTS5 and dataclasses are stdlib.

### Entry Points

```toml
[project.scripts]
hrc = "harness_recall.cli:main"
harness-recall = "harness_recall.cli:main"
```

### Parser Interface

```python
class BaseParser(ABC):
    name: str                      # "codex", "claude-code"
    default_paths: list[str]       # ["~/.codex/sessions/"]
    file_pattern: str              # "**/*.jsonl"

    @abstractmethod
    def parse(self, file_path: Path) -> Session: ...

    def discover(self) -> list[Path]: ...  # glob default_paths with file_pattern
```

Adding a new source = one file implementing `parse()` with `name`, `default_paths`, `file_pattern`.

---

## Versioning & Roadmap

### v1.0 — Ship Target

- Codex parser + Claude Code parser
- SQLite + FTS5 indexing with auto-detection and incremental updates
- `list`, `search`, `show`, `export`, `index`, `config` commands
- Markdown, HTML, JSON export
- Polished terminal output with `rich`
- README with install instructions and GIF demo
- Solid error handling

### v1.1

- Interactive `hrc browse` TUI mode (textual library)
- Live search, session preview, keyboard navigation

### v2.0

- Analytics: token usage trends, session stats, cost estimation
- Additional parsers: Cursor, Copilot, Windsurf, Aider
- Tagging and favorites

---

## Competitive Positioning

"The universal, open-source CLI for exporting and searching AI coding sessions."

| vs | Advantage |
|----|-----------|
| ZeroSumQuant | Multi-source, actively maintained, SQLite search (not re-parse), no security vulns |
| SpecStory | Standalone CLI (no VS Code), no commercial cloud, no vendor lock-in |
| Codex_Relay | Export + search (not just transfer), multi-source |
| cursor-chat-browser | CLI-first (not web UI), multi-source, scriptable |

---

## Open Source Strategy

- **License:** MIT
- **Distribution:** PyPI (`pip install harness-recall` / `pipx install harness-recall`)
- **Contribution model:** Parser plugins are the easiest entry point for contributors
- **First impression:** Clean README, working demo GIF, handles errors gracefully on first `pip install && hrc list`
