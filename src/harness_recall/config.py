from __future__ import annotations

import tomllib
from pathlib import Path


DEFAULT_CONFIG_DIR = Path.home() / ".harness-recall"

DEFAULT_SOURCE_PATHS = {
    "codex": ["~/.codex/sessions/"],
    "claude-code": ["~/.claude/projects/"],
}


class Config:
    def __init__(self, config_file: Path | None = None, config_dir: Path | None = None):
        self._config_dir = config_dir or DEFAULT_CONFIG_DIR
        self._config_dir.mkdir(parents=True, exist_ok=True)

        self.source_paths: dict[str, list[str]] = dict(DEFAULT_SOURCE_PATHS)
        self.db_path: str = str(self._config_dir / "index.db")

        if config_file is None:
            config_file = self._config_dir / "config.toml"

        if config_file.exists():
            with open(config_file, "rb") as f:
                data = tomllib.load(f)
            if "sources" in data:
                for key, val in data["sources"].items():
                    self.source_paths[key] = val
            if "index" in data and "db_path" in data["index"]:
                self.db_path = data["index"]["db_path"]

    @property
    def config_dir(self) -> Path:
        return self._config_dir
