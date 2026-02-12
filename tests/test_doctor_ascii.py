from __future__ import annotations

import json
from pathlib import Path

from sdetkit import doctor


def test_doctor_ascii_detects_non_ascii(tmp_path: Path, monkeypatch, capsys):
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "tools").mkdir(parents=True)

    (root / "src" / "ok.py").write_text("x = 1\n", encoding="utf-8")
    (root / "tools" / "bad.bin").write_bytes(b"hi\xff\n")

    monkeypatch.chdir(root)
    rc = doctor.main(["--ascii", "--fail-on", "medium", "--json"])
    out = capsys.readouterr()

    assert rc == 2
    data = json.loads(out.out)
    assert data["non_ascii"] == ["tools/bad.bin"]
    assert "non-ascii: tools/bad.bin" in out.err.replace("\\", "/")


def test_doctor_ascii_ok(tmp_path: Path, monkeypatch, capsys):
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "tools").mkdir(parents=True)

    (root / "src" / "ok.py").write_text("x = 1\n", encoding="utf-8")
    (root / "tools" / "ok.txt").write_text("hello\n", encoding="utf-8")

    monkeypatch.chdir(root)
    rc = doctor.main(["--ascii", "--json"])
    out = capsys.readouterr()

    assert rc == 0
    data = json.loads(out.out)
    assert data["non_ascii"] == []
    assert out.err.strip() == ""


def test_doctor_ascii_ignores_pyc(tmp_path: Path, monkeypatch, capsys):
    root = tmp_path / "repo"
    (root / "src" / "__pycache__").mkdir(parents=True)
    (root / "tools").mkdir(parents=True)

    (root / "src" / "ok.py").write_text("x = 1\n", encoding="utf-8")

    (root / "src" / "__pycache__" / "ok.cpython-312.pyc").write_bytes(b"\x00\xff\x00\x80")
    (root / "tools" / "generated.pyc").write_bytes(b"\xff\x00\x80\x01")

    monkeypatch.chdir(root)
    rc = doctor.main(["--ascii", "--json"])
    out = capsys.readouterr()

    assert rc == 0
    data = json.loads(out.out)
    assert data["non_ascii"] == []
    assert out.err.strip() == ""


def test_doctor_ascii_ignores_egg_info_artifacts(tmp_path: Path, monkeypatch, capsys):
    root = tmp_path / "repo"
    (root / "src" / "sdetkit.egg-info").mkdir(parents=True)
    (root / "tools").mkdir(parents=True)

    (root / "src" / "ok.py").write_text("x = 1\n", encoding="utf-8")
    (root / "src" / "sdetkit.egg-info" / "PKG-INFO").write_bytes("name: sdetkit – docs\n".encode())

    monkeypatch.chdir(root)
    rc = doctor.main(["--ascii", "--json"])
    out = capsys.readouterr()

    assert rc == 0
    data = json.loads(out.out)
    assert data["non_ascii"] == []
    assert out.err.strip() == ""
