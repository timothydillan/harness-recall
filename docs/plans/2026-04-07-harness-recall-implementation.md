# harness-recall Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a universal CLI tool that parses AI coding sessions from Codex and Claude Code, indexes them with full-text search, and exports to Markdown/HTML/JSON.

**Architecture:** Adapter pattern — source-specific parsers normalize raw JSONL into a common IR, stored in SQLite+FTS5. Renderers target the IR only. CLI orchestrates via `click` + `rich`.

**Tech Stack:** Python 3.11+, click, rich, orjson, jinja2, SQLite FTS5 (stdlib)

**Spec:** `docs/specs/2026-04-07-harness-recall-design.md`

---

## File Map

```
harness-recall/
├── pyproject.toml                      # Project metadata, deps, entry points
├── LICENSE                             # MIT
├── src/
│   └── harness_recall/
│       ├── __init__.py                 # Version string
│       ├── ir.py                       # IR dataclasses: Session, Turn, ToolCall, TokenUsage
│       ├── parsers/
│       │   ├── __init__.py             # Parser registry: get_parser(), get_all_parsers()
│       │   ├── base.py                 # BaseParser ABC
│       │   ├── codex.py               # Codex JSONL → IR
│       │   └── claude_code.py         # Claude Code JSONL → IR
│       ├── index.py                    # SQLite schema, indexing, FTS5 search, queries
│       ├── renderers/
│       │   ├── __init__.py             # Renderer registry: get_renderer()
│       │   ├── base.py                 # BaseRenderer ABC
│       │   ├── markdown.py            # Session → Markdown string
│       │   ├── html.py                # Session → HTML string (via Jinja2)
│       │   └── json_renderer.py       # Session → normalized JSON string
│       ├── display.py                  # Rich terminal formatting for show/list/search
│       ├── config.py                   # Config file loading + defaults
│       └── cli.py                      # Click commands: list, search, show, export, index, config
├── templates/
│   └── export.html                     # Jinja2 HTML export template
└── tests/
    ├── conftest.py                     # Shared fixtures
    ├── fixtures/                       # Sample JSONL files
    │   ├── codex_simple.jsonl          # Minimal Codex session (5-10 lines)
    │   ├── codex_with_tools.jsonl      # Codex session with function_call + output
    │   ├── codex_subagent.jsonl        # Codex subagent session with forked_from_id
    │   ├── claude_simple.jsonl         # Minimal Claude Code session
    │   ├── claude_with_tools.jsonl     # Claude Code session with tool_use + tool_result
    │   └── claude_with_thinking.jsonl  # Claude Code session with thinking blocks
    ├── test_ir.py
    ├── test_codex_parser.py
    ├── test_claude_code_parser.py
    ├── test_index.py
    ├── test_markdown_renderer.py
    ├── test_html_renderer.py
    ├── test_json_renderer.py
    ├── test_display.py
    └── test_cli.py
```

---

## Task 1: Project Scaffolding + IR Dataclasses

**Files:**
- Create: `pyproject.toml`
- Create: `LICENSE`
- Create: `src/harness_recall/__init__.py`
- Create: `src/harness_recall/ir.py`
- Create: `tests/conftest.py`
- Create: `tests/test_ir.py`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "harness-recall"
version = "0.1.0"
description = "Universal CLI for exporting and searching AI coding sessions"
readme = "README.md"
license = "MIT"
requires-python = ">=3.11"
authors = [
    { name = "Timothy Dillan" },
]
keywords = ["ai", "codex", "claude", "cli", "export", "sessions"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Environment :: Console",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Topic :: Software Development :: Documentation",
]
dependencies = [
    "click>=8.1",
    "rich>=13.0",
    "orjson>=3.9",
    "jinja2>=3.1",
]

[project.scripts]
hrc = "harness_recall.cli:main"
harness-recall = "harness_recall.cli:main"

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=4.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

- [ ] **Step 2: Create `LICENSE`**

MIT license with Timothy Dillan as copyright holder, year 2026.

- [ ] **Step 3: Create `src/harness_recall/__init__.py`**

```python
"""harness-recall: Universal CLI for exporting and searching AI coding sessions."""

__version__ = "0.1.0"
```

- [ ] **Step 4: Write failing test for IR dataclasses**

Create `tests/test_ir.py`:

```python
from datetime import datetime, timezone

from harness_recall.ir import Session, Turn, ToolCall, TokenUsage


def test_session_creation():
    session = Session(
        id="019cbc4c-568c-7b81-9812-3515e63daa70",
        source="codex",
        source_file="/path/to/session.jsonl",
        source_file_mtime=1709600000.0,
        started_at=datetime(2026, 3, 5, 4, 40, 45, tzinfo=timezone.utc),
        ended_at=None,
        project_dir="/Users/dev/project",
        model="gpt-5.3-codex",
        model_provider="openai",
        cli_version="0.108.0",
        git_branch="main",
        git_commit="9b980c4c",
        git_repo_url="https://github.com/user/repo",
        title="Fix auth middleware bug",
        parent_session_id=None,
        agent_name=None,
        agent_role=None,
        turns=[],
    )
    assert session.id == "019cbc4c-568c-7b81-9812-3515e63daa70"
    assert session.source == "codex"
    assert session.turns == []


def test_turn_with_tool_calls():
    tool_call = ToolCall(
        id="call_MqE5W8F8PNnUAAmESYHXOhjT",
        name="exec_command",
        arguments='{"cmd":"pwd && ls","workdir":"/Users/dev"}',
        output="Chunk ID: 9e632a\nexit 0\n/Users/dev\nfile.py",
    )
    usage = TokenUsage(
        input_tokens=90889,
        output_tokens=79,
        cached_tokens=86400,
        reasoning_tokens=13,
    )
    turn = Turn(
        id="019cbc4c:0",
        role="assistant",
        content="I'll check the directory structure.",
        timestamp=datetime(2026, 3, 5, 4, 42, 15, tzinfo=timezone.utc),
        reasoning=None,
        tool_calls=[tool_call],
        token_usage=usage,
    )
    assert turn.role == "assistant"
    assert len(turn.tool_calls) == 1
    assert turn.tool_calls[0].name == "exec_command"
    assert turn.token_usage.input_tokens == 90889


def test_session_title_generation():
    session = Session(
        id="test",
        source="codex",
        source_file="/path/file.jsonl",
        source_file_mtime=0.0,
        started_at=datetime(2026, 3, 5, tzinfo=timezone.utc),
        ended_at=None,
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
        turns=[],
    )
    generated = session.generate_title()
    assert generated == "codex session 2026-03-05 00:00"


def test_session_title_generation_from_user_message():
    turn = Turn(
        id="test:0",
        role="user",
        content="Can you please fix my code at ApiController.php specifically the has_attempted logic?",
        timestamp=datetime(2026, 3, 5, tzinfo=timezone.utc),
        reasoning=None,
        tool_calls=[],
        token_usage=None,
    )
    session = Session(
        id="test",
        source="codex",
        source_file="/path/file.jsonl",
        source_file_mtime=0.0,
        started_at=datetime(2026, 3, 5, tzinfo=timezone.utc),
        ended_at=None,
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
        turns=[turn],
    )
    generated = session.generate_title()
    assert len(generated) <= 80
    assert generated.startswith("Can you please fix my code")


def test_session_to_dict():
    session = Session(
        id="test",
        source="codex",
        source_file="/path/file.jsonl",
        source_file_mtime=0.0,
        started_at=datetime(2026, 3, 5, tzinfo=timezone.utc),
        ended_at=None,
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
        turns=[],
    )
    d = session.to_dict()
    assert d["id"] == "test"
    assert d["source"] == "codex"
    assert d["started_at"] == "2026-03-05T00:00:00+00:00"
```

- [ ] **Step 5: Run tests to verify they fail**

Run: `cd /Users/timothydillan/Documents_Local/GitHub/codex-chat-exporter && python -m pytest tests/test_ir.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'harness_recall'`

- [ ] **Step 6: Implement IR dataclasses**

Create `src/harness_recall/ir.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime


@dataclass
class TokenUsage:
    input_tokens: int
    output_tokens: int
    cached_tokens: int | None = None
    reasoning_tokens: int | None = None


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str
    output: str | None = None


@dataclass
class Turn:
    id: str
    role: str
    content: str
    timestamp: datetime
    reasoning: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    token_usage: TokenUsage | None = None


@dataclass
class Session:
    id: str
    source: str
    source_file: str
    source_file_mtime: float
    started_at: datetime
    ended_at: datetime | None = None
    project_dir: str | None = None
    model: str | None = None
    model_provider: str | None = None
    cli_version: str | None = None
    git_branch: str | None = None
    git_commit: str | None = None
    git_repo_url: str | None = None
    title: str | None = None
    parent_session_id: str | None = None
    agent_name: str | None = None
    agent_role: str | None = None
    turns: list[Turn] = field(default_factory=list)

    def generate_title(self) -> str:
        """Auto-generate title from first user message, or fallback to source + date."""
        for turn in self.turns:
            if turn.role == "user" and turn.content:
                text = turn.content.strip()
                if len(text) > 80:
                    return text[:77] + "..."
                return text
        return f"{self.source} session {self.started_at.strftime('%Y-%m-%d %H:%M')}"

    def to_dict(self) -> dict:
        """Serialize to dict with ISO datetime strings."""
        def convert(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            return obj

        result = {}
        for k, v in asdict(self).items():
            if isinstance(v, datetime):
                result[k] = v.isoformat()
            elif isinstance(v, list) and k == "turns":
                turns_list = []
                for turn_dict in v:
                    turn_out = {}
                    for tk, tv in turn_dict.items():
                        if isinstance(tv, datetime):
                            turn_out[tk] = tv.isoformat()
                        else:
                            turn_out[tk] = tv
                    turns_list.append(turn_out)
                result[k] = turns_list
            else:
                result[k] = v
        return result
```

- [ ] **Step 7: Create `tests/conftest.py`**

```python
import pytest
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir():
    return FIXTURES_DIR
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `cd /Users/timothydillan/Documents_Local/GitHub/codex-chat-exporter && pip install -e ".[dev]" && python -m pytest tests/test_ir.py -v`
Expected: All 5 tests PASS

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml LICENSE src/ tests/
git commit -m "feat: project scaffolding and IR dataclasses"
```

---

## Task 2: Parser Base + Registry

**Files:**
- Create: `src/harness_recall/parsers/__init__.py`
- Create: `src/harness_recall/parsers/base.py`

- [ ] **Step 1: Create `src/harness_recall/parsers/base.py`**

```python
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from harness_recall.ir import Session


class BaseParser(ABC):
    """Base class for all session parsers."""

    name: str
    default_paths: list[str]
    file_pattern: str

    @abstractmethod
    def parse(self, file_path: Path) -> Session:
        """Parse a single source file into an IR Session."""
        ...

    def discover(self, paths: list[str] | None = None) -> list[Path]:
        """Find all session files in given or default paths."""
        search_paths = paths or self.default_paths
        results = []
        for p in search_paths:
            base = Path(p).expanduser()
            if base.exists():
                results.extend(sorted(base.glob(self.file_pattern)))
        return results
```

- [ ] **Step 2: Create `src/harness_recall/parsers/__init__.py`**

```python
from __future__ import annotations

from harness_recall.parsers.base import BaseParser

_REGISTRY: dict[str, BaseParser] = {}


def register_parser(parser: BaseParser) -> None:
    _REGISTRY[parser.name] = parser


def get_parser(name: str) -> BaseParser:
    if name not in _REGISTRY:
        raise ValueError(f"Unknown parser: {name}. Available: {list(_REGISTRY.keys())}")
    return _REGISTRY[name]


def get_all_parsers() -> dict[str, BaseParser]:
    return dict(_REGISTRY)


def _auto_register() -> None:
    """Import parser modules to trigger registration."""
    try:
        from harness_recall.parsers import codex  # noqa: F401
    except ImportError:
        pass
    try:
        from harness_recall.parsers import claude_code  # noqa: F401
    except ImportError:
        pass


_auto_register()
```

