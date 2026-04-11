from __future__ import annotations

import json
from pathlib import Path

from sdetkit import doctor, inspect_data


def test_inspect_records_shared_workspace_and_reuses_run_hash(tmp_path: Path) -> None:
    data = tmp_path / "orders.csv"
    data.write_text("id,amount\nA1,10\n", encoding="utf-8")
    out_dir = tmp_path / "inspect-out"
    workspace = tmp_path / "workspace"

    rc1 = inspect_data.main(
        [
            str(data),
            "--format",
            "json",
            "--out-dir",
            str(out_dir),
            "--workspace-root",
            str(workspace),
        ]
    )
    rc2 = inspect_data.main(
        [
            str(data),
            "--format",
            "json",
            "--out-dir",
            str(out_dir),
            "--workspace-root",
            str(workspace),
        ]
    )

    assert rc1 == 0
    assert rc2 == 0

    payload = json.loads((out_dir / "inspect.json").read_text(encoding="utf-8"))
    run_hash = payload["workspace"]["run_hash"]

    manifest = json.loads((workspace / "manifest.json").read_text(encoding="utf-8"))
    runs = [r for r in manifest["runs"] if r["workflow"] == "inspect"]
    assert len(runs) == 1
    assert runs[0]["run_hash"] == run_hash
    assert (workspace / runs[0]["record_path"]).exists()
    latest = json.loads(
        (workspace / "latest" / "inspect" / "orders.csv.json").read_text(encoding="utf-8")
    )
    assert latest["run_hash"] == run_hash


def test_doctor_records_shared_workspace(tmp_path: Path, monkeypatch, capsys) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.chdir(root)

    workspace = root / ".sdetkit" / "workspace"
    rc = doctor.main(["--ci", "--json", "--workspace-root", str(workspace)])
    data = json.loads(capsys.readouterr().out)

    assert rc == 2
    assert data["workspace"]["workflow"] == "doctor"

    manifest = json.loads((workspace / "manifest.json").read_text(encoding="utf-8"))
    assert any(row["workflow"] == "doctor" for row in manifest["runs"])
    latest_files = list((workspace / "latest" / "doctor").glob("*.json"))
    assert latest_files
