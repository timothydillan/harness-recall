from __future__ import annotations

from harness_recall.ir import Session
from harness_recall.renderers.base import BaseRenderer
from harness_recall.renderers import register_renderer


class MarkdownRenderer(BaseRenderer):
    name = "markdown"
    file_extension = ".md"

    def render(self, session: Session) -> str:
        lines: list[str] = []
        title = session.title or session.generate_title()
        lines.append(f"# {title}")
        lines.append("")

        # Metadata
        lines.append(f"**Source:** {session.source}  ")
        lines.append(f"**Date:** {session.started_at.strftime('%Y-%m-%d %H:%M UTC')}  ")
        if session.model:
            lines.append(f"**Model:** {session.model}  ")
        if session.project_dir:
            lines.append(f"**Project:** `{session.project_dir}`  ")
        if session.git_branch:
            lines.append(f"**Branch:** `{session.git_branch}`  ")
        if session.cli_version:
            lines.append(f"**CLI Version:** {session.cli_version}  ")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Turns
        for turn in session.turns:
            role_label = turn.role.capitalize()
            time_str = turn.timestamp.strftime("%H:%M")
            lines.append(f"### **{role_label}** _{time_str}_")
            lines.append("")
            if turn.content:
                lines.append(turn.content)
                lines.append("")

            if turn.reasoning:
                lines.append("<details>")
                lines.append("<summary>Thinking</summary>")
                lines.append("")
                lines.append(turn.reasoning)
                lines.append("")
                lines.append("</details>")
                lines.append("")

            for tc in turn.tool_calls:
                lines.append(f"<details>")
                lines.append(f"<summary><code>{tc.name}</code>: {_summarize_args(tc.arguments)}</summary>")
                lines.append("")
                lines.append("**Arguments:**")
                lines.append(f"```json\n{tc.arguments}\n```")
                if tc.output:
                    lines.append("**Output:**")
                    lines.append(f"```\n{tc.output}\n```")
                lines.append("</details>")
                lines.append("")

        # Footer
        lines.append("---")
        lines.append(f"*Exported by [harness-recall](https://github.com/timothydillan/harness-recall)*")
        return "\n".join(lines)


def _summarize_args(args_json: str) -> str:
    """Create a short summary of tool arguments."""
    try:
        import json
        args = json.loads(args_json)
        if isinstance(args, dict):
            if "cmd" in args:
                return f"`{args['cmd'][:60]}`"
            if "file_path" in args:
                return f"`{args['file_path']}`"
            first_val = next(iter(args.values()), "")
            return f"`{str(first_val)[:60]}`"
    except Exception:
        pass
    return args_json[:60]


register_renderer(MarkdownRenderer())