- [ ] **Step 3: Commit**

```bash
git add src/harness_recall/parsers/
git commit -m "feat: parser base class and registry"
```

---

## Task 3: Codex Parser

**Files:**
- Create: `tests/fixtures/codex_simple.jsonl`
- Create: `tests/fixtures/codex_with_tools.jsonl`
- Create: `tests/fixtures/codex_subagent.jsonl`
- Create: `tests/test_codex_parser.py`
- Create: `src/harness_recall/parsers/codex.py`

- [ ] **Step 1: Create test fixtures**

Create `tests/fixtures/codex_simple.jsonl` — a minimal Codex session with session_meta, one user_message event, one agent_message event, one task_started, one task_complete, and one token_count:

```jsonl
{"timestamp":"2026-03-05T04:40:45.464Z","type":"session_meta","payload":{"id":"019cbc4c-568c-7b81-9812-3515e63daa70","timestamp":"2026-03-05T04:40:45.455Z","cwd":"/Users/dev/project","originator":"Codex Desktop","cli_version":"0.108.0","source":"vscode","model_provider":"openai","git":{"commit_hash":"9b980c4c","branch":"main","repository_url":"https://github.com/user/repo"}}}
{"timestamp":"2026-03-05T04:41:59.488Z","type":"event_msg","payload":{"type":"task_started","turn_id":"019cbc4d-772c-7f21-9c31-6b8be2999ddc","model_context_window":258400,"collaboration_mode_kind":"default"}}
{"timestamp":"2026-03-05T04:41:59.483Z","type":"response_item","payload":{"type":"message","role":"developer","content":[{"type":"input_text","text":"<permissions instructions>Sandbox mode is danger-full-access.</permissions instructions>"}]}}
{"timestamp":"2026-03-05T04:41:59.490Z","type":"turn_context","payload":{"turn_id":"019cbc4d-772c-7f21-9c31-6b8be2999ddc","model":"gpt-5.3-codex","effort":"xhigh"}}
{"timestamp":"2026-03-05T04:41:59.519Z","type":"event_msg","payload":{"type":"user_message","message":"Can you fix the auth bug in login.py?","images":[],"local_images":[],"text_elements":[]}}
{"timestamp":"2026-03-05T04:42:12.069Z","type":"event_msg","payload":{"type":"agent_message","message":"I'll fix the auth bug by correcting the token validation logic.","phase":"commentary"}}
{"timestamp":"2026-03-05T04:42:30.845Z","type":"response_item","payload":{"type":"reasoning","summary":[],"content":null,"encrypted_content":"gAAAAABpqQnyfh61..."}}
{"timestamp":"2026-03-05T04:43:00.000Z","type":"event_msg","payload":{"type":"agent_message","message":"Fixed the auth bug. The token validation was comparing against the wrong field.","phase":"final"}}
{"timestamp":"2026-03-05T04:43:00.100Z","type":"event_msg","payload":{"type":"token_count","info":{"total_token_usage":{"input_tokens":50000,"cached_input_tokens":40000,"output_tokens":2000,"reasoning_output_tokens":500,"total_tokens":52000},"last_token_usage":{"input_tokens":50000,"cached_input_tokens":40000,"output_tokens":2000,"reasoning_output_tokens":500,"total_tokens":52000},"model_context_window":258400}}}
{"timestamp":"2026-03-05T04:43:00.200Z","type":"event_msg","payload":{"type":"task_complete","turn_id":"019cbc4d-772c-7f21-9c31-6b8be2999ddc","last_agent_message":"Fixed the auth bug."}}
```

Create `tests/fixtures/codex_with_tools.jsonl` — session with function_call + output:

```jsonl
{"timestamp":"2026-03-10T10:00:00.000Z","type":"session_meta","payload":{"id":"019cd000-1111-2222-3333-444444444444","timestamp":"2026-03-10T10:00:00.000Z","cwd":"/Users/dev/app","originator":"CLI","cli_version":"0.110.0","source":"cli","model_provider":"openai"}}
{"timestamp":"2026-03-10T10:00:01.000Z","type":"event_msg","payload":{"type":"task_started","turn_id":"turn-001","model_context_window":258400,"collaboration_mode_kind":"default"}}
{"timestamp":"2026-03-10T10:00:01.000Z","type":"turn_context","payload":{"turn_id":"turn-001","model":"gpt-5.3-codex","effort":"high"}}
{"timestamp":"2026-03-10T10:00:02.000Z","type":"event_msg","payload":{"type":"user_message","message":"List the files in the current directory","images":[],"local_images":[],"text_elements":[]}}
{"timestamp":"2026-03-10T10:00:03.000Z","type":"event_msg","payload":{"type":"agent_message","message":"I'll list the directory contents.","phase":"commentary"}}
{"timestamp":"2026-03-10T10:00:04.000Z","type":"response_item","payload":{"type":"function_call","name":"exec_command","arguments":"{\"cmd\":\"ls -la\",\"workdir\":\"/Users/dev/app\"}","call_id":"call_abc123"}}
{"timestamp":"2026-03-10T10:00:05.000Z","type":"response_item","payload":{"type":"function_call_output","call_id":"call_abc123","output":"total 32\ndrwxr-xr-x  5 dev staff 160 Mar 10 10:00 .\n-rw-r--r--  1 dev staff 256 Mar 10 09:00 main.py\n-rw-r--r--  1 dev staff 128 Mar 10 09:00 config.yaml"}}
{"timestamp":"2026-03-10T10:00:06.000Z","type":"event_msg","payload":{"type":"agent_message","message":"The directory contains main.py and config.yaml.","phase":"final"}}
{"timestamp":"2026-03-10T10:00:07.000Z","type":"event_msg","payload":{"type":"token_count","info":{"total_token_usage":{"input_tokens":10000,"cached_input_tokens":8000,"output_tokens":500,"reasoning_output_tokens":100,"total_tokens":10500},"last_token_usage":{"input_tokens":10000,"cached_input_tokens":8000,"output_tokens":500,"reasoning_output_tokens":100,"total_tokens":10500},"model_context_window":258400}}}
{"timestamp":"2026-03-10T10:00:08.000Z","type":"event_msg","payload":{"type":"task_complete","turn_id":"turn-001","last_agent_message":"The directory contains main.py and config.yaml."}}
```

Create `tests/fixtures/codex_subagent.jsonl` — subagent session:

```jsonl
{"timestamp":"2026-04-07T00:26:30.102Z","type":"session_meta","payload":{"id":"019d6555-sub1-sub1-sub1-sub1sub1sub1","forked_from_id":"019d6555-parent-0000-0000-000000000000","timestamp":"2026-04-07T00:26:30.058Z","cwd":"/Users/dev/project","originator":"Codex Desktop","cli_version":"0.118.0","source":{"subagent":{"thread_spawn":{"parent_thread_id":"019d6555-parent-0000-0000-000000000000","depth":1,"agent_path":null,"agent_nickname":"Euclid","agent_role":"explorer"}}},"agent_nickname":"Euclid","agent_role":"explorer","model_provider":"openai"}}
{"timestamp":"2026-04-07T00:26:31.000Z","type":"event_msg","payload":{"type":"task_started","turn_id":"turn-sub-001","model_context_window":258400,"collaboration_mode_kind":"plan"}}
{"timestamp":"2026-04-07T00:26:32.000Z","type":"event_msg","payload":{"type":"user_message","message":"Explore the codebase structure","images":[],"local_images":[],"text_elements":[]}}
{"timestamp":"2026-04-07T00:26:33.000Z","type":"event_msg","payload":{"type":"agent_message","message":"Exploring directory structure.","phase":"final"}}
{"timestamp":"2026-04-07T00:26:34.000Z","type":"event_msg","payload":{"type":"task_complete","turn_id":"turn-sub-001","last_agent_message":"Exploring directory structure."}}
```

- [ ] **Step 2: Write failing tests for Codex parser**

Create `tests/test_codex_parser.py`:

```python
from pathlib import Path
from datetime import datetime, timezone

from harness_recall.parsers.codex import CodexParser


def test_parse_simple_session(fixtures_dir):
    parser = CodexParser()
    session = parser.parse(fixtures_dir / "codex_simple.jsonl")

    assert session.id == "019cbc4c-568c-7b81-9812-3515e63daa70"
    assert session.source == "codex"
    assert session.model_provider == "openai"
    assert session.cli_version == "0.108.0"
    assert session.project_dir == "/Users/dev/project"
    assert session.git_branch == "main"
    assert session.git_commit == "9b980c4c"
    assert session.git_repo_url == "https://github.com/user/repo"
    assert session.started_at == datetime(2026, 3, 5, 4, 40, 45, 455000, tzinfo=timezone.utc)


def test_parse_extracts_user_and_assistant_turns(fixtures_dir):
    parser = CodexParser()
    session = parser.parse(fixtures_dir / "codex_simple.jsonl")

    user_turns = [t for t in session.turns if t.role == "user"]
    assistant_turns = [t for t in session.turns if t.role == "assistant"]

    assert len(user_turns) == 1
    assert user_turns[0].content == "Can you fix the auth bug in login.py?"

    assert len(assistant_turns) >= 1
    # Final agent message becomes the assistant turn content
    assert any("Fixed the auth bug" in t.content for t in assistant_turns)


def test_parse_skips_developer_messages(fixtures_dir):
    parser = CodexParser()
    session = parser.parse(fixtures_dir / "codex_simple.jsonl")

    developer_turns = [t for t in session.turns if t.role == "developer"]
    assert len(developer_turns) == 0


def test_parse_with_tool_calls(fixtures_dir):
    parser = CodexParser()
    session = parser.parse(fixtures_dir / "codex_with_tools.jsonl")

    # Find the assistant turn with tool calls
    tool_turns = [t for t in session.turns if t.tool_calls]
    assert len(tool_turns) == 1
    assert tool_turns[0].tool_calls[0].name == "exec_command"
    assert tool_turns[0].tool_calls[0].id == "call_abc123"
    assert "ls -la" in tool_turns[0].tool_calls[0].arguments
    assert "main.py" in tool_turns[0].tool_calls[0].output


def test_parse_extracts_token_usage(fixtures_dir):
    parser = CodexParser()
    session = parser.parse(fixtures_dir / "codex_simple.jsonl")

    # At least one turn should have token usage from the token_count event
    turns_with_tokens = [t for t in session.turns if t.token_usage]
    assert len(turns_with_tokens) >= 1
    assert turns_with_tokens[0].token_usage.input_tokens == 50000
    assert turns_with_tokens[0].token_usage.output_tokens == 2000
    assert turns_with_tokens[0].token_usage.cached_tokens == 40000
    assert turns_with_tokens[0].token_usage.reasoning_tokens == 500


def test_parse_subagent_session(fixtures_dir):
    parser = CodexParser()
    session = parser.parse(fixtures_dir / "codex_subagent.jsonl")

    assert session.parent_session_id == "019d6555-parent-0000-0000-000000000000"
    assert session.agent_name == "Euclid"
    assert session.agent_role == "explorer"


def test_parse_sets_ended_at(fixtures_dir):
    parser = CodexParser()
    session = parser.parse(fixtures_dir / "codex_simple.jsonl")

    assert session.ended_at is not None
    assert session.ended_at > session.started_at


def test_parse_encrypted_reasoning_is_none(fixtures_dir):
    parser = CodexParser()
    session = parser.parse(fixtures_dir / "codex_simple.jsonl")

    # Encrypted reasoning should result in None
    for turn in session.turns:
        if turn.reasoning is not None:
            # If reasoning exists, it should be actual text, not encrypted blob
            assert not turn.reasoning.startswith("gAAAAA")


def test_discover_default_paths(tmp_path):
    # Create a fake codex sessions structure
    session_dir = tmp_path / ".codex" / "sessions" / "2026" / "03" / "05"
    session_dir.mkdir(parents=True)
    (session_dir / "rollout-2026-03-05T12-00-00-abc123.jsonl").write_text("{}")

    parser = CodexParser()
    files = parser.discover(paths=[str(tmp_path / ".codex" / "sessions")])
    assert len(files) == 1
    assert files[0].name == "rollout-2026-03-05T12-00-00-abc123.jsonl"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/test_codex_parser.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'harness_recall.parsers.codex'`

