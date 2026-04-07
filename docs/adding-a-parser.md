# Adding a Parser

This guide explains how to add support for a new AI coding tool to harness-recall.

## What a Parser Does

A parser reads raw session files from a source (typically JSONL) and converts them into the harness-recall Intermediate Representation (IR): `Session`, `Turn`, and `ToolCall` objects. The rest of the system (indexing, rendering, search) only ever sees IR — never raw source data.

## The BaseParser Interface

```python
from harness_recall.parsers.base import BaseParser
from harness_recall.ir import Session
from pathlib import Path

class BaseParser:
    name: str           # unique source identifier, e.g. "cursor"
    default_paths: list[str]  # default glob roots, e.g. ["~/.cursor/sessions/"]
    file_pattern: str   # glob pattern relative to each path, e.g. "**/*.jsonl"

    def parse(self, file_path: Path) -> Session:
        """Read file_path and return a fully populated Session."""
        ...

    def discover(self, paths: list[str] | None = None) -> list[Path]:
        """Return all matching files under the given paths (or default_paths)."""
        # Default implementation provided by BaseParser — override if needed.
        ...
```

`discover()` is provided by `BaseParser` — it expands `~`, resolves each root, and globs with `file_pattern`. Override it only if your source uses a non-standard layout.

## Skeleton Example

```python
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import orjson

from harness_recall.ir import Session, Turn, ToolCall
from harness_recall.parsers.base import BaseParser
from harness_recall.parsers import register_parser


class MyCLIParser(BaseParser):
    name = "mycli"
    default_paths = ["~/.mycli/sessions/"]
    file_pattern = "**/*.jsonl"

    def parse(self, file_path: Path) -> Session:
        events = [orjson.loads(line) for line in file_path.read_bytes().splitlines() if line.strip()]

        session_id = None
        started_at = datetime.now(timezone.utc)
        turns: list[Turn] = []
        seq = 0

        for ev in events:
            if ev.get("type") == "session_start":
                session_id = ev["id"]
                started_at = datetime.fromisoformat(ev["timestamp"])
            elif ev.get("type") == "user_message":
                turns.append(Turn(
                    id=f"{session_id}:{seq}",
                    role="user",
                    content=ev.get("text", ""),
                    timestamp=datetime.fromisoformat(ev["timestamp"]),
                    tool_calls=[],
                ))
                seq += 1
            elif ev.get("type") == "assistant_message":
                turns.append(Turn(
                    id=f"{session_id}:{seq}",
                    role="assistant",
                    content=ev.get("text", ""),
                    timestamp=datetime.fromisoformat(ev["timestamp"]),
                    tool_calls=[],
                ))
                seq += 1

        session = Session(
            id=session_id or file_path.stem,
            source="mycli",
            source_file=str(file_path),
            source_file_mtime=file_path.stat().st_mtime,
            started_at=started_at,
            ended_at=turns[-1].timestamp if turns else None,
            project_dir=None,
            model=None,
            model_provider=None,
            cli_version=None,
            git_branch=None,
            git_commit=None,
            git_repo_url=None,
            title=None,
            parent_session_id=None,
            agent_name=None,
            agent_role=None,
            turns=turns,
        )
        session.title = session.generate_title()
        return session


register_parser(MyCLIParser())
```

## How to Register

Call `register_parser(MyCLIParser())` at the bottom of your parser file. Then import the module in `src/harness_recall/parsers/__init__.py` so it is loaded at startup.

## File Location

- Parser: `src/harness_recall/parsers/mycli.py`
- Tests: `tests/test_mycli_parser.py`
- Test fixtures: `tests/fixtures/` (add one or two real or synthetic `.jsonl` files)

## Testing

Use the existing parser tests as a reference (`tests/test_codex_parser.py`, `tests/test_claude_code_parser.py`). At minimum, write tests that:

1. Parse a fixture file and assert `session.id`, `session.source`, and `len(session.turns)`.
2. Verify that turns have the correct `role` values.
3. Cover any tool-call handling your parser does.
