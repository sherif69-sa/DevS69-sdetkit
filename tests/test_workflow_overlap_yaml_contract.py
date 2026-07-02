from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_workflow_overlap_report.py"


def test_workflow_event_key_is_preserved(tmp_path: Path) -> None:
    spec = importlib.util.spec_from_file_location("workflow_overlap", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    workflow = tmp_path / "workflow.yml"
    workflow.write_text(
        "name: Example\non:\n  pull_request:\n  push:\njobs: {}\n",
        encoding="utf-8",
    )

    loaded = module._load_workflow(workflow)

    assert module._triggers(loaded) == ["pull_request", "push"]
