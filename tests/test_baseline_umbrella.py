from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli


def test_baseline_write_and_check(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)

    import sdetkit.doctor
    import sdetkit.gate

    monkeypatch.setattr(sdetkit.doctor, "main", lambda argv=None: 0)
    monkeypatch.setattr(sdetkit.gate, "main", lambda argv=None: 0)

    rc1 = cli.main(["baseline", "write", "--format", "json"])
    data1 = json.loads(capsys.readouterr().out)
    assert rc1 == 0
    assert data1["ok"] is True
    assert [s["id"] for s in data1["steps"]] == ["doctor_baseline", "gate_baseline"]

    rc2 = cli.main(["baseline", "check", "--format", "json"])
    data2 = json.loads(capsys.readouterr().out)
    assert rc2 == 0
    assert data2["ok"] is True


def test_baseline_check_forwards_diff_flags(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)

    import sdetkit.doctor
    import sdetkit.gate

    calls: list[list[str]] = []

    def rec(argv=None) -> int:
        calls.append(list(argv) if argv is not None else [])
        return 0

    monkeypatch.setattr(sdetkit.doctor, "main", rec)
    monkeypatch.setattr(sdetkit.gate, "main", rec)

    rc = cli.main(["baseline", "check", "--format", "json", "--diff", "--diff-context", "7"])
    data = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert data["ok"] is True
    assert calls[0][:5] == ["baseline", "check", "--diff", "--diff-context", "7"]
    assert calls[1][:5] == ["baseline", "check", "--diff", "--diff-context", "7"]
