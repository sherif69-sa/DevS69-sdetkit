from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from sdetkit import cli


def test_importing_cli_does_not_eager_import_heavy_command_modules() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    env = {**os.environ, "PYTHONPATH": str(repo_root / "src")}
    script = """
import sys
import sdetkit.cli  # noqa: F401
assert "sdetkit.repo" not in sys.modules
assert "sdetkit.report" not in sys.modules
assert "sdetkit.patch" not in sys.modules
"""
    proc = subprocess.run(
        [sys.executable, "-c", script],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr


def test_run_module_main_imports_target_module_on_demand(monkeypatch) -> None:
    called: dict[str, list[str]] = {}

    def _fake_main(args: list[str]) -> int:
        called["args"] = args
        return 0

    def _fake_import(name: str) -> SimpleNamespace:
        assert name == "sdetkit.fake_command"
        return SimpleNamespace(main=_fake_main)

    monkeypatch.setattr(cli, "import_module", _fake_import)

    rc = cli._run_module_main("sdetkit.fake_command", ("--flag", "value"))
    assert rc == 0
    assert called["args"] == ["--flag", "value"]
