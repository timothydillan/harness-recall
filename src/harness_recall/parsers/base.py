from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from harness_recall.ir import Session


class BaseParser(ABC):
    """Base class for all session parsers."""

    name: str
    default_paths: list[str]
    file_pattern: str

    @abstractmethod
    def parse(self, file_path: Path) -> Session:
        """Parse a single source file into an IR Session."""
        ...

    def discover(self, paths: list[str] | None = None) -> list[Path]:
        """Find all session files in given or default paths."""
        search_paths = paths or self.default_paths
        results = []
        for p in search_paths:
            base = Path(p).expanduser()
            if base.exists():
                results.extend(sorted(base.glob(self.file_pattern)))
        return results
