from pathlib import Path
from harness_recall.config import Config


def test_default_config():
    config = Config()
    assert config.db_path.endswith("index.db")
    assert "codex" in config.source_paths
    assert "claude-code" in config.source_paths


def test_config_from_file(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text("""
[sources]
codex = ["/custom/codex/path"]
claude-code = ["/custom/claude/path"]

[index]
db_path = "/custom/index.db"
""")
    config = Config(config_file=config_file)
    assert config.db_path == "/custom/index.db"
    assert config.source_paths["codex"] == ["/custom/codex/path"]


def test_config_dir_creation(tmp_path):
    config = Config(config_dir=tmp_path / "harness-recall")
    assert Path(config.db_path).parent.exists()
