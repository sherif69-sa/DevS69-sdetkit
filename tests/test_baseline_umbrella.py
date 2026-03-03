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