- [ ] **Step 4: Implement Codex parser**

Create `src/harness_recall/parsers/codex.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import orjson

from harness_recall.ir import Session, Turn, ToolCall, TokenUsage
from harness_recall.parsers.base import BaseParser
from harness_recall.parsers import register_parser


class CodexParser(BaseParser):
    name = "codex"
    default_paths = ["~/.codex/sessions/"]
    file_pattern = "**/*.jsonl"

    def parse(self, file_path: Path) -> Session:
        lines = file_path.read_bytes().split(b"\n")
        events = []
        for line in lines:
            line = line.strip()
            if line:
                events.append(orjson.loads(line))

        # Extract session metadata
        session_meta = None
        turn_context = None
        for ev in events:
            if ev["type"] == "session_meta":
                session_meta = ev["payload"]
                break

        for ev in events:
            if ev["type"] == "turn_context":
                turn_context = ev["payload"]
                break

        if session_meta is None:
            raise ValueError(f"No session_meta found in {file_path}")

        # Parse metadata
        session_id = session_meta["id"]
        started_at = _parse_ts(session_meta["timestamp"])
        cwd = session_meta.get("cwd")
        cli_version = session_meta.get("cli_version")
        model_provider = session_meta.get("model_provider")
        originator = session_meta.get("originator")

        # Git info
        git = session_meta.get("git", {})
        git_branch = git.get("branch") if isinstance(git, dict) else None
        git_commit = git.get("commit_hash") if isinstance(git, dict) else None
        git_repo_url = git.get("repository_url") if isinstance(git, dict) else None

        # Model from turn_context
        model = turn_context.get("model") if turn_context else None

        # Subagent info
        parent_session_id = session_meta.get("forked_from_id")
        agent_name = session_meta.get("agent_nickname")
        agent_role = session_meta.get("agent_role")

        # Build turns from events
        turns = []
        pending_tool_calls: dict[str, ToolCall] = {}
        last_token_usage: TokenUsage | None = None
        ended_at: datetime | None = None
        seq = 0

        for ev in events:
            ts = _parse_ts(ev["timestamp"])
            ended_at = ts  # track latest timestamp

            if ev["type"] == "event_msg":
                payload = ev["payload"]
                msg_type = payload["type"]

                if msg_type == "user_message":
                    text = payload.get("message", "")
                    if text.strip():
                        turns.append(Turn(
                            id=f"{session_id}:{seq}",
                            role="user",
                            content=text,
                            timestamp=ts,
                            tool_calls=[],
                        ))
                        seq += 1

                elif msg_type == "agent_message":
                    phase = payload.get("phase", "")
                    text = payload.get("message", "")
                    if text.strip():
                        # Attach pending tool calls to the last assistant turn
                        resolved_tools = list(pending_tool_calls.values())
                        pending_tool_calls.clear()
                        turns.append(Turn(
                            id=f"{session_id}:{seq}",
                            role="assistant",
                            content=text,
                            timestamp=ts,
                            tool_calls=resolved_tools,
                            token_usage=last_token_usage,
                        ))
                        last_token_usage = None
                        seq += 1

                elif msg_type == "token_count":
                    info = payload.get("info", {})
                    total = info.get("total_token_usage", {})
                    last_token_usage = TokenUsage(
                        input_tokens=total.get("input_tokens", 0),
                        output_tokens=total.get("output_tokens", 0),
                        cached_tokens=total.get("cached_input_tokens"),
                        reasoning_tokens=total.get("reasoning_output_tokens"),
                    )

            elif ev["type"] == "response_item":
                payload = ev["payload"]
                item_type = payload["type"]

                if item_type == "function_call":
                    call_id = payload.get("call_id", "")
                    pending_tool_calls[call_id] = ToolCall(
                        id=call_id,
                        name=payload.get("name", ""),
                        arguments=payload.get("arguments", ""),
                        output=None,
                    )
                elif item_type == "function_call_output":
                    call_id = payload.get("call_id", "")
                    if call_id in pending_tool_calls:
                        output = payload.get("output", "")
                        # Truncate to 10KB for storage
                        if len(output) > 10240:
                            output = output[:10240] + "\n... [truncated]"
                        pending_tool_calls[call_id].output = output

        # If there are remaining tool calls not attached to a turn, create one
        if pending_tool_calls:
            resolved_tools = list(pending_tool_calls.values())
            turns.append(Turn(
                id=f"{session_id}:{seq}",
                role="assistant",
                content="",
                timestamp=ended_at or started_at,
                tool_calls=resolved_tools,
                token_usage=last_token_usage,
            ))
            seq += 1

        session = Session(
            id=session_id,
            source="codex",
            source_file=str(file_path),
            source_file_mtime=file_path.stat().st_mtime,
            started_at=started_at,
            ended_at=ended_at,
            project_dir=cwd,
            model=model,
            model_provider=model_provider,
            cli_version=cli_version,
            git_branch=git_branch,
            git_commit=git_commit,
            git_repo_url=git_repo_url,
            title=None,
            parent_session_id=parent_session_id,
            agent_name=agent_name,
            agent_role=agent_role,
            turns=turns,
        )
        # Auto-generate title
        session.title = session.generate_title()
        return session


def _parse_ts(ts_str: str) -> datetime:
    """Parse ISO 8601 timestamp string to datetime."""
    if ts_str.endswith("Z"):
        ts_str = ts_str[:-1] + "+00:00"
    return datetime.fromisoformat(ts_str)


register_parser(CodexParser())
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_codex_parser.py -v`
Expected: All 9 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/harness_recall/parsers/codex.py tests/fixtures/codex_*.jsonl tests/test_codex_parser.py
git commit -m "feat: Codex JSONL parser with tool call and subagent support"
```

---

## Task 4: Claude Code Parser

**Files:**
- Create: `tests/fixtures/claude_simple.jsonl`
- Create: `tests/fixtures/claude_with_tools.jsonl`
- Create: `tests/fixtures/claude_with_thinking.jsonl`
- Create: `tests/test_claude_code_parser.py`
- Create: `src/harness_recall/parsers/claude_code.py`

- [ ] **Step 1: Create test fixtures**

Create `tests/fixtures/claude_simple.jsonl` — minimal Claude Code session:

```jsonl
{"type":"queue-operation","operation":"enqueue","timestamp":"2026-03-17T12:00:28.839Z","sessionId":"285b38ce-dc4a-444b-b107-b40470be2a52","content":"Hello, please help me with this project."}
{"type":"queue-operation","operation":"dequeue","timestamp":"2026-03-17T12:00:28.883Z","sessionId":"285b38ce-dc4a-444b-b107-b40470be2a52"}
{"parentUuid":null,"isSidechain":false,"type":"progress","data":{"type":"hook_progress","hookEvent":"SessionStart","hookName":"SessionStart:startup","command":"hook.sh"},"timestamp":"2026-03-17T12:00:28.201Z","uuid":"a2493b54-0001","cwd":"/Users/dev/project","sessionId":"285b38ce-dc4a-444b-b107-b40470be2a52","version":"2.1.75","gitBranch":"main"}
{"parentUuid":"a2493b54-0001","isSidechain":false,"promptId":"prompt-001","type":"user","message":{"role":"user","content":"Help me fix the login bug in auth.py"},"uuid":"user-001","timestamp":"2026-03-17T12:00:30.000Z","cwd":"/Users/dev/project","sessionId":"285b38ce-dc4a-444b-b107-b40470be2a52","version":"2.1.75","gitBranch":"main"}
{"parentUuid":"user-001","isSidechain":false,"message":{"model":"claude-opus-4-6","id":"msg_001","type":"message","role":"assistant","content":[{"type":"text","text":"I'll help you fix the login bug. Let me look at the auth.py file first."}],"stop_reason":"end_turn","usage":{"input_tokens":1500,"cache_creation_input_tokens":0,"cache_read_input_tokens":500,"output_tokens":30}},"type":"assistant","uuid":"asst-001","timestamp":"2026-03-17T12:00:32.000Z","cwd":"/Users/dev/project","sessionId":"285b38ce-dc4a-444b-b107-b40470be2a52","version":"2.1.75","gitBranch":"main"}
{"type":"last-prompt","lastPrompt":"Help me fix the login bug...","sessionId":"285b38ce-dc4a-444b-b107-b40470be2a52"}
```

Create `tests/fixtures/claude_with_tools.jsonl` — with tool_use and tool_result:

```jsonl
{"type":"queue-operation","operation":"enqueue","timestamp":"2026-03-20T09:00:00.000Z","sessionId":"session-tools-001","content":"Read the config"}
{"type":"queue-operation","operation":"dequeue","timestamp":"2026-03-20T09:00:00.100Z","sessionId":"session-tools-001"}
{"parentUuid":null,"isSidechain":false,"promptId":"prompt-001","type":"user","message":{"role":"user","content":"Read the config file and tell me what port the server runs on"},"uuid":"user-001","timestamp":"2026-03-20T09:00:01.000Z","cwd":"/Users/dev/app","sessionId":"session-tools-001","version":"2.1.80","gitBranch":"develop"}
{"parentUuid":"user-001","isSidechain":false,"message":{"model":"claude-sonnet-4-6","id":"msg_001","type":"message","role":"assistant","content":[{"type":"text","text":"I'll read the config file for you."}],"stop_reason":null,"usage":{"input_tokens":800,"output_tokens":15}},"type":"assistant","uuid":"asst-001","timestamp":"2026-03-20T09:00:02.000Z","cwd":"/Users/dev/app","sessionId":"session-tools-001","version":"2.1.80","gitBranch":"develop"}
{"parentUuid":"asst-001","isSidechain":false,"message":{"model":"claude-sonnet-4-6","id":"msg_001","type":"message","role":"assistant","content":[{"type":"tool_use","id":"toolu_01ABC","name":"Read","input":{"file_path":"/Users/dev/app/config.yaml"},"caller":{"type":"direct"}}],"stop_reason":"tool_use","usage":{"input_tokens":800,"output_tokens":50}},"type":"assistant","uuid":"asst-002","timestamp":"2026-03-20T09:00:03.000Z","cwd":"/Users/dev/app","sessionId":"session-tools-001","version":"2.1.80","gitBranch":"develop"}
{"parentUuid":"asst-002","isSidechain":false,"promptId":"prompt-001","type":"user","message":{"role":"user","content":[{"tool_use_id":"toolu_01ABC","type":"tool_result","content":"port: 8080\nhost: 0.0.0.0\ndebug: true","is_error":false}]},"uuid":"tool-result-001","timestamp":"2026-03-20T09:00:04.000Z","cwd":"/Users/dev/app","sessionId":"session-tools-001","version":"2.1.80","gitBranch":"develop"}
{"parentUuid":"tool-result-001","isSidechain":false,"message":{"model":"claude-sonnet-4-6","id":"msg_002","type":"message","role":"assistant","content":[{"type":"text","text":"The server runs on port **8080**, bound to all interfaces (0.0.0.0) with debug mode enabled."}],"stop_reason":"end_turn","usage":{"input_tokens":900,"output_tokens":25}},"type":"assistant","uuid":"asst-003","timestamp":"2026-03-20T09:00:05.000Z","cwd":"/Users/dev/app","sessionId":"session-tools-001","version":"2.1.80","gitBranch":"develop"}
```

Create `tests/fixtures/claude_with_thinking.jsonl` — with thinking blocks:

```jsonl
{"type":"queue-operation","operation":"enqueue","timestamp":"2026-03-22T14:00:00.000Z","sessionId":"session-think-001","content":"Explain the algorithm"}
{"type":"queue-operation","operation":"dequeue","timestamp":"2026-03-22T14:00:00.100Z","sessionId":"session-think-001"}
{"parentUuid":null,"isSidechain":false,"promptId":"prompt-001","type":"user","message":{"role":"user","content":"Explain how the sorting algorithm works in utils.py"},"uuid":"user-001","timestamp":"2026-03-22T14:00:01.000Z","cwd":"/Users/dev/algo","sessionId":"session-think-001","version":"2.1.85","gitBranch":"feature/sort"}
{"parentUuid":"user-001","isSidechain":false,"message":{"model":"claude-opus-4-6","id":"msg_001","type":"message","role":"assistant","content":[{"type":"thinking","thinking":"The user wants to understand the sorting algorithm. Let me think about how to explain this clearly. The algorithm in utils.py uses a modified merge sort with a cutoff to insertion sort for small subarrays.","signature":"EpYECkYI..."},{"type":"text","text":"The sorting algorithm in utils.py is a hybrid approach combining merge sort with insertion sort for small subarrays (< 16 elements). This gives O(n log n) worst-case with better constant factors for small inputs."}],"stop_reason":"end_turn","usage":{"input_tokens":2000,"output_tokens":60}},"type":"assistant","uuid":"asst-001","timestamp":"2026-03-22T14:00:05.000Z","cwd":"/Users/dev/algo","sessionId":"session-think-001","version":"2.1.85","gitBranch":"feature/sort"}
```

- [ ] **Step 2: Write failing tests for Claude Code parser**

Create `tests/test_claude_code_parser.py`:

```python
from pathlib import Path

