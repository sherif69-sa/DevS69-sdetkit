from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit.ops import _interpolate, _load_workflow, _resolve_order, diff_runs, run_workflow
from sdetkit.security import SecurityError


def test_workflow_parse_toml_and_json(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    toml_path = Path("wf.toml")
    toml_path.write_text(
        """
[workflow]
name = "x"
version = "1"
[[workflow.steps]]
id = "a"
type = "write_file"
inputs = { path = "a.txt", text = "ok" }
""",
        encoding="utf-8",
    )
    wf = _load_workflow(toml_path)
    assert wf.name == "x"

    json_path = Path("wf.json")
    json_path.write_text(
        json.dumps(
            {
                "workflow": {
                    "name": "x",
                    "version": "1",
                    "steps": [{"id": "a", "type": "write_file", "inputs": {"path": "a.txt"}}],
                }
            }
        ),
        encoding="utf-8",
    )
    wf2 = _load_workflow(json_path)
    assert wf2.name == "x"


def test_cycle_detection(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    path = Path("wf.toml")
    path.write_text(
        """
[workflow]
name = "c"
version = "1"
[[workflow.steps]]
id = "a"
type = "write_file"
depends_on = ["b"]
[[workflow.steps]]
id = "b"
type = "write_file"
depends_on = ["a"]
""",
        encoding="utf-8",
    )
    try:
        _load_workflow(path)
    except ValueError as exc:
        assert "cycle" in str(exc)
    else:
        raise AssertionError("expected cycle")


def test_variable_interpolation() -> None:
    out = _interpolate(
        "${input.name}-${step.s1.value}", {"input": {"name": "n"}, "step": {"s1": {"value": "v"}}}
    )
    assert out == "n-v"


def test_deterministic_results_workers(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    path = Path("wf.toml")
    path.write_text(
        """
[workflow]
name = "det"
version = "1"
[[workflow.steps]]
id = "a"
type = "write_file"
inputs = { path = "a.txt", text = "A" }
[[workflow.steps]]
id = "b"
type = "write_file"
inputs = { path = "b.txt", text = "B" }
[[workflow.steps]]
id = "c"
type = "write_file"
depends_on = ["a", "b"]
inputs = { path = "c.txt", text = "C" }
""",
        encoding="utf-8",
    )
    r1 = run_workflow(
        path,
        inputs={},
        artifacts_dir=Path("a1"),
        history_dir=Path("h1"),
        workers=1,
        dry_run=False,
        fail_fast=False,
    )
    r2 = run_workflow(
        path,
        inputs={},
        artifacts_dir=Path("a2"),
        history_dir=Path("h2"),
        workers=4,
        dry_run=False,
        fail_fast=False,
    )
    assert (
        list(r1["steps"].keys()) == list(r2["steps"].keys()) == _resolve_order(_load_workflow(path))
    )


def test_history_replay_and_diff(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    path = Path("wf.toml")
    path.write_text(
        """
[workflow]
name = "h"
version = "1"
[[workflow.steps]]
id = "a"
type = "write_file"
inputs = { path = "a.txt", text = "hello" }
""",
        encoding="utf-8",
    )
    first = run_workflow(
        path,
        inputs={},
        artifacts_dir=Path("art"),
        history_dir=Path("."),
        workers=1,
        dry_run=False,
        fail_fast=False,
    )
    run_a = first["run_id"]
    second = run_workflow(
        path,
        inputs={},
        artifacts_dir=Path("art"),
        history_dir=Path("."),
        workers=1,
        dry_run=False,
        fail_fast=False,
    )
    run_b = second["run_id"]
    diff = diff_runs(Path("."), run_a, run_b)
    assert diff["changed_steps"] == []


def test_history_diff_detects_changed_artifact_content(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    path = Path("wf.toml")
    path.write_text(
        """
[workflow]
name = "h2"
version = "1"
[[workflow.steps]]
id = "a"
type = "write_file"
inputs = { path = "a.txt", text = "${input.text}" }
""",
        encoding="utf-8",
    )

    first = run_workflow(
        path,
        inputs={"text": "one"},
        artifacts_dir=Path("art"),
        history_dir=Path("."),
        workers=1,
        dry_run=False,
        fail_fast=False,
    )
    run_a = first["run_id"]

    second = run_workflow(
        path,
        inputs={"text": "two"},
        artifacts_dir=Path("art"),
        history_dir=Path("."),
        workers=1,
        dry_run=False,
        fail_fast=False,
    )
    run_b = second["run_id"]

    diff = diff_runs(Path("."), run_a, run_b)
    assert diff["changed_steps"] == ["a"]
    assert diff["changed_artifacts"] == ["a.txt"]


def test_load_run_rejects_invalid_id(tmp_path: Path) -> None:
    from sdetkit.ops import load_run

    with pytest.raises(ValueError):
        load_run(tmp_path, "../bad")


def test_run_workflow_rejects_traversal_path(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    bad = Path(*("..", "outside.toml"))
    with pytest.raises((ValueError, SecurityError)):
        run_workflow(
            bad,
            inputs={},
            artifacts_dir=Path("a"),
            history_dir=Path("h"),
            workers=1,
            dry_run=False,
            fail_fast=False,
        )


def test_run_workflow_rejects_absolute_path(tmp_path: Path) -> None:
    wf = tmp_path / "wf.toml"
    wf.write_text(
        """
[workflow]
name = "x"
version = "1"
[[workflow.steps]]
id = "a"
type = "write_file"
inputs = { path = "a.txt", text = "ok" }
""",
        encoding="utf-8",
    )
    with pytest.raises((ValueError, SecurityError)):
        run_workflow(
            wf.resolve(),
            inputs={},
            artifacts_dir=Path("a"),
            history_dir=Path("h"),
            workers=1,
            dry_run=False,
            fail_fast=False,
        )


def test_run_workflow_allows_nested_relative_path(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "wf.toml").write_text(
        '[workflow]\nname="x"\nversion="1"\n', encoding="utf-8"
    )
    out = run_workflow(
        Path("nested/wf.toml"),
        inputs={},
        artifacts_dir=Path("a"),
        history_dir=Path("h"),
        workers=1,
        dry_run=False,
        fail_fast=False,
    )
    assert out["workflow_name"] == "x"
