from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit import doctor


def _stubbed_doctor_environment(monkeypatch):
    monkeypatch.setattr(doctor, "find_stdlib_shadowing", lambda _root: [])
    monkeypatch.setattr(doctor, "_in_virtualenv", lambda: True)
    monkeypatch.setattr(doctor, "_check_tools", lambda: (["git", "python3"], []))
    monkeypatch.setattr(
        doctor, "_check_pyproject_toml", lambda _root: (True, "pyproject.toml is valid TOML")
    )
    monkeypatch.setattr(doctor, "_check_release_meta", lambda _root: (True, "ok", [], [], {}))
    monkeypatch.setattr(doctor, "_scan_non_ascii", lambda _root: ([], []))
    monkeypatch.setattr(doctor, "_check_ci_workflows", lambda _root: ([], []))
    monkeypatch.setattr(doctor, "_check_security_files", lambda _root: ([], []))
    monkeypatch.setattr(doctor, "_check_pre_commit", lambda _root: True)
    monkeypatch.setattr(doctor, "_check_deps", lambda _root: True)
    monkeypatch.setattr(doctor, "_check_clean_tree", lambda _root: True)
    monkeypatch.setattr(doctor, "_check_repo_readiness", lambda _root: ([], []))


def test_doctor_enterprise_profile_applies_reliability_defaults(
    tmp_path: Path, monkeypatch, capsys
):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "pyproject.toml").write_text("[project]\nname='x'\nversion='0.1.0'\n", encoding="utf-8")

    captured: dict[str, object] = {}

    def fake_upgrade(_root, **kwargs):
        captured.update(kwargs)
        return True, "ok", [], [], {"packages_audited": 0, "actionable_packages": 0}

    _stubbed_doctor_environment(monkeypatch)
    monkeypatch.setattr(doctor, "_check_upgrade_audit", fake_upgrade)
    monkeypatch.chdir(root)

    rc = doctor.main(["--enterprise", "--json", "--no-workspace"])
    data = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert data["profile"] == "enterprise"
    assert data["profile_mode"] == "full_scan"
    assert data["policy"]["strict"] is True
    assert data["policy"]["fail_on"] == "medium"
    assert captured["used_in_repo_only"] is True
    assert captured["outdated_only"] is True
    assert captured["top"] == 15
    assert data["enterprise"]["maturity_tier"] == "production_hardened"
    assert data["enterprise"]["blocker_count"] == 0
    assert data["enterprise"]["remediation_bundle"] == []
    assert data["enterprise"]["next_pass_command"] == ""
    assert data["enterprise"]["next_pass_reason"] == "none"
    assert data["enterprise"]["alternate_commands"] == []


def test_doctor_enterprise_profile_respects_explicit_fail_on(tmp_path: Path, monkeypatch, capsys):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "pyproject.toml").write_text("[project]\nname='x'\nversion='0.1.0'\n", encoding="utf-8")

    _stubbed_doctor_environment(monkeypatch)
    monkeypatch.setattr(
        doctor,
        "_check_upgrade_audit",
        lambda _root, **_kwargs: (True, "ok", [], [], {"packages_audited": 0, "actionable_packages": 0}),
    )
    monkeypatch.chdir(root)

    rc = doctor.main(["--enterprise", "--fail-on", "high", "--json", "--no-workspace"])
    data = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert data["policy"]["fail_on"] == "high"


def test_doctor_enterprise_profile_surfaces_blockers(tmp_path: Path, monkeypatch, capsys):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "pyproject.toml").write_text("[project]\nname='x'\nversion='0.1.0'\n", encoding="utf-8")

    _stubbed_doctor_environment(monkeypatch)
    monkeypatch.setattr(doctor, "_check_clean_tree", lambda _root: False)
    monkeypatch.setattr(
        doctor,
        "_check_upgrade_audit",
        lambda _root, **_kwargs: (True, "ok", [], [], {"packages_audited": 0, "actionable_packages": 0}),
    )
    monkeypatch.chdir(root)

    rc = doctor.main(["--enterprise", "--json", "--no-workspace"])
    data = json.loads(capsys.readouterr().out)

    assert rc == 2
    assert data["enterprise"]["maturity_tier"] == "at_risk"
    assert data["enterprise"]["blocker_count"] >= 1
    assert any(item["id"] == "clean_tree" for item in data["enterprise"]["blockers"])
    assert data["enterprise"]["remediation_bundle"]
    assert data["enterprise"]["remediation_bundle"][0]["check_id"] == "clean_tree"
    assert data["enterprise"]["next_pass_command"] == doctor.ENTERPRISE_RERUN_HIGH_COMMAND
    assert data["enterprise"]["next_pass_reason"] == "blockers_present"
    assert data["enterprise"]["alternate_commands"][0] == doctor.ENTERPRISE_RERUN_HIGH_COMMAND


