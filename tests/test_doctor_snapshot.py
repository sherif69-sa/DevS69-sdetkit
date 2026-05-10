from __future__ import annotations

import json
from pathlib import Path

from sdetkit import doctor


def test_doctor_snapshot_writes_stable_json(tmp_path: Path, monkeypatch, capsys) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="x"\nversion="1.2.3"\n', encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    snap = tmp_path / "snap.json"
    rc = doctor.main(["--only", "pyproject", "--format", "json", "--snapshot", str(snap)])
    out = capsys.readouterr().out
    assert rc == 0
    assert snap.exists()
    assert snap.read_text(encoding="utf-8").endswith("\n")
    json.loads(snap.read_text(encoding="utf-8"))
    json.loads(out)


def test_doctor_diff_snapshot_ok_when_equal(tmp_path: Path, monkeypatch, capsys) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="x"\nversion="1.2.3"\n', encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    snap = tmp_path / "snap.json"
    rc1 = doctor.main(["--only", "pyproject", "--format", "json", "--snapshot", str(snap)])
    assert rc1 == 0
    capsys.readouterr()

    rc2 = doctor.main(["--only", "pyproject", "--format", "json", "--diff-snapshot", str(snap)])
    data2 = json.loads(capsys.readouterr().out)
    assert rc2 == 0
    assert data2["snapshot_diff_ok"] is True


def test_doctor_diff_snapshot_fails_on_missing_file(tmp_path: Path, monkeypatch, capsys) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="x"\nversion="1.2.3"\n', encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    snap = tmp_path / "missing.json"
    rc = doctor.main(["--only", "pyproject", "--format", "json", "--diff-snapshot", str(snap)])
    data = json.loads(capsys.readouterr().out)
    assert rc == 2
    assert data["snapshot_diff_ok"] is False


def test_doctor_diff_snapshot_reports_new_evidence_items(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "tools").mkdir()
    (tmp_path / "src" / "old_ascii.py").write_text('MESSAGE = "old debt …"\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    snap = tmp_path / "snap.json"
    rc1 = doctor.main(
        [
            "--only",
            "ascii",
            "--fail-on",
            "high",
            "--format",
            "json",
            "--snapshot",
            str(snap),
        ]
    )
    assert rc1 == 0
    capsys.readouterr()

    (tmp_path / "tools" / "new_ascii.py").write_text('MESSAGE = "new debt …"\n', encoding="utf-8")

    rc2 = doctor.main(
        [
            "--only",
            "ascii",
            "--fail-on",
            "high",
            "--format",
            "json",
            "--diff-snapshot",
            str(snap),
        ]
    )
    data = json.loads(capsys.readouterr().out)

    assert rc2 == 2
    assert data["snapshot_diff_ok"] is False
    assert data["snapshot_new_evidence"] == [
        {
            "check": "ascii",
            "message": "non-ASCII bytes detected",
            "path": "tools/new_ascii.py",
            "type": "non_ascii",
        }
    ]
