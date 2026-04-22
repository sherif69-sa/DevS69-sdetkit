from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit.ops import ops


def test_parse_http_path_and_safe_run_id() -> None:
    path, query = ops._parse_http_path("/runs/abc-123?x=1&x=2&empty=")
    assert path == "/runs/abc-123"
    assert query == {"x": ["1", "2"], "empty": [""]}

    assert ops._safe_run_id("/runs/abc-123") == "abc-123"
    assert ops._safe_run_id("/runs/../etc/passwd") is None
    assert ops._safe_run_id("/health") is None


def test_validate_run_id_rejects_invalid_value() -> None:
    with pytest.raises(ValueError, match="invalid run id"):
        ops._validate_run_id("bad/run")


def test_interpolate_nested_list_and_dict_values() -> None:
    ctx = {"input": {"name": "proj"}, "step": {"prep": {"count": 3}}}
    payload = {
        "title": "${input.name}",
        "items": ["n=${step.prep.count}", {"v": "${input.name}-${step.prep.count}"}],
    }

    out = ops._interpolate(payload, ctx)

    assert out == {"title": "proj", "items": ["n=3", {"v": "proj-3"}]}


def test_interpolate_unknown_key_raises() -> None:
    with pytest.raises(ValueError, match="unknown interpolation variable"):
        ops._interpolate("${step.missing.value}", {"step": {}})


def _write_run(history_dir: Path, run_id: str, results: dict[str, object]) -> None:
    run_dir = history_dir / ".sdetkit" / "ops-history" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run.json").write_text(json.dumps({"run_id": run_id}), encoding="utf-8")
    (run_dir / "results.json").write_text(json.dumps(results), encoding="utf-8")


def test_diff_runs_normalizes_artifact_paths_and_findings_order(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    history = tmp_path
    _write_run(
        history,
        "run-a",
        {
            "workflow_name": "wf",
            "status": "ok",
            "steps": {
                "scan": {
                    "step_id": "scan",
                    "type": "python_call",
                    "status": "ok",
                    "inputs": {},
                    "outputs": {"findings": [{"id": 1}, {"id": 2}]},
                    "findings": [{"msg": "b"}, {"msg": "a"}],
                },
                "write": {
                    "step_id": "write",
                    "type": "write_file",
                    "status": "ok",
                    "inputs": {},
                    "outputs": {
                        "path": str(history / ".sdetkit" / "ops-history" / "run-a" / "artifacts" / "out.txt"),
                        "sha256": "x",
                    },
                    "findings": [],
                },
            },
            "artifacts": [{"path": "out.txt", "sha256": "x"}],
        },
    )
    _write_run(
        history,
        "run-b",
        {
            "workflow_name": "wf",
            "status": "ok",
            "steps": {
                "scan": {
                    "step_id": "scan",
                    "type": "python_call",
                    "status": "ok",
                    "inputs": {},
                    "outputs": {"findings": [{"id": 1}, {"id": 2}]},
                    "findings": [{"msg": "a"}, {"msg": "b"}],
                },
                "write": {
                    "step_id": "write",
                    "type": "write_file",
                    "status": "ok",
                    "inputs": {},
                    "outputs": {
                        "path": str(history / ".sdetkit" / "ops-replay-artifacts" / "out.txt"),
                        "sha256": "x",
                    },
                    "findings": [],
                },
            },
            "artifacts": [{"path": "out.txt", "sha256": "x"}],
        },
    )

    diff = ops.diff_runs(history, "run-a", "run-b")

    assert diff["changed_steps"] == []
    assert diff["changed_artifacts"] == []
    assert diff["audit_security_finding_delta"] == 0
