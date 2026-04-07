from __future__ import annotations

from pathlib import Path

import mistune
from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup, escape

from harness_recall.ir import Session
from harness_recall.renderers.base import BaseRenderer
from harness_recall.renderers import register_renderer


# ---------------------------------------------------------------------------
# Markdown renderer (mistune 3.x) with full formatting support
# ---------------------------------------------------------------------------

_md = mistune.create_markdown(
    plugins=["strikethrough", "table", "task_lists", "footnotes"],
    escape=True,  # Escape raw HTML in input (XSS protection)
)


def render_markdown(value: str | None) -> Markup:
    """Jinja2 filter: render Markdown to HTML via mistune.

    - Handles code blocks, inline code, bold, italic, strikethrough
    - Handles headings, lists (ordered, unordered, task lists), blockquotes
    - Handles tables, links, images, horizontal rules, footnotes
    - Escapes raw HTML in input to prevent XSS
    - Returns Markup so Jinja2 doesn't double-escape the output
    """
    if not value:
        return Markup("")
    html = _md(value)
    return Markup(html)


def nl2br(value: str | None) -> Markup:
    """Jinja2 filter: escape value and replace newlines with <br> tags.
    Used for tool call output and other pre-formatted text."""
    if not value:
        return Markup("")
    return Markup(escape(value).replace('\n', Markup('<br>\n')))


# Template directory
_TEMPLATE_DIRS = [
    Path(__file__).parent.parent / "templates",  # inside package: src/harness_recall/templates/
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
        self._env.filters['render_markdown'] = render_markdown
        self._env.filters['nl2br'] = nl2br

    def render(self, session: Session) -> str:
        template = self._env.get_template("export.html")
        return template.render(session=session.to_dict())


register_renderer(HtmlRenderer())