def test_doctor_enterprise_rerun_failed_selects_only_failed_checks(
    tmp_path: Path, monkeypatch, capsys
):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "pyproject.toml").write_text("[project]\nname='x'\nversion='0.1.0'\n", encoding="utf-8")

    _stubbed_doctor_environment(monkeypatch)
    monkeypatch.setattr(
        doctor,
        "_check_upgrade_audit",
        lambda _root, **_kwargs: (True, "ok", [], [], {"packages_audited": 0, "actionable_packages": 0}),
    )
    monkeypatch.setattr(
        doctor,
        "_resolve_rerun_failed_checks",
        lambda **_kwargs: ["clean_tree", "repo_readiness"],
    )
    monkeypatch.chdir(root)

    rc = doctor.main(["--enterprise-rerun-failed", "--json"])
    data = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert data["profile"] == "enterprise"
    assert data["profile_mode"] == "rerun_failed"
    assert data["selected_checks"] == ["clean_tree", "repo_readiness"]


def test_doctor_enterprise_rerun_failed_requires_workspace(tmp_path: Path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.chdir(root)

    with pytest.raises(SystemExit):
        doctor.main(["--enterprise-rerun-failed", "--no-workspace"])


def test_doctor_enterprise_markdown_includes_execution_section(tmp_path: Path, monkeypatch, capsys):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "pyproject.toml").write_text("[project]\nname='x'\nversion='0.1.0'\n", encoding="utf-8")

    _stubbed_doctor_environment(monkeypatch)
    monkeypatch.setattr(doctor, "_check_clean_tree", lambda _root: False)
    monkeypatch.setattr(
        doctor,
        "_check_upgrade_audit",
        lambda _root, **_kwargs: (True, "ok", [], [], {"packages_audited": 0, "actionable_packages": 0}),
    )
    monkeypatch.chdir(root)

    rc = doctor.main(["--enterprise", "--format", "md", "--no-workspace"])
    out = capsys.readouterr().out

    assert rc == 2
    assert "#### Enterprise execution" in out
    assert "- blocker count:" in out
    assert "- next pass reason: `blockers_present`" in out
    assert "- remediation bundle:" in out
    assert f"- next pass command: `{doctor.ENTERPRISE_RERUN_HIGH_COMMAND}`" in out


def test_doctor_help_includes_enterprise_rerun_flag(capsys):
    with pytest.raises(SystemExit):
        doctor.main(["--help"])
    out = capsys.readouterr().out
    assert "--enterprise-rerun-failed" in out
    assert "--enterprise-rerun-high" in out
    assert "--enterprise-rerun-top" in out
    assert "--enterprise-next-pass-only" in out
    assert "--enterprise-next-pass-exit-code" in out


def test_resolve_rerun_failed_checks_uses_failed_checks_fallback(monkeypatch):
    monkeypatch.setattr(
        doctor,
        "load_latest_previous_payload",
        lambda **_kwargs: ({"failed_checks": ["repo_readiness", "clean_tree"]}, {}),
    )

    selected = doctor._resolve_rerun_failed_checks(workspace_root=Path("."), scope="repo")

    assert selected == ["clean_tree", "repo_readiness"]


def test_resolve_rerun_failed_checks_returns_empty_when_no_payload(monkeypatch):
    monkeypatch.setattr(doctor, "load_latest_previous_payload", lambda **_kwargs: (None, {}))

    selected = doctor._resolve_rerun_failed_checks(workspace_root=Path("."), scope="repo")

    assert selected == []


def test_resolve_rerun_failed_checks_filters_by_severity(monkeypatch):
    monkeypatch.setattr(
        doctor,
        "load_latest_previous_payload",
        lambda **_kwargs: (
            {
                "next_actions": [
                    {"id": "clean_tree", "severity": "high"},
                    {"id": "repo_readiness", "severity": "high"},
                    {"id": "deps", "severity": "medium"},
                ]
            },
            {},
        ),
    )

    selected = doctor._resolve_rerun_failed_checks(
        workspace_root=Path("."), scope="repo", severity="high"
    )

    assert selected == ["clean_tree", "repo_readiness"]


