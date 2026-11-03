from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from sdetkit import doctor, inspect_data
from sdetkit.evidence import evidence_workspace
from sdetkit.utils import atomicio


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


def _record(workspace: Path, scope: str) -> dict[str, object]:
    return evidence_workspace.record_workspace_run(
        workspace_root=workspace,
        workflow="review",
        scope=scope,
        payload={"scope": scope},
        artifacts={},
        recommendations=[],
    )


def test_a_reader_during_a_record_sees_a_complete_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Another run reading the workspace while this one records into it: rewriting the manifest
    # in place let that reader parse an empty or half-written file (JSONDecodeError).
    workspace = tmp_path / "workspace"
    _record(workspace, "first")
    seen: list[list[str]] = []
    real_replace = os.replace

    def replace_then_read(source: str | Path, target: str | Path) -> None:
        if Path(target).name == "manifest.json":
            # The new manifest is complete in its temp file; the old one is still in place.
            assert json.loads(Path(source).read_text(encoding="utf-8"))["runs"]
            manifest = evidence_workspace.load_workspace_manifest(workspace)
            seen.append([run["scope"] for run in manifest["runs"]])
        real_replace(source, target)

    monkeypatch.setattr(atomicio.os, "replace", replace_then_read)

    _record(workspace, "second")

    assert seen == [["first"]]
    scopes = [run["scope"] for run in evidence_workspace.load_workspace_manifest(workspace)["runs"]]
    assert scopes == ["first", "second"]
    assert not list(workspace.glob("manifest.json.*")), "no temp file is left behind"
