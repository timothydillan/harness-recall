from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import orjson

from harness_recall.ir import Session, Turn, ToolCall, TokenUsage
from harness_recall.parsers.base import BaseParser
from harness_recall.parsers import register_parser


class CodexParser(BaseParser):
    name = "codex"
    default_paths = ["~/.codex/sessions/"]
    file_pattern = "**/*.jsonl"

    _session_titles: dict[str, str] | None = None

    def _load_session_titles(self) -> dict[str, str]:
        if self._session_titles is not None:
            return self._session_titles
        index_path = Path.home() / ".codex" / "session_index.jsonl"
        titles: dict[str, str] = {}
        if index_path.exists():
            for line in index_path.read_bytes().splitlines():
                line = line.strip()
                if line:
                    try:
                        entry = orjson.loads(line)
                        session_id = entry.get("id")
                        thread_name = entry.get("thread_name")
                        if session_id and thread_name:
                            titles[session_id] = thread_name
                    except Exception:
                        pass
        CodexParser._session_titles = titles
        return titles

    def _get_session_title(self, session_id: str) -> str | None:
        titles = self._load_session_titles()
        return titles.get(session_id)

    def parse(self, file_path: Path) -> Session:
        lines = file_path.read_bytes().split(b"\n")
        events = []
        for line in lines:
            line = line.strip()
            if line:
                events.append(orjson.loads(line))

        # Extract session metadata
        session_meta = None
        turn_context = None
        for ev in events:
            if ev["type"] == "session_meta":
                session_meta = ev["payload"]
                break

        for ev in events:
            if ev["type"] == "turn_context":
                turn_context = ev["payload"]
                break

        if session_meta is None:
            raise ValueError(f"No session_meta found in {file_path}")

        # Parse metadata
        session_id = session_meta["id"]
        started_at = _parse_ts(session_meta["timestamp"])
        cwd = session_meta.get("cwd")
        cli_version = session_meta.get("cli_version")
        model_provider = session_meta.get("model_provider")

        # Git info
        git = session_meta.get("git", {})
        git_branch = git.get("branch") if isinstance(git, dict) else None
        git_commit = git.get("commit_hash") if isinstance(git, dict) else None
        git_repo_url = git.get("repository_url") if isinstance(git, dict) else None

        # Model from turn_context
        model = turn_context.get("model") if turn_context else None

        # Subagent info
        parent_session_id = session_meta.get("forked_from_id")
        agent_name = session_meta.get("agent_nickname")
        agent_role = session_meta.get("agent_role")

        # Build turns from events
        turns = []
        pending_tool_calls: dict[str, ToolCall] = {}
        last_token_usage: TokenUsage | None = None
        ended_at: datetime | None = None
        seq = 0

        for ev in events:
            ts = _parse_ts(ev["timestamp"])
            ended_at = ts  # track latest timestamp

            if ev["type"] == "event_msg":
                payload = ev["payload"]
                msg_type = payload["type"]

                if msg_type == "user_message":
                    text = payload.get("message", "")
                    if text.strip():
                        turns.append(Turn(
                            id=f"{session_id}:{seq}",
                            role="user",
                            content=text,
                            timestamp=ts,
                            tool_calls=[],
                        ))
                        seq += 1

                elif msg_type == "agent_message":
                    text = payload.get("message", "")
                    if text.strip():
                        # Attach pending tool calls to the last assistant turn
                        resolved_tools = list(pending_tool_calls.values())
                        pending_tool_calls.clear()
                        turns.append(Turn(
                            id=f"{session_id}:{seq}",
                            role="assistant",
                            content=text,
                            timestamp=ts,
                            tool_calls=resolved_tools,
                            token_usage=last_token_usage,
                        ))
                        last_token_usage = None
                        seq += 1

                elif msg_type == "token_count":
                    info = payload.get("info") or {}
                    total = info.get("total_token_usage") or {}
                    last_token_usage = TokenUsage(
                        input_tokens=total.get("input_tokens", 0),
                        output_tokens=total.get("output_tokens", 0),
                        cached_tokens=total.get("cached_input_tokens"),
                        reasoning_tokens=total.get("reasoning_output_tokens"),
                    )

            elif ev["type"] == "response_item":
                payload = ev["payload"]
                item_type = payload["type"]

                if item_type == "function_call":
                    call_id = payload.get("call_id", "")
                    pending_tool_calls[call_id] = ToolCall(
                        id=call_id,
                        name=payload.get("name", ""),
                        arguments=payload.get("arguments", ""),
                        output=None,
                    )
                elif item_type == "function_call_output":
                    call_id = payload.get("call_id", "")
                    if call_id in pending_tool_calls:
                        output = payload.get("output", "")
                        # Truncate to 10KB for storage
                        if len(output) > 10240:
                            output = output[:10240] + "\n... [truncated]"
                        pending_tool_calls[call_id].output = output

        # If token_count came after the last agent_message, attach it retroactively
        if last_token_usage is not None:
            for turn in reversed(turns):
                if turn.role == "assistant":
                    turn.token_usage = last_token_usage
                    last_token_usage = None
                    break

        # If there are remaining tool calls not attached to a turn, create one
        if pending_tool_calls:
            resolved_tools = list(pending_tool_calls.values())
            turns.append(Turn(
                id=f"{session_id}:{seq}",
                role="assistant",
                content="",
                timestamp=ended_at or started_at,
                tool_calls=resolved_tools,
                token_usage=last_token_usage,
            ))
            seq += 1

        session = Session(
            id=session_id,
            source="codex",
            source_file=str(file_path),
            source_file_mtime=file_path.stat().st_mtime,
            started_at=started_at,
            ended_at=ended_at,
            project_dir=cwd,
            model=model,
            model_provider=model_provider,
            cli_version=cli_version,
            git_branch=git_branch,
            git_commit=git_commit,
            git_repo_url=git_repo_url,
            title=None,
            parent_session_id=parent_session_id,
            agent_name=agent_name,
            agent_role=agent_role,
            turns=turns,
        )
        # Use session_index.jsonl title if available, otherwise auto-generate
        title = self._get_session_title(session_id)
        session.title = title or session.generate_title()
        return session


def _parse_ts(ts_str: str) -> datetime:
    """Parse ISO 8601 timestamp string to datetime."""
    if ts_str.endswith("Z"):
        ts_str = ts_str[:-1] + "+00:00"
    return datetime.fromisoformat(ts_str)


register_parser(CodexParser())