def test_resolve_rerun_failed_checks_high_severity_uses_failed_checks_fallback(monkeypatch):
    monkeypatch.setattr(
        doctor,
        "load_latest_previous_payload",
        lambda **_kwargs: ({"failed_checks": ["repo_readiness", "clean_tree"]}, {}),
    )

    selected = doctor._resolve_rerun_failed_checks(
        workspace_root=Path("."), scope="repo", severity="high"
    )

    assert selected == ["clean_tree", "repo_readiness"]


def test_doctor_enterprise_rerun_high_selects_high_only(tmp_path: Path, monkeypatch, capsys):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "pyproject.toml").write_text("[project]\nname='x'\nversion='0.1.0'\n", encoding="utf-8")

    _stubbed_doctor_environment(monkeypatch)
    monkeypatch.setattr(
        doctor,
        "_check_upgrade_audit",
        lambda _root, **_kwargs: (True, "ok", [], [], {"packages_audited": 0, "actionable_packages": 0}),
    )
    monkeypatch.setattr(
        doctor,
        "_resolve_rerun_failed_checks",
        lambda **_kwargs: ["clean_tree"],
    )
    monkeypatch.chdir(root)

    rc = doctor.main(["--enterprise-rerun-high", "--json"])
    data = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert data["profile"] == "enterprise"
    assert data["profile_mode"] == "rerun_high"
    assert data["selected_checks"] == ["clean_tree"]


def test_doctor_enterprise_rerun_modes_are_mutually_exclusive(tmp_path: Path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.chdir(root)

    with pytest.raises(SystemExit):
        doctor.main(["--enterprise-rerun-failed", "--enterprise-rerun-high"])


def test_doctor_enterprise_rerun_top_limits_selected_checks(tmp_path: Path, monkeypatch, capsys):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "pyproject.toml").write_text("[project]\nname='x'\nversion='0.1.0'\n", encoding="utf-8")

    _stubbed_doctor_environment(monkeypatch)
    monkeypatch.setattr(
        doctor,
        "_check_upgrade_audit",
        lambda _root, **_kwargs: (True, "ok", [], [], {"packages_audited": 0, "actionable_packages": 0}),
    )
    monkeypatch.setattr(
        doctor,
        "_resolve_rerun_failed_checks",
        lambda **_kwargs: ["clean_tree", "repo_readiness"],
    )
    monkeypatch.chdir(root)

    rc = doctor.main(["--enterprise-rerun-failed", "--enterprise-rerun-top", "1", "--json"])
    data = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert data["rerun_top"] == 1
    assert data["selected_checks"] == ["clean_tree"]


def test_doctor_enterprise_rerun_top_requires_rerun_mode(tmp_path: Path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.chdir(root)

    with pytest.raises(SystemExit):
        doctor.main(["--enterprise-rerun-top", "1"])


def test_doctor_enterprise_rerun_top_requires_positive_value(tmp_path: Path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.chdir(root)

    with pytest.raises(SystemExit):
        doctor.main(["--enterprise-rerun-failed", "--enterprise-rerun-top", "0"])


def test_doctor_enterprise_markdown_includes_profile_mode_for_rerun_high(
    tmp_path: Path, monkeypatch, capsys
):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "pyproject.toml").write_text("[project]\nname='x'\nversion='0.1.0'\n", encoding="utf-8")

    _stubbed_doctor_environment(monkeypatch)
    monkeypatch.setattr(
        doctor,
        "_check_upgrade_audit",
        lambda _root, **_kwargs: (True, "ok", [], [], {"packages_audited": 0, "actionable_packages": 0}),
    )
    monkeypatch.setattr(doctor, "_resolve_rerun_failed_checks", lambda **_kwargs: ["clean_tree"])
    monkeypatch.chdir(root)

    rc = doctor.main(["--enterprise-rerun-high", "--format", "md"])
    out = capsys.readouterr().out

    assert rc == 0
    assert "- profile mode: `rerun_high`" in out


def test_doctor_enterprise_next_pass_only_prints_command(tmp_path: Path, monkeypatch, capsys):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "pyproject.toml").write_text("[project]\nname='x'\nversion='0.1.0'\n", encoding="utf-8")

    _stubbed_doctor_environment(monkeypatch)
    monkeypatch.setattr(doctor, "_check_clean_tree", lambda _root: False)
    monkeypatch.setattr(
        doctor,
        "_check_upgrade_audit",
        lambda _root, **_kwargs: (True, "ok", [], [], {"packages_audited": 0, "actionable_packages": 0}),
    )
    monkeypatch.chdir(root)

    rc = doctor.main(["--enterprise-next-pass-only"])
    out = capsys.readouterr().out

    assert rc == 0
    lines = out.strip().splitlines()
    assert lines[0] == doctor.ENTERPRISE_RERUN_HIGH_COMMAND
    assert lines[1] == "reason: blockers_present"
    assert lines[2] == (
        f"alternates: {doctor.ENTERPRISE_RERUN_HIGH_COMMAND} | {doctor.ENTERPRISE_RERUN_FAILED_COMMAND}"
    )


