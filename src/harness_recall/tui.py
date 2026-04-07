"""
harness-recall interactive TUI browser.
Built with Textual (https://textual.textualize.io).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.css.query import NoMatches
from textual.message import Message
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import (
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    RadioButton,
    RadioSet,
    Static,
)

if TYPE_CHECKING:
    from harness_recall.index import SessionIndex

# ---------------------------------------------------------------------------
# Color constants (warm stone palette, matching HTML export)
# ---------------------------------------------------------------------------
STONE_900 = "#1c1917"
STONE_800 = "#292524"
STONE_700 = "#44403c"
STONE_600 = "#57534e"
STONE_400 = "#a8a29e"
STONE_100 = "#f5f5f4"
TEAL_600 = "#0d9488"
TEAL_400 = "#2dd4bf"
CYAN_500 = "#06b6d4"
GREEN_500 = "#22c55e"
VIOLET_400 = "#a78bfa"
ORANGE_400 = "#fb923c"
BLUE_400 = "#60a5fa"

SOURCE_COLORS: dict[str, str] = {
    "codex": VIOLET_400,
    "claude-code": ORANGE_400,
    "cursor": BLUE_400,
}

SOURCE_CYCLE = ["all", "codex", "claude-code", "cursor"]

# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _short_id(session_id: str) -> str:
    return session_id[:8]


def _date_str(started_at: str | None) -> str:
    if not started_at:
        return ""
    return started_at[5:10]  # MM-DD


def _source_color(source: str) -> str:
    return SOURCE_COLORS.get(source, STONE_400)


def _session_title(s: dict) -> str:
    title = s.get("title") or ""
    if not title:
        return "(no title)"
    if len(title) > 55:
        return title[:52] + "..."
    return title


# ---------------------------------------------------------------------------
# Session item label builder
# ---------------------------------------------------------------------------

def _build_session_label(s: dict, selected: bool = False) -> str:
    """Build a rich-markup string for a session list item."""
    sid = _short_id(s["id"])
    src = s.get("source", "")
    src_color = _source_color(src)
    date = _date_str(s.get("started_at"))
    title = _session_title(s)
    pointer = f"[{TEAL_400}]▸[/{TEAL_400}] " if selected else "  "
    title_style = f"bold {STONE_100}" if selected else STONE_400
    return (
        f"{pointer}[bold]{sid}[/bold]  "
        f"[{src_color}]{src}[/{src_color}]  "
        f"[{STONE_400}]{date}[/{STONE_400}]\n"
        f"    [{title_style}]{title}[/{title_style}]"
    )


# ---------------------------------------------------------------------------
# Preview content builder
# ---------------------------------------------------------------------------

def _truncate(text: str, limit: int = 500) -> str:
    if not text:
        return ""
    if len(text) > limit:
        return text[:limit] + "..."
    return text


def _build_preview_content(session: dict, turns: list[dict], tool_calls_by_turn: dict) -> str:
    """Build rich-markup text for the preview pane."""
    lines: list[str] = []

    # Session header
    title = session.get("title") or session["id"]
    src = session.get("source", "")
    src_color = _source_color(src)
    date = (session.get("started_at") or "")[:10]
    model = session.get("model") or ""

    lines.append(f"[bold {STONE_100}]{title}[/bold {STONE_100}]")
    lines.append(
        f"[{src_color}]{src}[/{src_color}]"
        + (f"  [{STONE_400}]{date}[/{STONE_400}]" if date else "")
        + (f"  [{STONE_400}]{model}[/{STONE_400}]" if model else "")
    )
    lines.append("")

    for turn in turns:
        role = turn.get("role", "")
        ts = (turn.get("timestamp") or "")[:16].replace("T", " ")

        if role == "user":
            role_str = f"[bold {CYAN_500}]User[/bold {CYAN_500}]"
        elif role == "assistant":
            role_str = f"[bold {GREEN_500}]Assistant[/bold {GREEN_500}]"
        else:
            role_str = f"[bold {STONE_400}]{role.capitalize()}[/bold {STONE_400}]"

        ts_str = f"[{STONE_400}]{ts}[/{STONE_400}]" if ts else ""
        lines.append(f"{role_str}  {ts_str}")

        content = turn.get("content") or ""
        if content:
            # Escape markup-like brackets so rich doesn't interpret them
            content = _truncate(content, 600)
            content = content.replace("[", "\\[")
            lines.append(content)
        lines.append("")

        # Tool calls (muted, indented)
        tcs = tool_calls_by_turn.get(turn["id"], [])
        for tc in tcs:
            name = tc.get("name", "")
            args = _truncate(tc.get("arguments") or "", 120)
            out = _truncate(tc.get("output") or "", 150)
            lines.append(f"  [{STONE_600}]⚙ {name}[/{STONE_600}]")
            if args:
                args_escaped = args.replace("[", "\\[")
                lines.append(f"    [{STONE_400}]{args_escaped}[/{STONE_400}]")
            if out:
                out_escaped = out.replace("[", "\\[")
                lines.append(f"    [{STONE_400}]→ {out_escaped}[/{STONE_400}]")
            lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Export Modal
# ---------------------------------------------------------------------------

class ExportModal(ModalScreen[str | None]):
    """Modal dialog to pick export format. Dismisses on selection."""

    DEFAULT_CSS = f"""
    ExportModal {{
        align: center middle;
    }}
    #export-dialog {{
        background: {STONE_800};
        border: solid {STONE_700};
        width: 40;
        height: auto;
        padding: 1 2;
    }}
    #export-title {{
        text-align: center;
        color: {STONE_100};
        margin-bottom: 1;
    }}
    #export-hint {{
        text-align: center;
        color: {STONE_400};
        margin-top: 1;
    }}
    RadioSet {{
        background: {STONE_800};
        border: none;
        width: 100%;
    }}
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    FMT_MAP = {"fmt-markdown": "markdown", "fmt-html": "html", "fmt-json": "json"}

    def compose(self) -> ComposeResult:
        with Container(id="export-dialog"):
            yield Label("Export Format", id="export-title")
            yield RadioSet(
                RadioButton("Markdown", value=True, id="fmt-markdown"),
                RadioButton("HTML", id="fmt-html"),
                RadioButton("JSON", id="fmt-json"),
                id="format-picker",
            )
            yield Label("Select a format  Esc to cancel", id="export-hint")

    def action_cancel(self) -> None:
        self.dismiss(None)

    @on(RadioSet.Changed, "#format-picker")
    def on_format_changed(self, event: RadioSet.Changed) -> None:
        """Dismiss immediately when user selects a format."""
        if event.pressed is not None:
            btn_id = event.pressed.id or ""
            fmt = self.FMT_MAP.get(btn_id, "markdown")
            self.dismiss(fmt)


