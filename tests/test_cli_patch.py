from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli


def test_sdetkit_patch_writes_changes(tmp_path: Path, monkeypatch, capsys):
    (tmp_path / "a.txt").write_text("MARK\n", encoding="utf-8")
    spec = {
        "spec_version": 1,
        "files": [
            {
                "path": "a.txt",
                "ops": [{"op": "insert_after", "pattern": r"^MARK$", "text": "X\\n"}],
            }
        ],
    }
    (tmp_path / "spec.json").write_text(json.dumps(spec), encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    rc = cli.main(["patch", "spec.json"])

    assert rc == 0
    assert (tmp_path / "a.txt").read_text(encoding="utf-8") == "MARK\nX\n"
    assert "+X\n" in capsys.readouterr().out


def test_sdetkit_patch_check_exits_nonzero_when_changes_needed(tmp_path: Path, monkeypatch):
    (tmp_path / "a.txt").write_text("MARK\n", encoding="utf-8")
    spec = {
        "spec_version": 1,
        "files": [
            {
                "path": "a.txt",
                "ops": [{"op": "insert_after", "pattern": r"^MARK$", "text": "X\\n"}],
            }
        ],
    }
    (tmp_path / "spec.json").write_text(json.dumps(spec), encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    rc = cli.main(["patch", "spec.json", "--check"])

    assert rc == 1
    assert (tmp_path / "a.txt").read_text(encoding="utf-8") == "MARK\n"
