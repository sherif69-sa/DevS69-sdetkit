from __future__ import annotations

import argparse

from sdetkit import gate


def _ns(**kwargs):
    base = dict(
        root=".",
        only=None,
        skip=None,
        list_steps=False,
        fix=False,
        fix_only=False,
        no_doctor=True,
        no_ci_templates=True,
        no_ruff=True,
        no_mypy=True,
        no_pytest=True,
        strict=False,
        format="json",
        out=None,
        mypy_args=None,
        full_pytest=False,
        pytest_args=None,
        dry_run=False,
        release_full=False,
        playbooks_all=False,
        playbooks_legacy=False,
        playbooks_aliases=False,
        playbook_name=[],
    )
    base.update(kwargs)
    return argparse.Namespace(**base)


def test_run_fast_unknown_and_list_steps(capsys):
    rc = gate._run_fast(_ns(only="nope"))
    assert rc == 2
    assert "unknown step" in capsys.readouterr().err

    rc2 = gate._run_fast(_ns(list_steps=True))
    assert rc2 == 0
    assert "ruff_fix" in capsys.readouterr().out


def test_run_release_failure_path(monkeypatch, capsys):
    monkeypatch.setattr(gate, "_run", lambda cmd, cwd: {"cmd": cmd, "rc": 1, "ok": False})
    rc = gate._run_release(_ns())
    assert rc == 2
    assert "problems found" in capsys.readouterr().err
