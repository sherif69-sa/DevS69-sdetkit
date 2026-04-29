from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_ops_bundle_trend_builds_history_and_summary(tmp_path: Path) -> None:
    contract = tmp_path / "contract.json"
    contract.write_text(json.dumps({"ok": True, "missing": []}), encoding="utf-8")

    history = tmp_path / "history.jsonl"
    out = tmp_path / "trend.json"

    subprocess.run(
        [
            sys.executable,
            "scripts/build_first_proof_ops_bundle_trend.py",
            "--contract",
            str(contract),
            "--history",
            str(history),
            "--out",
            str(out),
            "--window",
            "5",
            "--format",
            "json",
        ],
        check=True,
    )

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["recent_runs"] == 1
    assert payload["recent_passes"] == 1
    assert payload["recent_pass_rate"] == 1.0
    assert payload["branch"] == "local"
    assert payload["branch_recent_runs"] == 1


def test_ops_bundle_trend_branch_split(tmp_path: Path) -> None:
    contract = tmp_path / "contract.json"
    history = tmp_path / "history.jsonl"
    out = tmp_path / "trend.json"

    contract.write_text(json.dumps({"ok": True, "missing": []}), encoding="utf-8")
    subprocess.run(
        [
            sys.executable,
            "scripts/build_first_proof_ops_bundle_trend.py",
            "--contract",
            str(contract),
            "--history",
            str(history),
            "--out",
            str(out),
            "--branch",
            "main",
        ],
        check=True,
    )

    contract.write_text(json.dumps({"ok": False, "missing": ["x"]}), encoding="utf-8")
    subprocess.run(
        [
            sys.executable,
            "scripts/build_first_proof_ops_bundle_trend.py",
            "--contract",
            str(contract),
            "--history",
            str(history),
            "--out",
            str(out),
            "--branch",
            "feature/test",
            "--format",
            "json",
        ],
        check=True,
    )

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["branch"] == "feature/test"
    assert payload["branch_recent_runs"] == 1
    assert payload["branch_recent_pass_rate"] == 0.0
