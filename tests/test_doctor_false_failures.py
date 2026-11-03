from __future__ import annotations

import json
import sys
from pathlib import Path

from sdetkit import doctor
from tests.doctor_test_support import stub_enterprise_env


def _release_repo(root: Path, changelog: str) -> Path:
    (root / ".github" / "workflows").mkdir(parents=True)
    (root / "scripts").mkdir(parents=True)
    (root / "pyproject.toml").write_text(
        '[project]\nname="sdetkit"\nversion="1.2.3"\n', encoding="utf-8"
    )
    (root / "CHANGELOG.md").write_text(changelog, encoding="utf-8")
    (root / ".github" / "workflows" / "release.yml").write_text(
        "name: Release\nsteps:\n  - run: python scripts/check_release_tag_version.py v1.2.3\n",
        encoding="utf-8",
    )
    (root / "scripts" / "check_release_tag_version.py").write_text(
        "print('ok')\n", encoding="utf-8"
    )
    return root


def test_release_meta_accepts_a_keep_a_changelog_heading(tmp_path: Path) -> None:
    root = _release_repo(tmp_path / "repo", "# Changelog\n## [1.2.3] - 2026-01-15\n- ok\n")
    ok, _summary, evidence, _fix, _meta = doctor._check_release_meta(root)
    assert ok is True, evidence


def test_release_meta_does_not_take_a_longer_version_for_the_current_one(tmp_path: Path) -> None:
    root = _release_repo(tmp_path / "repo", "# Changelog\n## [1.2.30] - 2026-01-15\n")
    ok, _summary, evidence, _fix, _meta = doctor._check_release_meta(root)
    assert ok is False
    assert evidence[0]["message"] == "missing changelog heading for 1.2.3"


def test_skip_is_honoured_for_venv_dev_tools_and_release_meta(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    stub_enterprise_env(monkeypatch)
    monkeypatch.setattr(doctor, "_in_virtualenv", lambda: False)
    monkeypatch.setattr(doctor, "_check_tools", lambda: (["git"], ["ruff"]))
    monkeypatch.setattr(
        doctor, "_check_release_meta", lambda _root: (False, "bad", [], ["fix it"], {})
    )
    monkeypatch.chdir(tmp_path)

    doctor.main(
        [
            "--dev",
            "--release",
            "--skip",
            "venv,dev_tools,release_meta",
            "--format",
            "json",
        ]
    )
    checks = json.loads(capsys.readouterr().out)["checks"]
    for check_id in ("venv", "dev_tools", "release_meta"):
        assert checks.get(check_id, {}).get("ok") is not False, check_id


def test_run_reports_a_missing_executable_instead_of_raising() -> None:
    rc, out, err = doctor._run(["sdetkit-no-such-binary-for-tests"])
    assert rc == 127
    assert out == ""
    assert err


def test_run_tolerates_undecodable_output() -> None:
    rc, out, _err = doctor._run(
        [sys.executable, "-c", "import sys; sys.stdout.buffer.write(b'caf\\xe9')"]
    )
    assert rc == 0
    assert out.startswith("caf")


def test_check_deps_uses_uv_when_the_environment_has_no_pip(tmp_path: Path, monkeypatch) -> None:
    seen: list[list[str]] = []

    def fake_run(cmd, *, cwd=None):
        seen.append(cmd)
        return 0, "", ""

    monkeypatch.setattr(doctor, "_run", fake_run)
    monkeypatch.setattr(
        doctor.shutil, "which", lambda name: "/opt/bin/uv" if name == "uv" else None
    )
    monkeypatch.setattr(
        doctor.importlib.util, "find_spec", lambda name: None if name == "pip" else object()
    )

    assert doctor._check_deps(tmp_path) is True
    assert seen == [["/opt/bin/uv", "pip", "check", "--python", sys.executable]]