# ---------------------------------------------------------------------------
# Help Modal
# ---------------------------------------------------------------------------

class HelpModal(ModalScreen):
    """Displays keyboard shortcut help."""

    DEFAULT_CSS = f"""
    HelpModal {{
        align: center middle;
    }}
    #help-dialog {{
        background: {STONE_800};
        border: solid {STONE_700};
        width: 50;
        height: auto;
        padding: 1 2;
    }}
    #help-title {{
        text-align: center;
        color: {TEAL_400};
        margin-bottom: 1;
    }}
    #help-body {{
        color: {STONE_100};
    }}
    """

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("q", "dismiss", "Close"),
        Binding("question_mark", "dismiss", "Close"),
    ]

    HELP_TEXT = f"""\
[{TEAL_400}]Tab[/{TEAL_400}]     Focus sessions list
[{TEAL_400}]↑ / k[/{TEAL_400}]   Move up
[{TEAL_400}]↓ / j[/{TEAL_400}]   Move down
[{TEAL_400}]Enter[/{TEAL_400}]   Expand session (full view)
[{TEAL_400}]Esc[/{TEAL_400}]     Back to list
[{TEAL_400}]/[/{TEAL_400}]       Focus search
[{TEAL_400}]e[/{TEAL_400}]       Export selected session
[{TEAL_400}]f[/{TEAL_400}]       Cycle source filter
[{TEAL_400}]?[/{TEAL_400}]       Show this help
[{TEAL_400}]q[/{TEAL_400}]       Quit"""

    def compose(self) -> ComposeResult:
        with Container(id="help-dialog"):
            yield Label("Keyboard Shortcuts", id="help-title")
            yield Static(self.HELP_TEXT, id="help-body")


