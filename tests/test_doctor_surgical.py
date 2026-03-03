from __future__ import annotations

import json
from pathlib import Path

from sdetkit import doctor


def test_doctor_list_checks_prints_ids(capsys) -> None:
    rc = doctor.main(["--list-checks"])
    out = capsys.readouterr().out.splitlines()
    assert rc == 0
    assert "pyproject" in out
    assert "clean_tree" in out
    assert "deps" in out


def test_doctor_only_pyproject_skips_stdlib_shadowing(tmp_path: Path, monkeypatch, capsys) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="x"\nversion="1.2.3"\n', encoding="utf-8"
    )

    calls: list[list[str]] = []

    def fake_run(cmd, *, cwd=None):
        calls.append(list(cmd))
        return 0, "", ""

    monkeypatch.setattr(doctor, "_run", fake_run)
    monkeypatch.chdir(tmp_path)

    rc = doctor.main(["--only", "pyproject", "--format", "json"])
    data = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert data["checks"]["pyproject"]["ok"] is True
    assert data["checks"]["stdlib_shadowing"]["skipped"] is True
    assert calls == []


def test_doctor_skip_deps_does_not_run_pip_check(tmp_path: Path, monkeypatch, capsys) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="x"\nversion="1.2.3"\n', encoding="utf-8"
    )

    calls: list[list[str]] = []

    def fake_run(cmd, *, cwd=None):
        calls.append(list(cmd))
        if cmd == ["git", "status", "--porcelain"]:
            return 0, "", ""
        return 0, "", ""

    monkeypatch.setattr(doctor, "_run", fake_run)
    monkeypatch.chdir(tmp_path)

    rc = doctor.main(["--deps", "--clean-tree", "--skip", "deps", "--format", "json"])
    data = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert data["checks"]["deps"]["skipped"] is True
    assert not any(c[:3] == [doctor.sys.executable, "-m", "pip"] for c in calls)
