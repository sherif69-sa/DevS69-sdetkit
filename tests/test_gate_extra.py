from __future__ import annotations

import argparse
import json
from pathlib import Path

from sdetkit import gate


def test_release_helper_functions(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    cmd = ["/usr/bin/python3", str(root / "x"), "arg"]
    normalized = gate._normalize_release_cmd(cmd, root)
    assert normalized[1] == "<repo>/x"

    ns = argparse.Namespace(
        playbooks_all=False,
        playbooks_legacy=False,
        playbooks_aliases=False,
        playbook_name=["a", "b"],
    )
    args = gate._playbooks_validate_args(ns)
    assert args[:4] == ["--name", "a", "--name", "b"]

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
