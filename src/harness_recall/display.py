from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.markdown import Markdown
from rich import box


ROLE_STYLES = {
    "user": "bold cyan",
    "assistant": "bold green",
    "system": "bold yellow",
}


def format_session_list(console: Console, sessions: list[dict]) -> None:
    if not sessions:
        console.print("[dim]No sessions found.[/dim]")
        return

    table = Table(box=box.SIMPLE_HEAVY, show_edge=False, pad_edge=False)
    table.add_column("ID", style="dim", max_width=10)
    table.add_column("Source", style="magenta")
    table.add_column("Date", style="cyan")
    table.add_column("Model", style="dim")
    table.add_column("Title", max_width=60)

    for s in sessions:
        short_id = s["id"][:8]
        date = s["started_at"][:10] if s.get("started_at") else ""
        model = s.get("model") or ""
        if len(model) > 20:
            model = model[:17] + "..."
        title = s.get("title") or ""
        if len(title) > 60:
            title = title[:57] + "..."
        table.add_row(short_id, s.get("source", ""), date, model, title)

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


def format_search_results(console: Console, results: list[dict]) -> None:
    if not results:
        console.print("[dim]No results found.[/dim]")
        return

    seen_sessions = set()
    for r in results:
        sid = r["session_id"]
        if sid in seen_sessions:
            continue
        seen_sessions.add(sid)

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
