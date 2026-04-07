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
