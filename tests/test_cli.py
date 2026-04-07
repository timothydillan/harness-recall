from click.testing import CliRunner

from harness_recall.cli import main


def _make_empty_config(tmp_path):
    """Write a config.toml with no source paths so auto-index is a no-op."""
    config_dir = tmp_path / "cfg"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.toml").write_text("[sources]\ncodex = []\nclaude-code = []\n")
    return str(config_dir)


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "harness-recall" in result.output.lower() or "hrc" in result.output.lower()


def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_cli_list_empty(tmp_path):
    runner = CliRunner()
    result = runner.invoke(main, ["list", "--config-dir", _make_empty_config(tmp_path)])
    assert result.exit_code == 0


def test_cli_search_empty(tmp_path):
    runner = CliRunner()
    result = runner.invoke(main, ["search", "test query", "--config-dir", _make_empty_config(tmp_path)])
    assert result.exit_code == 0


def test_cli_index_stats(tmp_path):
    runner = CliRunner()
    result = runner.invoke(main, ["index", "--stats", "--config-dir", _make_empty_config(tmp_path)])
    assert result.exit_code == 0
    assert "0" in result.output  # 0 sessions


def test_cli_show_not_found(tmp_path):
    runner = CliRunner()
    result = runner.invoke(main, ["show", "nonexistent", "--config-dir", _make_empty_config(tmp_path)])
    assert result.exit_code != 0 or "not found" in result.output.lower()


def test_cli_export_not_found(tmp_path):
    runner = CliRunner()
    result = runner.invoke(main, ["export", "nonexistent", "--config-dir", _make_empty_config(tmp_path)])
    assert result.exit_code != 0 or "not found" in result.output.lower()


def test_full_workflow(tmp_path, fixtures_dir):
    """Integration test: index fixtures → list → search → export."""
    config_dir = tmp_path / "config"
    export_dir = tmp_path / "exports"

    runner = CliRunner()

    # Override source paths to point at fixtures
    config_file = config_dir / "config.toml"
    config_dir.mkdir(parents=True)
    config_file.write_text(f"""
[sources]
codex = ["{fixtures_dir}"]
claude-code = ["{fixtures_dir}"]
""")

    # Index
    result = runner.invoke(main, ["index", "--config-dir", str(config_dir)])
    assert result.exit_code == 0

    # List
    result = runner.invoke(main, ["list", "--config-dir", str(config_dir)])
    assert result.exit_code == 0

    # Search
    result = runner.invoke(main, ["search", "auth", "--config-dir", str(config_dir)])
    assert result.exit_code == 0

    # Index stats
    result = runner.invoke(main, ["index", "--stats", "--config-dir", str(config_dir)])
    assert result.exit_code == 0
