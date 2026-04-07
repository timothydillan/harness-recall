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
