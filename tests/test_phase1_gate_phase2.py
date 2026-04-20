from __future__ import annotations

import json
from pathlib import Path

from scripts import phase1_gate_phase2 as gate


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_build_gate_result_ready() -> None:
    payload = gate.build_gate_result(
        {"status": "complete", "gate_ok": True, "blocking_required_checks": []},
        {"ok": True, "missing": []},
    )
    assert payload["ready_for_phase2"] is True


def test_main_missing_inputs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    rc = gate.main(["--format", "json"])
    assert rc == 1


def test_main_success(tmp_path: Path) -> None:
    finish = tmp_path / "finish.json"
    artifacts = tmp_path / "artifacts.json"
    _write(finish, {"status": "complete", "gate_ok": True, "blocking_required_checks": []})
    _write(artifacts, {"ok": True, "missing": []})

    rc = gate.main(
        ["--finish-signal", str(finish), "--artifact-set", str(artifacts), "--format", "json"]
    )
    assert rc == 0
