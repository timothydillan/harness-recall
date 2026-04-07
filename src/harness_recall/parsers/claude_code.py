from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import orjson

from harness_recall.ir import Session, Turn, ToolCall, TokenUsage
from harness_recall.parsers.base import BaseParser
from harness_recall.parsers import register_parser


class ClaudeCodeParser(BaseParser):
    name = "claude-code"
    default_paths = ["~/.claude/projects/"]
    file_pattern = "**/*.jsonl"

    def parse(self, file_path: Path) -> Session:
        lines = file_path.read_bytes().split(b"\n")
        events = []
        for line in lines:
            line = line.strip()
            if line:
                events.append(orjson.loads(line))

        session_id = None
        cwd = None
        version = None
        git_branch = None
        model = None
        started_at = None
        ended_at = None

        turns: list[Turn] = []
        # Track pending tool calls by tool_use_id
        pending_tool_calls: dict[str, ToolCall] = {}
        seq = 0

        for ev in events:
            ev_type = ev.get("type")
            ts_str = ev.get("timestamp")
            ts = _parse_ts(ts_str) if ts_str else None

            if ts:
                if started_at is None:
                    started_at = ts
                ended_at = ts

            # Extract session metadata from any event that has it
            if not session_id and ev.get("sessionId"):
                session_id = ev["sessionId"]
            if not cwd and ev.get("cwd"):
                cwd = ev["cwd"]
            if not version and ev.get("version"):
                version = ev["version"]
            if not git_branch and ev.get("gitBranch"):
                git_branch = ev["gitBranch"]

            if ev_type == "user":
                msg = ev.get("message", {})
                content = msg.get("content", "")

                # Skip tool_result messages
                if isinstance(content, list):
                    is_tool_result = all(
                        isinstance(b, dict) and b.get("type") == "tool_result"
                        for b in content
                    )
                    if is_tool_result:
                        # Attach tool outputs to pending calls
                        for block in content:
                            tool_id = block.get("tool_use_id", "")
                            if tool_id in pending_tool_calls:
                                output = block.get("content", "")
                                if isinstance(output, list):
                                    output = "\n".join(
                                        b.get("text", "") for b in output if isinstance(b, dict)
                                    )
                                if len(output) > 10240:
                                    output = output[:10240] + "\n... [truncated]"
                                pending_tool_calls[tool_id].output = output
                        continue

                    # Extract text from content blocks
                    text_parts = []
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "input_text":
                            text_parts.append(block.get("text", ""))
                        elif isinstance(block, str):
                            text_parts.append(block)
                    content = "\n".join(text_parts)

                if isinstance(content, str) and content.strip():
                    # Skip system instructions injected as user messages
                    if content.strip().startswith("<system_instruction>"):
                        continue
                    turns.append(Turn(
                        id=f"{session_id}:{seq}",
                        role="user",
                        content=content,
                        timestamp=ts or started_at or datetime.now(timezone.utc),
                        tool_calls=[],
                    ))
                    seq += 1

            elif ev_type == "assistant":
                msg = ev.get("message", {})
                content_blocks = msg.get("content", [])
                usage = msg.get("usage", {})

                if not model:
                    model = msg.get("model")

                text_parts = []
                thinking_text = None
                turn_tool_calls = []

                for block in content_blocks:
                    if not isinstance(block, dict):
                        continue
                    block_type = block.get("type")

                    if block_type == "text":
                        text = block.get("text", "").strip()
                        if text:
                            text_parts.append(text)

                    elif block_type == "thinking":
                        thinking_text = block.get("thinking", "")

                    elif block_type == "tool_use":
                        tool_id = block.get("id", "")
                        tc = ToolCall(
                            id=tool_id,
                            name=block.get("name", ""),
                            arguments=json.dumps(block.get("input", {})),
                            output=None,
                        )
                        pending_tool_calls[tool_id] = tc
                        turn_tool_calls.append(tc)

                text = "\n\n".join(text_parts)

                # Only create a turn if there's text or tool calls
                if text or turn_tool_calls:
                    token_usage = None
                    if usage:
                        token_usage = TokenUsage(
                            input_tokens=usage.get("input_tokens", 0),
                            output_tokens=usage.get("output_tokens", 0),
                            cached_tokens=usage.get("cache_read_input_tokens"),
                            reasoning_tokens=None,
                        )

                    turns.append(Turn(
                        id=f"{session_id}:{seq}",
                        role="assistant",
                        content=text,
                        timestamp=ts or ended_at or datetime.now(timezone.utc),
                        reasoning=thinking_text,
                        tool_calls=turn_tool_calls,
                        token_usage=token_usage,
                    ))
                    seq += 1

        if started_at is None:
            started_at = datetime.now(timezone.utc)

        session = Session(
            id=session_id or file_path.stem,
            source="claude-code",
            source_file=str(file_path),
            source_file_mtime=file_path.stat().st_mtime,
            started_at=started_at,
            ended_at=ended_at,
            project_dir=cwd,
            model=model,
            model_provider="anthropic",
            cli_version=version,
            git_branch=git_branch,
            git_commit=None,
            git_repo_url=None,
            title=None,
            parent_session_id=None,
            agent_name=None,
            agent_role=None,
            turns=turns,
        )
        session.title = session.generate_title()
        return session


def _parse_ts(ts_str: str) -> datetime:
    if ts_str.endswith("Z"):
        ts_str = ts_str[:-1] + "+00:00"
    return datetime.fromisoformat(ts_str)


register_parser(ClaudeCodeParser())
