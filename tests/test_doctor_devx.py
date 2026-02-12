from __future__ import annotations

import json
from pathlib import Path

from sdetkit import doctor


def test_doctor_dev_flags_report_missing_venv_and_pr_mode(tmp_path: Path, monkeypatch, capsys):
    root = tmp_path / "repo"
    wf = root / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "ci.yml").write_text("name: ci\n", encoding="utf-8")
    (wf / "quality.yml").write_text("name: quality\n", encoding="utf-8")
    (wf / "security.yml").write_text("name: security\n", encoding="utf-8")
    (root / "pyproject.toml").write_text("[project]\nname='x'\nversion='0.1.0'\n", encoding="utf-8")

    def fake_run(cmd, *, cwd=None):
        s = " ".join(cmd)
        if "check-yaml" in s:
            return 0, "", ""
        if s.endswith("-m pip check"):
            return 0, "", ""
        if s == "git status --porcelain":
            return 0, "", ""
        return 0, "", ""

    monkeypatch.setattr(doctor, "_run", fake_run)
    monkeypatch.setattr(doctor, "_check_tools", lambda: (["git", "python3"], []))
    monkeypatch.setattr(doctor, "_in_virtualenv", lambda: False)
    monkeypatch.setattr(
        doctor, "_check_pyproject_toml", lambda _root: (True, "pyproject.toml is valid TOML")
    )
    monkeypatch.chdir(root)

    rc = doctor.main(["--dev", "--ci", "--deps", "--clean-tree", "--pr"])
    out = capsys.readouterr()

    assert rc == 0
    assert "### SDET Doctor Report" in out.out
    assert "`venv`" in out.out
    assert "virtual environment is not active" in out.out


def test_doctor_pyproject_parse_failure(tmp_path: Path, monkeypatch, capsys):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "pyproject.toml").write_text("[project\nname='broken'\n", encoding="utf-8")
    monkeypatch.chdir(root)

    rc = doctor.main(["--pyproject", "--json"])
    data = json.loads(capsys.readouterr().out)

    assert rc == 2
    assert data["pyproject_ok"] is False
    assert data["checks"]["pyproject"]["ok"] is False
    assert any("Fix pyproject.toml syntax" in item for item in data["recommendations"])


def test_check_tools_does_not_require_pre_commit_binary(monkeypatch):
    monkeypatch.setattr(doctor.shutil, "which", lambda _name: "/usr/bin/mock")

    present, missing = doctor._check_tools()

    assert "pre-commit" not in present
    assert "pre-commit" not in missing
