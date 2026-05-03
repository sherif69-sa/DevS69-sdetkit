from __future__ import annotations

import json
from pathlib import Path

from sdetkit.cli import main


def test_top_level_cli_portfolio_passthrough_validate_graph(tmp_path: Path) -> None:
    graph_path = tmp_path / "graph.json"
    schema_path = tmp_path / "schema.json"
    graph_path.write_text(
        json.dumps({"repos": [{"name": "api", "path": "repos/api", "language": "python"}]}),
        encoding="utf-8",
    )
    schema_path.write_text(
        json.dumps({"type": "object", "required": ["repos"], "properties": {"repos": {"type": "array"}}}),
        encoding="utf-8",
    )
    rc = main([
        "portfolio-orchestrate",
        "validate-graph",
        "--repo-graph",
        str(graph_path),
        "--schema",
        str(schema_path),
    ])
    assert rc == 0
