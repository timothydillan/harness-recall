from __future__ import annotations

import json

from harness_recall.ir import Session
from harness_recall.renderers.base import BaseRenderer
from harness_recall.renderers import register_renderer


class JsonRenderer(BaseRenderer):
    name = "json"
    file_extension = ".json"

    def render(self, session: Session) -> str:
        return json.dumps(session.to_dict(), indent=2, ensure_ascii=False)


register_renderer(JsonRenderer())
