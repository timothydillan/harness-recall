from pathlib import Path
from unittest.mock import patch

from harness_recall.config import Config, _get_default_source_paths


def test_default_config():
    config = Config()
    assert config.db_path.endswith("index.db")
    assert "codex" in config.source_paths
    assert "claude-code" in config.source_paths
    assert "cursor" in config.source_paths


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


class TestPlatformPaths:
    """Test that _get_default_source_paths returns correct paths per platform."""

    def test_macos_cursor_path(self):
        with patch("harness_recall.config.sys") as mock_sys:
            mock_sys.platform = "darwin"
            paths = _get_default_source_paths()
        assert paths["cursor"] == [
            "~/Library/Application Support/Cursor/User/globalStorage/"
        ]

    def test_linux_cursor_path(self):
        with patch("harness_recall.config.sys") as mock_sys:
            mock_sys.platform = "linux"
            paths = _get_default_source_paths()
        assert paths["cursor"] == ["~/.config/Cursor/User/globalStorage/"]

    def test_windows_cursor_path_with_appdata(self):
        with (
            patch("harness_recall.config.sys") as mock_sys,
            patch("harness_recall.config.os") as mock_os,
        ):
            mock_sys.platform = "win32"
            mock_os.environ.get.return_value = "C:\\Users\\dev\\AppData\\Roaming"
            paths = _get_default_source_paths()
        cursor_path = paths["cursor"][0]
        assert "Cursor" in cursor_path
        assert "globalStorage" in cursor_path
        assert cursor_path.startswith("C:\\Users\\dev\\AppData\\Roaming")

    def test_windows_cursor_path_fallback_no_appdata(self):
        with (
            patch("harness_recall.config.sys") as mock_sys,
            patch("harness_recall.config.os") as mock_os,
        ):
            mock_sys.platform = "win32"
            mock_os.environ.get.return_value = str(
                Path.home() / "AppData" / "Roaming"
            )
            paths = _get_default_source_paths()
        assert "Cursor" in paths["cursor"][0]
        assert "globalStorage" in paths["cursor"][0]

    def test_codex_and_claude_paths_are_platform_agnostic(self):
        for platform in ("darwin", "linux", "win32"):
            with patch("harness_recall.config.sys") as mock_sys:
                mock_sys.platform = platform
                if platform == "win32":
                    with patch("harness_recall.config.os") as mock_os:
                        mock_os.environ.get.return_value = "C:\\Users\\dev\\AppData\\Roaming"
                        paths = _get_default_source_paths()
                else:
                    paths = _get_default_source_paths()
            assert paths["codex"] == ["~/.codex/sessions/"]
            assert paths["claude-code"] == ["~/.claude/projects/"]
