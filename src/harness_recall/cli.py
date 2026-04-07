from __future__ import annotations

import contextlib
import re
from pathlib import Path

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from harness_recall import __version__
from harness_recall.config import Config
from harness_recall.index import SessionIndex
from harness_recall.parsers import get_all_parsers
from harness_recall.renderers import get_renderer
from harness_recall.display import format_session_list, format_session_detail, format_search_results, format_stats

console = Console()


@contextlib.contextmanager
def _maybe_progress(description: str, transient: bool = False):
    """Show a spinner progress only if running in a real terminal."""
    if console.is_terminal:
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                      console=console, transient=transient) as progress:
            progress.add_task(description, total=None)
            yield progress
    else:
        yield None


def _get_config(config_dir: str | None) -> Config:
    if config_dir:
        return Config(config_dir=Path(config_dir))
    return Config()


def _get_index(config: Config) -> SessionIndex:
    return SessionIndex(config.db_path)


def _auto_index(config: Config, index: SessionIndex, show_progress: bool = True) -> int:
    """Index new/changed sessions. Returns count of newly indexed sessions."""
    parsers = get_all_parsers()

    # First pass: collect files that need indexing
    to_index: list[tuple[str, object, Path]] = []
    for name, parser in parsers.items():
        if name in config.source_paths:
            paths = config.source_paths[name]
        else:
            paths = parser.default_paths
        if not paths:
            continue
        files = parser.discover(paths=paths)
        for f in files:
            if index.needs_reindex(str(f), f.stat().st_mtime):
                to_index.append((name, parser, f))

    if not to_index:
        return 0

    count = 0
    if show_progress and console.is_terminal and len(to_index) > 5:
        from rich.progress import Progress, BarColumn, TextColumn, MofNCompleteColumn
        with Progress(
            TextColumn("[dim]Indexing..."),
            BarColumn(),
            MofNCompleteColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("", total=len(to_index))
            for name, parser, f in to_index:
                try:
                    sessions = parser.parse_all(f)
                    for session in sessions:
                        index.add_session(session)
                    count += len(sessions)
                except Exception:
                    pass  # silently skip on first index to avoid wall of errors
                progress.advance(task)
    else:
        for name, parser, f in to_index:
            try:
                sessions = parser.parse_all(f)
                for session in sessions:
                    index.add_session(session)
                count += len(sessions)
            except Exception:
                pass
    return count


@click.group()
@click.version_option(__version__, prog_name="harness-recall")
def main():
    """harness-recall (hrc) - Universal CLI for AI coding session export and search."""
    pass


@main.command()
@click.option("--source", help="Filter by source (codex, claude-code, cursor)")
@click.option("--after", help="Show sessions after date (YYYY-MM-DD)")
@click.option("--before", help="Show sessions before date (YYYY-MM-DD)")
@click.option("--project", help="Filter by project directory")
@click.option("--limit", default=25, help="Max results")
@click.option("--config-dir", hidden=True, help="Override config directory")
def list(source, after, before, project, limit, config_dir):
    """List all indexed sessions."""
    config = _get_config(config_dir)
    index = _get_index(config)

    # Auto-index if needed
    with _maybe_progress("Checking for new sessions...", transient=True):
        new = _auto_index(config, index)
    if new:
        console.print(f"[dim]Indexed {new} new session(s).[/dim]")

    sessions = index.list_sessions(source=source, after=after, before=before, project=project, limit=limit)
    format_session_list(console, sessions)


@main.command()
@click.argument("query")
@click.option("--source", help="Filter by source")
@click.option("--tool", help="Filter by tool name")
@click.option("--after", help="Show sessions after date (YYYY-MM-DD)")
@click.option("--before", help="Show sessions before date (YYYY-MM-DD)")
@click.option("--limit", default=25, help="Max results")
@click.option("--config-dir", hidden=True, help="Override config directory")
def search(query, source, tool, after, before, limit, config_dir):
    """Full-text search across all sessions."""
    config = _get_config(config_dir)
    index = _get_index(config)
    _auto_index(config, index)
    results = index.search(query, source=source, tool=tool, after=after, before=before, limit=limit)
    format_search_results(console, results)


@main.command()
@click.argument("session_id")
@click.option("--full", is_flag=True, help="Show tool call details")
@click.option("--turns", help="Show specific turns (e.g., 1-5)")
@click.option("--config-dir", hidden=True, help="Override config directory")
def show(session_id, full, turns, config_dir):
    """Show a session in the terminal."""
    config = _get_config(config_dir)
    index = _get_index(config)
    _auto_index(config, index)

    session = index.get_session(session_id)
    if not session:
        matches = index.find_sessions_by_prefix(session_id)
        if matches:
            console.print(f"[yellow]Ambiguous prefix '{session_id}' matches {len(matches)} sessions:[/yellow]")
            for m in matches:
                console.print(f"  {m['id']}  {m['source']}  {m['title'] or ''}")
            console.print("[yellow]Please be more specific.[/yellow]")
        else:
            console.print(f"[red]Session not found: {session_id}[/red]")
        raise SystemExit(1)

    turn_rows = index.get_session_turns(session["id"])
    tool_calls = index.get_tool_calls(session["id"])

    if turns:
        try:
            parts = turns.split("-")
            start = int(parts[0]) - 1
            end = int(parts[1]) if len(parts) > 1 else start + 1
            turn_rows = turn_rows[start:end]
        except (ValueError, IndexError):
            console.print(f"[red]Invalid turn range: {turns}. Use format like 1-5 or 3.[/red]")
            raise SystemExit(1)

    format_session_detail(console, session, turn_rows, tool_calls, full=full)


@main.command()
@click.argument("session_id", required=False)
@click.option("--format", "fmt", default="markdown", type=click.Choice(["markdown", "html", "json"]))
@click.option("-o", "--output", "output_dir", help="Output directory")
@click.option("--all", "export_all", is_flag=True, help="Export all sessions")
@click.option("--source", help="Export sessions from specific source")
@click.option("--config-dir", hidden=True, help="Override config directory")
def export(session_id, fmt, output_dir, export_all, source, config_dir):
    """Export session(s) to Markdown, HTML, or JSON."""
    config = _get_config(config_dir)
    index = _get_index(config)
    _auto_index(config, index)
    renderer = get_renderer(fmt)

    if not session_id and not export_all and not source:
        console.print("[red]Provide a session ID, --all, or --source.[/red]")
        raise SystemExit(1)

    out_dir = Path(output_dir) if output_dir else Path.cwd()
    out_dir.mkdir(parents=True, exist_ok=True)

    if export_all or source:
        sessions = index.list_sessions(source=source, limit=10000)
        if not sessions:
            console.print("[dim]No sessions to export.[/dim]")
            return
        parsers = get_all_parsers()
        if console.is_terminal:
            with Progress(console=console) as progress:
                task = progress.add_task("Exporting...", total=len(sessions))
                for s in sessions:
                    _export_one(s, parsers, renderer, out_dir)
                    progress.advance(task)
        else:
            for s in sessions:
                _export_one(s, parsers, renderer, out_dir)
        console.print(f"[green]Exported {len(sessions)} session(s) to {out_dir}[/green]")
    else:
        session_meta = index.get_session(session_id)
        if not session_meta:
            matches = index.find_sessions_by_prefix(session_id)
            if matches:
                console.print(f"[yellow]Ambiguous prefix '{session_id}' matches {len(matches)} sessions:[/yellow]")
                for m in matches:
                    console.print(f"  {m['id']}  {m['source']}  {m['title'] or ''}")
                console.print("[yellow]Please be more specific.[/yellow]")
            else:
                console.print(f"[red]Session not found: {session_id}[/red]")
            raise SystemExit(1)
        parsers = get_all_parsers()
        filepath = _export_one(session_meta, parsers, renderer, out_dir)
        console.print(f"[green]Exported to {filepath}[/green]")


def _export_one(session_meta, parsers, renderer, out_dir):
    """Re-parse source file and export via renderer."""
    source_file = Path(session_meta["source_file"])
    parser = parsers.get(session_meta["source"])
    if not parser or not source_file.exists():
        console.print(f"[yellow]Skipped {session_meta['id']}: source file not found[/yellow]")
        return None
    # For multi-session files (e.g., Cursor), find the matching session by ID
    sessions = parser.parse_all(source_file)
    session = None
    for s in sessions:
        if s.id == session_meta["id"]:
            session = s
            break
    if session is None:
        session = sessions[0] if sessions else None
    if session is None:
        console.print(f"[yellow]Skipped {session_meta['id']}: could not parse session[/yellow]")
        return None
    content = renderer.render(session)
    safe_id = session.id[:8]
    title_slug = re.sub(r'[^a-z0-9]+', '-', (session.title or session.source).lower()).strip('-')[:50]
    filename = f"{safe_id}-{title_slug}{renderer.file_extension}"
    filepath = out_dir / filename
    filepath.write_text(content, encoding="utf-8")
    return filepath


@main.command()
@click.option("--rebuild", is_flag=True, help="Full re-index")
@click.option("--stats", is_flag=True, help="Show index statistics")
@click.option("--config-dir", hidden=True, help="Override config directory")
def index(rebuild, stats, config_dir):
    """Manage the session index."""
    config = _get_config(config_dir)
    idx = _get_index(config)

    if stats:
        s = idx.detailed_stats()
        format_stats(console, s)
        db_size = Path(config.db_path).stat().st_size if Path(config.db_path).exists() else 0
        if db_size >= 1024 * 1024:
            console.print(f"[dim]DB size: {db_size / 1024 / 1024:.1f} MB[/dim]")
        else:
            console.print(f"[dim]DB size: {db_size / 1024:.1f} KB[/dim]")
        return

    if rebuild:
        # Delete and recreate
        db = Path(config.db_path)
        if db.exists():
            db.unlink()
        idx = _get_index(config)

    with _maybe_progress("Indexing sessions..."):
        new = _auto_index(config, idx)
    console.print(f"[green]Indexed {new} session(s).[/green]")


@main.command()
@click.option("--config-dir", hidden=True)
def browse(config_dir):
    """Interactive session browser."""
    config = _get_config(config_dir)
    idx = _get_index(config)
    _auto_index(config, idx)
    from harness_recall.tui import HarnessRecallApp
    app = HarnessRecallApp(idx)
    app.run()
    idx.close()


@main.command()
@click.option("--config-dir", hidden=True)
def stats(config_dir):
    """Show session statistics and usage summary."""
    config = _get_config(config_dir)
    idx = _get_index(config)
    with _maybe_progress("Checking for new sessions...", transient=True):
        _auto_index(config, idx)
    s = idx.detailed_stats()
    format_stats(console, s)
    db_size = Path(config.db_path).stat().st_size if Path(config.db_path).exists() else 0
    if db_size >= 1024 * 1024:
        console.print(f"[dim]DB size: {db_size / 1024 / 1024:.1f} MB[/dim]")
    else:
        console.print(f"[dim]DB size: {db_size / 1024:.1f} KB[/dim]")


@main.command()
@click.option("--config-dir", hidden=True, help="Override config directory")
def config(config_dir):
    """Show current configuration."""
    cfg = _get_config(config_dir)
    console.print(f"[bold]Config directory:[/bold] {cfg.config_dir}")
    console.print(f"[bold]Database:[/bold] {cfg.db_path}")
    console.print(f"[bold]Source paths:[/bold]")
    for name, paths in cfg.source_paths.items():
        for p in paths:
            console.print(f"  {name}: {p}")
