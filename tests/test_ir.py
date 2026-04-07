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
