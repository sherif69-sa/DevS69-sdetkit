from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "sdetkit", *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


def test_patch_workbench_operator_json_schema_and_keys(tmp_path: Path) -> None:
    plan = {
        "source_risks": [{"file": "src/a.py", "kind": "source", "severity": "major"}],
        "patch_candidates": [{"title": "Fix A", "reason": "risk", "files": ["src/a.py"]}],
        "validation_commands": ["python -m pytest -q"],
        "evidence_paths": ["build/release-room/plan.json"],
    }
    in_file = tmp_path / "plan.json"
    in_file.write_text(json.dumps(plan), encoding="utf-8")
    proc = _run(
        "patch", "workbench", ".", "--from-release-room", str(in_file), "--format", "operator-json"
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["schema_version"] == "sdetkit.patch.workbench.v1"
    assert list(payload.keys()) == sorted(payload.keys())
    assert payload["candidate_count"] == 1
    assert payload["candidates"][0]["validation_commands"] == ["python -m pytest -q"]


def test_patch_workbench_text_respects_cap_and_filters_generated(tmp_path: Path) -> None:
    plan = {
        "source_risks": [
            {"file": "build/out.txt", "kind": "generated_artifact"},
            {"file": "src/good.py", "kind": "source"},
        ],
        "patch_candidates": [
            {"title": f"C{i}", "reason": "r", "files": ["src/good.py"]} for i in range(7)
        ],
    }
    in_file = tmp_path / "plan.json"
    in_file.write_text(json.dumps(plan), encoding="utf-8")
    proc = _run(
        "patch",
        "workbench",
        ".",
        "--from-release-room",
        str(in_file),
        "--max-candidates",
        "5",
        "--format",
        "text",
    )
    assert proc.returncode == 0
    assert proc.stdout.count("- cand-") == 5


def test_patch_workbench_missing_or_invalid_json_is_deterministic_error(tmp_path: Path) -> None:
    missing = _run(
        "patch",
        "workbench",
        ".",
        "--from-release-room",
        str(tmp_path / "nope.json"),
        "--format",
        "operator-json",
    )
    assert missing.returncode != 0
    mp = json.loads(missing.stdout)
    assert mp["code"] == "PATCH_WORKBENCH_INPUT_UNREADABLE"

    bad = tmp_path / "bad.json"
    bad.write_text("{", encoding="utf-8")
    invalid = _run(
        "patch", "workbench", ".", "--from-release-room", str(bad), "--format", "operator-json"
    )
    assert invalid.returncode != 0
    ip = json.loads(invalid.stdout)
    assert ip["code"] == "PATCH_WORKBENCH_INPUT_INVALID_JSON"


def test_patch_workbench_does_not_modify_files(tmp_path: Path) -> None:
    plan = {"patch_candidates": [{"title": "x", "files": ["src/x.py"]}]}
    in_file = tmp_path / "plan.json"
    marker = tmp_path / "marker.txt"
    marker.write_text("same", encoding="utf-8")
    before = marker.read_text(encoding="utf-8")
    in_file.write_text(json.dumps(plan), encoding="utf-8")
    proc = _run("patch", "workbench", ".", "--from-release-room", str(in_file), "--format", "text")
    assert proc.returncode == 0
    assert marker.read_text(encoding="utf-8") == before
