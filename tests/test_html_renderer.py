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
