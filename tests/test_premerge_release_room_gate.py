from __future__ import annotations

import json
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _load_module():
    module_path = Path("scripts/premerge_release_room_gate.py")
    spec = spec_from_file_location("premerge_release_room_gate", module_path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_run_gate_reports_fail_when_steps_fail(tmp_path: Path, monkeypatch) -> None:
    mod = _load_module()

    class _FakeProc:
        def __init__(self, code: int) -> None:
            self.returncode = code
            self.stdout = "{}\n"
            self.stderr = ""

    calls = {"count": 0}

    def _fake_run(*args, **kwargs):  # type: ignore[no-untyped-def]
        _ = args, kwargs
        calls["count"] += 1
        return _FakeProc(1 if calls["count"] == 2 else 0)

    monkeypatch.setattr(mod.subprocess, "run", _fake_run)

    payload = mod.run_gate(tmp_path)

    assert payload["ok"] is False
    assert len(payload["steps"]) == 5


def test_main_writes_output_json(tmp_path: Path, monkeypatch, capsys) -> None:
    mod = _load_module()

    class _FakeProc:
        def __init__(self) -> None:
            self.returncode = 0
            self.stdout = "{}\n"
            self.stderr = ""

    def _fake_run(*args, **kwargs):  # type: ignore[no-untyped-def]
        _ = args, kwargs
        return _FakeProc()

    monkeypatch.setattr(mod.subprocess, "run", _fake_run)

    # Pre-create expected artifacts so run_gate can pass generated_artifacts checks.
    (tmp_path / "docs/artifacts/enterprise-assessment-pack").mkdir(parents=True)
    (
        tmp_path / "docs/artifacts/enterprise-assessment-pack/enterprise-assessment-summary.json"
    ).write_text("{}")
    (tmp_path / "build/ship-readiness").mkdir(parents=True)
    (tmp_path / "build/ship-readiness/ship-readiness-summary.json").write_text("{}")
    (tmp_path / "build/release-room-summary.md").write_text("ok")

    out = tmp_path / "gate.json"
    rc = mod.main([str(tmp_path), "--out", str(out), "--format", "json", "--strict"])

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert out.exists()


def test_run_gate_forwards_ship_release_dry_run(tmp_path: Path, monkeypatch) -> None:
    mod = _load_module()

    captured_cmds: list[list[str]] = []

    class _FakeProc:
        def __init__(self) -> None:
            self.returncode = 0
            self.stdout = "{}\n"
            self.stderr = ""

    def _fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
        _ = kwargs
        if isinstance(cmd, list):
            captured_cmds.append(cmd)
        return _FakeProc()

    monkeypatch.setattr(mod.subprocess, "run", _fake_run)

    payload = mod.run_gate(tmp_path, ship_release_dry_run=True)
    assert payload["steps"]
    ship_cmd = next(step["cmd"] for step in payload["steps"] if step["id"] == "ship_readiness")
    assert "--release-dry-run" in ship_cmd