# ---------------------------------------------------------------------------
# Preview Pane
# ---------------------------------------------------------------------------

class PreviewPane(Widget):
    """Right panel showing the selected session's turns."""

    DEFAULT_CSS = f"""
    PreviewPane {{
        background: {STONE_800};
        border: solid {STONE_700};
        overflow-y: auto;
        padding: 1 2;
    }}
    #preview-placeholder {{
        color: {STONE_400};
    }}
    #preview-content {{
        color: {STONE_100};
    }}
    """

    def compose(self) -> ComposeResult:
        yield Static(
            f"[{STONE_400}]Select a session to preview[/{STONE_400}]",
            id="preview-placeholder",
        )
        yield Static("", id="preview-content")

    def show_session(self, session: dict, turns: list[dict], tool_calls: list[dict]) -> None:
        """Render session content into the pane."""
        placeholder = self.query_one("#preview-placeholder", Static)
        content_widget = self.query_one("#preview-content", Static)

        placeholder.display = False

        # Build tool_calls_by_turn index
        tc_by_turn: dict[str, list[dict]] = {}
        for tc in tool_calls:
            tc_by_turn.setdefault(tc["turn_id"], []).append(tc)

        text = _build_preview_content(session, turns, tc_by_turn)
        content_widget.update(text)
        # Scroll to top
        self.scroll_home(animate=False)

    def clear(self) -> None:
        placeholder = self.query_one("#preview-placeholder", Static)
        content_widget = self.query_one("#preview-content", Static)
        placeholder.display = True
        content_widget.update("")


# ---------------------------------------------------------------------------
# Confirmation banner
# ---------------------------------------------------------------------------

class NotificationBanner(Widget):
    """Temporary notification message at bottom of screen."""

    DEFAULT_CSS = f"""
    NotificationBanner {{
        background: {TEAL_600};
        color: {STONE_100};
        height: 1;
        padding: 0 2;
        display: none;
    }}
    """

    def compose(self) -> ComposeResult:
        yield Static("", id="notif-text")

    def show(self, message: str) -> None:
        self.display = True
        self.query_one("#notif-text", Static).update(message)
        self.set_timer(3.0, self._hide)

    def _hide(self) -> None:
        self.display = False


# ---------------------------------------------------------------------------
# Main App
# ---------------------------------------------------------------------------

APP_CSS = f"""
Screen {{
    background: {STONE_900};
    layers: base overlay notification;
}}

#app-header {{
    background: {STONE_900};
    color: {TEAL_400};
    height: 1;
    padding: 0 2;
    layer: base;
}}

#search-row {{
    height: 3;
    padding: 0 1;
    layer: base;
}}

#search-input {{
    background: {STONE_800};
    border: solid {STONE_700};
    color: {STONE_100};
    width: 1fr;
}}

#search-input:focus {{
    border: solid {TEAL_600};
}}

#filter-label {{
    color: {STONE_400};
    height: 3;
    content-align: center middle;
    padding: 0 1;
    width: auto;
}}

#main-row {{
    height: 1fr;
    padding: 0 1;
    layer: base;
}}

#session-panel {{
    width: 40%;
    height: 100%;
    margin-right: 1;
}}

#session-panel-title {{
    color: {STONE_400};
    height: 1;
    padding: 0 1;
}}

ListView {{
    background: {STONE_800};
    border: solid {STONE_700};
    height: 1fr;
    overflow-y: auto;
}}

ListView:focus {{
    border: solid {TEAL_600};
}}

ListItem {{
    background: {STONE_800};
    color: {STONE_100};
    padding: 0 1;
    height: auto;
    border-left: solid {STONE_800};
}}

ListItem.--highlight {{
    background: #1a2f2e;
    border-left: solid {TEAL_400};
}}

ListItem > Static {{
    background: transparent;
}}

#preview-panel {{
    width: 60%;
    height: 100%;
}}

#preview-panel-title {{
    color: {STONE_400};
    height: 1;
    padding: 0 1;
}}

PreviewPane {{
    height: 1fr;
}}

#notification-row {{
    height: 1;
    layer: notification;
}}

Footer {{
    background: {STONE_900};
    color: {STONE_400};
}}

#empty-state {{
    color: {STONE_400};
    text-align: center;
    padding: 2;
}}
"""