from harness_recall.parsers.claude_code import ClaudeCodeParser


def test_parse_simple_session(fixtures_dir):
    parser = ClaudeCodeParser()
    session = parser.parse(fixtures_dir / "claude_simple.jsonl")

    assert session.id == "285b38ce-dc4a-444b-b107-b40470be2a52"
    assert session.source == "claude-code"
    assert session.project_dir == "/Users/dev/project"
    assert session.git_branch == "main"


def test_parse_extracts_user_and_assistant_turns(fixtures_dir):
    parser = ClaudeCodeParser()
    session = parser.parse(fixtures_dir / "claude_simple.jsonl")

    user_turns = [t for t in session.turns if t.role == "user"]
    assistant_turns = [t for t in session.turns if t.role == "assistant"]

    assert len(user_turns) == 1
    assert "login bug" in user_turns[0].content

    assert len(assistant_turns) == 1
    assert "auth.py" in assistant_turns[0].content


def test_parse_extracts_model_info(fixtures_dir):
    parser = ClaudeCodeParser()
    session = parser.parse(fixtures_dir / "claude_simple.jsonl")

    assert session.model == "claude-opus-4-6"
    assert session.model_provider == "anthropic"


def test_parse_extracts_version(fixtures_dir):
    parser = ClaudeCodeParser()
    session = parser.parse(fixtures_dir / "claude_simple.jsonl")

    assert session.cli_version == "2.1.75"


def test_parse_with_tool_calls(fixtures_dir):
    parser = ClaudeCodeParser()
    session = parser.parse(fixtures_dir / "claude_with_tools.jsonl")

    tool_turns = [t for t in session.turns if t.tool_calls]
    assert len(tool_turns) == 1
    assert tool_turns[0].tool_calls[0].name == "Read"
    assert tool_turns[0].tool_calls[0].id == "toolu_01ABC"
    assert "file_path" in tool_turns[0].tool_calls[0].arguments
    assert "port: 8080" in tool_turns[0].tool_calls[0].output


def test_parse_with_thinking(fixtures_dir):
    parser = ClaudeCodeParser()
    session = parser.parse(fixtures_dir / "claude_with_thinking.jsonl")

    assistant_turns = [t for t in session.turns if t.role == "assistant"]
    assert len(assistant_turns) == 1
    assert assistant_turns[0].reasoning is not None
    assert "merge sort" in assistant_turns[0].reasoning


def test_parse_skips_tool_result_as_user_turn(fixtures_dir):
    """tool_result messages should not create user turns."""
    parser = ClaudeCodeParser()
    session = parser.parse(fixtures_dir / "claude_with_tools.jsonl")

    user_turns = [t for t in session.turns if t.role == "user"]
    # Only the actual user message, not the tool_result
    assert len(user_turns) == 1
    assert "config file" in user_turns[0].content


def test_parse_token_usage(fixtures_dir):
    parser = ClaudeCodeParser()
    session = parser.parse(fixtures_dir / "claude_simple.jsonl")

    assistant_turns = [t for t in session.turns if t.role == "assistant"]
    assert assistant_turns[0].token_usage is not None
    assert assistant_turns[0].token_usage.input_tokens == 1500
    assert assistant_turns[0].token_usage.output_tokens == 30


def test_discover_default_paths(tmp_path):
    project_dir = tmp_path / ".claude" / "projects" / "my-project"
    project_dir.mkdir(parents=True)
    (project_dir / "abc123.jsonl").write_text("{}")

    parser = ClaudeCodeParser()
    files = parser.discover(paths=[str(tmp_path / ".claude" / "projects")])
    assert len(files) == 1
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/test_claude_code_parser.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Implement Claude Code parser**

Create `src/harness_recall/parsers/claude_code.py`:

```python
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import orjson

from harness_recall.ir import Session, Turn, ToolCall, TokenUsage
from harness_recall.parsers.base import BaseParser
from harness_recall.parsers import register_parser


class ClaudeCodeParser(BaseParser):
    name = "claude-code"
    default_paths = ["~/.claude/projects/"]
    file_pattern = "**/*.jsonl"

    def parse(self, file_path: Path) -> Session:
        lines = file_path.read_bytes().split(b"\n")
        events = []
        for line in lines:
            line = line.strip()
            if line:
                events.append(orjson.loads(line))

        session_id = None
        cwd = None
        version = None
        git_branch = None
        model = None
        started_at = None
        ended_at = None

        turns: list[Turn] = []
        # Track pending tool calls by tool_use_id
        pending_tool_calls: dict[str, ToolCall] = {}
        seq = 0

        for ev in events:
            ev_type = ev.get("type")
            ts_str = ev.get("timestamp")
            ts = _parse_ts(ts_str) if ts_str else None

            if ts:
                if started_at is None:
                    started_at = ts
                ended_at = ts

            # Extract session metadata from any event that has it
            if not session_id and ev.get("sessionId"):
                session_id = ev["sessionId"]
            if not cwd and ev.get("cwd"):
                cwd = ev["cwd"]
            if not version and ev.get("version"):
                version = ev["version"]
            if not git_branch and ev.get("gitBranch"):
                git_branch = ev["gitBranch"]

            if ev_type == "user":
                msg = ev.get("message", {})
                content = msg.get("content", "")

                # Skip tool_result messages
                if isinstance(content, list):
                    is_tool_result = all(
                        isinstance(b, dict) and b.get("type") == "tool_result"
                        for b in content
                    )
                    if is_tool_result:
                        # Attach tool outputs to pending calls
                        for block in content:
                            tool_id = block.get("tool_use_id", "")
                            if tool_id in pending_tool_calls:
                                output = block.get("content", "")
                                if isinstance(output, list):
                                    output = "\n".join(
                                        b.get("text", "") for b in output if isinstance(b, dict)
                                    )
                                if len(output) > 10240:
                                    output = output[:10240] + "\n... [truncated]"
                                pending_tool_calls[tool_id].output = output
                        continue

                    # Extract text from content blocks
                    text_parts = []
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "input_text":
                            text_parts.append(block.get("text", ""))
                        elif isinstance(block, str):
                            text_parts.append(block)
                    content = "\n".join(text_parts)

                if isinstance(content, str) and content.strip():
                    # Skip system instructions injected as user messages
                    if content.strip().startswith("<system_instruction>"):
                        continue
                    turns.append(Turn(
                        id=f"{session_id}:{seq}",
                        role="user",
                        content=content,
                        timestamp=ts or started_at or datetime.now(timezone.utc),
                        tool_calls=[],
                    ))
                    seq += 1

            elif ev_type == "assistant":
                msg = ev.get("message", {})
                content_blocks = msg.get("content", [])
                usage = msg.get("usage", {})

                if not model:
                    model = msg.get("model")

                text_parts = []
                thinking_text = None
                turn_tool_calls = []

                for block in content_blocks:
                    if not isinstance(block, dict):
                        continue
                    block_type = block.get("type")

                    if block_type == "text":
                        text = block.get("text", "").strip()
                        if text:
                            text_parts.append(text)

                    elif block_type == "thinking":
                        thinking_text = block.get("thinking", "")

                    elif block_type == "tool_use":
                        tool_id = block.get("id", "")
                        tc = ToolCall(
                            id=tool_id,
                            name=block.get("name", ""),
                            arguments=json.dumps(block.get("input", {})),
                            output=None,
                        )
                        pending_tool_calls[tool_id] = tc
                        turn_tool_calls.append(tc)

                text = "\n\n".join(text_parts)

                # Only create a turn if there's text or tool calls
                if text or turn_tool_calls:
                    token_usage = None
                    if usage:
                        token_usage = TokenUsage(
                            input_tokens=usage.get("input_tokens", 0),
                            output_tokens=usage.get("output_tokens", 0),
                            cached_tokens=usage.get("cache_read_input_tokens"),
                            reasoning_tokens=None,
                        )

                    turns.append(Turn(
                        id=f"{session_id}:{seq}",
                        role="assistant",
                        content=text,
                        timestamp=ts or ended_at or datetime.now(timezone.utc),
                        reasoning=thinking_text,
                        tool_calls=turn_tool_calls,
                        token_usage=token_usage,
                    ))
                    seq += 1

        if started_at is None:
            started_at = datetime.now(timezone.utc)

        session = Session(
            id=session_id or file_path.stem,
            source="claude-code",
            source_file=str(file_path),
            source_file_mtime=file_path.stat().st_mtime,
            started_at=started_at,
            ended_at=ended_at,
            project_dir=cwd,
            model=model,
            model_provider="anthropic",
            cli_version=version,
            git_branch=git_branch,
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


def _parse_ts(ts_str: str) -> datetime:
    if ts_str.endswith("Z"):
        ts_str = ts_str[:-1] + "+00:00"
    return datetime.fromisoformat(ts_str)


register_parser(ClaudeCodeParser())
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_claude_code_parser.py -v`
Expected: All 9 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/harness_recall/parsers/claude_code.py tests/fixtures/claude_*.jsonl tests/test_claude_code_parser.py
git commit -m "feat: Claude Code JSONL parser with tool_use and thinking support"
```

---

## Task 5: SQLite Index + FTS5

**Files:**
- Create: `src/harness_recall/index.py`
- Create: `tests/test_index.py`

- [ ] **Step 1: Write failing tests for index**

Create `tests/test_index.py`:

```python
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from harness_recall.ir import Session, Turn, ToolCall, TokenUsage
from harness_recall.index import SessionIndex


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test_index.db"


