from __future__ import annotations

from pathlib import Path

WORKFLOW = Path(".github/workflows/runtime-watchlist-bot.yml")


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_runtime_watchlist_issue_embeds_worker_outputs() -> None:
    text = _workflow_text()

    assert 'worker_dir = Path(".sdetkit/agent/template-runs/runtime-watchlist-worker")' in text
    assert (
        'runtime_watchlist_excerpt = markdown_excerpt(worker_dir / "runtime-watchlist.md")' in text
    )
    assert 'worker_dir / "route-map.json",' in text
    assert '"## Runtime watchlist output",' in text
    assert "*runtime_watchlist_excerpt," in text
    assert '"## Runtime route-map output",' in text
    assert "*runtime_route_map_excerpt," in text


def test_runtime_watchlist_issue_limits_embedded_output_size() -> None:
    text = _workflow_text()

    assert "def markdown_excerpt(path: Path, *, max_lines: int = 36, max_chars: int = 4000)" in text
    assert "if len(selected) >= max_lines:" in text
    assert "if next_used > max_chars:" in text
    assert 'selected.append("...")' in text
