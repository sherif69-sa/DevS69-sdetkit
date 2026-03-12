from __future__ import annotations

import hashlib
import json
from pathlib import Path

from sdetkit import evidence


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_evidence_pack_stable_manifest(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
    out = tmp_path / ".sdetkit" / "out" / "evidence.zip"
    assert evidence.main(["pack", "--output", str(out)]) == 0
    manifest = tmp_path / ".sdetkit" / "out" / "manifest.json"
    first = _sha(manifest)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "sdetkit.evidence.v2"
    assert evidence.main(["pack", "--output", str(out)]) == 0
    second = _sha(manifest)
    assert first == second


def test_evidence_validate_and_compare(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")

    left = tmp_path / "left.zip"
    right = tmp_path / "right.zip"
    assert evidence.main(["pack", "--output", str(left)]) == 0
    _ = capsys.readouterr()
    assert evidence.main(["pack", "--output", str(right), "--redacted"]) == 0
    _ = capsys.readouterr()

    assert evidence.main(["validate", str(left), "--format", "json"]) == 0
    validate_payload = json.loads(capsys.readouterr().out)
    assert validate_payload["ok"] is True

    assert evidence.main(["compare", str(left), str(right), "--format", "json"]) == 0
    compare_payload = json.loads(capsys.readouterr().out)
    assert compare_payload["schema_version"] == "sdetkit.evidence.v2"
    assert set(compare_payload) >= {"added", "removed", "changed", "ok"}
