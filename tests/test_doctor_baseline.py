from __future__ import annotations

import json
from pathlib import Path

from sdetkit import doctor


def test_doctor_baseline_write_creates_default_snapshot(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="x"\nversion="1.2.3"\n', encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    rc = doctor.main(["baseline", "write", "--", "--only", "pyproject"])
    capsys.readouterr()
    assert rc == 0

    snap = tmp_path / ".sdetkit" / "doctor.snapshot.json"
    assert snap.exists()
    assert snap.read_text(encoding="utf-8").endswith("\n")
    json.loads(snap.read_text(encoding="utf-8"))


def test_doctor_baseline_check_passes_when_equal(tmp_path: Path, monkeypatch, capsys) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="x"\nversion="1.2.3"\n', encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    rc1 = doctor.main(["baseline", "write", "--", "--only", "pyproject"])
    assert rc1 == 0
    capsys.readouterr()

    rc2 = doctor.main(["baseline", "check", "--", "--only", "pyproject"])
    data = json.loads(capsys.readouterr().out)
    assert rc2 == 0
    assert data["snapshot_diff_ok"] is True


def test_doctor_baseline_check_fails_when_missing(tmp_path: Path, monkeypatch, capsys) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="x"\nversion="1.2.3"\n', encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    rc = doctor.main(["baseline", "check", "--", "--only", "pyproject"])
    data = json.loads(capsys.readouterr().out)
    assert rc == 2
    assert data["snapshot_diff_ok"] is False
