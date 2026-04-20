from __future__ import annotations

import json
from pathlib import Path

from sdetkit import doctor
from tests.doctor_test_support import stub_enterprise_env


def test_next_pass_json_contract_no_follow_up(tmp_path: Path, monkeypatch, capsys):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "pyproject.toml").write_text("[project]\nname='x'\nversion='0.1.0'\n", encoding="utf-8")
    stub_enterprise_env(monkeypatch)
    monkeypatch.chdir(root)

    rc = doctor.main(["--enterprise-next-pass-only", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert payload["schema_version"] == doctor.NEXT_PASS_SCHEMA_VERSION
    assert payload["workflow"] == "doctor"
    assert payload["profile"] == "enterprise"
    assert payload["profile_mode"] == "full_scan"
    assert payload["next_pass_reason"] == "none"
    assert payload["alternate_commands"] == []
    assert payload["has_next_pass"] is False
    assert payload["exit_code_hint"] == 0


def test_next_pass_json_contract_with_follow_up(tmp_path: Path, monkeypatch, capsys):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "pyproject.toml").write_text("[project]\nname='x'\nversion='0.1.0'\n", encoding="utf-8")
    stub_enterprise_env(monkeypatch, clean_tree_ok=False)
    monkeypatch.chdir(root)

    rc = doctor.main(["--enterprise-next-pass-only", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert payload["profile_mode"] == "full_scan"
    assert payload["next_pass_reason"] == "blockers_present"
    assert payload["alternate_commands"][:2] == [
        doctor.ENTERPRISE_RERUN_HIGH_COMMAND,
        doctor.ENTERPRISE_RERUN_FAILED_COMMAND,
    ]
    assert payload["has_next_pass"] is True
    assert payload["exit_code_hint"] == 2
    assert payload["next_pass_command"] == doctor.ENTERPRISE_RERUN_HIGH_COMMAND


def test_next_pass_exit_code_flag_returns_zero_without_follow_up(
    tmp_path: Path, monkeypatch, capsys
):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "pyproject.toml").write_text("[project]\nname='x'\nversion='0.1.0'\n", encoding="utf-8")
    stub_enterprise_env(monkeypatch)
    monkeypatch.chdir(root)

    rc = doctor.main(["--enterprise-next-pass-only", "--enterprise-next-pass-exit-code"])
    payload = capsys.readouterr().out.strip().splitlines()

    assert rc == 0
    assert payload[0] == "no follow-up pass required"
