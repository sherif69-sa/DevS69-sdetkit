from __future__ import annotations

import json

from sdetkit.baseline_dispatch import run_baseline


def test_run_baseline_json_success(capsys) -> None:
    def _ok(_args: list[str]) -> int:
        return 0

    rc = run_baseline(["check", "--format", "json"], doctor_main=_ok, gate_main=_ok)
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["failed_steps"] == []


def test_run_baseline_text_failure(capsys) -> None:
    def _ok(_args: list[str]) -> int:
        return 0

    def _fail(_args: list[str]) -> int:
        return 2

    rc = run_baseline(["write"], doctor_main=_ok, gate_main=_fail)
    assert rc == 2
    out = capsys.readouterr().out
    assert "baseline: FAIL" in out
    assert "gate_baseline" in out
