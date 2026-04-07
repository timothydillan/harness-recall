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
