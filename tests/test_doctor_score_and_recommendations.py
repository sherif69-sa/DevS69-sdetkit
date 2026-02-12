from __future__ import annotations

import json
from pathlib import Path

from sdetkit import doctor


def test_doctor_reports_score_and_recommendations_on_failure(tmp_path: Path, monkeypatch, capsys):
    root = tmp_path / "repo"
    root.mkdir()

    def fake_run(cmd, *, cwd=None):
        s = " ".join(cmd)
        if s == "git status --porcelain":
            return 0, " M README.md\n", ""
        return 0, "", ""

    monkeypatch.setattr(doctor, "_run", fake_run)
    monkeypatch.chdir(root)

    rc = doctor.main(["--clean-tree", "--fail-on", "low", "--json"])
    data = json.loads(capsys.readouterr().out)

    assert rc == 2
    assert data["score"] == 0
    assert data["checks"]["clean_tree"]["ok"] is False
    assert any("Commit or stash pending changes" in item for item in data["recommendations"])


def test_doctor_human_report_prints_score_and_recommendations(tmp_path: Path, monkeypatch, capsys):
    root = tmp_path / "repo"
    root.mkdir()

    monkeypatch.chdir(root)
    rc = doctor.main([])
    out = capsys.readouterr()

    assert rc == 0
    assert "doctor score: 100%" in out.out
    assert "recommendations:" in out.out
    assert "No immediate blockers detected" in out.out
