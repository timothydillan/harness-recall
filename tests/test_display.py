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
