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
