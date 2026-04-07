from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text
from rich.markdown import Markdown
from rich import box


ROLE_STYLES = {
    "user": "bold cyan",
    "assistant": "bold green",
    "system": "bold yellow",
}

SOURCE_COLORS = {
    "codex": "bright_magenta",      # violet-ish
    "claude-code": "dark_orange",    # orange
    "cursor": "dodger_blue2",        # blue
}


def print_header(console: Console) -> None:
    from harness_recall import __version__
    console.print(f"[dim]harness-recall v{__version__}[/dim]")
    console.print()


def format_session_list(console: Console, sessions: list[dict]) -> None:
    print_header(console)

    if not sessions:
        console.print("[dim]No sessions found.[/dim]")
        return

    table = Table(box=box.SIMPLE_HEAVY, show_edge=False, pad_edge=False)
    table.add_column("ID", style="dim", max_width=10)
    table.add_column("Source")
    table.add_column("Date", style="cyan")
    table.add_column("Model", style="dim")
    table.add_column("Title", max_width=60)

    for s in sessions:
        short_id = s["id"][:8]
        source = s.get("source", "")
        date = s["started_at"][:10] if s.get("started_at") else ""
        model = s.get("model") or ""
        if len(model) > 20:
            model = model[:17] + "..."
        title = s.get("title") or ""
        if len(title) > 60:
            title = title[:57] + "..."
        table.add_row(short_id, Text(source, style=SOURCE_COLORS.get(source, "magenta")), date, model, title)

    console.print(table)


def format_session_detail(console: Console, session: dict, turns: list[dict],
                          tool_calls: list[dict], full: bool = False) -> None:
    # Header panel
    title = session.get("title") or session["id"]
    meta_lines = []
    meta_lines.append(f"[dim]Source:[/dim] {session['source']}")
    meta_lines.append(f"[dim]Date:[/dim] {session.get('started_at', '')[:19]}")
    if session.get("model"):
        meta_lines.append(f"[dim]Model:[/dim] {session['model']}")
    if session.get("project_dir"):
        meta_lines.append(f"[dim]Project:[/dim] {session['project_dir']}")
    if session.get("git_branch"):
        meta_lines.append(f"[dim]Branch:[/dim] {session['git_branch']}")

    console.print(Panel(
        "\n".join(meta_lines),
        title=f"[bold]{title}[/bold]",
        border_style="dim",
        padding=(1, 2),
    ))
    console.print()

    # Build tool call lookup by turn_id
    tc_by_turn: dict[str, list[dict]] = {}
    for tc in tool_calls:
        tc_by_turn.setdefault(tc["turn_id"], []).append(tc)

    # Turns
    for turn in turns:
        role = turn["role"]
        style = ROLE_STYLES.get(role, "")
        ts = turn.get("timestamp", "")[:16].replace("T", " ")

        console.print(f" [{style}]{role.capitalize()}[/{style}]  [dim]{ts}[/dim]")
        if turn.get("content"):
            console.print(Markdown(turn["content"]), style="  ")
        console.print()

        if full:
            turn_tcs = tc_by_turn.get(turn["id"], [])
            for tc in turn_tcs:
                summary = f"[dim]{tc['name']}[/dim]"
                console.print(Panel(
                    f"[dim]Args:[/dim] {tc.get('arguments', '')[:200]}\n"
                    f"[dim]Output:[/dim] {(tc.get('output') or '')[:500]}",
                    title=summary,
                    border_style="dim",
                    padding=(0, 1),
                ))
                console.print()


