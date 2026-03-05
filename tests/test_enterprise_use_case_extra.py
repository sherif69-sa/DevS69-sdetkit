from __future__ import annotations

import json
import subprocess
from pathlib import Path

from sdetkit import enterprise_use_case as euc


def test_write_defaults_noop_when_page_is_already_valid(tmp_path: Path) -> None:
    page = tmp_path / "docs/use-cases-enterprise-regulated.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(euc._DAY13_DEFAULT_PAGE, encoding="utf-8")

    touched = euc._write_defaults(tmp_path)

    assert touched == []


def test_execute_commands_timeout_and_markdown_output(monkeypatch, tmp_path: Path, capsys) -> None:
    page = tmp_path / "docs/use-cases-enterprise-regulated.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(euc._DAY13_DEFAULT_PAGE, encoding="utf-8")

    def _raise_timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=1, output="", stderr="late")

    monkeypatch.setattr(euc.subprocess, "run", _raise_timeout)

    out_file = tmp_path / "artifacts/day13.md"
    rc = euc.main(
        [
            "--root",
            str(tmp_path),
            "--execute",
            "--evidence-dir",
            "docs/evidence",
            "--format",
            "markdown",
            "--output",
            str(out_file),
            "--strict",
            "--timeout-sec",
            "1",
        ]
    )
    assert rc == 1
    stdout = capsys.readouterr().out
    assert "## Execution summary" in stdout
    assert out_file.exists()

    summary = json.loads((tmp_path / "docs/evidence/day13-execution-summary.json").read_text())
    assert summary["failed_commands"] == summary["total_commands"]
