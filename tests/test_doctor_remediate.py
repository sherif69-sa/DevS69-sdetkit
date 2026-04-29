from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_doctor_remediate_no_action(tmp_path: Path) -> None:
    summary_path = tmp_path / "first-proof-summary.json"
    summary_path.write_text(json.dumps({"failed_steps": [], "ok": True}), encoding="utf-8")
    out_json = tmp_path / "doctor-remediate.json"
    out_md = tmp_path / "doctor-remediate.md"

    subprocess.run(
        [
            sys.executable,
            "scripts/doctor_remediate.py",
            "--summary",
            str(summary_path),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ],
        check=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["decision"] == "NO-ACTION"
    assert payload["actions"] == []


def test_doctor_remediate_actions(tmp_path: Path) -> None:
    summary_path = tmp_path / "first-proof-summary.json"
    summary_path.write_text(
        json.dumps({"failed_steps": ["doctor", "gate-release"], "ok": False}), encoding="utf-8"
    )
    out_json = tmp_path / "doctor-remediate.json"
    out_md = tmp_path / "doctor-remediate.md"

    subprocess.run(
        [
            sys.executable,
            "scripts/doctor_remediate.py",
            "--summary",
            str(summary_path),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
            "--limit",
            "1",
            "--format",
            "json",
        ],
        check=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["decision"] == "REMEDIATE"
    assert len(payload["actions"]) == 1
    assert payload["actions"][0]["step"] == "doctor"
    assert "tags" in payload["actions"][0]
    assert "doctor" in payload["actions"][0]["tags"]
