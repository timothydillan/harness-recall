import json
from datetime import datetime, timezone

from harness_recall.ir import Session, Turn
from harness_recall.renderers.json_renderer import JsonRenderer


def test_render_valid_json():
    session = Session(
        id="test", source="codex", source_file="/f.jsonl", source_file_mtime=0.0,
        started_at=datetime(2026, 3, 5, tzinfo=timezone.utc), turns=[
            Turn(id="test:0", role="user", content="hello",
                 timestamp=datetime(2026, 3, 5, tzinfo=timezone.utc), tool_calls=[]),
        ],
    )
    renderer = JsonRenderer()
    output = renderer.render(session)
    parsed = json.loads(output)
    assert parsed["id"] == "test"
    assert parsed["source"] == "codex"
    assert len(parsed["turns"]) == 1


def test_render_file_extension():
    renderer = JsonRenderer()
    assert renderer.file_extension == ".json"
