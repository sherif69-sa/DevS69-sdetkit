from __future__ import annotations

import json
from pathlib import Path

from scripts import check_phase2_kickoff_contract as contract


class _Proc:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_contract_passes_with_valid_payload_and_evidence(tmp_path: Path, monkeypatch) -> None:
    evidence = (
        tmp_path / "build/phase2-workflow/phase2-kickoff-pack/evidence/phase2-kickoff-execution-summary.json"
    )
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text(json.dumps({"total_commands": 3}), encoding="utf-8")

    payload = {"summary": {"strict_pass": True, "activation_score": 97}}

    monkeypatch.setattr(contract.subprocess, "run", lambda *a, **k: _Proc(0, json.dumps(payload)))
    rc = contract.main(["--root", str(tmp_path)])
    assert rc == 0


def test_contract_fails_with_bad_payload(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(contract.subprocess, "run", lambda *a, **k: _Proc(1, "{}"))
    rc = contract.main(["--root", str(tmp_path), "--skip-evidence"])
    assert rc == 1
