from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "first_proof.py"
_SPEC = importlib.util.spec_from_file_location("first_proof_script", _SCRIPT_PATH)
assert _SPEC is not None and _SPEC.loader is not None
first_proof = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = first_proof
_SPEC.loader.exec_module(first_proof)


def test_first_proof_writes_decision_line_for_ship(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(first_proof, "_resolve_python", lambda _explicit: "python3.11")
    step_results = [
        first_proof.StepResult("gate-fast", ["cmd"], 0, "a.stdout.log", "a.stderr.log", "a.json"),
        first_proof.StepResult("gate-release", ["cmd"], 0, "b.stdout.log", "b.stderr.log", "b.json"),
        first_proof.StepResult("doctor", ["cmd"], 0, "c.stdout.log", "c.stderr.log", "c.json"),
    ]
    monkeypatch.setattr(first_proof, "_run_step", lambda **_kwargs: step_results.pop(0))

    rc = first_proof.main(["first_proof.py", "--out-dir", str(tmp_path)])
    assert rc == 0
    payload = json.loads((tmp_path / "first-proof-summary.json").read_text(encoding="utf-8"))
    assert payload["decision"] == "SHIP"
    assert payload["decision_line"] == "FIRST_PROOF_DECISION=SHIP"
    out = capsys.readouterr().out
    assert "FIRST_PROOF_DECISION=SHIP" in out


def test_first_proof_writes_decision_line_for_no_ship(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(first_proof, "_resolve_python", lambda _explicit: "python3.11")
    step_results = [
        first_proof.StepResult("gate-fast", ["cmd"], 0, "a.stdout.log", "a.stderr.log", "a.json"),
        first_proof.StepResult("gate-release", ["cmd"], 1, "b.stdout.log", "b.stderr.log", "b.json"),
        first_proof.StepResult("doctor", ["cmd"], 0, "c.stdout.log", "c.stderr.log", "c.json"),
    ]
    monkeypatch.setattr(first_proof, "_run_step", lambda **_kwargs: step_results.pop(0))

    rc = first_proof.main(["first_proof.py", "--strict", "--out-dir", str(tmp_path)])
    assert rc == 1
    payload = json.loads((tmp_path / "first-proof-summary.json").read_text(encoding="utf-8"))
    assert payload["decision"] == "NO-SHIP"
    assert payload["decision_line"] == "FIRST_PROOF_DECISION=NO-SHIP"
