from __future__ import annotations

import json
from pathlib import Path

from sdetkit import doctor


def test_doctor_ci_missing_files(tmp_path: Path, monkeypatch, capsys):
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.chdir(root)

    rc = doctor.main(["--ci", "--json"])
    data = json.loads(capsys.readouterr().out)

    assert rc == 2
    assert data["checks"]["ci_workflows"]["ok"] is False
    assert {"ci", "quality", "security"}.issubset(set(data["ci_missing"]))


def test_doctor_security_files_pass_when_present(tmp_path: Path, monkeypatch, capsys):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "SECURITY.md").write_text("sec\n", encoding="utf-8")
    (root / "CONTRIBUTING.md").write_text("contrib\n", encoding="utf-8")
    (root / "CODE_OF_CONDUCT.md").write_text("coc\n", encoding="utf-8")
    (root / "LICENSE").write_text("license\n", encoding="utf-8")
    monkeypatch.chdir(root)

    rc = doctor.main(["--ci", "--fail-on", "high", "--json"])
    data = json.loads(capsys.readouterr().out)

    assert rc == 2
    assert data["checks"]["security_files"]["ok"] is True


def test_doctor_pre_commit_and_deps_and_clean_tree(tmp_path: Path, monkeypatch, capsys):
    root = tmp_path / "repo"
    root.mkdir()
    (root / ".pre-commit-config.yaml").write_text("repos: []\n", encoding="utf-8")

    def fake_run(cmd, *, cwd=None):
        s = " ".join(cmd)
        if s.endswith("-m pre_commit --version"):
            return 0, "pre-commit 9.9.9\\n", ""
        if "validate-config" in s:
            return 0, "", ""
        if s.endswith("-m pip check"):
            return 0, "", ""
        if s == "git status --porcelain":
            return 0, "", ""
        return 0, "", ""

    monkeypatch.setattr(doctor, "_run", fake_run)
    monkeypatch.chdir(root)

    rc = doctor.main(["--pre-commit", "--deps", "--clean-tree", "--json"])
    data = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert data["pre_commit_ok"] is True
    assert data["deps_ok"] is True
    assert data["clean_tree_ok"] is True
