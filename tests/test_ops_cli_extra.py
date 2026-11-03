from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit import ops


def _write_minimal_workflow(path: Path) -> None:
    path.write_text(
        """
[workflow]
name = "mini"
version = "1"
[[workflow.steps]]
id = "a"
type = "write_file"
inputs = { path = "a.txt", text = "ok" }
""",
        encoding="utf-8",
    )


def test_sanitize_workflow_filename_accepts_and_rejects() -> None:
    assert ops._sanitize_workflow_filename(Path("wf.toml")) == "wf.toml"
    with pytest.raises(ValueError):
        ops._sanitize_workflow_filename(Path("nested/wf.toml"))
    with pytest.raises(ValueError):
        ops._sanitize_workflow_filename(Path("wf.exe"))


def test_main_list_and_init_template(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert ops.main(["list", "--history-dir", "."]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == {"runs": []}

    out = tmp_path / "templates" / "quick.toml"
    with pytest.raises(ValueError, match="unknown template"):
        ops.main(["init-template", "quickstart", "--output", str(out)])


def test_main_run_replay_and_diff_json(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    wf = Path("wf.toml")
    _write_minimal_workflow(wf)

    assert (
        ops.main(
            [
                "run",
                "wf.toml",
                "--inputs",
                "{}",
                "--artifacts-dir",
                "art",
                "--history-dir",
                ".",
            ]
        )
        == 0
    )
    first = json.loads(capsys.readouterr().out)

    with pytest.raises(ValueError, match="relative"):
        ops.main(["replay", first["run_id"], "--history-dir", "."])

    assert (
        ops.main(
            ["diff", first["run_id"], first["run_id"], "--history-dir", ".", "--format", "json"]
        )
        == 0
    )
    diff = json.loads(capsys.readouterr().out)
    assert diff["changed_steps"] == []


def test_main_run_rejects_non_object_inputs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    wf = Path("wf.toml")
    _write_minimal_workflow(wf)

    with pytest.raises(ValueError, match="JSON object"):
        ops.main(["run", "wf.toml", "--inputs", "[]"])


def test_main_run_fail_fast_stops_and_exits_non_zero(tmp_path: Path, monkeypatch, capsys) -> None:
    import sys

    monkeypatch.chdir(tmp_path)
    fail = json.dumps([sys.executable, "-c", "raise SystemExit(3)"])
    Path("wf.toml").write_text(
        f"""
[workflow]
name = "fails"
version = "1"
[[workflow.steps]]
id = "a_fail"
type = "command"
inputs = {{ cmd = {fail} }}
[[workflow.steps]]
id = "b_other"
type = "write_file"
inputs = {{ path = "b.txt", text = "ran" }}
""",
        encoding="utf-8",
    )

    rc = ops.main(
        [
            "run",
            "wf.toml",
            "--inputs",
            "{}",
            "--artifacts-dir",
            "art",
            "--history-dir",
            ".",
            "--workers",
            "1",
            "--fail-fast",
        ]
    )
    out = json.loads(capsys.readouterr().out)

    assert rc == 1
    assert out["status"] == "error"
    assert list(out["steps"]) == ["a_fail"]
