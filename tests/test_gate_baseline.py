from __future__ import annotations

import json
from pathlib import Path

from sdetkit import gate


def test_gate_baseline_write_creates_snapshot(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    rc = gate.main(
        ["baseline", "write", "--", "--no-doctor", "--no-ci-templates", "--no-mypy", "--no-pytest"]
    )
    assert rc == 0
    snap = tmp_path / ".sdetkit" / "gate.fast.snapshot.json"
    assert snap.exists()
    assert snap.read_text(encoding="utf-8").endswith("\n")
    json.loads(snap.read_text(encoding="utf-8"))


def test_gate_baseline_check_passes_when_equal(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    rc1 = gate.main(
        ["baseline", "write", "--", "--no-doctor", "--no-ci-templates", "--no-mypy", "--no-pytest"]
    )
    assert rc1 == 0
    capsys.readouterr()

    rc2 = gate.main(
        ["baseline", "check", "--", "--no-doctor", "--no-ci-templates", "--no-mypy", "--no-pytest"]
    )
    out = capsys.readouterr().out
    data = json.loads(out)
    assert rc2 == 0
    assert data["snapshot_diff_ok"] is True


def test_gate_baseline_check_fails_when_missing(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    rc = gate.main(
        ["baseline", "check", "--", "--no-doctor", "--no-ci-templates", "--no-mypy", "--no-pytest"]
    )
    out = capsys.readouterr().out
    data = json.loads(out)
    assert rc == 2
    assert data["snapshot_diff_ok"] is False
