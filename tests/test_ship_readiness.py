from __future__ import annotations

import json
from pathlib import Path

from sdetkit import ship_readiness as sr


def test_build_contract_no_go_when_any_step_fails() -> None:
    contract = sr._build_release_contract(
        [
            {"id": "gate_fast", "ok": True},
            {"id": "gate_release", "ok": False},
            {"id": "doctor", "ok": True},
            {"id": "release_readiness", "ok": True},
        ]
    )

    assert contract["decision"] == "no-go"
    assert contract["blockers"] == ["gate_release"]


def test_main_emits_summary_json_with_mocked_commands(tmp_path: Path, monkeypatch) -> None:
    class _FakeProc:
        def __init__(self) -> None:
            self.returncode = 0
            self.stdout = '{"summary":{"ok":true}}\n'
            self.stderr = ""

    def _fake_run(*args, **kwargs):  # type: ignore[no-untyped-def]
        _ = args, kwargs
        return _FakeProc()

    monkeypatch.setattr(sr.subprocess, "run", _fake_run)

    out_dir = tmp_path / "out"
    rc = sr.main(
        ["--root", str(tmp_path), "--out-dir", str(out_dir), "--format", "json", "--strict"]
    )

    assert rc == 0
    payload = json.loads((out_dir / "ship-readiness-summary.json").read_text(encoding="utf-8"))
    assert payload["summary"]["decision"] == "go"
    assert payload["summary"]["all_green"] is True
    assert all(run["error_kind"] == "none" for run in payload["runs"])


def test_main_strict_returns_non_zero_when_step_fails(tmp_path: Path, monkeypatch) -> None:
    class _FakeProc:
        def __init__(self, code: int) -> None:
            self.returncode = code
            self.stdout = "{}\n"
            self.stderr = ""

    calls = {"count": 0}

    def _fake_run(*args, **kwargs):  # type: ignore[no-untyped-def]
        _ = args, kwargs
        calls["count"] += 1
        return _FakeProc(1 if calls["count"] == 1 else 0)

    monkeypatch.setattr(sr.subprocess, "run", _fake_run)

    rc = sr.main(["--root", str(tmp_path), "--out-dir", str(tmp_path / "out"), "--strict"])

    assert rc == 1


def test_run_command_retries_timeout_once_then_succeeds(tmp_path: Path, monkeypatch) -> None:
    class _FakeProc:
        def __init__(self) -> None:
            self.returncode = 0
            self.stdout = "{}\n"
            self.stderr = ""

    calls = {"count": 0}

    def _fake_run(*args, **kwargs):  # type: ignore[no-untyped-def]
        _ = args, kwargs
        calls["count"] += 1
        if calls["count"] == 1:
            raise sr.subprocess.TimeoutExpired(cmd="cmd", timeout=1)
        return _FakeProc()

    monkeypatch.setattr(sr.subprocess, "run", _fake_run)
    monkeypatch.setattr(sr.time, "sleep", lambda *_: None)

    result = sr._run_command(
        "python -m sdetkit doctor --format json",
        root=tmp_path,
        timeout_sec=1,
        retries=1,
        retry_delay_sec=0,
        log_path=None,
    )

    assert result["ok"] is True
    assert result["attempts"] == 2
