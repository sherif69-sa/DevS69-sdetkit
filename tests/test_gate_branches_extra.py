from __future__ import annotations

import argparse
import json

from sdetkit import gate


def _ns(**kwargs):
    base = dict(
        root=".",
        only=None,
        skip=None,
        list_steps=False,
        fix=False,
        fix_only=False,
        no_doctor=False,
        no_ci_templates=False,
        no_ruff=False,
        no_mypy=False,
        no_pytest=False,
        strict=False,
        format="text",
        out=None,
        mypy_args=None,
        full_pytest=False,
        pytest_args=None,
    )
    base.update(kwargs)
    return argparse.Namespace(**base)


def test_run_fast_fix_only_and_md(monkeypatch, capsys):
    monkeypatch.setattr(
        gate,
        "_run",
        lambda cmd, cwd: {
            "cmd": cmd,
            "rc": 0,
            "ok": True,
            "duration_ms": 1,
            "stdout": "",
            "stderr": "",
        },
    )
    rc = gate._run_fast(_ns(fix=True, fix_only=True, format="md"))
    assert rc == 0
    out = capsys.readouterr().out
    assert "SDET Gate Fast" in out


def test_run_fast_failure_text_path(monkeypatch, capsys):
    def fake_run(cmd, cwd):
        ok = "ruff" not in " ".join(cmd)
        return {
            "cmd": cmd,
            "rc": 0 if ok else 1,
            "ok": ok,
            "duration_ms": 1,
            "stdout": "",
            "stderr": "",
        }

    monkeypatch.setattr(gate, "_run", fake_run)
    rc = gate._run_fast(
        _ns(no_doctor=True, no_ci_templates=True, no_mypy=True, no_pytest=True, format="json")
    )
    assert rc == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
