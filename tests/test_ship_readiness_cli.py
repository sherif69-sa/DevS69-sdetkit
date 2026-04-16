from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli


def test_cli_ship_readiness_alias_json(tmp_path: Path, capsys) -> None:
    rc = cli.main(["ship-readiness", "--root", str(tmp_path), "--out-dir", str(tmp_path / "out"), "--format", "json"])

    assert rc in {0, 1}
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert "summary" in payload


def test_cli_launch_ready_alias_text(tmp_path: Path, capsys) -> None:
    rc = cli.main(["launch-ready", "--root", str(tmp_path), "--out-dir", str(tmp_path / "out"), "--format", "text"])

    assert rc in {0, 1}
    out = capsys.readouterr().out
    assert out.startswith("ship-readiness")
