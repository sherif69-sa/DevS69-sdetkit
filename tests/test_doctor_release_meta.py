from __future__ import annotations

import json
from pathlib import Path

from sdetkit import doctor


def test_doctor_release_meta_passes(tmp_path: Path, monkeypatch, capsys) -> None:
    root = tmp_path / "repo"
    (root / ".github" / "workflows").mkdir(parents=True)
    (root / "scripts").mkdir(parents=True)

    (root / "pyproject.toml").write_text(
        '[project]\nname="sdetkit"\nversion="1.2.3"\n', encoding="utf-8"
    )
    (root / "CHANGELOG.md").write_text("# Changelog\n## [1.2.3]\n- ok\n", encoding="utf-8")
    (root / ".github" / "workflows" / "release.yml").write_text(
        "name: Release\nsteps:\n  - run: python scripts/check_release_tag_version.py v1.2.3\n",
        encoding="utf-8",
    )
    (root / "scripts" / "check_release_tag_version.py").write_text(
        "print('ok')\n", encoding="utf-8"
    )

    def fake_run(cmd, *, cwd=None):
        if cmd == ["git", "status", "--porcelain"]:
            return 0, "", ""
        return 0, "", ""

    monkeypatch.setattr(doctor, "_run", fake_run)
    monkeypatch.chdir(root)

    rc = doctor.main(["--release", "--format", "json"])
    data = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert data["checks"]["release_meta"]["ok"] is True
    assert data["checks"]["clean_tree"]["severity"] == "high"


def test_doctor_release_meta_missing_changelog_heading_fails(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    root = tmp_path / "repo"
    (root / ".github" / "workflows").mkdir(parents=True)
    (root / "scripts").mkdir(parents=True)

    (root / "pyproject.toml").write_text(
        '[project]\nname="sdetkit"\nversion="1.2.3"\n', encoding="utf-8"
    )
    (root / "CHANGELOG.md").write_text("# Changelog\n## [1.2.2]\n- old\n", encoding="utf-8")
    (root / ".github" / "workflows" / "release.yml").write_text(
        "name: Release\nsteps:\n  - run: python scripts/check_release_tag_version.py v1.2.3\n",
        encoding="utf-8",
    )
    (root / "scripts" / "check_release_tag_version.py").write_text(
        "print('ok')\n", encoding="utf-8"
    )

    def fake_run(cmd, *, cwd=None):
        if cmd == ["git", "status", "--porcelain"]:
            return 0, "", ""
        return 0, "", ""

    monkeypatch.setattr(doctor, "_run", fake_run)
    monkeypatch.chdir(root)

    rc = doctor.main(["--release", "--format", "json"])
    data = json.loads(capsys.readouterr().out)

    assert rc == 2
    assert data["checks"]["release_meta"]["ok"] is False


def test_doctor_release_full_still_enables_repo_readiness(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / ".pre-commit-config.yaml").write_text("repos: []\n", encoding="utf-8")
    (root / "pyproject.toml").write_text(
        '[project]\nname="sdetkit"\nversion="1.2.3"\n', encoding="utf-8"
    )
    (root / "CHANGELOG.md").write_text("# Changelog\n## [1.2.3]\n- ok\n", encoding="utf-8")
    (root / ".github" / "workflows").mkdir(parents=True)
    (root / "scripts").mkdir(parents=True)
    (root / ".github" / "workflows" / "release.yml").write_text(
        "name: Release\nsteps:\n  - run: python scripts/check_release_tag_version.py v1.2.3\n",
        encoding="utf-8",
    )
    (root / "scripts" / "check_release_tag_version.py").write_text(
        "print('ok')\n", encoding="utf-8"
    )

    def fake_run(cmd, *, cwd=None):
        s = " ".join(cmd)
        if s.endswith("-m pre_commit --version"):
            return 0, "pre-commit 9.9.9\n", ""
        if "validate-config" in s:
            return 0, "", ""
        if s.endswith("-m pip check"):
            return 0, "", ""
        if s == "git status --porcelain":
            return 0, "", ""
        return 0, "", ""

    monkeypatch.setattr(doctor, "_run", fake_run)
    monkeypatch.chdir(root)

    rc = doctor.main(["--release-full", "--format", "json"])
    data = json.loads(capsys.readouterr().out)
    assert rc == 2
    assert data["checks"]["repo_readiness"]["ok"] is False
