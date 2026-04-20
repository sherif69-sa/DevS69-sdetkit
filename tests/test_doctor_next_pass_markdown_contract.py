from __future__ import annotations

from pathlib import Path

from sdetkit import doctor
from tests.doctor_test_support import stub_enterprise_env


def test_next_pass_markdown_contract_no_follow_up(tmp_path: Path, monkeypatch, capsys):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "pyproject.toml").write_text("[project]\nname='x'\nversion='0.1.0'\n", encoding="utf-8")
    stub_enterprise_env(monkeypatch)
    monkeypatch.chdir(root)

    rc = doctor.main(["--enterprise-next-pass-only", "--format", "md"])
    lines = capsys.readouterr().out.strip().splitlines()

    assert rc == 0
    assert lines[0] == "_no follow-up pass required_"
    assert lines[1] == "`reason: none`"
    assert lines[2] == "`alternates: none`"


def test_next_pass_markdown_contract_with_follow_up(tmp_path: Path, monkeypatch, capsys):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "pyproject.toml").write_text("[project]\nname='x'\nversion='0.1.0'\n", encoding="utf-8")
    stub_enterprise_env(monkeypatch, clean_tree_ok=False)
    monkeypatch.chdir(root)

    rc = doctor.main(["--enterprise-next-pass-only", "--format", "md"])
    lines = capsys.readouterr().out.strip().splitlines()

    assert rc == 0
    assert lines[0] == f"`{doctor.ENTERPRISE_RERUN_HIGH_COMMAND}`"
    assert lines[1] == "`reason: blockers_present`"
    assert lines[2] == (
        f"`alternates: {doctor.ENTERPRISE_RERUN_HIGH_COMMAND} | {doctor.ENTERPRISE_RERUN_FAILED_COMMAND}`"
    )
