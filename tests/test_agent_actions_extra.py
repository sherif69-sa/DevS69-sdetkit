from __future__ import annotations

from pathlib import Path

from sdetkit.agent.actions import ActionRegistry, maybe_parse_action_task


def test_maybe_parse_action_task_variants() -> None:
    assert maybe_parse_action_task("noop") is None
    assert maybe_parse_action_task("action fs.read") == ("fs.read", {})
    assert maybe_parse_action_task("action x 1") == ("x", {"value": 1})
    assert maybe_parse_action_task("action x [1,2]") == ("x", {"value": [1, 2]})


def test_action_registry_error_paths(tmp_path: Path, monkeypatch) -> None:
    reg = ActionRegistry(
        root=tmp_path, write_allowlist=("allowed",), shell_allowlist=("python -c",)
    )

    assert reg.run("missing", {}).ok is False
    assert reg.run("fs.read", {"path": "/abs"}).ok is False
    assert reg.run("fs.write", {"path": "denied/out.txt", "content": "x"}).ok is False
    assert reg.run("shell.run", {"cmd": ""}).ok is False
    assert reg.run("shell.run", {"cmd": 'python -c "x'}).ok is False

    class _P:
        returncode = 1
        stdout = ""
        stderr = "bad"

    monkeypatch.setattr("subprocess.run", lambda *a, **k: _P())
    res = reg.run("shell.run", {"cmd": 'python -c "print(1)"'})
    assert res.ok is False

    import pytest

    with pytest.raises(ValueError):
        reg.run("report.build", {"output": "/abs/path.html", "format": "html"})
