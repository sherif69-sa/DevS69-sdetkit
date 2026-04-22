from __future__ import annotations

import json
import zipfile
from pathlib import Path

from sdetkit import forensics


def _write_run(path: Path, *, status: str = "ok") -> None:
    payload = {
        "schema_version": "sdetkit.run-record.v1",
        "summary": {"status": status},
        "findings": [],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_forensics_bundle_and_bundle_diff(tmp_path: Path) -> None:
    run_path = tmp_path / "run.json"
    _write_run(run_path)
    include_file = tmp_path / "notes.txt"
    include_file.write_text("forensics-notes", encoding="utf-8")
    bundle_a = tmp_path / "a.zip"
    bundle_b = tmp_path / "b.zip"

    payload = forensics._bundle(
        run_path,
        bundle_a,
        include=[str(include_file), str(tmp_path / "missing.txt")],
    )
    assert payload["schema_version"] == "sdetkit.forensics.bundle.v1"
    extras = payload["manifest"]["extras"]
    assert any(item["status"] == "included" for item in extras)
    assert any(item["status"] == "missing" for item in extras)

    _ = forensics._bundle(run_path, bundle_b, include=[])
    diff = forensics._bundle_diff(bundle_a, bundle_b)
    assert diff["summary"]["passed"] is False
    assert "manifest.json" in diff["changed"] or diff["added"] or diff["removed"]

    with zipfile.ZipFile(bundle_a, "r") as zf:
        assert "run.json" in zf.namelist()
        assert "manifest.json" in zf.namelist()


def test_forensics_compare_and_main_paths(tmp_path: Path, capsys) -> None:
    run_a = tmp_path / "run-a.json"
    run_b = tmp_path / "run-b.json"
    _write_run(run_a)
    _write_run(run_b)

    cmp_payload = forensics._compare(run_a, run_b)
    assert cmp_payload["schema_version"] == "sdetkit.forensics.compare.v1"
    assert "regression_summary" in cmp_payload

    rc = forensics.main(
        [
            "compare",
            "--from",
            str(run_a),
            "--to",
            str(run_b),
            "--fail-on",
            "none",
        ]
    )
    assert rc == 0
    assert "schema_version" in capsys.readouterr().out

    bundle = tmp_path / "bundle.zip"
    rc = forensics.main(["bundle", "--run", str(run_b), "--output", str(bundle)])
    assert rc == 0
    capsys.readouterr()

    rc = forensics.main(["bundle-diff", "--from-bundle", str(bundle), "--to-bundle", str(bundle)])
    assert rc == 0

    rc = forensics.main(
        ["bundle", "--run", str(tmp_path / "missing.json"), "--output", str(bundle)]
    )
    assert rc == 2
    assert "forensics error:" in capsys.readouterr().err


def test_forensics_main_fail_on_modes(monkeypatch, tmp_path: Path, capsys) -> None:
    run_a = tmp_path / "run-a.json"
    run_b = tmp_path / "run-b.json"
    _write_run(run_a)
    _write_run(run_b)

    monkeypatch.setattr(
        forensics,
        "_compare",
        lambda *_a, **_k: {
            "new": [{"severity": "warn"}, {"severity": "error"}],
            "summary": {},
            "counts": {},
            "schema_version": "sdetkit.forensics.compare.v1",
            "regression_summary": {},
            "next_step": "x",
        },
    )
    rc = forensics.main(["compare", "--from", str(run_a), "--to", str(run_b), "--fail-on", "warn"])
    assert rc == 1
    capsys.readouterr()

    rc = forensics.main(["compare", "--from", str(run_a), "--to", str(run_b), "--fail-on", "error"])
    assert rc == 1
