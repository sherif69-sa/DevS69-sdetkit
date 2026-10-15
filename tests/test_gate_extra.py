from __future__ import annotations

import json
from pathlib import Path

from sdetkit import gate


def test_release_helper_functions(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    cmd = ["/usr/bin/python3", str(root / "x"), "arg"]
    normalized = gate._normalize_release_cmd(cmd, root)
    assert normalized[1] == "<repo>/x"

    steps = gate._normalize_release_steps(
        [{"id": "x", "cmd": [str(root), "y"], "stdout": "s", "stderr": "e", "duration_ms": 10}],
        root,
    )
    assert "stdout" not in steps[0] and "stderr" not in steps[0]


def test_run_release_dry_run_json(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    rc = gate.main(["release", "--dry-run", "--format", "json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["dry_run"] is True
    assert len(payload["steps"]) == 3
