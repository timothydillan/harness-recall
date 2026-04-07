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
    assert "1.1.0" in result.output


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


def test_cli_stats(tmp_path):
    runner = CliRunner()
    result = runner.invoke(main, ["stats", "--config-dir", _make_empty_config(tmp_path)])
    assert result.exit_code == 0
    # Should show stats panel even on empty DB
    assert "0" in result.output


def test_cli_list_before_filter(tmp_path):
    """Verify --before filter works — inserts a session and filters by date."""
    from harness_recall.config import Config
    from harness_recall.index import SessionIndex
    from harness_recall.ir import Session, Turn
    from datetime import datetime, timezone
    from pathlib import Path

    config_dir = tmp_path / "cfg"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.toml").write_text("[sources]\ncodex = []\nclaude-code = []\n")

    # Directly insert a session into the index
    cfg = Config(config_dir=config_dir)
    idx = SessionIndex(cfg.db_path)
    session = Session(
        id="test-before-001",
        source="codex",
        source_file="/tmp/fake.jsonl",
        source_file_mtime=0.0,
        started_at=datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
        ended_at=None,
        project_dir=None,
        model="gpt-5.3-codex",
        model_provider="openai",
        cli_version=None,
        git_branch=None,
        git_commit=None,
        git_repo_url=None,
        title="Old session",
        parent_session_id=None,
        agent_name=None,
        agent_role=None,
        turns=[
            Turn(
                id="test-before-001:0",
                role="user",
                content="Hello",
                timestamp=datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
                tool_calls=[],
            )
        ],
    )
    idx.add_session(session)
    idx.close()

    runner = CliRunner()

    # --before date after the session — should return the session
    result = runner.invoke(main, ["list", "--before", "2026-02-01",
                                  "--config-dir", str(config_dir)])
    assert result.exit_code == 0
    assert "test-be" in result.output  # short ID prefix

    # --before date before the session — should return nothing
    result = runner.invoke(main, ["list", "--before", "2026-01-01",
                                  "--config-dir", str(config_dir)])
    assert result.exit_code == 0
    assert "test-be" not in result.output


def test_cli_browse_help():
    runner = CliRunner()
    result = runner.invoke(main, ["browse", "--help"])
    assert result.exit_code == 0
    assert "Interactive" in result.output


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
