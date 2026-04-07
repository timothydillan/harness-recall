from __future__ import annotations

from abc import ABC, abstractmethod

from harness_recall.ir import Session


class BaseRenderer(ABC):
    name: str
    file_extension: str

    @abstractmethod
    def render(self, session: Session) -> str:
        """Render a session to a string in this format."""
        ...
