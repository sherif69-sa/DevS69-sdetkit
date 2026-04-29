from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_onboarding_next_bootstrap_without_summary(tmp_path: Path) -> None:
    out_json = tmp_path / "onboarding-next.json"
    out_md = tmp_path / "onboarding-next.md"
    subprocess.run(
        [
            sys.executable,
            "scripts/operator_onboarding_next.py",
            "--summary",
            str(tmp_path / "missing.json"),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ],
        check=True,
    )
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["decision"] == "BOOTSTRAP"


def test_onboarding_next_advance_when_ok(tmp_path: Path) -> None:
    summary = tmp_path / "first-proof-summary.json"
    summary.write_text(json.dumps({"ok": True}), encoding="utf-8")
    out_json = tmp_path / "onboarding-next.json"
    out_md = tmp_path / "onboarding-next.md"
    subprocess.run(
        [
            sys.executable,
            "scripts/operator_onboarding_next.py",
            "--summary",
            str(summary),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
            "--format",
            "json",
        ],
        check=True,
    )
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["decision"] == "ADVANCE"
    assert payload["tasks"][0] == "make ops-now-lite"
