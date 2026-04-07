from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup, escape

from harness_recall.ir import Session
from harness_recall.renderers.base import BaseRenderer
from harness_recall.renderers import register_renderer


def nl2br(value):
    """Jinja2 filter: escape value and replace newlines with <br> tags."""
    if not value:
        return ""
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
        self._env.filters['nl2br'] = nl2br

    def render(self, session: Session) -> str:
        template = self._env.get_template("export.html")
        return template.render(session=session.to_dict())


register_renderer(HtmlRenderer())