def test_doctor_enterprise_next_pass_only_reports_no_follow_up(tmp_path: Path, monkeypatch, capsys):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "pyproject.toml").write_text("[project]\nname='x'\nversion='0.1.0'\n", encoding="utf-8")

    _stubbed_doctor_environment(monkeypatch)
    monkeypatch.setattr(
        doctor,
        "_check_upgrade_audit",
        lambda _root, **_kwargs: (True, "ok", [], [], {"packages_audited": 0, "actionable_packages": 0}),
    )
    monkeypatch.chdir(root)

    rc = doctor.main(["--enterprise-next-pass-only", "--json"])
    data = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert data["schema_version"] == doctor.NEXT_PASS_SCHEMA_VERSION
    assert data["workflow"] == "doctor"
    assert data["profile"] == "enterprise"
    assert data["profile_mode"] == "full_scan"
    assert "selected_checks" in data
    assert data["next_pass_command"] == ""
    assert data["next_pass_reason"] == "none"
    assert data["alternate_commands"] == []
    assert data["has_next_pass"] is False
    assert data["exit_code_hint"] == 0
    assert data["message"] == "no follow-up pass required"


def test_doctor_enterprise_next_pass_only_tolerates_non_dict_enterprise_payload(
    tmp_path: Path, monkeypatch, capsys
):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "pyproject.toml").write_text("[project]\nname='x'\nversion='0.1.0'\n", encoding="utf-8")

    _stubbed_doctor_environment(monkeypatch)
    monkeypatch.setattr(doctor, "_build_enterprise_insights", lambda _data: ["not-a-dict"])
    monkeypatch.chdir(root)

    rc = doctor.main(["--enterprise-next-pass-only", "--json"])
    data = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert data["next_pass_command"] == ""
    assert data["next_pass_reason"] == "none"
    assert data["alternate_commands"] == []
    assert data["has_next_pass"] is False


def test_doctor_enterprise_next_pass_only_json_reports_available_pass(
    tmp_path: Path, monkeypatch, capsys
):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "pyproject.toml").write_text("[project]\nname='x'\nversion='0.1.0'\n", encoding="utf-8")

    _stubbed_doctor_environment(monkeypatch)
    monkeypatch.setattr(doctor, "_check_clean_tree", lambda _root: False)
    monkeypatch.setattr(
        doctor,
        "_check_upgrade_audit",
        lambda _root, **_kwargs: (True, "ok", [], [], {"packages_audited": 0, "actionable_packages": 0}),
    )
    monkeypatch.chdir(root)

    rc = doctor.main(["--enterprise-next-pass-only", "--json"])
    data = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert data["next_pass_command"] == doctor.ENTERPRISE_RERUN_HIGH_COMMAND
    assert data["next_pass_reason"] == "blockers_present"
    assert data["alternate_commands"][:2] == [
        doctor.ENTERPRISE_RERUN_HIGH_COMMAND,
        doctor.ENTERPRISE_RERUN_FAILED_COMMAND,
    ]
    assert data["has_next_pass"] is True
    assert data["exit_code_hint"] == 2
    assert data["message"] == "next pass available"


def test_doctor_enterprise_next_pass_only_plain_no_follow_up_message(
    tmp_path: Path, monkeypatch, capsys
):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "pyproject.toml").write_text("[project]\nname='x'\nversion='0.1.0'\n", encoding="utf-8")

    _stubbed_doctor_environment(monkeypatch)
    monkeypatch.chdir(root)

    rc = doctor.main(["--enterprise-next-pass-only"])
    lines = capsys.readouterr().out.strip().splitlines()

    assert rc == 0
    assert lines[0] == "no follow-up pass required"
    assert lines[1] == "reason: none"
    assert lines[2] == "alternates: none"


def test_doctor_enterprise_next_pass_only_is_mutually_exclusive_with_rerun_flags(
    tmp_path: Path, monkeypatch
):
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.chdir(root)

    with pytest.raises(SystemExit):
        doctor.main(["--enterprise-next-pass-only", "--enterprise-rerun-failed"])

    with pytest.raises(SystemExit):
        doctor.main(["--enterprise-next-pass-only", "--enterprise-rerun-high"])