@pytest.fixture
def index(db_path):
    return SessionIndex(db_path)


@pytest.fixture
def sample_session():
    return Session(
        id="session-001",
        source="codex",
        source_file="/path/to/file.jsonl",
        source_file_mtime=1709600000.0,
        started_at=datetime(2026, 3, 5, 10, 0, 0, tzinfo=timezone.utc),
        ended_at=datetime(2026, 3, 5, 10, 30, 0, tzinfo=timezone.utc),
        project_dir="/Users/dev/project",
        model="gpt-5.3-codex",
        model_provider="openai",
        cli_version="0.108.0",
        git_branch="main",
        git_commit="abc123",
        git_repo_url=None,
        title="Fix the authentication bug",
        parent_session_id=None,
        agent_name=None,
        agent_role=None,
        turns=[
            Turn(
                id="session-001:0",
                role="user",
                content="Fix the authentication bug in login.py where tokens expire too early",
                timestamp=datetime(2026, 3, 5, 10, 0, 0, tzinfo=timezone.utc),
                tool_calls=[],
            ),
            Turn(
                id="session-001:1",
                role="assistant",
                content="I found the bug. The token expiry was set to 60 seconds instead of 3600.",
                timestamp=datetime(2026, 3, 5, 10, 5, 0, tzinfo=timezone.utc),
                tool_calls=[
                    ToolCall(id="call_001", name="exec_command", arguments='{"cmd":"grep -n expiry login.py"}', output="42: TOKEN_EXPIRY = 60"),
                ],
                token_usage=TokenUsage(input_tokens=5000, output_tokens=200, cached_tokens=4000, reasoning_tokens=50),
            ),
        ],
    )


def test_create_index(index):
    """Index creates tables on init."""
    conn = sqlite3.connect(index.db_path)
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    table_names = {t[0] for t in tables}
    assert "sessions" in table_names
    assert "turns" in table_names
    assert "tool_calls" in table_names
    assert "turns_fts" in table_names
    conn.close()


def test_add_session(index, sample_session):
    index.add_session(sample_session)
    sessions = index.list_sessions()
    assert len(sessions) == 1
    assert sessions[0]["id"] == "session-001"
    assert sessions[0]["title"] == "Fix the authentication bug"


def test_search_fts(index, sample_session):
    index.add_session(sample_session)
    results = index.search("authentication bug")
    assert len(results) > 0
    assert results[0]["session_id"] == "session-001"


def test_search_fts_no_results(index, sample_session):
    index.add_session(sample_session)
    results = index.search("kubernetes deployment")
    assert len(results) == 0


def test_search_with_source_filter(index, sample_session):
    index.add_session(sample_session)
    results = index.search("authentication", source="codex")
    assert len(results) > 0
    results = index.search("authentication", source="claude-code")
    assert len(results) == 0


def test_get_session(index, sample_session):
    index.add_session(sample_session)
    session = index.get_session("session-001")
    assert session is not None
    assert session["id"] == "session-001"
    assert session["model"] == "gpt-5.3-codex"


def test_get_session_turns(index, sample_session):
    index.add_session(sample_session)
    turns = index.get_session_turns("session-001")
    assert len(turns) == 2
    assert turns[0]["role"] == "user"
    assert turns[1]["role"] == "assistant"


def test_get_session_tool_calls(index, sample_session):
    index.add_session(sample_session)
    tool_calls = index.get_tool_calls("session-001")
    assert len(tool_calls) == 1
    assert tool_calls[0]["name"] == "exec_command"


def test_list_sessions_with_filters(index, sample_session):
    index.add_session(sample_session)

    # Filter by source
    results = index.list_sessions(source="codex")
    assert len(results) == 1
    results = index.list_sessions(source="claude-code")
    assert len(results) == 0

    # Filter by after date
    results = index.list_sessions(after="2026-03-01")
    assert len(results) == 1
    results = index.list_sessions(after="2026-04-01")
    assert len(results) == 0


def test_needs_reindex(index, sample_session, tmp_path):
    # File doesn't exist in index → needs reindex
    fake_file = tmp_path / "session.jsonl"
    fake_file.write_text("{}")
    assert index.needs_reindex(str(fake_file), fake_file.stat().st_mtime)

    # After adding, same mtime → no reindex
    index.add_session(sample_session)
    assert not index.needs_reindex(sample_session.source_file, sample_session.source_file_mtime)

    # Different mtime → needs reindex
    assert index.needs_reindex(sample_session.source_file, sample_session.source_file_mtime + 100)


def test_remove_session(index, sample_session):
    index.add_session(sample_session)
    assert len(index.list_sessions()) == 1
    index.remove_session("session-001")
    assert len(index.list_sessions()) == 0


