from __future__ import annotations

import json
from pathlib import Path

from sdetkit import adoption


def test_adoption_cli_json_output_with_missing_inputs(tmp_path: Path, capsys) -> None:
    rc = adoption.main(
        [
            "--fit",
            str(tmp_path / "missing-fit.json"),
            "--summary",
            str(tmp_path / "missing-summary.json"),
            "--format",
            "json",
        ]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["fit"] == "unknown"
    assert payload["decision"] == "NO-DATA"


def test_adoption_cli_writes_markdown(tmp_path: Path, capsys) -> None:
    out = tmp_path / "adoption.md"
    rc = adoption.main(
        [
            "--fit",
            str(tmp_path / "missing-fit.json"),
            "--summary",
            str(tmp_path / "missing-summary.json"),
            "--format",
            "md",
            "--out",
            str(out),
        ]
    )
    assert rc == 0
    _ = capsys.readouterr()
    assert out.exists()
    assert "# Adoption follow-up" in out.read_text(encoding="utf-8")