def test_doctor_enterprise_next_pass_exit_code_requires_next_pass_only(tmp_path: Path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.chdir(root)

    with pytest.raises(SystemExit):
        doctor.main(["--enterprise-next-pass-exit-code"])


def test_doctor_enterprise_next_pass_only_writes_out_file(tmp_path: Path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    out_file = root / "next-pass.txt"
    (root / "pyproject.toml").write_text("[project]\nname='x'\nversion='0.1.0'\n", encoding="utf-8")

    _stubbed_doctor_environment(monkeypatch)
    monkeypatch.setattr(doctor, "_check_clean_tree", lambda _root: False)
    monkeypatch.setattr(
        doctor,
        "_check_upgrade_audit",
        lambda _root, **_kwargs: (True, "ok", [], [], {"packages_audited": 0, "actionable_packages": 0}),
    )
    monkeypatch.chdir(root)

    rc = doctor.main(["--enterprise-next-pass-only", "--out", str(out_file)])

    assert rc == 0
    lines = out_file.read_text(encoding="utf-8").strip().splitlines()
    assert lines[0] == doctor.ENTERPRISE_RERUN_HIGH_COMMAND
    assert lines[1] == "reason: blockers_present"
    assert lines[2] == (
        f"alternates: {doctor.ENTERPRISE_RERUN_HIGH_COMMAND} | {doctor.ENTERPRISE_RERUN_FAILED_COMMAND}"
    )


def test_doctor_enterprise_next_pass_only_markdown_wraps_command(
    tmp_path: Path, monkeypatch, capsys
):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "pyproject.toml").write_text("[project]\nname='x'\nversion='0.1.0'\n", encoding="utf-8")

    _stubbed_doctor_environment(monkeypatch)
    monkeypatch.setattr(doctor, "_check_clean_tree", lambda _root: False)
    monkeypatch.setattr(
        doctor,
        "_check_upgrade_audit",
        lambda _root, **_kwargs: (True, "ok", [], [], {"packages_audited": 0, "actionable_packages": 0}),
    )
    monkeypatch.chdir(root)

    rc = doctor.main(["--enterprise-next-pass-only", "--format", "md"])
    out = capsys.readouterr().out

    assert rc == 0
    lines = out.strip().splitlines()
    assert lines[0] == f"`{doctor.ENTERPRISE_RERUN_HIGH_COMMAND}`"
    assert lines[1] == "`reason: blockers_present`"
    assert lines[2] == (
        f"`alternates: {doctor.ENTERPRISE_RERUN_HIGH_COMMAND} | {doctor.ENTERPRISE_RERUN_FAILED_COMMAND}`"
    )


def test_doctor_enterprise_next_pass_only_markdown_no_follow_up_message(
    tmp_path: Path, monkeypatch, capsys
):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "pyproject.toml").write_text("[project]\nname='x'\nversion='0.1.0'\n", encoding="utf-8")

    _stubbed_doctor_environment(monkeypatch)
    monkeypatch.setattr(
        doctor,
        "_check_upgrade_audit",
        lambda _root, **_kwargs: (True, "ok", [], [], {"packages_audited": 0, "actionable_packages": 0}),
    )
    monkeypatch.chdir(root)

    rc = doctor.main(["--enterprise-next-pass-only", "--format", "md"])
    out = capsys.readouterr().out

    assert rc == 0
    lines = out.strip().splitlines()
    assert lines[0] == "_no follow-up pass required_"
    assert lines[1] == "`reason: none`"
    assert lines[2] == "`alternates: none`"


def test_doctor_enterprise_next_pass_only_can_return_exit_code_hint(
    tmp_path: Path, monkeypatch, capsys
):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "pyproject.toml").write_text("[project]\nname='x'\nversion='0.1.0'\n", encoding="utf-8")

    _stubbed_doctor_environment(monkeypatch)
    monkeypatch.setattr(doctor, "_check_clean_tree", lambda _root: False)
    monkeypatch.setattr(
        doctor,
        "_check_upgrade_audit",
        lambda _root, **_kwargs: (True, "ok", [], [], {"packages_audited": 0, "actionable_packages": 0}),
    )
    monkeypatch.chdir(root)

    rc = doctor.main(["--enterprise-next-pass-only", "--enterprise-next-pass-exit-code"])
    lines = capsys.readouterr().out.strip().splitlines()

    assert rc == 2
    assert lines[0] == doctor.ENTERPRISE_RERUN_HIGH_COMMAND