def test_stats(index, sample_session):
    index.add_session(sample_session)
    stats = index.stats()
    assert stats["total_sessions"] == 1
    assert stats["total_turns"] == 2
    assert stats["sources"]["codex"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_index.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement `src/harness_recall/index.py`**

```python
from __future__ import annotations

import sqlite3
from pathlib import Path

from harness_recall.ir import Session


class SessionIndex:
    def __init__(self, db_path: Path | str):
        self.db_path = str(db_path)
        self._init_db()

    def _init_db(self):
        conn = self._connect()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
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

            CREATE TABLE IF NOT EXISTS turns (
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

            CREATE TABLE IF NOT EXISTS tool_calls (
                id TEXT PRIMARY KEY,
                turn_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                name TEXT NOT NULL,
                arguments TEXT,
                output TEXT,
                FOREIGN KEY (turn_id) REFERENCES turns(id),
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            );

            CREATE INDEX IF NOT EXISTS idx_sessions_started_at ON sessions(started_at);
            CREATE INDEX IF NOT EXISTS idx_sessions_source ON sessions(source);
            CREATE INDEX IF NOT EXISTS idx_sessions_project_dir ON sessions(project_dir);
            CREATE INDEX IF NOT EXISTS idx_turns_session_id ON turns(session_id);
            CREATE INDEX IF NOT EXISTS idx_tool_calls_session_id ON tool_calls(session_id);
            CREATE INDEX IF NOT EXISTS idx_tool_calls_name ON tool_calls(name);
        """)
        # FTS5 table — separate statement because CREATE VIRTUAL TABLE IF NOT EXISTS
        # doesn't work reliably with executescript
        try:
            conn.execute("""
                CREATE VIRTUAL TABLE turns_fts USING fts5(
                    content,
                    content='turns',
                    content_rowid='rowid',
                    tokenize='porter unicode61'
                )
            """)
        except sqlite3.OperationalError:
            pass  # Already exists
        conn.commit()
        conn.close()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def add_session(self, session: Session) -> None:
        conn = self._connect()
        # Remove existing session data if re-indexing
        self._remove_session_data(conn, session.id)

        total_input = sum(t.token_usage.input_tokens for t in session.turns if t.token_usage)
        total_output = sum(t.token_usage.output_tokens for t in session.turns if t.token_usage)

        conn.execute("""
            INSERT INTO sessions (id, source, source_file, source_file_mtime,
                started_at, ended_at, project_dir, model, model_provider,
                cli_version, git_branch, git_commit, git_repo_url, title,
                parent_session_id, agent_name, agent_role,
                total_input_tokens, total_output_tokens)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session.id, session.source, session.source_file, session.source_file_mtime,
            session.started_at.isoformat(), session.ended_at.isoformat() if session.ended_at else None,
            session.project_dir, session.model, session.model_provider,
            session.cli_version, session.git_branch, session.git_commit, session.git_repo_url,
            session.title, session.parent_session_id, session.agent_name, session.agent_role,
            total_input or None, total_output or None,
        ))

        for i, turn in enumerate(session.turns):
            input_t = turn.token_usage.input_tokens if turn.token_usage else None
            output_t = turn.token_usage.output_tokens if turn.token_usage else None
            conn.execute("""
                INSERT INTO turns (id, session_id, sequence_num, role, content,
                    timestamp, reasoning, input_tokens, output_tokens)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                turn.id, session.id, i, turn.role, turn.content,
                turn.timestamp.isoformat(), turn.reasoning, input_t, output_t,
            ))
            # Populate FTS
            rowid = conn.execute("SELECT rowid FROM turns WHERE id = ?", (turn.id,)).fetchone()[0]
            conn.execute("INSERT INTO turns_fts(rowid, content) VALUES (?, ?)", (rowid, turn.content or ""))

            for tc in turn.tool_calls:
                conn.execute("""
                    INSERT INTO tool_calls (id, turn_id, session_id, name, arguments, output)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (tc.id, turn.id, session.id, tc.name, tc.arguments, tc.output))

        conn.commit()
        conn.close()

    def remove_session(self, session_id: str) -> None:
        conn = self._connect()
        self._remove_session_data(conn, session_id)
        conn.commit()
        conn.close()

    def _remove_session_data(self, conn: sqlite3.Connection, session_id: str) -> None:
        # Remove FTS entries for turns
        rows = conn.execute("SELECT rowid FROM turns WHERE session_id = ?", (session_id,)).fetchall()
        for row in rows:
            conn.execute("INSERT INTO turns_fts(turns_fts, rowid, content) VALUES('delete', ?, '')", (row[0],))
        conn.execute("DELETE FROM tool_calls WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM turns WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))

    def list_sessions(self, source: str | None = None, after: str | None = None,
                      project: str | None = None, limit: int = 25) -> list[dict]:
        conn = self._connect()
        query = "SELECT * FROM sessions WHERE 1=1"
        params: list = []
        if source:
            query += " AND source = ?"
            params.append(source)
        if after:
            query += " AND started_at >= ?"
            params.append(after)
        if project:
            query += " AND project_dir LIKE ?"
            params.append(f"%{project}%")
        query += " ORDER BY started_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def search(self, query: str, source: str | None = None,
               tool: str | None = None, limit: int = 25) -> list[dict]:
        conn = self._connect()
        sql = """
            SELECT t.session_id, t.content, t.role, t.timestamp,
                   s.title, s.source, s.started_at, s.model,
                   snippet(turns_fts, 0, '>>>', '<<<', '...', 40) as snippet,
                   rank
            FROM turns_fts
            JOIN turns t ON t.rowid = turns_fts.rowid
            JOIN sessions s ON s.id = t.session_id
            WHERE turns_fts MATCH ?
        """
        params: list = [query]
        if source:
            sql += " AND s.source = ?"
            params.append(source)
        if tool:
            sql += " AND t.id IN (SELECT turn_id FROM tool_calls WHERE name = ?)"
            params.append(tool)
        sql += " ORDER BY rank LIMIT ?"
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_session(self, session_id: str) -> dict | None:
        conn = self._connect()
        row = conn.execute("SELECT * FROM sessions WHERE id = ? OR id LIKE ?",
                           (session_id, f"{session_id}%")).fetchone()
        conn.close()
        return dict(row) if row else None

    def get_session_turns(self, session_id: str) -> list[dict]:
        conn = self._connect()
        rows = conn.execute(
            "SELECT * FROM turns WHERE session_id = ? ORDER BY sequence_num",
            (session_id,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_tool_calls(self, session_id: str) -> list[dict]:
        conn = self._connect()
        rows = conn.execute(
            "SELECT * FROM tool_calls WHERE session_id = ? ORDER BY rowid",
            (session_id,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def needs_reindex(self, source_file: str, current_mtime: float) -> bool:
        conn = self._connect()
        row = conn.execute(
            "SELECT source_file_mtime FROM sessions WHERE source_file = ?",
            (source_file,)
        ).fetchone()
        conn.close()
        if row is None:
            return True
        return row[0] != current_mtime

    def stats(self) -> dict:
        conn = self._connect()
        total = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        turns = conn.execute("SELECT COUNT(*) FROM turns").fetchone()[0]
        sources = {}
        for row in conn.execute("SELECT source, COUNT(*) FROM sessions GROUP BY source"):
            sources[row[0]] = row[1]
        db_size = Path(self.db_path).stat().st_size if Path(self.db_path).exists() else 0
        conn.close()
        return {
            "total_sessions": total,
            "total_turns": turns,
            "sources": sources,
            "db_size_bytes": db_size,
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_index.py -v`
Expected: All 12 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/harness_recall/index.py tests/test_index.py
git commit -m "feat: SQLite index with FTS5 full-text search"
```

---

## Task 6: Config Management

**Files:**
- Create: `src/harness_recall/config.py`
- Create: `tests/test_config.py` (minimal — config is simple)

- [ ] **Step 1: Write failing test**

Create `tests/test_config.py`:

```python
from pathlib import Path
from harness_recall.config import Config


def test_default_config():
    config = Config()
    assert config.db_path.endswith("index.db")
    assert "codex" in config.source_paths
    assert "claude-code" in config.source_paths


def test_config_from_file(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text("""
[sources]
codex = ["/custom/codex/path"]
claude-code = ["/custom/claude/path"]

[index]
db_path = "/custom/index.db"
""")
    config = Config(config_file=config_file)
    assert config.db_path == "/custom/index.db"
    assert config.source_paths["codex"] == ["/custom/codex/path"]


def test_config_dir_creation(tmp_path):
    config = Config(config_dir=tmp_path / "harness-recall")
    assert Path(config.db_path).parent.exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_config.py -v`

- [ ] **Step 3: Implement config**

Create `src/harness_recall/config.py`:

```python
from __future__ import annotations

import tomllib
from pathlib import Path


DEFAULT_CONFIG_DIR = Path.home() / ".harness-recall"

DEFAULT_SOURCE_PATHS = {
    "codex": ["~/.codex/sessions/"],
    "claude-code": ["~/.claude/projects/"],
}


class Config:
    def __init__(self, config_file: Path | None = None, config_dir: Path | None = None):
        self._config_dir = config_dir or DEFAULT_CONFIG_DIR
        self._config_dir.mkdir(parents=True, exist_ok=True)

        self.source_paths: dict[str, list[str]] = dict(DEFAULT_SOURCE_PATHS)
        self.db_path: str = str(self._config_dir / "index.db")

        if config_file is None:
            config_file = self._config_dir / "config.toml"

        if config_file.exists():
            with open(config_file, "rb") as f:
                data = tomllib.load(f)
            if "sources" in data:
                for key, val in data["sources"].items():
                    self.source_paths[key] = val
            if "index" in data and "db_path" in data["index"]:
                self.db_path = data["index"]["db_path"]

    @property
    def config_dir(self) -> Path:
        return self._config_dir
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_config.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/harness_recall/config.py tests/test_config.py
git commit -m "feat: config management with TOML support"
```

---

## Task 7: Renderers (Markdown + JSON + HTML)

**Files:**
- Create: `src/harness_recall/renderers/__init__.py`
- Create: `src/harness_recall/renderers/base.py`
- Create: `src/harness_recall/renderers/markdown.py`
- Create: `src/harness_recall/renderers/json_renderer.py`
- Create: `src/harness_recall/renderers/html.py`
- Create: `templates/export.html`
- Create: `tests/test_markdown_renderer.py`
- Create: `tests/test_json_renderer.py`
- Create: `tests/test_html_renderer.py`

- [ ] **Step 1: Create renderer base and registry**

Create `src/harness_recall/renderers/base.py`:

```python
from __future__ import annotations

from abc import ABC, abstractmethod

from harness_recall.ir import Session


class BaseRenderer(ABC):
    name: str
    file_extension: str

    @abstractmethod
    def render(self, session: Session) -> str:
        """Render a session to a string in this format."""
        ...
```

Create `src/harness_recall/renderers/__init__.py`:

```python
from __future__ import annotations

from harness_recall.renderers.base import BaseRenderer

_REGISTRY: dict[str, BaseRenderer] = {}


def register_renderer(renderer: BaseRenderer) -> None:
    _REGISTRY[renderer.name] = renderer


def get_renderer(name: str) -> BaseRenderer:
    if name not in _REGISTRY:
        raise ValueError(f"Unknown renderer: {name}. Available: {list(_REGISTRY.keys())}")
    return _REGISTRY[name]


def _auto_register() -> None:
    try:
        from harness_recall.renderers import markdown  # noqa: F401
    except ImportError:
        pass
    try:
        from harness_recall.renderers import json_renderer  # noqa: F401
    except ImportError:
        pass
    try:
        from harness_recall.renderers import html  # noqa: F401
    except ImportError:
        pass


_auto_register()
```

- [ ] **Step 2: Write failing tests for Markdown renderer**

Create `tests/test_markdown_renderer.py`:

```python
from datetime import datetime, timezone

from harness_recall.ir import Session, Turn, ToolCall, TokenUsage
from harness_recall.renderers.markdown import MarkdownRenderer


def _make_session():
    return Session(
        id="test-001",
        source="codex",
        source_file="/path/file.jsonl",
        source_file_mtime=0.0,
        started_at=datetime(2026, 3, 5, 10, 0, 0, tzinfo=timezone.utc),
        ended_at=datetime(2026, 3, 5, 10, 30, 0, tzinfo=timezone.utc),
        project_dir="/Users/dev/project",
        model="gpt-5.3-codex",
        model_provider="openai",
        cli_version="0.108.0",
        git_branch="main",
        git_commit=None,
        git_repo_url=None,
        title="Fix the auth bug",
        turns=[
            Turn(id="test-001:0", role="user", content="Fix the auth bug in login.py",
                 timestamp=datetime(2026, 3, 5, 10, 0, 0, tzinfo=timezone.utc), tool_calls=[]),
            Turn(id="test-001:1", role="assistant", content="I found and fixed the bug.",
                 timestamp=datetime(2026, 3, 5, 10, 5, 0, tzinfo=timezone.utc),
                 tool_calls=[ToolCall(id="c1", name="exec_command", arguments='{"cmd":"grep expiry"}', output="42: EXPIRY=60")],
                 token_usage=TokenUsage(input_tokens=5000, output_tokens=200)),
        ],
    )


def test_render_contains_title():
    renderer = MarkdownRenderer()
    md = renderer.render(_make_session())
    assert "# Fix the auth bug" in md


def test_render_contains_metadata():
    renderer = MarkdownRenderer()
    md = renderer.render(_make_session())
    assert "codex" in md
    assert "gpt-5.3-codex" in md
    assert "2026-03-05" in md


def test_render_contains_turns():
    renderer = MarkdownRenderer()
    md = renderer.render(_make_session())
    assert "**User**" in md
    assert "Fix the auth bug in login.py" in md
    assert "**Assistant**" in md
    assert "I found and fixed the bug." in md


def test_render_contains_tool_calls():
    renderer = MarkdownRenderer()
    md = renderer.render(_make_session())
    assert "exec_command" in md
    assert "EXPIRY=60" in md


def test_render_file_extension():
    renderer = MarkdownRenderer()
    assert renderer.file_extension == ".md"
```

- [ ] **Step 3: Implement Markdown renderer**

Create `src/harness_recall/renderers/markdown.py`:

```python
from __future__ import annotations

from harness_recall.ir import Session
from harness_recall.renderers.base import BaseRenderer
from harness_recall.renderers import register_renderer


class MarkdownRenderer(BaseRenderer):
    name = "markdown"
    file_extension = ".md"

    def render(self, session: Session) -> str:
        lines: list[str] = []
        title = session.title or session.generate_title()
        lines.append(f"# {title}")
        lines.append("")

        # Metadata
        lines.append(f"**Source:** {session.source}  ")
        lines.append(f"**Date:** {session.started_at.strftime('%Y-%m-%d %H:%M UTC')}  ")
        if session.model:
            lines.append(f"**Model:** {session.model}  ")
        if session.project_dir:
            lines.append(f"**Project:** `{session.project_dir}`  ")
        if session.git_branch:
            lines.append(f"**Branch:** `{session.git_branch}`  ")
        if session.cli_version:
            lines.append(f"**CLI Version:** {session.cli_version}  ")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Turns
        for turn in session.turns:
            role_label = turn.role.capitalize()
            time_str = turn.timestamp.strftime("%H:%M")
            lines.append(f"### **{role_label}** _{time_str}_")
            lines.append("")
            if turn.content:
                lines.append(turn.content)
                lines.append("")

            if turn.reasoning:
                lines.append("<details>")
                lines.append("<summary>Thinking</summary>")
                lines.append("")
                lines.append(turn.reasoning)
                lines.append("")
                lines.append("</details>")
                lines.append("")

            for tc in turn.tool_calls:
                lines.append(f"<details>")
                lines.append(f"<summary><code>{tc.name}</code>: {_summarize_args(tc.arguments)}</summary>")
                lines.append("")
                lines.append("**Arguments:**")
                lines.append(f"```json\n{tc.arguments}\n```")
                if tc.output:
                    lines.append("**Output:**")
                    lines.append(f"```\n{tc.output}\n```")
                lines.append("</details>")
                lines.append("")

        # Footer
        lines.append("---")
        lines.append(f"*Exported by [harness-recall](https://github.com/timothydillan/harness-recall)*")
        return "\n".join(lines)


def _summarize_args(args_json: str) -> str:
    """Create a short summary of tool arguments."""
    try:
        import json
        args = json.loads(args_json)
        if isinstance(args, dict):
            if "cmd" in args:
                return f"`{args['cmd'][:60]}`"
            if "file_path" in args:
                return f"`{args['file_path']}`"
            first_val = next(iter(args.values()), "")
            return f"`{str(first_val)[:60]}`"
    except Exception:
        pass
    return args_json[:60]


register_renderer(MarkdownRenderer())
```

- [ ] **Step 4: Run Markdown tests**

Run: `python -m pytest tests/test_markdown_renderer.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Write failing tests for JSON renderer**

Create `tests/test_json_renderer.py`:

```python
import json
from datetime import datetime, timezone

from harness_recall.ir import Session, Turn
from harness_recall.renderers.json_renderer import JsonRenderer


def test_render_valid_json():
    session = Session(
        id="test", source="codex", source_file="/f.jsonl", source_file_mtime=0.0,
        started_at=datetime(2026, 3, 5, tzinfo=timezone.utc), turns=[
            Turn(id="test:0", role="user", content="hello",
                 timestamp=datetime(2026, 3, 5, tzinfo=timezone.utc), tool_calls=[]),
        ],
    )
    renderer = JsonRenderer()
    output = renderer.render(session)
    parsed = json.loads(output)
    assert parsed["id"] == "test"
    assert parsed["source"] == "codex"
    assert len(parsed["turns"]) == 1


def test_render_file_extension():
    renderer = JsonRenderer()
    assert renderer.file_extension == ".json"
```

- [ ] **Step 6: Implement JSON renderer**

Create `src/harness_recall/renderers/json_renderer.py`:

```python
from __future__ import annotations

import json

from harness_recall.ir import Session
from harness_recall.renderers.base import BaseRenderer
from harness_recall.renderers import register_renderer


class JsonRenderer(BaseRenderer):
    name = "json"
    file_extension = ".json"

    def render(self, session: Session) -> str:
        return json.dumps(session.to_dict(), indent=2, ensure_ascii=False)


register_renderer(JsonRenderer())
```

- [ ] **Step 7: Run JSON tests**

Run: `python -m pytest tests/test_json_renderer.py -v`
Expected: All 2 tests PASS

- [ ] **Step 8: Write failing tests for HTML renderer**

Create `tests/test_html_renderer.py`:

```python
from datetime import datetime, timezone

from harness_recall.ir import Session, Turn, ToolCall
from harness_recall.renderers.html import HtmlRenderer


def _make_session():
    return Session(
        id="test-001", source="codex", source_file="/f.jsonl", source_file_mtime=0.0,
        started_at=datetime(2026, 3, 5, 10, 0, 0, tzinfo=timezone.utc),
        model="gpt-5.3-codex", title="Fix the auth bug",
        turns=[
            Turn(id="test:0", role="user", content="Fix the auth bug",
                 timestamp=datetime(2026, 3, 5, 10, 0, 0, tzinfo=timezone.utc), tool_calls=[]),
            Turn(id="test:1", role="assistant", content="Fixed it.",
                 timestamp=datetime(2026, 3, 5, 10, 5, 0, tzinfo=timezone.utc),
                 tool_calls=[ToolCall(id="c1", name="Read", arguments='{"file_path":"auth.py"}', output="def login():\n    pass")]),
        ],
    )


def test_render_is_valid_html():
    renderer = HtmlRenderer()
    html = renderer.render(_make_session())
    assert "<!DOCTYPE html>" in html
    assert "</html>" in html


def test_render_contains_title():
    renderer = HtmlRenderer()
    html = renderer.render(_make_session())
    assert "Fix the auth bug" in html


def test_render_contains_turns():
    renderer = HtmlRenderer()
    html = renderer.render(_make_session())
    assert "Fix the auth bug" in html
    assert "Fixed it." in html


def test_render_contains_tool_calls_as_details():
    renderer = HtmlRenderer()
    html = renderer.render(_make_session())
    assert "<details" in html
    assert "Read" in html


def test_render_has_dark_mode_support():
    renderer = HtmlRenderer()
    html = renderer.render(_make_session())
    assert "prefers-color-scheme: dark" in html


def test_render_has_print_styles():
    renderer = HtmlRenderer()
    html = renderer.render(_make_session())
    assert "@media print" in html


def test_render_self_contained():
    """HTML should have embedded CSS, no external stylesheet links."""
    renderer = HtmlRenderer()
    html = renderer.render(_make_session())
    assert "<style>" in html
    # Only font CDNs allowed as external links
    link_count = html.count('<link rel="stylesheet"')
    assert link_count <= 1  # At most one Google Fonts link


def test_render_file_extension():
    renderer = HtmlRenderer()
    assert renderer.file_extension == ".html"
```

- [ ] **Step 9: Create Jinja2 HTML template**

Create `templates/export.html` — the full HTML template following the taste-skill design spec. This is a self-contained Jinja2 template with embedded CSS, warm stone color palette, Space Grotesk + system font stack, collapsible tool calls via `<details>`, dark mode support, print styles, and all micro-details from the design spec.

The template receives a `session` variable (the IR Session object's `to_dict()` output) and renders the full HTML page. Key elements:

- CSS custom properties for light/dark theming
- `::selection` styled to teal accent
- Custom scrollbars on `pre` blocks
- `<details><summary>` for tool calls
- Role labels as small caps
- Assistant turns with subtle background band
- Max-width 720px reading column
- Print styles that hide theme toggle and force light mode

(Full template content should be ~200 lines of HTML/CSS/Jinja2 — the implementing agent should create this following the design spec in `docs/specs/2026-04-07-harness-recall-design.md` Section "HTML Export Design".)

- [ ] **Step 10: Implement HTML renderer**

Create `src/harness_recall/renderers/html.py`:

```python
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from harness_recall.ir import Session
from harness_recall.renderers.base import BaseRenderer
from harness_recall.renderers import register_renderer


# Template directory — check multiple locations
_TEMPLATE_DIRS = [
    Path(__file__).parent.parent.parent.parent / "templates",  # development: repo root
    Path(__file__).parent / "templates",  # installed package fallback
]


class HtmlRenderer(BaseRenderer):
    name = "html"
    file_extension = ".html"

    def __init__(self):
        template_dir = None
        for d in _TEMPLATE_DIRS:
            if (d / "export.html").exists():
                template_dir = d
                break
        if template_dir is None:
            raise FileNotFoundError(
                f"Could not find templates/export.html in: {_TEMPLATE_DIRS}"
            )
        self._env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=True,
        )

    def render(self, session: Session) -> str:
        template = self._env.get_template("export.html")
        return template.render(session=session.to_dict())


register_renderer(HtmlRenderer())
```

- [ ] **Step 11: Run all renderer tests**

Run: `python -m pytest tests/test_markdown_renderer.py tests/test_json_renderer.py tests/test_html_renderer.py -v`
Expected: All 15 tests PASS

- [ ] **Step 12: Commit**

```bash
git add src/harness_recall/renderers/ templates/ tests/test_markdown_renderer.py tests/test_json_renderer.py tests/test_html_renderer.py
git commit -m "feat: Markdown, JSON, and HTML renderers with taste-informed template"
```

---

## Task 8: Rich Terminal Display

**Files:**
- Create: `src/harness_recall/display.py`
- Create: `tests/test_display.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_display.py`:

```python
from io import StringIO
from datetime import datetime, timezone

from rich.console import Console

from harness_recall.display import format_session_list, format_session_detail, format_search_results


def test_format_session_list():
    sessions = [
        {"id": "019cbc4c-568c-7b81", "source": "codex", "started_at": "2026-03-05T10:00:00+00:00",
         "model": "gpt-5.3-codex", "title": "Fix auth bug", "total_input_tokens": 5000, "total_output_tokens": 200},
    ]
    output = StringIO()
    console = Console(file=output, force_terminal=True, width=120)
    format_session_list(console, sessions)
    text = output.getvalue()
    assert "019cbc4c" in text
    assert "codex" in text
    assert "Fix auth bug" in text


def test_format_session_detail():
    session = {
        "id": "019cbc4c", "source": "codex", "started_at": "2026-03-05T10:00:00+00:00",
        "model": "gpt-5.3-codex", "title": "Fix auth bug", "project_dir": "/Users/dev/project",
        "git_branch": "main", "cli_version": "0.108.0", "ended_at": "2026-03-05T10:30:00+00:00",
        "model_provider": "openai", "agent_name": None, "agent_role": None,
        "parent_session_id": None, "git_commit": None, "git_repo_url": None,
        "total_input_tokens": 5000, "total_output_tokens": 200,
    }
    turns = [
        {"role": "user", "content": "Fix the bug", "timestamp": "2026-03-05T10:00:00+00:00",
         "reasoning": None, "id": "t:0", "sequence_num": 0},
        {"role": "assistant", "content": "Fixed it.", "timestamp": "2026-03-05T10:05:00+00:00",
         "reasoning": None, "id": "t:1", "sequence_num": 1},
    ]
    tool_calls = []
    output = StringIO()
    console = Console(file=output, force_terminal=True, width=120)
    format_session_detail(console, session, turns, tool_calls, full=False)
    text = output.getvalue()
    assert "Fix auth bug" in text
    assert "Fix the bug" in text
    assert "Fixed it." in text


def test_format_search_results():
    results = [
        {"session_id": "019cbc4c", "source": "codex", "started_at": "2026-03-05T10:00:00+00:00",
         "title": "Fix auth bug", "snippet": "...the >>>auth<<< middleware...", "model": "gpt-5.3"},
    ]
    output = StringIO()
    console = Console(file=output, force_terminal=True, width=120)
    format_search_results(console, results)
    text = output.getvalue()
    assert "019cbc4c" in text
    assert "auth" in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_display.py -v`

- [ ] **Step 3: Implement display module**

Create `src/harness_recall/display.py`:

```python
from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.markdown import Markdown
from rich import box


ROLE_STYLES = {
    "user": "bold cyan",
    "assistant": "bold green",
    "system": "bold yellow",
}


def format_session_list(console: Console, sessions: list[dict]) -> None:
    if not sessions:
        console.print("[dim]No sessions found.[/dim]")
        return

    table = Table(box=box.SIMPLE_HEAVY, show_edge=False, pad_edge=False)
    table.add_column("ID", style="dim", max_width=10)
    table.add_column("Source", style="magenta")
    table.add_column("Date", style="cyan")
    table.add_column("Model", style="dim")
    table.add_column("Title", max_width=60)

    for s in sessions:
        short_id = s["id"][:8]
        date = s["started_at"][:10] if s.get("started_at") else ""
        model = s.get("model") or ""
        if len(model) > 20:
            model = model[:17] + "..."
        title = s.get("title") or ""
        if len(title) > 60:
            title = title[:57] + "..."
        table.add_row(short_id, s.get("source", ""), date, model, title)

    console.print(table)


def format_session_detail(console: Console, session: dict, turns: list[dict],
                          tool_calls: list[dict], full: bool = False) -> None:
    # Header panel
    title = session.get("title") or session["id"]
    meta_lines = []
    meta_lines.append(f"[dim]Source:[/dim] {session['source']}")
    meta_lines.append(f"[dim]Date:[/dim] {session.get('started_at', '')[:19]}")
    if session.get("model"):
        meta_lines.append(f"[dim]Model:[/dim] {session['model']}")
    if session.get("project_dir"):
        meta_lines.append(f"[dim]Project:[/dim] {session['project_dir']}")
    if session.get("git_branch"):
        meta_lines.append(f"[dim]Branch:[/dim] {session['git_branch']}")

    console.print(Panel(
        "\n".join(meta_lines),
        title=f"[bold]{title}[/bold]",
        border_style="dim",
        padding=(1, 2),
    ))
    console.print()

    # Build tool call lookup by turn_id
    tc_by_turn: dict[str, list[dict]] = {}
    for tc in tool_calls:
        tc_by_turn.setdefault(tc["turn_id"], []).append(tc)

    # Turns
    for turn in turns:
        role = turn["role"]
        style = ROLE_STYLES.get(role, "")
        ts = turn.get("timestamp", "")[:16].replace("T", " ")

        console.print(f" [{style}]{role.capitalize()}[/{style}]  [dim]{ts}[/dim]")
        if turn.get("content"):
            console.print(Markdown(turn["content"]), style="  ")
        console.print()

        if full:
            turn_tcs = tc_by_turn.get(turn["id"], [])
            for tc in turn_tcs:
                summary = f"[dim]{tc['name']}[/dim]"
                console.print(Panel(
                    f"[dim]Args:[/dim] {tc.get('arguments', '')[:200]}\n"
                    f"[dim]Output:[/dim] {(tc.get('output') or '')[:500]}",
                    title=summary,
                    border_style="dim",
                    padding=(0, 1),
                ))
                console.print()


def format_search_results(console: Console, results: list[dict]) -> None:
    if not results:
        console.print("[dim]No results found.[/dim]")
        return

    seen_sessions = set()
    for r in results:
        sid = r["session_id"]
        if sid in seen_sessions:
            continue
        seen_sessions.add(sid)

        short_id = sid[:8]
        source = r.get("source", "")
        date = r.get("started_at", "")[:10]
        title = r.get("title") or ""
        snippet = r.get("snippet", "")
        # Replace FTS markers with rich markup
        snippet = snippet.replace(">>>", "[bold yellow]").replace("<<<", "[/bold yellow]")

        console.print(f"  [dim]{short_id}[/dim]  [magenta]{source}[/magenta]  [cyan]{date}[/cyan]  {title}")
        console.print(f"    {snippet}")
        console.print()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_display.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/harness_recall/display.py tests/test_display.py
git commit -m "feat: rich terminal display for list, show, and search"
```

---

## Task 9: CLI Commands

**Files:**
- Create: `src/harness_recall/cli.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_cli.py`:

```python
from click.testing import CliRunner

from harness_recall.cli import main


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "harness-recall" in result.output.lower() or "hrc" in result.output.lower()


def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_cli_list_empty(tmp_path):
    runner = CliRunner()
    result = runner.invoke(main, ["list", "--config-dir", str(tmp_path)])
    assert result.exit_code == 0


def test_cli_search_empty(tmp_path):
    runner = CliRunner()
    result = runner.invoke(main, ["search", "test query", "--config-dir", str(tmp_path)])
    assert result.exit_code == 0


def test_cli_index_stats(tmp_path):
    runner = CliRunner()
    result = runner.invoke(main, ["index", "--stats", "--config-dir", str(tmp_path)])
    assert result.exit_code == 0
    assert "0" in result.output  # 0 sessions


def test_cli_show_not_found(tmp_path):
    runner = CliRunner()
    result = runner.invoke(main, ["show", "nonexistent", "--config-dir", str(tmp_path)])
    assert result.exit_code != 0 or "not found" in result.output.lower()


def test_cli_export_not_found(tmp_path):
    runner = CliRunner()
    result = runner.invoke(main, ["export", "nonexistent", "--config-dir", str(tmp_path)])
    assert result.exit_code != 0 or "not found" in result.output.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_cli.py -v`

- [ ] **Step 3: Implement CLI**

Create `src/harness_recall/cli.py`:

```python
from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from harness_recall import __version__
from harness_recall.config import Config
from harness_recall.index import SessionIndex
from harness_recall.parsers import get_all_parsers
from harness_recall.renderers import get_renderer
from harness_recall.display import format_session_list, format_session_detail, format_search_results

console = Console()


def _get_config(config_dir: str | None) -> Config:
    if config_dir:
        return Config(config_dir=Path(config_dir))
    return Config()


def _get_index(config: Config) -> SessionIndex:
    return SessionIndex(config.db_path)


def _auto_index(config: Config, index: SessionIndex) -> int:
    """Index new/changed sessions. Returns count of newly indexed sessions."""
    parsers = get_all_parsers()
    count = 0
    for name, parser in parsers.items():
        paths = config.source_paths.get(name, parser.default_paths)
        files = parser.discover(paths=paths)
        for f in files:
            if index.needs_reindex(str(f), f.stat().st_mtime):
                try:
                    session = parser.parse(f)
                    index.add_session(session)
                    count += 1
                except Exception as e:
                    console.print(f"[dim red]Skipped {f.name}: {e}[/dim red]")
    return count


@click.group()
@click.version_option(__version__, prog_name="harness-recall")
def main():
    """harness-recall (hrc) - Universal CLI for AI coding session export and search."""
    pass


@main.command()
@click.option("--source", help="Filter by source (codex, claude-code)")
@click.option("--after", help="Show sessions after date (YYYY-MM-DD)")
@click.option("--project", help="Filter by project directory")
@click.option("--limit", default=25, help="Max results")
@click.option("--config-dir", hidden=True, help="Override config directory")
def list(source, after, project, limit, config_dir):
    """List all indexed sessions."""
    config = _get_config(config_dir)
    index = _get_index(config)

    # Auto-index if needed
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                  console=console, transient=True) as progress:
        progress.add_task("Checking for new sessions...", total=None)
        new = _auto_index(config, index)
    if new:
        console.print(f"[dim]Indexed {new} new session(s).[/dim]")

    sessions = index.list_sessions(source=source, after=after, project=project, limit=limit)
    format_session_list(console, sessions)


@main.command()
@click.argument("query")
@click.option("--source", help="Filter by source")
@click.option("--tool", help="Filter by tool name")
@click.option("--limit", default=25, help="Max results")
@click.option("--config-dir", hidden=True, help="Override config directory")
def search(query, source, tool, limit, config_dir):
    """Full-text search across all sessions."""
    config = _get_config(config_dir)
    index = _get_index(config)
    _auto_index(config, index)
    results = index.search(query, source=source, tool=tool, limit=limit)
    format_search_results(console, results)


@main.command()
@click.argument("session_id")
@click.option("--full", is_flag=True, help="Show tool call details")
@click.option("--turns", help="Show specific turns (e.g., 1-5)")
@click.option("--config-dir", hidden=True, help="Override config directory")
def show(session_id, full, turns, config_dir):
    """Show a session in the terminal."""
    config = _get_config(config_dir)
    index = _get_index(config)
    _auto_index(config, index)

    session = index.get_session(session_id)
    if not session:
        console.print(f"[red]Session not found: {session_id}[/red]")
        raise SystemExit(1)

    turn_rows = index.get_session_turns(session["id"])
    tool_calls = index.get_tool_calls(session["id"])

    if turns:
        # Parse turn range like "1-5"
        parts = turns.split("-")
        start = int(parts[0]) - 1
        end = int(parts[1]) if len(parts) > 1 else start + 1
        turn_rows = turn_rows[start:end]

    format_session_detail(console, session, turn_rows, tool_calls, full=full)


@main.command()
@click.argument("session_id", required=False)
@click.option("--format", "fmt", default="markdown", type=click.Choice(["markdown", "html", "json"]))
@click.option("-o", "--output", "output_dir", help="Output directory")
@click.option("--all", "export_all", is_flag=True, help="Export all sessions")
@click.option("--source", help="Export sessions from specific source")
@click.option("--config-dir", hidden=True, help="Override config directory")
def export(session_id, fmt, output_dir, export_all, source, config_dir):
    """Export session(s) to Markdown, HTML, or JSON."""
    config = _get_config(config_dir)
    index = _get_index(config)
    _auto_index(config, index)
    renderer = get_renderer(fmt)

    if not session_id and not export_all and not source:
        console.print("[red]Provide a session ID, --all, or --source.[/red]")
        raise SystemExit(1)

    out_dir = Path(output_dir) if output_dir else Path.cwd()
    out_dir.mkdir(parents=True, exist_ok=True)

    if export_all or source:
        sessions = index.list_sessions(source=source, limit=10000)
        if not sessions:
            console.print("[dim]No sessions to export.[/dim]")
            return
        parsers = get_all_parsers()
        with Progress(console=console) as progress:
            task = progress.add_task("Exporting...", total=len(sessions))
            for s in sessions:
                _export_one(s, parsers, renderer, out_dir)
                progress.advance(task)
        console.print(f"[green]Exported {len(sessions)} session(s) to {out_dir}[/green]")
    else:
        session_meta = index.get_session(session_id)
        if not session_meta:
            console.print(f"[red]Session not found: {session_id}[/red]")
            raise SystemExit(1)
        parsers = get_all_parsers()
        filepath = _export_one(session_meta, parsers, renderer, out_dir)
        console.print(f"[green]Exported to {filepath}[/green]")


def _export_one(session_meta, parsers, renderer, out_dir):
    """Re-parse source file and export via renderer."""
    source_file = Path(session_meta["source_file"])
    parser = parsers.get(session_meta["source"])
    if not parser or not source_file.exists():
        console.print(f"[yellow]Skipped {session_meta['id']}: source file not found[/yellow]")
        return None
    session = parser.parse(source_file)
    content = renderer.render(session)
    safe_id = session.id[:8]
    filename = f"{safe_id}-{session.source}{renderer.file_extension}"
    filepath = out_dir / filename
    filepath.write_text(content, encoding="utf-8")
    return filepath


@main.command()
@click.option("--rebuild", is_flag=True, help="Full re-index")
@click.option("--stats", is_flag=True, help="Show index statistics")
@click.option("--config-dir", hidden=True, help="Override config directory")
def index(rebuild, stats, config_dir):
    """Manage the session index."""
    config = _get_config(config_dir)
    idx = _get_index(config)

    if stats:
        s = idx.stats()
        console.print(f"Sessions: {s['total_sessions']}")
        console.print(f"Turns: {s['total_turns']}")
        for src, count in s.get("sources", {}).items():
            console.print(f"  {src}: {count}")
        console.print(f"DB size: {s['db_size_bytes'] / 1024:.1f} KB")
        return

    if rebuild:
        # Delete and recreate
        db = Path(config.db_path)
        if db.exists():
            db.unlink()
        idx = _get_index(config)

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                  console=console) as progress:
        progress.add_task("Indexing sessions...", total=None)
        new = _auto_index(config, idx)
    console.print(f"[green]Indexed {new} session(s).[/green]")


@main.command()
@click.option("--config-dir", hidden=True, help="Override config directory")
def config(config_dir):
    """Show current configuration."""
    cfg = _get_config(config_dir)
    console.print(f"[bold]Config directory:[/bold] {cfg.config_dir}")
    console.print(f"[bold]Database:[/bold] {cfg.db_path}")
    console.print(f"[bold]Source paths:[/bold]")
    for name, paths in cfg.source_paths.items():
        for p in paths:
            console.print(f"  {name}: {p}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_cli.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/harness_recall/cli.py tests/test_cli.py
git commit -m "feat: CLI commands — list, search, show, export, index, config"
```

---

## Task 10: Integration Test with Real Fixtures

**Files:**
- Modify: `tests/test_cli.py` (add integration tests)

- [ ] **Step 1: Add integration test that indexes and searches fixtures**

Add to `tests/test_cli.py`:

```python
def test_full_workflow(tmp_path, fixtures_dir):
    """Integration test: index fixtures → list → search → export."""
    config_dir = tmp_path / "config"
    export_dir = tmp_path / "exports"

    runner = CliRunner()

    # Override source paths to point at fixtures
    config_file = config_dir / "config.toml"
    config_dir.mkdir(parents=True)
    config_file.write_text(f"""
[sources]
codex = ["{fixtures_dir}"]
claude-code = ["{fixtures_dir}"]
""")

    # Index
    result = runner.invoke(main, ["index", "--config-dir", str(config_dir)])
    assert result.exit_code == 0

    # List
    result = runner.invoke(main, ["list", "--config-dir", str(config_dir)])
    assert result.exit_code == 0

    # Search
    result = runner.invoke(main, ["search", "auth", "--config-dir", str(config_dir)])
    assert result.exit_code == 0

    # Index stats
    result = runner.invoke(main, ["index", "--stats", "--config-dir", str(config_dir)])
    assert result.exit_code == 0
```

- [ ] **Step 2: Run integration test**

Run: `python -m pytest tests/test_cli.py::test_full_workflow -v`
Expected: PASS

- [ ] **Step 3: Run full test suite one final time**

Run: `python -m pytest tests/ -v --tb=short`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_cli.py
git commit -m "test: add integration test for full index → search → export workflow"
```

---

## Task 11: README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write README**

Create `README.md` with:
- Project name and one-line description
- Installation (`pip install harness-recall` / `pipx install harness-recall`)
- Quick start (3 commands: `hrc list`, `hrc search`, `hrc export`)
- Supported sources (Codex, Claude Code)
- All CLI commands with examples
- Export format examples
- How to add a new parser (link to `docs/adding-a-parser.md` — create this too)
- License (MIT)
- Contributing section

The README should be direct, developer-focused, no fluff. Show real CLI output examples.

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add README with install, usage, and contribution guide"
```

---

## Dependency Graph

```
Task 1 (Scaffolding + IR) ──┬── Task 3 (Codex Parser) ──┐
                             │                             │
                             ├── Task 4 (Claude Parser) ──┤
                             │                             │
                             ├── Task 2 (Parser Base) ─────┤
                             │                             │
                             ├── Task 5 (Index) ───────────┤
                             │                             │
                             ├── Task 6 (Config) ──────────┤
                             │                             ├── Task 9 (CLI) ── Task 10 (Integration)
                             ├── Task 7 (Renderers) ───────┤
                             │                             │
                             └── Task 8 (Display) ─────────┘
                                                           │
                                                           └── Task 11 (README)
```

**Parallelizable after Task 1+2:** Tasks 3, 4, 5, 6, 7, 8 can all run in parallel.
**Sequential:** Task 9 depends on all of 3-8. Task 10 depends on 9. Task 11 depends on 10.
