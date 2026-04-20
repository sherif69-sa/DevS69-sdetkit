from __future__ import annotations

from sdetkit import doctor


def stub_enterprise_env(monkeypatch, *, clean_tree_ok: bool = True) -> None:
    monkeypatch.setattr(doctor, "find_stdlib_shadowing", lambda _root: [])
    monkeypatch.setattr(doctor, "_in_virtualenv", lambda: True)
    monkeypatch.setattr(doctor, "_check_tools", lambda: (["git", "python3"], []))
    monkeypatch.setattr(doctor, "_check_pyproject_toml", lambda _root: (True, "ok"))
    monkeypatch.setattr(doctor, "_check_release_meta", lambda _root: (True, "ok", [], [], {}))
    monkeypatch.setattr(doctor, "_scan_non_ascii", lambda _root: ([], []))
    monkeypatch.setattr(doctor, "_check_ci_workflows", lambda _root: ([], []))
    monkeypatch.setattr(doctor, "_check_security_files", lambda _root: ([], []))
    monkeypatch.setattr(doctor, "_check_pre_commit", lambda _root: True)
    monkeypatch.setattr(doctor, "_check_deps", lambda _root: True)
    monkeypatch.setattr(doctor, "_check_clean_tree", lambda _root: clean_tree_ok)
    monkeypatch.setattr(doctor, "_check_repo_readiness", lambda _root: ([], []))
    monkeypatch.setattr(
        doctor,
        "_check_upgrade_audit",
        lambda _root, **_kwargs: (
            True,
            "ok",
            [],
            [],
            {"packages_audited": 0, "actionable_packages": 0},
        ),
    )
