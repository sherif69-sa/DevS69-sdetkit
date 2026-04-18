from __future__ import annotations

import json
from pathlib import Path

from scripts import check_phase1_artifact_set as contract


def test_contract_fails_when_missing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    rc = contract.main(["--format", "json"])
    assert rc == 1


def test_contract_passes_when_artifacts_present(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    for rel in contract.REQUIRED_JSON:
        p = Path(rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"ok": True}) + "\n", encoding="utf-8")

    for rel in contract.REQUIRED_MD:
        p = Path(rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("# ok\n", encoding="utf-8")

    rc = contract.main(["--format", "json"])
    assert rc == 0