def _fmt_tokens(n: int) -> str:
    """Format token count with K/M suffixes."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def format_stats(console: Console, stats: dict) -> None:
    """Render a polished stats view using rich."""
    print_header(console)
    total_sessions = stats.get("total_sessions", 0)
    total_turns = stats.get("total_turns", 0)
    total_input = stats.get("total_input_tokens", 0)
    total_output = stats.get("total_output_tokens", 0)

    # Header panel
    header_lines = [
        f"[bold cyan]Sessions:[/bold cyan]      {total_sessions}",
        f"[bold cyan]Turns:[/bold cyan]         {total_turns}",
        f"[bold cyan]Input tokens:[/bold cyan]  {_fmt_tokens(total_input)}",
        f"[bold cyan]Output tokens:[/bold cyan] {_fmt_tokens(total_output)}",
    ]
    console.print(Panel(
        "\n".join(header_lines),
        title="[bold]harness-recall — Session Statistics[/bold]",
        border_style="cyan",
        padding=(1, 2),
    ))
    console.print()

    # Sessions by source
    sources = stats.get("sources", {})
    if sources:
        src_table = Table(title="Sessions by Source", box=box.SIMPLE_HEAVY,
                          show_edge=False, pad_edge=False)
        src_table.add_column("Source", style="magenta")
        src_table.add_column("Sessions", justify="right", style="cyan")
        for src, count in sources.items():
            src_table.add_row(src, str(count))
        console.print(src_table)
        console.print()

    # Sessions by month (last 6)
    by_month = stats.get("by_month", [])
    if by_month:
        month_table = Table(title="Sessions by Month (last 6)", box=box.SIMPLE_HEAVY,
                            show_edge=False, pad_edge=False)
        month_table.add_column("Month", style="cyan")
        month_table.add_column("Sessions", justify="right")
        month_table.add_column("Bar")
        max_count = max(m["count"] for m in by_month) if by_month else 1
        for m in by_month:
            bar_width = int((m["count"] / max_count) * 20)
            bar = "█" * bar_width
            month_table.add_row(m["month"], str(m["count"]), Text(bar, style="cyan"))
        console.print(month_table)
        console.print()

    # Top projects
    top_projects = stats.get("top_projects", [])
    if top_projects:
        proj_table = Table(title="Top Projects", box=box.SIMPLE_HEAVY,
                           show_edge=False, pad_edge=False)
        proj_table.add_column("Project", style="dim")
        proj_table.add_column("Sessions", justify="right", style="cyan")
        for entry in top_projects:
            proj_table.add_row(entry["project_dir"], str(entry["count"]))
        console.print(proj_table)
        console.print()

    # Models used
    models_used = stats.get("models_used", {})
    if models_used:
        model_table = Table(title="Models Used", box=box.SIMPLE_HEAVY,
                            show_edge=False, pad_edge=False)
        model_table.add_column("Model", style="dim")
        model_table.add_column("Sessions", justify="right", style="cyan")
        for model, count in models_used.items():
            model_table.add_row(model, str(count))
        console.print(model_table)
        console.print()

    # Token summary footer (only if there are tokens)
    if total_input or total_output:
        total_tokens = total_input + total_output
        console.print(
            f"[dim]Token usage:[/dim] "
            f"[green]{_fmt_tokens(total_input)}[/green] input + "
            f"[yellow]{_fmt_tokens(total_output)}[/yellow] output = "
            f"[bold]{_fmt_tokens(total_tokens)}[/bold] total"
        )
        console.print()


def format_search_results(console: Console, results: list[dict]) -> None:
    if not results:
        console.print("[dim]No results found.[/dim]")
        return

    seen_sessions = set()
    deduped = []
    for r in results:
        sid = r["session_id"]
        if sid in seen_sessions:
            continue
        seen_sessions.add(sid)
        deduped.append(r)

    for i, r in enumerate(deduped):
        sid = r["session_id"]
        short_id = sid[:8]
        source = r.get("source", "")
        date = r.get("started_at", "")[:10]
        title = r.get("title") or ""
        snippet = r.get("snippet", "")
        # Replace FTS markers with rich markup
        snippet = snippet.replace(">>>", "[bold yellow]").replace("<<<", "[/bold yellow]")

        console.print(f"  [dim]{short_id}[/dim]  [magenta]{source}[/magenta]  [cyan]{date}[/cyan]  {title}")
        console.print(f"    {snippet}")
        console.print()
        if i < len(deduped) - 1:
            console.print(Rule(style="dim"))
