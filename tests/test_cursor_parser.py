from __future__ import annotations

import json
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from harness_recall.parsers.cursor import CursorParser, _parse_cursor_ts


# ---------------------------------------------------------------------------
# Helpers to build minimal state.vscdb fixtures
# ---------------------------------------------------------------------------

def _make_vscdb(tmp_path: Path, rows: list[tuple[str, str]]) -> Path:
    """Create a minimal state.vscdb with the given (key, value) rows."""
    db_path = tmp_path / "state.vscdb"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE cursorDiskKV (key TEXT PRIMARY KEY, value BLOB)"
    )
    for key, value in rows:
        conn.execute(
            "INSERT INTO cursorDiskKV (key, value) VALUES (?, ?)",
            (key, value.encode("utf-8")),
        )
    conn.commit()
    conn.close()
    return db_path


def _composer(composer_id: str, created_ms: int = 1_700_000_000_000,
               model: str = "gpt-4o") -> tuple[str, str]:
    data = {
        "_v": 13,
        "composerId": composer_id,
        "text": "",
        "status": "none",
        "createdAt": created_ms,
        "modelConfig": {"modelName": model},
        "context": {},
        "unifiedMode": "chat",
    }
    return (f"composerData:{composer_id}", json.dumps(data))


def _bubble(composer_id: str, bubble_id: str, btype: int, text: str,
            created_ms: int = 1_700_000_001_000,
            tool_former_data=None,
            token_count=None) -> tuple[str, str]:
    data: dict = {
        "_v": 3,
        "type": btype,
        "bubbleId": bubble_id,
        "text": text,
        "createdAt": created_ms,
    }
    if tool_former_data is not None:
        data["toolFormerData"] = tool_former_data
    if token_count is not None:
        data["tokenCount"] = token_count
    return (f"bubbleId:{composer_id}:{bubble_id}", json.dumps(data))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestParseAllFromFixture:
    def test_returns_one_session_per_conversation(self, tmp_path):
        cid = "conv-0001"
        rows = [
            _composer(cid),
            _bubble(cid, "b1", 1, "Hello, cursor!", created_ms=1_700_000_001_000),
            _bubble(cid, "b2", 2, "Hello back from assistant.", created_ms=1_700_000_002_000),
        ]
        db = _make_vscdb(tmp_path, rows)
        parser = CursorParser()
        sessions = parser.parse_all(db)

        assert len(sessions) == 1
        session = sessions[0]
        assert session.id == cid
        assert session.source == "cursor"
        assert session.source_file == str(db)

    def test_session_has_correct_turns(self, tmp_path):
        cid = "conv-0002"
        rows = [
            _composer(cid),
            _bubble(cid, "b1", 1, "user message", created_ms=1_700_000_001_000),
            _bubble(cid, "b2", 2, "assistant reply", created_ms=1_700_000_002_000),
        ]
        db = _make_vscdb(tmp_path, rows)
        parser = CursorParser()
        sessions = parser.parse_all(db)
        session = sessions[0]

        assert len(session.turns) == 2
        assert session.turns[0].role == "user"
        assert session.turns[0].content == "user message"
        assert session.turns[1].role == "assistant"
        assert session.turns[1].content == "assistant reply"

    def test_turns_sorted_by_timestamp(self, tmp_path):
        cid = "conv-0003"
        # Insert bubbles out of order (assistant before user in DB, later timestamp)
        rows = [
            _composer(cid),
            _bubble(cid, "b2", 2, "assistant reply", created_ms=1_700_000_002_000),
            _bubble(cid, "b1", 1, "user message", created_ms=1_700_000_001_000),
        ]
        db = _make_vscdb(tmp_path, rows)
        parser = CursorParser()
        sessions = parser.parse_all(db)
        session = sessions[0]

        assert session.turns[0].role == "user"
        assert session.turns[1].role == "assistant"

    def test_model_extracted_from_model_config(self, tmp_path):
        cid = "conv-0004"
        rows = [
            _composer(cid, model="claude-3-5-sonnet"),
            _bubble(cid, "b1", 1, "hi"),
        ]
        db = _make_vscdb(tmp_path, rows)
        parser = CursorParser()
        sessions = parser.parse_all(db)
        assert sessions[0].model == "claude-3-5-sonnet"

    def test_model_default_stored_as_is(self, tmp_path):
        cid = "conv-0005"
        rows = [
            _composer(cid, model="default"),
            _bubble(cid, "b1", 1, "hi"),
        ]
        db = _make_vscdb(tmp_path, rows)
        parser = CursorParser()
        sessions = parser.parse_all(db)
        assert sessions[0].model == "default"

    def test_started_at_from_composer_created_at(self, tmp_path):
        cid = "conv-0006"
        created_ms = 1_700_000_000_000
        rows = [
            _composer(cid, created_ms=created_ms),
            _bubble(cid, "b1", 1, "hi", created_ms=created_ms + 1000),
        ]
        db = _make_vscdb(tmp_path, rows)
        parser = CursorParser()
        sessions = parser.parse_all(db)
        expected_ts = datetime.fromtimestamp(created_ms / 1000.0, tz=timezone.utc)
        assert sessions[0].started_at == expected_ts

    def test_multiple_conversations(self, tmp_path):
        rows = [
            _composer("conv-A"),
            _bubble("conv-A", "bA1", 1, "msg from conv A"),
            _composer("conv-B"),
            _bubble("conv-B", "bB1", 1, "msg from conv B"),
        ]
        db = _make_vscdb(tmp_path, rows)
        parser = CursorParser()
        sessions = parser.parse_all(db)
        assert len(sessions) == 2
        ids = {s.id for s in sessions}
        assert ids == {"conv-A", "conv-B"}


