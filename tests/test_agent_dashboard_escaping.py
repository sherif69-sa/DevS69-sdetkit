from __future__ import annotations

import json
from pathlib import Path

from sdetkit.agent.dashboard import build_dashboard


def test_dashboard_html_escapes_user_content(tmp_path: Path) -> None:
    history = tmp_path / ".sdetkit/agent/history"
    history.mkdir(parents=True)
    (history / "run.json").write_text(
        json.dumps(
            {
                "captured_at": "2024-01-01T00:00:00Z",
                "hash": "h1",
                "status": "error",
                "task": "<script>alert(1)</script>",
                "actions": [{"action": "<b>bad</b>"}],
            }
        ),
        encoding="utf-8",
    )

    out = tmp_path / "dashboard.html"
    build_dashboard(history_dir=history, output=out, fmt="html")
    html = out.read_text(encoding="utf-8")

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