class HarnessRecallApp(App):
    """Interactive TUI browser for harness-recall session index."""

    TITLE = "harness-recall"
    CSS = APP_CSS

    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("tab", "focus_sessions", "Sessions", show=True, priority=True),
        Binding("slash", "focus_search", "Search", show=True),
        Binding("f", "cycle_filter", "Filter", show=True),
        Binding("e", "export_session", "Export", show=True),
        Binding("question_mark", "show_help", "?Help", show=True),
        Binding("escape", "escape_action", "Back", show=False),
        Binding("enter", "enter_action", "Expand", show=True),
        Binding("j", "move_down", "Down", show=False),
        Binding("k", "move_up", "Up", show=False),
    ]

    # Reactive state
    source_filter: reactive[str] = reactive("all")
    search_query: reactive[str] = reactive("")
    _debounce_timer = None

    def __init__(self, index: "SessionIndex") -> None:
        super().__init__()
        self._index = index
        self._sessions: list[dict] = []
        self._selected_session: dict | None = None
        self._full_view_active: bool = False
        self._notification: NotificationBanner | None = None

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Static(
            f"[bold {TEAL_400}]harness-recall[/bold {TEAL_400}]",
            id="app-header",
        )

        with Horizontal(id="search-row"):
            yield Input(
                placeholder="Search sessions... (/ to focus)",
                id="search-input",
            )
            yield Label("filter: all", id="filter-label")

        with Horizontal(id="main-row"):
            with Vertical(id="session-panel"):
                yield Label(f"Sessions  [{STONE_600}]Tab to navigate[/{STONE_600}]", id="session-panel-title")
                yield ListView(id="session-list")

            with Vertical(id="preview-panel"):
                yield Label("Preview", id="preview-panel-title")
                yield PreviewPane(id="preview-pane")

        yield NotificationBanner(id="notification-banner")
        yield Footer()

    def on_mount(self) -> None:
        self._notification = self.query_one("#notification-banner", NotificationBanner)
        self._load_sessions()

    # ------------------------------------------------------------------
    # Session loading
    # ------------------------------------------------------------------

    @work(thread=True)
    def _load_sessions(self) -> None:
        """Load sessions from index in a background thread."""
        query = self.search_query.strip()
        source = self.source_filter if self.source_filter != "all" else None

        if query:
            try:
                results = self._index.search(query, source=source, limit=100)
                # Deduplicate by session_id and fetch full session row
                seen: set[str] = set()
                sessions: list[dict] = []
                for r in results:
                    sid = r["session_id"]
                    if sid not in seen:
                        seen.add(sid)
                        row = self._index.get_session(sid)
                        if row:
                            sessions.append(row)
            except Exception:
                sessions = self._index.list_sessions(source=source, limit=100)
        else:
            sessions = self._index.list_sessions(source=source, limit=100)

        self.call_from_thread(self._update_session_list, sessions)

    def _update_session_list(self, sessions: list[dict]) -> None:
        """Update the ListView on the main thread."""
        self._sessions = sessions
        lv = self.query_one("#session-list", ListView)
        lv.clear()

        if not sessions:
            lv.append(
                ListItem(
                    Static(
                        f"[{STONE_400}]No sessions found. Run `hrc index` to build the index.[/{STONE_400}]",
                        id="empty-state",
                    )
                )
            )
            # Clear preview
            self.query_one("#preview-pane", PreviewPane).clear()
            self._selected_session = None
            return

        for i, s in enumerate(sessions):
            item = ListItem(Static(_build_session_label(s, selected=(i == 0))))
            lv.append(item)

        # Highlight first item
        lv.index = 0
        self._load_preview_for_index(0)

    # ------------------------------------------------------------------
    # Preview loading
    # ------------------------------------------------------------------

    def _load_preview_for_index(self, idx: int) -> None:
        if not self._sessions or idx < 0 or idx >= len(self._sessions):
            return
        session = self._sessions[idx]
        self._selected_session = session
        self._load_preview(session)

    @work(thread=True)
    def _load_preview(self, session: dict) -> None:
        turns = self._index.get_session_turns(session["id"])
        tool_calls = self._index.get_tool_calls(session["id"])
        self.call_from_thread(self._render_preview, session, turns, tool_calls)

    def _render_preview(self, session: dict, turns: list[dict], tool_calls: list[dict]) -> None:
        pane = self.query_one("#preview-pane", PreviewPane)
        pane.show_session(session, turns, tool_calls)

    # ------------------------------------------------------------------
    # Input events
    # ------------------------------------------------------------------

    @on(Input.Changed, "#search-input")
    def on_search_changed(self, event: Input.Changed) -> None:
        """Debounce search to avoid querying on every keystroke."""
        if self._debounce_timer is not None:
            self._debounce_timer.stop()
        self.search_query = event.value
        self._debounce_timer = self.set_timer(0.3, self._fire_search)

    def _fire_search(self) -> None:
        self._debounce_timer = None
        self._load_sessions()

    @on(ListView.Selected, "#session-list")
    def on_list_selected(self, event: ListView.Selected) -> None:
        """Enter pressed on a session — expand to full view."""
        self.action_enter_action()

    @on(ListView.Highlighted, "#session-list")
    def on_list_highlighted(self, event: ListView.Highlighted) -> None:
        if event.item is None:
            return
        lv = self.query_one("#session-list", ListView)
        idx = lv.index
        if idx is not None:
            # Update pointer indicators on all items
            for i, item in enumerate(lv.children):
                if i < len(self._sessions):
                    static = item.query_one(Static)
                    static.update(_build_session_label(self._sessions[i], selected=(i == idx)))
            self._load_preview_for_index(idx)

    # ------------------------------------------------------------------
    # Key actions
    # ------------------------------------------------------------------

    def action_focus_sessions(self) -> None:
        self.query_one("#session-list", ListView).focus()

    def action_focus_search(self) -> None:
        self.query_one("#search-input", Input).focus()

    def action_cycle_filter(self) -> None:
        cur = self.source_filter
        next_idx = (SOURCE_CYCLE.index(cur) + 1) % len(SOURCE_CYCLE)
        self.source_filter = SOURCE_CYCLE[next_idx]
        # Update label
        label = self.query_one("#filter-label", Label)
        label.update(f"filter: [{_source_color(self.source_filter)}]{self.source_filter}[/{_source_color(self.source_filter)}]")
        self._load_sessions()

    def action_escape_action(self) -> None:
        if self._full_view_active:
            self._full_view_active = False
            # Reload preview normally
            lv = self.query_one("#session-list", ListView)
            if lv.index is not None:
                self._load_preview_for_index(lv.index)
        else:
            # Defocus search, return focus to list
            lv = self.query_one("#session-list", ListView)
            lv.focus()

    def action_enter_action(self) -> None:
        """Expand selected session to full scrollable content."""
        # If no session selected, try to get from current list index
        if self._selected_session is None:
            lv = self.query_one("#session-list", ListView)
            if lv.index is not None and self._sessions and lv.index < len(self._sessions):
                self._selected_session = self._sessions[lv.index]
        if self._selected_session is None:
            return
        self._full_view_active = True
        self._load_full_preview(self._selected_session)

    @work(thread=True)
    def _load_full_preview(self, session: dict) -> None:
        turns = self._index.get_session_turns(session["id"])
        tool_calls = self._index.get_tool_calls(session["id"])
        self.call_from_thread(self._render_full_preview, session, turns, tool_calls)

    def _render_full_preview(self, session: dict, turns: list[dict], tool_calls: list[dict]) -> None:
        """Render full (non-truncated) content in preview pane."""
        tc_by_turn: dict[str, list[dict]] = {}
        for tc in tool_calls:
            tc_by_turn.setdefault(tc["turn_id"], []).append(tc)

        lines: list[str] = []
        title = session.get("title") or session["id"]
        src = session.get("source", "")
        src_color = _source_color(src)
        date = (session.get("started_at") or "")[:10]
        model = session.get("model") or ""

        lines.append(f"[bold {STONE_100}]{title}[/bold {STONE_100}]")
        lines.append(
            f"[{src_color}]{src}[/{src_color}]"
            + (f"  [{STONE_400}]{date}[/{STONE_400}]" if date else "")
            + (f"  [{STONE_400}]{model}[/{STONE_400}]" if model else "")
        )
        lines.append("")

        for turn in turns:
            role = turn.get("role", "")
            ts = (turn.get("timestamp") or "")[:16].replace("T", " ")
            if role == "user":
                role_str = f"[bold {CYAN_500}]User[/bold {CYAN_500}]"
            elif role == "assistant":
                role_str = f"[bold {GREEN_500}]Assistant[/bold {GREEN_500}]"
            else:
                role_str = f"[bold {STONE_400}]{role.capitalize()}[/bold {STONE_400}]"
            ts_str = f"[{STONE_400}]{ts}[/{STONE_400}]" if ts else ""
            lines.append(f"{role_str}  {ts_str}")

            content = turn.get("content") or ""
            if content:
                content_escaped = content.replace("[", "\\[")
                lines.append(content_escaped)
            lines.append("")

            tcs = tc_by_turn.get(turn["id"], [])
            for tc in tcs:
                name = tc.get("name", "")
                args = tc.get("arguments") or ""
                out = tc.get("output") or ""
                lines.append(f"  [{STONE_600}]⚙ {name}[/{STONE_600}]")
                if args:
                    lines.append(f"    [{STONE_400}]{args.replace('[', chr(92) + '[')[:(2000)]}[/{STONE_400}]")
                if out:
                    lines.append(f"    [{STONE_400}]→ {out.replace('[', chr(92) + '[')[:(2000)]}[/{STONE_400}]")
                lines.append("")

        pane = self.query_one("#preview-pane", PreviewPane)
        content_widget = pane.query_one("#preview-content", Static)
        placeholder = pane.query_one("#preview-placeholder", Static)
        placeholder.display = False
        content_widget.update("\n".join(lines))
        pane.scroll_home(animate=False)

    def action_move_down(self) -> None:
        lv = self.query_one("#session-list", ListView)
        lv.action_cursor_down()

    def action_move_up(self) -> None:
        lv = self.query_one("#session-list", ListView)
        lv.action_cursor_up()

    def action_show_help(self) -> None:
        self.push_screen(HelpModal())

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def action_export_session(self) -> None:
        if self._selected_session is None:
            if self._notification:
                self._notification.show("No session selected.")
            return

        def _on_format_chosen(fmt: str | None) -> None:
            if fmt is None:
                return
            self._do_export(self._selected_session, fmt)

        self.push_screen(ExportModal(), _on_format_chosen)

    @work(thread=True)
    def _do_export(self, session: dict | None, fmt: str) -> None:
        if session is None:
            return
        self.call_from_thread(self._notify, f"Exporting as {fmt}...")
        try:
            from harness_recall.renderers import get_renderer
            from harness_recall.parsers import get_all_parsers

            parsers = get_all_parsers()
            renderer = get_renderer(fmt)
            source_file = Path(session["source_file"])
            parser = parsers.get(session["source"])
            if not parser or not source_file.exists():
                self.call_from_thread(
                    self._notify, f"Source file not found: {source_file.name}"
                )
                return

            # Use parse_all + ID matching for multi-session files (e.g., Cursor)
            sessions_parsed = parser.parse_all(source_file)
            parsed_session = None
            for sp in sessions_parsed:
                if sp.id == session["id"]:
                    parsed_session = sp
                    break
            if parsed_session is None:
                parsed_session = sessions_parsed[0] if sessions_parsed else None
            if parsed_session is None:
                self.call_from_thread(self._notify, "Could not parse session")
                return
            content = renderer.render(parsed_session)
            safe_id = session["id"][:8]
            title = session.get("title") or session["source"]
            title_slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:50]
            filename = f"{safe_id}-{title_slug}{renderer.file_extension}"
            out_path = Path.cwd() / filename
            out_path.write_text(content, encoding="utf-8")
            self.call_from_thread(self._notify, f"Exported to {out_path}")
        except Exception as exc:
            self.call_from_thread(self._notify, f"Export failed: {exc}")

    def _notify(self, message: str) -> None:
        if self._notification:
            self._notification.show(message)
