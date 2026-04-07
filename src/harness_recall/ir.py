from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime


@dataclass
class TokenUsage:
    input_tokens: int
    output_tokens: int
    cached_tokens: int | None = None
    reasoning_tokens: int | None = None


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str
    output: str | None = None


@dataclass
class Turn:
    id: str
    role: str
    content: str
    timestamp: datetime
    reasoning: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    token_usage: TokenUsage | None = None


@dataclass
class Session:
    id: str
    source: str
    source_file: str
    source_file_mtime: float
    started_at: datetime
    ended_at: datetime | None = None
    project_dir: str | None = None
    model: str | None = None
    model_provider: str | None = None
    cli_version: str | None = None
    git_branch: str | None = None
    git_commit: str | None = None
    git_repo_url: str | None = None
    title: str | None = None
    parent_session_id: str | None = None
    agent_name: str | None = None
    agent_role: str | None = None
    turns: list[Turn] = field(default_factory=list)

    def generate_title(self) -> str:
        """Auto-generate title from first user message, or fallback to source + date."""
        for turn in self.turns:
            if turn.role == "user" and turn.content:
                text = turn.content.strip()
                if len(text) > 80:
                    return text[:77] + "..."
                return text
        return f"{self.source} session {self.started_at.strftime('%Y-%m-%d %H:%M')}"

    def to_dict(self) -> dict:
        """Serialize to dict with ISO datetime strings."""
        def convert(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            return obj

        result = {}
        for k, v in asdict(self).items():
            if isinstance(v, datetime):
                result[k] = v.isoformat()
            elif isinstance(v, list) and k == "turns":
                turns_list = []
                for turn_dict in v:
                    turn_out = {}
                    for tk, tv in turn_dict.items():
                        if isinstance(tv, datetime):
                            turn_out[tk] = tv.isoformat()
                        else:
                            turn_out[tk] = tv
                    turns_list.append(turn_out)
                result[k] = turns_list
            else:
                result[k] = v
        return result