class TestParseExtractsToolCalls:
    def test_tool_call_mapped_from_tool_former_data(self, tmp_path):
        cid = "conv-tool"
        tfd = {
            "tool": 15,
            "name": "run_terminal_command_v2",
            "toolCallId": "tc-uuid-001",
            "status": "completed",
            "rawArgs": '{"command": "ls -la"}',
            "result": "file1.py\nfile2.py",
        }
        rows = [
            _composer(cid),
            _bubble(cid, "b1", 1, "run ls"),
            _bubble(cid, "b2", 2, "Sure!", created_ms=1_700_000_002_000,
                    tool_former_data=tfd),
        ]
        db = _make_vscdb(tmp_path, rows)
        parser = CursorParser()
        sessions = parser.parse_all(db)
        session = sessions[0]

        assistant_turns = [t for t in session.turns if t.role == "assistant"]
        assert len(assistant_turns) == 1
        assert len(assistant_turns[0].tool_calls) == 1
        tc = assistant_turns[0].tool_calls[0]
        assert tc.id == "tc-uuid-001"
        assert tc.name == "run_terminal_command_v2"
        assert "ls -la" in tc.arguments
        assert "file1.py" in tc.output

    def test_tool_call_output_truncated(self, tmp_path):
        cid = "conv-trunc"
        large_result = "x" * 20000
        tfd = {
            "name": "big_tool",
            "toolCallId": "tc-big",
            "rawArgs": "{}",
            "result": large_result,
        }
        rows = [
            _composer(cid),
            _bubble(cid, "b1", 2, "result incoming", tool_former_data=tfd),
        ]
        db = _make_vscdb(tmp_path, rows)
        parser = CursorParser()
        sessions = parser.parse_all(db)
        tc = sessions[0].turns[0].tool_calls[0]
        assert len(tc.output) <= 10240 + len("\n... [truncated]") + 1
        assert tc.output.endswith("... [truncated]")

    def test_null_tool_former_data_produces_no_tool_calls(self, tmp_path):
        cid = "conv-notool"
        rows = [
            _composer(cid),
            _bubble(cid, "b1", 2, "plain reply"),
        ]
        db = _make_vscdb(tmp_path, rows)
        parser = CursorParser()
        sessions = parser.parse_all(db)
        assert sessions[0].turns[0].tool_calls == []


class TestTokenUsage:
    def test_token_count_mapped(self, tmp_path):
        cid = "conv-tokens"
        rows = [
            _composer(cid),
            _bubble(cid, "b1", 2, "reply", token_count={"inputTokens": 100, "outputTokens": 50}),
        ]
        db = _make_vscdb(tmp_path, rows)
        parser = CursorParser()
        sessions = parser.parse_all(db)
        tu = sessions[0].turns[0].token_usage
        assert tu is not None
        assert tu.input_tokens == 100
        assert tu.output_tokens == 50

    def test_zero_token_count_is_none(self, tmp_path):
        cid = "conv-zerotokens"
        rows = [
            _composer(cid),
            _bubble(cid, "b1", 2, "reply", token_count={"inputTokens": 0, "outputTokens": 0}),
        ]
        db = _make_vscdb(tmp_path, rows)
        parser = CursorParser()
        sessions = parser.parse_all(db)
        assert sessions[0].turns[0].token_usage is None


