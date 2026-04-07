from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from harness_recall.ir import Session, Turn, ToolCall, TokenUsage
from harness_recall.parsers.base import BaseParser
from harness_recall.parsers import register_parser


class CursorParser(BaseParser):
    name = "cursor"
    default_paths = ["~/Library/Application Support/Cursor/User/globalStorage/"]
    file_pattern = "state.vscdb"

    def parse(self, file_path: Path) -> Session:
        """Parse the first conversation from a Cursor state.vscdb file."""
        sessions = self.parse_all(file_path)
        if not sessions:
            raise ValueError(f"No conversations found in {file_path}")
        return sessions[0]

    def parse_all(self, file_path: Path) -> list[Session]:
        """Parse all conversations from a Cursor state.vscdb SQLite database."""
        db_path = str(file_path)
        file_mtime = file_path.stat().st_mtime
        sessions: list[Session] = []

        conn = sqlite3.connect(db_path)
        try:
            conn.row_factory = sqlite3.Row

            # Fetch all composerData entries
            cursor = conn.execute(
                "SELECT key, value FROM cursorDiskKV WHERE key LIKE 'composerData:%'"
            )
            composer_rows = cursor.fetchall()

            for row in composer_rows:
                key: str = row["key"]
                value_blob = row["value"]

                # Decode the BLOB as UTF-8 JSON
                try:
                    if isinstance(value_blob, bytes):
                        composer_json = value_blob.decode("utf-8", errors="replace")
                    else:
                        composer_json = str(value_blob)
                    composer_data = json.loads(composer_json)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue

                composer_id = composer_data.get("composerId")
                if not composer_id:
                    # Fall back to extracting from key: "composerData:{composerId}"
                    composer_id = key[len("composerData:"):]
                if not composer_id:
                    continue

                # Parse conversation start time
                created_at_raw = composer_data.get("createdAt")
                started_at = _parse_cursor_ts(created_at_raw)

                # Extract model
                model_config = composer_data.get("modelConfig") or {}
                model = model_config.get("modelName") or None

                # Fetch all bubbles for this conversation
                bubble_cursor = conn.execute(
                    "SELECT key, value FROM cursorDiskKV WHERE key LIKE ?",
                    (f"bubbleId:{composer_id}:%",),
                )
                bubble_rows = bubble_cursor.fetchall()

                if not bubble_rows:
                    # Skip conversations with 0 bubbles
                    continue

                # Parse bubble JSON objects
                bubbles: list[dict] = []
                for brow in bubble_rows:
                    bvalue = brow["value"]
                    try:
                        if isinstance(bvalue, bytes):
                            bjson = bvalue.decode("utf-8", errors="replace")
                        else:
                            bjson = str(bvalue)
                        bdata = json.loads(bjson)
                        bubbles.append(bdata)
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        continue

                # Sort bubbles by timestamp
                bubbles.sort(key=lambda b: _bubble_sort_key(b))

                # Build IR turns
                turns: list[Turn] = []
                seq = 0
                ended_at: datetime | None = None

                for bubble in bubbles:
                    bubble_id = bubble.get("bubbleId", f"{composer_id}:{seq}")
                    btype = bubble.get("type")  # 1=user, 2=assistant
                    text = bubble.get("text") or ""
                    created_raw = bubble.get("createdAt")
                    ts = _parse_cursor_ts(created_raw) or started_at

                    if ts:
                        ended_at = ts

                    # Determine role
                    if btype == 1:
                        role = "user"
                    elif btype == 2:
                        role = "assistant"
                    else:
                        # Unknown type — skip
                        continue

                    # Extract tool calls from toolFormerData
                    tool_calls: list[ToolCall] = []
                    tfd = bubble.get("toolFormerData")
                    if tfd and isinstance(tfd, dict):
                        tc_id = tfd.get("toolCallId") or f"{bubble_id}-tool"
                        tc_name = tfd.get("name") or ""
                        tc_args = tfd.get("rawArgs") or ""
                        tc_output = tfd.get("result") or None
                        if tc_output and len(tc_output) > 10240:
                            tc_output = tc_output[:10240] + "\n... [truncated]"
                        tool_calls.append(ToolCall(
                            id=tc_id,
                            name=tc_name,
                            arguments=tc_args,
                            output=tc_output,
                        ))

                    # Extract token usage
                    token_usage: TokenUsage | None = None
                    tc_raw = bubble.get("tokenCount")
                    if tc_raw and isinstance(tc_raw, dict):
                        input_t = tc_raw.get("inputTokens") or 0
                        output_t = tc_raw.get("outputTokens") or 0
                        if input_t or output_t:
                            token_usage = TokenUsage(
                                input_tokens=input_t,
                                output_tokens=output_t,
                            )

                    # Only create a turn if there's text or tool calls
                    if text.strip() or tool_calls:
                        turns.append(Turn(
                            id=f"{composer_id}:{seq}",
                            role=role,
                            content=text,
                            timestamp=ts or started_at or datetime.now(timezone.utc),
                            tool_calls=tool_calls,
                            token_usage=token_usage,
                        ))
                        seq += 1

                if not turns:
                    continue

                session = Session(
                    id=composer_id,
                    source="cursor",
                    source_file=str(file_path),
                    source_file_mtime=file_mtime,
                    started_at=started_at or turns[0].timestamp,
                    ended_at=ended_at,
                    project_dir=None,
                    model=model,
                    model_provider=None,
                    cli_version=None,
                    turns=turns,
                )
                session.title = session.generate_title()
                sessions.append(session)

        finally:
            conn.close()

        return sessions


def _parse_cursor_ts(value) -> datetime | None:
    """Parse a Cursor timestamp: Unix ms integer, or ISO 8601 string."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        # Unix milliseconds
        try:
            return datetime.fromtimestamp(value / 1000.0, tz=timezone.utc)
        except (OSError, OverflowError, ValueError):
            return None
    if isinstance(value, str):
        if not value:
            return None
        # Try ISO 8601
        ts_str = value
        if ts_str.endswith("Z"):
            ts_str = ts_str[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(ts_str)
        except ValueError:
            pass
        # Try parsing as a numeric string (Unix ms)
        try:
            ms = float(value)
            return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)
        except (ValueError, OSError, OverflowError):
            pass
    return None


def _bubble_sort_key(bubble: dict):
    """Return a sortable key for a bubble based on its timestamp."""
    ts = _parse_cursor_ts(bubble.get("createdAt"))
    if ts:
        return ts
    # Fall back to epoch so unknowns sort first
    return datetime(1970, 1, 1, tzinfo=timezone.utc)


register_parser(CursorParser())
