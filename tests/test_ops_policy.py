from __future__ import annotations

from pathlib import Path

import pytest

from sdetkit.ops import run_workflow


def test_shell_blocked_by_default(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    wf = Path("wf.toml")
    wf.write_text(
        """
[workflow]
name = "policy"
version = "1"
[[workflow.steps]]
id = "cmd"
type = "command"
inputs = { cmd = ["echo", "ok"], shell = true }
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        run_workflow(
            wf,
            inputs={},
            artifacts_dir=Path("a"),
            history_dir=Path("h"),
            workers=1,
            dry_run=False,
            fail_fast=False,
        )
