"""The repository root a `repo` subcommand is given is the operator's choice.

Paths inside that root (outputs, baselines, configs) stay confined to it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit import cli


@pytest.fixture
def elsewhere(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A repository outside the working directory."""

    repo = tmp_path / "target"
    repo.mkdir()
    (repo / "a.txt").write_text("hello\n", encoding="utf-8")
    cwd = tmp_path / "cwd" / "sub"
    cwd.mkdir(parents=True)
    monkeypatch.chdir(cwd)
    return repo


def test_init_accepts_an_absolute_root(elsewhere: Path, capsys: pytest.CaptureFixture) -> None:
    rc = cli.main(["init", "--root", str(elsewhere), "--format", "json"])

    out = capsys.readouterr()
    assert rc == 0, out.err
    assert "escapes root" not in out.err
    assert (elsewhere / "SECURITY.md").is_file()


def test_check_accepts_a_parent_relative_root(
    elsewhere: Path, capsys: pytest.CaptureFixture
) -> None:
    rc = cli.main(["repo", "check", "../../target", "--format", "json"])

    out = capsys.readouterr()
    assert rc in (0, 1), out.err
    assert json.loads(out.out)["root"] == elsewhere.resolve().as_posix()


def test_paths_inside_the_root_stay_confined(
    elsewhere: Path, tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    outside = tmp_path / "report.json"

    rc = cli.main(["repo", "check", str(elsewhere), "--out", str(outside)])

    assert rc == 2
    assert "escapes root" in capsys.readouterr().err
    assert not outside.exists()
    assert cli.main(["repo", "check", str(elsewhere), "--out", "../report.json"]) == 2


def test_a_root_with_a_nul_byte_is_rejected(capsys: pytest.CaptureFixture) -> None:
    assert cli.main(["repo", "check", "bad\x00root"]) == 2
    assert "NUL" in capsys.readouterr().err
