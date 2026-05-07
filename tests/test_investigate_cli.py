from __future__ import annotations

import pytest

from sdetkit import cli


def test_cli_dispatches_investigate_failure_help(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["investigate", "failure", "--help"])

    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "investigate failure" in out
    assert "--log LOG" in out


def test_cli_dispatches_investigate_repo_help(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["investigate", "repo", "--help"])

    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "investigate repo" in out
    assert "--root ROOT" in out


def test_cli_dispatches_investigate_surface_help(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["investigate", "surface", "--help"])

    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "investigate surface" in out
    assert "--surface SURFACE" in out