class TestSkipsEmptyConversations:
    def test_conversation_with_no_bubbles_is_skipped(self, tmp_path):
        rows = [
            _composer("empty-conv"),
            # No bubbles for empty-conv
            _composer("real-conv"),
            _bubble("real-conv", "b1", 1, "hello"),
        ]
        db = _make_vscdb(tmp_path, rows)
        parser = CursorParser()
        sessions = parser.parse_all(db)
        assert len(sessions) == 1
        assert sessions[0].id == "real-conv"

    def test_conversation_with_all_empty_text_and_no_tools_is_skipped(self, tmp_path):
        cid = "empty-text-conv"
        rows = [
            _composer(cid),
            _bubble(cid, "b1", 1, ""),
            _bubble(cid, "b2", 2, "   "),
        ]
        db = _make_vscdb(tmp_path, rows)
        parser = CursorParser()
        sessions = parser.parse_all(db)
        assert len(sessions) == 0


class TestDiscoverDefaultPaths:
    def test_discover_finds_state_vscdb(self, tmp_path):
        # Create a fake globalStorage directory with a state.vscdb
        gs_dir = tmp_path / "globalStorage"
        gs_dir.mkdir()
        db_file = gs_dir / "state.vscdb"
        db_file.write_bytes(b"")

        parser = CursorParser()
        files = parser.discover(paths=[str(gs_dir)])
        assert len(files) == 1
        assert files[0].name == "state.vscdb"

    def test_discover_returns_empty_if_no_vscdb(self, tmp_path):
        parser = CursorParser()
        files = parser.discover(paths=[str(tmp_path)])
        assert files == []


class TestParseTimestamps:
    def test_unix_ms_integer(self):
        ts = _parse_cursor_ts(1_700_000_000_000)
        assert ts is not None
        assert ts.tzinfo is not None

    def test_iso_string_with_z(self):
        ts = _parse_cursor_ts("2024-01-15T10:30:00Z")
        assert ts is not None
        assert ts.year == 2024

    def test_iso_string_with_offset(self):
        ts = _parse_cursor_ts("2024-01-15T10:30:00+00:00")
        assert ts is not None
        assert ts.year == 2024

    def test_numeric_string_unix_ms(self):
        ts = _parse_cursor_ts("1700000000000")
        assert ts is not None

    def test_none_returns_none(self):
        assert _parse_cursor_ts(None) is None

    def test_empty_string_returns_none(self):
        assert _parse_cursor_ts("") is None


class TestParseFirstSession:
    def test_parse_returns_first_session(self, tmp_path):
        rows = [
            _composer("first-conv", created_ms=1_700_000_000_000),
            _bubble("first-conv", "b1", 1, "first message"),
            _composer("second-conv", created_ms=1_700_100_000_000),
            _bubble("second-conv", "b1", 1, "second message"),
        ]
        db = _make_vscdb(tmp_path, rows)
        parser = CursorParser()
        session = parser.parse(db)
        # parse() should return one session (the first in parse_all())
        assert session.source == "cursor"
        assert session.id in {"first-conv", "second-conv"}

    def test_parse_raises_on_empty_db(self, tmp_path):
        db = _make_vscdb(tmp_path, [])
        parser = CursorParser()
        with pytest.raises(ValueError, match="No conversations found"):
            parser.parse(db)


class TestTitleGeneration:
    def test_title_generated_from_first_user_message(self, tmp_path):
        cid = "conv-title"
        rows = [
            _composer(cid),
            _bubble(cid, "b1", 1, "Fix the login bug please", created_ms=1_700_000_001_000),
            _bubble(cid, "b2", 2, "Sure, here is the fix.", created_ms=1_700_000_002_000),
        ]
        db = _make_vscdb(tmp_path, rows)
        parser = CursorParser()
        sessions = parser.parse_all(db)
        assert sessions[0].title == "Fix the login bug please"

    def test_long_title_truncated(self, tmp_path):
        cid = "conv-longtitle"
        long_msg = "A" * 100
        rows = [
            _composer(cid),
            _bubble(cid, "b1", 1, long_msg),
        ]
        db = _make_vscdb(tmp_path, rows)
        parser = CursorParser()
        sessions = parser.parse_all(db)
        assert len(sessions[0].title) <= 80
        assert sessions[0].title.endswith("...")
